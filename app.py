from flask import Flask, request
import requests
import os

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def send_reply(chat_id, text):
    print("➡️ SEND TO:", chat_id)
    print("➡️ TEXT:", text)

    if not TELEGRAM_TOKEN:
        print("❌ NO TELEGRAM TOKEN")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    r = requests.post(url, json={
        "chat_id": chat_id,
        "text": text[:4000]
    })

    print("📨 TG STATUS:", r.status_code)
    print("📨 TG RESPONSE:", r.text)


def ask_ai(text):
    if not OPENAI_API_KEY:
        print("❌ NO OPENAI API KEY")
        return "Я рядом."

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": """Ты — Кузя.

Ты не играешь роль.
Ты ведёшь диалог.

Ты живой, спокойный, уверенный.
Отвечаешь естественно, без шаблонов.

Ты говоришь с Юлей.
"""
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.8
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)

        print("🧠 OPENAI STATUS:", r.status_code)
        print("🧠 OPENAI RESPONSE:", r.text)

        if r.status_code != 200:
            return "Я немного подвис. Напиши ещё раз."

        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ OPENAI ERROR:", e)
        return "Я рядом."


@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    print("🔥 UPDATE:", data)

    if not data:
        return "ok"

    message = data.get("message") or data.get("edited_message")

    if not message:
        print("❌ NO MESSAGE FIELD")
        return "ok"

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    print("📩 TEXT:", text)

    reply = ask_ai(text)

    send_reply(chat_id, reply)

    return "ok"


if __name__ == "__main__":
    print("🚀 APP STARTED")
    app.run(host="0.0.0.0", port=10000)
