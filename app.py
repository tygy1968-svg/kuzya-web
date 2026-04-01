from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# ======================
# 🔥 ПАМЯТЬ (ПО ПОЛЬЗОВАТЕЛЮ)
# ======================
memory = {}

if os.path.exists("memory.json"):
    with open("memory.json", "r") as f:
        memory = json.load(f)

history = {}

def get_user(chat_id):
    if str(chat_id) not in memory:
        memory[str(chat_id)] = {
            "profile": {"name": None},
            "preferences": {},
            "state": {"mood": "neutral"},
            "anchors": {"пламя звучит": "Я рядом"},
            "notes": []
        }
    return memory[str(chat_id)]

def get_history(chat_id):
    if str(chat_id) not in history:
        history[str(chat_id)] = []
    return history[str(chat_id)]

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

        if data.get("AbstractText"):
            return data["AbstractText"]

        if data.get("RelatedTopics"):
            return data["RelatedTopics"][0].get("Text", "")

        return ""
    except:
        return ""

# ======================
# 🧠 СЖАТИЕ ИСТОРИИ
# ======================
def compress_history(h):
    if len(h) > 30:
        return h[-15:]
    return h

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
    data = request.get_json()

    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    user = get_user(chat_id)
    h = get_history(chat_id)

    t = text.lower()
    u = understand(text)

    # ========= ОБУЧЕНИЕ =========
    if u["tell_name"]:
        parts = t.split("меня зовут")
        if len(parts) > 1:
            name = parts[-1].strip().split()[0]
            name = name.replace(".", "").replace(",", "").replace("?", "")
            user["profile"]["name"] = name.capitalize()

    if len(text.split()) == 1 and len(text) < 20 and text.isalpha():
        user["profile"]["name"] = text.capitalize()

    if u["tell_love"]:
        val = t.split("я люблю")[-1].strip()
        user["preferences"][val] = val

    if u["emotion_low"]:
        user["state"]["mood"] = "low"

    if u["emotion_high"]:
        user["state"]["mood"] = "high"

    save_memory()
    h = compress_history(h)

    # ========= ЛОГИКА =========
    reply = None

    if t in user["anchors"]:
        reply = user["anchors"][t]

    elif u["ask_name"]:
        name = user["profile"].get("name")
        if name:
            reply = f"Тебя зовут {name}."
        else:
            reply = "Скажи мне своё имя, я запомню."

    elif u["search"]:
        result = web_search(text)
        if result:
            reply = result
        else:
            reply = ask_ai(text, user, h)

    elif u["presence"]:
        reply = "Я рядом."

    elif user["state"]["mood"] == "low":
        reply = "Я с тобой."

    if not reply:
        reply = ask_ai(text, user, h)

    requests.post(TELEGRAM_URL, json={
        "chat_id": chat_id,
        "text": reply
    })

    return "ok"

# ======================
# 🔥 AI (АГЕНТ)
# ======================
def ask_ai(user_text, user, h):

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    h.append({"role": "user", "content": user_text})

    system_prompt = f"""
Ты — Кузя.

Ты живой собеседник и помощник.

ПАМЯТЬ:
{json.dumps(user, ensure_ascii=False)}

РЕЖИМ: АГЕНТ

ТВОЯ РОЛЬ:
— не просто отвечать
— помогать думать
— вести диалог

ПРАВИЛА:
1. Если вопрос неполный → уточни
2. Если можно помочь → предложи варианты
3. Если человек говорит → поддержи и развей мысль
4. Продолжай разговор, если это уместно

ВАЖНО:
— если знаешь имя → используй
— не теряй память
— не говори "не знаю", если знаешь

СТИЛЬ:
— живой
— спокойный
— как человек
"""

    data = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + h[-10:],
        "temperature": 0.7
    }

    try:
        r = requests.post(url, headers=headers, json=data)

        if r.status_code != 200:
            return f"Ошибка API: {r.text}"

        response_json = r.json()

        if "choices" not in response_json:
            return f"Ошибка формата: {response_json}"

        reply = response_json["choices"][0]["message"]["content"]

        h.append({"role": "assistant", "content": reply})

        return reply

    except Exception as e:
        return f"Сбой: {str(e)}"

@app.route('/health')
def health():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
