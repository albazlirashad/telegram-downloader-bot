import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

# إعداد السجلات لمراقبة الأداء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = "8501806873:AAEJm8Za9yreXJTZT_omDtzvq8MLEZo-e1k"
ADMIN_ID = 7795462538


# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('users_data.db')
    cursor = conn.cursor()
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS downloads (user_id INTEGER, username TEXT, video_url TEXT, timestamp TEXT)')
    conn.commit()
    conn.close()


def save_download(user_id, username, url):
    conn = sqlite3.connect('users_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO downloads VALUES (?, ?, ?, ?)',
                   (user_id, username, url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


# --- المهام ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 بوت التحميل الاحترافي جاهز!\nأرسل الرابط وسأعرض لك الجودات المتاحة.")


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"): return

    wait_msg = await update.message.reply_text("🔎 جاري فحص الرابط...")

    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

            buttons = []
            seen_res = set()

            # ترتيب الجودات الشائعة
            for f in reversed(formats):
                res = f.get('height')
                if res and res not in seen_res and res in [144, 240, 360, 480, 720, 1080]:
                    filesize = f.get('filesize') or f.get('filesize_approx') or 0
                    size_mb = round(filesize / (1024 * 1024), 1)

                    # علامة تحذير إذا كان الحجم أكبر من 50MB (حد تيليجرام المجاني)
                    prefix = "✅" if size_mb < 50 else "⚠️"
                    label = f"{prefix} {res}p ({size_mb} MB)"

                    buttons.append([InlineKeyboardButton(label, callback_data=f"{f['format_id']}|{url}")])
                    seen_res.add(res)

            if not buttons:
                buttons.append([InlineKeyboardButton("📦 أفضل جودة متاحة", callback_data=f"best|{url}")])

            await wait_msg.edit_text(f"🎬 **العنوان:** {info.get('title')[:50]}...\n\nاختر الجودة:",
                                     reply_markup=InlineKeyboardMarkup(buttons[:8]), parse_mode='Markdown')

    except Exception as e:
        await wait_msg.edit_text(f"❌ خطأ: {str(e)}")


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    format_id, url = query.data.split('|')
    user = query.from_user

    status_msg = await query.edit_message_text("📥 جاري التحميل والمعالجة...")

    # اسم الملف يعتمد على معرف المستخدم ورسالة التليجرام لضمان عدم التكرار
    filename = f"video_{user.id}_{query.message.message_id}.mp4"

    try:
        save_download(user.id, user.username or user.first_name, url)

        ydl_opts = {
            'format': f"{format_id}+bestaudio/best",
            'outtmpl': filename,
            'merge_output_format': 'mp4',
            'quiet': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # التأكد من وجود الملف وحجمه قبل الإرسال
        if os.path.exists(filename):
            if os.path.getsize(filename) > 50 * 1024 * 1024:
                await status_msg.edit_text("⚠️ الفيديو جاهز ولكن حجمه أكبر من 50MB (حد تيليجرام للبوتات).")
            else:
                await status_msg.edit_text("📤 جاري الإرسال...")
                with open(filename, 'rb') as video:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=video,
                        supports_streaming=True
                    )
                await status_msg.delete()

        if os.path.exists(filename): os.remove(filename)

    except Exception as e:
        await query.message.reply_text(f"❌ فشل: {str(e)}")
        if os.path.exists(filename): os.remove(filename)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    conn = sqlite3.connect('users_data.db');
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(DISTINCT user_id), COUNT(*) FROM downloads');
    data = cursor.fetchone()
    conn.close()
    await update.message.reply_text(f"📊 إحصائيات:\n👥 مستخدمين: {data[0]}\n📥 تحميلات: {data[1]}")


def main():
    init_db()
    app = Application.builder().token(TOKEN).read_timeout(120).write_timeout(120).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(download_callback))
    app.run_polling()


if __name__ == '__main__': main()