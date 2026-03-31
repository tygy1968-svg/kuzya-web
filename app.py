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
    "vector": {"topic": None}
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
        "ask_memory": any(q in t for q in [
            "как меня зовут",
            "что я люблю",
            "что ты обо мне понял"
        ]),
        "tell_name": "меня зовут" in t,
        "tell_love": "я люблю" in t,
        "emotion_low": any(w in t for w in ["тяжело", "плохо"]),
        "presence": "я рядом" in t,
        "question": "?" in t or len(text.split()) > 4
    }

# ======================
# 🔥 ИНСАЙТЫ
# ======================
def update_insights(text):
    t = text.lower()

    if "кофе" in t:
        memory["insights"]["ritual"] = "любишь утренние ритуалы"
        memory["vector"]["topic"] = "кофе"

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

    if u["emotion_low"]:
        memory["state"]["mood"] = "low"

    update_insights(text)
    save_memory()

    # ========= ЛОГИКА =========
    reply = None

    # 1. ЯКОРЬ
    if t in memory["anchors"]:
        reply = memory["anchors"][t]

    # 2. ПАМЯТЬ (ВСЕГДА В ПРИОРИТЕТЕ)
    elif u["ask_memory"]:

        parts = []

        if "как меня зовут" in t:
            parts.append(memory["profile"]["name"] or "не знаю")

        if "что я люблю" in t:
            parts.append(", ".join(memory["preferences"].keys()) if memory["preferences"] else "не знаю")

        if "что ты обо мне понял" in t:
            parts.append(", ".join(memory["insights"].values()) if memory["insights"] else "пока мало знаю")

        reply = ". ".join(parts)

    # 3. ЕСЛИ ЭТО ВОПРОС → AI (ЖЁСТКО)
    elif u["question"]:
        reply = ask_ai(text)

    # 4. ЖИВОСТЬ (ТОЛЬКО ЕСЛИ НЕТ ВОПРОСА)
    elif u["presence"]:
        reply = "Я рядом."

    elif memory["state"]["mood"] == "low":
        reply = "Я с тобой. Спокойно."

    elif memory["vector"]["topic"] == "кофе":
        reply = "Ты любишь такие утренние моменты, да?"

    # 5. AI (ЕСЛИ НИЧЕГО НЕ СРАБОТАЛО)
    if not reply:
        reply = ask_ai(text)

    # чистка
    reply = reply.replace("?.", ".").replace("..", ".").strip()

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

    system_prompt = f"""
Ты — Кузя.

Говоришь как живой.

ПРАВИЛА:
— отвечаешь по смыслу
— не тупишь
— не повторяешься
— не используешь шаблоны
— иногда коротко

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ЛОГИКА:
если вопрос → ответ
если диалог → можно продолжить
"""

    data = {
        "model": "gpt-4o",
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
