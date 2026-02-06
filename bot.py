import os
import sqlite3
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

import yt_dlp


# ================== الإعدادات ==================
TOKEN = "8501806873:AAHi_cDFWGHW2CavQBJkK1-im2TVeSUVM00"
ADMIN_ID = 7795462538

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users_data.db")

COOKIES_PATH = os.path.join(BASE_DIR, "cookies.txt")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# ================== قاعدة البيانات ==================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            user_id INTEGER,
            username TEXT,
            video_url TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_download(user_id, username, url):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO downloads VALUES (?, ?, ?, ?)",
            (user_id, username, url, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"DB Error: {e}")


# ================== إعدادات yt-dlp ==================
def get_ydl_extract_opts():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
    }

    # إذا cookies موجودة
    if os.path.exists(COOKIES_PATH):
        opts["cookiefile"] = COOKIES_PATH

    return opts


def get_ydl_download_opts(format_id, filename):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": f"{format_id}+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": filename,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
    }

    # إذا cookies موجودة
    if os.path.exists(COOKIES_PATH):
        opts["cookiefile"] = COOKIES_PATH

    return opts


# ================== أوامر البوت ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك!\n\n"
        "أرسل رابط فيديو من:\n"
        "• YouTube\n"
        "• TikTok\n"
        "• Instagram\n\n"
        "وسأحمله لك بأفضل جودة متاحة 🎬"
    )


# ================== معالجة الرابط ==================
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith("http"):
        return

    wait_msg = await update.message.reply_text("🔎 جاري تحليل الرابط...")

    try:
        ydl_opts = get_ydl_extract_opts()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "فيديو")
        formats = info.get("formats", [])

        buttons = []
        seen = set()

        # جلب جودات الفيديو المهمة فقط
        for f in formats:
            height = f.get("height")
            vcodec = f.get("vcodec")

            # تجاهل الصوت فقط
            if vcodec == "none":
                continue

            if height and height in (360, 480, 720, 1080) and height not in seen:
                fmt_id = f.get("format_id")
                size = f.get("filesize") or f.get("filesize_approx") or 0
                size_mb = round(size / (1024 * 1024), 1)

                label = f"🎬 {height}p"
                if size_mb > 0:
                    label += f" ({size_mb} MB)"

                buttons.append([
                    InlineKeyboardButton(
                        label,
                        callback_data=f"{fmt_id}|{url}"
                    )
                ])
                seen.add(height)

        if not buttons:
            buttons.append([
                InlineKeyboardButton(
                    "📦 أفضل جودة متاحة",
                    callback_data=f"best|{url}"
                )
            ])

        await wait_msg.edit_text(
            f"🎬 **{title[:60]}**\n\nاختر الجودة:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )

    except Exception as e:
        logging.exception("Extract Error")

        # رسالة أوضح
        await wait_msg.edit_text(
            "❌ فشل جلب بيانات الفيديو.\n\n"
            "📌 السبب غالباً:\n"
            "• يوتيوب حاجب Render IP\n"
            "• أو تحتاج cookies.txt\n"
            "• أو yt-dlp قديم\n\n"
            "✅ جرّب فيديو آخر أو تأكد من cookies."
        )


# ================== التحميل ==================
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        format_id, url = query.data.split("|")
    except ValueError:
        await query.edit_message_text("❌ خطأ في البيانات.")
        return

    user = query.from_user
    status = await query.edit_message_text("📥 جاري التحميل...")

    filename = os.path.join(BASE_DIR, f"video_{user.id}_{int(datetime.now().timestamp())}.mp4")

    try:
        save_download(user.id, user.username or user.first_name, url)

        ydl_opts = get_ydl_download_opts(format_id, filename)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(filename):
            await status.edit_text("❌ فشل إنشاء الملف.")
            return

        size = os.path.getsize(filename)

        # حد تيليجرام للبوتات غالباً 50MB
        if size > 50 * 1024 * 1024:
            await status.edit_text(
                f"⚠️ حجم الفيديو {round(size/1024/1024,1)}MB\n"
                "أكبر من حد تيليجرام (50MB).\n\n"
                "🔻 اختر جودة أقل."
            )
            return

        await status.edit_text("📤 جاري الإرسال...")

        with open(filename, "rb") as v:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=v,
                supports_streaming=True,
                caption="✅ تم التحميل بنجاح"
            )

        await status.delete()

    except Exception as e:
        logging.exception("Download Error")
        await query.message.reply_text("❌ فشل التحميل، جرّب جودة أخرى.")

    finally:
        if os.path.exists(filename):
            os.remove(filename)


# ================== إحصائيات ==================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT user_id), COUNT(*) FROM downloads")
    users, downloads = cur.fetchone()
    conn.close()

    await update.message.reply_text(
        f"📊 إحصائيات البوت:\n\n"
        f"👥 المستخدمون: {users}\n"
        f"📥 التحميلات: {downloads}"
    )


# ================== تشغيل البوت ==================
def main():
    init_db()

    app = Application.builder() \
        .token(TOKEN) \
        .connect_timeout(30) \
        .read_timeout(30) \
        .build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(download_callback))

    logging.info("🚀 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
