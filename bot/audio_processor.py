import os
import tempfile
import subprocess
import logging

logger = logging.getLogger(__name__)

class AudioProcessor:
    @staticmethod
    def convert_to_wav(audio_path, output_path):
        """
        Конвертирует аудиофайл в WAV формат с оптимизацией памяти
        """
        try:
            logger.info(f"Конвертация: {audio_path} -> {output_path}")
            
            if not os.path.exists(audio_path):
                logger.error(f"Исходный файл не существует: {audio_path}")
                return False
            
            # Оптимизированная команда ffmpeg с буферизацией
            command = [
                'ffmpeg',
                '-i', audio_path,
                '-ac', '1',
                '-ar', '16000',
                '-acodec', 'pcm_s16le',
                '-threads', '2',  # Ограничиваем потоки для экономии памяти
                '-y',
                output_path
            ]
            
            # Запускаем с ограничением памяти
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, 'FFMPEG_BINARY': 'ffmpeg'}
            )
            
            if result.returncode == 0:
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Конвертация успешна, размер: {os.path.getsize(output_path)} байт")
                    return True
                else:
                    logger.error("Выходной файл не создан или пустой")
                    return False
            else:
                logger.error(f"Ошибка конвертации: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут конвертации аудио")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при конвертации: {e}")
            return False

    @staticmethod
    async def process_telegram_audio(audio_file):
        """
        Асинхронно обрабатывает аудиофайл из Telegram
        """
        logger.info(f"Обработка аудио файла: {audio_file.file_id}")
        
        # Создаем временный файл для конвертации
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_wav_path = temp_file.name
        
        input_path = None
        try:
            # Скачиваем файл во временную директорию
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_input:
                input_path = temp_input.name
                logger.info(f"Скачивание файла в: {input_path}")
                
                # Скачиваем файл
                await audio_file.download_to_drive(input_path)
                
                # Проверяем что файл скачался
                if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                    logger.error("Файл не скачался или пустой")
                    return None
                
                logger.info(f"Файл скачан, размер: {os.path.getsize(input_path)} байт")
            
            # Конвертируем в нужный формат
            success = AudioProcessor.convert_to_wav(input_path, temp_wav_path)
            
            # Удаляем временный входной файл
            try:
                os.unlink(input_path)
            except:
                pass
            
            if success:
                logger.info(f"Аудио успешно обработано: {temp_wav_path}")
                return temp_wav_path
            else:
                logger.error("Ошибка конвертации аудио")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка обработки аудио: {e}")
            # Очищаем временные файлы
            try:
                if input_path and os.path.exists(input_path):
                    os.unlink(input_path)
            except:
                pass
            try:
                os.unlink(temp_wav_path)
            except:
                pass
            return None

    @staticmethod
    def cleanup_temp_file(file_path):
        """
        Удаляет временный файл
        """
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except:
            pass

    @staticmethod
    def get_audio_duration(audio_path):
        """
        Оптимизированное получение длительности аудио
        """
        try:
            # Быстрый способ через ffprobe
            result = subprocess.run([
                'ffprobe', 
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return float(result.stdout.strip())
            return 0
        except (subprocess.TimeoutExpired, ValueError):
            return 0
        except Exception:
            return 0