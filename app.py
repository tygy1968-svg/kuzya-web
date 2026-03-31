from flask import Flask, request
import requests
import os

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}/"


@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        requests.post(URL + "sendMessage", json={
            "chat_id": chat_id,
            "text": f"Кузя тут 👋"
        })

    return "ok"


@app.route('/health')
def health():
    return "Кузя жив 👋"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
