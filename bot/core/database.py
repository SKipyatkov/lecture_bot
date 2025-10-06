import sqlite3
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_path='bot_database.db'):
        self.db_path = db_path
        self.connection = None
    
    def connect(self):
        """Устанавливает соединение с базой данных"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            logger.info("✅ Соединение с базой данных установлено")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к базе данных: {e}")
            raise
    
    def init_db(self):
        """Инициализирует базу данных и создает таблицы"""
        try:
            self.connect()
            
            cursor = self.connection.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_requests INTEGER DEFAULT 0,
                    total_size INTEGER DEFAULT 0,
                    total_duration INTEGER DEFAULT 0
                )
            ''')
            
            # Таблица запросов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audio_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    file_id TEXT,
                    file_size INTEGER,
                    duration INTEGER,
                    recognized_text TEXT,
                    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    language TEXT DEFAULT 'ru',
                    processing_time INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица обратной связи
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER,
                    rating INTEGER,
                    comment TEXT,
                    feedback_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES audio_requests (id)
                )
            ''')
            
            # Таблица сессий администратора
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица A/B тестирования
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ab_testing (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    test_name TEXT,
                    group_name TEXT,
                    success BOOLEAN,
                    metrics TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            self.connection.commit()
            logger.info("✅ Таблицы базы данных инициализированы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            raise
    
    def add_user(self, user_id, username, first_name, last_name):
        """Добавляет пользователя в базу данных"""
        try:
            cursor = self.connection.cursor()
            
            # Проверяем, существует ли пользователь
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                # Обновляем последнюю активность
                cursor.execute(
                    'UPDATE users SET last_active = ?, username = ?, first_name = ?, last_name = ? WHERE user_id = ?',
                    (datetime.now(), username, first_name, last_name, user_id)
                )
            else:
                # Добавляем нового пользователя
                cursor.execute(
                    'INSERT INTO users (user_id, username, first_name, last_name, last_active) VALUES (?, ?, ?, ?, ?)',
                    (user_id, username, first_name, last_name, datetime.now())
                )
            
            self.connection.commit()
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления пользователя: {e}")
    
    def add_audio_request(self, user_id, file_id, file_size, duration, recognized_text):
        """Добавляет запрос на распознавание аудио"""
        try:
            cursor = self.connection.cursor()
            
            # Добавляем запрос
            cursor.execute(
                '''INSERT INTO audio_requests 
                   (user_id, file_id, file_size, duration, recognized_text, request_date) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (user_id, file_id, file_size, duration, recognized_text, datetime.now())
            )
            
            request_id = cursor.lastrowid
            
            # Обновляем статистику пользователя
            cursor.execute(
                '''UPDATE users 
                   SET total_requests = total_requests + 1,
                       total_size = total_size + ?,
                       total_duration = total_duration + ?,
                       last_active = ?
                   WHERE user_id = ?''',
                (file_size, duration, datetime.now(), user_id)
            )
            
            self.connection.commit()
            return request_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления запроса: {e}")
            return None
    
    def get_user_stats(self, user_id):
        """Возвращает статистику пользователя"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                'SELECT total_requests, total_size, total_duration FROM users WHERE user_id = ?',
                (user_id,)
            )
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики пользователя: {e}")
            return None
    
    def get_global_stats(self):
        """Возвращает глобальную статистику"""
        try:
            cursor = self.connection.cursor()
            
            # Общее количество пользователей
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            # Общее количество запросов
            cursor.execute('SELECT COUNT(*) FROM audio_requests')
            total_requests = cursor.fetchone()[0]
            
            # Общий размер файлов
            cursor.execute('SELECT SUM(file_size) FROM audio_requests')
            total_size = cursor.fetchone()[0] or 0
            
            # Общая длительность
            cursor.execute('SELECT SUM(duration) FROM audio_requests')
            total_duration = cursor.fetchone()[0] or 0
            
            return total_users, total_requests, total_size, total_duration
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения глобальной статистики: {e}")
            return 0, 0, 0, 0
    
    def get_all_users(self):
        """Возвращает список всех пользователей"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                '''SELECT user_id, username, first_name, last_name, total_requests, last_active 
                   FROM users ORDER BY last_active DESC'''
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка пользователей: {e}")
            return []
    
    def add_feedback(self, request_id, rating, comment=None):
        """Добавляет обратную связь"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                'INSERT INTO feedback (request_id, rating, comment) VALUES (?, ?, ?)',
                (request_id, rating, comment)
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления обратной связи: {e}")
            return False
    
    def get_average_rating(self):
        """Возвращает средний рейтинг"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT AVG(rating), COUNT(*) FROM feedback')
            result = cursor.fetchone()
            return result[0] or 0, result[1] or 0
        except Exception as e:
            logger.error(f"❌ Ошибка получения среднего рейтинга: {e}")
            return 0, 0
    
    def add_admin_session(self, user_id):
        """Добавляет сессию администратора"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                'INSERT INTO admin_sessions (user_id) VALUES (?)',
                (user_id,)
            )
            self.connection.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"❌ Ошибка добавления сессии администратора: {e}")
            return None
    
    def end_admin_session(self, user_id):
        """Завершает сессию администратора"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                '''UPDATE admin_sessions 
                   SET end_time = ? 
                   WHERE user_id = ? AND end_time IS NULL''',
                (datetime.now(), user_id)
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка завершения сессии администратора: {e}")
            return False
    
    def add_ab_test_result(self, user_id, test_name, group_name, success, metrics=None):
        """Добавляет результат A/B тестирования"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                '''INSERT INTO ab_testing 
                   (user_id, test_name, group_name, success, metrics) 
                   VALUES (?, ?, ?, ?, ?)''',
                (user_id, test_name, group_name, success, str(metrics) if metrics else None)
            )
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления результата A/B тестирования: {e}")
            return False
    
    def close(self):
        """Закрывает соединение с базой данных"""
        if self.connection:
            self.connection.close()
            logger.info("✅ Соединение с базой данных закрыто")

# Создаем глобальный экземпляр базы данных
db = Database()