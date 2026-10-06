import os
from pathlib import Path
from dotenv import load_dotenv

from .paths import DATA_DIR, LOG_DIR, PROJECT_ROOT, TEMP_DIR

load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


class Config:
    # Корень репозитория и каталог данных (база, логи, кэш, бэкапы)
    BASE_DIR = PROJECT_ROOT
    DATA_DIR = DATA_DIR
    LOG_DIR = LOG_DIR

    # Токен бота из .env файла
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    # Пути к внешним зависимостям
    FFMPEG_PATH = os.getenv('FFMPEG_PATH', 'ffmpeg')

    # eSpeak
    ESPEAK_PATH = os.getenv('ESPEAK_PATH', 'espeak')

    # Мультиязычная модель Whisper. Относительный путь считается от корня репозитория.
    WHISPER_MODEL_PATH = _resolve_path(os.getenv(
        'WHISPER_MODEL_PATH',
        'models/faster-whisper-small',
    ))

    # Временная папка для файлов
    TEMP_DIR = TEMP_DIR

    # Максимальный размер файла (20 МБ по умолчанию)
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 20971520))

    # Пароль администратора
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

    # ID администратора
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0)) if os.getenv('ADMIN_USER_ID') else 0

    # Настройки кэширования
    CACHE_TTL_HOURS = int(os.getenv('CACHE_TTL_HOURS', 24))
    CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'

    # Настройки бэкапов
    BACKUP_ENABLED = os.getenv('BACKUP_ENABLED', 'true').lower() == 'true'
    BACKUP_INTERVAL_HOURS = int(os.getenv('BACKUP_INTERVAL_HOURS', 24))

    # Настройки плагинов
    PLUGINS_ENABLED = os.getenv('PLUGINS_ENABLED', 'true').lower() == 'true'

    # Поддерживаемые типы файлов
    SUPPORTED_FILE_TYPES = ['voice', 'audio', 'video', 'video_note']
    MAX_VIDEO_DURATION = 600  # 10 минут максимальная длительность видео

    # Настройки улучшения качества аудио
    AUDIO_ENHANCEMENT = {
        'noise_reduction': True,
        'normalize': True,
        'sample_rate': 16000,
        'channels': 1,
        'bit_depth': 16,
        'aggressive_nr': True
    }

    # Список команд для регистрации в боте
    COMMANDS = [
        ("start", "Начать"),
        ("stats", "Моя статистика"),
        ("help", "Как пользоваться"),
        ("settings", "Как устроена расшифровка"),
    ]

    # Проверяем, что токен есть
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Токен бота не найден! Проверьте файл .env")

    # Создаем временную папку если её нет
    @classmethod
    def init_temp_dir(cls):
        for directory in (cls.DATA_DIR, cls.LOG_DIR, cls.TEMP_DIR):
            directory.mkdir(parents=True, exist_ok=True)


# Создаем экземпляр конфигурации
config = Config()
config.init_temp_dir()