from flask import Flask, request
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

# ======================
# ENV (безопасно)
# ======================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ======================
# TEMP FIXES
# ======================
def get_memory_summary(user): return ""
def is_duplicate(a,b): return False
def is_processing(a): return False
def get_user(a): return {"history": [], "chronicle": "", "core": {}, "state": {}, "agent": {}}
def update_history(u,r,c): pass
def save_user(a,b): pass
def parse_name(t): return None
def extract_memory(u,t): pass
def update_chronicle(u,t): pass
def log_agent(u,a,b): pass
def reflect(u,a,b): pass
def release_processing(a): pass

# ======================
# TELEGRAM SEND
# ======================
def send_reply(chat_id, text):
    if not TELEGRAM_TOKEN:
        print("❌ NO TELEGRAM TOKEN")
        return

    if not text:
        text = "..."

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    try:
        r = requests.post(url, json=data)
        print("📨 TG STATUS:", r.status_code)
        print("📨 TG RESPONSE:", r.text)
    except Exception as e:
        print("❌ SEND ERROR:", e)

# ======================
# AI (тестовый ответ)
# ======================
def ask_ai(user):
    return "Я рядом."

# ======================
# WEBHOOK
# ======================
@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    print("🔥 UPDATE:", data)

    if not data:
        return "ok"

    if "message" not in data:
        return "ok"

    chat_id = str(data["message"]["chat"]["id"])
    text = data["message"].get("text", "")

    print("📩 TEXT:", text)

    try:
        user = get_user(chat_id)

        update_history(user, "user", text)

        reply = ask_ai(user)

        update_history(user, "assistant", reply)
        save_user(chat_id, user)

        send_reply(chat_id, reply)

    except Exception as e:
        print("❌ ERROR:", e)

    return "ok"

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
