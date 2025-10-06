import os
import logging
import asyncio
import traceback
import psutil
import gc
import torch
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Импортируем наши модули
from core.config import config
from core.database import db
from core.processing_queue import processing_queue
from core.cache_manager import cache_manager
from processors.audio_processor import AudioProcessor
from processors.vosk_recognizer import VoskRecognizer
from processors.text_enhancer import text_enhancer
from processors.plugin_system import plugin_system
from services.voice_synthesizer import voice_synthesizer
from services.backup_service import backup_service
from services.ab_testing import ab_testing
from utils.system_check import system_checker

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

# Проверка прав администратора
def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    if config.ADMIN_USER_ID == 0:
        return False
    return user_id == config.ADMIN_USER_ID or admin_sessions.get(user_id, False)

# Проверка режима администратора
def is_in_admin_mode(user_id):
    """Проверяет, находится ли пользователь в режиме администратора"""
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

# Запуск сервисов
async def start_services():
    """Запускает все фоновые сервисы"""
    try:
        # Запуск очереди обработки
        await processing_queue.start()
        logger.info("✅ Очередь обработки запущена")
        
        # Запуск автоматического резервного копирования
        if config.BACKUP_ENABLED:
            backup_service.start_auto_backup(config.BACKUP_INTERVAL_HOURS)
            logger.info("✅ Сервис бэкапов запущен")
        
        # Очистка старого кэша
        deleted_count = cache_manager.clear_old_cache()
        if deleted_count > 0:
            logger.info(f"✅ Очищено устаревших кэш-файлов: {deleted_count}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска сервисов: {e}")

# Проверка системы
def check_system_requirements():
    """Проверяет системные требования"""
    logger.info("🔍 Проверка системных требований...")
    
    deps_status = system_checker.check_dependencies()
    system_info = system_checker.get_system_info()
    disk_space = system_checker.check_disk_space()
    
    logger.info(f"💻 Система: {system_info['system']} {system_info['release']}")
    logger.info(f"🐍 Python: {system_info['python_version']}")
    
    if disk_space and 'free_gb' in disk_space:
        logger.info(f"💾 Свободно места: {disk_space['free_gb']} GB ({disk_space['free_percent']}%)")
    
    # Проверяем обязательные зависимости
    missing_required = []
    for dep_name, status in deps_status.items():
        if status['required'] and not status['available']:
            missing_required.append(dep_name)
    
    if missing_required:
        logger.warning("⚠️  Отсутствуют обязательные зависимости:")
        for dep in missing_required:
            logger.warning(f"   - {dep}")
    else:
        logger.info("✅ Все обязательные зависимости доступны")
    
    return len(missing_required) == 0

# КОМАНДЫ БОТА
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
        "📎 Максимальный размер файла: 20 МБ\n"
        "🎥 Также поддерживаю видеофайлы и кружочки!"
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
        "3. 🎥 Или отправь видеофайл (MP4)\n"
        "4. ⭕ Или отправь кружочек (video note)\n"
        "5. ⏳ Подожди 10-60 секунд\n"
        "6. 📝 Получи улучшенный текст с пунктуацией!\n\n"
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

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды для смены языка"""
    user = update.effective_user
    
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

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin"""
    user = update.effective_user
    
    if user.id != config.ADMIN_USER_ID and config.ADMIN_USER_ID != 0:
        await update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
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
    
    admin_sessions[user.id] = True
    db.add_admin_session(user.id)
    
    await update.message.reply_text(
        "👑 Добро пожаловать в панель администратора!",
        reply_markup=config.ADMIN_MENU
    )

async def batch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды для пакетной обработки"""
    help_text = (
        "🗃️ *Пакетная обработка файлов*\n\n"
        "Отправьте несколько аудио/видео файлов в одном сообщении "
        "или ZIP-архив с файлами.\n\n"
        "Бот обработает все файлы и пришлет ZIP-архив с результатами.\n\n"
        "📎 *Поддерживаемые форматы:*\n"
        "• Аудио: MP3, WAV, OGG, M4A\n"
        "• Видео: MP4, AVI, MOV\n"
        "• Архивы: ZIP\n\n"
        "⏱️ *Обработка:* Параллельная, до 10 файлов одновременно\n"
        "💾 *Максимальный размер:* 50 МБ на архив"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=config.MAIN_MENU
    )

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды для озвучивания текста"""
    if not context.args:
        await update.message.reply_text(
            "🔊 *Озвучивание текста*\n\n"
            "Использование: `/voice ваш текст для озвучивания`\n\n"
            "Пример: `/voice Привет, это тестовое сообщение`\n\n"
            "⚠️ *Ограничения:*\n"
            "• До 500 символов\n"
            "• Только русский и английский\n"
            "• MP3 формат на выходе",
            parse_mode='Markdown'
        )
        return
    
    text = ' '.join(context.args)
    
    if len(text) > 500:
        await update.message.reply_text("❌ Текст слишком длинный (максимум 500 символов)")
        return
    
    processing_msg = await update.message.reply_text("🔊 Озвучиваю текст...")
    
    try:
        user_group = ab_testing.assign_group(update.effective_user.id, "voice_synthesis_method")
        audio_path = voice_synthesizer.text_to_speech(text)
        
        if audio_path:
            await update.message.reply_voice(
                voice=open(audio_path, 'rb'),
                caption=f"📝 Озвученный текст: {text[:100]}..."
            )
            
            ab_testing.track_result(
                "voice_synthesis_method",
                update.effective_user.id,
                user_group,
                success=True,
                metrics={'text_length': len(text), 'audio_size': os.path.getsize(audio_path)}
            )
            
            os.unlink(audio_path)
        else:
            await update.message.reply_text("❌ Не удалось озвучить текст")
            
            ab_testing.track_result(
                "voice_synthesis_method", 
                update.effective_user.id,
                user_group,
                success=False
            )
    
    except Exception as e:
        log_error("Voice synthesis error", e, update)
        await update.message.reply_text("❌ Ошибка при озвучивании текста")
    
    finally:
        try:
            await processing_msg.delete()
        except:
            pass

# ОБРАБОТЧИКИ МЕДИАФАЙЛОВ
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик видеофайлов"""
    await process_media(update, context, "video")

async def handle_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кружочков (video notes)"""
    await process_media(update, context, "video_note")

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type):
    """Общая функция обработки медиафайлов"""
    user = update.effective_user
    
    if is_in_admin_mode(user.id):
        await update.message.reply_text(
            "❌ В режиме администратора распознавание медиа недоступно.",
            reply_markup=config.ADMIN_MENU
        )
        return

    if not recognizer:
        await update.message.reply_text("❌ Бот временно не работает.")
        return

    if media_type == "video":
        media_file = update.message.video
        file_type = "видеофайл"
    elif media_type == "video_note":
        media_file = update.message.video_note
        file_type = "кружочек"
    else:
        return

    if media_file.file_size > config.MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ Файл слишком большой! Максимальный размер: {config.MAX_FILE_SIZE // (1024*1024)} МБ"
        )
        return

    if media_type == "video" and media_file.duration > config.MAX_VIDEO_DURATION:
        await update.message.reply_text(
            f"❌ Видео слишком длинное! Максимальная длительность: {config.MAX_VIDEO_DURATION // 60} минут"
        )
        return

    user_language = get_user_language(user.id)

    processing_msg = await update.message.reply_text(
        f"⏳ Обрабатываю {file_type}...\n"
        f"📏 Размер: {media_file.file_size // 1024} КБ\n"
        f"⏱️ Длительность: {media_file.duration} сек\n"
        f"🌍 Язык: {user_language.upper()}\n"
        "Извлекаю аудио и распознаю речь..."
    )

    temp_audio_path = None
    try:
        telegram_file = await media_file.get_file()
        
        if media_type == "video":
            temp_audio_path = await AudioProcessor.process_telegram_video(telegram_file)
        elif media_type == "video_note":
            temp_audio_path = await AudioProcessor.process_telegram_video_note(telegram_file)

        if not temp_audio_path:
            await processing_msg.edit_text("❌ Ошибка при обработке медиафайла")
            return

        recognized_text = recognizer.recognize_audio(temp_audio_path, user_language)

        if recognized_text and "Ошибка" not in recognized_text:
            try:
                enhanced_text = text_enhancer.enhance_text(recognized_text, [])
                if enhanced_text:
                    recognized_text = enhanced_text
            except Exception as e:
                logger.error(f"Ошибка улучшения текста: {e}")

        db.add_audio_request(user.id, media_file.file_id, media_file.file_size, media_file.duration, recognized_text)

        if recognized_text and "Ошибка" not in recognized_text:
            response_text = (
                f"✅ Распознано из {file_type}!\n"
                f"⏱️ Длительность: {media_file.duration} сек\n"
                f"📝 Текст:\n\n{recognized_text}"
            )
            
            if len(response_text) > 4000:
                parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                for part in parts:
                    await update.message.reply_text(part)
            else:
                await update.message.reply_text(response_text)
        else:
            await update.message.reply_text("❌ Не удалось распознать речь из видео.")

    except Exception as e:
        error_msg = log_error(f"{media_type} processing error", e, update)
        await update.message.reply_text("❌ Произошла ошибка при обработке.")

    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except:
                pass
        
        try:
            await processing_msg.delete()
        except:
            pass

        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        gc.collect()

# ОБРАБОТЧИК АДМИН-МЕНЮ
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
        
        queue_stats = processing_queue.get_queue_stats()
        cache_stats = cache_manager.get_cache_stats()
        avg_rating, total_ratings = db.get_average_rating()
        
        stats_text = (
            f"📊 *Глобальная статистика:*\n\n"
            f"• 👥 Пользователей: {total_users}\n"
            f"• 📨 Запросов: {total_requests}\n"
            f"• 💾 Объем данных: {total_size / (1024*1024):.1f} МБ\n"
            f"• ⏱️ Длительность: {total_duration / 60:.1f} мин\n"
            f"• ⭐ Рейтинг: {avg_rating:.1f}/5 ({total_ratings} оценок)\n\n"
            f"*Система:*\n"
            f"• 🎯 Активных задач: {queue_stats['active_tasks']}\n"
            f"• 💰 Файлов в кэше: {cache_stats['total_files']}\n"
        )
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    elif text == "👥 Пользователи":
        users = db.get_all_users()
        if not users:
            await update.message.reply_text("📝 Пользователей пока нет.")
            return
        
        users_text = "👥 *Список пользователей:*\n\n"
        for i, user in enumerate(users[:10], 1):
            user_id, username, first_name, last_name, requests, last_active = user
            users_text += f"{i}. {first_name} {last_name} (@{username})\n"
            users_text += f"   ID: {user_id}, Запросов: {requests}\n"
            users_text += f"   Активность: {last_active}\n\n"
        
        if len(users) > 10:
            users_text += f"... и еще {len(users) - 10} пользователей"
        
        await update.message.reply_text(users_text, parse_mode='Markdown')
        
    elif text == "📋 Логи":
        try:
            log_file = f'bot_log_{datetime.now().strftime("%Y%m%d")}.log'
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = f.read()[-4000:]
                await update.message.reply_text(f"📋 *Последние логи:*\n\n```\n{logs}\n```", parse_mode='Markdown')
            else:
                await update.message.reply_text("📋 Файл логов не найден.")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка чтения логов: {e}")
            
    elif text == "💾 Создать бэкап":
        await update.message.reply_text("💾 Создаю резервную копию...")
        try:
            backup_path = backup_service.create_backup()
            if backup_path:
                await update.message.reply_document(
                    document=open(backup_path, 'rb'),
                    filename=os.path.basename(backup_path),
                    caption="✅ Резервная копия создана успешно!"
                )
            else:
                await update.message.reply_text("❌ Ошибка создания бэкапа")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            
    elif text == "🔄 Перезагрузка":
        await update.message.reply_text("🔄 Перезагрузка сервисов...")
        try:
            await start_services()
            await update.message.reply_text("✅ Сервисы перезапущены!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка перезагрузки: {e}")
            
    elif text == "⏹️ Остановка":
        await update.message.reply_text("⏹️ Остановка бота...")
        
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

# ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (кнопок)"""
    user = update.effective_user
    
    if is_in_admin_mode(user.id):
        await handle_admin_message(update, context)
        return
        
    text = update.message.text
    
    if text == "🎤 Распознать голос":
        await update.message.reply_text(
            "Отправьте мне голосовое сообщение, аудиофайл, видео или кружочек для распознавания! 🎤",
            reply_markup=config.MAIN_MENU
        )
    elif text == "🗃️ Пакетная обработка":
        await batch_command(update, context)
    elif text == "🔊 Озвучить текст":
        await voice_command(update, context)
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

# ОБРАБОТЧИК АУДИО
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик аудиосообщений и аудиофайлов"""
    user = update.effective_user
    
    if is_in_admin_mode(user.id):
        await update.message.reply_text(
            "❌ В режиме администратора распознавание аудио недоступно.\n"
            "Нажмите '🔙 Назад' для возврата в обычный режим.",
            reply_markup=config.ADMIN_MENU
        )
        return

    if not recognizer:
        error_msg = "Распознаватель Vosk не инициализирован"
        log_error("Vosk not initialized", error_msg, update)
        await update.message.reply_text("❌ Бот временно не работает.")
        return

    if update.message.voice:
        audio_file = update.message.voice
        file_type = "голосовое сообщение"
    elif update.message.audio:
        audio_file = update.message.audio
        file_type = "аудиофайл"
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте голосовое сообщение или аудиофайл")
        return
    
    if audio_file.file_size > config.MAX_FILE_SIZE:
        await update.message.reply_text(f"❌ Файл слишком большой! Максимальный размер: {config.MAX_FILE_SIZE // (1024*1024)} МБ")
        return
    
    user_language = get_user_language(user.id)
    enhancement_group = ab_testing.assign_group(user.id, "text_enhancement_method")
    
    processing_msg = await update.message.reply_text(
        f"⏳ Обрабатываю {file_type}...\n"
        f"📏 Размер: {audio_file.file_size // 1024} КБ\n"
        f"🌍 Язык: {user_language.upper()}\n"
        "Это займет некоторое время..."
    )
    
    temp_audio_path = None
    request_id = None
    
    try:
        telegram_file = await audio_file.get_file()
        temp_audio_path = await AudioProcessor.process_telegram_audio(telegram_file)
        
        if not temp_audio_path:
            await processing_msg.edit_text("❌ Ошибка при обработке аудио")
            return
        
        cached_result = None
        if config.CACHE_ENABLED:
            cached_result = cache_manager.get(temp_audio_path, user_language)
        
        if cached_result:
            recognized_text = cached_result
            logger.info("✅ Использован кэшированный результат")
        else:
            task_id = f"{user.id}_{datetime.now().timestamp()}"
            recognized_text = await processing_queue.add_task(
                task_id, 
                recognizer.recognize_audio, 
                temp_audio_path, 
                user_language
            )
            
            if config.CACHE_ENABLED and recognized_text and "Ошибка" not in recognized_text:
                cache_manager.set(temp_audio_path, user_language, recognized_text)
        
        duration = AudioProcessor.get_audio_duration(temp_audio_path)
        
        final_text = recognized_text
        if recognized_text and "Ошибка" not in recognized_text and "Не удалось" not in recognized_text:
            try:
                if enhancement_group == "enhancer_v1":
                    final_text = text_enhancer.enhance_text(recognized_text, [])
                elif enhancement_group == "enhancer_v2":
                    plugin_result = plugin_system.process_text(recognized_text)
                    final_text = plugin_result['text']
                else:
                    final_text = recognized_text
                
                logger.info(f"✅ Текст улучшен методом: {enhancement_group}")
            except Exception as e:
                logger.error(f"Ошибка улучшения текста: {e}")
                final_text = recognized_text
        
        request_id = db.add_audio_request(user.id, audio_file.file_id, audio_file.file_size, duration, final_text)
        
        if final_text and "Ошибка" not in final_text and "Не удалось" not in final_text:
            response_text = (
                f"✅ Распознано успешно!\n"
                f"⏱️ Длительность: {duration:.1f} сек\n"
                f"🧪 Метод: {enhancement_group}\n"
                f"📝 Текст:\n\n{final_text}"
            )
            
            feedback_keyboard = {
                "inline_keyboard": [[
                    {"text": "👍 Хорошо", "callback_data": f"feedback_{request_id}_5"},
                    {"text": "👎 Плохо", "callback_data": f"feedback_{request_id}_1"}
                ]]
            }
            
            if len(response_text) > 4000:
                parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:
                        await update.message.reply_text(part, reply_markup=feedback_keyboard)
                    else:
                        await update.message.reply_text(part)
            else:
                await update.message.reply_text(response_text, reply_markup=feedback_keyboard)
            
            ab_testing.track_result(
                "text_enhancement_method",
                user.id,
                enhancement_group,
                success=True,
                metrics={
                    'original_length': len(recognized_text),
                    'enhanced_length': len(final_text),
                    'duration': duration
                }
            )
            
        else:
            error_response = "❌ Не удалось распознать речь. Попробуйте записать в более тихом месте."
            await update.message.reply_text(error_response)
            
            ab_testing.track_result(
                "text_enhancement_method",
                user.id,
                enhancement_group,
                success=False
            )
    
    except Exception as e:
        error_msg = log_error("Audio processing error", e, update)
        await update.message.reply_text("❌ Произошла ошибка при обработке аудио.")
        
        ab_testing.track_result(
            "text_enhancement_method",
            user.id,
            enhancement_group,
            success=False
        )
    
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except Exception as e:
                logger.error(f"Ошибка удаления временного файла: {e}")
        
        try:
            await processing_msg.delete()
        except:
            pass
        
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        gc.collect()

# ОБРАБОТЧИК ОБРАТНОЙ СВЯЗИ
async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик обратной связи"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith('feedback_'):
        parts = data.split('_')
        if len(parts) == 3:
            request_id = parts[1]
            rating = int(parts[2])
            
            db.add_feedback(request_id, rating)
            
            if rating >= 4:
                await query.edit_message_text(
                    query.message.text + "\n\n✅ Спасибо за вашу оценку!"
                )
            else:
                await query.edit_message_text(
                    query.message.text + "\n\n😔 Сожалеем, что результат вас не устроил. Мы работаем над улучшением качества!"
                )

# ФУНКЦИЯ ЗАПУСКА БОТА
def main():
    """Основная функция запуска бота"""
    try:
        if not check_system_requirements():
            logger.warning("⚠️  Запуск с отсутствующими зависимостями может привести к ошибкам")
        
        logger.info("🚀 Запуск бота...")
        
        db.init_db()
        logger.info("✅ База данных инициализирована")
        
        # Создаем новый event loop для главного потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Запускаем сервисы в event loop
        loop.run_until_complete(start_services())
        
        application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("settings", settings_command))
        application.add_handler(CommandHandler("language", language_command))
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CommandHandler("batch", batch_command))
        application.add_handler(CommandHandler("voice", voice_command))
        
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
        application.add_handler(MessageHandler(filters.VIDEO, handle_video))
        application.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(CallbackQueryHandler(handle_feedback, pattern="^feedback_"))
        
        application.add_error_handler(error_handler)
        
        logger.info("🤖 Бот запускается...")
        
        # Запускаем бота в event loop
        loop.run_until_complete(application.run_polling())
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске: {e}")
        raise

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")