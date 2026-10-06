import re


def polish_text(text: str) -> str:
    """Схлопывает пробелы, поднимает первую букву и ставит точку, если её нет.

    Распознаватель возвращает строчную фразу без пунктуации. Это не исправление слов.
    """
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return text
    cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned
