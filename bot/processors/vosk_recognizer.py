"""
processors/vosk_recognizer.py - распознавание речи с помощью Vosk
"""

import logging
import json
import wave
import os
from pathlib import Path
from typing import Optional, Dict, Any, Union

logger = logging.getLogger(__name__)


class VoskRecognizer:
    def __init__(self, models_paths: Union[Dict[str, str], str] = "models"):
        """
        Инициализация распознавателя Vosk

        Args:
            models_paths: Словарь с путями к моделям или путь к папке с моделями
        """
        self.models_paths = models_paths
        self.models: Dict[str, Any] = {}
        self.recognizers: Dict[str, Any] = {}
        self.initialized = False

    def initialize(self) -> bool:
        """Инициализация моделей Vosk"""
        try:
            logger.info("🔄 Инициализация VoskRecognizer...")

            # Если переданы пути как словарь
            if isinstance(self.models_paths, dict):
                return self._initialize_from_dict(self.models_paths)
            else:
                # Или как строка пути к папке
                return self._initialize_from_directory(str(self.models_paths))

        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации VoskRecognizer: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _initialize_from_dict(self, model_paths: Dict[str, str]) -> bool:
        """Инициализация из словаря путей"""
        try:
            # Импортируем Vosk
            try:
                import vosk
            except ImportError:
                logger.error("❌ Библиотека vosk не установлена. Установите: pip install vosk")
                return False

            models_loaded = 0

            for language, model_path in model_paths.items():
                if not model_path or not os.path.exists(model_path):
                    logger.error(f"❌ Путь к модели {language} не существует: {model_path}")
                    continue

                try:
                    logger.info(f"🔄 Загрузка модели {language} из: {model_path}")
                    self.models[language] = vosk.Model(model_path)
                    self.recognizers[language] = vosk.KaldiRecognizer(self.models[language], 16000)

                    # Настраиваем параметры распознавания
                    self.recognizers[language].SetWords(True)
                    self.recognizers[language].SetPartialWords(True)

                    logger.info(f"✅ Модель {language} загружена: {os.path.basename(model_path)}")
                    models_loaded += 1

                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки модели {language}: {e}")

            if models_loaded == 0:
                logger.error("❌ Не удалось загрузить ни одну модель")
                return False

            self.initialized = True
            logger.info(f"✅ VoskRecognizer готов. Загружено моделей: {models_loaded}")
            logger.info(f"🌐 Доступные языки: {list(self.models.keys())}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации из словаря: {e}")
            return False

    def _initialize_from_directory(self, models_dir: str) -> bool:
        """Инициализация из директории с поиском моделей"""
        try:
            models_path = Path(models_dir)

            logger.info(f"🔍 Поиск моделей в: {models_path}")

            if not models_path.exists():
                logger.error(f"❌ Директория с моделями не найдена: {models_path}")
                return False

            # Ищем модели в директории
            available_dirs = []
            for item in os.listdir(models_path):
                full_path = os.path.join(models_path, item)
                if os.path.isdir(full_path):
                    available_dirs.append(item)

            logger.info(f"📁 Найдено папок: {available_dirs}")

            if not available_dirs:
                logger.error("❌ В директории нет подпапок с моделями")
                return False

            # Импортируем Vosk
            try:
                import vosk
            except ImportError:
                logger.error("❌ Библиотека vosk не установлена")
                return False

            # Определяем языки моделей
            models_found = {}

            for dir_name in available_dirs:
                dir_path = os.path.join(models_path, dir_name)

                # Определяем язык по имени папки
                language = None
                dir_lower = dir_name.lower()

                if 'ru' in dir_lower or 'russian' in dir_lower:
                    language = 'ru'
                elif 'en' in dir_lower or 'english' in dir_lower or 'us' in dir_lower:
                    language = 'en'

                if language and language not in models_found:
                    models_found[language] = dir_path
                    logger.info(f"✅ Найдена модель {language}: {dir_name}")

            if not models_found:
                logger.error("❌ Не найдены модели с распознаваемыми именами")
                logger.info("ℹ️ Имена папок должны содержать 'ru', 'en', 'russian' или 'english'")
                return False

            # Загружаем найденные модели
            models_loaded = 0
            for language, model_path in models_found.items():
                try:
                    logger.info(f"🔄 Загрузка модели {language}: {model_path}")
                    self.models[language] = vosk.Model(model_path)
                    self.recognizers[language] = vosk.KaldiRecognizer(self.models[language], 16000)

                    # Настраиваем параметры распознавания
                    self.recognizers[language].SetWords(True)
                    self.recognizers[language].SetPartialWords(True)

                    logger.info(f"✅ Модель {language} успешно загружена")
                    models_loaded += 1

                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки модели {language}: {e}")

            if models_loaded == 0:
                logger.error("❌ Не удалось загрузить ни одну модель")
                return False

            self.initialized = True
            logger.info(f"✅ VoskRecognizer готов. Загружено моделей: {models_loaded}")
            logger.info(f"🌐 Доступные языки: {list(self.models.keys())}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации из директории: {e}")
            return False

    def recognize_audio(self, audio_path: str, language: str = 'ru') -> Optional[str]:
        """
        Распознавание аудиофайла

        Args:
            audio_path: Путь к аудиофайлу
            language: Язык распознавания ('ru' или 'en')

        Returns:
            Распознанный текст или None в случае ошибки
        """
        if not self.initialized:
            logger.error("❌ Распознаватель Vosk не инициализирован")
            return None

        if language not in self.recognizers:
            available = list(self.recognizers.keys())
            logger.error(f"❌ Язык '{language}' не поддерживается. Доступные: {available}")

            # Пробуем использовать первый доступный язык
            if available:
                language = available[0]
                logger.info(f"🔄 Используем язык по умолчанию: {language}")
            else:
                return None

        try:
            import wave
            import json

            # Проверяем существование файла
            if not os.path.exists(audio_path):
                logger.error(f"❌ Аудиофайл не найден: {audio_path}")
                return None

            # Открываем аудиофайл
            with wave.open(audio_path, 'rb') as wf:
                # Проверяем формат аудио
                if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                    logger.error("❌ Неподдерживаемый формат аудио. Требуется: mono, 16-bit")
                    return None

                sample_rate = wf.getframerate()
                if sample_rate != 16000:
                    logger.warning(f"⚠️ Частота дискретизации {sample_rate}Hz, ожидалось 16000Hz")

                recognizer = self.recognizers[language]

                # Процесс распознавания
                text_parts = []
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if 'text' in result and result['text']:
                            text_parts.append(result['text'])

                # Получаем финальный результат
                result = json.loads(recognizer.FinalResult())
                if 'text' in result and result['text']:
                    text_parts.append(result['text'])

                text = ' '.join(text_parts).strip()

                if text:
                    logger.info(f"✅ Распознан текст ({language}): {text[:100]}...")
                    return text
                else:
                    logger.warning(f"⚠️ Текст не распознан ({language})")
                    return None

        except FileNotFoundError:
            logger.error(f"❌ Аудиофайл не найден: {audio_path}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка распознавания аудио: {e}")
            return None

    def get_available_languages(self) -> list:
        """Получение списка доступных языков"""
        return list(self.models.keys())

    def is_initialized(self) -> bool:
        """Проверка инициализации"""
        return self.initialized

    def check_models(self) -> Dict[str, bool]:
        """Проверка доступности моделей"""
        result = {}

        if isinstance(self.models_paths, dict):
            for lang, path in self.models_paths.items():
                result[lang] = os.path.exists(path) if path else False
                logger.info(f"{'✅' if result[lang] else '❌'} Модель {lang}: {path}")
        else:
            models_path = Path(self.models_paths)
            if models_path.exists():
                for item in os.listdir(models_path):
                    full_path = os.path.join(models_path, item)
                    if os.path.isdir(full_path):
                        result[item] = True

        return result