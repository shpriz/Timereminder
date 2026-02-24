from src.parser import Lesson


def format_schedule(lessons: list[Lesson], group: str = "", group_name: str = "") -> str:
    title = group_name or f"группы {group}"
    if not lessons:
        return f"{title}: занятий нет."

    header = f"📋 {title}\n\n"
    lines: list[str] = []
    current_date = ""

    for lesson in lessons:
        if lesson.date != current_date:
            current_date = lesson.date
            parts = current_date.split(", ", 1)
            if len(parts) == 2:
                day_name = parts[0].upper()
                date_str = parts[1]
                lines.append(f"\n📅  {date_str} | {day_name}")
            else:
                lines.append(f"\n📅  {current_date}")
            lines.append("━" * 16)

        lines.append(
            f"  {lesson.number}. {lesson.time}\n"
            f"     {lesson.kind}: {lesson.subject}\n"
            f"     👤 {lesson.teacher}\n"
            f"     📍 {lesson.room}"
        )

    return header + "\n".join(lines)
