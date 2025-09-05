import os
import tempfile
import subprocess
import logging
import numpy as np
from scipy import signal
from scipy.io import wavfile
import noisereduce as nr

# Добавляем импорт config
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config

logger = logging.getLogger(__name__)

class AudioProcessor:
    @staticmethod
    def enhance_audio(audio_path, output_path):
        """
        Улучшает качество аудио: шумоподавление, нормализация
        """
        try:
            logger.info(f"Улучшение аудио: {audio_path}")
            
            # Читаем аудиофайл
            sample_rate, audio_data = wavfile.read(audio_path)
            
            # Конвертируем в float32 для обработки
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32) / np.iinfo(audio_data.dtype).max
            
            # Шумоподавление
            if config.AUDIO_ENHANCEMENT['noise_reduction']:
                try:
                    # Используем более агрессивные настройки для лучшего подавления шума
                    reduced_noise = nr.reduce_noise(
                        y=audio_data,
                        sr=sample_rate,
                        prop_decrease=0.9,
                        stationary=True,
                        n_fft=1024,
                        win_length=512
                    )
                    audio_data = reduced_noise
                    logger.info("Шумоподавление применено")
                except Exception as e:
                    logger.warning(f"Ошибка шумоподавления: {e}")
            
            # Применяем полосовой фильтр для человеческой речи (300-3400 Hz)
            try:
                nyquist = 0.5 * sample_rate
                low = 300 / nyquist
                high = 3400 / nyquist
                b, a = signal.butter(4, [low, high], btype='band')
                audio_data = signal.filtfilt(b, a, audio_data)
                logger.info("Полосовой фильтр применен")
            except Exception as e:
                logger.warning(f"Ошибка фильтрации: {e}")
            
            # Нормализация громкости
            if config.AUDIO_ENHANCEMENT['normalize']:
                try:
                    max_val = np.max(np.abs(audio_data))
                    if max_val > 0:
                        audio_data = audio_data / max_val * 0.95
                        logger.info("Нормализация громкости применена")
                except Exception as e:
                    logger.warning(f"Ошибка нормализации: {e}")
            
            # Конвертируем обратно в 16-bit PCM
            audio_data = (audio_data * 32767).astype(np.int16)
            
            # Сохраняем улучшенное аудио
            wavfile.write(output_path, sample_rate, audio_data)
            
            logger.info(f"Аудио улучшено: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка улучшения аудио: {e}")
            return False

    @staticmethod
    def convert_to_wav(audio_path, output_path):
        """
        Конвертирует аудиофайл в WAV формат с улучшением качества
        """
        try:
            logger.info(f"Конвертация с улучшением: {audio_path} -> {output_path}")
            
            if not os.path.exists(audio_path):
                logger.error(f"Исходный файл не существует: {audio_path}")
                return False
            
            # Сначала конвертируем в базовый WAV
            temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
            
            command = [
                'ffmpeg',
                '-i', audio_path,
                '-ac', '1',
                '-ar', '16000',
                '-acodec', 'pcm_s16le',
                '-y',
                temp_wav
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Ошибка конвертации: {result.stderr}")
                return False
            
            # Улучшаем качество аудио
            success = AudioProcessor.enhance_audio(temp_wav, output_path)
            
            # Удаляем временный файл
            try:
                os.unlink(temp_wav)
            except:
                pass
            
            return success
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут конвертации аудио")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при конвертации: {e}")
            return False

    @staticmethod
    def extract_audio_from_video(video_path, output_audio_path):
        """
        Извлекает и улучшает аудиодорожку из видеофайла
        """
        try:
            logger.info(f"Извлечение аудио из видео: {video_path}")
            
            # Временный файл для сырого аудио
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
            
            command = [
                'ffmpeg',
                '-i', video_path,
                '-vn',
                '-ac', '1',
                '-ar', '16000',
                '-acodec', 'pcm_s16le',
                '-y',
                temp_audio
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"Ошибка извлечения аудио: {result.stderr}")
                return False
            
            # Улучшаем качество аудио
            success = AudioProcessor.enhance_audio(temp_audio, output_audio_path)
            
            # Удаляем временный файл
            try:
                os.unlink(temp_audio)
            except:
                pass
            
            return success
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут извлечения аудио из видео")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при извлечении аудио: {e}")
            return False

    @staticmethod
    async def process_telegram_audio(audio_file):
        """
        Асинхронно обрабатывает аудиофайл из Telegram с улучшением качества
        """
        logger.info(f"Обработка аудио файла: {audio_file.file_id}")
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_wav_path = temp_file.name
        
        input_path = None
        try:
            # Скачиваем файл
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_input:
                input_path = temp_input.name
                await audio_file.download_to_drive(input_path)
                
                if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                    logger.error("Файл не скачался или пустой")
                    return None
            
            # Конвертируем с улучшением качества
            success = AudioProcessor.convert_to_wav(input_path, temp_wav_path)
            
            # Удаляем временный файл
            try:
                os.unlink(input_path)
            except:
                pass
            
            if success and os.path.exists(temp_wav_path) and os.path.getsize(temp_wav_path) > 0:
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
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
            temp_audio_path = temp_audio.name
        
        input_path = None
        try:
            # Скачиваем видеофайл
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_input:
                input_path = temp_input.name
                await video_file.download_to_drive(input_path)
                
                if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                    logger.error("Видеофайл не скачался или пустой")
                    return None
            
            # Извлекаем и улучшаем аудио
            success = AudioProcessor.extract_audio_from_video(input_path, temp_audio_path)
            
            # Удаляем временный видеофайл
            try:
                os.unlink(input_path)
            except:
                pass
            
            if success and os.path.exists(temp_audio_path) and os.path.getsize(temp_audio_path) > 0:
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

    @staticmethod
    def analyze_audio_quality(audio_path):
        """
        Анализирует качество аудио для диагностики
        """
        try:
            sample_rate, audio_data = wavfile.read(audio_path)
            
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32) / np.iinfo(audio_data.dtype).max
            
            # Анализ RMS (громкость)
            rms = np.sqrt(np.mean(audio_data**2))
            
            # Анализ SNR (отношение сигнал/шум)
            noise_floor = np.std(audio_data[:1000]) if len(audio_data) > 1000 else np.std(audio_data)
            signal_power = np.std(audio_data)
            snr = 20 * np.log10(signal_power / noise_floor) if noise_floor > 0 else 100
            
            return {
                'sample_rate': sample_rate,
                'duration': len(audio_data) / sample_rate,
                'rms': rms,
                'snr_db': snr,
                'max_amplitude': np.max(np.abs(audio_data))
            }
        except Exception as e:
            logger.error(f"Ошибка анализа аудио: {e}")
            return None