import logging
import os
from dataclasses import dataclass

from core.cache_manager import cache_manager
from processors.audio_processor import AudioProcessor
from processors.text_enhancer import polish_text
from processors.whisper_recognizer import WhisperRecognizer

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str | None
    duration: float
    language: str | None = None


def transcribe_file(
    source_path: str,
    recognizer: WhisperRecognizer,
    cache_enabled: bool = True,
) -> TranscriptionResult:
    """Конвертирует файл в wav и распознаёт речь. Вызывается из очереди, не из event loop."""
    wav_path = f"{source_path}.wav"
    processor = AudioProcessor()
    try:
        processor.convert_to_wav_file(source_path, wav_path)
        cached = cache_manager.get(wav_path, "auto") if cache_enabled else None
        if isinstance(cached, dict) and cached.get("text"):
            text = cached["text"]
            language = cached.get("language")
            logger.info("Результат взят из кэша")
        else:
            text, language = recognizer.recognize_audio(wav_path)
            if cache_enabled and text:
                cache_manager.set(wav_path, "auto", {"text": text, "language": language})
        if text:
            text = polish_text(text)
        duration = AudioProcessor.get_audio_duration(wav_path)
        return TranscriptionResult(text=text, duration=duration or 0, language=language)
    finally:
        for path in (source_path, wav_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as error:
                    logger.error("Не удалось удалить %s: %s", path, error)
