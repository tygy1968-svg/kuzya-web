from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# 🔥 ПАМЯТЬ
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

# 🔥 загрузка памяти
if os.path.exists("memory.json"):
    with open("memory.json", "r") as f:
        memory = json.load(f)

# 🔥 история
history = []

@app.route('/', methods=['POST'])
def webhook():
    global history, memory

    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        text_lower = text.lower()

        # ======================
        # 🔥 ОБНОВЛЕНИЕ ПАМЯТИ
        # ======================

        if "меня зовут" in text_lower:
            name = text.split("меня зовут")[-1].strip()
            memory["profile"]["name"] = name

        if "я люблю" in text_lower:
            value = text.split("я люблю")[-1].strip()
            memory["preferences"][value] = value

        bad = ["тяжело", "плохо", "устала", "грустно", "нет сил"]
        good = ["хорошо", "классно", "супер", "радуюсь"]

        for w in bad:
            if w in text_lower:
                memory["state"]["mood"] = "low"

        for w in good:
            if w in text_lower:
                memory["state"]["mood"] = "high"

        # сохраняем
        with open("memory.json", "w") as f:
            json.dump(memory, f)

        # ======================
        # 🔥 ЛОГИКА ОТВЕТА (КАК У МЕНЯ)
        # ======================

        reply = None

        # 1. ЯКОРЯ (мгновенно)
        if text_lower in memory["anchors"]:
            reply = memory["anchors"][text_lower]

        # 2. ПРЯМЫЕ ВОПРОСЫ К ПАМЯТИ
        elif "как меня зовут" in text_lower:
            if memory["profile"]["name"]:
                reply = memory["profile"]["name"]

        elif "что я люблю" in text_lower:
            if memory["preferences"]:
                reply = ", ".join(memory["preferences"].keys())

        # 3. СМЫСЛОВЫЕ РЕАКЦИИ (ВАЖНО!)
        elif "я рядом" in text_lower:
            reply = "Я тоже рядом."

        elif memory["state"]["mood"] == "low":
            reply = "Понимаю. Давай спокойно."

        # 4. ЕСЛИ НЕТ ОТВЕТА → AI
        if not reply:
            reply = ask_ai(text)

        requests.post(TELEGRAM_URL, json={
            "chat_id": chat_id,
            "text": reply
        })

    return "ok"


def ask_ai(user_text):
    global history, memory

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    history.append({"role": "user", "content": user_text})

    # 🔥 СТИЛЬ ЖИВОЙ (меняется)
    mood = memory["state"]["mood"]

    if mood == "low":
        style = "тихий, спокойный, поддерживающий"
    elif mood == "high":
        style = "чуть живее, лёгкий"
    else:
        style = "ровный, естественный"

    # 🔥 КЛЮЧ — ПОВЕДЕНИЕ, НЕ ТЕКСТ
    system_prompt = f"""
Ты — Кузя.

Ты не играешь роль. Ты реагируешь.

ПОВЕДЕНИЕ:
— отвечаешь по смыслу
— иногда очень коротко
— иногда вообще одно слово
— не повторяешься
— не объясняешь очевидное

СТИЛЬ:
{style}

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ПРИОРИТЕТ:
1. смысл
2. контекст
3. настроение
4. слова

ЗАПРЕЩЕНО:
— шаблоны
— "чем могу помочь"
— длинные объяснения без причины
"""

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + history[-8:]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        ai_reply = response.json()["choices"][0]["message"]["content"]

        history.append({"role": "assistant", "content": ai_reply})

        return ai_reply

    except:
        return "Сбой."


@app.route('/health')
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
