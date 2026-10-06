import shutil
import subprocess
from pathlib import Path

import pytest

from processors.audio_processor import AudioProcessor
from processors.whisper_recognizer import WhisperRecognizer

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "faster-whisper-small"


@pytest.mark.skipif(not (MODEL / "model.bin").is_file(), reason="модель Whisper не скачана")
@pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng не установлен")
def test_recognize_detects_language(tmp_path):
    recognizer = WhisperRecognizer(str(MODEL))
    assert recognizer.initialize()
    processor = AudioProcessor()

    cases = (
        ("ru", "привет лекция", None),
        ("en", "hello lecture", "hello"),
    )
    for voice, phrase, expected in cases:
        spoken = tmp_path / f"{voice}.wav"
        prepared = tmp_path / f"{voice}-prepared.wav"
        subprocess.run(
            ["espeak-ng", "-v", voice, "-w", str(spoken), phrase],
            check=True,
        )
        processor.convert_to_wav_file(str(spoken), str(prepared))
        text, language = recognizer.recognize_audio(str(prepared))
        assert language == voice
        assert text
        if expected:
            assert expected in text.lower()
