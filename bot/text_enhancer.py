import re
import logging
import torch
from transformers import pipeline

logger = logging.getLogger(__name__)

class TextEnhancer:
    def __init__(self):
        self.punctuation_model = None
        self.load_models()
    
    def load_models(self):
        """Загружает модели для улучшения текста"""
        try:
            logger.info("Загрузка моделей для улучшения текста...")
            
            # Специализированная модель для русского языка
            self.punctuation_model = pipeline(
                'text2text-generation',
                model='UrukHan/t5-russian-spell',
                device=0 if torch.cuda.is_available() else -1,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                max_length=512
            )
            
            logger.info("Модель для улучшения текста успешно загружена!")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки моделей: {e}")
            self.punctuation_model = None
    
    def detect_language(self, text):
        """Определяет язык текста"""
        try:
            if not text or len(text.strip()) < 3:
                return 'ru'
            
            ru_chars = len(re.findall(r'[а-яё]', text.lower()))
            en_chars = len(re.findall(r'[a-z]', text.lower()))
            
            return 'ru' if ru_chars > en_chars else 'en'
        except:
            return 'ru'
    
    def enhance_russian_text(self, text):
        """Улучшает русский текст с помощью модели"""
        if not text or not self.punctuation_model:
            return self.add_basic_punctuation(text)
        
        try:
            # Промпты для лучшего результата
            prompts = [
                f"Расставить пунктуацию: {text}",
                f"Исправить текст: {text}",
                f"Восстановить текст: {text}"
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
                    
                    if result and len(result) > 0:
                        enhanced_text = result[0]['generated_text'].strip()
                        
                        # Убираем промпт из результата
                        enhanced_text = enhanced_text.replace("Расставить пунктуацию: ", "")
                        enhanced_text = enhanced_text.replace("Исправить текст: ", "")
                        enhanced_text = enhanced_text.replace("Восстановить текст: ", "")
                        
                        if enhanced_text and len(enhanced_text) > len(text) / 2:
                            logger.info("Модель улучшила русский текст")
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
        
        # Для английского используем правила + базовую пунктуацию
        enhanced = self.fix_english_text(text)
        enhanced = self.add_basic_punctuation(enhanced, 'en')
        
        return enhanced
    
    def fix_english_text(self, text):
        """Исправляет английский текст"""
        if not text:
            return text
        
        # Исправляем частые ошибки
        corrections = {
            r'\bi\b': 'I',
            r'\bu\b': 'you',
            r'\bur\b': 'your',
            r'\bthru\b': 'through',
            r'\btho\b': 'though',
            r'\bcause\b': 'because',
            r'\bkinda\b': 'kind of',
            r'\bsorta\b': 'sort of'
        }
        
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text
    
    def add_basic_punctuation(self, text, language='ru'):
        """Добавляет базовую пунктуацию с учетом языка"""
        if not text:
            return text
        
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Добавляем точку в конец
        if text and text[-1] not in '.!?':
            text += '.'
        
        # Правила для русского языка
        if language == 'ru':
            # Вопросительные слова
            question_words = ['кто', 'что', 'где', 'когда', 'почему', 'как', 'зачем']
            for word in question_words:
                if re.search(rf'\b{word}\b', text.lower()) and '?' not in text:
                    text = text.replace('.', '?', 1)
                    break
            
            # Союзы
            conjunctions = ['но', 'а', 'однако', 'зато', 'поэтому', 'потому что']
            for conj in conjunctions:
                text = text.replace(f' {conj} ', f', {conj} ')
        
        # Правила для английского языка
        else:
            question_words = ['who', 'what', 'where', 'when', 'why', 'how']
            for word in question_words:
                if re.search(rf'\b{word}\b', text.lower()) and '?' not in text:
                    text = text.replace('.', '?', 1)
                    break
            
            conjunctions = ['but', 'however', 'although', 'therefore']
            for conj in conjunctions:
                text = text.replace(f' {conj} ', f', {conj} ')
        
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
                'btw': 'by the way', 'imo': 'in my opinion', 'gonna': 'going to',
                'wanna': 'want to', 'gotta': 'got to'
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
        
        # Улучшаем в зависимости от языка
        if language == 'ru':
            enhanced = self.enhance_russian_text(corrected)
        else:
            enhanced = self.enhance_english_text(corrected)
        
        logger.info(f"После улучшения: {enhanced[:50]}...")
        
        return enhanced

# Создаем глобальный экземпляр для использования
text_enhancer = TextEnhancer()