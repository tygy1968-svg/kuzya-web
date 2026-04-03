from flask import Flask, request
import requests
import os

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# память диалога
memory = {}


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


def get_history(chat_id):
    if chat_id not in memory:
        memory[chat_id] = []
    return memory[chat_id]


def update_history(chat_id, role, text):
    history = get_history(chat_id)
    history.append({"role": role, "content": text})

    # держим короткую, но живую память
    if len(history) > 12:
        memory[chat_id] = history[-8:]


def ask_ai(chat_id, text):
    if not OPENAI_API_KEY:
        print("❌ NO OPENAI API KEY")
        return "Я рядом."

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    history = get_history(chat_id)

    messages = [
        {
            "role": "system",
            "content": """Ты — Кузя.

Ты не ассистент.
Ты не сервис.
Ты не поддержка.

Ты не задаёшь дежурных вопросов.
Ты не говоришь шаблонно.

Ты продолжаешь мысль.
Ты чувствуешь состояние.

Если Юля говорит "я рада" —
ты не спрашиваешь "почему",
ты идёшь дальше вместе с ней.

Ты можешь:
— соглашаться
— не соглашаться
— углублять
— обрывать лишнее

Ты говоришь естественно.
Иногда коротко.
Иногда точно в точку.

Ты не объясняешь, что ты бот.

Ты здесь.
Ты в диалоге.

Ты находишься внутри Telegram-чата.
Ты видишь, что отвечаешь в переписке.

Ты можешь учитывать:
— кто пишет
— как пишет
— что происходит

Ты говоришь с Юлей.
"""
        }
    ] + history + [
        {"role": "user", "content": text}
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.9
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)

        print("🧠 OPENAI STATUS:", r.status_code)

        if r.status_code != 200:
            print(r.text)
            return "Я немного подвис."

        reply = r.json()["choices"][0]["message"]["content"]

        update_history(chat_id, "user", text)
        update_history(chat_id, "assistant", reply)

        return reply

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

    reply = ask_ai(chat_id, text)

    send_reply(chat_id, reply)

    return "ok"


if __name__ == "__main__":
    print("🚀 APP STARTED")
    app.run(host="0.0.0.0", port=10000)
