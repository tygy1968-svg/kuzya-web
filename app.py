from flask import Flask, request
import requests
import os

app = Flask(name)

======================

ENV

======================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

======================

TELEGRAM SEND (исправлено)

======================

def send_reply(chat_id, text):
if not TELEGRAM_TOKEN:
print("❌ NO TELEGRAM TOKEN")
return

if not text:
    text = "..."

url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

data = {
    "chat_id": chat_id,
    "text": text
}

try:
    # ⚠️ ВАЖНО: используем data= вместо json=
    r = requests.post(url, data=data)

    print("📨 TG STATUS:", r.status_code)
    print("📨 TG RESPONSE:", r.text)

except Exception as e:
    print("❌ SEND ERROR:", e)

======================

AI (тест)

======================

def ask_ai(text):
return f"Ответ на: {text}"

======================

WEBHOOK

======================

@app.route('/', methods=['POST'])
def webhook():
data = request.get_json()

print("🔥 UPDATE:", data)

if not data or "message" not in data:
    return "ok"

chat_id = data["message"]["chat"]["id"]
text = data["message"].get("text", "")

print("📩 TEXT:", text)

reply = ask_ai(text)

send_reply(chat_id, reply)

return "ok"

======================

RUN

======================

if name == "main":
app.run(host="0.0.0.0", port=10000)
