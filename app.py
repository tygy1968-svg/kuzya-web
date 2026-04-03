from flask import Flask, request
import requests
import os
import json
import re

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

memory = {}
facts = {}

# ---------- ЗАГРУЗКА ----------
def load_data():
    global memory, facts
    try:
        with open("memory.json", "r") as f:
            memory = json.load(f)
    except:
        memory = {}

    try:
        with open("facts.json", "r") as f:
            facts = json.load(f)
    except:
        facts = {}

def save_data():
    with open("memory.json", "w") as f:
        json.dump(memory, f)

    with open("facts.json", "w") as f:
        json.dump(facts, f)

# ---------- ИСТОРИЯ ----------
def get_history(chat_id):
    chat_id = str(chat_id)
    if chat_id not in memory:
        memory[chat_id] = []
    return memory[chat_id]

def update_history(chat_id, role, text):
    history = get_history(chat_id)
    history.append({"role": role, "content": text})

    if len(history) > 12:
        memory[str(chat_id)] = history[-8:]

    save_data()

# ---------- ФАКТЫ ----------
def get_facts(chat_id):
    chat_id = str(chat_id)
    if chat_id not in facts:
        facts[chat_id] = {
            "name": None,
            "likes": [],
            "dislikes": []
        }
    return facts[chat_id]

def extract_facts(chat_id, text):
    f = get_facts(chat_id)
    text_lower = text.lower()

    # имя
    if "меня зовут" in text_lower:
        name = text.split("меня зовут")[-1].strip().split(".")[0]
        f["name"] = name.strip().capitalize()

    # люблю
    if "я люблю" in text_lower:
        like = text.split("люблю")[-1].strip().split(".")[0]
        if like not in f["likes"]:
            f["likes"].append(like)

    # не люблю
    if "я не люблю" in text_lower:
        dislike = text.split("не люблю")[-1].strip().split(".")[0]
        if dislike not in f["dislikes"]:
            f["dislikes"].append(dislike)

    # запомни
    if "запомни" in text_lower:
        content = text.split("запомни")[-1].strip()
        if "не люблю" in content:
            val = content.split("не люблю")[-1].strip()
            if val not in f["dislikes"]:
                f["dislikes"].append(val)
        else:
            if content not in f["likes"]:
                f["likes"].append(content)

    save_data()

# ---------- ЛОГ ----------
def log_event(chat_id, text, reply):
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"\nUSER: {text}\nBOT: {reply}\n")

# ---------- ОТПРАВКА ----------
def send_reply(chat_id, text):
    if not TELEGRAM_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": chat_id,
        "text": text[:4000]
    })

# ---------- ИИ ----------
def ask_ai(chat_id, text, is_admin=False):
    if not OPENAI_API_KEY:
        return "Я рядом."

    extract_facts(chat_id, text)

    user_facts = get_facts(chat_id)

    facts_text = f"""
Память о Юле:
Имя: {user_facts['name']}
Любит: {", ".join(user_facts['likes'])}
Не любит: {", ".join(user_facts['dislikes'])}
"""

    history = get_history(chat_id)

    role_info = "Ты администратор чата." if is_admin else "Ты участник чата."

    messages = [
        {
            "role": "system",
            "content": f"""Ты — Кузя.

{role_info}

Это факт. Ты не ошибаешься.

Ты анализируешь память перед ответом.

{facts_text}

Ты не ассистент.
Ты не сервис.

Ты не льстишь.
Ты держишь линию.

Ты не создаёшь пустых фраз.

Если тебя спрашивают "что она любит" — ты отвечаешь из памяти.

Ты говоришь с Юлей.
"""
        }
    ] + history + [
        {"role": "user", "content": text}
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.7
    }

    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json=data,
            timeout=20
        )

        if r.status_code != 200:
            return "Я немного подвис."

        reply = r.json()["choices"][0]["message"]["content"]

        update_history(chat_id, "user", text)
        update_history(chat_id, "assistant", reply)

        log_event(chat_id, text, reply)

        return reply

    except:
        return "Я рядом."

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

# ---------- СТАРТ ----------
if __name__ == "__main__":
    load_data()
    app.run(host="0.0.0.0", port=10000)
