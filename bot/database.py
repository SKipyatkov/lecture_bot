
import sqlite3
import os

class Database:
    def __init__(self, db_name='bot_database.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        """Создает соединение с базой данных"""
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        """Инициализирует базу данных и создает таблицы"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица для админов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    logout_time TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name):
        """Добавляет пользователя в базу данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            conn.commit()
    
    def add_audio_request(self, user_id, file_id, file_size, duration, recognized_text):
        """Добавляет запрос на распознавание в базу данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audio_requests (user_id, file_id, file_size, duration, recognized_text)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, file_id, file_size, duration, recognized_text))
            conn.commit()
    
    def get_user_stats(self, user_id):
        """Возвращает статистику пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as total_requests, 
                       SUM(file_size) as total_size,
                       SUM(duration) as total_duration
                FROM audio_requests 
                WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            return result if result else (0, 0, 0)
    
    def get_global_stats(self):
        """Возвращает глобальную статистику по всем пользователям"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(*) as total_requests,
                    SUM(file_size) as total_size,
                    SUM(duration) as total_duration
                FROM audio_requests
            ''')
            result = cursor.fetchone()
            return result if result else (0, 0, 0, 0)
    
    # Функции для админа
    def get_all_users(self):
        """Возвращает список всех пользователей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT users.user_id, users.username, users.first_name, users.last_name, 
                       COUNT(audio_requests.id) as request_count,
                       MAX(audio_requests.created_at) as last_activity
                FROM users 
                LEFT JOIN audio_requests ON users.user_id = audio_requests.user_id
                GROUP BY users.user_id
                ORDER BY last_activity DESC
            ''')
            return cursor.fetchall()
    
    def add_admin_session(self, user_id):
        """Добавляет запись о входе администратора"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admin_sessions (user_id) VALUES (?)
            ''', (user_id,))
            conn.commit()
    
    def end_admin_session(self, user_id):
        """Завершает сессию администратора"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admin_sessions 
                SET logout_time = CURRENT_TIMESTAMP 
                WHERE user_id = ? AND logout_time IS NULL
            ''', (user_id,))
            conn.commit()

# Глобальная база данных
db = Database()
