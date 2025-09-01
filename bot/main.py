import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Импортируем наши модули
from config import config
from database import db
from audio_processor import AudioProcessor
from vosk_recognizer import VoskRecognizer

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация распознавателя Vosk
try:
    recognizer = VoskRecognizer(config.VOSK_MODEL_PATH)
    logger.info("✅ Модель Vosk успешно загружена!")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации Vosk: {e}")
    recognizer = None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = (
        "🎤 Привет! Я бот для преобразования голосовых сообщений в текст.\n\n"
        "📝 Просто отправь мне голосовое сообщение или аудиофайл, "
        "и я преобразую его в текст с помощью локальной нейросети!\n\n"
        "⚡ Работаю полностью оффлайн и бесплатно!\n"
        "🇷🇺 Поддерживаю русский язык\n\n"
        "📎 Максимальный размер файла: 20 МБ"
    )
    
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "❓ Как пользоваться ботом:\n\n"
        "1. 🎤 Отправь голосовое сообщение\n"
        "2. 📎 Или отправь аудиофайл (MP3, OGG, WAV)\n"
        "3. ⏳ Подожди 10-60 секунд\n"
        "4. 📝 Получи распознанный текст!\n\n"
        "⚠️ Ограничения:\n"
        "• Максимальный размер: 20 МБ\n"
        "• Лучше всего работаю с четкой речью\n"
        "• Поддерживаю только русский язык\n\n"
        "📊 Статистика: /stats"
    )
    
    await update.message.reply_text(help_text)

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
    
    await update.message.reply_text(stats_text)

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик аудиосообщений и аудиофайлов"""
    if not recognizer:
        await update.message.reply_text("❌ Ошибка: распознаватель не инициализирован")
        return
    
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
    
    # Отправляем сообщение о начале обработки
    processing_msg = await update.message.reply_text(
        f"⏳ Обрабатываю {file_type}...\n"
        f"📏 Размер: {audio_file.file_size // 1024} КБ\n"
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
        
        # Распознаем речь
        recognized_text = recognizer.recognize_audio(temp_audio_path)
        
        # Сохраняем в базу данных
        db.add_audio_request(user.id, audio_file.file_id, audio_file.file_size, duration, recognized_text)
        
        # Отправляем результат
        if recognized_text and "Ошибка" not in recognized_text and "Не удалось" not in recognized_text:
            if len(recognized_text) > 4000:
                chunks = [recognized_text[i:i+4000] for i in range(0, len(recognized_text), 4000)]
                for i, chunk in enumerate(chunks, 1):
                    await update.message.reply_text(f"📝 Часть {i}/{len(chunks)}:\n\n{chunk}")
            else:
                await processing_msg.edit_text(f"📝 Распознанный текст:\n\n{recognized_text}")
        else:
            await processing_msg.edit_text("❌ Не удалось распознать речь")
            
    except Exception as e:
        logger.error(f"Ошибка обработки аудио: {e}")
        try:
            await processing_msg.edit_text("❌ Произошла ошибка при обработке")
        except:
            await update.message.reply_text("❌ Произошла ошибка при обработке")
        
    finally:
        # Очищаем временные файлы
        if temp_audio_path:
            AudioProcessor.cleanup_temp_file(temp_audio_path)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке сообщения: {context.error}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text("❌ Произошла ошибка. Попробуйте еще раз.")
        except:
            pass

def main():
    """Основная функция запуска бота"""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("Токен бота не найден! Проверьте файл .env")
        return
    
    if not recognizer:
        logger.error("Не удалось инициализировать распознаватель Vosk")
        return
    
    print("🚀 Запуск бота...")
    print(f"📊 Модель Vosk: {config.VOSK_MODEL_PATH}")
    
    try:
        # Создаем приложение
        application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
        
        # Обработчик ошибок
        application.add_error_handler(error_handler)
        
        # Запускаем бота
        print("✅ Бот запущен! Ожидаем сообщения...")
        print("🛑 Для остановки нажмите Ctrl+C")
        
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    # Для Windows
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    main()