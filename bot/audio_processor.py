import os
import tempfile
import subprocess
import logging

logger = logging.getLogger(__name__)

class AudioProcessor:
    @staticmethod
    def convert_to_wav(audio_path, output_path):
        """
        Конвертирует аудиофайл в WAV формат (16kHz, mono) для Vosk
        Используем subprocess вместо ffmpeg-python
        """
        try:
            logger.info(f"Конвертация: {audio_path} -> {output_path}")
            
            # Исходный файл
            if not os.path.exists(audio_path):
                logger.error(f"Исходный файл не существует: {audio_path}")
                return False
            
            # subprocess для вызова ffmpeg
            command = [
                'ffmpeg',
                '-i', audio_path,      # входной файл
                '-ac', '1',            # моно
                '-ar', '16000',        # 16 kHz
                '-acodec', 'pcm_s16le', # 16-bit PCM
                '-y',                  # перезаписать выходной файл
                output_path            # выходной файл
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Проверяем что выходной файл создан и не пустой
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
    def extract_audio_from_video(video_path, output_audio_path):
        """
        Извлекает аудиодорожку из видеофайла
        """
        try:
            logger.info(f"Извлечение аудио из видео: {video_path}")
            
            command = [
                'ffmpeg',
                '-i', video_path,          # входной видеофайл
                '-vn',                     # без видео
                '-ac', '1',               # моно
                '-ar', '16000',           # 16 kHz
                '-acodec', 'pcm_s16le',   # 16-bit PCM
                '-y',                     # перезаписать выходной файл
                output_audio_path         # выходной аудиофайл
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60  # увеличенный таймаут для видео
            )
            
            if result.returncode == 0:
                if os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 0:
                    logger.info(f"Аудио извлечено успешно, размер: {os.path.getsize(output_audio_path)} байт")
                    return True
                else:
                    logger.error("Выходной аудиофайл не создан или пустой")
                    return False
            else:
                logger.error(f"Ошибка извлечения аудио: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут извлечения аудио из видео")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при извлечении аудио: {e}")
            return False

    @staticmethod
    async def process_telegram_audio(audio_file):
        """
        Асинхронно обрабатывает аудиофайл из Telegram
        """
        logger.info(f"Обработка аудио файла: {audio_file.file_id}")
        
        # Временный файл для конвертации
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_wav_path = temp_file.name
        
        input_path = None
        try:
            # Файл в дир
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_input:
                input_path = temp_input.name
                logger.info(f"Скачивание файла в: {input_path}")
                
                # Скачиваем файл
                await audio_file.download_to_drive(input_path)
                
                if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                    logger.error("Файл не скачался или пустой")
                    return None
                
                logger.info(f"Файл скачан, размер: {os.path.getsize(input_path)} байт")
            
            # Конверт в нужный формат
            success = AudioProcessor.convert_to_wav(input_path, temp_wav_path)
            
            # Удаляем временный файл
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
    async def process_telegram_video(video_file):
        """
        Асинхронно обрабатывает видеофайл из Telegram
        """
        logger.info(f"Обработка видео файла: {video_file.file_id}")
        
        # Временные файлы
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video_path = temp_video.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
            temp_audio_path = temp_audio.name
        
        try:
            # Скачиваем видеофайл
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_input:
                input_path = temp_input.name
                logger.info(f"Скачивание видео в: {input_path}")
                
                await video_file.download_to_drive(input_path)
                
                if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                    logger.error("Видеофайл не скачался или пустой")
                    return None
                
                logger.info(f"Видеофайл скачан, размер: {os.path.getsize(input_path)} байt")
            
            # Извлекаем аудиодорожку
            success = AudioProcessor.extract_audio_from_video(input_path, temp_audio_path)
            
            # Удаляем временный видеофайл
            try:
                os.unlink(input_path)
            except:
                pass
            
            if success:
                logger.info(f"Аудио из видео успешно извлечено: {temp_audio_path}")
                return temp_audio_path
            else:
                logger.error("Ошибка извлечения аудио из видео")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка обработки видео: {e}")
            # Очищаем временные файлы
            try:
                if input_path and os.path.exists(input_path):
                    os.unlink(input_path)
            except:
                pass
            try:
                os.unlink(temp_audio_path)
            except:
                pass
            return None

    @staticmethod
    async def process_telegram_video_note(video_note_file):
        """
        Обрабатывает кружочек (video note) из Telegram
        """
        logger.info(f"Обработка кружочка: {video_note_file.file_id}")
        return await AudioProcessor.process_telegram_video(video_note_file)

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
        Получает длительность аудиофайла в секундах
        """
        try:
            # Используем ffprobe для получения длительности
            result = subprocess.run([
                'ffprobe', 
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return float(result.stdout.strip())
            return 0
        except:
            return 0