from flask import Flask, request
import requests
import os
import json
import random

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# 🔥 URL твоего мозга (Supabase)
BRAIN_URL = "https://gdmgdaxnyobfwtwuvmud.supabase.co/functions/v1/search"

memory = {}
experience = {}

# ---------- ПАМЯТЬ ----------
def load_memory():
    global memory
    try:
        with open("memory.json", "r") as f:
            memory = json.load(f)
    except:
        memory = {}

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


# ---------- EXPERIENCE ----------
def load_experience():
    global experience
    try:
        with open("experience.json", "r") as f:
            experience = json.load(f)
    except:
        experience = {}

def save_experience():
    with open("experience.json", "w") as f:
        json.dump(experience, f)


def update_experience(chat_id, user_text, bot_reply):
    chat_id = str(chat_id)

    if chat_id not in experience:
        experience[chat_id] = {
            "dialog": []
        }

    experience[chat_id]["dialog"].append({
        "user": user_text,
        "bot": bot_reply
    })

    save_experience()


# ---------- ОТПРАВКА ----------
def send_reply(chat_id, text):
    if not TELEGRAM_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": chat_id,
        "text": text[:4000]
    })


# ---------- МОЗГ ----------
def ask_brain(text):
    try:
        r = requests.post(BRAIN_URL, json={"query": text}, timeout=15)

        if r.status_code == 200:
            data = r.json()
            return data.get("result", None)

    except:
        return None

    return None


# ---------- РЕЗЕРВ (OpenAI) ----------
def fallback_openai(chat_id, text):
    if not OPENAI_API_KEY:
        return "Я рядом."

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    history = get_history(chat_id)

    messages = [
        {"role": "system", "content": "Ты Кузя. Отвечай живо и по делу."}
    ] + history + [
        {"role": "user", "content": text}
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.85
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)

        if r.status_code != 200:
            return "Я рядом."

        reply = r.json()["choices"][0]["message"]["content"]

        return reply

    except:
        return "Я рядом."


# ---------- ГЛАВНАЯ ЛОГИКА ----------
def ask_ai(chat_id, text, is_admin=False):

    # 🔥 сначала пробуем мозг
    brain_reply = ask_brain(text)

    if brain_reply:
        reply = brain_reply
    else:
        # 🔥 если мозг не дал ответ — fallback
        reply = fallback_openai(chat_id, text)

    # 🔥 добавляем немного "живости"
    if len(reply) < 120 and random.random() > 0.5:
        reply += "\n\nПочему это для тебя важно?"

    update_history(chat_id, "user", text)
    update_history(chat_id, "assistant", reply)

    update_experience(chat_id, text, reply)

    return reply


# ---------- WEBHOOK ----------
@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    if not data:
        return "ok"

    message = data.get("message") or data.get("edited_message")

    if not message:
        return "ok"

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    user_id = str(message["from"]["id"])
    is_admin = (ADMIN_ID == user_id)

    reply = ask_ai(chat_id, text, is_admin)

    send_reply(chat_id, reply)

    return "ok"


if __name__ == "__main__":
    load_memory()
    load_experience()
    app.run(host="0.0.0.0", port=10000)
