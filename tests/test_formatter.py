from src.parser import Lesson
from src.formatter import format_schedule


def test_format_schedule():
    lessons = [
        Lesson(
            date="понедельник, 24.02.2026",
            number="1",
            time="08:20–09:55",
            kind="Лекция",
            subject="Математика",
            teacher="Иванов И.И.",
            room="ауд. 4452, наб. Северной Двины, д. 14",
        ),
        Lesson(
            date="понедельник, 24.02.2026",
            number="2",
            time="10:10–11:45",
            kind="Практика",
            subject="Физика",
            teacher="Петров П.П.",
            room="ауд. 1269, наб. Северной Двины, д. 17",
        ),
    ]
    text = format_schedule(lessons, group="131318")
    assert "24.02.2026" in text
    assert "ПОНЕДЕЛЬНИК" in text
    assert "Математика" in text
    assert "Иванов И.И." in text
    assert "08:20–09:55" in text
    assert "131318" in text


def test_format_empty():
    text = format_schedule([], group="131318")
    assert "нет" in text.lower() or "пусто" in text.lower()
