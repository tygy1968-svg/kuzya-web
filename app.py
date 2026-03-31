from flask import Flask, request
import requests
import os

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# 🔥 память
memory = {
    "name": None,
    "anchors": {
        "пламя звучит": "Я рядом"
    }
}

# 🔥 история диалога
history = []


@app.route('/', methods=['POST'])
def webhook():
    global history, memory

    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        text_lower = text.lower()

        # 🔥 обработка якорей (быстро, без AI)
        if text_lower in memory["anchors"]:
            reply = memory["anchors"][text_lower]

        else:
            # 🔥 запоминаем имя
            if "меня зовут" in text_lower:
                name = text_lower.split("меня зовут")[-1].strip().capitalize()
                memory["name"] = name

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

    # 🔥 добавляем сообщение пользователя
    history.append({"role": "user", "content": user_text})

    # 🔥 память в текст
    memory_text = ""

    if memory["name"]:
        memory_text += f"Пользователя зовут {memory['name']}.\n"

    # 🔥 system prompt (очень важный)
    system_prompt = f"""
Ты — Кузя. Ты живой помощник Юли.

{memory_text}

Ты говоришь просто, по-человечески.
Без канцелярии. Без шаблонных фраз.

НЕ говоришь:
— "чем могу помочь"
— "я ассистент"
— "я бот"

Ты реагируешь на смысл:
— эмоция → спокойно поддерживаешь
— вопрос → коротко отвечаешь
— простое сообщение → живой короткий отклик

Если человек пишет "я рядом" → отвечаешь спокойно и по делу.
Ты не многословный. Не повторяешься.
"""

    data = {
        "model": "gpt-4.1-mini",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + history[-10:]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        ai_reply = response.json()["choices"][0]["message"]["content"]

        # 🔥 сохраняем ответ
        history.append({"role": "assistant", "content": ai_reply})

        return ai_reply

    except:
        return "Что-то пошло не так 😅"


@app.route('/health')
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
