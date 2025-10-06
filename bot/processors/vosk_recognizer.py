import os
import json
import logging
from vosk import Model, KaldiRecognizer
import wave

logger = logging.getLogger(__name__)

class VoskRecognizer:
    """Класс для распознавания речи с помощью Vosk"""
    
    def __init__(self, model_paths):
        self.models = {}
        self.available_languages = []
        
        # Загружаем модели для каждого языка
        for lang, path in model_paths.items():
            if os.path.exists(path):
                try:
                    self.models[lang] = Model(path)
                    self.available_languages.append(lang)
                    logger.info(f"✅ Модель Vosk для языка '{lang}' загружена: {path}")
                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки модели {lang}: {e}")
            else:
                logger.warning(f"⚠️ Модель Vosk не найдена: {path}")
        
        if not self.models:
            raise Exception("Не удалось загрузить ни одну модель Vosk!")
    
    def get_available_languages(self):
        """Возвращает список доступных языков"""
        return self.available_languages
    
    def recognize_audio(self, audio_path, language='ru'):
        """
        Распознает речь из аудиофайла
        Возвращает распознанный текст
        """
        if language not in self.models:
            available = ', '.join(self.available_languages)
            return f"Ошибка: Язык '{language}' не поддерживается. Доступные языки: {available}"
        
        try:
            # Открываем аудиофайл
            with wave.open(audio_path, 'rb') as wf:
                # Проверяем формат аудио
                if wf.getnchannels() != 1:
                    return "Ошибка: Аудио должно быть моно (1 канал)"
                
                if wf.getsampwidth() != 2:
                    return "Ошибка: Поддерживается только 16-битное аудио"
                
                # Создаем распознаватель
                recognizer = KaldiRecognizer(self.models[language], wf.getframerate())
                recognizer.SetWords(True)
                
                results = []
                
                # Читаем и распознаем данные
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if 'text' in result and result['text']:
                            results.append(result['text'])
                
                # Получаем финальный результат
                final_result = json.loads(recognizer.FinalResult())
                if 'text' in final_result and final_result['text']:
                    results.append(final_result['text'])
                
                # Объединяем все результаты
                full_text = ' '.join(results).strip()
                
                if full_text:
                    logger.info(f"✅ Распознано: {len(full_text)} символов")
                    return full_text
                else:
                    return "Не удалось распознать речь. Возможно, в аудио нет речи или качество слишком низкое."
        
        except Exception as e:
            error_msg = f"Ошибка распознавания: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def recognize_with_timestamps(self, audio_path, language='ru'):
        """
        Распознает речь с временными метками
        """
        if language not in self.models:
            return None
        
        try:
            with wave.open(audio_path, 'rb') as wf:
                recognizer = KaldiRecognizer(self.models[language], wf.getframerate())
                recognizer.SetWords(True)
                
                results = []
                
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if 'result' in result:
                            results.extend(result['result'])
                
                final_result = json.loads(recognizer.FinalResult())
                if 'result' in final_result:
                    results.extend(final_result['result'])
                
                return results
        
        except Exception as e:
            logger.error(f"Ошибка распознавания с временными метками: {e}")
            return None
    
    def get_model_info(self, language='ru'):
        """Возвращает информацию о модели"""
        if language in self.models:
            return {
                'language': language,
                'model_path': self.models[language].model_path,
                'vocab_size': getattr(self.models[language], 'vocab_size', 'N/A')
            }
        return None