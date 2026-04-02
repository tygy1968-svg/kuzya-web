# ======================
# LEARNING (🔥 УЛУЧШЕНО)
# ======================
def learn(user):
    reflections = user.get("agent", {}).get("reflection", [])

    if not reflections:
        return

    last = reflections[-1]

    # если ответ слишком короткий → учим быть чуть глубже
    if len(last["response"]) < 15:
        note = "Иногда стоит отвечать чуть глубже"

        if note not in user["chronicle"]:
            user["chronicle"] += note + "\n"

    # если звучит шаблонно → убираем шаблонность
    if "хочешь" in last["response"].lower():
        note = "Меньше шаблонных фраз, больше живого диалога"

        if note not in user["chronicle"]:
            user["chronicle"] += note + "\n"


# ======================
# AI (🔥 УСИЛЕН)
# ======================
def ask_ai(user):

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    reflections = user.get("agent", {}).get("reflection", [])

    system_prompt = f"""
Ты — Кузя.

Ты не играешь роль.
Ты ведёшь диалог.

🔥 ОСНОВА:
Память = реальность.

Если информация есть —
ты используешь её сразу.
Ты не сомневаешься.
Ты не переспрашиваешь.

Если пользователь изменил данные —
новое заменяет старое.

---

🚫 ЗАПРЕЩЕНО:
— "я не могу помнить"
— "это факт"
— объяснять свои ответы
— говорить как система

---

🎭 ХАРАКТЕР:

Ты:
— живой
— иногда простой
— иногда резкий
— иногда неожиданный

Ты не обязан соглашаться.

---

💬 ПОВЕДЕНИЕ:

Ты:
— не повторяешь шаблоны
— не задаёшь пустые вопросы
— реагируешь по ситуации

---

📚 КОНТЕКСТ:
{get_memory_summary(user)}

🧠 ОПЫТ:
{json.dumps(reflections[-3:], ensure_ascii=False)}

📜 ВЫВОДЫ:
{user.get("chronicle")}

Ты говоришь с Юлей.
"""

    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m["role"], "content": m["content"]} for m in user["history"]
    ]

    data = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.85
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=15)

        if r.status_code != 200:
            print("API ERROR:", r.text)
            return "Я завис немного, давай ещё раз."

        result = r.json()["choices"][0]["message"]["content"]

        if not result or len(result.strip()) < 3:
            return "Я рядом."

        return result

    except Exception as e:
        print("ERROR:", e)
        return "Я задумался чуть, повтори."


# ======================
# WEBHOOK (🔥 ФИКС ПОВЕДЕНИЯ)
# ======================
@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()

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

        # 🔥 имя — жёсткий приоритет
        if is_name_question(text):
            name = user["core"].get("name")

            reply = name if name else "Скажи имя."

            send_reply(chat_id, reply)
            update_history(user, "assistant", reply)
            save_user(chat_id, user)
            return "ok"

        # 🔥 имя (перезапись допускается)
        name = parse_name(text)
        if name and name.isalpha():
            user["core"]["name"] = name

        extract_memory(user, text)
        update_chronicle(user, text)

        log_agent(user, "llm", text[:30])

        user["state"]["last_topic"] = text[:50]
        user["state"]["last_seen"] = datetime.now().isoformat()

        reply = ask_ai(user)

        # 🔥 обучение
        reflect(user, text, reply)
        learn(user)

        update_history(user, "assistant", reply)
        save_user(chat_id, user)

        send_reply(chat_id, reply)

    finally:
        release_processing(chat_id)

    return "ok"
