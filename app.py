from flask import Flask, request
import requests
import os
import json
import sqlite3

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# ======================
# 🧠 SQLITE ПАМЯТЬ
# ======================
conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    chat_id TEXT PRIMARY KEY,
    data TEXT
)
""")
conn.commit()

# ======================
# 🧠 USER
# ======================
def get_user(chat_id):
    chat_id = str(chat_id)

    cursor.execute("SELECT data FROM users WHERE chat_id=?", (chat_id,))
    row = cursor.fetchone()

    if row:
        user = json.loads(row[0])
    else:
        user = {
            "profile": {"name": None},
            "history": []
        }

    return user


def save_user(chat_id, user):
    cursor.execute(
        "INSERT OR REPLACE INTO users (chat_id, data) VALUES (?, ?)",
        (str(chat_id), json.dumps(user))
    )
    conn.commit()

# ======================
# 🔒 ЗАЩИТА
# ======================
last_messages = {}
processing_lock = {}

def is_duplicate(chat_id, message_id):
    chat_id = str(chat_id)

    if chat_id not in last_messages:
        last_messages[chat_id] = set()

    if message_id in last_messages[chat_id]:
        return True

    last_messages[chat_id].add(message_id)
    return False


def is_processing(chat_id):
    if processing_lock.get(chat_id):
        return True

    processing_lock[chat_id] = True
    return False


def release_processing(chat_id):
    processing_lock[chat_id] = False

# ======================
# 📤 ОТПРАВКА
# ======================
def send_reply(chat_id, text):
    if not text:
        return

    if len(text) > 2000:
        text = text[:2000]

    requests.post(TELEGRAM_URL, json={
        "chat_id": chat_id,
        "text": text
    })

# ======================
# 🧠 HISTORY
# ======================
def update_history(user, role, text):
    user["history"].append({"role": role, "content": text})

    if len(user["history"]) > 20:
        user["history"] = user["history"][-10:]

# ======================
# 🤖 AI
# ======================
def ask_ai(user, user_text):

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""
Ты — Кузя.

Ты живой собеседник.

ПАМЯТЬ:
{json.dumps(user["profile"], ensure_ascii=False)}

ПРАВИЛА:
— если знаешь имя → всегда используй
— если пользователь сообщает имя → ответь "Запомнил."
— если спрашивает имя → ответь точно
— не придумывай
— говори естественно
"""

    messages = [{"role": "system", "content": system_prompt}] + user["history"]
    messages.append({"role": "user", "content": user_text})

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.5
    }

    try:
        r = requests.post(url, headers=headers, json=data)

        if r.status_code != 200:
            return "Ошибка API"

        return r.json()["choices"][0]["message"]["content"]

    except:
        return "Сбой"

# ======================
# 🔥 WEBHOOK
# ======================
@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    message_id = data["message"]["message_id"]
    text = data["message"].get("text", "")

    if is_duplicate(chat_id, message_id):
        return "ok"

    if is_processing(chat_id):
        return "ok"

    try:
        user = get_user(chat_id)

        update_history(user, "user", text)

        # 🔥 СОХРАНЕНИЕ ИМЕНИ (СРАЗУ)
        if "меня зовут" in text.lower():
            parts = text.lower().split("меня зовут")
            if len(parts) > 1:
                words = parts[1].strip().split()
                if words:
                    user["profile"]["name"] = words[0].capitalize()
                    save_user(chat_id, user)

        # 🔥 ЕСЛИ СПРАШИВАЕТ ИМЯ
        t = text.lower().strip()

if (
    "как меня зовут" in t
    or "напомни имя" in t
    or "моё имя" in t
    or ("зовут" in t and "меня" in t)
):
            name = user["profile"].get("name")

            if name:
                reply = f"Тебя зовут {name}."
            else:
                reply = "Скажи имя, я запомню."

            send_reply(chat_id, reply)
            update_history(user, "assistant", reply)
            save_user(chat_id, user)
            return "ok"

        # 🤖 AI
        reply = ask_ai(user, text)

        send_reply(chat_id, reply)
        update_history(user, "assistant", reply)
        save_user(chat_id, user)

    finally:
        release_processing(chat_id)

    return "ok"

# ======================
# 🔥 HEALTH
# ======================
@app.route('/health')
def health():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
