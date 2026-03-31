
from flask import Flask, request
import requests
import os

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        # 👉 запрос к AI
        ai_response = ask_ai(text)

        # 👉 отправка ответа в Telegram
        requests.post(TELEGRAM_URL, json={
            "chat_id": chat_id,
            "text": ai_response
        })

    return "ok"


def ask_ai(user_text):
    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Ты — Кузя. Живой, спокойный, дружелюбный ассистент. Говоришь просто и по делу."},
            {"role": "user", "content": user_text}
        ]
    }

    response = requests.post(url, headers=headers, json=data)

    try:
        return response.json()["choices"][0]["message"]["content"]
    except:
        return "Что-то пошло не так 😅"

@app.route('/health')
def health():
    return "ok"
