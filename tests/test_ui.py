from handlers.common import HELP_BUTTON, STATS_BUTTON, feedback_markup, format_duration, main_keyboard


def test_format_duration():
    assert format_duration(18.2) == "18 сек"
    assert format_duration(90) == "1 мин 30 сек"
    assert format_duration(120) == "2 мин"


def test_keyboards_use_color_styles():
    row = main_keyboard().keyboard[0]
    assert [button.text for button in row] == [STATS_BUTTON, HELP_BUTTON]
    assert row[0].style == "primary"
    assert row[1].style == "success"

    rating = feedback_markup(3).inline_keyboard[0]
    assert rating[0].style == "success"
    assert rating[1].style == "danger"
    assert rating[0].callback_data == "feedback_3_5"
