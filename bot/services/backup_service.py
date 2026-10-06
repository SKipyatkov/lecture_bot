import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

import psycopg

from core.database import DEFAULT_DSN, Database
from core.paths import BACKUP_DIR

logger = logging.getLogger(__name__)


class BackupService:
    """Периодически пишет SQL-дамп таблиц PostgreSQL."""

    def __init__(self, backup_dir: str = "backups", retention_days: int = 7, dsn: str | None = None):
        self.backup_dir = backup_dir
        self.dsn = dsn or os.getenv("DATABASE_URL", DEFAULT_DSN)
        self.retention_days = retention_days
        self.is_running = False
        self.thread = None
        os.makedirs(backup_dir, exist_ok=True)

    def create_backup(self) -> Optional[str]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = os.path.join(self.backup_dir, f"backup_{timestamp}.sql")
        database = Database(self.dsn)
        if not database.connect(attempts=1):
            return None
        try:
            sql = database.dump_inserts()
        except psycopg.Error as error:
            logger.error("Ошибка создания дампа PostgreSQL: %s", error)
            return None
        finally:
            database.close()
        with open(dump_path, "w", encoding="utf-8") as dump_file:
            dump_file.write(sql)
        self._clean_old_backups()
        logger.info("Дамп PostgreSQL записан: %s", dump_path)
        return dump_path

    def _clean_old_backups(self):
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for filename in os.listdir(self.backup_dir):
            if not (filename.startswith("backup_") and filename.endswith(".sql")):
                continue
            path = os.path.join(self.backup_dir, filename)
            if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                os.remove(path)
                logger.info("Удалён старый дамп: %s", filename)

    def start_auto_backup(self, interval_hours: int = 24):
        if self.is_running:
            return
        self.is_running = True

        def backup_loop():
            while self.is_running:
                try:
                    self.create_backup()
                    for _ in range(interval_hours * 60):
                        if not self.is_running:
                            break
                        time.sleep(60)
                except Exception as error:
                    logger.error("Ошибка автоматического дампа: %s", error)
                    time.sleep(300)

        self.thread = threading.Thread(target=backup_loop, daemon=True)
        self.thread.start()
        logger.info("Автоматический дамп PostgreSQL запущен, интервал %s ч", interval_hours)

    def stop_auto_backup(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Автоматический дамп PostgreSQL остановлен")


backup_service = BackupService(backup_dir=str(BACKUP_DIR))
