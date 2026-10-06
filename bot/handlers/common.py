from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.constants import KeyboardButtonStyle

STATS_BUTTON = "📊 Статистика"
HELP_BUTTON = "❓ Помощь"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[
            KeyboardButton(STATS_BUTTON, style=KeyboardButtonStyle.PRIMARY),
            KeyboardButton(HELP_BUTTON, style=KeyboardButtonStyle.SUCCESS),
        ]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Голосовое, аудио или видео",
    )


def feedback_markup(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "👍 Хорошо",
            callback_data=f"feedback_{request_id}_5",
            style=KeyboardButtonStyle.SUCCESS,
        ),
        InlineKeyboardButton(
            "👎 Плохо",
            callback_data=f"feedback_{request_id}_1",
            style=KeyboardButtonStyle.DANGER,
        ),
    ]])


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    if total < 60:
        return f"{total} сек"
    minutes, secs = divmod(total, 60)
    if secs == 0:
        return f"{minutes} мин"
    return f"{minutes} мин {secs} сек"


def split_text(text: str, limit: int = 4000) -> list[str]:
    return [text[i:i + limit] for i in range(0, len(text), limit)] or [""]


def html(text: str) -> str:
    return escape(text)
