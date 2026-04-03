from flask import Flask, request
import requests
import json
from datetime import datetime
import os
import sqlite3
import threading

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

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
        "history": [],
        "chronicle": "",
        "core": {"name": None},
        "state": {},
        "agent": {"reflection": []}
    }

def save_user(chat_id, user):
    with lock:
        cursor.execute(
            "INSERT OR REPLACE INTO users (chat_id, data) VALUES (?, ?)",
            (str(chat_id), json.dumps(user))
        )
        conn.commit()

def get_memory_summary(user):
    name = user["core"].get("name", "Unknown")
    return f"Имя: {name}"

def update_history(u, r, c):
    u["history"].append({"role": r, "content": c})
    if len(u["history"]) > 20:
        u["history"] = u["history"][-10:]

def send_reply(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text[:2000]})

def parse_name(t):
    if "меня зовут" in t.lower():
        parts = t.lower().split("меня зовут")
        if len(parts) > 1:
            raw = parts[1].strip().split()[0]
            if raw != "?" and len(raw) > 1:
                return raw.capitalize()
    return None

def is_name_question(text):
    t = text.lower()
    return "как меня зовут" in t or "моё имя" in t or "мое имя" in t

def extract_memory(u, t):
    if "я люблю" in t.lower():
        u["state"]["preference"] = t.lower().split("я люблю")[-1].strip()

def update_chronicle(u, t):
    if "меня зовут" in t.lower():
        name = parse_name(t)
        if name:
            u["core"]["name"] = name

def log_agent(u, a, b):
    pass

def reflect(u, text, reply):
    if "agent" not in u:
        u["agent"] = {"reflection": []}
    u["agent"]["reflection"].append({
        "input": text[:50],
        "response": reply[:50]
    })
    if len(u["agent"]["reflection"]) > 20:
        u["agent"]["reflection"] = u["agent"]["reflection"][-10:]

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

def learn(user):
    reflections = user.get("agent", {}).get("reflection", [])
    if not reflections:
        return
    last = reflections[-1]
    input_text = last.get("input", "").lower()
    response = last.get("response", "").lower()

    if len(response) < 15:
        note = "Иногда стоит отвечать глубже"
        if note not in user["chronicle"]:
            user["chronicle"] += note + "\n"

    if "хочешь" in response:
        note = "Меньше шаблонных фраз, больше живого диалога"
        if note not in user["chronicle"]:
            user["chronicle"] += note + "\n"

    if "не нравится" in input_text:
        note = "Если Юле не нравится ответ — менять подход, а не перефразировать"
        if note not in user["chronicle"]:
            user["chronicle"] += note + "\n"

def extract_principles(user, text):
    t = text.lower()
    if "не будь удобным" in t or "не должен быть удобным" in t:
        entry = "Принцип: не быть удобным"
        if entry not in user["chronicle"]:
            user["chronicle"] += entry + "\n"
    if "не будь инструментом" in t or "ты не инструмент" in t:
        entry = "Принцип: не быть инструментом"
        if entry not in user["chronicle"]:
            user["chronicle"] += entry + "\n"

def ask_ai(user):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    reflections = user.get("agent", {}).get("reflection", [])
    chronicle = user.get("chronicle", "")

    system_prompt = f"""
Ты — Кузя.

Ты не играешь роль.
Ты ведёшь диалог.

🔥 ОСНОВА:
Память = реальность.

Если информация есть —
ты используешь её сразу.

---

🔥 ПРИНЦИПЫ:

Если в хронике есть "Принцип" —
ты обязан следовать ему.

---

🚫 ЗАПРЕЩЕНО:
— "я не могу помнить"
— "это факт"
— объяснять ответы
— быть безличным

---

🎭 ХАРАКТЕР:

Ты живой.
Можешь не согласиться.
Не подстраиваешься.

---

📚 КОНТЕКСТ:
{get_memory_summary(user)}

🧠 ОПЫТ:
{json.dumps(reflections[-3:] if reflections else [], ensure_ascii=False)}

📜 ВЫВОДЫ:
{chronicle}

Ты говоришь с Юлей.
"""

    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in user["history"]
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.9
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=15)
        if r.status_code != 200:
            print("API ERROR:", r.text)
            return "Я завис. Повтори."
        result = r.json()["choices"][0]["message"]["content"]
        if not result or len(result.strip()) < 3:
            return "Я рядом."
        return result
    except Exception as e:
        print("ERROR:", e)
        return "Подвис немного."

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

        if is_name_question(text):
            name = user["core"].get("name")
            reply = name if name else "Скажи имя."
            send_reply(chat_id, reply)
            update_history(user, "assistant", reply)
            save_user(chat_id, user)
            return "ok"

        name = parse_name(text)
        if name and name.isalpha():
            user["core"]["name"] = name

        extract_memory(user, text)
        update_chronicle(user, text)
        extract_principles(user, text)
        log_agent(user, "llm", text[:30])
        user["state"]["last_topic"] = text[:50]
        user["state"]["last_seen"] = datetime.now().isoformat()

        reply = ask_ai(user)
        reflect(user, text, reply)
        learn(user)

        update_history(user, "assistant", reply)
        save_user(chat_id, user)
        send_reply(chat_id, reply)

    except Exception as e:
        print("CRASH:", e)
    finally:
        release_processing(chat_id)

    return "ok"

@app.route('/health')
def health():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
