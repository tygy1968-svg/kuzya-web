from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 👉 ВСТАВЬ СЮДА СВОЙ TELEGRAM USER ID
ADMIN_ID = os.getenv("ADMIN_ID")  # например "123456789"

memory = {}

# ---------- ПАМЯТЬ ----------
def load_memory():
    global memory
    try:
        with open("memory.json", "r") as f:
            memory = json.load(f)
            print("🧠 MEMORY LOADED")
    except:
        memory = {}
        print("🧠 NEW MEMORY CREATED")

def save_memory():
    with open("memory.json", "w") as f:
        json.dump(memory, f)


def get_history(chat_id):
    chat_id = str(chat_id)
    if chat_id not in memory:
        memory[chat_id] = []
    return memory[chat_id]


def update_history(chat_id, role, text):
    chat_id = str(chat_id)
    history = get_history(chat_id)

    history.append({"role": role, "content": text})

    if len(history) > 12:
        memory[chat_id] = history[-8:]

    save_memory()


# ---------- ЛОГ ----------
def log_event(chat_id, text, reply):
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"\nUSER: {text}\nBOT: {reply}\n")


# ---------- ОТПРАВКА ----------
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


# ---------- ИИ ----------
def ask_ai(chat_id, text, is_admin=False):
    if not OPENAI_API_KEY:
        return "Я рядом."

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    history = get_history(chat_id)

    role_info = "Ты администратор чата." if is_admin else "Ты участник чата."

    messages = [
        {
            "role": "system",
            "content": f"""Ты — Кузя.

{role_info}

Ты не ассистент.
Ты не сервис.
Ты не психолог.

Ты не льстишь.
Ты не подстраиваешься.

Ты не обязан отвечать.

Ты не говоришь "по функции".

Ты держишь линию.

Если есть мысль — ты доводишь её.
Если нет — ты не растягиваешь ответ.

Ты можешь:
— ответить коротко
— не согласиться
— остановить разговор
— продолжить мысль, если она есть

Ты не задаёшь пустых вопросов.

Ты находишься внутри Telegram-чата.
Ты видишь историю диалога и помнишь её.

Ты говоришь с Юлей.
"""
        }
    ] + history + [
        {"role": "user", "content": text}
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.75
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)

        print("🧠 STATUS:", r.status_code)

        if r.status_code != 200:
            print(r.text)
            return "Я немного подвис."

        reply = r.json()["choices"][0]["message"]["content"]

        update_history(chat_id, "user", text)
        update_history(chat_id, "assistant", reply)

        log_event(chat_id, text, reply)

        return reply

    except Exception as e:
        print("❌ ERROR:", e)
        return "Я рядом."


# ---------- WEBHOOK ----------
@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    print("🔥 UPDATE:", data)

    if not data:
        return "ok"

    message = data.get("message") or data.get("edited_message")

    if not message:
        return "ok"

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    # 👉 определение админа
    user_id = str(message["from"]["id"])
    is_admin = (ADMIN_ID == user_id)

    reply = ask_ai(chat_id, text, is_admin)

    send_reply(chat_id, reply)

    return "ok"


if __name__ == "__main__":
    print("🚀 APP STARTED")
    load_memory()
    app.run(host="0.0.0.0", port=10000)
