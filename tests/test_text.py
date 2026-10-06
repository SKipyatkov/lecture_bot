from processors.text_enhancer import polish_text


def test_polish_text_adds_capital_and_period():
    assert polish_text("  привет   лекция ") == "Привет лекция."


def test_polish_text_keeps_existing_punctuation():
    assert polish_text("как дела?") == "Как дела?"
