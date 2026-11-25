import os
import requests
import threading
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai

app = Flask(__name__)

BALE_TOKEN = os.environ.get("BALE_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

BALE_API_URL = f"https://tapi.bale.ai/bot{BALE_TOKEN}" if BALE_TOKEN else ""

PROCESSED_UPDATES = set()
MAX_CACHE_SIZE = 2000

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

def get_best_model():
    # تنظیم دقیق روی مدل سبک و سریع gemini-2.5-flash-lite
    return 'gemini-2.5-flash-lite'

def call_gemini_chat(text_prompt):
    if not GEMINI_API_KEY:
        return "❌ کلید API جمنای تنظیم نشده است."
    
    try:
        model_name = get_best_model()
        print(f"using model: {model_name}", flush=True)
        
        model = genai.GenerativeModel(model_name)
        prompt = f"پاسخ را به زبان فارسی روان و صمیمی بنویس:\n\n{text_prompt}"
        response = model.generate_content(prompt)
        
        if response and hasattr(response, 'text') and response.text:
            return response.text.strip()
        else:
            return "⚠️ پاسخ معتبری از هوش مصنوعی دریافت نشد."
    except Exception as e:
        print(f"Gemini Execution Error: {e}", flush=True)
        return f"⚠️ خطا در ارتباط با هوش مصنوعی: {str(e)}"

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

        answer = call_gemini_chat(text)
        send_message(chat_id, answer)

    except Exception as main_err:
        print(f"Error in process_update_async: {main_err}", flush=True)

# قالب صفحه چت وب برای نمایش در مرورگر
CHAT_PAGE_HTML = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>آرین چت | هوش مصنوعی</title>
    <style>
        body { font-family: Tahoma, sans-serif; background-color: #f4f4f9; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .chat-container { width: 100%; max-width: 600px; height: 90vh; background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }
        .chat-header { background: #4f46e5; color: white; padding: 15px; text-align: center; font-size: 18px; font-weight: bold; }
        .chat-box { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; background: #fafafa; }
        .message { padding: 10px 15px; border-radius: 8px; max-width: 75%; line-height: 1.6; word-wrap: break-word; }
        .user-message { background: #4f46e5; color: white; align-self: flex-start; border-bottom-left-radius: 2px; }
        .bot-message { background: #e5e7eb; color: #1f2937; align-self: flex-end; border-bottom-right-radius: 2px; }
        .chat-input-area { display: flex; padding: 12px; background: white; border-top: 1px solid #e5e7eb; gap: 10px; }
        .chat-input-area input { flex: 1; padding: 10px 15px; border: 1px solid #d1d5db; border-radius: 6px; outline: none; font-size: 14px; }
        .chat-input-area button { background: #4f46e5; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .chat-input-area button:hover { background: #4338ca; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">🤖 چت با هوش مصنوعی آرین</div>
        <div class="chat-box" id="chatBox">
            <div class="message bot-message">سلام! من هوش مصنوعی آرین هستم. چطور می‌توانم کمکت کنم؟ 👋</div>
        </div>
        <div class="chat-input-area">
            <input type="text" id="userInput" placeholder="پیام خود را اینجا بنویسید..." onkeypress="handleKeyPress(event)">
            <button onclick="sendMessage()">ارسال</button>
        </div>
    </div>

    <script>
        async function sendMessage() {
            const inputField = document.getElementById('userInput');
            const chatBox = document.getElementById('chatBox');
            const text = inputField.value.trim();
            if (!text) return;

            const userDiv = document.createElement('div');
            userDiv.className = 'message user-message';
            userDiv.textContent = text;
            chatBox.appendChild(userDiv);
            inputField.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            const botDiv = document.createElement('div');
            botDiv.className = 'message bot-message';
            botDiv.textContent = 'در حال تفکر... 🤖';
            chatBox.appendChild(botDiv);
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const response = await fetch('/api/web-chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await response.json();
                botDiv.textContent = data.response || data.error || 'خطایی رخ داد.';
            } catch (err) {
                botDiv.textContent = '⚠️ خطا در اتصال به سرور.';
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
    </script>
</body>
</html>
"""

@app.route('/', methods=['POST', 'GET'])
def webhook_or_home():
    if request.method == 'GET':
        return render_template_string(CHAT_PAGE_HTML)

    data = request.get_json()
    if not data:
        return jsonify({"status": "ok"}), 200

    update_id = data.get("update_id")
    if update_id:
        if update_id in PROCESSED_UPDATES:
            return jsonify({"status": "already processed"}), 200
        PROCESSED_UPDATES.add(update_id)
        if len(PROCESSED_UPDATES) > MAX_CACHE_SIZE:
            PROCESSED_UPDATES.clear()

    threading.Thread(target=process_update_async, args=(data,)).start()
    return jsonify({"status": "ok"}), 200

@app.route('/api/web-chat', methods=['POST'])
def web_chat_api():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({"error": "پیامی وارد نشده است"}), 400

        answer = call_gemini_chat(user_message)
        return jsonify({"response": answer}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
