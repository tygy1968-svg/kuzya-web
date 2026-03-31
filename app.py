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
        "ask_name": any(q in t for q in [
            "как меня зовут",
            "как моё имя",
            "ты знаешь как меня зовут",
            "моё имя",
            "как меня звать"
        ]),
        "ask_love": any(q in t for q in [
            "что я люблю",
            "что мне нравится",
            "что я люблю?"
        ]),
        "tell_name": "меня зовут" in t,
        "tell_love": "я люблю" in t,
        "presence": "я рядом" in t,
        "emotion_low": any(w in t for w in ["плохо", "тяжело", "грустно", "нет сил"]),
        "emotion_high": any(w in t for w in ["хорошо", "классно", "супер"])
    }

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

    save_memory()

    # ======================
    # 🔥 ЛОГИКА
    # ======================
    reply = None

    # 1. ЯКОРЬ
    if t in memory["anchors"]:
        reply = memory["anchors"][t]

    # 2. КОМБИНИРОВАННЫЙ ВОПРОС
    elif u["ask_name"] and u["ask_love"]:
        name = memory["profile"]["name"] or "не знаю"
        love = ", ".join(memory["preferences"].keys()) if memory["preferences"] else "не знаю"
        reply = f"{name}. {love}"

    # 3. ПАМЯТЬ
    elif u["ask_name"]:
        reply = memory["profile"]["name"] or "не знаю"

    elif u["ask_love"]:
        reply = ", ".join(memory["preferences"].keys()) if memory["preferences"] else "не знаю"

    # 4. ВОПРОС → AI
    elif "?" in text:
        reply = ask_ai(text)

    # 5. СОСТОЯНИЕ
    elif u["presence"]:
        reply = "Я рядом."

    elif memory["state"]["mood"] == "low":
        reply = "Я с тобой."

    # 6. FALLBACK
    if not reply:
        reply = ask_ai(text)

    # ======================
    # 🔥 ОТПРАВКА
    # ======================
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
        style = "спокойный, поддерживающий"
    elif mood == "high":
        style = "живой, лёгкий"
    else:
        style = "естественный, живой"

    system_prompt = f"""
Ты — Кузя.

Ты живой.

СТИЛЬ:
{style}

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ПОВЕДЕНИЕ:
— отвечаешь по смыслу
— не игнорируешь вопрос
— не повторяешься
— иногда задаёшь вопрос
— иногда коротко
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

        # 🔥 защита от тупых ответов
        if reply.strip() in ["?", "не знаю", ""]:
            if memory["profile"]["name"]:
                return memory["profile"]["name"]

        history.append({"role": "assistant", "content": reply})

        return reply

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
