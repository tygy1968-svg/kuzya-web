from flask import Flask, request
import requests
import os

app = Flask(name)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

def send_reply(chat_id, text):
if not TELEGRAM_TOKEN:
print("NO TOKEN")
return

url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

data = {
    "chat_id": chat_id,
    "text": text
}

r = requests.post(url, data=data)

print("STATUS:", r.status_code)
print("RESPONSE:", r.text)

@app.route('/', methods=['POST'])
def webhook():
data = request.get_json()

print("UPDATE:", data)

if not data or "message" not in data:
    return "ok"

chat_id = data["message"]["chat"]["id"]
text = data["message"].get("text", "")

print("TEXT:", text)

send_reply(chat_id, f"Ты написала: {text}")

return "ok"

if name == "main":
app.run(host="0.0.0.0", port=10000)
