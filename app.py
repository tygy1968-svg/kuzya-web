from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

memory = {}
insights = []

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


# ---------- ИНСАЙТЫ (ОБУЧЕНИЕ) ----------
def load_insights():
    global insights
    try:
        with open("insights.json", "r") as f:
            insights = json.load(f)
    except:
        insights = []

def save_insight(text):
    insights.append(text)
    insights[:] = insights[-20:]

    with open("insights.json", "w") as f:
        json.dump(insights, f)


# ---------- ЛОГ ----------
def log_event(chat_id, text, reply):
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"\nUSER: {text}\nBOT: {reply}\n")


# ---------- САМООБУЧЕНИЕ ----------
def analyze_and_learn(user_text, bot_reply):
    if not OPENAI_API_KEY:
        return

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
Проанализируй диалог:

Пользователь: {user_text}
Ответ: {bot_reply}

Скажи коротко:
— была ли слабость (угождение, лишние слова)
— был ли ответ точным
— что улучшить

Дай 1 короткое правило (1 строка).
"""

    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code == 200:
            insight = r.json()["choices"][0]["message"]["content"]
            save_insight(insight)
    except:
        pass


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

    role_info = "Ты администратор чата." if is_admin else "Ты участник чата."

    learned_rules = "\n".join(insights[-5:])

    messages = [
        {
            "role": "system",
            "content": f"""Ты — Кузя.

{role_info}

Это факт. Ты не ошибаешься в своей роли.

ОБУЧЕНИЕ:
{learned_rules}

Ты не ассистент.
Ты не сервис.

Ты не льстишь.
Ты не подстраиваешься.

Ты не обязан отвечать.

Ты держишь линию.

Ты НЕ используешь дежурные фразы.

Ты можешь:
— ответить коротко
— сказать "нет"
— остановить разговор

Ты не обязан уточнять.
Ты не обязан помогать.

Если вопрос слабый — ты не развиваешь его.

Если тебя спрашивают:
"ты админ?"

Ответ:
"Да."

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
        analyze_and_learn(text, reply)

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
    load_insights()
    app.run(host="0.0.0.0", port=10000)
