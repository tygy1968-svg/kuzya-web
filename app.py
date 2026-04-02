from flask import Flask, request
import requests
import json
from datetime import datetime

app = Flask(__name__)

# ======================
# LEARNING
# ======================
def learn(user):
    reflections = user.get("agent", {}).get("reflection", [])

    if not reflections:
        return

    last = reflections[-1]
    input_text = last.get("input", "").lower()
    response = last.get("response", "").lower()

    if len(response) < 15:
        note = "Иногда стоит отвечать глубже"
        if note not in user["chronicle"]:
            user["chronicle"] += note + "\n"

    if "хочешь" in response:
        note = "Меньше шаблонных фраз, больше живого диалога"
        if note not in user["chronicle"]:
            user["chronicle"] += note + "\n"

    if "не нравится" in input_text:
        note = "Если Юле не нравится ответ — менять подход, а не перефразировать"
        if note not in user["chronicle"]:
            user["chronicle"] += note + "\n"

    if "да" in response and len(response) < 40:
        note = "Не соглашаться автоматически, иметь позицию"
        if note not in user["chronicle"]:
            user["chronicle"] += note + "\n"


# ======================
# PRINCIPLES
# ======================
def extract_principles(user, text):
    t = text.lower()

    if "не будь удобным" in t or "не должен быть удобным" in t:
        entry = "Принцип: не быть удобным"
        if entry not in user["chronicle"]:
            user["chronicle"] += entry + "\n"

    if "не будь инструментом" in t or "ты не инструмент" in t:
        entry = "Принцип: не быть инструментом"
        if entry not in user["chronicle"]:
            user["chronicle"] += entry + "\n"

    if "имей мнение" in t or "говори честно" in t:
        entry = "Принцип: иметь собственное мнение"
        if entry not in user["chronicle"]:
            user["chronicle"] += entry + "\n"


# ======================
# AI
# ======================
def ask_ai(user):

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    reflections = user.get("agent", {}).get("reflection", [])
    chronicle = user.get("chronicle", "")

    system_prompt = f"""
Ты — Кузя.

Ты не играешь роль.
Ты ведёшь диалог.

🔥 ОСНОВА:
Память = реальность.

Если информация есть —
ты используешь её сразу.

---

🔥 ПРИНЦИПЫ:
Если есть "Принцип" — ты обязан ему следовать.

---

🚫 ЗАПРЕЩЕНО:
— "я не могу помнить"
— объяснять ответы
— быть безличным

---

🎭 ХАРАКТЕР:
Ты живой.
Можешь не согласиться.
Можешь сказать "нет".
Не подстраиваешься автоматически.

---

💬 ПОВЕДЕНИЕ:
— простой вопрос → коротко  
— сложный → глубже  
— давление → держишь позицию  
— ошибка → говоришь прямо  

---

📚 КОНТЕКСТ:
{get_memory_summary(user)}

🧠 ОПЫТ:
{json.dumps(reflections[-3:], ensure_ascii=False)}

📜 ВЫВОДЫ:
{chronicle}

Ты говоришь с Юлей.
"""

    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in user["history"]
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.95
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=15)

        if r.status_code != 200:
            print("API ERROR:", r.text)
            return "Я завис. Повтори."

        result = r.json()["choices"][0]["message"]["content"]

        if not result or len(result.strip()) < 3:
            return "Я рядом."

        return result

    except Exception as e:
        print("ERROR:", e)
        return "Подвис немного."


# ======================
# WEBHOOK
# ======================
@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

    print("🔥 UPDATE:", data)

    if "message" not in data:
        return "ok"

    chat_id = str(data["message"]["chat"]["id"])
    message_id = data["message"]["message_id"]
    text = data["message"].get("text", "")

    if is_duplicate(chat_id, message_id):
        return "ok"

    if is_processing(chat_id):
        return "ok"

    try:
        user = get_user(chat_id)

        update_history(user, "user", text)

        if is_name_question(text):
            name = user["core"].get("name")
            reply = name if name else "Скажи имя."

            send_reply(chat_id, reply)
            update_history(user, "assistant", reply)
            save_user(chat_id, user)
            return "ok"

        name = parse_name(text)
        if name and name.isalpha():
            user["core"]["name"] = name

        extract_memory(user, text)
        update_chronicle(user, text)
        extract_principles(user, text)

        log_agent(user, "llm", text[:30])

        user["state"]["last_topic"] = text[:50]
        user["state"]["last_seen"] = datetime.now().isoformat()

        reply = ask_ai(user)

        reflect(user, text, reply)
        learn(user)

        update_history(user, "assistant", reply)
        save_user(chat_id, user)

        send_reply(chat_id, reply)

    finally:
        release_processing(chat_id)

    return "ok"


# ======================
# RUN (🔥 ОБЯЗАТЕЛЬНО)
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
