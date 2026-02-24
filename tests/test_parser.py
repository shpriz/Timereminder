# tests/test_parser.py
from pathlib import Path

from src.parser import Lesson, parse_schedule

FIXTURE = Path(__file__).parent / "fixtures" / "schedule.html"


def test_parse_returns_lessons():
    html = FIXTURE.read_text()
    lessons = parse_schedule(html)
    assert len(lessons) == 3


def test_lesson_fields():
    html = FIXTURE.read_text()
    lessons = parse_schedule(html)
    first = lessons[0]
    assert first.date == "понедельник, 24.02.2026"
    assert first.number == "1"
    assert "08:20" in first.time
    assert "09:55" in first.time
    assert first.kind == "Лекция"
    assert "Математика" in first.subject
    assert first.teacher == "Иванов И.И."
    assert "4452" in first.room


def test_filter_by_teacher():
    html = FIXTURE.read_text()
    lessons = parse_schedule(html, teacher="Иванов")
    assert len(lessons) == 1
    assert lessons[0].teacher == "Иванов И.И."
