import os
import sqlite3
import logging
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
    try:
        conn = sqlite3.connect('users_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO downloads VALUES (?, ?, ?, ?)', 
                       (user_id, username, url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error saving to DB: {e}")

# --- وظائف البوت الرئيسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 أهلاً بك!\n\n"
        "أرسل لي أي رابط من (YouTube, TikTok, Instagram) وسأقوم بتحميله لك بأفضل جودة متاحة."
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        return

    wait_msg = await update.message.reply_text("🔎 جاري تحليل الرابط وجلب الجودات...")

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
            
            # ترتيب الجودات الشائعة تنازلياً
            for f in reversed(formats):
                res = f.get('height')
                # نختار الجودات القياسية فقط للعرض
                if res and res not in seen_res and res in [360, 480, 720, 1080]:
                    filesize = f.get('filesize') or f.get('filesize_approx') or 0
                    size_mb = round(filesize / (1024 * 1024), 1)
                    
                    label = f"🎬 {res}p" + (f" ({size_mb} MB)" if size_mb > 0 else "")
                    # نرسل طلب الجودة مع طلب أفضل صوت مدمج
                    callback_data = f"{f['format_id']}+bestaudio/best|{url}"
                    buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])
                    seen_res.add(res)

            if not buttons:
                buttons.append([InlineKeyboardButton("📦 أفضل جودة متاحة", callback_data=f"best|{url}")])

            await wait_msg.edit_text(
                f"🎬 **العنوان:** {info.get('title')[:60]}...\n\nاختر الجودة المطلوب تحميلها:",
                reply_markup=InlineKeyboardMarkup(buttons[:8]),
                parse_mode='Markdown'
            )

    except Exception as e:
        logging.error(f"Error in handle_url: {e}")
        await wait_msg.edit_text(f"❌ فشل جلب البيانات. تأكد من أن الرابط صحيح ومن وجود ملف cookies.txt")

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # استخراج البيانات من الكولباك
    try:
        format_selection, url = query.data.split('|')
    except ValueError:
        await query.edit_message_text("❌ خطأ في البيانات المستلمة.")
        return

    user = query.from_user
    status_msg = await query.edit_message_text("📥 جاري التحميل... قد يستغرق الأمر دقيقة.")

    # اسم ملف فريد لكل عملية
    filename = f"video_{user.id}_{datetime.now().strftime('%M%S')}.mp4"

    try:
        save_download(user.id, user.username or user.first_name, url)

        ydl_opts = {
            'format': format_selection,
            'outtmpl': filename,
            'merge_output_format': 'mp4',
            'cookiefile': 'cookies.txt',
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(filename):
            filesize = os.path.getsize(filename)
            if filesize > 50 * 1024 * 1024:
                await status_msg.edit_text(f"⚠️ حجم الملف ({round(filesize/1024/1024, 1)}MB) أكبر من مسموحات تيليجرام (50MB).")
            else:
                await status_msg.edit_text("📤 جاري إرسال الفيديو...")
                with open(filename, 'rb') as video:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=video,
                        supports_streaming=True,
                        caption="✅ تم التحميل بنجاح عبر بوتك."
                    )
                await status_msg.delete()
        else:
            await status_msg.edit_text("❌ عذراً، تعذر العثور على الملف بعد التحميل.")

    except Exception as e:
        logging.error(f"Download Error: {e}")
        await query.message.reply_text(f"❌ فشل التحميل. يوتيوب قد يرفض هذه الجودة حالياً، جرب جودة أخرى.")
    
    finally:
        if os.path.exists(filename):
            os.remove(filename)

# --- نظام الإحصائيات للمسؤول ---
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect('users_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(DISTINCT user_id), COUNT(*) FROM downloads')
    res = cursor.fetchone()
    conn.close()
    
    await update.message.reply_text(f"📊 إحصائيات البوت:\n\n👥 عدد المستخدمين: {res[0]}\n📥 إجمالي التحميلات: {res[1]}")

def main():
    init_db()
    # بناء التطبيق مع زيادة مهلات الانتظار للشبكة
    app = Application.builder().token(TOKEN).connect_timeout(30).read_timeout(30).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(download_callback))
    
    logging.info("البوت بدأ العمل بنجاح...")
    app.run_polling()

if __name__ == '__main__':
    main()
