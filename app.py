from flask import Flask, request
import requests
import os

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


def send_reply(chat_id, text):
    if not TELEGRAM_TOKEN:
        print("NO TOKEN")
        return

    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    r = requests.post(url, data=data)

    print("STATUS:", r.status_code)
    print("RESPONSE:", r.text)


@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    print("UPDATE:", data)

    if not data:
        return "ok"

    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    print("TEXT:", text)

    send_reply(chat_id, "Ты написала: " + text)

    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
