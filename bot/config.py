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
    
    # Проверяем, что токен есть
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Токен бота не найден! Проверьте файл .env")

# Создаем экземпляр конфигурации
config = Config()