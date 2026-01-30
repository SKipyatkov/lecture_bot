import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Базовый путь проекта
    BASE_DIR = Path(__file__).parent

    # Токен бота из .env файла
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    # Пути к внешним зависимостям
    # FFmpeg
    FFMPEG_PATH = "ffmpeg"  # или os.getenv('FFMPEG_PATH', 'ffmpeg')

    # eSpeak
    ESPEAK_PATH = os.getenv('ESPEAK_PATH', 'espeak')

    # Пути к моделям Vosk - АБСОЛЮТНЫЕ пути
    VOSK_MODEL_PATHS = {
        'ru': os.getenv('VOSK_MODEL_PATH_RU', r'C:\projects\lecture_bot\models\vosk-model-ru-0.42'),
        'en': os.getenv('VOSK_MODEL_PATH_EN', r'C:\projects\lecture_bot\models\vosk-model-en-us-0.42-gigaspeech')
    }

    # Проверка существования моделей
    @classmethod
    def check_models_exist(cls):
        missing_models = []
        for lang, path in cls.VOSK_MODEL_PATHS.items():
            if not os.path.exists(path):
                missing_models.append((lang, path))
        return missing_models

    # Временная папка для файлов
    TEMP_DIR = BASE_DIR / "temp"

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

    # Поддерживаемые языки
    SUPPORTED_LANGUAGES = ['ru', 'en']
    DEFAULT_LANGUAGE = 'ru'

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

    # Настройки Vosk для улучшения распознавания
    VOSK_SETTINGS = {
        'max_alternatives': 5,
        'words': True,
        'partial_results': True,
        'speech_timeout': 0.3,
        'min_confidence': 0.6
    }

    # Клавиатура главного меню
    MAIN_MENU = {
        "keyboard": [
            ["🎤 Распознать голос", "📊 Статистика"],
            ["🗃️ Пакетная обработка", "🔊 Озвучить текст"],
            ["❓ Помощь", "⚙️ Настройки", "🌍 Язык"]
        ],
        "resize_keyboard": True
    }

    # Клавиатура администратора
    ADMIN_MENU = {
        "keyboard": [
            ["📊 Общая статистика", "👥 Пользователи"],
            ["📋 Логи", "🔄 Перезагрузка", "🌐 Веб-панель"],
            ["💾 Создать бэкап", "⏹️ Остановка", "🔙 Назад"]
        ],
        "resize_keyboard": True
    }

    # Клавиатура выбора языка
    LANGUAGE_MENU = {
        "keyboard": [
            ["🇷🇺 Русский", "🇺🇸 English"],
            ["🔙 Назад"]
        ],
        "resize_keyboard": True
    }

    # Список команд для регистрации в боте
    COMMANDS = [
        ("start", "Запустить бота"),
        ("stats", "Показать статистику"),
        ("help", "Показать справку"),
        ("settings", "Настройки бота"),
        ("language", "Сменить язык"),
        ("admin", "Панель администратора"),
        ("batch", "Пакетная обработка"),
        ("voice", "Озвучить текст")
    ]

    # Проверяем, что токен есть
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Токен бота не найден! Проверьте файл .env")

    # Создаем временную папку если её нет
    @classmethod
    def init_temp_dir(cls):
        cls.TEMP_DIR.mkdir(exist_ok=True)


# Создаем экземпляр конфигурации
config = Config()
config.init_temp_dir()