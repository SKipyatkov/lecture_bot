import os
import logging
import threading
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class AdminAPI:
    """Веб-интерфейс для администрирования бота с использованием FastAPI"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.app = None
        self.thread = None
        self.is_running = False
        self.stats_cache = {}
        self.cache_timeout = 30  # секунды
        
    def _setup_fastapi(self) -> bool:
        """Настраивает FastAPI приложение"""
        try:
            from fastapi import FastAPI, HTTPException
            from fastapi.middleware.cors import CORSMiddleware
            from fastapi.responses import FileResponse
            from fastapi.staticfiles import StaticFiles
            
            self.app = FastAPI(
                title="Lecture Bot Admin API",
                description="API для администрирования Telegram бота распознавания речи",
                version="1.0.0",
                docs_url="/docs",
                redoc_url="/redoc"
            )
            
            # Настраиваем CORS
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            
            # Настраиваем маршруты
            self._setup_routes()
            
            # Создаем директорию для статических файлов
            static_dir = "web/static"
            os.makedirs(static_dir, exist_ok=True)
            self.app.mount("/static", StaticFiles(directory=static_dir), name="static")
            
            logger.info("✅ FastAPI приложение настроено")
            return True
            
        except ImportError as e:
            logger.warning(f"❌ FastAPI не доступен: {e}")
            logger.warning("Установите: pip install fastapi uvicorn")
            self.app = None
            return False
    
    def _setup_routes(self):
        """Настраивает маршруты API"""
        from fastapi import HTTPException, Query, Path
        
        @self.app.get("/")
        async def root():
            return {
                "message": "Lecture Bot Admin API", 
                "status": "running",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.get("/api/health")
        async def health_check():
            """Проверка здоровья сервиса"""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "database": "ok",
                    "cache": "ok", 
                    "processing_queue": "ok"
                }
            }
        
        @self.app.get("/api/stats")
        async def get_stats(use_cache: bool = True):
            """Возвращает общую статистику бота"""
            cache_key = "global_stats"
            
            if use_cache and cache_key in self.stats_cache:
                cache_time, data = self.stats_cache[cache_key]
                if (datetime.now() - cache_time).total_seconds() < self.cache_timeout:
                    return data
            
            try:
                # Импортируем здесь, чтобы избежать циклических импортов
                from core.database import db
                from core.processing_queue import processing_queue
                from core.cache_manager import cache_manager
                
                # Базовая статистика
                total_users, total_requests, total_size, total_duration = db.get_global_stats()
                queue_stats = processing_queue.get_queue_stats()
                cache_stats = cache_manager.get_cache_stats()
                avg_rating, total_ratings = db.get_average_rating()
                
                data = {
                    "users": {
                        "total": total_users,
                        "active_today": 0,  # Заглушка
                    },
                    "requests": {
                        "total": total_requests,
                        "total_size_mb": round(total_size / (1024 * 1024), 2),
                        "total_duration_min": round(total_duration / 60, 1),
                        "avg_rating": round(avg_rating, 2) if avg_rating else 0,
                        "total_ratings": total_ratings
                    },
                    "system": {
                        "queue": queue_stats,
                        "cache": cache_stats,
                        "uptime": "0:00:00"
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
                # Кэшируем результат
                self.stats_cache[cache_key] = (datetime.now(), data)
                
                return data
                
            except Exception as e:
                logger.error(f"Ошибка получения статистики: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/users")
        async def get_users(
            limit: int = Query(50, ge=1, le=1000),
            offset: int = Query(0, ge=0),
            sort_by: str = Query("last_active", regex="^(last_active|total_requests|registration_date)$")
        ):
            """Возвращает список пользователей с пагинацией"""
            try:
                from core.database import db
                users = db.get_all_users()
                
                # Сортировка
                if sort_by == "total_requests":
                    users.sort(key=lambda x: x[4] if len(x) > 4 else 0, reverse=True)
                elif sort_by == "registration_date":
                    users.sort(key=lambda x: x[5] if len(x) > 5 else "", reverse=True)
                else:  # last_active
                    users.sort(key=lambda x: x[5] if len(x) > 5 else "", reverse=True)
                
                # Пагинация
                paginated_users = users[offset:offset + limit]
                
                formatted_users = []
                for user in paginated_users:
                    if len(user) >= 6:
                        formatted_users.append({
                            "user_id": user[0],
                            "username": user[1] or "N/A",
                            "first_name": user[2] or "N/A", 
                            "last_name": user[3] or "N/A",
                            "total_requests": user[4],
                            "last_active": user[5]
                        })
                
                return {
                    "users": formatted_users,
                    "pagination": {
                        "total": len(users),
                        "limit": limit,
                        "offset": offset,
                        "has_more": offset + limit < len(users)
                    }
                }
                
            except Exception as e:
                logger.error(f"Ошибка получения пользователей: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/queue")
        async def get_queue_info():
            """Возвращает информацию об очереди обработки"""
            try:
                from core.processing_queue import processing_queue
                return processing_queue.get_queue_stats()
            except Exception as e:
                logger.error(f"Ошибка получения информации об очереди: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/cache")
        async def get_cache_info():
            """Возвращает информацию о кэше"""
            try:
                from core.cache_manager import cache_manager
                return cache_manager.get_cache_stats()
            except Exception as e:
                logger.error(f"Ошибка получения информации о кэше: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/cache")
        async def clear_cache():
            """Очищает весь кэш"""
            try:
                from core.cache_manager import cache_manager
                deleted_count = cache_manager.clear_all_cache()
                return {"message": f"Cache cleared", "deleted_files": deleted_count}
            except Exception as e:
                logger.error(f"Ошибка очистки кэша: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/backups")
        async def get_backups():
            """Возвращает информацию о бэкапах"""
            try:
                from services.backup_service import backup_service
                return backup_service.get_backup_info()
            except Exception as e:
                logger.error(f"Ошибка получения информации о бэкапах: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/backups/create")
        async def create_backup(comment: str = None):
            """Создает резервную копию"""
            try:
                from services.backup_service import backup_service
                backup_path = backup_service.create_backup(comment)
                if backup_path:
                    return {
                        "message": "Backup created successfully",
                        "backup_path": backup_path,
                        "filename": os.path.basename(backup_path)
                    }
                else:
                    raise HTTPException(status_code=500, detail="Backup creation failed")
            except Exception as e:
                logger.error(f"Ошибка создания бэкапа: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/logs")
        async def get_logs(lines: int = Query(100, ge=1, le=10000)):
            """Возвращает последние строки логов"""
            try:
                log_file = f'bot_log_{datetime.now().strftime("%Y%m%d")}.log'
                if not os.path.exists(log_file):
                    return {"logs": [], "file": log_file, "exists": False}
                
                with open(log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                
                last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                
                return {
                    "logs": last_lines,
                    "file": log_file,
                    "total_lines": len(all_lines),
                    "returned_lines": len(last_lines),
                    "exists": True
                }
            except Exception as e:
                logger.error(f"Ошибка чтения логов: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def start(self):
        """Запускает веб-сервер в отдельном процессе"""
        if self.is_running:
            logger.warning("Веб-сервер уже запущен")
            return
        
        if not self._setup_fastapi():
            logger.warning("Admin API отключен - FastAPI не доступен")
            return
        
        def run_server():
            try:
                import uvicorn
                # Создаем новое event loop для этого потока
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                config = uvicorn.Config(
                    self.app, 
                    host=self.host, 
                    port=self.port,
                    log_level="info",
                    access_log=True,
                    loop="asyncio"
                )
                server = uvicorn.Server(config)
                loop.run_until_complete(server.serve())
                
            except Exception as e:
                logger.error(f"❌ Ошибка веб-сервера: {e}")
                self.is_running = False
        
        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()
        self.is_running = True
        
        logger.info(f"🌐 Веб-панель администратора запущена: http://{self.host}:{self.port}")
        logger.info(f"📚 Документация API: http://{self.host}:{self.port}/docs")
    
    def stop(self):
        """Останавливает веб-сервер"""
        self.is_running = False
        logger.info("🌐 Веб-панель администратора остановлена")
    
    def get_status(self) -> Dict[str, Any]:
        """Возвращает статус веб-сервера"""
        return {
            "is_running": self.is_running,
            "host": self.host,
            "port": self.port,
            "docs_url": f"http://{self.host}:{self.port}/docs" if self.is_running else None
        }

# Глобальный экземпляр API
admin_api = AdminAPI()