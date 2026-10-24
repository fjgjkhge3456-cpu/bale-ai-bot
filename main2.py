import os
import requests
from flask import Flask
import threading
import time
from google import genai

app = Flask(__name__)

SERVER_BOT_TOKEN = os.environ.get("SERVER_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)
URL_SERVER = f"https://tapi.bale.ai/bot{SERVER_BOT_TOKEN}"
last_update_id = 0

@app.route('/')
def home():
    return "Bot Server is Running Live!"

def process_updates():
    global last_update_id
    print("🚀 سرور هوش مصنوعی بله آنلاین شد...")
    while True:
        try:
            res = requests.get(f"{URL_SERVER}/getUpdates", params={"offset": last_update_id + 1}, timeout=10).json()
            if res.get("ok") and res.get("result"):
                for update in res["result"]:
                    up_id = update.get("update_id", 0)
                    if up_id > last_update_id:
                        last_update_id = up_id
                        msg = update.get("message", {})
                        chat_id = msg.get("chat", {}).get("id")
                        text = msg.get("text", "")
                        
                        if text and chat_id:
                            print(f"📩 پیام دریافت شد: {text}")
                            try:
                                # استفاده از مدل رسمی و بسیار سریع Gemini 2.0 Flash Lite
                                response = ai_client.models.generate_content(
                                    model='gemini-2.0-flash-lite',
                                    contents=text,
                                )
                                reply_text = response.text if response.text else "پاسخی دریافت نشد."
                            except Exception as e:
                                print(f"❌ خطای جمنای: {e}")
                                reply_text = f"خطا در پردازش هوش مصنوعی: {e}"

                            requests.post(f"{URL_SERVER}/sendMessage", json={
                                "chat_id": chat_id,
                                "text": reply_text
                            })
        except Exception as e:
            print(f"⚠️ خطای حلقه اصلی: {e}")
        time.sleep(2)

threading.Thread(target=process_updates, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
