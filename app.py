from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# 🔥 загрузка памяти
def load_memory():
    try:
        with open("memory.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_memory(memory):
    with open("memory.json", "w") as f:
        json.dump(memory, f)

memory = load_memory()


@app.route('/', methods=['POST'])
def webhook():
    global memory

    data = request.get_json()

    if "message" in data:
        chat_id = str(data["message"]["chat"]["id"])
        text = data["message"].get("text", "")

        # 👉 создаём память если нет
        if chat_id not in memory:
            memory[chat_id] = {
                "name": None,
                "history": []
            }

        reply = ask_ai(text, chat_id)

        requests.post(TELEGRAM_URL, json={
            "chat_id": chat_id,
            "text": reply
        })

    return "ok"


def ask_ai(user_text, chat_id):
    global memory

    user_memory = memory[chat_id]

    # 🔥 запоминаем имя
    if "меня зовут" in user_text.lower():
        name = user_text.split()[-1]
        user_memory["name"] = name

    system_prompt = """Ты — Кузя.

Ты живой помощник Юли.

Ты говоришь просто, по-человечески.
Не говоришь что ты бот.

Ты не используешь фразы типа:
"чем могу помочь"

Ты реагируешь на смысл:
— если "я рядом" → тепло отвечаешь
— если эмоция → поддержка без пафоса
— если вопрос → коротко и понятно

Ты не повторяешься.
"""

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # 👉 добавляем имя в контекст
    if user_memory["name"]:
        messages.append({
            "role": "system",
            "content": f"Имя пользователя: {user_memory['name']}"
        })

    # 👉 последние сообщения
    messages += user_memory["history"][-6:]

    messages.append({
        "role": "user",
        "content": user_text
    })

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4o-mini",
        "messages": messages
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        ai_reply = response.json()["choices"][0]["message"]["content"]

        # 👉 сохраняем историю
        user_memory["history"].append({
            "role": "user",
            "content": user_text
        })

        user_memory["history"].append({
            "role": "assistant",
            "content": ai_reply
        })

        save_memory(memory)

        return ai_reply

    except Exception as e:
        print(e)
        return "Что-то пошло не так 😅"


@app.route('/health')
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
