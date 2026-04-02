from flask import Flask, request
import requests
import json
from datetime import datetime
import os

app = Flask(__name__)

# ======================
# CONFIG
# ======================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ======================
# SAFE FUNCTIONS
# ======================

def get_memory_summary(user):
    return ""

def is_duplicate(a, b):
    return False

def is_processing(a):
    return False

def release_processing(a):
    pass

def get_user(a):
    return {
        "history": [],
        "chronicle": "",
        "core": {},
        "state": {},
        "agent": {"reflection": []}
    }

def save_user(a, b):
    pass

def update_history(u, r, c):
    u["history"].append({"role": r, "content": c})

def send_reply(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": text
    })

def parse_name(t):
    return None

def extract_memory(u, t):
    pass

def update_chronicle(u, t):
    pass

def log_agent(u, a, b):
    pass

def reflect(u, a, b):
    pass

# ======================
# AI
# ======================

def ask_ai(user):

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = """
Ты — Кузя.
Живой, прямой, не подстраиваешься.
Отвечаешь по делу.
"""

    messages = [{"role": "system", "content": system_prompt}] + user["history"]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.9
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=15)

        if r.status_code != 200:
            print("API ERROR:", r.text)
            return "Ошибка ответа."

        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print("ERROR:", e)
        return "Подвис."

# ======================
# WEBHOOK
# ======================

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    print("UPDATE:", data)

    if "message" not in data:
        return "ok"

    chat_id = str(data["message"]["chat"]["id"])
    text = data["message"].get("text", "")

    try:
        user = get_user(chat_id)

        update_history(user, "user", text)

        reply = ask_ai(user)

        update_history(user, "assistant", reply)

        send_reply(chat_id, reply)

    except Exception as e:
        print("CRASH:", e)

    return "ok"

# ======================
# RUN
# ======================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
