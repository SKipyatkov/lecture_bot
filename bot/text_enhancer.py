import re
import logging
from transformers import pipeline
import torch

logger = logging.getLogger(__name__)

class TextEnhancer:
    def __init__(self):
        # Инициализируем модели для исправления опечаток и пунктуации
        self.spell_checkers = {}
        self.punctuation_restorers = {}
        
        # Оптимизация памяти: используем более легкие модели
        self.load_models()
    
    def load_models(self):
        """Загружает модели с оптимизацией памяти"""
        try:
            logger.info("Загрузка оптимизированных моделей...")
            
            # Для русского языка используем более легкие модели
            self.spell_checkers['ru'] = self.create_spell_checker('ru')
            self.punctuation_restorers['ru'] = self.create_punctuation_restorer('ru')
            
            # Для английского языка
            self.spell_checkers['en'] = self.create_spell_checker('en')
            self.punctuation_restorers['en'] = self.create_punctuation_restorer('en')
            
            logger.info("Модели успешно загружены с оптимизацией памяти!")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки моделей: {e}")
            # Резервные простые обработчики
            self.spell_checkers = {'ru': None, 'en': None}
            self.punctuation_restorers = {'ru': None, 'en': None}
    
    def create_spell_checker(self, language):
        """Создает исправитель опечаток с оптимизацией памяти"""
        try:
            if language == 'ru':
                # Используем более простую модель для русского
                return pipeline(
                    'text2text-generation',
                    model='UrukHan/t5-russian-spell',
                    device=0 if torch.cuda.is_available() else -1,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    max_length=128  # Уменьшаем максимальную длину
                )
            else:
                # Используем более простую модель для английского
                return pipeline(
                    'text2text-generation',
                    model='textattack/t5-base-grammar-correction',
                    device=0 if torch.cuda.is_available() else -1,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    max_length=128
                )
        except Exception as e:
            logger.error(f"Ошибка создания исправителя для {language}: {e}")
            return None
    
    def create_punctuation_restorer(self, language):
        """Создает восстановитель пунктуации с оптимизацией памяти"""
        try:
            # Используем text2text-generation для восстановления пунктуации
            if language == 'ru':
                return pipeline(
                    'text2text-generation',
                    model='sberbank-ai/ruRoberta-large',
                    device=0 if torch.cuda.is_available() else -1,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
                )
            else:
                return pipeline(
                    'text2text-generation',
                    model='prithivida/grammar_error_correcter_v1',
                    device=0 if torch.cuda.is_available() else -1,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
                )
        except Exception as e:
            logger.error(f"Ошибка создания восстановителя пунктуации: {e}")
            return None

    def detect_language(self, text):
        """Определяет язык текста"""
        try:
            if not text or len(text.strip()) < 5:
                return 'ru'  # по умолчанию русский
            
            # Простая эвристика для определения языка
            ru_chars = len(re.findall(r'[а-яё]', text.lower()))
            en_chars = len(re.findall(r'[a-z]', text.lower()))
            
            if ru_chars > en_chars:
                return 'ru'
            else:
                return 'en'
        except:
            return 'ru'
    
    def correct_spelling(self, text, language='ru'):
        """Исправляет опечатки с помощью трансформеров"""
        if not text or language not in self.spell_checkers or not self.spell_checkers[language]:
            return text
            
        try:
            # Ограничиваем длину текста для экономии памяти
            if len(text) > 200:
                text = text[:200] + "..."
            
            if language == 'ru':
                prompt = f"исправить: {text}"
                result = self.spell_checkers['ru'](
                    prompt,
                    max_new_tokens=100,
                    num_beams=3,
                    early_stopping=True
                )
                return result[0]['generated_text'].replace("исправить: ", "")
            else:
                prompt = f"correct: {text}"
                result = self.spell_checkers['en'](
                    prompt,
                    max_new_tokens=100,
                    num_beams=3,
                    early_stopping=True
                )
                return result[0]['generated_text'].replace("correct: ", "")
                
        except Exception as e:
            logger.error(f"Ошибка исправления опечаток: {e}")
            return text
    
def restore_punctuation(self, text, language='ru'):
    """Восстанавливает пунктуацию с помощью трансформеров"""
    if not text or language not in self.punctuation_restorers or not self.punctuation_restorers[language]:
        return self.add_basic_punctuation(text)
        
    try:
        # Ограничиваем длину текста
        if len(text) > 300:
            text = text[:300]
        
        # Для английского используем специальный промпт
        if language == 'en':
            prompt = f"Add punctuation to: {text}"
            result = self.punctuation_restorers[language](
                prompt,
                max_new_tokens=150,
                num_beams=3,
                early_stopping=True
            )
            generated = result[0]['generated_text'].replace("Add punctuation to: ", "")
            
            # Проверяем, не дублируется ли текст
            if generated.count(text) > 1:
                # Если текст дублируется, возвращаем оригинал с базовой пунктуацией
                return self.add_basic_punctuation(text)
            return generated
        else:
            # Для русского используем стандартный подход
            result = self.punctuation_restorers[language](text)
            return result[0]['generated_text']
    except Exception as e:
        logger.error(f"Ошибка восстановления пунктуации: {e}")
        return self.add_basic_punctuation(text)
    
def add_basic_punctuation(self, text):
    """Добавляет базовую пунктуацию (резервный метод)"""
    if not text:
        return text
        
    # Убираем лишние пробелы
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Добавляем точку в конец, если её нет
    if text and text[-1] not in '.!?':
        text += '.'
        
    # Простые правила для запятых (общие для обоих языков)
    conjunctions = ['and', 'but', 'or', 'so', 'because', 'although', 'however', 'therefore']
    
    for conj in conjunctions:
        text = re.sub(r'\s+' + conj + r'\s+', ', ' + conj + ' ', text)
    
    # Заглавная буква в начале предложения
    if text and len(text) > 1:
        text = text[0].upper() + text[1:]
    
    return text
    
    def improve_with_context(self, text, context_words=None):
        """Улучшает текст на основе контекста"""
        if not text:
            return text
            
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
            'седня': 'сегодня',
            'ща': 'сейчас',
            'плиз': 'пожалуйста',
            'ок': 'окей',
            'ладно': 'хорошо'
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
        logger.info(f"После исправления опечаток: {corrected[:50]}...")
        
        # Улучшаем контекст
        enhanced = self.improve_with_context(corrected, context_words)
        logger.info(f"После контекстного улучшения: {enhanced[:50]}...")
        
        # Восстанавливаем пунктуацию
        punctuated = self.restore_punctuation(enhanced, language)
        logger.info(f"После восстановления пунктуации: {punctuated[:50]}...")
        
        return punctuated

# Создаем глобальный экземпляр для использования
text_enhancer = TextEnhancer()