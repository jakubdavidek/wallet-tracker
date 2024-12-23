from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv

# Load API keys from .env
load_dotenv()

app = Flask(__name__)

# Function to fetch USD price of a cryptocurrency
def get_usd_price(crypto):
    try:
        response = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={crypto}&vs_currencies=usd")
        if response.status_code == 200:
            return response.json().get(crypto, {}).get("usd")
    except Exception as e:
        print(f"Error fetching USD price for {crypto}: {e}")
    return None

# Ethereum API integration
def get_ethereum_data(wallet_address):
    try:
        api_url = "https://api.etherscan.io/api"
        eth_usd_price = get_usd_price("ethereum")

        # Fetch balance
        balance_params = {
            "module": "account",
            "action": "balance",
            "address": wallet_address,
            "tag": "latest",
            "apikey": os.getenv('ETH_API_KEY')
        }
        transactions_params = {
            "module": "account",
            "action": "txlist",
            "address": wallet_address,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "desc",
            "apikey": os.getenv('ETH_API_KEY')
        }

        # Get balance
        balance_response = requests.get(api_url, params=balance_params)
        if balance_response.status_code != 200 or "result" not in balance_response.json():
            return {"error": f"Error fetching Ethereum balance: {balance_response.text}"}
        balance_eth = int(balance_response.json().get("result", 0)) / 1e18

        # Get transactions
        transactions_response = requests.get(api_url, params=transactions_params)
        if transactions_response.status_code != 200 or "result" not in transactions_response.json():
            return {"error": f"Error fetching Ethereum transactions: {transactions_response.text}"}
        transactions = []
        for tx in transactions_response.json().get("result", [])[:10]:
            amount_eth = int(tx.get("value", 0)) / 1e18
            amount_usd = amount_eth * eth_usd_price if eth_usd_price else "N/A"
            transactions.append({
                "time": int(tx.get("timeStamp", 0)),
                "amount": amount_eth,
                "amount_usd": amount_usd,
                "hash": tx.get("hash"),
            })

        return {"balance": balance_eth, "transactions": transactions}
    except Exception as e:
        return {"error": f"Error fetching Ethereum data: {str(e)}"}

# Bitcoin API integration using BlockCypher
def get_bitcoin_data(wallet_address):
    try:
        api_url = f"https://api.blockcypher.com/v1/btc/main/addrs/{wallet_address}/full"
        btc_usd_price = get_usd_price("bitcoin")

        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            balance_btc = data.get("balance", 0) / 1e8
            transactions = []
            
            for tx in data.get("txs", [])[:10]:
                # Extract the time from the "confirmed" field if it exists
                confirmed_time = tx.get("confirmed")
                if confirmed_time:
                    # Parse the confirmed timestamp to UNIX time (seconds since epoch)
                    from datetime import datetime
                    parsed_time = int(datetime.strptime(confirmed_time, "%Y-%m-%dT%H:%M:%SZ").timestamp())
                else:
                    parsed_time = None

                transactions.append({
                    "time": parsed_time,
                    "amount": sum(output.get("value", 0) for output in tx.get("outputs", [])) / 1e8,
                    "amount_usd": (sum(output.get("value", 0) for output in tx.get("outputs", [])) / 1e8) * btc_usd_price if btc_usd_price else "N/A",
                    "hash": tx.get("hash"),
                })

            return {"balance": balance_btc, "transactions": transactions}
        else:
            return {"error": f"Error fetching Bitcoin data: {response.status_code} {response.text}"}
    except Exception as e:
        return {"error": f"Error fetching Bitcoin data: {str(e)}"}


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/wallet', methods=['POST'])
def get_wallet_data():
    wallet_address = request.form.get('wallet_address', '').strip()
    response = {"errors": {}, "ethereum": None, "bitcoin": None}

    try:
        if wallet_address.startswith("0x") and len(wallet_address) == 42:
            eth_data = get_ethereum_data(wallet_address)
            if "error" in eth_data:
                response["errors"]["ethereum"] = eth_data["error"]
            else:
                response["ethereum"] = eth_data
        elif wallet_address.startswith(("1", "3", "bc1")):
            btc_data = get_bitcoin_data(wallet_address)
            if "error" in btc_data:
                response["errors"]["bitcoin"] = btc_data["error"]
            else:
                response["bitcoin"] = btc_data
        else:
            response["errors"]["general"] = "Invalid wallet address format."
    except Exception as e:
        response["errors"]["general"] = f"Unexpected error occurred: {str(e)}"

    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
