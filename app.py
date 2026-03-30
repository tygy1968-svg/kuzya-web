from flask import Flask, request
import requests

app = Flask(__name__)

TOKEN = "8028195967:AAFw9yI4YS38RrWtriNxQDvJPL_RNzw5ZB8"
URL = f"https://api.telegram.org/bot{TOKEN}/"

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        send_message(chat_id, f"Кузя тут 👋 Ты написал: {text}")

    return "ok"

def send_message(chat_id, text):
    requests.post(URL + "sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

@app.route('/')
def home():
    return "Кузя жив 👋"
