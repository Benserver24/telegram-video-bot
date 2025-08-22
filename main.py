import os
import asyncio
import logging
import threading
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import yt_dlp
from flask import Flask, send_file

# Import config (generated at install)
from .config import BOT_TOKEN, VPS_IP

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("/var/log/video-bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
download_files = {}

class ProgressHook:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, d):
        if d["status"] == "downloading" and "total_bytes" in d:
            percent = int(d["downloaded_bytes"] / d["total_bytes"] * 100)
            progress_bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
            self.callback(f"📥 Downloading: {progress_bar} {percent}%")
        elif d["status"] == "finished":
            self.callback("✅ Download completed! Converting...")

class VideoBot:
    def __init__(self):
        self.download_path = "/tmp/videobot"
        os.makedirs(self.download_path, exist_ok=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_message = """
🎥 **Video Downloader Bot** 🎵
Send me a link, choose quality, and I’ll deliver it!
"""
        keyboard = [
            [InlineKeyboardButton("📖 Help", callback_data="help")],
            [InlineKeyboardButton("ℹ️ About", callback_data="about")],
        ]
        await update.message.reply_text(
            welcome_message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    def create_quality_keyboard(self, url: str):
        keyboard = [
            [
                InlineKeyboardButton("🎵 MP3 - Send", callback_data=f"mp3_send_{url}"),
                InlineKeyboardButton("🎵 MP3 - Link", callback_data=f"mp3_link_{url}"),
            ]
        ]
        qualities = ["144", "240", "360", "480", "720", "1080"]
        for q in qualities:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📹 {q}p - Send", callback_data=f"video_send_{q}_{url}"
                    ),
                    InlineKeyboardButton(
                        f"🔗 {q}p - Link", callback_data=f"video_link_{q}_{url}"
                    ),
                ]
            )
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        return InlineKeyboardMarkup(keyboard)

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = update.message.text
        if not any(p in url.lower() for p in ["youtube", "tiktok", "instagram", "facebook", "twitter", "vimeo"]):
            await update.message.reply_text("❌ Invalid link.")
            return

        msg = await update.message.reply_text("🔍 Analyzing video... 0%")
        try:
            await asyncio.sleep(1)
            ydl_opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            title = info.get("title", "Unknown")[:50]
            duration = info.get("duration", 0)

            if duration > 1800:
                await msg.edit_text("❌ Video too long (max 30min).")
                return

            video_info = f"""
📹 **Video Ready**
📝 {title}
⏱️ {duration//60}:{duration%60:02d}
"""
            await msg.edit_text(
                video_info, parse_mode="Markdown", reply_markup=self.create_quality_keyboard(url)
            )
        except Exception as e:
            logger.error(e)
            await msg.edit_text("❌ Failed to analyze video.")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("❌ Cancelled.")
            return
        # keep rest same as your original process_audio/video

@app.route("/download/<file_id>")
def download_file(file_id):
    if file_id not in download_files:
        return "Not found", 404
    file_info = download_files[file_id]
    if datetime.now() > file_info["expiry"]:
        if os.path.exists(file_info["path"]):
            os.remove(file_info["path"])
        del download_files[file_id]
        return "Expired", 410
    return send_file(file_info["path"], as_attachment=True, download_name=file_info["filename"])

def cleanup_expired_files():
    while True:
        now = datetime.now()
        expired = [fid for fid, f in download_files.items() if now > f["expiry"]]
        for fid in expired:
            try:
                if os.path.exists(download_files[fid]["path"]):
                    os.remove(download_files[fid]["path"])
                del download_files[fid]
            except Exception as e:
                logger.error(e)
        time.sleep(3600)

def main():
    threading.Thread(target=cleanup_expired_files, daemon=True).start()
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5000), daemon=True).start()

    bot = VideoBot()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_url))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))

    logger.info("🚀 Bot started")
    application.run_polling()

if __name__ == "__main__":
    main()
