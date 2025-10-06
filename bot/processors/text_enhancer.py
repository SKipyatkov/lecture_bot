import re
import logging
from typing import List

logger = logging.getLogger(__name__)

class TextEnhancer:
    """Класс для улучшения распознанного текста"""
    
    def __init__(self):
        self.setup_enhancement_rules()
    
    def setup_enhancement_rules(self):
        """Настройка правил улучшения текста"""
        # Правила для исправления частых ошибок распознавания
        self.common_fixes = [
            # Русский язык
            (r'\bнаверное\b', 'наверное'),
            (r'\bвозможно\b', 'возможно'),
            (r'\bконечно\b', 'конечно'),
            (r'\bвообще\b', 'вообще'),
            (r'\bнапример\b', 'например'),
            (r'\bпожалуйста\b', 'пожалуйста'),
            
            # Английский язык
            (r'\bprobably\b', 'probably'),
            (r'\bpossible\b', 'possible'),
            (r'\bcertainly\b', 'certainly'),
            (r'\bgenerally\b', 'generally'),
            (r'\bfor example\b', 'for example'),
            (r'\bplease\b', 'please'),
        ]
        
        # Правила пунктуации
        self.punctuation_rules = [
            # Вопросительные слова
            (r'\b(что|где|когда|почему|как|кто|чей|сколько)\b[^.?!/]*$', lambda m: m.group(0) + '?'),
            # Восклицательные слова
            (r'\b(вот|так|ну|ой|ах|ух)\b[^.?!/]*$', lambda m: m.group(0) + '!'),
            # Добавление точек в конец предложений
            (r'[а-яa-z0-9]((?![.?!/])\S)*$', lambda m: m.group(0) + '.'),
        ]
    
    def enhance_text(self, text: str, custom_rules: List = None) -> str:
        """
        Улучшает текст: исправляет ошибки, добавляет пунктуацию
        """
        if not text or not text.strip():
            return text
        
        try:
            # Шаг 1: Базовая очистка
            enhanced = self.clean_text(text)
            
            # Шаг 2: Применение общих исправлений
            enhanced = self.apply_common_fixes(enhanced)
            
            # Шаг 3: Применение пользовательских правил
            if custom_rules:
                enhanced = self.apply_custom_rules(enhanced, custom_rules)
            
            # Шаг 4: Улучшение пунктуации
            enhanced = self.enhance_punctuation(enhanced)
            
            # Шаг 5: Исправление регистра
            enhanced = self.fix_capitalization(enhanced)
            
            # Шаг 6: Удаление лишних пробелов
            enhanced = self.remove_extra_spaces(enhanced)
            
            logger.info(f"✅ Текст улучшен: {len(text)} -> {len(enhanced)} символов")
            return enhanced.strip()
            
        except Exception as e:
            logger.error(f"❌ Ошибка улучшения текста: {e}")
            return text
    
    def clean_text(self, text: str) -> str:
        """Очистка текста от артефактов распознавания"""
        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text)
        
        # Удаление специальных символов (кроме пунктуации)
        text = re.sub(r'[^\w\s\.,!?;:()\-—]', '', text)
        
        # Исправление common OCR/ASR ошибок
        text = re.sub(r'\\u\d+', '', text)  # Unicode escape sequences
        
        return text.strip()
    
    def apply_common_fixes(self, text: str) -> str:
        """Применение общих исправлений"""
        for pattern, replacement in self.common_fixes:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
    
    def apply_custom_rules(self, text: str, rules: List) -> str:
        """Применение пользовательских правил"""
        for pattern, replacement in rules:
            text = re.sub(pattern, replacement, text)
        return text
    
    def enhance_punctuation(self, text: str) -> str:
        """Улучшение пунктуации"""
        # Разбиваем на предложения (грубо)
        sentences = re.split(r'([.!?]+\s*)', text)
        enhanced_sentences = []
        
        for i in range(0, len(sentences), 2):
            if i < len(sentences):
                sentence = sentences[i].strip()
                punctuation = sentences[i+1] if i+1 < len(sentences) else ''
                
                if sentence:
                    # Применяем правила пунктуации
                    for pattern, replacement in self.punctuation_rules:
                        if re.search(pattern, sentence, re.IGNORECASE):
                            if callable(replacement):
                                sentence = re.sub(pattern, replacement, sentence)
                            else:
                                sentence = re.sub(pattern, replacement, sentence)
                            break
                    
                    # Добавляем предложение с пунктуацией
                    if not punctuation and not sentence.endswith(('.', '!', '?')):
                        sentence += '.'
                    
                    enhanced_sentences.append(sentence + punctuation)
        
        return ' '.join(enhanced_sentences)
    
    def fix_capitalization(self, text: str) -> str:
        """Исправление регистра букв"""
        # Первая буква первого предложения - заглавная
        if text and text[0].isalpha():
            text = text[0].upper() + text[1:]
        
        # После точки, восклицательного или вопросительного знака - заглавная
        text = re.sub(r'([.!?]\s+)([a-zа-я])', 
                     lambda m: m.group(1) + m.group(2).upper(), text)
        
        return text
    
    def remove_extra_spaces(self, text: str) -> str:
        """Удаление лишних пробелов"""
        # Удаление пробелов вокруг пунктуации
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        text = re.sub(r'([.,!?;:])\s+', r'\1 ', text)
        
        # Удаление множественных пробелов
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def detect_language(self, text: str) -> str:
        """Определение языка текста"""
        russian_chars = len(re.findall(r'[а-яё]', text, re.IGNORECASE))
        english_chars = len(re.findall(r'[a-z]', text, re.IGNORECASE))
        
        if russian_chars > english_chars:
            return 'ru'
        elif english_chars > russian_chars:
            return 'en'
        else:
            return 'unknown'

# Создаем глобальный экземпляр
text_enhancer = TextEnhancer()