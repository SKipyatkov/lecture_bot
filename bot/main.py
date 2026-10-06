import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from telegram import BotCommand, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from core.config import config
from core.database import db
from core.processing_queue import processing_queue
from handlers.commands import (
    handle_text,
    help_command,
    settings_command,
    start_command,
    stats_command,
)
from handlers.media import handle_audio, handle_feedback, handle_video, handle_video_note
from processors.whisper_recognizer import WhisperRecognizer
from services.backup_service import backup_service
from utils.system_check import system_checker

logger = logging.getLogger(__name__)


def setup_logging():
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = config.LOG_DIR / "bot.log"
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


async def post_init(application: Application):
    await processing_queue.start()
    await application.bot.set_my_commands(
        [BotCommand(name, description) for name, description in config.COMMANDS]
    )
    logger.info("Очередь запущена, команды зарегистрированы")


async def post_shutdown(application: Application):
    await processing_queue.stop()
    backup_service.stop_auto_backup()


def build_application(recognizer: WhisperRecognizer) -> Application:
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data["recognizer"] = recognizer
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^feedback_"))
    return application


def main():
    setup_logging()
    deps = system_checker.check_dependencies()
    if not deps.get("ffmpeg", {}).get("available"):
        logger.warning("ffmpeg не найден. Конвертация аудио не заработает.")

    if not db.init_db():
        raise SystemExit("Не удалось подключиться к PostgreSQL")
    recognizer = WhisperRecognizer(config.WHISPER_MODEL_PATH)
    if not recognizer.initialize():
        raise SystemExit("Не удалось загрузить модель Whisper")

    if config.BACKUP_ENABLED:
        backup_service.start_auto_backup(config.BACKUP_INTERVAL_HOURS)

    logger.info("Запуск бота, язык определяется по записи")
    build_application(recognizer).run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
