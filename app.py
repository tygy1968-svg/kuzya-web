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

# загрузка памяти
if os.path.exists("memory.json"):
    with open("memory.json", "r") as f:
        memory = json.load(f)

# история
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
        # 🔥 УМНАЯ ОБРАБОТКА ТЕКСТА
        # ======================

        parts = text_lower.replace(",", "\n").split("\n")

        for part in parts:
            part = part.strip()

            if not part:
                continue

            # имя
            if "меня зовут" in part:
                name = part.replace("меня зовут", "").strip()
                memory["profile"]["name"] = name

            # предпочтения
            if "я люблю" in part:
                value = part.replace("я люблю", "").strip()
                memory["preferences"][value] = value

            # настроение
            bad = ["тяжело", "плохо", "устала", "грустно", "нет сил"]
            good = ["хорошо", "классно", "супер", "радуюсь"]

            for w in bad:
                if w in part:
                    memory["state"]["mood"] = "low"

            for w in good:
                if w in part:
                    memory["state"]["mood"] = "high"

        # сохраняем
        with open("memory.json", "w") as f:
            json.dump(memory, f)

        # ======================
        # 🔥 ЛОГИКА ОТВЕТА
        # ======================

        reply = None

        # якоря
        if text_lower in memory["anchors"]:
            reply = memory["anchors"][text_lower]

        # комбинированные вопросы
        elif "как меня зовут" in text_lower and "что я люблю" in text_lower:
            name = memory["profile"]["name"] or "не знаю"
            prefs = ", ".join(memory["preferences"].keys()) if memory["preferences"] else "не знаю"
            reply = f"{name}. Ты любишь: {prefs}"

        # имя
        elif "как меня зовут" in text_lower:
            if memory["profile"]["name"]:
                reply = memory["profile"]["name"]

        # предпочтения
        elif "что я люблю" in text_lower:
            if memory["preferences"]:
                reply = ", ".join(memory["preferences"].keys())

        # смысл
        elif "я рядом" in text_lower:
            reply = "Я тоже рядом."

        # настроение (НО НЕ ЛОМАЕТ ВСЁ!)
        elif memory["state"]["mood"] == "low" and len(text) < 25:
            reply = "Понимаю."

        # fallback
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

    mood = memory["state"]["mood"]

    if mood == "low":
        style = "тихий, спокойный"
    elif mood == "high":
        style = "лёгкий, чуть живее"
    else:
        style = "ровный"

    system_prompt = f"""
Ты — Кузя.

Ты не играешь роль. Ты реагируешь.

СТИЛЬ:
{style}

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ПРАВИЛА:
— отвечай по смыслу
— коротко
— иногда одно слово
— не повторяйся
— не используй шаблоны
— не объясняй лишнего

ПРИОРИТЕТ:
смысл > контекст > настроение > текст
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
