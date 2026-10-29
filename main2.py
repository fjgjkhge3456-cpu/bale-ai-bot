import os
import requests
import threading
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# دریافت توکن‌ها از محیط Render
BALE_TOKEN = os.environ.get("BALE_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

BALE_API_URL = f"https://tapi.bale.ai/bot{BALE_TOKEN}" if BALE_TOKEN else ""

PROCESSED_UPDATES = set()
MAX_CACHE_SIZE = 2000

# تنظیم کلید API جمنای
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("--- Gemini API configured successfully ---", flush=True)
    except Exception as e:
        print(f"Gemini config error: {e}", flush=True)

def send_message(chat_id, text):
    if not BALE_API_URL or not text:
        return
    url = f"{BALE_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}", flush=True)

def process_update_async(data):
    try:
        if not data or "message" not in data:
            return

        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()

        if not text:
            return

        if text == "/start":
            send_message(chat_id, "سلام! ربات هوش مصنوعی شما در بله آنلاین و آماده پاسخگویی است 👋🤖")
            return

        # ارتباط مستقیم و ساده با مدل جمنای
        if not GEMINI_API_KEY:
            send_message(chat_id, "❌ خطای تنظیمات: کلید API جمنای در Render وارد نشده است.")
            return

        try:
            # استفاده از مدل پایدار فلاش
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"پاسخ را به زبان فارسی روان و صمیمی بنویس:\n\n{text}"
            response = model.generate_content(prompt)
            
            if response and hasattr(response, 'text') and response.text:
                answer = response.text.strip()
            else:
                answer = "⚠️ پاسخ معتبری از هوش مصنوعی دریافت نشد."
        except Exception as gemini_err:
            print(f"Gemini API Execution Error: {gemini_err}", flush=True)
            answer = f"⚠️ خطا در پردازش هوش مصنوعی: {str(gemini_err)}"

        send_message(chat_id, answer)

    except Exception as main_err:
        print(f"Error in process_update_async: {main_err}", flush=True)

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'GET':
        return "Server is Live!", 200

    data = request.get_json()
    if not data:
        return jsonify({"status": "ok"}}, 200

    update_id = data.get("update_id")
    if update_id:
        if update_id in PROCESSED_UPDATES:
            return jsonify({"status": "already processed"}), 200
        PROCESSED_UPDATES.add(update_id)
        if len(PROCESSED_UPDATES) > MAX_CACHE_SIZE:
            PROCESSED_UPDATES.clear()

    threading.Thread(target=process_update_async, args=(data,)).start()
    return jsonify({"status": "ok"}}, 200

# تنظیم خودکار وب‌هوک
def setup_webhook_automatically():
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url and BALE_TOKEN:
        webhook_url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/setWebhook?url={render_url}/"
        try:
            res = requests.get(webhook_url, timeout=10).json()
            print(f"Auto Webhook Setup Result: {res}", flush=True)
        except Exception as e:
            print(f"Failed to auto setup webhook: {e}", flush=True)

setup_webhook_automatically()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
