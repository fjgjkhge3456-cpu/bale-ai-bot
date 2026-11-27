import streamlit as st
import sqlite3
import datetime
import os
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps

# تنظیمات اصلی صفحه
st.set_page_config(page_title="ربات هوش مصنوعی آرین", page_icon="🤖", layout="centered")

# دریافت کلید API از متغیرهای محیطی Render
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# راه‌اندازی دیتابیس محلی
def init_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            name TEXT,
            text_count INT,
            image_count INT,
            video_count INT,
            last_login TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            name TEXT,
            action_type TEXT,
            content TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# مقداردهی نشست‌ها (Session State)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_phone" not in st.session_state:
    st.session_state.user_phone = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "messages" not in st.session_state:
    st.session_state.messages = []

def log_activity(phone, name, action_type, content):
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activity_logs (phone, name, action_type, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (phone, name, action_type, content, str(datetime.datetime.now()))
    )
    conn.commit()
    conn.close()

def get_or_create_user(phone, name):
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (phone, name, text_count, image_count, video_count, last_login) VALUES (?, ?, 0, 0, 0, ?)",
            (phone, name, str(datetime.datetime.now()))
        )
        conn.commit()
    conn.close()

# ----------------- سیستم ورود -----------------
if not st.session_state.authenticated:
    st.title("🔐 ورود به ربات هوش مصنوعی")
    st.write("لطفاً نام و شماره تلفن خود را وارد کنید تا وارد سامانه شوید.")
    
    name_input = st.text_input("نام و نام خانوادگی:")
    phone_input = st.text_input("شماره تلفن همراه (مثلا 09123456789):")
    
    if st.button("ورود به سایت 🚀"):
        if name_input and phone_input:
            st.session_state.user_name = name_input
            st.session_state.user_phone = phone_input
            st.session_state.authenticated = True
            get_or_create_user(phone_input, name_input)
            log_activity(phone_input, name_input, "ورود", "کاربر وارد سامانه شد")
            st.rerun()
        else:
            st.error("❌ لطفاً هم نام و هم شماره تلفن را وارد کنید.")

else:
    st.sidebar.success(f"👤 کاربر: {st.session_state.user_name}")
    if st.sidebar.button("خروج از حساب 🚪"):
        st.session_state.authenticated = False
        st.rerun()

    menu = st.selectbox(
        "منوی اصلی سایت 👇",
        ["💬 چت هوشمند (Gemini)", "🎨 تولید با Flux و ویرایش آزاد عکس", "🎬 استودیوی ویدیوی واقعی", "🔑 بخش ادمین"]
    )

    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT text_count, image_count, video_count FROM users WHERE phone = ?", (st.session_state.user_phone,))
    u_data = cursor.fetchone()
    t_cnt, i_cnt, v_cnt = u_data if u_data else (0, 0, 0)
    conn.close()

    # ----------------- چت هوشمند جمنای با دریافت هوشمند مدل‌ها -----------------
    if menu == "💬 چت هوشمند (Gemini)":
        st.title("💬 چت هوشمند زنده (Google Gemini)")
        st.write(f"سلام {st.session_state.user_name} جان! سوالت رو بپرس تا کلمه‌به‌کلمه برات تایپ کنم.")
        
        # نمایش تاریخچه چت
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_prompt := st.chat_input("پیام خود را بنویسید..."):
            if t_cnt >= 200:
                st.error("❌ سهمیه پیام امروز شما تمام شده است!")
            else:
                conn = sqlite3.connect("database.db", check_same_thread=False)
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET text_count = text_count + 1 WHERE phone = ?", (st.session_state.user_phone,))
                conn.commit()
                conn.close()
                
                log_activity(st.session_state.user_phone, st.session_state.user_name, "چت", user_prompt)
                
                st.session_state.messages.append({"role": "user", "content": user_prompt})
                with st.chat_message("user"):
                    st.markdown(user_prompt)

                with st.chat_message("assistant"):
                    response_stream = None
                    last_error = ""

                    # 1. دریافت هوشمند تمام مدل‌های فعال اکانت شما از گوگل
                    available_models = []
                    try:
                        for m in genai.list_models():
                            if 'generateContent' in m.supported_generation_methods:
                                available_models.append(m.name)
                    except Exception as e:
                        last_error = str(e)

                    # 2. لیست پشتیبان در صورت عدم دریافت لیست مستقیم
                    if not available_models:
                        available_models = [
                            "models/gemini-2.5-flash",
                            "models/gemini-2.0-flash",
                            "models/gemini-1.5-flash",
                            "models/gemini-1.5-pro"
                        ]

                    # آماده‌سازی تاریخچه چت
                    chat_history = []
                    for msg in st.session_state.messages[-6:]:
                        role = "user" if msg["role"] == "user" else "model"
                        chat_history.append({"role": role, "parts": [msg["content"]]})

                    # تلاش برای فراخوانی مدل‌های فعال به ترتیب
                    for m_name in available_models:
                        try:
                            model = genai.GenerativeModel(m_name)
                            chat = model.start_chat(history=chat_history[:-1])
                            response_stream = chat.send_message(user_prompt, stream=True)
                            if response_stream:
                                break
                        except Exception as e:
                            last_error = str(e)
                            continue

                    if response_stream:
                        def generate_chunks():
                            for chunk in response_stream:
                                if chunk.text:
                                    yield chunk.text

                        full_response = st.write_stream(generate_chunks)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
                    else:
                        st.error(f"❌ خطایی در اتصال به جمنای رخ داد: {last_error}")

    # ----------------- بخش‌های دیگر -----------------
    elif menu == "🎨 تولید با Flux و ویرایش آزاد عکس":
        st.title("🎨 تولید با Flux و ویرایش دستی عکس")
        tab1, tab2 = st.tabs(["ساخت تصویر با Flux 🌟", "ویرایش آزاد عکس 🛠️"])
        
        with tab1:
            flux_prompt = st.text_input("توضیح تصویر:", key="flux_p")
            if st.button("تولید تصویر با Flux 🚀"):
                if flux_prompt:
                    st.image(f"https://image.pollinations.ai/prompt/{flux_prompt}?model=flux&width=1024&height=1024&nologo=true", use_container_width=True)

        with tab2:
            edit_file = st.file_uploader("عکس خود را آپلود کنید:", type=["jpg", "png", "jpeg"], key="edit_img")
            user_edit_instruction = st.text_input("دستور ویرایش (روشنایی، سیاه و سفید، تاریک، چرخش):")
            if st.button("اعمال ویرایش روی عکس 🪄") and edit_file:
                image = Image.open(edit_file)
                inst = user_edit_instruction.lower()
                if "روشنایی" in inst:
                    image = ImageEnhance.Brightness(image).enhance(1.6)
                elif "سیاه و سفید" in inst:
                    image = ImageOps.grayscale(image)
                st.image(image, use_container_width=True)

    elif menu == "🎬 استودیوی ویدیوی واقعی":
        st.title("🎬 استودیوی رندر ویدیو")
        video_prompt = st.text_input("پرامپت ویدیو:")
        if st.button("ساخت و رندر ویدیوی واقعی 🎥") and video_prompt:
            st.video(f"https://image.pollinations.ai/prompt/cinematic%20video%20{video_prompt}?width=720&height=720&nologo=true")

    elif menu == "🔑 بخش ادمین":
        st.title("🔑 پنل مدیریت")
        if st.text_input("رمز عبور:", type="password") == "2345":
            conn = sqlite3.connect("database.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT phone, name, text_count FROM users")
            for u in cursor.fetchall():
                st.write(f"📞 {u[0]} | 👤 {u[1]} | پیام‌ها: {u[2]}")
            conn.close()
