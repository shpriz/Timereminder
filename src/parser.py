# src/parser.py
import re
from dataclasses import dataclass

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


def parse_schedule(html: str, teacher: str = "") -> list[Lesson]:
    soup = BeautifulSoup(html, "lxml")
    lessons: list[Lesson] = []

    for week_div in soup.select("div.tab-pane"):
        current_date = ""
        for day_div in week_div.select("div.list"):
            dayofweek = day_div.select_one("div.dayofweek.hidden-xs")
            if dayofweek:
                current_date = dayofweek.get_text(strip=True)

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
                    room=room_el.get_text(" ", strip=True) if room_el else "",
                )
                lessons.append(lesson)

    if teacher:
        lessons = [
            l for l in lessons if teacher.lower() in l.teacher.lower()
        ]

    return lessons
