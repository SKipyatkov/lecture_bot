import os
import json
import wave
import logging
import re  # Добавляем импорт re
from vosk import Model, KaldiRecognizer

# Добавляем импорт config и AudioProcessor
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config
from audio_processor import AudioProcessor

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
        
        recognizer = KaldiRecognizer(self.models[language], self.sample_rate)
        
        # Устанавливаем настройки для улучшения качества
        recognizer.SetWords(True)
        recognizer.SetPartialWords(True)
        recognizer.SetMaxAlternatives(config.VOSK_SETTINGS['max_alternatives'])
        
        return recognizer
    
    def detect_language(self, audio_path):
        """
        Автоматически определяет язык аудио
        """
        try:
            # Простая эвристика: пробуем распознать короткий сегмент на разных языках
            with wave.open(audio_path, "rb") as wf:
                # Читаем первые 5 секунд
                data = wf.readframes(5 * self.sample_rate)
                
                scores = {}
                for lang in self.models.keys():
                    try:
                        rec = KaldiRecognizer(self.models[lang], self.sample_rate)
                        rec.SetWords(False)
                        rec.SetMaxAlternatives(1)
                        
                        if rec.AcceptWaveform(data):
                            result = json.loads(rec.Result())
                            if 'text' in result and result['text'].strip():
                                # Оцениваем уверенность по длине текста
                                scores[lang] = len(result['text'])
                    except:
                        continue
                
                if scores:
                    best_lang = max(scores.items(), key=lambda x: x[1])[0]
                    logger.info(f"Автоопределение языка: {best_lang} (score: {scores[best_lang]})")
                    return best_lang
        
        except Exception as e:
            logger.error(f"Ошибка определения языка: {e}")
        
        return 'ru'  # fallback
    
    def recognize_audio(self, audio_path, language='auto'):
        """
        Распознает речь из аудиофайла и возвращает текст с улучшенным качеством
        """
        if not os.path.exists(audio_path):
            return "Ошибка: аудиофайл не найден"
        
        # Автоопределение языка если нужно
        if language == 'auto':
            language = self.detect_language(audio_path)
        
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
                
                results = []
                alternatives = []
                confidence_scores = []
                
                # Читаем и обрабатываем аудио порциями
                chunk_size = 4000
                total_frames = wf.getnframes()
                processed_frames = 0
                
                while True:
                    data = wf.readframes(chunk_size)
                    if len(data) == 0:
                        break
                    
                    processed_frames += len(data) / (wf.getsampwidth() * wf.getnchannels())
                    
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        if 'text' in result and result['text']:
                            results.append(result['text'])
                        
                        # Сохраняем альтернативы если есть
                        if 'alternatives' in result:
                            alternatives.extend(result['alternatives'])
                    
                    # Также получаем частичные результаты
                    partial_result = json.loads(rec.PartialResult())
                    if 'partial' in partial_result and partial_result['partial']:
                        logger.debug(f"Partial: {partial_result['partial']}")
                
                # Получаем финальный результат
                final_result = json.loads(rec.FinalResult())
                if 'text' in final_result and final_result['text']:
                    results.append(final_result['text'])
                
                if 'alternatives' in final_result:
                    alternatives.extend(final_result['alternatives'])
                
                # Объединяем все результаты
                full_text = " ".join(results).strip()
                
                if not full_text and alternatives:
                    # Используем лучшую альтернативу
                    best_alternative = max(alternatives, key=lambda x: x.get('confidence', 0))
                    full_text = best_alternative.get('text', '')
                
                # Постобработка текста
                full_text = self.postprocess_text(full_text)
                
                return full_text if full_text else "Не удалось распознать речь"
                
        except Exception as e:
            logger.error(f"Ошибка распознавания: {e}")
            return f"Ошибка при распознавании: {str(e)}"
    
    def postprocess_text(self, text):
        """
        Постобработка распознанного текста
        """
        if not text:
            return text
        
        # Удаляем лишние пробелы
        text = ' '.join(text.split())
        
        # Исправляем частые ошибки распознавания
        common_errors = {
            'щас': 'сейчас', 'кста': 'кстати', 'вообщем': 'в общем',
            'итд': 'и так далее', 'здрасте': 'здравствуйте', 'пака': 'пока',
            'спсибо': 'спасибо', 'пожалуйсто': 'пожалуйста', 'седня': 'сегодня'
        }
        
        for wrong, correct in common_errors.items():
            text = text.replace(wrong, correct)
        
        # Добавляем точку в конец если нужно
        if text and text[-1] not in '.!?':
            text += '.'
        
        # Заглавная буква в начале
        if text and len(text) > 1:
            text = text[0].upper() + text[1:]
        
        return text
    
    def get_available_languages(self):
        """
        Возвращает список доступных языков
        """
        return list(self.models.keys())
    
    def get_model_info(self, language):
        """
        Возвращает информацию о модели
        """
        if language in self.models:
            return {
                'language': language,
                'model': self.models[language],
                'version': '0.42'  # Примерная версия
            }
        return None
    
    def get_recognition_quality(self, audio_path):
        """
        Оценивает качество аудио для распознавания
        """
        try:
            quality = AudioProcessor.analyze_audio_quality(audio_path)
            if quality:
                # Простая оценка качества
                score = 0
                if quality['rms'] > 0.05:  # Достаточно громко
                    score += 1
                if quality['snr_db'] > 15:  # Хорошее отношение сигнал/шум
                    score += 1
                if quality['max_amplitude'] > 0.1:  # Нет клиппинга
                    score += 1
                
                return {
                    'score': score,
                    'details': quality,
                    'quality': 'good' if score >= 2 else 'poor'
                }
        except:
            pass
        
        return {'score': 0, 'quality': 'unknown'}