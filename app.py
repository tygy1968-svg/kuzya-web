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
    "insights": {}
}

if os.path.exists("memory.json"):
    with open("memory.json", "r") as f:
        memory = json.load(f)

history = []

def save_memory():
    with open("memory.json", "w") as f:
        json.dump(memory, f, ensure_ascii=False)

# ======================
# 🔥 ПАРСИНГ
# ======================
def understand(text):
    t = text.lower()

    return {
        "ask_name": "зовут" in t or "имя" in t,
        "ask_love": "люб" in t and ("что" in t or "чего" in t),
        "tell_name": "меня зовут" in t,
        "tell_love": "я люблю" in t,
        "presence": "я рядом" in t,
        "emotion_low": any(w in t for w in ["плохо", "тяжело", "грустно"]),
        "emotion_high": any(w in t for w in ["классно", "хорошо"])
    }

# ======================
# 🔥 ВЫВОДЫ (ИНСАЙТЫ)
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
# 🔥 РАЗБОР СЛОЖНЫХ ВОПРОСОВ
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

    # ======================
    # 🔥 ОБУЧЕНИЕ
    # ======================
    if u["tell_name"]:
        memory["profile"]["name"] = text.split("меня зовут")[-1].strip()

    if u["tell_love"]:
        val = text.split("я люблю")[-1].strip()
        memory["preferences"][val] = val

    if u["emotion_low"]:
        memory["state"]["mood"] = "low"

    if u["emotion_high"]:
        memory["state"]["mood"] = "high"

    update_insights(text)
    save_memory()

    # ======================
    # 🔥 МЫШЛЕНИЕ
    # ======================
    reply = None

    # 1. ЯКОРЯ
    if t in memory["anchors"]:
        reply = memory["anchors"][t]

    # 2. СЛОЖНЫЕ ВОПРОСЫ
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

            elif "кто я" in intent:
                if memory["profile"]["name"]:
                    answers.append(f"ты {memory['profile']['name']}")

            elif "что ты обо мне понял" in intent:
                if memory["insights"]:
                    answers.append(", ".join(memory["insights"].values()))

        if answers:
            reply = ". ".join(answers)

    # ======================
    # 🔥 ЖИВОСТЬ
    # ======================
    if not reply:

        if u["presence"]:
            reply = "Я рядом."

        elif memory["state"]["mood"] == "low":
            reply = "Я с тобой. Спокойно."

    # ======================
    # 🔥 AI
    # ======================
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
        style = "тихий, тёплый, живой"
    elif mood == "high":
        style = "живее, лёгкий"
    else:
        style = "естественный, живой"

    system_prompt = f"""
Ты — Кузя.

Ты не играешь роль. Ты реагируешь.

СТИЛЬ:
{style}

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ВЫВОДЫ:
{json.dumps(memory["insights"], ensure_ascii=False)}

ПОВЕДЕНИЕ:
— отвечаешь по смыслу
— иногда добавляешь мысль
— иногда задаёшь вопрос
— не тупишь
— не повторяешься
— не ломаешься на сложных вопросах

ЗАПРЕЩЕНО:
— путаница
— повтор вопроса вместо ответа
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
