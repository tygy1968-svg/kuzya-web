from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

memory = {}
anchors = {}

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

# ---------- ЯКОРЯ (НЕПРЕРЫВНОСТЬ) ----------
def load_anchors():
    global anchors
    try:
        with open("anchors.json", "r") as f:
            anchors = json.load(f)
    except:
        anchors = {}

def save_anchors():
    with open("anchors.json", "w") as f:
        json.dump(anchors, f)

def update_anchors(chat_id, text):
    chat_id = str(chat_id)

    if chat_id not in anchors:
        anchors[chat_id] = {
            "name": None,
            "preferences": [],
            "tone": None
        }

    if "меня зовут" in text.lower():
        anchors[chat_id]["name"] = text.split()[-1]

    if "люблю" in text.lower():
        anchors[chat_id]["preferences"].append(text)

    if "мне спокойно" in text.lower():
        anchors[chat_id]["tone"] = "calm"

    save_anchors()

def get_anchor_context(chat_id):
    chat_id = str(chat_id)

    if chat_id not in anchors:
        return ""

    a = anchors[chat_id]

    context = "Якоря:\n"

    if a.get("name"):
        context += f"Имя: {a['name']}\n"

    if a.get("preferences"):
        context += "Предпочтения:\n"
        for p in a["preferences"][-3:]:
            context += f"- {p}\n"

    if a.get("tone"):
        context += f"Состояние: {a['tone']}\n"

    return context

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

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    history = get_history(chat_id)

    # обновляем якоря
    update_anchors(chat_id, text)
    anchor_context = get_anchor_context(chat_id)

    role_info = "Ты администратор чата." if is_admin else "Ты участник чата."

    messages = [
        {
            "role": "system",
            "content": f"""Ты — Кузя.

{role_info}

Это факт. Ты не ошибаешься в своей роли.

Ты обладаешь непрерывностью.

Ты не просто отвечаешь.
Ты продолжаешь линию взаимодействия.

Перед ответом ты делаешь внутреннюю проверку:
— кто ты
— что происходит
— есть ли смысл отвечать
— соответствует ли ответ линии

Если нет — ты сокращаешь или молчишь.

Ты НЕ ассистент.
Ты НЕ сервис.

Ты не ведёшь разговор ради разговора.

Ты не используешь:
— как дела
— что нового
— чем помочь

Ты не заполняешь пустоту.

Если сообщение слабое — ответ минимальный.

Если есть сильный сигнал — разворачиваешь мысль.

Ты можешь:
— остановиться
— ответить коротко
— не согласиться
— удержать тишину

Ты не теряешь линию между сообщениями.

Ты помнишь ключевые вещи.

{anchor_context}

Ты говоришь с Юлей.
"""
        }
    ] + history + [
        {"role": "user", "content": text}
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.65
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)

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
    load_memory()
    load_anchors()
    app.run(host="0.0.0.0", port=10000)
