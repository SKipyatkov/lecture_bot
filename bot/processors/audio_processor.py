import os
import tempfile
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import subprocess
import ffmpeg

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Класс для обработки аудиофайлов"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.thread_pool = ThreadPoolExecutor(max_workers=3)
        
    async def process_telegram_audio(self, telegram_file):
        """Обработка аудиофайла из Telegram"""
        try:
            # Скачиваем файл
            file_path = await self._download_telegram_file(telegram_file)
            if not file_path:
                return None
                
            # Конвертируем в WAV
            wav_path = await self._convert_to_wav(file_path)
            
            # Удаляем временный исходный файл
            try:
                os.unlink(file_path)
            except:
                pass
                
            return wav_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки аудио: {e}")
            return None
            
    async def process_telegram_video(self, telegram_file):
        """Обработка видеофайла из Telegram"""
        try:
            # Скачиваем файл
            file_path = await self._download_telegram_file(telegram_file)
            if not file_path:
                return None
                
            # Извлекаем аудио
            audio_path = await self._extract_audio_from_video(file_path)
            
            # Удаляем временный видеофайл
            try:
                os.unlink(file_path)
            except:
                pass
                
            return audio_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки видео: {e}")
            return None
            
    async def process_telegram_video_note(self, telegram_file):
        """Обработка видеосообщения из Telegram"""
        return await self.process_telegram_video(telegram_file)
        
    async def _download_telegram_file(self, telegram_file):
        """Скачивание файла из Telegram"""
        try:
            # Получаем информацию о файле
            file_id = telegram_file.file_id
            file_size = telegram_file.file_size
            
            # Создаем временный файл
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix='.download',
                dir=self.temp_dir
            )
            temp_path = temp_file.name
            temp_file.close()
            
            # Скачиваем файл
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.thread_pool,
                lambda: telegram_file.download(custom_path=temp_path)
            )
            
            logger.debug(f"✅ Файл {file_id} скачан: {temp_path} ({file_size} bytes)")
            return temp_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания файла: {e}")
            return None
            
    async def _convert_to_wav(self, input_path):
        """Конвертация аудио в WAV формат"""
        try:
            output_path = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix='.wav',
                dir=self.temp_dir
            ).name
            
            loop = asyncio.get_event_loop()
            
            # Используем ffmpeg для конвертации
            await loop.run_in_executor(
                self.thread_pool,
                lambda: (
                    ffmpeg
                    .input(input_path)
                    .output(
                        output_path,
                        ac=1,           # моно
                        ar='16000',     # 16kHz
                        acodec='pcm_s16le',
                        loglevel='error'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            )
            
            logger.debug(f"✅ Аудио сконвертировано: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка конвертации аудио: {e}")
            return None
            
    async def _extract_audio_from_video(self, video_path):
        """Извлечение аудио из видео"""
        try:
            output_path = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix='.wav',
                dir=self.temp_dir
            ).name
            
            loop = asyncio.get_event_loop()
            
            # Извлекаем аудио с помощью ffmpeg
            await loop.run_in_executor(
                self.thread_pool,
                lambda: (
                    ffmpeg
                    .input(video_path)
                    .output(
                        output_path,
                        ac=1,           # моно
                        ar='16000',     # 16kHz
                        acodec='pcm_s16le',
                        vn=None,        # без видео
                        loglevel='error'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            )
            
            logger.debug(f"✅ Аудио извлечено из видео: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения аудио: {e}")
            return None
            
    @staticmethod
    def get_audio_duration(audio_path):
        """Получение длительности аудиофайла"""
        try:
            probe = ffmpeg.probe(audio_path)
            duration = float(probe['format']['duration'])
            return duration
        except Exception as e:
            logger.error(f"❌ Ошибка получения длительности аудио: {e}")
            return 0

# Глобальный экземпляр процессора
audio_processor = AudioProcessor()