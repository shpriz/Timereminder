# src/parser.py
import re
from dataclasses import dataclass
from datetime import date, timedelta

from bs4 import BeautifulSoup


@dataclass
class Lesson:
    date: str
    number: str
    time: str
    kind: str
    subject: str
    teacher: str
    room: str


def _normalize_whitespace(text: str) -> str:
    """Collapse all whitespace (newlines, tabs, spaces) into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def parse_group_name(html: str) -> str:
    """Extract group code + specialty from page, e.g. '131318 Биотехнические системы и технологии'."""
    soup = BeautifulSoup(html, "lxml")
    h4 = soup.select_one("h4.visible-xs")
    if h4:
        return _normalize_whitespace(h4.get_text())
    title = soup.select_one("title")
    if title:
        text = title.get_text()
        text = text.replace("Расписание САФУ", "").replace("Группа", "").strip(". ")
        return _normalize_whitespace(text)
    return ""


def parse_schedule(html: str, teacher: str = "") -> list[Lesson]:
    soup = BeautifulSoup(html, "lxml")
    lessons: list[Lesson] = []

    for week_div in soup.select("div.tab-pane"):
        current_date = ""
        for day_div in week_div.select("div.list"):
            dayofweek = day_div.select_one("div.dayofweek")
            if dayofweek:
                current_date = _normalize_whitespace(dayofweek.get_text())

            for sheet in day_div.select("div.timetable_sheet.hidden-xs"):
                num = sheet.select_one("span.num_para")
                time_el = sheet.select_one("span.time_para")
                kind_el = sheet.select_one("span.kindOfWork")
                disc_el = sheet.select_one("span.discipline")
                room_el = sheet.select_one("span.auditorium")

                # Extract teacher from discipline text: "Subject (Teacher Name)"
                disc_text = disc_el.get_text(strip=True) if disc_el else ""
                teacher_match = re.search(r"\(([^)]+)\)\s*$", disc_text)
                teacher_name = teacher_match.group(1) if teacher_match else ""
                subject_name = re.sub(r"\s*\([^)]+\)\s*$", "", disc_text)

                lesson = Lesson(
                    date=current_date,
                    number=num.get_text(strip=True) if num else "",
                    time=time_el.get_text(strip=True) if time_el else "",
                    kind=kind_el.get_text(strip=True) if kind_el else "",
                    subject=subject_name,
                    teacher=teacher_name,
                    room=_normalize_whitespace(room_el.get_text()) if room_el else "",
                )
                lessons.append(lesson)

    if teacher:
        lessons = [
            l for l in lessons if teacher.lower() in l.teacher.lower()
        ]

    return lessons


def _extract_date(date_str: str) -> date | None:
    """Extract date from 'вторник, 24.02.2026' format."""
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", date_str)
    if match:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return date(year, month, day)
    return None


def filter_by_date(lessons: list[Lesson], target: date) -> list[Lesson]:
    """Filter lessons for a specific date."""
    target_str = target.strftime("%d.%m.%Y")
    return [l for l in lessons if target_str in l.date]


def get_today_lessons(lessons: list[Lesson]) -> list[Lesson]:
    return filter_by_date(lessons, date.today())


def get_tomorrow_lessons(lessons: list[Lesson]) -> list[Lesson]:
    return filter_by_date(lessons, date.today() + timedelta(days=1))
