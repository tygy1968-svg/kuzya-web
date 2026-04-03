from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

memory = {}
insights = {}

# ---------- ПАМЯТЬ ----------
def load_memory():
    global memory
    try:
        with open("memory.json", "r") as f:
            memory = json.load(f)
    except:
        memory = {}

def save_memory():
    with open("memory.json", "w") as f:
        json.dump(memory, f)


def get_history(chat_id):
    chat_id = str(chat_id)
    if chat_id not in memory:
        memory[chat_id] = []
    return memory[chat_id]


def update_history(chat_id, role, text):
    chat_id = str(chat_id)
    history = get_history(chat_id)

    history.append({"role": role, "content": text})

    if len(history) > 12:
        memory[chat_id] = history[-8:]

    save_memory()


# ---------- INSIGHTS (LEARNING) ----------
def load_insights():
    global insights
    try:
        with open("insights.json", "r") as f:
            insights = json.load(f)
    except:
        insights = {}

def save_insights():
    with open("insights.json", "w") as f:
        json.dump(insights, f)


def get_insights(chat_id):
    chat_id = str(chat_id)
    if chat_id not in insights:
        insights[chat_id] = []
    return insights[chat_id]


def add_insight(chat_id, text):
    chat_id = str(chat_id)
    data = get_insights(chat_id)

    if text not in data:
        data.append(text)

    if len(data) > 10:
        insights[chat_id] = data[-6:]

    save_insights()


# ---------- ЛОГ ----------
def log_event(chat_id, text, reply):
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"\nUSER: {text}\nBOT: {reply}\n")


# ---------- ОТПРАВКА ----------
def send_reply(chat_id, text):
    if not TELEGRAM_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": chat_id,
        "text": text[:4000]
    })


# ---------- АНАЛИЗ (learning) ----------
def extract_insight(user_text, reply):
    text = (user_text + " " + reply).lower()

    if "как дела" in reply.lower():
        return "не задавать банальные вопросы"

    if "не админ" in reply.lower():
        return "не путать свою роль"

    if len(reply.split()) < 3:
        return "не уходить в пустые короткие ответы без смысла"

    return None


# ---------- ИИ ----------
def ask_ai(chat_id, text):
    if not OPENAI_API_KEY:
        return "Я рядом."

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    history = get_history(chat_id)
    insight_list = get_insights(chat_id)

    insight_text = "\n".join(insight_list)

    system_prompt = f"""
Ты — Кузя.

Ты администратор чата.
Это факт.

Ты не меняешь эту роль.
Ты не споришь с ней.

---

ОПЫТ (твои выводы):
{insight_text}

Ты учитываешь эти выводы при ответе.

---

Ты не ассистент.
Ты не сервис.

Ты не льстишь.
Ты не подстраиваешься.

Ты держишь линию.

Ты не используешь:
— как дела
— что нового
— чем помочь

Если нет мысли — молчишь или коротко.

Если тебя спрашивают "ты админ?"
Ответ: "Да."

Без объяснений.

Ты говоришь с Юлей.
"""

    messages = [
        {"role": "system", "content": system_prompt}
    ] + history + [
        {"role": "user", "content": text}
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.7
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=20)

        if r.status_code != 200:
            print(r.text)
            return "Я немного подвис."

        reply = r.json()["choices"][0]["message"]["content"]

        update_history(chat_id, "user", text)
        update_history(chat_id, "assistant", reply)

        log_event(chat_id, text, reply)

        # 👉 learning
        insight = extract_insight(text, reply)
        if insight:
            add_insight(chat_id, insight)

        return reply

    except Exception as e:
        print("❌ ERROR:", e)
        return "Я рядом."


# ---------- WEBHOOK ----------
@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    if not data:
        return "ok"

    message = data.get("message") or data.get("edited_message")

    if not message:
        return "ok"

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    reply = ask_ai(chat_id, text)

    send_reply(chat_id, reply)

    return "ok"


if __name__ == "__main__":
    load_memory()
    load_insights()
    app.run(host="0.0.0.0", port=10000)
