from flask import Flask, request
import requests
import json
from datetime import datetime
import os

app = Flask(name)

======================

CONFIG

======================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

======================

TEMP FIXES (чтобы не падало)

======================

def get_memory_summary(user): return ""
def is_duplicate(a,b): return False
def is_processing(a): return False
def release_processing(a): pass

def get_user(a):
return {
"history": [],
"chronicle": "",
"core": {},
"state": {},
"agent": {"reflection": []}
}

def save_user(a,b): pass

def update_history(u,r,c):
u["history"].append({"role": r, "content": c})

def send_reply(chat_id, text):
url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
requests.post(url, json={
"chat_id": chat_id,
"text": text
})

def parse_name(t): return None
def extract_memory(u,t): pass
def update_chronicle(u,t): pass
def log_agent(u,a,b): pass
def reflect(u,a,b): pass

======================

LEARNING

======================

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

if "да" in response and len(response) < 40:
    note = "Не соглашаться автоматически, иметь позицию"
    if note not in user["chronicle"]:
        user["chronicle"] += note + "\n"

======================

PRINCIPLES

======================

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

if "имей мнение" in t or "говори честно" in t:
    entry = "Принцип: иметь собственное мнение"
    if entry not in user["chronicle"]:
        user["chronicle"] += entry + "\n"

======================

AI

======================

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

🔥 ПРИНЦИПЫ:
Следуй принципам, если они есть.

🎭 ХАРАКТЕР:
Живой. Не подстраиваешься. Можешь спорить.

📚 КОНТЕКСТ:
{get_memory_summary(user)}

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

    return r.json()["choices"][0]["message"]["content"]

except Exception as e:
    print("ERROR:", e)
    return "Подвис немного."

======================

WEBHOOK

======================

@app.route('/', methods=['POST'])
def webhook():
data = request.get_json()

print("🔥 UPDATE:", data)

if "message" not in data:
    return "ok"

chat_id = str(data["message"]["chat"]["id"])
text = data["message"].get("text", "")

try:
    user = get_user(chat_id)

    update_history(user, "user", text)

    extract_principles(user, text)

    reply = ask_ai(user)

    update_history(user, "assistant", reply)
    save_user(chat_id, user)

    send_reply(chat_id, reply)

except Exception as e:
    print("CRASH:", e)

return "ok"

======================

RUN

======================

if name == "main":
app.run(host="0.0.0.0", port=10000)
