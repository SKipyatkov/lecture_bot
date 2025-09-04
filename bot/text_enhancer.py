import re
import logging
import torch
from transformers import pipeline

logger = logging.getLogger(__name__)

class TextEnhancer:
    def __init__(self):
        self.punctuation_model = None
        self.spell_checker = None
        self.load_models()
    
    def load_models(self):
        """Загружает модели для улучшения текста"""
        try:
            logger.info("Загрузка моделей для улучшения текста...")
            
            # Специализированная модель для русского языка с пунктуацией
            self.punctuation_model = pipeline(
                'text2text-generation',
                model='UrukHan/t5-russian-spell',
                device=0 if torch.cuda.is_available() else -1,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                max_length=512
            )
            
            logger.info("Модель для русского текста успешно загружена!")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки моделей: {e}")
            self.punctuation_model = None
    
    def detect_language(self, text):
        """Определяет язык текста"""
        try:
            if not text or len(text.strip()) < 5:
                return 'ru'
            
            ru_chars = len(re.findall(r'[а-яё]', text.lower()))
            en_chars = len(re.findall(r'[a-z]', text.lower()))
            
            if ru_chars > en_chars:
                return 'ru'
            else:
                return 'en'
        except:
            return 'ru'
    
    def enhance_russian_text(self, text):
        """Улучшает русский текст с помощью специализированной модели"""
        if not text or not self.punctuation_model:
            return self.add_basic_punctuation(text)
        
        try:
            # Промпты для русской модели
            prompts = [
                f"исправить: {text}",
                f"Добавить пунктуацию: {text}",
                f"Восстановить текст: {text}",
                f"Исправить орфографию: {text}"
            ]
            
            for prompt in prompts:
                try:
                    result = self.punctuation_model(
                        prompt,
                        max_new_tokens=512,
                        num_beams=3,
                        temperature=0.3,
                        do_sample=False,
                        early_stopping=True,
                        repetition_penalty=1.1
                    )
                    
                    enhanced_text = result[0]['generated_text'].strip()
                    
                    # Убираем промпт из результата
                    enhanced_text = enhanced_text.replace("исправить: ", "")
                    enhanced_text = enhanced_text.replace("Добавить пунктуацию: ", "")
                    enhanced_text = enhanced_text.replace("Восстановить текст: ", "")
                    enhanced_text = enhanced_text.replace("Исправить орфографию: ", "")
                    
                    if enhanced_text and len(enhanced_text) > 10:
                        logger.info(f"Модель вернула: {enhanced_text[:50]}...")
                        return enhanced_text
                        
                except Exception as e:
                    logger.warning(f"Ошибка с промптом {prompt}: {e}")
                    continue
            
            return self.add_basic_punctuation(text)
            
        except Exception as e:
            logger.error(f"Ошибка улучшения русского текста: {e}")
            return self.add_basic_punctuation(text)
    
    def enhance_english_text(self, text):
        """Улучшает английский текст"""
        if not text:
            return text
        
        try:
            # Для английского используем базовые правила
            return self.add_basic_punctuation(text, 'en')
        except Exception as e:
            logger.error(f"Ошибка улучшения английского текста: {e}")
            return text
    
    def add_basic_punctuation(self, text, language='ru'):
        """Добавляет базовую пунктуацию"""
        if not text:
            return text
        
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Добавляем точку в конец
        if text and text[-1] not in '.!?':
            text += '.'
        
        if language == 'ru':
            # Правила для русского языка
            conjunctions = ['но', 'а', 'однако', 'зато', 'поэтому', 'потому что', 'также']
            for conj in conjunctions:
                text = text.replace(f' {conj} ', f', {conj} ')
            
            # Вопросительные слова
            question_words = ['кто', 'что', 'где', 'когда', 'почему', 'как', 'зачем']
            for word in question_words:
                if word in text.lower() and '?' not in text:
                    text = text.replace('.', '?', 1)
                    break
        else:
            # Правила для английского языка
            conjunctions = ['but', 'however', 'although', 'though', 'therefore']
            for conj in conjunctions:
                text = text.replace(f' {conj} ', f', {conj} ')
            
            question_words = ['who', 'what', 'where', 'when', 'why', 'how']
            for word in question_words:
                if word in text.lower() and '?' not in text:
                    text = text.replace('.', '?', 1)
                    break
        
        # Заглавные буквы в начале предложений
        if text and len(text) > 1:
            text = text[0].upper() + text[1:]
        
        # Восстановление предложений
        text = re.sub(r'([.!?])\s*([a-zа-я])', 
                     lambda m: m.group(1) + ' ' + m.group(2).upper(), text)
        
        return text
    
    def correct_common_mistakes(self, text, language):
        """Исправляет частые ошибки распознавания"""
        if not text:
            return text
        
        common_mistakes = {
            'ru': {
                'щас': 'сейчас', 'кста': 'кстати', 'вообщем': 'в общем',
                'итд': 'и так далее', 'здрасте': 'здравствуйте', 'пака': 'пока',
                'спсибо': 'спасибо', 'пожалуйсто': 'пожалуйста', 'седня': 'сегодня',
                'ща': 'сейчас', 'ок': 'окей', 'чё': 'что', 'ничо': 'ничего',
                'скока': 'сколько', 'када': 'когда', 'чёто': 'что-то',
                'здеся': 'здесь', 'тута': 'тут', 'канеш': 'конечно'
            },
            'en': {
                'plz': 'please', 'thx': 'thanks', 'u': 'you', 'r': 'are',
                'btw': 'by the way', 'imo': 'in my opinion'
            }
        }
        
        mistakes = common_mistakes.get(language, {})
        for wrong, correct in mistakes.items():
            text = re.sub(r'\b' + wrong + r'\b', correct, text, flags=re.IGNORECASE)
        
        return text
    
    def enhance_text(self, text, context_words=None):
        """Основная функция улучшения текста"""
        if not text or text == "Не удалось распознать речь":
            return text
        
        logger.info(f"Улучшаем текст: {text[:50]}...")
        
        # Определяем язык
        language = self.detect_language(text)
        logger.info(f"Определен язык: {language}")
        
        # Исправляем частые ошибки
        corrected = self.correct_common_mistakes(text, language)
        logger.info(f"После исправления ошибок: {corrected[:50]}...")
        
        # Улучшаем в зависимости от языка
        if language == 'ru':
            enhanced = self.enhance_russian_text(corrected)
        else:
            enhanced = self.enhance_english_text(corrected)
        
        logger.info(f"После улучшения: {enhanced[:50]}...")
        
        return enhanced

# Создаем глобальный экземпляр для использования
text_enhancer = TextEnhancer()