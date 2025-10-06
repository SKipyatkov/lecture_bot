import os
import logging
import tempfile
from typing import Optional, List, Dict
import subprocess
import asyncio
import platform
import winreg  # Для Windows TTS

logger = logging.getLogger(__name__)

class VoiceSynthesizer:
    """Синтезатор речи с поддержкой Windows TTS и eSpeak"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.supported_methods = self._check_available_methods()
        self.available_voices = self._get_available_voices()
        self.temp_dir = "temp_audio"
        os.makedirs(self.temp_dir, exist_ok=True)
        
        logger.info(f"✅ Синтезатор речи инициализирован. Методы: {list(self.supported_methods.keys())}")
    
    def _check_available_methods(self) -> Dict[str, bool]:
        """Проверяет доступные методы синтеза речи"""
        methods = {}
        
        # Проверяем eSpeak
        methods['espeak'] = self._check_espeak()
        
        # Проверяем Windows TTS (только для Windows)
        if self.system == "windows":
            methods['windows_tts'] = self._check_windows_tts()
        else:
            methods['windows_tts'] = False
        
        # Проверяем наличие ffmpeg для конвертации
        methods['ffmpeg'] = self._check_ffmpeg()
        
        return methods
    
    def _check_espeak(self) -> bool:
        """Проверяет доступность eSpeak"""
        try:
            if self.system == "windows":
                result = subprocess.run(['where', 'espeak'], capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run(['which', 'espeak'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _check_windows_tts(self) -> bool:
        """Проверяет доступность Windows TTS"""
        try:
            # Пробуем импортировать библиотеки для Windows TTS
            import win32com.client
            return True
        except ImportError:
            logger.warning("Для Windows TTS установите: pip install pywin32")
            return False
        except:
            return False
    
    def _check_ffmpeg(self) -> bool:
        """Проверяет доступность ffmpeg"""
        try:
            if self.system == "windows":
                result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _get_available_voices(self) -> List[Dict]:
        """Возвращает список доступных голосов"""
        voices = []
        
        # Базовые голоса
        base_voices = [
            {'id': 'ru', 'name': 'Русский', 'language': 'ru', 'gender': 'male', 'method': 'espeak'},
            {'id': 'en', 'name': 'English', 'language': 'en', 'gender': 'male', 'method': 'espeak'},
        ]
        
        # Добавляем Windows TTS голоса если доступны
        if self.supported_methods.get('windows_tts', False):
            try:
                windows_voices = self._get_windows_voices()
                voices.extend(windows_voices)
            except Exception as e:
                logger.warning(f"Ошибка получения Windows голосов: {e}")
        
        # Добавляем eSpeak голоса если доступны
        if self.supported_methods.get('espeak', False):
            try:
                espeak_voices = self._get_espeak_voices()
                voices.extend(espeak_voices)
            except Exception as e:
                logger.warning(f"Ошибка получения eSpeak голосов: {e}")
        
        # Если ничего не найдено, используем базовые
        if not voices:
            voices = base_voices
        
        return voices
    
    def _get_windows_voices(self) -> List[Dict]:
        """Получает голоса Windows TTS"""
        voices = []
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            for voice in speaker.GetVoices():
                voice_info = {
                    'id': voice.Id,
                    'name': voice.GetDescription(),
                    'language': self._extract_language_from_voice(voice.GetDescription()),
                    'gender': 'unknown',
                    'method': 'windows_tts'
                }
                voices.append(voice_info)
        except Exception as e:
            logger.error(f"Ошибка получения Windows голосов: {e}")
        
        return voices
    
    def _extract_language_from_voice(self, voice_description: str) -> str:
        """Извлекает язык из описания голоса Windows"""
        description_lower = voice_description.lower()
        if 'russian' in description_lower or 'русск' in description_lower:
            return 'ru'
        elif 'english' in description_lower or 'англ' in description_lower:
            return 'en'
        else:
            return 'en'  # По умолчанию английский
    
    def _get_espeak_voices(self) -> List[Dict]:
        """Получает голоса eSpeak"""
        voices = []
        try:
            if self.system == "windows":
                result = subprocess.run(['espeak', '--voices'], capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run(['espeak', '--voices'], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 4:
                        voice_id = parts[1]
                        language = parts[2]
                        gender = 'female' if '+f' in voice_id.lower() else 'male'
                        
                        voices.append({
                            'id': voice_id,
                            'name': f"{language} {gender}",
                            'language': language,
                            'gender': gender,
                            'method': 'espeak'
                        })
        except Exception as e:
            logger.error(f"Ошибка получения eSpeak голосов: {e}")
        
        return voices
    
    def text_to_speech(self, text: str, language: str = 'ru', voice_id: str = None) -> Optional[str]:
        """
        Преобразует текст в речь используя лучший доступный метод
        """
        if not text or len(text.strip()) < 2:
            logger.warning("Текст для синтеза слишком короткий")
            return None
        
        # Ограничиваем длину текста
        if len(text) > 1000:
            text = text[:1000] + "..."
            logger.warning("Текст обрезан до 1000 символов")
        
        # Пробуем разные методы в порядке приоритета
        methods_to_try = []
        
        # Windows TTS имеет лучший звук
        if self.supported_methods.get('windows_tts', False):
            methods_to_try.append(('windows_tts', self._windows_tts_synthesize))
        
        # eSpeak как запасной вариант
        if self.supported_methods.get('espeak', False):
            methods_to_try.append(('espeak', self._espeak_synthesize))
        
        if not methods_to_try:
            logger.error("Нет доступных методов синтеза речи")
            return self._create_fallback_audio(text)
        
        # Пробуем каждый метод пока не получится
        for method_name, method_func in methods_to_try:
            try:
                result = method_func(text, language, voice_id)
                if result:
                    logger.info(f"✅ Синтез завершен методом {method_name}: {len(text)} символов")
                    return result
            except Exception as e:
                logger.warning(f"❌ Ошибка синтеза методом {method_name}: {e}")
                continue
        
        logger.error("Все методы синтеза завершились ошибкой")
        return self._create_fallback_audio(text)
    
    def _windows_tts_synthesize(self, text: str, language: str, voice_id: str = None) -> Optional[str]:
        """Синтез речи через Windows TTS"""
        try:
            import win32com.client
            from comtypes.client import CreateObject
            
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, dir=self.temp_dir) as temp_file:
                output_path = temp_file.name
            
            # Создаем объект TTS
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            
            # Выбираем голос если указан
            if voice_id:
                for voice in speaker.GetVoices():
                    if voice.Id == voice_id:
                        speaker.Voice = voice
                        break
            
            # Создаем поток для сохранения в файл
            stream = CreateObject("SAPI.SpFileStream")
            stream.Open(output_path, 3)  # 3 = SSFMCreateForWrite
            speaker.AudioOutputStream = stream
            
            # Синтезируем речь
            speaker.Speak(text)
            stream.Close()
            
            # Конвертируем в MP3 если доступен ffmpeg
            if self.supported_methods.get('ffmpeg', False):
                mp3_path = self._convert_to_mp3(output_path)
                if mp3_path:
                    os.unlink(output_path)
                    return mp3_path
            
            return output_path
            
        except Exception as e:
            logger.error(f"Ошибка Windows TTS синтеза: {e}")
            return None
    
    def _espeak_synthesize(self, text: str, language: str, voice_id: str = None) -> Optional[str]:
        """Синтез речи через eSpeak"""
        try:
            # Выбираем голос
            voice = self._select_voice(language, voice_id, 'espeak')
            if not voice:
                voice = {'id': language}
            
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, dir=self.temp_dir) as temp_file:
                output_path = temp_file.name
            
            # Команда для eSpeak
            cmd = ['espeak', '-v', voice['id'], '-s', '150', '-w', output_path]
            
            # Добавляем текст
            cmd.append(text)
            
            # Запускаем синтез
            if self.system == "windows":
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return None
            
            # Конвертируем в MP3 если доступен ffmpeg
            if self.supported_methods.get('ffmpeg', False) and os.path.exists(output_path):
                mp3_path = self._convert_to_mp3(output_path)
                if mp3_path:
                    os.unlink(output_path)
                    return mp3_path
            
            return output_path if os.path.exists(output_path) else None
            
        except Exception as e:
            logger.error(f"Ошибка eSpeak синтеза: {e}")
            return None
    
    def _select_voice(self, language: str, voice_id: str = None, method: str = None) -> Optional[Dict]:
        """Выбирает подходящий голос"""
        if voice_id:
            for voice in self.available_voices:
                if voice['id'] == voice_id:
                    return voice
        
        # Ищем голос по языку и методу
        for voice in self.available_voices:
            if voice['language'].startswith(language):
                if method is None or voice.get('method') == method:
                    return voice
        
        # Если не нашли, возвращаем первый доступный
        return self.available_voices[0] if self.available_voices else None
    
    def _convert_to_mp3(self, wav_path: str) -> Optional[str]:
        """Конвертирует WAV в MP3"""
        try:
            mp3_path = wav_path.replace('.wav', '.mp3')
            
            cmd = ['ffmpeg', '-i', wav_path, '-codec:a', 'libmp3lame', '-qscale:a', '2', '-y', mp3_path]
            
            if self.system == "windows":
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=10)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and os.path.exists(mp3_path):
                return mp3_path
            else:
                return None
                
        except Exception as e:
            logger.error(f"Ошибка конвертации аудио: {e}")
            return None
    
    def _create_fallback_audio(self, text: str) -> Optional[str]:
        """Создает простой fallback аудиофайл с сообщением об ошибке"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, dir=self.temp_dir) as temp_file:
                temp_file.write(f"Синтез речи недоступен. Текст: {text}".encode('utf-8'))
                return temp_file.name
        except:
            return None
    
    def get_available_voices(self) -> List[Dict]:
        """Возвращает список доступных голосов"""
        return self.available_voices
    
    def get_available_methods(self) -> Dict[str, bool]:
        """Возвращает доступные методы синтеза"""
        return self.supported_methods
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Очищает старые временные файлы"""
        try:
            import time
            current_time = time.time()
            files_removed = 0
            
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                file_age = current_time - os.path.getctime(file_path)
                
                # Удаляем файлы старше max_age_hours
                if file_age > (max_age_hours * 3600):
                    os.unlink(file_path)
                    files_removed += 1
            
            if files_removed > 0:
                logger.info(f"🧹 Очищено {files_removed} временных аудиофайлов")
                
        except Exception as e:
            logger.error(f"Ошибка очистки временных файлов: {e}")

# Глобальный синтезатор речи
voice_synthesizer = VoiceSynthesizer()