import os
import json
import wave
import tempfile
import subprocess
from vosk import Model, KaldiRecognizer

class VoskRecognizer:
    def __init__(self, model_path):
        """
        Инициализирует распознаватель Vosk с указанной моделью
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Модель Vosk не найдена по пути: {model_path}")
        
        print(f"Загрузка модели Vosk из: {model_path}")
        self.model = Model(model_path)
        print("Модель Vosk успешно загружена!")
    
    def recognize_audio(self, audio_path):
        """
        Распознает речь из аудиофайла и возвращает текст
        """
        if not os.path.exists(audio_path):
            return "Ошибка: аудиофайл не найден"
        
        try:
            # Открываем файл
            with wave.open(audio_path, "rb") as wf:
                # формат аудио
                if (wf.getnchannels() != 1 or 
                    wf.getsampwidth() != 2 or 
                    wf.getcomptype() != "NONE"):
                    return "Ошибка: неверный формат аудио"
                
                # Создаем распознаватель
                rec = KaldiRecognizer(self.model, wf.getframerate())
                rec.SetWords(True)
                
                results = []
                
                # Читаем и обрабатываем аудио порциями
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        if 'text' in result and result['text']:
                            results.append(result['text'])
                
                # Получаем финальный результат
                final_result = json.loads(rec.FinalResult())
                if 'text' in final_result and final_result['text']:
                    results.append(final_result['text'])
                
                # Объединяем все результаты
                full_text = " ".join(results).strip()
                
                return full_text if full_text else "Не удалось распознать речь"
                
        except Exception as e:
            return f"Ошибка при распознавании: {str(e)}"