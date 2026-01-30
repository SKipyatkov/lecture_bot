"""
core/database.py - полная исправленная версия
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "bot.db"):
        """
        Инициализация базы данных

        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = Path(db_path)
        self.connection: Optional[sqlite3.Connection] = None

    def connect(self) -> bool:
        """Установка соединения с базой данных"""
        try:
            # Создаем директорию для БД если нужно
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")

            logger.info(f"✅ Соединение с базой данных установлено: {self.db_path}")
            return True

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка подключения к базе данных: {e}")
            return False

    def init_db(self) -> bool:
        """Инициализация базы данных (для совместимости с main.py)"""
        return self.connect() and self.initialize_tables()

    def initialize_tables(self) -> bool:
        """Инициализация таблиц базы данных с миграциями"""
        if not self.connection:
            logger.error("❌ Нет соединения с базой данных")
            return False

        try:
            cursor = self.connection.cursor()

            # Таблица пользователей с ВСЕМИ необходимыми столбцами
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT DEFAULT 'ru',
                    is_premium BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settings TEXT DEFAULT '{}',
                    UNIQUE(telegram_id)
                )
            ''')

            # Таблица запросов аудио (из main.py используется add_audio_request)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audio_requests (
                                                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                              user_id INTEGER NOT NULL,
                                                              file_id TEXT NOT NULL,
                                                              file_size INTEGER,
                                                              duration REAL,
                                                              recognized_text TEXT,
                                                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                                              FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')

            # Таблица статистики
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    total_messages INTEGER DEFAULT 0,
                    voice_messages INTEGER DEFAULT 0,
                    total_users INTEGER DEFAULT 0,
                    new_users INTEGER DEFAULT 0
                )
            ''')

            # Таблица оценок (feedback)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (request_id) REFERENCES audio_requests (id) ON DELETE CASCADE
                )
            ''')

            # Таблица сессий администратора
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_sessions (
                                                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                              user_id INTEGER NOT NULL,
                                                              started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                                              ended_at TIMESTAMP,
                                                              FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')

            self.connection.commit()

            # Выполняем миграции для существующих таблиц
            self._migrate_database()

            logger.info("✅ Таблицы базы данных инициализированы")
            return True

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка инициализации таблиц: {e}")
            return False

    def _migrate_database(self):
        """Миграция базы данных - добавление отсутствующих столбцов"""
        try:
            cursor = self.connection.cursor()

            # Проверяем наличие столбцов в таблице users
            cursor.execute("PRAGMA table_info(users)")
            users_columns = {row[1] for row in cursor.fetchall()}

            # Добавляем отсутствующие столбцы
            missing_columns = []

            if 'last_active' not in users_columns:
                cursor.execute('''
                    ALTER TABLE users 
                    ADD COLUMN last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                               ''')
                missing_columns.append('last_active')

            if 'settings' not in users_columns:
                cursor.execute('''
                    ALTER TABLE users 
                    ADD COLUMN settings TEXT DEFAULT '{}'
                ''')
                missing_columns.append('settings')

            if 'is_premium' not in users_columns:
                cursor.execute('''
                    ALTER TABLE users 
                    ADD COLUMN is_premium BOOLEAN DEFAULT 0
                ''')
                missing_columns.append('is_premium')

            if missing_columns:
                logger.info(f"🔄 Добавлены столбцы: {', '.join(missing_columns)}")

            self.connection.commit()

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка миграции базы данных: {e}")

    def add_user(self, telegram_id: int, username: Optional[str] = None,
                first_name: Optional[str] = None, last_name: Optional[str] = None) -> Optional[int]:
        """Добавление пользователя (для совместимости с main.py)"""
        return self.add_or_update_user(telegram_id, username, first_name, last_name)

    def add_or_update_user(self, telegram_id: int, username: Optional[str] = None,
                          first_name: Optional[str] = None, last_name: Optional[str] = None,
                          language_code: str = 'ru', is_premium: bool = False) -> Optional[int]:
        """
        Добавление или обновление пользователя

        Returns:
            ID пользователя или None в случае ошибки
        """
        if not self.connection:
            logger.error("❌ Нет соединения с базой данных")
            return None

        try:
            cursor = self.connection.cursor()

            # Проверяем существование пользователя
            cursor.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            existing_user = cursor.fetchone()

            current_time = datetime.now().isoformat()

            if existing_user:
                # Обновляем существующего пользователя
                cursor.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?,
                        last_active = ?
                    WHERE telegram_id = ?
                ''', (username, first_name, last_name, current_time, telegram_id))
                user_id = existing_user['id']
                logger.debug(f"🔄 Пользователь обновлен: {telegram_id}")
            else:
                # Добавляем нового пользователя
                cursor.execute('''
                    INSERT INTO users 
                    (telegram_id, username, first_name, last_name, last_active)
                    VALUES (?, ?, ?, ?, ?)
                ''', (telegram_id, username, first_name, last_name, current_time))
                user_id = cursor.lastrowid
                logger.info(f"👤 Новый пользователь добавлен: {telegram_id}")

            self.connection.commit()
            return user_id

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка добавления/обновления пользователя: {e}")
            return None

    def add_audio_request(self, user_id: int, file_id: str, file_size: Optional[int] = None,
                         duration: Optional[float] = None, recognized_text: Optional[str] = None) -> Optional[int]:
        """Добавление запроса аудио (для совместимости с main.py)"""
        if not self.connection:
            return None

        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO audio_requests 
                (user_id, file_id, file_size, duration, recognized_text)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, file_id, file_size, duration, recognized_text))

            request_id = cursor.lastrowid
            self.connection.commit()

            # Обновляем last_active у пользователя
            cursor.execute(
                "UPDATE users SET last_active = ? WHERE id = ?",
                (datetime.now().isoformat(), user_id)
            )
            self.connection.commit()

            logger.debug(f"💾 Запрос аудио сохранен: ID={request_id}")
            return request_id

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка сохранения запроса аудио: {e}")
            return None

    def get_user_stats(self, user_id: int) -> Optional[tuple]:
        """Получение статистики пользователя (для совместимости с main.py)"""
        if not self.connection:
            return None

        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(file_size) as total_size,
                    SUM(duration) as total_duration
                FROM audio_requests 
                WHERE user_id = ?
            ''', (user_id,))

            result = cursor.fetchone()
            if result:
                return (result[0] or 0, result[1] or 0, result[2] or 0)
            return (0, 0, 0)

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return (0, 0, 0)

    def add_feedback(self, request_id: int, rating: int) -> bool:
        """Добавление оценки"""
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO feedback (request_id, rating)
                VALUES (?, ?)
            ''', (request_id, rating))

            self.connection.commit()
            logger.debug(f"⭐ Оценка добавлена: request_id={request_id}, rating={rating}")
            return True

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка добавления оценки: {e}")
            return False

    def add_admin_session(self, user_id: int) -> bool:
        """Добавление сессии администратора"""
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO admin_sessions (user_id)
                VALUES (?)
            ''', (user_id,))

            self.connection.commit()
            return True

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка добавления сессии админа: {e}")
            return False

    def end_admin_session(self, user_id: int) -> bool:
        """Завершение сессии администратора"""
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE admin_sessions 
                SET ended_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND ended_at IS NULL
            ''', (user_id,))

            self.connection.commit()
            return cursor.rowcount > 0

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка завершения сессии админа: {e}")
            return False

    def get_global_stats(self) -> tuple:
        """Получение глобальной статистики (для админ-панели)"""
        if not self.connection:
            return (0, 0, 0, 0)

        try:
            cursor = self.connection.cursor()

            # Общее количество пользователей
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0] or 0

            # Общее количество запросов
            cursor.execute("SELECT COUNT(*) FROM audio_requests")
            total_requests = cursor.fetchone()[0] or 0

            # Общий объем данных
            cursor.execute("SELECT SUM(file_size) FROM audio_requests")
            total_size = cursor.fetchone()[0] or 0

            # Общая длительность
            cursor.execute("SELECT SUM(duration) FROM audio_requests")
            total_duration = cursor.fetchone()[0] or 0

            return (total_users, total_requests, total_size, total_duration)

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка получения глобальной статистики: {e}")
            return (0, 0, 0, 0)

    def get_all_users(self) -> List[tuple]:
        """Получение списка всех пользователей"""
        if not self.connection:
            return []

        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT 
                    u.telegram_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    COUNT(ar.id) as request_count,
                    u.last_active
                FROM users u
                LEFT JOIN audio_requests ar ON u.id = ar.user_id
                GROUP BY u.id
                ORDER BY u.last_active DESC
            ''')

            return cursor.fetchall()

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка получения списка пользователей: {e}")
            return []

    def get_average_rating(self) -> tuple:
        """Получение средней оценки"""
        if not self.connection:
            return (0.0, 0)

        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT AVG(rating), COUNT(*) FROM feedback")
            result = cursor.fetchone()

            avg_rating = round(float(result[0] or 0), 1)
            total_ratings = result[1] or 0

            return (avg_rating, total_ratings)

        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка получения средней оценки: {e}")
            return (0.0, 0)

    def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("📴 Соединение с базой данных закрыто")
            except Exception as e:
                logger.error(f"❌ Ошибка при закрытии БД: {e}")
            finally:
                self.connection = None


# Глобальный экземпляр базы данных
db = Database()