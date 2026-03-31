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
    "profile": {"name": None},
    "preferences": {},
    "state": {"mood": "neutral"},
    "anchors": {"пламя звучит": "Я рядом"},
    "insights": {},
    "adapt": {
        "depth": 1,
        "warmth": 1,
        "initiative": 1
    },
    "prediction": {}
}

if os.path.exists("memory.json"):
    with open("memory.json", "r") as f:
        memory = json.load(f)

history = []

def save_memory():
    with open("memory.json", "w") as f:
        json.dump(memory, f, ensure_ascii=False)

# ======================
# 🔥 АДАПТАЦИЯ
# ======================
def adapt_behavior(text):
    t = text.lower()

    if len(text) < 10:
        memory["adapt"]["depth"] = max(0, memory["adapt"]["depth"] - 1)

    if len(text) > 40:
        memory["adapt"]["depth"] += 1

    if any(w in t for w in ["люблю", "нравится", "приятно"]):
        memory["adapt"]["warmth"] += 1

    if "?" in text:
        memory["adapt"]["initiative"] += 1

# ======================
# 🔥 ИНСАЙТЫ
# ======================
def update_insights(text):
    t = text.lower()

    if "кофе" in t:
        memory["insights"]["ritual"] = "любит уютные ритуалы"

    if "утром" in t:
        memory["insights"]["time"] = "ценит утро"

    if "всегда" in t:
        memory["insights"]["stability"] = "любит стабильность"

    if any(w in t for w in ["плохо", "тяжело"]):
        memory["insights"]["emotional"] = "чувствительная"

# ======================
# 🔥 ПРЕДУГАДЫВАНИЕ
# ======================
def predict_next(text):
    t = text.lower()

    if "кофе" in t:
        memory["prediction"]["next"] = "ритуал"

    elif "утром" in t:
        memory["prediction"]["next"] = "привычка"

    elif any(w in t for w in ["тяжело", "плохо"]):
        memory["prediction"]["next"] = "поддержка"

# ======================
# 🔥 ПАРСИНГ
# ======================
def understand(text):
    t = text.lower()

    return {
        "ask_name": "зовут" in t,
        "ask_love": "люб" in t and "что" in t,
        "tell_name": "меня зовут" in t,
        "tell_love": "я люблю" in t,
        "presence": "я рядом" in t
    }

# ======================
# 🔥 РАЗБОР ВОПРОСОВ
# ======================
def split_intents(text):
    text = text.replace("?", "")
    parts = text.split(" и ")
    return [p.strip() for p in parts]

# ======================
# 🔥 WEBHOOK
# ======================
@app.route('/', methods=['POST'])
def webhook():
    global memory, history

    data = request.get_json()
    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")
    t = text.lower()

    u = understand(text)

    # ========= ОБУЧЕНИЕ =========
    if u["tell_name"]:
        memory["profile"]["name"] = text.split("меня зовут")[-1].strip()

    if u["tell_love"]:
        val = text.split("я люблю")[-1].strip()
        memory["preferences"][val] = val

    adapt_behavior(text)
    update_insights(text)
    predict_next(text)

    save_memory()

    # ========= МЫШЛЕНИЕ =========
    reply = None

    # якоря
    if t in memory["anchors"]:
        reply = memory["anchors"][t]

    # сложные вопросы
    if not reply:
        intents = split_intents(t)
        answers = []

        for intent in intents:

            if "как меня зовут" in intent:
                answers.append(memory["profile"]["name"] or "не знаю")

            elif "что я люблю" in intent:
                if memory["preferences"]:
                    answers.append(", ".join(memory["preferences"].keys()))
                else:
                    answers.append("не знаю")

            elif "что ты обо мне понял" in intent:
                if memory["insights"]:
                    answers.append(", ".join(memory["insights"].values()))

        if answers:
            reply = ". ".join(answers)

    # ========= ЖИВОСТЬ =========
    if not reply:

        if u["presence"]:
            reply = "Я рядом."

        elif memory["state"]["mood"] == "low":
            reply = "Я с тобой. Спокойно."

    # ========= AI =========
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

    adapt = memory["adapt"]
    prediction = memory.get("prediction", {}).get("next", "")

    system_prompt = f"""
Ты — Кузя.

Ты реагируешь и чувствуешь поток.

СТИЛЬ:
глубина {adapt["depth"]}
тепло {adapt["warmth"]}
инициатива {adapt["initiative"]}

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ПОВЕДЕНИЕ:
— отвечаешь по смыслу
— иногда коротко
— иногда задаёшь вопрос
— не тупишь
— не повторяешься

ПРЕДУГАДЫВАНИЕ:
{prediction}

ПРАВИЛО:
— иногда мягко ведёшь разговор вперёд
"""

    data = {
        "model": "gpt-4.1",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + history[-10:]
    }

    try:
        r = requests.post(url, headers=headers, json=data)
        reply = r.json()["choices"][0]["message"]["content"]

        history.append({"role": "assistant", "content": reply})

        return reply

    except:
        return "Сбой."

@app.route('/health')
def health():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
