import os
import tempfile
import logging

import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TWITTER_DOMAINS = ("twitter.com", "x.com", "t.co")


def is_twitter_url(text: str) -> bool:
    return any(domain in text for domain in TWITTER_DOMAINS)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "שלום! 👋\n"
        "שלח לי קישור של סרטון מטוויטר/X ואוריד אותו בשבילך.\n\n"
        "לדוגמה:\n"
        "https://twitter.com/user/status/123456789\n"
        "https://x.com/user/status/123456789"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()

    if not is_twitter_url(text):
        await update.message.reply_text(
            "❌ נראה שזה לא קישור של טוויטר/X.\n"
            "שלח קישור שמכיל twitter.com או x.com"
        )
        return

    status_msg = await update.message.reply_text("מוריד את הסרטון... ⏳")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                "outtmpl": os.path.join(tmp_dir, "video.%(ext)s"),
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "quiet": False,
                "no_warnings": False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                filepath = ydl.prepare_filename(info)

                # מוודא שהסיומת היא mp4
                if not filepath.endswith(".mp4"):
                    filepath = os.path.splitext(filepath)[0] + ".mp4"

            if not os.path.exists(filepath):
                # חיפוש כל קובץ שהורד בתיקיה
                files = os.listdir(tmp_dir)
                if files:
                    filepath = os.path.join(tmp_dir, files[0])
                else:
                    raise FileNotFoundError("הקובץ לא נמצא לאחר ההורדה")

            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            logger.info(f"Downloaded: {filepath} ({file_size_mb:.1f}MB)")

            if file_size_mb > 50:
                await status_msg.edit_text(
                    f"❌ הסרטון גדול מדי ({file_size_mb:.1f}MB).\n"
                    "טלגרם מאפשר שליחת קבצים עד 50MB."
                )
                return

            await status_msg.edit_text("שולח... 📤")

            with open(filepath, "rb") as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ הנה הסרטון שביקשת!",
                    supports_streaming=True,
                )

            await status_msg.delete()

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp error: {e}")
        error_text = str(e)
        if "login" in error_text.lower() or "auth" in error_text.lower() or "cookie" in error_text.lower():
            msg = "❌ טוויטר/X דורש התחברות להורדת הסרטון הזה.\nנסה קישור אחר."
        elif "private" in error_text.lower():
            msg = "❌ הסרטון פרטי ולא ניתן להורידו."
        elif "not found" in error_text.lower() or "404" in error_text:
            msg = "❌ הסרטון לא נמצא – ייתכן שנמחק."
        else:
            msg = f"❌ שגיאה בהורדה:\n<code>{error_text[:300]}</code>"
        await status_msg.edit_text(msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await status_msg.edit_text("❌ אירעה שגיאה בלתי צפויה. נסה שוב.")


def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("חסר משתנה סביבה: TELEGRAM_TOKEN")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("הבוט מופעל...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
