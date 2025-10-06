import os
import logging
import zipfile
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading
import time
import sqlite3

logger = logging.getLogger(__name__)

class BackupService:
    """Сервис для создания резервных копий данных бота"""
    
    def __init__(self, backup_dir: str = "backups", retention_days: int = 7):
        self.backup_dir = backup_dir
        self.retention_days = retention_days
        self.is_running = False
        self.thread = None
        
        os.makedirs(backup_dir, exist_ok=True)
        logger.info(f"✅ Сервис бэкапов инициализирован. Директория: {backup_dir}")
    
    def create_backup(self, comment: str = None) -> Optional[str]:
        """
        Создает резервную копию данных бота
        Возвращает путь к созданному backup-файлу
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"
            if comment:
                backup_name += f"_{comment.replace(' ', '_')}"
            backup_name += ".zip"
            
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # Создаем временную директорию для бэкапа
            temp_dir = os.path.join(self.backup_dir, f"temp_{timestamp}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Собираем файлы для бэкапа
            files_to_backup = self._collect_files_for_backup(temp_dir)
            
            # Создаем ZIP архив
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path, arcname in files_to_backup:
                    if os.path.exists(file_path):
                        zipf.write(file_path, arcname)
                        logger.debug(f"📦 Добавлен в бэкап: {file_path}")
            
            # Очищаем временную директорию
            shutil.rmtree(temp_dir)
            
            # Очищаем старые бэкапы
            self._clean_old_backups()
            
            # Записываем информацию о бэкапе
            backup_info = {
                'filename': backup_name,
                'path': backup_path,
                'size': os.path.getsize(backup_path),
                'created_at': datetime.now().isoformat(),
                'comment': comment,
                'file_count': len(files_to_backup)
            }
            
            self._save_backup_info(backup_info)
            
            size_mb = backup_info['size'] / (1024 * 1024)
            logger.info(f"✅ Бэкап создан: {backup_name} ({size_mb:.1f} МБ, {len(files_to_backup)} файлов)")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")
            # Очистка в случае ошибки
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return None
    
    def _collect_files_for_backup(self, temp_dir: str) -> List[tuple]:
        """Собирает файлы для резервного копирования"""
        files_to_backup = []
        
        # 1. База данных
        db_files = [
            'bot_database.db',
            'bot_database.db-shm',
            'bot_database.db-wal'
        ]
        
        for db_file in db_files:
            if os.path.exists(db_file):
                files_to_backup.append((db_file, f"database/{db_file}"))
        
        # 2. Файлы логов (только текущий день)
        log_files = [f for f in os.listdir('.') if f.startswith('bot_log_') and f.endswith('.log')]
        today_log = f"bot_log_{datetime.now().strftime('%Y%m%d')}.log"
        
        for log_file in log_files:
            if log_file == today_log:  # Бекапим только сегодняшний лог
                files_to_backup.append((log_file, f"logs/{log_file}"))
        
        # 3. Конфигурационные файлы
        config_files = ['.env', 'config.py', 'requirements.txt']
        
        for config_file in config_files:
            if os.path.exists(config_file):
                files_to_backup.append((config_file, f"config/{config_file}"))
        
        # 4. Создаем дамп базы данных в SQL
        db_dump_path = self._create_database_dump(temp_dir)
        if db_dump_path:
            files_to_backup.append((db_dump_path, "database/database_dump.sql"))
        
        # 5. Создаем файл с информацией о системе
        system_info_path = self._create_system_info(temp_dir)
        if system_info_path:
            files_to_backup.append((system_info_path, "system_info.txt"))
        
        return files_to_backup
    
    def _create_database_dump(self, temp_dir: str) -> Optional[str]:
        """Создает SQL дамп базы данных"""
        try:
            dump_path = os.path.join(temp_dir, "database_dump.sql")
            
            if not os.path.exists('bot_database.db'):
                return None
            
            conn = sqlite3.connect('bot_database.db')
            
            with open(dump_path, 'w', encoding='utf-8') as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
            
            conn.close()
            return dump_path
            
        except Exception as e:
            logger.error(f"Ошибка создания дампа БД: {e}")
            return None
    
    def _create_system_info(self, temp_dir: str) -> Optional[str]:
        """Создает файл с информацией о системе"""
        try:
            info_path = os.path.join(temp_dir, "system_info.txt")
            
            with open(info_path, 'w', encoding='utf-8') as f:
                f.write(f"Backup created: {datetime.now()}\n")
                f.write(f"Python version: {os.sys.version}\n")
                f.write(f"Platform: {os.sys.platform}\n")
                f.write(f"Working directory: {os.getcwd()}\n")
                f.write(f"User: {os.getenv('USER', 'Unknown')}\n")
                
                # Информация о файловой системе
                f.write("\n=== File System ===\n")
                for item in os.listdir('.'):
                    if os.path.isfile(item):
                        size = os.path.getsize(item)
                        f.write(f"{item}: {size} bytes\n")
            
            return info_path
            
        except Exception as e:
            logger.error(f"Ошибка создания системной информации: {e}")
            return None
    
    def _save_backup_info(self, backup_info: Dict):
        """Сохраняет информацию о бэкапе в отдельный файл"""
        try:
            info_file = os.path.join(self.backup_dir, "backups_info.json")
            
            import json
            backups = []
            
            if os.path.exists(info_file):
                with open(info_file, 'r', encoding='utf-8') as f:
                    backups = json.load(f)
            
            backups.append(backup_info)
            
            # Оставляем только последние 50 записей
            if len(backups) > 50:
                backups = backups[-50:]
            
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(backups, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Ошибка сохранения информации о бэкапе: {e}")
    
    def _clean_old_backups(self):
        """Удаляет устаревшие резервные копии"""
        try:
            cutoff_time = datetime.now() - timedelta(days=self.retention_days)
            deleted_count = 0
            
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('backup_') and filename.endswith('.zip'):
                    file_path = os.path.join(self.backup_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    
                    if file_time < cutoff_time:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"🗑️ Удален старый бэкап: {filename}")
            
            if deleted_count > 0:
                logger.info(f"🧹 Очищено устаревших бэкапов: {deleted_count}")
                
        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Восстанавливает данные из backup-файла
        """
        if not os.path.exists(backup_path):
            logger.error(f"Файл бэкапа не найден: {backup_path}")
            return False
        
        try:
            # Создаем временную директорию для восстановления
            temp_dir = os.path.join(self.backup_dir, f"restore_{datetime.now().strftime('%H%M%S')}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Распаковываем архив
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(temp_dir)
            
            # Восстанавливаем файлы
            self._restore_files_from_backup(temp_dir)
            
            # Очищаем временную директорию
            shutil.rmtree(temp_dir)
            
            logger.info(f"✅ Восстановление из бэкапа завершено: {os.path.basename(backup_path)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления из бэкапа: {e}")
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False
    
    def _restore_files_from_backup(self, temp_dir: str):
        """Восстанавливает файлы из распакованного бэкапа"""
        # Восстанавливаем базу данных
        db_source = os.path.join(temp_dir, "database", "bot_database.db")
        if os.path.exists(db_source):
            # Создаем бэкап текущей БД перед восстановлением
            current_db = 'bot_database.db'
            if os.path.exists(current_db):
                backup_name = f"pre_restore_{datetime.now().strftime('%H%M%S')}.db"
                shutil.copy2(current_db, backup_name)
                logger.info(f"💾 Создан бэкап текущей БД: {backup_name}")
            
            shutil.copy2(db_source, current_db)
            logger.info("✅ База данных восстановлена")
        
        # Восстанавливаем конфигурационные файлы
        config_dir = os.path.join(temp_dir, "config")
        if os.path.exists(config_dir):
            for config_file in os.listdir(config_dir):
                source = os.path.join(config_dir, config_file)
                if os.path.isfile(source):
                    shutil.copy2(source, ".")
                    logger.info(f"✅ Восстановлен конфиг: {config_file}")
    
    def start_auto_backup(self, interval_hours: int = 24):
        """Запускает автоматическое резервное копирование"""
        if self.is_running:
            logger.warning("Автоматическое резервное копирование уже запущено")
            return
        
        self.is_running = True
        
        def backup_loop():
            while self.is_running:
                try:
                    # Создаем бэкап
                    comment = f"auto_{datetime.now().strftime('%H%M')}"
                    self.create_backup(comment)
                    
                    # Ждем указанное количество часов
                    for _ in range(interval_hours * 60):
                        if not self.is_running:
                            break
                        time.sleep(60)  # Проверяем каждую минуту
                        
                except Exception as e:
                    logger.error(f"Ошибка в автоматическом бэкапе: {e}")
                    time.sleep(300)  # Ждем 5 минут при ошибке
        
        self.thread = threading.Thread(target=backup_loop, daemon=True)
        self.thread.start()
        
        logger.info(f"✅ Автоматическое резервное копирование запущено (интервал: {interval_hours}ч)")
    
    def stop_auto_backup(self):
        """Останавливает автоматическое резервное копирование"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("⏹️ Автоматическое резервное копирование остановлено")
    
    def get_backup_info(self) -> Dict:
        """Возвращает информацию о резервных копиях"""
        try:
            backups = []
            total_size = 0
            
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('backup_') and filename.endswith('.zip'):
                    file_path = os.path.join(self.backup_dir, filename)
                    stat = os.stat(file_path)
                    
                    backups.append({
                        'name': filename,
                        'size_mb': round(stat.st_size / (1024 * 1024), 2),
                        'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'path': file_path
                    })
                    total_size += stat.st_size
            
            # Сортируем по дате создания (новые сначала)
            backups.sort(key=lambda x: x['created'], reverse=True)
            
            return {
                'backup_dir': self.backup_dir,
                'total_backups': len(backups),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'retention_days': self.retention_days,
                'auto_backup_running': self.is_running,
                'backups': backups[:10]  # Последние 10 бэкапов
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о бэкапах: {e}")
            return {'error': str(e)}
    
    def get_backup_size_info(self) -> Dict:
        """Возвращает детальную информацию о размерах бэкапов"""
        try:
            size_by_date = {}
            
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('backup_') and filename.endswith('.zip'):
                    file_path = os.path.join(self.backup_dir, filename)
                    date_str = datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d')
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    
                    if date_str not in size_by_date:
                        size_by_date[date_str] = 0
                    size_by_date[date_str] += size_mb
            
            return {
                'size_by_date': size_by_date,
                'total_backups': len([f for f in os.listdir(self.backup_dir) 
                                    if f.startswith('backup_') and f.endswith('.zip')]),
                'total_size_mb': sum(size_by_date.values())
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о размерах: {e}")
            return {}

# Глобальный сервис бэкапов
backup_service = BackupService()