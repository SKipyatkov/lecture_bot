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
            
            # Таблица 1 (ЮЗ)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица (Запросы)
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

# Глобал БД
db = Database()