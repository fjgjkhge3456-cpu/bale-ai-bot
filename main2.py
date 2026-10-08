import os
import time
import requests
import google.generativeai as genai

# ---------------- تنظیمات سرور ----------------
# توکن ربات اصلی سرور (متصل به رندر)
SERVER_BOT_TOKEN = "872030909:ak1SkM_p9O1XpLz9i1BLW-8eLZQYZuOqduw"

# دریافت کلید API مستقیماً از متغیرهای محیطی Render
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("⚠️ هشدار: متغیر GEMINI_API_KEY در پنل Render تنظیم نشده است!")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

URL = f"https://tapi.bale.ai/bot{SERVER_BOT_TOKEN}"
last_update_id = 0

print("🚀 سرور هوش مصنوعی فعال شد و منتظر پیام است...")

while True:
    try:
        res = requests.get(f"{URL}/getUpdates", params={"offset": last_update_id + 1, "timeout": 10}, timeout=15).json()
        
        if res.get("ok") and res.get("result"):
            for update in res["result"]:
                last_update_id = update["update_id"]
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "")

                if text and chat_id:
                    print(f"📩 پیام دریافت شد: {text}")
                    
                    try:
                        response = model.generate_content(text)
                        reply_text = response.text
                    except Exception as e:
                        reply_text = f"❌ خطا در پردازش هوش مصنوعی: {e}"

                    requests.post(f"{URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": reply_text
                    })
                    print("پاسخ به بله ارسال شد.")
                    
    except Exception as e:
        print(f"⚠️ خطا در ارتباط: {e}")
    
    time.sleep(2)