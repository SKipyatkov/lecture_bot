import os
import logging
import asyncio
import traceback
import psutil
import gc
import torch
from datetime import datetime
from telegram import Update
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Импортируем наши модули
from config import config
from database import db
from audio_processor import AudioProcessor
from vosk_recognizer import VoskRecognizer
from text_enhancer import text_enhancer

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(f'bot_log_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Словарь для хранения сессий администратора
admin_sessions = {}

# Словарь для хранения языков пользователей
user_languages = {}

# Функция для детального логирования ошибок
def log_error(error_type, error, update=None):
    """Детальное логирование ошибок"""
    error_msg = f"❌ {error_type}: {error}"
    logger.error(error_msg)
    
    if update and hasattr(update, 'effective_user'):
        user_info = f"User: {update.effective_user.id} {update.effective_user.username}"
        logger.error(f"   {user_info}")
    
    logger.error(f"   Traceback: {traceback.format_exc()}")
    return error_msg

# Функция для мониторинга памяти
def get_memory_usage():
    """Возвращает информацию об использовании памяти"""
    process = psutil.Process()
    memory_info = process.memory_info()
    return {
        'rss_mb': memory_info.rss / 1024 / 1024,
        'vms_mb': memory_info.vms / 1024 / 1024,
        'percent': process.memory_percent()
    }

# Проверка прав администратора
def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    if config.ADMIN_USER_ID == 0:
        return False  # Админ не настроен
    return user_id == config.ADMIN_USER_ID or admin_sessions.get(user_id, False)

# Проверка режима администратора
def is_in_admin_mode(user_id):
    """Проверяет, находится ли пользователь в режиме администратора (активная сессия)"""
    return admin_sessions.get(user_id, False)

# Получение языка пользователя
def get_user_language(user_id):
    """Возвращает язык пользователя"""
    return user_languages.get(user_id, config.DEFAULT_LANGUAGE)

# Глобальный обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    try:
        log_error("Global error", context.error, update)
        
        if update and update.effective_message:
            error_text = (
                "❌ Произошла непредвиденная ошибка.\n"
                "🛠️ Разработчик уже уведомлен.\n"
                "🔄 Попробуйте отправить сообщение еще раз."
            )
            await update.effective_message.reply_text(error_text)
            
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

# Инициализация распознавателя Vosk
try:
    recognizer = VoskRecognizer(config.VOSK_MODEL_PATHS)
    logger.info("✅ Модели Vosk успешно загружены!")
    logger.info(f"Доступные языки: {recognizer.get_available_languages()}")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации Vosk: {e}")
    recognizer = None

# Команда: /language
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды для смены языка"""
    user = update.effective_user
    
    # Проверяем доступные языки в Vosk
    available_languages = recognizer.get_available_languages() if recognizer else ['ru']
    
    keyboard = []
    if 'ru' in available_languages:
        keyboard.append(["🇷🇺 Русский"])
    if 'en' in available_languages:
        keyboard.append(["🇺🇸 English"])
    keyboard.append(["🔙 Назад"])
    
    language_menu = {
        "keyboard": keyboard,
        "resize_keyboard": True
    }
    
    await update.message.reply_text(
        "🌍 Выберите язык распознавания:\n\n"
        "• 🇷🇺 Русский - для лекций на русском\n"
        "• 🇺🇸 English - для английских лекций\n\n"
        "Бот автоматически определит язык, но выбор приоритетного языка улучшит точность!",
        reply_markup=language_menu
    )

# Команда: /admin
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin"""
    user = update.effective_user
    
    # Проверяем права администратора (не режим!)
    if user.id != config.ADMIN_USER_ID and config.ADMIN_USER_ID != 0:
        await update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    # Проверяем пароль
    if len(context.args) == 0:
        await update.message.reply_text(
            "🔐 Введите пароль администратора:\n"
            "Пример: /admin ваш_пароль"
        )
        return
    
    password = context.args[0]
    if password != config.ADMIN_PASSWORD:
        await update.message.reply_text("❌ Неверный пароль администратора!")
        return
    
    # Сохраняем сессию администратора
    admin_sessions[user.id] = True
    db.add_admin_session(user.id)
    
    await update.message.reply_text(
        "👑 Добро пожаловать в панель администратора!",
        reply_markup=config.ADMIN_MENU
    )

# Обработка админ-меню
async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений в режиме администратора"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    text = update.message.text
    
    if text == "📊 Общая статистика":
        stats = db.get_global_stats()
        total_users, total_requests, total_size, total_duration = stats
        
        stats_text = (
            f"📊 Глобальная статистика:\n\n"
            f"• Всего пользователей: {total_users}\n"
            f"• Всего запросов: {total_requests}\n"
            f"• Общий объем данных: {total_size / (1024*1024):.1f} МБ\n"
            f"• Общая длительность: {total_duration / 60:.1f} минут\n"
            f"• Активных сессий админа: {len(admin_sessions)}\n"
            f"• Доступные языки Vosk: {', '.join(recognizer.get_available_languages()) if recognizer else 'Нет'}"
        )
        await update.message.reply_text(stats_text)
        
    elif text == "👥 Пользователи":
        users = db.get_all_users()
        if not users:
            await update.message.reply_text("📝 Пользователей пока нет.")
            return
        
        users_text = "👥 Список пользователей:\n\n"
        for i, user in enumerate(users[:10], 1):  # Показываем первых 10
            user_id, username, first_name, last_name, requests, last_active = user
            users_text += f"{i}. {first_name} {last_name} (@{username})\n"
            users_text += f"   ID: {user_id}, Запросов: {requests}\n"
            users_text += f"   Последняя активность: {last_active}\n\n"
        
        if len(users) > 10:
            users_text += f"... и еще {len(users) - 10} пользователей"
        
        await update.message.reply_text(users_text)
        
    elif text == "📋 Логи":
        try:
            log_file = f'bot_log_{datetime.now().strftime("%Y%m%d")}.log'
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = f.read()[-4000:]  # Последние 4000 символов
                await update.message.reply_text(f"📋 Последние логи:\n\n```\n{logs}\n```", parse_mode='Markdown')
            else:
                await update.message.reply_text("📋 Файл логов не найден.")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка чтения логов: {e}")
            
    elif text == "🔄 Перезагрузка":
        await update.message.reply_text("🔄 Перезагрузка бота...")
        # Здесь будет код перезагрузки
        
    elif text == "⏹️ Остановка":
        await update.message.reply_text("⏹️ Остановка бота...")
        # Здесь будет код остановки
        
    elif text == "🔙 Назад":
        if user.id in admin_sessions:
            del admin_sessions[user.id]
            db.end_admin_session(user.id)
        await update.message.reply_text(
            "🔙 Возврат в обычный режим",
            reply_markup=config.MAIN_MENU
        )
        
    else:
        await update.message.reply_text("Неизвестная команда админа")

# Команда: /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = (
        "🎤 Привет! Я бот для преобразования голосовых сообщений в текст.\n\n"
        "📝 Просто отправь мне голосовое сообщение или аудиофайл, "
        "и я преобразую его в текст с помощью локальной нейросети!\n\n"
        "⚡ Работаю полностью оффлайн и бесплатно!\n"
        "🌍 Поддерживаю русский и английский языки\n"
        "✨ Автоматически исправляю опечатки и добавляю пунктуацию!\n\n"
        "📎 Максимальный размер файла: 20 МБ"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=config.MAIN_MENU
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "❓ Как пользоваться ботом:\n\n"
        "1. 🎤 Отправь голосовое сообщение\n"
        "2. 📎 Или отправь аудиофайл (MP3, OGG, WAV)\n"
        "3. ⏳ Подожди 10-60 секунд\n"
        "4. 📝 Получи улучшенный текст с пунктуацией!\n\n"
        "✨ Новые возможности:\n"
        "• 🤖 Автоисправление опечаток\n"
        "• 📝 Автоматическая пунктуация\n"
        "• 🌍 Поддержка русского и английского\n"
        "• 🧠 Умные контекстные исправления\n\n"
        "📊 Статистика: /stats\n"
        "⚙️ Настройки: /settings\n"
        "🌍 Язык: /language"
    )
    
    await update.message.reply_text(
        help_text,
        reply_markup=config.MAIN_MENU
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats"""
    user = update.effective_user
    stats = db.get_user_stats(user.id)
    
    if stats and stats[0] > 0:
        total_requests, total_size, total_duration = stats
        total_size_mb = total_size / (1024 * 1024) if total_size else 0
        total_minutes = total_duration / 60 if total_duration else 0
        
        stats_text = (
            f"📊 Ваша статистика:\n\n"
            f"• Всего запросов: {total_requests}\n"
            f"• Общий объем аудио: {total_size_mb:.1f} МБ\n"
            f"• Общая длительность: {total_minutes:.1f} минут\n\n"
            f"Спасибо, что используете бота! 🎉"
        )
    else:
        stats_text = "📊 Вы еще не отправляли аудио для распознавания."
    
    await update.message.reply_text(
        stats_text,
        reply_markup=config.MAIN_MENU
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /settings"""
    settings_text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        "Доступные опции:\n"
        "• Автоматическое удаление временных файлов\n"
        "• Уведомления о новых функциях\n"
        "• Статистика использования\n"
        "• Выбор языка распознавания (/language)\n\n"
        "Больше настроек появится в ближайшем обновлении! 🚀"
    )
    
    await update.message.reply_text(
        settings_text,
        parse_mode='HTML',
        reply_markup=config.MAIN_MENU
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (кнопок)"""
    user = update.effective_user
    
    # Проверяем, находится ли пользователь в режиме админа
    if is_in_admin_mode(user.id):
        await handle_admin_message(update, context)
        return
        
    text = update.message.text
    
    if text == "🎤 Распознать голос":
        await update.message.reply_text(
            "Отправьте мне голосовое сообщение или аудиофайл для распознавания! 🎤",
            reply_markup=config.MAIN_MENU
        )
    elif text == "📊 Статистика":
        await stats_command(update, context)
    elif text == "❓ Помощь":
        await help_command(update, context)
    elif text == "⚙️ Настройки":
        await settings_command(update, context)
    elif text == "🌍 Язык":
        await language_command(update, context)
    elif text == "🇷🇺 Русский":
        user_languages[user.id] = 'ru'
        await update.message.reply_text(
            "✅ Язык изменен на русский\n"
            "Теперь бот будет лучше распознавать русскую речь!",
            reply_markup=config.MAIN_MENU
        )
    elif text == "🇺🇸 English":
        user_languages[user.id] = 'en'
        await update.message.reply_text(
            "✅ Language changed to English\n"
            "The bot will now better recognize English speech!",
            reply_markup=config.MAIN_MENU
        )
    elif text == "🔙 Назад":
        await update.message.reply_text(
            "🔙 Возврат в главное меню",
            reply_markup=config.MAIN_MENU
        )
    else:
        await update.message.reply_text(
            "Не понимаю эту команду. Используйте меню ниже:",
            reply_markup=config.MAIN_MENU
        )

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик аудиосообщений и аудиофайлов"""
    user = update.effective_user
    
    # Если пользователь в режиме админа - игнорируем аудио
    if is_in_admin_mode(user.id):
        await update.message.reply_text(
            "❌ В режиме администратора распознавание аудио недоступно.\n"
            "Нажмите '🔙 Назад' для возврата в обычный режим.",
            reply_markup=config.ADMIN_MENU
        )
        return

    # ПРОВЕРКА: есть ли распознаватель
    if not recognizer:
        error_msg = "Распознаватель Vosk не инициализирован"
        log_error("Vosk not initialized", error_msg, update)
        await update.message.reply_text(
            "❌ Бот временно не работает.\n"
            "🛠️ Ведутся технические работы.\n"
            "⏳ Попробуйте позже."
        )
        return

    # ПРОВЕРКА: доступность модели Vosk
    available_languages = recognizer.get_available_languages()
    if not available_languages:
        error_msg = "Нет доступных моделей Vosk"
        log_error("No Vosk models available", error_msg, update)
        await update.message.reply_text(
            "❌ Ошибка загрузки моделей распознавания.\n"
            "🛠️ Разработчик уже уведомлен."
        )
        return
    
    # Логируем использование памяти перед обработкой
    memory_before = get_memory_usage()
    logger.info(f"Память до обработки: {memory_before['rss_mb']:.1f} MB")
    
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    # Получаем информацию о файле
    if update.message.voice:
        audio_file = update.message.voice
        file_type = "голосовое сообщение"
    elif update.message.audio:
        audio_file = update.message.audio
        file_type = "аудиофайл"
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте голосовое сообщение или аудиофайл")
        return
    
    # Проверяем размер файла
    if audio_file.file_size > config.MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ Файл слишком большой! Максимальный размер: {config.MAX_FILE_SIZE // (1024*1024)} МБ"
        )
        return
    
    # Получаем выбранный язык пользователя
    user_language = get_user_language(user.id)
    
    # Отправляем сообщение о начале обработки
    processing_msg = await update.message.reply_text(
        f"⏳ Обрабатываю {file_type}...\n"
        f"📏 Размер: {audio_file.file_size // 1024} КБ\n"
        f"🌍 Язык: {user_language.upper()}\n"
        "Это займет некоторое время..."
    )
    
    temp_audio_path = None
    try:
        # Скачиваем и обрабатываем аудио
        telegram_file = await audio_file.get_file()
        temp_audio_path = await AudioProcessor.process_telegram_audio(telegram_file)
        
        if not temp_audio_path:
            await processing_msg.edit_text("❌ Ошибка при обработке аудио")
            return
        
        # Получаем длительность аудио
        duration = AudioProcessor.get_audio_duration(temp_audio_path)
        
        # Распознаем речь с учетом выбранного языка
        recognized_text = recognizer.recognize_audio(temp_audio_path, user_language)

        # УЛУЧШАЕМ ТЕКСТ!
        if recognized_text and "Ошибка" not in recognized_text and "Не удалось" not in recognized_text:
            try:
                # Получаем ключевые слова из предыдущих сообщений пользователя
                context_words = []  # пока пустой список
                
                # Улучшаем текст
                enhanced_text = text_enhancer.enhance_text(recognized_text, context_words)
                
                if enhanced_text and enhanced_text != recognized_text:
                    recognized_text = enhanced_text
                    logger.info("✅ Текст успешно улучшен!")
            except Exception as e:
                logger.error(f"Ошибка улучшения текста: {e}")
                # Продолжаем с оригинальным текстом

        # Сохраняем запрос в базу данных (ИСПРАВЛЕННАЯ СТРОКА)
        db.add_audio_request(user.id, audio_file.file_id, audio_file.file_size, duration, recognized_text)

        # Формируем ответ
        if recognized_text and "Ошибка" not in recognized_text and "Не удалось" not in recognized_text:
            response_text = (
                f"✅ Распознано успешно!\n"
                f"⏱️ Длительность: {duration:.1f} сек\n"
                f"📝 Текст:\n\n{recognized_text}"
            )
            
            # Разбиваем длинный текст на части (ограничение Telegram)
            if len(response_text) > 4000:
                parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                for part in parts:
                    await update.message.reply_text(part)
            else:
                await update.message.reply_text(response_text)
                
        else:
            await update.message.reply_text(
                "❌ Не удалось распознать речь. Возможно:\n"
                "• Слишком тихий звук\n"
                "• Фоновая музыка/шум\n"
                "• Неподдерживаемый язык\n"
                "• Слишком короткое сообщение\n\n"
                "Попробуйте записать в тихом месте с четкой дикцией!"
            )
            
    except Exception as e:
        error_msg = log_error("Audio processing error", e, update)
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке аудио.\n"
            "🛠️ Разработчик уже уведомлен.\n"
            "🔄 Попробуйте отправить аудио еще раз."
        )
        
    finally:
        # Удаляем временные файлы
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass
        
        # Логируем использование памяти после обработки
        memory_after = get_memory_usage()
        logger.info(f"Память после обработки: {memory_after['rss_mb']:.1f} MB")
        logger.info(f"Использовано памяти: {memory_after['rss_mb'] - memory_before['rss_mb']:.1f} MB")
        
        # Удаляем сообщение о обработке
        try:
            await processing_msg.delete()
        except:
            pass

        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        gc.collect()

def main():
    """Основная функция запуска бота"""
    try:
        logger.info("🚀 Запуск бота...")
        
        # Проверяем наличие необходимых директорий
        os.makedirs('temp', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        # Создаем приложение
        application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("settings", settings_command))
        application.add_handler(CommandHandler("language", language_command))
        application.add_handler(CommandHandler("admin", admin_command))
        
        # Обработчики сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
        
        # Обработчик ошибок
        application.add_error_handler(error_handler)
        
        logger.info("✅ Бот запущен и готов к работе!")
        logger.info(f"Доступные языки Vosk: {recognizer.get_available_languages() if recognizer else 'Нет'}")
        
        # Запускаем бота
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()