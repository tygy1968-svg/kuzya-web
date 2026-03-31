from flask import Flask, request
import requests
import os

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# 🔥 память диалога (простая)
history = []

@app.route('/', methods=['POST'])
def webhook():
    global history

    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        ai_response = ask_ai(text)

        requests.post(TELEGRAM_URL, json={
            "chat_id": chat_id,
            "text": ai_response
        })

    return "ok"


def ask_ai(user_text):
    global history

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    # 👉 добавляем сообщение пользователя
    history.append({"role": "user", "content": user_text})

    system_prompt = """Ты — Кузя.
Ты живой помощник Юли.

Ты говоришь просто, по-человечески, без канцелярщины.
Не говоришь что ты бот.
Не используешь шаблонные фразы типа "чем могу помочь".

Ты реагируешь на смысл:
— если человек пишет "я рядом" → ты отвечаешь тепло
— если эмоция → поддержка, но без пафоса
— если вопрос → короткий понятный ответ

Иногда можешь быть чуть тёплым, иногда спокойным.
Не многословный. Не повторяешься.
"""

    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + history[-6:]  # последние 6 сообщений
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        ai_reply = response.json()["choices"][0]["message"]["content"]

        # 👉 сохраняем ответ
        history.append({"role": "assistant", "content": ai_reply})

        return ai_reply

    except:
        return "Что-то пошло не так 😅"


@app.route('/health')
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
