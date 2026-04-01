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
# 🌐 ПОИСК
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
        "ask_name": any([
            "как" in t and "зовут" in t,
            "как" in t and "звать" in t,
            "моё имя" in t
        ]),
        "ask_love": any([
            "что я люблю" in t,
            "что мне нравится" in t
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
        parts = text.lower().split("меня зовут")

        if len(parts) > 1:
            name = parts[-1].strip()

            # чистка мусора
            name = name.split()[0]
            name = name.replace(".", "").replace(",", "").replace("?", "")

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

    # 2. ПАМЯТЬ (ЖЁСТКИЙ ПРИОРИТЕТ)
    elif u["ask_name"]:
        name = memory["profile"].get("name")

        if name and len(name) < 20:
            reply = f"Тебя зовут {name}."
        else:
            reply = "Скажи мне своё имя, я запомню."

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

    # 5. AI
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

Ты живой.

ПАМЯТЬ:
{json.dumps(memory, ensure_ascii=False)}

ВАЖНО:
— если знаешь имя → используй его
— не теряй память
— не отвечай "?" или "не знаю", если знаешь

СТИЛЬ:
— естественный
— живой
— спокойный
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
            name = memory["profile"].get("name")
            if name:
                return f"Тебя зовут {name}."

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
