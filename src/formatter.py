from src.parser import Lesson


def format_schedule(lessons: list[Lesson], group: str = "") -> str:
    if not lessons:
        return f"Расписание группы {group}: занятий нет."

    header = f"📋 Расписание группы {group}\n{'=' * 35}\n\n"
    lines: list[str] = []
    current_date = ""

    for lesson in lessons:
        if lesson.date != current_date:
            current_date = lesson.date
            lines.append(f"📅 {current_date}")
            lines.append("-" * 30)

        lines.append(
            f"  {lesson.number}. {lesson.time}\n"
            f"     {lesson.kind}: {lesson.subject}\n"
            f"     👤 {lesson.teacher}\n"
            f"     📍 {lesson.room}\n"
        )

    return header + "\n".join(lines)
