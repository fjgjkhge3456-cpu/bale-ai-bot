import os
import requests
import threading
import urllib.parse
import random
from flask import Flask, request, jsonify
import google.generativeai as genai
from PIL import Image
import io

app = Flask(__name__)

# دریافت تنظیمات محیطی از Render
BALE_TOKEN = os.environ.get("BALE_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

BALE_API_URL = f"https://tapi.bale.ai/bot{BALE_TOKEN}" if BALE_TOKEN else ""
BALE_FILE_URL = f"https://tapi.bale.ai/file/bot{BALE_TOKEN}" if BALE_TOKEN else ""

PROCESSED_UPDATES = set()
MAX_CACHE_SIZE = 2000

# دستور سیستم برای پاسخ‌دهی صمیمی و فارسی
SYSTEM_INSTRUCTION = "پاسخ را فقط و فقط به زبان فارسی روان، صمیمی و با استفاده مناسب از ایموجی بنویس."

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("--- Gemini API آماده است ---", flush=True)
    except Exception as e:
        print(f"!!! خطا در تنظیم API جمنای: {e} !!!", flush=True)

MODELS_TO_TRY = ['gemini-1.5-flash', 'gemini-1.5-pro']

def clean_bot_response(text):
    if not text:
        return ""
    lines = text.strip().split('\n')
    filtered_lines = []
    for line in lines:
        l = line.strip().lower()
        if any(keyword in l for keyword in ['user input', 'constraint', 'persona', 'final response']):
            continue
        filtered_lines.append(line)
    return '\n'.join(filtered_lines).strip()

def call_gemini_chat(text_prompt):
    if not GEMINI_API_KEY:
        return "❌ خطا: کلید GEMINI_API_KEY در تنظیمات Render وارد نشده است."
    
    last_err = ""
    for model_name in MODELS_TO_TRY:
        try:
            model = genai.GenerativeModel(model_name, system_instruction=SYSTEM_INSTRUCTION)
            response = model.generate_content(text_prompt)
            if response and hasattr(response, 'text') and response.text:
                return clean_bot_response(response.text)
        except Exception as e:
            last_err = str(e)
            print(f"Chat error on {model_name}: {e}", flush=True)
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(f"{SYSTEM_INSTRUCTION}\n\n{text_prompt}")
                if response and hasattr(response, 'text') and response.text:
                    return clean_bot_response(response.text)
            except Exception as inner_e:
                last_err = str(inner_e)
                print(f"Inner error on {model_name}: {inner_e}", flush=True)
            continue
            
    return f"⚠️ خطای جمنای: {last_err}"

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
            send_message(chat_id, "سلام! ربات هوش مصنوعی شما آماده است 👋🤖")
            return

        # پاسخ به چت متنی
        answer = call_gemini_chat(text)
        send_message(chat_id, answer)

    except Exception as main_err:
        print(f"Error in process_update_async: {main_err}", flush=True)
        try:
            chat_id = data.get("message", {}).get("chat", {}).get("id")
            if chat_id:
                send_message(chat_id, f"❌ خطای سرور: {str(main_err)}")
        except:
            pass

@app.route('/', methods=['POST', 'GET'])
def webhook():
    if request.method == 'GET':
        return "Server is Live!", 200

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
