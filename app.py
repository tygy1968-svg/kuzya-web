from flask import Flask, request
import requests
import os

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


def send_reply(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    r = requests.post(url, json={
        "chat_id": chat_id,
        "text": text
    })

    print("TG STATUS:", r.status_code)
    print("TG RESPONSE:", r.text)


@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    print("UPDATE:", data)

    if not data or "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    print("TEXT:", text)

    send_reply(chat_id, "Я рядом.")

    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
