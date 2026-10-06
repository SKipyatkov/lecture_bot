import logging
import os
import threading

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "ru": "русский",
    "en": "английский",
    "uk": "украинский",
    "de": "немецкий",
    "fr": "французский",
    "es": "испанский",
    "it": "итальянский",
    "pl": "польский",
    "tr": "турецкий",
    "kk": "казахский",
    "zh": "китайский",
}


def language_label(code: str | None) -> str:
    if not code:
        return "не определён"
    return LANGUAGE_NAMES.get(code, code)


class WhisperRecognizer:
    """Локальный Whisper. Язык определяется по самой записи."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        self._lock = threading.Lock()

    def initialize(self) -> bool:
        if not os.path.isdir(self.model_path) or not os.path.isfile(os.path.join(self.model_path, "model.bin")):
            logger.error("Модель Whisper не найдена: %s", self.model_path)
            return False
        try:
            from faster_whisper import WhisperModel

            logger.info("Загрузка Whisper из %s", self.model_path)
            self.model = WhisperModel(self.model_path, device="cpu", compute_type="int8")
            logger.info("Whisper готов")
            return True
        except Exception as error:
            logger.error("Не удалось загрузить Whisper: %s", error)
            return False

    def is_initialized(self) -> bool:
        return self.model is not None

    def recognize_audio(self, audio_path: str) -> tuple[str | None, str | None]:
        """Возвращает текст и код языка. Язык не задаётся снаружи."""
        if self.model is None:
            return None, None
        with self._lock:
            segments, info = self.model.transcribe(
                audio_path,
                language=None,
                vad_filter=True,
                beam_size=5,
            )
            text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
            language = info.language or None
            logger.info(
                "Распознан текст (%s, %.2f): %s",
                language,
                info.language_probability,
                (text[:100] + "...") if len(text) > 100 else text,
            )
            return (text or None), language
