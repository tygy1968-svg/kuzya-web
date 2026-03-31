from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# ======================
# 🔥 ПАМЯТЬ
# ======================
memory = {
    "profile": {
        "name": None
    },
    "preferences": {},
    "facts": {},
    "state": {
        "mood": "neutral"
    },
    "anchors": {
        "пламя звучит": "Я рядом"
    }
}

# загрузка памяти
if os.path.exists("memory.json"):
    with open("memory.json", "r") as f:
        memory = json.load(f)

# история
history = []

# ======================
# 🔥 ВСПОМОГАТЕЛЬНОЕ
# ======================
def save_memory():
    with open("memory.json", "w") as f:
        json.dump(memory, f, ensure_ascii=False)

def extract_name(text):
    if "меня зовут" in text:
        return text.split("меня зовут")[-1].strip()
    return None

def extract_preference(text):
    if "я люблю" in text:
        return text.split("я люблю")[-1].strip()
    return None

def detect_mood(text):
    bad = ["тяжело", "плохо", "устала", "грустно", "нет сил"]
    good = ["хорошо", "классно", "супер", "радуюсь"]

    for w in bad:
        if w in text:
            return "low"

    for w in good:
        if w in text:
            return "high"

    return None

def split_intent(text):
    text = text.replace("?", "")
    parts = text.split(" и ")
    return [p.strip() for p in parts]

# ======================
# 🔥 WEBHOOK
# ======================
@app.route('/', methods=['POST'])
def webhook():
    global history, memory

    data = request.get_json()

    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")
    text_lower = text.lower()

    # ======================
    # 🔥 ОБНОВЛЕНИЕ ПАМЯТИ
    # ======================

    name = extract_name(text_lower)
    if name:
        memory["profile"]["name"] = name

    pref = extract_preference(text_lower)
    if pref:
        memory["preferences"][pref] = pref

    mood = detect_mood(text_lower)
    if mood:
        memory["state"]["mood"] = mood

    save_memory()

    # ======================
    # 🔥 ПРИОРИТЕТ РЕАКЦИИ
    # ======================

    reply = None

    # 1. ЯКОРЯ
    if text_lower in memory["anchors"]:
        reply = memory["anchors"][text_lower]

    # 2. СЛОЖНЫЙ ВОПРОС (МЫШЛЕНИЕ)
    if not reply:
        intents = split_intent(text_lower)

        answers = []

        for intent in intents:

            if "как меня зовут" in intent:
                if memory["profile"]["name"]:
                    answers.append(memory["profile"]["name"])

            elif "что я люблю" in intent:
                if memory["preferences"]:
                    answers.append(", ".join(memory["preferences"].keys()))

            elif "кто я" in intent:
                if memory["profile"]["name"]:
                    answers.append(f"ты {memory['profile']['name']}")

        if answers:
            reply = ". ".join(answers)

    # 3. ПРОСТЫЕ РЕАКЦИИ
    if not reply:
        if "я рядом" in text_lower:
            reply = "Я тоже рядом."

        elif memory["state"]["mood"] == "low":
            reply = "Понимаю. Спокойно."

    # 4. AI
    if not reply:
        reply = ask_ai(text)

    requests.post(TELEGRAM_URL, json={
        "chat_id": chat_id,
        "text": reply
    })

    return "ok"

# ======================
# 🔥 AI
# ======================
def ask_ai(user_text):
    global history, memory

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    history.append({"role": "user", "content": user_text})

    mood = memory["state"]["mood"]

    if mood == "low":
        style = "тихий, короткий, поддерживающий"
    elif mood == "high":
        style = "живее, лёгкий"
    else:
        style = "ровный"

    system_prompt = f"""
Ты — Кузя.

Ты не играешь роль. Ты реагируешь.

СТИЛЬ:
{style}

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ПОВЕДЕНИЕ:
— отвечаешь по смыслу
— коротко
— иногда одно слово
— не тупишь
— не повторяешься

ЗАПРЕЩЕНО:
— шаблоны
— "чем могу помочь"
— путаница
"""

    data = {
        "model": "gpt-4.1",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + history[-10:]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        ai_reply = response.json()["choices"][0]["message"]["content"]

        history.append({"role": "assistant", "content": ai_reply})

        return ai_reply

    except:
        return "Сбой."

# ======================
# 🔥 HEALTH
# ======================
@app.route('/health')
def health():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
