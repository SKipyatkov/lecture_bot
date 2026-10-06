from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from core.config import config
from core.database import db
from handlers.common import HELP_BUTTON, STATS_BUTTON, format_duration, html, main_keyboard


def _reply_kwargs() -> dict:
    return {"parse_mode": ParseMode.HTML, "reply_markup": main_keyboard()}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    name = html(user.first_name or "друг")
    await update.message.reply_text(
        f"<b>Привет, {name}.</b>\n\n"
        "Я расшифровываю голосовые, аудио и видео лекций.\n"
        "Язык определяю сам — выбирать его не нужно.\n\n"
        "Просто пришлите запись. Кнопки внизу — статистика и подсказка.",
        **_reply_kwargs(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_help(update.effective_message)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_stats(update.effective_message, update.effective_user)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    limit_mb = config.MAX_FILE_SIZE // (1024 * 1024)
    video_min = config.MAX_VIDEO_DURATION // 60
    await update.effective_message.reply_text(
        "<b>Как устроена расшифровка</b>\n\n"
        "Язык определяется по каждой записи.\n"
        "Аудио не уходит в облачный сервис распознавания.\n\n"
        f"Файл — до {limit_mb} МБ.\n"
        f"Видео — до {video_min} минут.",
        **_reply_kwargs(),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""
    db.add_user(user.id, user.username, user.first_name, user.last_name)

    if text == STATS_BUTTON:
        await _send_stats(update.message, user)
    elif text == HELP_BUTTON:
        await _send_help(update.message)
    else:
        await update.message.reply_text(
            "Пришлите голосовое, аудио, видео или кружок.\n"
            "Кнопки внизу открывают статистику и подсказку.",
            reply_markup=main_keyboard(),
        )


async def _send_help(message):
    await message.reply_text(
        "<b>Как пользоваться</b>\n\n"
        "1. Пришлите голосовое, аудио, видео или кружок.\n"
        "2. Я напишу, что запись в очереди.\n"
        "3. Пришлю текст и две кнопки оценки.\n\n"
        "Язык выбирается по записи.",
        **_reply_kwargs(),
    )


async def _send_stats(message, user):
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    total_requests, total_size, total_duration = db.get_user_stats(user.id) or (0, 0, 0)
    if total_requests:
        text = (
            "<b>Ваша статистика</b>\n\n"
            f"{total_requests} расшифровок\n"
            f"{total_size / (1024 * 1024):.1f} МБ\n"
            f"{format_duration(total_duration)}"
        )
    else:
        text = (
            "<b>Пока пусто</b>\n\n"
            "Пришлите голосовое или аудио — здесь появится статистика."
        )
    await message.reply_text(text, **_reply_kwargs())
