import logging
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from collections import Counter
import string

logger = logging.getLogger(__name__)

class TextProcessorPlugin(ABC):
    """Абстрактный базовый класс для плагинов обработки текста"""
    
    @abstractmethod
    def process(self, text: str, context: Dict[str, Any] = None) -> str:
        """Обрабатывает текст и возвращает результат"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Возвращает имя плагина"""
        pass
    
    @property
    def description(self) -> str:
        """Возвращает описание плагина"""
        return "Базовый плагин обработки текста"

class PunctuationPlugin(TextProcessorPlugin):
    """Плагин для улучшения пунктуации"""
    
    @property
    def name(self) -> str:
        return "punctuation_enhancer"
    
    @property
    def description(self) -> str:
        return "Улучшает пунктуацию и расставляет знаки препинания"
    
    def process(self, text: str, context: Dict[str, Any] = None) -> str:
        if not text or len(text.strip()) < 3:
            return text
        
        # Базовая очистка
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Добавляем точку в конец если нет пунктуации
        if text and text[-1] not in '.!?…':
            text += '.'
        
        # Заглавные буквы в начале предложений
        sentences = re.split(r'([.!?]+)', text)
        result = []
        
        for i, part in enumerate(sentences):
            if i % 2 == 0:  # Текстовая часть
                if part.strip():
                    # Первая буква - заглавная
                    part = part.strip()
                    if part and part[0].isalpha():
                        part = part[0].upper() + part[1:]
                    result.append(part)
            else:  # Знаки препинания
                result.append(part)
        
        text = ''.join(result)
        
        # Исправление множественных знаков препинания
        text = re.sub(r'([.!?])\1+', r'\1', text)
        
        # Добавление пробелов после знаков препинания
        text = re.sub(r'([.!?])([а-яa-z])', r'\1 \2', text, flags=re.IGNORECASE)
        
        return text

class SpellingCorrectionPlugin(TextProcessorPlugin):
    """Плагин для исправления частых орфографических ошибок"""
    
    def __init__(self):
        self.common_mistakes = {
            'ru': {
                'щас': 'сейчас', 'кста': 'кстати', 'вообщем': 'в общем',
                'здрасте': 'здравствуйте', 'пака': 'пока', 'спсибо': 'спасибо',
                'пожалуйсто': 'пожалуйста', 'седня': 'сегодня', 'ща': 'сейчас',
                'чё': 'что', 'ничо': 'ничего', 'скока': 'сколько', 'када': 'когда',
                'чёто': 'что-то', 'здеся': 'здесь', 'тута': 'тут', 'канеш': 'конечно',
                'ваще': 'вообще', 'го': 'идем', 'по-любому': 'обязательно',
                'респект': 'уважение', 'кросавчег': 'красавчик'
            },
            'en': {
                'plz': 'please', 'thx': 'thanks', 'u': 'you', 'r': 'are',
                'btw': 'by the way', 'imo': 'in my opinion', 'gonna': 'going to',
                'wanna': 'want to', 'gotta': 'got to', 'kinda': 'kind of',
                'sorta': 'sort of', 'ain\'t': 'is not', 'ya': 'you',
                'dunno': 'don\'t know', 'lemme': 'let me'
            }
        }
    
    @property
    def name(self) -> str:
        return "spelling_corrector"
    
    @property
    def description(self) -> str:
        return "Исправляет частые орфографические ошибки и сленг"
    
    def _detect_language(self, text: str) -> str:
        """Определяет язык текста"""
        ru_chars = len(re.findall(r'[а-яё]', text.lower()))
        en_chars = len(re.findall(r'[a-z]', text.lower()))
        return 'ru' if ru_chars > en_chars else 'en'
    
    def process(self, text: str, context: Dict[str, Any] = None) -> str:
        if not text:
            return text
        
        language = self._detect_language(text)
        mistakes = self.common_mistakes.get(language, {})
        
        for wrong, correct in mistakes.items():
            # Используем границы слов чтобы не заменять части слов
            text = re.sub(r'\b' + re.escape(wrong) + r'\b', correct, text, flags=re.IGNORECASE)
        
        return text

class KeywordExtractorPlugin(TextProcessorPlugin):
    """Плагин для извлечения ключевых слов"""
    
    @property
    def name(self) -> str:
        return "keyword_extractor"
    
    @property
    def description(self) -> str:
        return "Извлекает ключевые слова и важные фразы из текста"
    
    def process(self, text: str, context: Dict[str, Any] = None) -> str:
        if not text:
            return text
        
        # Сохраняем оригинальный текст
        original_text = text
        
        try:
            # Извлекаем слова (игнорируем стоп-слова)
            words = re.findall(r'\b\w{4,}\b', text.lower())
            
            # Подсчитываем частоту
            word_freq = Counter(words)
            
            # Получаем самые частые слова
            keywords = [word for word, count in word_freq.most_common(10) if count > 1]
            
            # Сохраняем ключевые слова в контекст
            if context is not None:
                context['keywords'] = keywords
                context['word_frequency'] = dict(word_freq.most_common(20))
            
            logger.debug(f"📊 Извлечены ключевые слова: {keywords}")
            
        except Exception as e:
            logger.error(f"Ошибка извлечения ключевых слов: {e}")
        
        return original_text  # Возвращаем оригинальный текст без изменений

class TextSummaryPlugin(TextProcessorPlugin):
    """Плагин для создания краткого содержания"""
    
    @property
    def name(self) -> str:
        return "text_summarizer"
    
    @property
    def description(self) -> str:
        return "Создает краткое содержание длинного текста"
    
    def process(self, text: str, context: Dict[str, Any] = None) -> str:
        if not text or len(text) < 100:
            return text
        
        try:
            # Простая суммаризация - берем первые 3 предложения
            sentences = re.split(r'[.!?]+', text)
            valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
            
            if len(valid_sentences) <= 3:
                return text
            
            summary = '. '.join(valid_sentences[:3]) + '.'
            
            # Сохраняем суммаризацию в контекст
            if context is not None:
                context['summary'] = summary
                context['original_length'] = len(text)
                context['summary_length'] = len(summary)
                context['compression_ratio'] = round(len(summary) / len(text) * 100, 1)
            
            logger.debug(f"📝 Создано краткое содержание: {len(summary)}/{len(text)} символов")
            
            return summary
            
        except Exception as e:
            logger.error(f"Ошибка суммаризации текста: {e}")
            return text

class EmotionDetectionPlugin(TextProcessorPlugin):
    """Плагин для определения эмоциональной окраски текста"""
    
    def __init__(self):
        self.emotion_words = {
            'positive': {
                'ru': ['хорошо', 'отлично', 'прекрасно', 'замечательно', 'великолепно', 
                      'рад', 'счастлив', 'удовольствие', 'спасибо', 'благодарю'],
                'en': ['good', 'great', 'excellent', 'wonderful', 'amazing', 
                      'happy', 'pleased', 'thanks', 'thank you', 'awesome']
            },
            'negative': {
                'ru': ['плохо', 'ужасно', 'отвратительно', 'грустно', 'злой',
                      'разочарован', 'ненавижу', 'противный', 'скучно', 'устал'],
                'en': ['bad', 'terrible', 'awful', 'sad', 'angry',
                      'disappointed', 'hate', 'boring', 'tired', 'upset']
            }
        }
    
    @property
    def name(self) -> str:
        return "emotion_detector"
    
    @property
    def description(self) -> str:
        return "Анализирует эмоциональную окраску текста"
    
    def _detect_language(self, text: str) -> str:
        ru_chars = len(re.findall(r'[а-яё]', text.lower()))
        en_chars = len(re.findall(r'[a-z]', text.lower()))
        return 'ru' if ru_chars > en_chars else 'en'
    
    def process(self, text: str, context: Dict[str, Any] = None) -> str:
        if not text:
            return text
        
        language = self._detect_language(text)
        text_lower = text.lower()
        
        positive_count = 0
        negative_count = 0
        
        # Считаем положительные слова
        for word in self.emotion_words['positive'][language]:
            positive_count += len(re.findall(r'\b' + re.escape(word) + r'\b', text_lower))
        
        # Считаем отрицательные слова
        for word in self.emotion_words['negative'][language]:
            negative_count += len(re.findall(r'\b' + re.escape(word) + r'\b', text_lower))
        
        # Определяем преобладающую эмоцию
        emotion = 'neutral'
        if positive_count > negative_count:
            emotion = 'positive'
        elif negative_count > positive_count:
            emotion = 'negative'
        
        # Сохраняем анализ в контекст
        if context is not None:
            context['emotion_analysis'] = {
                'emotion': emotion,
                'positive_words': positive_count,
                'negative_words': negative_count,
                'language': language
            }
        
        logger.debug(f"😊 Анализ эмоций: {emotion} (+{positive_count}/-{negative_count})")
        
        return text

class PluginSystem:
    """Система управления плагинами обработки текста"""
    
    def __init__(self):
        self.plugins: List[TextProcessorPlugin] = []
        self.enabled_plugins: List[str] = []
        self._load_builtin_plugins()
    
    def _load_builtin_plugins(self):
        """Загружает встроенные плагины"""
        self.register_plugin(PunctuationPlugin())
        self.register_plugin(SpellingCorrectionPlugin())
        self.register_plugin(KeywordExtractorPlugin())
        self.register_plugin(TextSummaryPlugin())
        self.register_plugin(EmotionDetectionPlugin())
        
        # По умолчанию включаем все плагины
        self.enabled_plugins = [plugin.name for plugin in self.plugins]
        
        logger.info(f"✅ Загружено {len(self.plugins)} встроенных плагинов")
    
    def register_plugin(self, plugin: TextProcessorPlugin):
        """Регистрирует новый плагин"""
        if any(p.name == plugin.name for p in self.plugins):
            logger.warning(f"Плагин {plugin.name} уже зарегистрирован")
            return
        
        self.plugins.append(plugin)
        logger.info(f"✅ Зарегистрирован плагин: {plugin.name} - {plugin.description}")
    
    def enable_plugin(self, plugin_name: str):
        """Включает плагин"""
        if plugin_name not in self.enabled_plugins:
            self.enabled_plugins.append(plugin_name)
            logger.info(f"✅ Включен плагин: {plugin_name}")
    
    def disable_plugin(self, plugin_name: str):
        """Выключает плагин"""
        if plugin_name in self.enabled_plugins:
            self.enabled_plugins.remove(plugin_name)
            logger.info(f"✅ Выключен плагин: {plugin_name}")
    
    def process_text(self, text: str, enabled_plugins: List[str] = None) -> Dict[str, Any]:
        """
        Обрабатывает текст через все включенные плагины
        Возвращает словарь с результатом и метаданными
        """
        if not text:
            return {'text': text, 'metadata': {}}
        
        # Используем переданный список или список по умолчанию
        plugins_to_use = enabled_plugins if enabled_plugins is not None else self.enabled_plugins
        
        context = {
            'original_text': text,
            'processed_plugins': [],
            'processing_stats': {}
        }
        
        result_text = text
        
        for plugin in self.plugins:
            if plugin.name in plugins_to_use:
                try:
                    start_time = logger.debug(f"🔧 Обработка плагином: {plugin.name}")
                    result_text = plugin.process(result_text, context)
                    context['processed_plugins'].append(plugin.name)
                    logger.debug(f"✅ Плагин {plugin.name} завершил обработку")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка плагина {plugin.name}: {e}")
                    # Продолжаем обработку с другими плагинами
        
        context['final_text'] = result_text
        context['total_plugins_used'] = len(context['processed_plugins'])
        
        return {
            'text': result_text,
            'metadata': context
        }
    
    def get_available_plugins(self) -> List[Dict[str, str]]:
        """Возвращает список доступных плагинов"""
        return [
            {
                'name': plugin.name,
                'description': plugin.description,
                'enabled': plugin.name in self.enabled_plugins
            }
            for plugin in self.plugins
        ]
    
    def get_plugin_info(self, plugin_name: str) -> Optional[Dict]:
        """Возвращает информацию о конкретном плагине"""
        for plugin in self.plugins:
            if plugin.name == plugin_name:
                return {
                    'name': plugin.name,
                    'description': plugin.description,
                    'enabled': plugin.name in self.enabled_plugins
                }
        return None

# Глобальная система плагинов
plugin_system = PluginSystem()