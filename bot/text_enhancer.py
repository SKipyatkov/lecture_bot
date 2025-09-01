import re
from autocorrect import Speller
from langdetect import detect
import logging

logger = logging.getLogger(__name__)

class TextEnhancer:
    def __init__(self):
        # Создаем "исправителей" для русского и английского (ЗАПОЛНИТЬ В БУДУЩЕМ!)
        self.speller_ru = Speller('ru')
        self.speller_en = Speller('en')
        

    def detect_language(self, text):
        """Определяет язык текста"""
        try:
            if not text or len(text.strip()) < 10:
                return 'ru'  # по умолчанию русский
            return detect(text)
        except:
            return 'ru'
    
    def correct_spelling(self, text, language='ru'):
        """Исправляет опечатки"""
        if not text:
            return text
            
        try:
            if language == 'ru':
                return self.speller_ru(text)
            else:
                return self.speller_en(text)
        except Exception as e:
            logger.error(f"Ошибка исправления опечаток: {e}")
            return text
    
    def add_punctuation(self, text):
        """Добавляет базовую пунктуацию"""
        if not text:
            return text
            
        # Добавляем точку в конец, если её нет
        text = text.strip()
        if text and text[-1] not in '.!?':
            text += '.'
            
        # Простые правила для запятых
        text = re.sub(r'\s+и\s+', ', и ', text)
        text = re.sub(r'\s+но\s+', ', но ', text)
        text = re.sub(r'\s+а\s+', ', а ', text)
        text = re.sub(r'\s+что\s+', ', что ', text)
        text = re.sub(r'\s+который\s+', ', который ', text)
        
        return text
    
    def improve_with_context(self, text, context_words=None):
        """Улучшает текст на основе контекста"""
        if not text:
            return text
            
        # Если указаны слова контекста, используем их
        if context_words:
            for word in context_words:
                if word in self.context_corrections:
                    # Можно добавить специальную обработку для контекстных слов (ПЕРСПЕКТИВА!)
                    pass
        
        # Простые замены часто неправильно распознаваемых слов
        common_mistakes = {
            'щас': 'сейчас',
            'кста': 'кстати', 
            'вообщем': 'в общем',
            'итд': 'и так далее',
            'итп': 'и тому подобное',
            'здрасте': 'здравствуйте',
            'пака': 'пока',
            'спсибо': 'спасибо',
            'пожалуйсто': 'пожалуйста',
            'седня': 'сегодня'
        }
        
        for wrong, correct in common_mistakes.items():
            text = text.replace(wrong, correct)
            
        return text
    
    def enhance_text(self, text, context_words=None):
        """Основная функция улучшения текста"""
        if not text or text == "Не удалось распознать речь":
            return text
            
        logger.info(f"Улучшаем текст: {text[:50]}...")
        
        # Определяем язык
        language = self.detect_language(text)
        logger.info(f"Определен язык: {language}")
        
        # Исправляем опечатки
        corrected = self.correct_spelling(text, language)
        
        # Улучшаем контекст
        enhanced = self.improve_with_context(corrected, context_words)
        
        # Добавляем пунктуацию
        punctuated = self.add_punctuation(enhanced)
        
        logger.info(f"Улучшенный текст: {punctuated[:50]}...")
        
        return punctuated

# Создаем глобальный экземпляр для использования
text_enhancer = TextEnhancer()