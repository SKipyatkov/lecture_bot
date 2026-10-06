import hashlib
import os
import pickle
import logging
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
import shutil

from .paths import CACHE_DIR

logger = logging.getLogger(__name__)

class CacheManager:
    """Менеджер кэширования результатов распознавания"""
    
    def __init__(self, cache_dir: str = "cache", ttl_hours: int = 24, max_size_mb: int = 500):
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        self.max_size_mb = max_size_mb
        os.makedirs(cache_dir, exist_ok=True)
        
        # Статистика
        self.hits = 0
        self.misses = 0
        self.writes = 0
    
    def _get_file_hash(self, file_path: str) -> str:
        """Вычисляет MD5 хеш файла"""
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Ошибка вычисления хеша файла {file_path}: {e}")
            # Альтернативный метод для больших файлов - используем размер и время изменения
            stat = os.stat(file_path)
            return hashlib.md5(f"{file_path}_{stat.st_size}_{stat.st_mtime}".encode()).hexdigest()
    
    def _get_cache_path(self, file_hash: str, language: str) -> str:
        """Возвращает путь к файлу кэша"""
        return os.path.join(self.cache_dir, f"{file_hash}_{language}.cache")
    
    def get(self, file_path: str, language: str) -> Optional[Any]:
        """Получает результат из кэша"""
        try:
            if not os.path.exists(file_path):
                self.misses += 1
                return None
            
            file_hash = self._get_file_hash(file_path)
            cache_path = self._get_cache_path(file_hash, language)
            
            if not os.path.exists(cache_path):
                self.misses += 1
                return None
            
            # Проверяем TTL
            cache_mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
            if datetime.now() - cache_mtime > self.ttl:
                os.remove(cache_path)
                self.misses += 1
                return None
            
            # Загружаем данные из кэша
            with open(cache_path, 'rb') as f:
                result = pickle.load(f)
            
            self.hits += 1
            logger.debug(f"✅ Cache hit for {file_hash}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Cache get error: {e}")
            self.misses += 1
            return None
    
    def set(self, file_path: str, language: str, result: Any) -> bool:
        """Сохраняет результат в кэш"""
        try:
            if not os.path.exists(file_path):
                return False
            
            file_hash = self._get_file_hash(file_path)
            cache_path = self._get_cache_path(file_hash, language)
            
            # Проверяем размер кэша перед записью
            if self._get_cache_size_mb() >= self.max_size_mb:
                self._cleanup_oldest_files(10)  # Удаляем 10 самых старых файлов
            
            # Сохраняем данные в кэш
            with open(cache_path, 'wb') as f:
                pickle.dump(result, f)
            
            self.writes += 1
            logger.debug(f"💾 Cache set for {file_hash}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache set error: {e}")
            return False
    
    def _get_cache_size_mb(self) -> float:
        """Возвращает размер кэша в мегабайтах"""
        total_size = 0
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    file_path = os.path.join(self.cache_dir, filename)
                    total_size += os.path.getsize(file_path)
            return total_size / (1024 * 1024)
        except Exception as e:
            logger.error(f"Ошибка получения размера кэша: {e}")
            return 0
    
    def _cleanup_oldest_files(self, count: int = 10):
        """Удаляет самые старые файлы из кэша"""
        try:
            cache_files = []
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    file_path = os.path.join(self.cache_dir, filename)
                    mtime = os.path.getmtime(file_path)
                    cache_files.append((file_path, mtime))
            
            # Сортируем по времени изменения (старые сначала)
            cache_files.sort(key=lambda x: x[1])
            
            # Удаляем самые старые файлы
            for file_path, _ in cache_files[:count]:
                try:
                    os.remove(file_path)
                    logger.debug(f"🗑️ Удален старый кэш-файл: {os.path.basename(file_path)}")
                except Exception as e:
                    logger.error(f"Ошибка удаления кэш-файла {file_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")
    
    def clear_old_cache(self) -> int:
        """Очищает устаревшие кэш-файлы и возвращает количество удаленных"""
        deleted_count = 0
        cutoff_time = datetime.now() - self.ttl
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    file_path = os.path.join(self.cache_dir, filename)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime < cutoff_time:
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                            logger.debug(f"🗑️ Удален устаревший кэш: {filename}")
                        except Exception as e:
                            logger.error(f"Ошибка удаления {file_path}: {e}")
                            
            if deleted_count > 0:
                logger.info(f"🧹 Очищено устаревших кэш-файлов: {deleted_count}")
                
        except Exception as e:
            logger.error(f"❌ Cache cleanup error: {e}")
        
        return deleted_count
    
    def clear_all_cache(self) -> int:
        """Очищает весь кэш и возвращает количество удаленных файлов"""
        deleted_count = 0
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка удаления {file_path}: {e}")
            
            logger.info(f"🧹 Очищен весь кэш: {deleted_count} файлов")
            self.hits = 0
            self.misses = 0
            self.writes = 0
            
        except Exception as e:
            logger.error(f"❌ Clear all cache error: {e}")
        
        return deleted_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кэша"""
        try:
            files = [f for f in os.listdir(self.cache_dir) if f.endswith('.cache')]
            total_size = sum(os.path.getsize(os.path.join(self.cache_dir, f)) for f in files)
            
            hit_rate = 0
            if self.hits + self.misses > 0:
                hit_rate = self.hits / (self.hits + self.misses) * 100
            
            return {
                'total_files': len(files),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'max_size_mb': self.max_size_mb,
                'hits': self.hits,
                'misses': self.misses,
                'writes': self.writes,
                'hit_rate_percent': round(hit_rate, 1),
                'cache_dir': self.cache_dir,
                'ttl_hours': self.ttl.total_seconds() / 3600
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики кэша: {e}")
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'max_size_mb': self.max_size_mb,
                'hits': self.hits,
                'misses': self.misses,
                'writes': self.writes,
                'hit_rate_percent': 0,
                'cache_dir': self.cache_dir,
                'ttl_hours': self.ttl.total_seconds() / 3600
            }
    
    def optimize_cache(self):
        """Оптимизирует кэш - удаляет старые файлы если превышен лимит"""
        current_size = self._get_cache_size_mb()
        if current_size > self.max_size_mb:
            files_to_delete = int((current_size - self.max_size_mb) / 10) + 5
            self._cleanup_oldest_files(files_to_delete)
            logger.info(f"🔧 Кэш оптимизирован, удалено ~{files_to_delete} файлов")

# Глобальный менеджер кэша
cache_manager = CacheManager(cache_dir=str(CACHE_DIR))