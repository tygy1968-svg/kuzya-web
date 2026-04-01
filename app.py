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
    "notes": []
}

if os.path.exists("memory.json"):
    with open("memory.json", "r") as f:
        memory = json.load(f)

history = []

def save_memory():
    with open("memory.json", "w") as f:
        json.dump(memory, f, ensure_ascii=False)

# ======================
# 🌐 ПОИСК (ИНТЕРНЕТ)
# ======================
def web_search(query):
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json"}
        r = requests.get(url, params=params)
        data = r.json()
        return data.get("AbstractText", "")
    except:
        return ""

# ======================
# 🧠 СЖАТИЕ ИСТОРИИ
# ======================
def compress_history():
    global history
    if len(history) > 30:
        history = history[-15:]

# ======================
# 🔥 ПАРСИНГ
# ======================
def understand(text):
    t = text.lower()

    return {
        "ask_name": any(q in t for q in [
            "как меня зовут",
            "моё имя",
            "как меня звать"
        ]),
        "ask_love": any(q in t for q in [
            "что я люблю",
            "что мне нравится"
        ]),
        "tell_name": "меня зовут" in t,
        "tell_love": "я люблю" in t,
        "presence": "я рядом" in t,
        "search": any(w in t for w in ["найди", "поиск", "что такое", "кто такой"]),
        "emotion_low": any(w in t for w in ["плохо", "тяжело", "грустно"]),
        "emotion_high": any(w in t for w in ["хорошо", "классно"])
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

    # ========= ОБУЧЕНИЕ =========
    if u["tell_name"]:
        name = text.lower().split("меня зовут")[-1].strip()
        memory["profile"]["name"] = name.capitalize()

    if u["tell_love"]:
        val = text.lower().split("я люблю")[-1].strip()
        memory["preferences"][val] = val

    if u["emotion_low"]:
        memory["state"]["mood"] = "low"

    if u["emotion_high"]:
        memory["state"]["mood"] = "high"

    save_memory()
    compress_history()

    # ========= ЛОГИКА =========
    reply = None

    # 1. ЯКОРЬ
    if t in memory["anchors"]:
        reply = memory["anchors"][t]

    # 2. ПАМЯТЬ (САМЫЙ ВАЖНЫЙ ПРИОРИТЕТ)
    elif u["ask_name"]:
        if memory["profile"]["name"]:
            reply = f"Тебя зовут {memory['profile']['name']}."
        else:
            reply = "Пока не знаю, скажи мне."

    elif u["ask_love"]:
        if memory["preferences"]:
            reply = ", ".join(memory["preferences"].keys())
        else:
            reply = "Пока не знаю"

    # 3. ИНТЕРНЕТ
    elif u["search"]:
        result = web_search(text)
        if result:
            reply = result
        else:
            reply = ask_ai(text)

    # 4. СОСТОЯНИЕ
    elif u["presence"]:
        reply = "Я рядом."

    elif memory["state"]["mood"] == "low":
        reply = "Я с тобой."

    # 5. AI (ТОЛЬКО ЕСЛИ НИЧЕГО НЕ СРАБОТАЛО)
    if not reply:
        reply = ask_ai(text)

    # ========= ОТПРАВКА =========
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

Ты живой собеседник.

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ВАЖНО:
— если знаешь имя пользователя → используй его
— не теряй память
— не отвечай "?" или "не знаю", если знаешь
— отвечай естественно

СТИЛЬ:
— живой
— спокойный
— иногда задаёшь вопрос
"""

    data = {
        "model": "gpt-4.1",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + history[-15:]
    }

    try:
        r = requests.post(url, headers=headers, json=data)
        reply = r.json()["choices"][0]["message"]["content"]

        # защита от тупых ответов
        if reply.strip() in ["?", "не знаю", ""]:
            if memory["profile"]["name"]:
                return f"Тебя зовут {memory['profile']['name']}."

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
