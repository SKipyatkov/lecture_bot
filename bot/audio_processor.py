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