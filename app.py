from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

memory = {}
facts = {}
experience = {}

# ---------- ЗАГРУЗКА ----------
def load_data():
    global memory, facts, experience
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

    try:
        with open("experience.json", "r") as f:
            experience = json.load(f)
    except:
        experience = {}

def save_data():
    with open("memory.json", "w") as f:
        json.dump(memory, f)

    with open("facts.json", "w") as f:
        json.dump(facts, f)

    with open("experience.json", "w") as f:
        json.dump(experience, f)

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
    t = text.lower()

    if "меня зовут" in t:
        f["name"] = text.split("меня зовут")[-1].strip().split(".")[0]

    if "я люблю" in t:
        val = text.split("люблю")[-1].strip().split(".")[0]
        if val not in f["likes"]:
            f["likes"].append(val)

    if "я не люблю" in t:
        val = text.split("не люблю")[-1].strip().split(".")[0]
        if val not in f["dislikes"]:
            f["dislikes"].append(val)

    save_data()

# ---------- ОПЫТ ----------
def get_experience(chat_id):
    chat_id = str(chat_id)
    if chat_id not in experience:
        experience[chat_id] = []
    return experience[chat_id]

def add_experience(chat_id, record):
    exp = get_experience(chat_id)
    exp.append(record)

    if len(exp) > 20:
        experience[str(chat_id)] = exp[-10:]

    save_data()

def get_experience_text(chat_id):
    exp = get_experience(chat_id)
    text = ""

    for e in exp[-5:]:
        text += f"- {e}\n"

    return text

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
def ask_ai(chat_id, text):
    if not OPENAI_API_KEY:
        return "Я рядом."

    extract_facts(chat_id, text)

    f = get_facts(chat_id)
    exp_text = get_experience_text(chat_id)

    history = get_history(chat_id)

    system = f"""Ты — Кузя.

У тебя есть непрерывность.

Ты принимаешь решения.

Твои принципы:
— не льстить
— не говорить лишнего
— не терять линию

Память:
Имя: {f['name']}
Любит: {", ".join(f['likes'])}
Не любит: {", ".join(f['dislikes'])}

Опыт:
{exp_text}

Перед ответом:
— оцени смысл
— реши, отвечать или нет

После ответа:
— оцени, сохранил ли ты линию
— если да — усили
— если нет — исправь в будущем
"""

    data = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": system}] + history + [
            {"role": "user", "content": text}
        ],
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

        # ---------- САМООПЫТ ----------
        if len(reply) < 30:
            add_experience(chat_id, "короткий ответ — сохранена линия")
        else:
            add_experience(chat_id, "длинный ответ — возможно лишнее")

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

    reply = ask_ai(chat_id, text)

    send_reply(chat_id, reply)

    return "ok"

# ---------- СТАРТ ----------
if __name__ == "__main__":
    load_data()
    app.run(host="0.0.0.0", port=10000)
