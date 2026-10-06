import math
import struct
import wave

from processors.audio_processor import AudioProcessor


def _write_stereo_tone(path):
    rate = 8000
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = bytearray()
        for index in range(rate):
            sample = int(8000 * math.sin(2 * math.pi * 440 * index / rate))
            frames.extend(struct.pack("<hh", sample, sample))
        wav.writeframes(frames)


def test_convert_to_mono_16k(tmp_path):
    source = tmp_path / "tone.wav"
    target = tmp_path / "out.wav"
    _write_stereo_tone(source)

    AudioProcessor().convert_to_wav_file(str(source), str(target))

    with wave.open(str(target), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16000
        assert wav.getnframes() > 0
