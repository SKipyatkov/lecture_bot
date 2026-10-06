import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg

logger = logging.getLogger(__name__)

DEFAULT_DSN = "postgresql://lecture:lecture@localhost:5433/lecture_bot"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
STATEMENT_TIMEOUT = "5s"


def _sql_statements(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return "'" + value.isoformat() + "'"
    return "'" + str(value).replace("'", "''") + "'"


class Database:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.getenv("DATABASE_URL", DEFAULT_DSN)
        self.connection: Optional[psycopg.Connection] = None

    def connect(self, attempts: int = 10) -> bool:
        self.close()
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                self.connection = psycopg.connect(
                    self.dsn,
                    connect_timeout=5,
                    options=f"-c statement_timeout={STATEMENT_TIMEOUT}",
                )
                logger.info("Подключение к PostgreSQL установлено")
                return True
            except psycopg.OperationalError as error:
                last_error = error
                logger.warning("PostgreSQL недоступен, попытка %s/%s", attempt, attempts)
                time.sleep(1)
        logger.error("Ошибка подключения к PostgreSQL: %s", last_error)
        return False

    def _ready(self) -> bool:
        if self.connection is not None and not self.connection.closed:
            return True
        self.connection = None
        return self.connect(attempts=2)

    def _with_connection(self, operation, default):
        """Выполняет запрос. Если соединение оборвалось, открывает его ещё раз."""
        for attempt in (1, 2):
            if not self._ready():
                return default
            try:
                result = operation()
                if self.connection is not None and not self.connection.closed:
                    self.connection.commit()
                return result
            except (psycopg.OperationalError, psycopg.InterfaceError) as error:
                logger.warning("Соединение с PostgreSQL потеряно, попытка %s: %s", attempt, error)
                self.close()
            except psycopg.Error as error:
                logger.error("Ошибка запроса PostgreSQL: %s", error)
                if self.connection is not None and not self.connection.closed:
                    self.connection.rollback()
                return default
        return default

    def init_db(self) -> bool:
        return self.connect() and self.apply_migrations()

    def apply_migrations(self) -> bool:
        if not self.connection:
            logger.error("Нет соединения с базой данных")
            return False
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute("SELECT version FROM schema_migrations")
                applied = {row[0] for row in cursor.fetchall()}
                for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                    if path.name in applied:
                        continue
                    for statement in _sql_statements(path.read_text(encoding="utf-8")):
                        cursor.execute(statement)
                    cursor.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (path.name,),
                    )
                    logger.info("Применена миграция %s", path.name)
            self.connection.commit()
            return True
        except psycopg.Error as error:
            self.connection.rollback()
            logger.error("Ошибка миграции: %s", error)
            return False

    def add_user(self, telegram_id: int, username: Optional[str] = None,
                 first_name: Optional[str] = None, last_name: Optional[str] = None) -> Optional[int]:
        return self.add_or_update_user(telegram_id, username, first_name, last_name)

    def add_or_update_user(self, telegram_id: int, username: Optional[str] = None,
                           first_name: Optional[str] = None, last_name: Optional[str] = None,
                           language_code: str = "ru", is_premium: bool = False) -> Optional[int]:
        del language_code, is_premium

        def operation():
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM users WHERE telegram_id = %s",
                    (telegram_id,),
                )
                existing_user = cursor.fetchone()
                now = datetime.now()
                if existing_user:
                    cursor.execute(
                        """
                        UPDATE users
                        SET username = %s, first_name = %s, last_name = %s, last_active = %s
                        WHERE telegram_id = %s
                        """,
                        (username, first_name, last_name, now, telegram_id),
                    )
                    return existing_user[0]
                cursor.execute(
                    """
                    INSERT INTO users (telegram_id, username, first_name, last_name, last_active)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (telegram_id, username, first_name, last_name, now),
                )
                return cursor.fetchone()[0]

        return self._with_connection(operation, None)

    def _internal_user_id(self, telegram_id: int) -> Optional[int]:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
            row = cursor.fetchone()
        return row[0] if row else None

    def add_audio_request(self, user_id: int, file_id: str, file_size: Optional[int] = None,
                          duration: Optional[float] = None, recognized_text: Optional[str] = None) -> Optional[int]:
        """user_id — это telegram id."""

        def operation():
            internal_id = self._internal_user_id(user_id)
            if internal_id is None:
                logger.error("Пользователь %s не найден", user_id)
                return None
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO audio_requests (user_id, file_id, file_size, duration, recognized_text)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (internal_id, file_id, file_size, duration, recognized_text),
                )
                request_id = cursor.fetchone()[0]
                cursor.execute(
                    "UPDATE users SET last_active = %s WHERE telegram_id = %s",
                    (datetime.now(), user_id),
                )
                return request_id

        return self._with_connection(operation, None)

    def get_user_stats(self, user_id: int) -> Optional[tuple]:
        def operation():
            internal_id = self._internal_user_id(user_id)
            if internal_id is None:
                return (0, 0, 0)
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(file_size), 0), COALESCE(SUM(duration), 0)
                    FROM audio_requests
                    WHERE user_id = %s
                    """,
                    (internal_id,),
                )
                row = cursor.fetchone()
            return (row[0] or 0, row[1] or 0, row[2] or 0)

        return self._with_connection(operation, (0, 0, 0))

    def add_feedback(self, request_id: int, rating: int) -> bool:
        def operation():
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO feedback (request_id, rating) VALUES (%s, %s)",
                    (request_id, rating),
                )
            return True

        return self._with_connection(operation, False)

    def get_language(self, telegram_id: int) -> str:
        def operation():
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT language_code FROM users WHERE telegram_id = %s",
                    (telegram_id,),
                )
                row = cursor.fetchone()
            if row and row[0]:
                return row[0]
            return "ru"

        return self._with_connection(operation, "ru")

    def set_language(self, telegram_id: int, language: str) -> bool:
        def operation():
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET language_code = %s WHERE telegram_id = %s",
                    (language, telegram_id),
                )
                return cursor.rowcount > 0

        return self._with_connection(operation, False)

    def dump_inserts(self) -> str:
        """SQL-дамп данных для бэкапа. Схему создают миграции."""
        lines = []
        tables = ("users", "audio_requests", "feedback")
        with self.connection.cursor() as cursor:
            for table in tables:
                cursor.execute(f"SELECT * FROM {table} ORDER BY id")
                columns = [item.name for item in cursor.description]
                for row in cursor.fetchall():
                    values = ", ".join(_sql_literal(value) for value in row)
                    names = ", ".join(columns)
                    lines.append(f"INSERT INTO {table} ({names}) VALUES ({values});")
        for table in tables:
            lines.append(
                "SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                "COALESCE((SELECT MAX(id) FROM {table}), 1), "
                "(SELECT MAX(id) FROM {table}) IS NOT NULL);".format(table=table)
            )
        return "\n".join(lines) + ("\n" if lines else "")

    def close(self):
        connection = self.connection
        self.connection = None
        if connection is not None and not connection.closed:
            connection.close()


db = Database()
