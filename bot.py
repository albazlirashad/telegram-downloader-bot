import os
import sqlite3
import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import yt_dlp

# إعداد السجلات لمراقبة أداء البوت في Render
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- الإعدادات الأساسية ---
TOKEN = "8501806873:AAGHntt7S4TZoObTGdKpO_hhIeqUspi3U_Q"
ADMIN_ID = 7795462538 

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('users_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            user_id INTEGER,
            username TEXT,
            video_url TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_download(user_id, username, url):
    conn = sqlite3.connect('users_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO downloads VALUES (?, ?, ?, ?)', 
                   (user_id, username, url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# --- وظائف البوت الرئيسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 أهلاً {user.first_name}!\n\n"
        "أنا بوت تحميل فيديوهات احترافي. أرسل لي أي رابط (YouTube, TikTok, Instagram) وسأعرض لك الجودات المتاحة."
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        return

    wait_msg = await update.message.reply_text("🔎 جاري جلب الجودات المتاحة...")

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': 'cookies.txt' 
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            buttons = []
            seen_res = set()
            
            # ترتيب الجودات الشائعة
            for f in reversed(formats):
                res = f.get('height')
                # نركز على الصيغ التي تحتوي على فيديو وصوت أو فيديو قابل للدمج
                if res and res not in seen_res and res in [144, 240, 360, 480, 720, 1080]:
                    filesize = f.get('filesize') or f.get('filesize_approx') or 0
                    size_mb = round(filesize / (1024 * 1024), 1)
                    
                    prefix = "✅" if size_mb < 50 else "⚠️"
                    label = f"{prefix} {res}p ({size_mb} MB)"
                    
                    # نرسل format_id لضمان تحميل ما اختاره المستخدم بالضبط
                    buttons.append([InlineKeyboardButton(label, callback_data=f"{f['format_id']}|{url}")])
                    seen_res.add(res)

            if not buttons:
                buttons.append([InlineKeyboardButton("📦 أفضل جودة متاحة", callback_data=f"best|{url}")])

            await wait_msg.edit_text(
                f"🎬 **العنوان:** {info.get('title')[:60]}...\n\nاختر الجودة المطلوب تحميلها:",
                reply_markup=InlineKeyboardMarkup(buttons[:8]),
                parse_mode='Markdown'
            )

    except Exception as e:
        await wait_msg.edit_text(f"❌ خطأ في جلب البيانات.\n\nالتفاصيل: {str(e)}")

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    format_data, url = query.data.split('|')
    user = query.from_user
    
    status_msg = await query.edit_message_text("📥 جاري التحميل والدمج...")

    filename = f"vid_{user.id}_{query.message.message_id}.mp4"

    try:
        save_download(user.id, user.username or user.first_name, url)

        # التعديل الجوهري هنا: نستخدم الجودة المختارة + أفضل صوت متاح
        ydl_opts = {
            'format': f'{format_data}+bestaudio/best', 
            'outtmpl': filename,
            'merge_output_format': 'mp4',
            'cookiefile': 'cookies.txt',
            'quiet': True,
            'postprocessor_args': ['-c:v', 'copy', '-c:a', 'aac'] # لسرعة الدمج
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(filename):
            filesize = os.path.getsize(filename)
            if filesize > 50 * 1024 * 1024:
                await status_msg.edit_text("⚠️ الحجم {round(filesize/1024/1024, 1)}MB تجاوز حد تيليجرام (50MB).")
            else:
                await status_msg.edit_text("📤 جاري الإرسال...")
                with open(filename, 'rb') as video:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=video,
                        supports_streaming=True,
                        caption="✅ تم التحميل بنجاح!"
                    )
                await status_msg.delete()
        
        if os.path.exists(filename): os.remove(filename)

    except Exception as e:
        await query.message.reply_text(f"❌ فشل التحميل: {str(e)}")
        if os.path.exists(filename): os.remove(filename)

# --- نظام الإحصائيات ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('users_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT user_id, username FROM downloads')
    users = cursor.fetchall()
    
    if not users:
        await update.message.reply_text("📊 السجل فارغ.")
        conn.close()
        return

    report = "📊 **إحصائيات النشاط:**\n"
    for user_id, username in users:
        cursor.execute('SELECT COUNT(*) FROM downloads WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        report += f"\n👤 {username} (`{user_id}`): {count} تحميلات"
    
    conn.close()
    await update.message.reply_text(report, parse_mode='Markdown')

def main():
    init_db()
    app = Application.builder().token(TOKEN).read_timeout(200).write_timeout(200).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(download_callback))
    
    app.run_polling()

if __name__ == '__main__':
    main()
