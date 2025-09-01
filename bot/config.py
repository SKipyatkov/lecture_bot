import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()

class Config:
    # Токен бота из .env файла
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    # Максимальный размер файла (20 МБ по умолчанию)
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 20971520))
    
    # Путь к модели Vosk
    VOSK_MODEL_PATH = os.getenv('VOSK_MODEL_PATH', 'models/ru-model')
    
    # Пароль администратора
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    # ID администратора
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0)) if os.getenv('ADMIN_USER_ID') else 0
    
    # Поддерживаемые языки (НОВОЕ!)
    SUPPORTED_LANGUAGES = ['ru', 'en']
    DEFAULT_LANGUAGE = 'ru'
    
    # Клавиатура главного меню
    MAIN_MENU = {
        "keyboard": [
            ["🎤 Распознать голос", "📊 Статистика"],
            ["❓ Помощь", "⚙️ Настройки", "🌍 Язык"]
        ],
        "resize_keyboard": True
    }
    
    # Клавиатура администратора
    ADMIN_MENU = {
        "keyboard": [
            ["📊 Общая статистика", "👥 Пользователи"],
            ["📋 Логи", "🔄 Перезагрузка"],
            ["⏹️ Остановка", "🔙 Назад"]
        ],
        "resize_keyboard": True
    }
    
    # Клавиатура выбора языка (НОВОЕ!)
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
        ("language", "Сменить язык"),  # НОВАЯ КОМАНДА
        ("admin", "Панель администратора")
    ]

    # Проверяем, что токен есть
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Токен бота не найден! Проверьте файл .env")

# Создаем экземпляр конфигурации
config = Config()