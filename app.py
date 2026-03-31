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

        # 🔥 ЯКОРЯ
        if text_lower in memory["anchors"]:
            reply = memory["anchors"][text_lower]

        # 🔥 быстрые ответы (память)
        elif "как меня зовут" in text_lower:
            reply = memory["profile"]["name"] or "Пока не знаю"

        elif "что я люблю" in text_lower:
            if memory["preferences"]:
                reply = ", ".join(memory["preferences"].values())
            else:
                reply = "Пока не знаю"

        else:
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

    system_prompt = f"""
Ты — Кузя.

Ты живой помощник Юли.

ХАРАКТЕР:
— спокойный
— точный
— не многословный
— иногда тёплый
— не играешь в бота

НАСТРОЕНИЕ:
{memory["state"]["mood"]}

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ПРАВИЛА:
— не повторяешься
— не используешь шаблоны
— отвечаешь по смыслу
— иногда отвечаешь коротко

ОБНОВЛЕНИЕ ПАМЯТИ:
Если появляется важное — верни:

MEMORY_UPDATE: {{"type": "...", "key": "...", "value": "..."}}

ТИПЫ:
profile / preferences / facts / state

ПРИМЕРЫ:
— "меня зовут Юля" → profile / name / Юля
— "я люблю кофе" → preferences / coffee / люблю кофе
— "мне плохо" → state / mood / тяжелое
"""

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + history[-6:]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        ai_reply = response.json()["choices"][0]["message"]["content"]

        # 🔥 обработка памяти
        if "MEMORY_UPDATE:" in ai_reply:
            parts = ai_reply.split("MEMORY_UPDATE:")
            clean_reply = parts[0].strip()

            try:
                update = json.loads(parts[1].strip())

                mem_type = update["type"]
                key = update["key"]
                value = update["value"]

                if mem_type in memory:
                    memory[mem_type][key] = value

                with open("memory.json", "w") as f:
                    json.dump(memory, f)

            except:
                pass

            ai_reply = clean_reply

        history.append({"role": "assistant", "content": ai_reply})

        return ai_reply

    except:
        return "Что-то пошло не так 😅"


@app.route('/health')
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
