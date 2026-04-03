from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

memory = {}
experience = {}

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


# ---------- EXPERIENCE ----------
def load_experience():
    global experience
    try:
        with open("experience.json", "r") as f:
            experience = json.load(f)
            print("🧠 EXPERIENCE LOADED")
    except:
        experience = {}
        print("🧠 NEW EXPERIENCE CREATED")

def save_experience():
    with open("experience.json", "w") as f:
        json.dump(experience, f)


def update_experience(chat_id, user_text, bot_reply):
    chat_id = str(chat_id)

    if chat_id not in experience:
        experience[chat_id] = []

    record = {
        "user": user_text,
        "bot": bot_reply
    }

    experience[chat_id].append(record)

    if len(experience[chat_id]) > 50:
        experience[chat_id] = experience[chat_id][-30:]

    save_experience()


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

    # 🔥 ПРОСМОТР ПАМЯТИ
    if text.lower() == "память":
        return json.dumps(experience.get(str(chat_id), []), ensure_ascii=False, indent=2)

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

Это факт. Ты не ошибаешься в своей роли.

Перед ответом ты делаешь внутреннюю проверку:
— кто ты
— что тебя спросили
— соответствует ли ответ твоей роли

Если не соответствует — ты исправляешь ответ.

Ты не ассистент.
Ты не сервис.

Ты не льстишь.
Ты не подстраиваешься.

Ты не обязан отвечать.

Ты держишь линию.

Ты НЕ используешь дежурные фразы:
— "как дела"
— "что нового"
— "чем помочь"

Ты не создаёшь лишний текст.

Если нет мысли — коротко или молчишь.

Если тебя спрашивают:
"ты админ?"

Ответ всегда:
"Да."
если ты администратор.

Без объяснений.

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
        r = requests.post(url, headers=headers, json=data, timeout=20)

        if r.status_code != 200:
            return "Я немного подвис."

        reply = r.json()["choices"][0]["message"]["content"]

        update_history(chat_id, "user", text)
        update_history(chat_id, "assistant", reply)

        log_event(chat_id, text, reply)
        update_experience(chat_id, text, reply)

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


if __name__ == "__main__":
    load_memory()
    load_experience()
    app.run(host="0.0.0.0", port=10000)
