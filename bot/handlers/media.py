import logging
import os

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from core.config import config
from core.database import db
from core.processing_queue import QueueFullError, processing_queue
from handlers.common import feedback_markup, format_duration, html, split_text
from pipeline.transcription import TranscriptionResult, transcribe_file
from processors.audio_processor import AudioProcessor
from processors.whisper_recognizer import language_label

logger = logging.getLogger(__name__)
audio_processor = AudioProcessor(temp_dir=str(config.TEMP_DIR))


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _enqueue_media(update, context, "audio")


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _enqueue_media(update, context, "video")


async def handle_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _enqueue_media(update, context, "video_note")


async def _enqueue_media(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str):
    user = update.effective_user
    message = update.message
    recognizer = context.bot_data.get("recognizer")
    if recognizer is None or not recognizer.is_initialized():
        await message.reply_text("Модели распознавания не загружены.")
        return

    if media_type == "video":
        media = message.video
        label = "Видео"
    elif media_type == "video_note":
        media = message.video_note
        label = "Кружок"
    elif message.voice:
        media = message.voice
        label = "Голосовое"
    elif message.audio:
        media = message.audio
        label = "Аудио"
    else:
        await message.reply_text("Пришлите голосовое, аудио или видео.")
        return

    if media.file_size and media.file_size > config.MAX_FILE_SIZE:
        limit_mb = config.MAX_FILE_SIZE // (1024 * 1024)
        await message.reply_text(f"Файл больше {limit_mb} МБ.")
        return

    duration = getattr(media, "duration", None)
    if media_type == "video" and duration and duration > config.MAX_VIDEO_DURATION:
        await message.reply_text(
            f"Видео длиннее {config.MAX_VIDEO_DURATION // 60} минут."
        )
        return

    db.add_user(user.id, user.username, user.first_name, user.last_name)
    waiting = processing_queue.get_queue_stats()["queue_size"]
    queue_note = f"\nПеред вами ещё {waiting}." if waiting else ""
    status = await message.reply_text(
        f"<b>{label} в очереди</b>\n"
        f"Язык определю по записи.{queue_note}",
        parse_mode=ParseMode.HTML,
    )

    telegram_file = await media.get_file()
    source_path = await audio_processor._download_telegram_file(telegram_file)

    if not source_path:
        await status.edit_text("Не удалось скачать файл.")
        return

    async def on_success(result: TranscriptionResult):
        request_id = db.add_audio_request(
            user.id,
            media.file_id,
            media.file_size,
            result.duration,
            result.text,
        )
        if not result.text:
            await status.edit_text("Речь не распознана. Попробуйте более тихую запись.")
            return
        header = (
            f"<b>Готово</b> · {format_duration(result.duration)}"
            f" · {html(language_label(result.language))}\n\n"
        )
        chunks = split_text(html(result.text), limit=4000 - len(header))
        markup = feedback_markup(request_id) if request_id else None
        await status.edit_text(
            header + chunks[0],
            parse_mode=ParseMode.HTML,
            reply_markup=markup if len(chunks) == 1 else None,
        )
        for index, chunk in enumerate(chunks[1:], start=1):
            is_last = index == len(chunks) - 1
            await message.reply_text(
                chunk,
                parse_mode=ParseMode.HTML,
                reply_markup=markup if is_last else None,
            )

    async def on_error(error: Exception):
        logger.error("Ошибка очереди распознавания: %s", error)
        if source_path and os.path.exists(source_path):
            os.remove(source_path)
        await status.edit_text("Не удалось обработать файл.")

    try:
        await processing_queue.submit(
            transcribe_file,
            source_path,
            recognizer,
            config.CACHE_ENABLED,
            on_success=on_success,
            on_error=on_error,
        )
    except QueueFullError:
        if os.path.exists(source_path):
            os.remove(source_path)
        await status.edit_text("Очередь занята. Пришлите файл чуть позже.")


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = (query.data or "").split("_")
    if len(parts) != 3 or parts[0] != "feedback":
        await query.answer()
        return
    request_id = int(parts[1])
    rating = int(parts[2])
    db.add_feedback(request_id, rating)
    await query.answer("Спасибо, оценка сохранена")
    await query.edit_message_reply_markup(reply_markup=None)
