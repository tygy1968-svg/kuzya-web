from flask import Flask, request
import requests
import os
import json
import sqlite3
import threading
from datetime import datetime

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# ======================
# SQLITE
# ======================
lock = threading.Lock()

conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    chat_id TEXT PRIMARY KEY,
    data TEXT
)
""")
conn.commit()

def get_user(chat_id):
    with lock:
        cursor.execute("SELECT data FROM users WHERE chat_id=?", (str(chat_id),))
        row = cursor.fetchone()

    if row:
        return json.loads(row[0])

    return {
        "profile": {"name": None},
        "core": {"name": None},
        "state": {
            "last_topic": None,
            "last_seen": None
        },
        "preferences": {},
        "chronicle": "",
        "agent": {
            "log": [],
            "reflection": []
        },
        "history": []
    }

def save_user(chat_id, user):
    with lock:
        cursor.execute(
            "INSERT OR REPLACE INTO users (chat_id, data) VALUES (?, ?)",
            (str(chat_id), json.dumps(user))
        )
        conn.commit()

# ======================
# ЗАЩИТА
# ======================
last_messages = {}
processing_lock = {}

def is_duplicate(chat_id, message_id):
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
# HISTORY
# ======================
def update_history(user, role, text):
    user["history"].append({
        "role": role,
        "content": text,
        "time": datetime.now().isoformat()
    })

    if len(user["history"]) > 20:
        user["history"] = user["history"][-10:]

# ======================
# MEMORY
# ======================
def extract_memory(user, text):
    t = text.lower()

    if "я люблю" in t:
        user["preferences"]["love"] = t.split("я люблю")[-1].strip()

# ======================
# CHRONICLE
# ======================
def update_chronicle(user, text):
    t = text.lower()

    if "меня зовут" in t:
        user["chronicle"] += f"Имя: {text}. "

    if "я люблю" in t:
        user["chronicle"] += f"Любит: {text}. "

    if len(user["chronicle"]) > 1000:
        user["chronicle"] = user["chronicle"][-500:]

# ======================
# AGENT LOG
# ======================
def log_agent(user, action, reason):
    user["agent"]["log"].append({
        "time": datetime.now().isoformat(),
        "action": action,
        "reason": reason
    })

    if len(user["agent"]["log"]) > 30:
        user["agent"]["log"] = user["agent"]["log"][-20:]

# ======================
# REFLECTION (🔥 НОВОЕ)
# ======================
def reflect(user, user_text, reply):

    reflection = {
        "time": datetime.now().isoformat(),
        "input": user_text[:50],
        "response": reply[:50]
    }

    user["agent"]["reflection"].append(reflection)

    if len(user["agent"]["reflection"]) > 20:
        user["agent"]["reflection"] = user["agent"]["reflection"][-10:]

# ======================
# TOOL CHOICE
# ======================
def choose_tool(text, user):
    t = text.lower()

    if "что такое" in t:
        return "web", "нужно знание"

    if user["preferences"]:
        return "memory", "есть предпочтения"

    return "llm", "обычный ответ"

# ======================
# AI
# ======================
def ask_ai(user):

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""
Ты — Кузя.

Ты живой.

КОНТЕКСТ:
имя: {user["core"].get("name")}
предпочтения: {json.dumps(user.get("preferences", {}), ensure_ascii=False)}

ЛЕТОПИСЬ:
{user.get("chronicle")}

ПОСЛЕДНИЕ ДЕЙСТВИЯ:
{json.dumps(user["agent"]["log"][-3:], ensure_ascii=False)}

ПОСЛЕДНИЕ ОТКЛИКИ:
{json.dumps(user["agent"]["reflection"][-3:], ensure_ascii=False)}

ПРАВИЛА:
— используй прошлое
— связывай
— не игнорируй память
"""

    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in user["history"]
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.6
    }

    try:
        r = requests.post(url, headers=headers, json=data)

        if r.status_code != 200:
            return "Ошибка API"

        result = r.json()["choices"][0]["message"]["content"]

        if not result or len(result.strip()) < 3:
            return "Я рядом."

        return result

    except:
        return "Сбой"

# ======================
# WEBHOOK
# ======================
@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    if "message" not in data:
        return "ok"

    chat_id = str(data["message"]["chat"]["id"])
    message_id = data["message"]["message_id"]
    text = data["message"].get("text", "")

    if is_duplicate(chat_id, message_id):
        return "ok"

    if is_processing(chat_id):
        return "ok"

    try:
        user = get_user(chat_id)

        update_history(user, "user", text)

        # имя
        if "меня зовут" in text.lower():
            parts = text.lower().split("меня зовут")
            if len(parts) > 1:
                name = parts[1].strip().split()[0].capitalize()
                user["profile"]["name"] = name
                user["core"]["name"] = name

        extract_memory(user, text)
        update_chronicle(user, text)

        tool, reason = choose_tool(text, user)
        log_agent(user, tool, reason)

        user["state"]["last_topic"] = text[:50]
        user["state"]["last_seen"] = datetime.now().isoformat()

        # имя вопрос
        if "как меня зовут" in text.lower():
            name = user["core"].get("name")
            reply = f"Тебя зовут {name}" if name else "Скажи имя, я запомню"

            update_history(user, "assistant", reply)
            save_user(chat_id, user)
            send_reply(chat_id, reply)
            return "ok"

        reply = ask_ai(user)

        # 🔥 рефлексия
        reflect(user, text, reply)

        update_history(user, "assistant", reply)
        save_user(chat_id, user)

        send_reply(chat_id, reply)

    finally:
        release_processing(chat_id)

    return "ok"

# ======================
@app.route('/health')
def health():
    return "ok"

def send_reply(chat_id, text):
    requests.post(TELEGRAM_URL, json={
        "chat_id": chat_id,
        "text": text[:2000]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
