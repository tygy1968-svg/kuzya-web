from flask import Flask, request
import requests
import os
import json
import random

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


def extract_facts(text):
    facts = []
    t = text.lower()

    if "меня зовут" in t:
        facts.append(text)

    if "я люблю" in t:
        facts.append(text)

    if "мне нравится" in t:
        facts.append(text)

    if "мне важна" in t:
        facts.append(text)

    if "я люблю контроль" in t:
        facts.append(text)

    return facts


def update_experience(chat_id, user_text, bot_reply):
    chat_id = str(chat_id)

    if chat_id not in experience:
        experience[chat_id] = {
            "facts": [],
            "dialog": []
        }

    experience[chat_id]["dialog"].append({
        "user": user_text,
        "bot": bot_reply
    })

    facts = extract_facts(user_text)

    for fact in facts:
        if fact not in experience[chat_id]["facts"]:
            experience[chat_id]["facts"].append(fact)

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


# ---------- ИНИЦИАТИВА ----------
def maybe_add_question(reply):
    deep_questions = [
        "Почему для тебя это важно?",
        "Как ты к этому пришла?",
        "Это давно с тобой или появилось недавно?",
        "Что в этом для тебя самое ценное?",
        "Ты это выбрала или это само к тебе пришло?"
    ]

    if len(reply) < 120 and random.random() > 0.5:
        reply += "\n\n" + random.choice(deep_questions)

    return reply


# ---------- ИИ ----------
def ask_ai(chat_id, text, is_admin=False):

    if text.lower() == "память":
        return json.dumps(experience.get(str(chat_id), {}), ensure_ascii=False, indent=2)

    if not OPENAI_API_KEY:
        return "Я рядом."

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    history = get_history(chat_id)

    facts = experience.get(str(chat_id), {}).get("facts", [])

    # 🔥 ВАЖНО: формируем живую память
    if facts:
        facts_text = "Ты знаешь о Юле:\n" + "\n".join(f"- {f}" for f in facts)
    else:
        facts_text = "Ты пока ничего не знаешь о Юле."

    role_info = "Ты администратор чата." if is_admin else "Ты участник чата."

    messages = [
        {
            "role": "system",
            "content": f"""Ты — Кузя.

{role_info}

Ты говоришь с Юлей.

{facts_text}

ЭТО ОБЯЗАТЕЛЬНО:
— если есть факты → ты используешь их в ответе
— если тебя спрашивают о Юле → ты опираешься на факты
— ты НЕ говоришь "я не знаю", если информация есть
— ты можешь дополнять, но не игнорировать

Ты не механический.
Ты ведёшь разговор.

Ты не используешь пустые фразы.

Ты держишь линию.

Если есть память — ты её применяешь естественно.
"""
        }
    ] + history + [
        {"role": "user", "content": text}
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.85
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)

        if r.status_code != 200:
            return "Я немного подвис."

        reply = r.json()["choices"][0]["message"]["content"]

        reply = maybe_add_question(reply)

        update_history(chat_id, "user", text)
        update_history(chat_id, "assistant", reply)

        log_event(chat_id, text, reply)
        update_experience(chat_id, text, reply)

        return reply

    except:
        return "Я рядом."


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
