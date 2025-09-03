import os
import json
import wave
from vosk import Model, KaldiRecognizer
import logging

logger = logging.getLogger(__name__)

class VoskRecognizer:
    def __init__(self, model_paths):
        """
        Инициализирует распознаватель Vosk с поддержкой нескольких языков
        """
        self.models = {}
        self.sample_rate = 16000
        
        # Загружаем все модели
        for lang, path in model_paths.items():
            if not os.path.exists(path):
                logger.warning(f"Модель Vosk для языка '{lang}' не найдена по пути: {path}")
                continue
            
            try:
                logger.info(f"Загрузка модели Vosk для языка '{lang}' из: {path}")
                self.models[lang] = Model(path)
                logger.info(f"Модель Vosk для языка '{lang}' успешно загружена!")
            except Exception as e:
                logger.error(f"Ошибка загрузки модели для языка '{lang}': {e}")
        
        if not self.models:
            raise ValueError("Не удалось загрузить ни одну модель Vosk!")
    
    def create_recognizer(self, language='ru'):
        """
        Создает новый распознаватель для указанного языка
        """
        if language not in self.models:
            # Если модель для языка не найдена, используем первую доступную
            available_languages = list(self.models.keys())
            if not available_languages:
                raise ValueError("Нет доступных моделей для распознавания!")
            language = available_languages[0]
            logger.warning(f"Модель для языка '{language}' не найдена, используем '{language}'")
        
        return KaldiRecognizer(self.models[language], self.sample_rate)
    
    def recognize_audio(self, audio_path, language='ru'):
        """
        Распознает речь из аудиофайла и возвращает текст
        """
        if not os.path.exists(audio_path):
            return "Ошибка: аудиофайл не найден"
        
        try:
            # Открываем аудиофайл
            with wave.open(audio_path, "rb") as wf:
                # Проверяем формат аудио
                if (wf.getnchannels() != 1 or 
                    wf.getsampwidth() != 2 or 
                    wf.getcomptype() != "NONE"):
                    return "Ошибка: неверный формат аудио"
                
                # Создаем распознаватель для нужного языка
                rec = self.create_recognizer(language)
                rec.SetWords(True)
                
                results = []
                
                # Читаем и обрабатываем аудио порциями
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        if 'text' in result and result['text']:
                            results.append(result['text'])
                
                # Получаем финальный результат
                final_result = json.loads(rec.FinalResult())
                if 'text' in final_result and final_result['text']:
                    results.append(final_result['text'])
                
                # Объединяем все результаты
                full_text = " ".join(results).strip()
                
                return full_text if full_text else "Не удалось распознать речь"
                
        except Exception as e:
            logger.error(f"Ошибка распознавания: {e}")
            return f"Ошибка при распознавании: {str(e)}"
    
    def get_available_languages(self):
        """
        Возвращает список доступных языков
        """
        return list(self.models.keys())