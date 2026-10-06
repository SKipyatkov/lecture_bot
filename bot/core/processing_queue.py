import asyncio
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

logger = logging.getLogger(__name__)


class QueueFullError(Exception):
    """Очередь не принимает новые задачи."""

class ProcessingQueue:
    """Асинхронная очередь обработки задач"""
    
    def __init__(self, max_workers=2, max_queue_size=10):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.task_queue = asyncio.Queue(maxsize=max_queue_size)
        self.results = {}
        self.is_running = False
        self.workers = []
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.loop = None
        self._inflight = 0
        
    async def start(self):
        """Запуск очереди обработки"""
        if self.is_running:
            return
            
        self.is_running = True
        self.loop = asyncio.get_event_loop()
        
        # Запускаем workers
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i+1}"))
            self.workers.append(worker)
            
        logger.info(f"🚀 Очередь обработки запущена с {self.max_workers} воркерами")
        
    async def stop(self):
        """Остановка очереди обработки"""
        self.is_running = False
        
        # Останавливаем workers
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        self.thread_pool.shutdown(wait=True)
        logger.info("⏹️ Очередь обработки остановлена")
        
    async def submit(self, func, *args, on_success=None, on_error=None, **kwargs):
        """Ставит задачу в очередь и сразу возвращает управление.

        Тяжёлая функция выполняется в пуле потоков. Колбэки вызываются
        уже в event loop бота, поэтому из них можно писать в PostgreSQL
        и отвечать в Telegram.
        """
        if self.task_queue.qsize() >= self.max_queue_size:
            raise QueueFullError("Очередь переполнена")

        await self.task_queue.put({
            'func': func,
            'args': args,
            'kwargs': kwargs,
            'future': None,
            'on_success': on_success,
            'on_error': on_error,
        })

    async def add_task(self, task_id, func, *args, **kwargs):
        """Добавление задачи в очередь"""
        if self.task_queue.qsize() >= self.max_queue_size:
            raise QueueFullError("Очередь переполнена")
            
        # Создаем future для результата
        future = asyncio.Future()
        self.results[task_id] = future
        
        # Добавляем задачу в очередь
        task_data = {
            'task_id': task_id,
            'func': func,
            'args': args,
            'kwargs': kwargs,
            'future': future,
            'on_success': None,
            'on_error': None,
        }
        
        await self.task_queue.put(task_data)
        logger.debug(f"📥 Задача {task_id} добавлена в очередь")
        
        # Ждем результат
        try:
            result = await future
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения задачи {task_id}: {e}")
            raise
        finally:
            # Убираем из результатов
            self.results.pop(task_id, None)
            
    async def _worker(self, worker_name):
        """Воркер для обработки задач"""
        logger.debug(f"👷 {worker_name} запущен")
        
        while self.is_running:
            try:
                # Ждем задачу с таймаутом
                try:
                    task_data = await asyncio.wait_for(
                        self.task_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                    
                func = task_data['func']
                args = task_data['args']
                kwargs = task_data['kwargs']
                future = task_data.get('future')
                on_success = task_data.get('on_success')
                on_error = task_data.get('on_error')
                self._inflight += 1

                try:
                    if inspect.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = await self.loop.run_in_executor(
                            self.thread_pool,
                            partial(func, *args, **kwargs),
                        )

                    if future is not None and not future.done():
                        future.set_result(result)
                    await self._invoke_callback(on_success, result)
                except Exception as e:
                    logger.error(f"❌ {worker_name} ошибка задачи: {e}")
                    if future is not None and not future.done():
                        future.set_exception(e)
                    await self._invoke_callback(on_error, e)
                        
                finally:
                    self._inflight = max(0, self._inflight - 1)
                    self.task_queue.task_done()
                    
            except asyncio.CancelledError:
                logger.debug(f"⏹️ {worker_name} остановлен")
                break
            except Exception as e:
                logger.error(f"❌ {worker_name} критическая ошибка: {e}")
                continue
                
    async def _invoke_callback(self, callback, value):
        if callback is None:
            return
        result = callback(value)
        if asyncio.iscoroutine(result):
            await result

    def get_queue_stats(self):
        """Получение статистики очереди"""
        return {
            'queue_size': self.task_queue.qsize(),
            'max_queue_size': self.max_queue_size,
            'active_tasks': self._inflight,
            'workers': len(self.workers)
        }
        
    async def wait_for_completion(self):
        """Ожидание завершения всех задач"""
        await self.task_queue.join()
        
    def cancel_task(self, task_id):
        """Отмена задачи"""
        if task_id in self.results:
            future = self.results[task_id]
            if not future.done():
                future.cancel()
                logger.info(f"❌ Задача {task_id} отменена")
                return True
        return False

# Глобальный экземпляр очереди
processing_queue = ProcessingQueue()