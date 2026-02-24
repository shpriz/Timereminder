# NARFU Schedule Reminder — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Dockerized Python service that parses NARFU university schedule and sends it via Telegram + Email twice daily.

**Architecture:** Single Python process in Docker — FastAPI health endpoint, Telegram bot (long polling) for management, APScheduler for 2x/day schedule sends, BeautifulSoup for HTML parsing, httpx for HTTP, smtplib for email.

**Tech Stack:** Python 3.12, FastAPI, python-telegram-bot v21+, APScheduler 3.x, BeautifulSoup4, httpx, pydantic-settings

---

## HTML Structure Reference (ruz.narfu.ru)

The schedule page uses this HTML structure (needed for parsing):

- Weeks: `div.tab-pane#week_N` (N=1..6)
- Days: `div.list.col-md-2` — day header in `div.dayofweek` (text: "вторник, 24.02.2026")
- Lessons (desktop): `div.timetable_sheet.hidden-xs.hidden-sm` with color class (green/yellow/blue/red)
  - `span.num_para` — lesson number (1-5)
  - `span.time_para` — time ("08:20–09:55")
  - `span.kindOfWork` — type ("Лекция", "Практическое занятие", etc.)
  - `span.discipline` — subject + teacher in `<nobr>` ("Метрология... (Глуханов А.А.)")
  - `span.auditorium` — room in `<b>` + address text
- Status line: `p.status` — last update time

---

### Task 1: Project Scaffolding

**Files:**
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`

**Step 1: Create requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-telegram-bot==21.9
apscheduler==3.10.4
beautifulsoup4==4.12.3
httpx==0.28.1
pydantic-settings==2.7.1
lxml==5.3.0
```

**Step 2: Create .env.example**

```env
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_CHAT_ID=your-chat-id-here
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_TO=recipient@example.com
DEFAULT_GROUP=19624
DEFAULT_TEACHER=
SCAN_TIMES=07:00,19:00
TZ=Europe/Moscow
```

**Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.egg-info/
data/
.venv/
```

**Step 4: Create src/__init__.py**

Empty file.

**Step 5: Create src/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_chat_id: str
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_to: str = ""
    default_group: str = "19624"
    default_teacher: str = ""
    scan_times: str = "07:00,19:00"
    tz: str = "Europe/Moscow"

    @property
    def scan_time_list(self) -> list[tuple[int, int]]:
        result = []
        for t in self.scan_times.split(","):
            t = t.strip()
            h, m = t.split(":")
            result.append((int(h), int(m)))
        return result

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

**Step 6: Commit**

```bash
git init
git add -A
git commit -m "feat: project scaffolding with config and dependencies"
```

---

### Task 2: Schedule Parser

**Files:**
- Create: `src/parser.py`
- Create: `tests/test_parser.py`
- Reference: HTML structure from top of this document

**Step 1: Create test fixture**

Save a sample HTML fragment to `tests/fixtures/schedule.html`. Fetch real HTML from `curl -s 'https://ruz.narfu.ru/?timetable&group=19624' > tests/fixtures/schedule.html` or use this minimal fixture:

```html
<div class="tab-content">
<div class="row tab-pane active" id="week_1">
  <div class="list col-md-2">
    <div class="dayofweek hidden-xs hidden-sm">понедельник, 24.02.2026</div>
    <div class="timetable_sheet hidden-xs hidden-sm green">
      <span class="num_para">1</span>
      <span class="time_para">08:20&ndash;09:55</span>
      <span class="kindOfWork">Лекция</span>
      <span class="discipline">Математика (<nobr>Иванов И.И.</nobr>)</span>
      <span class="auditorium"><b>ауд.&nbsp;4452</b>, наб. Северной Двины, д. 14</span>
    </div>
    <div class="timetable_sheet hidden-xs hidden-sm yellow">
      <span class="num_para">2</span>
      <span class="time_para">10:10&ndash;11:45</span>
      <span class="kindOfWork">Практическое занятие</span>
      <span class="discipline">Физика (<nobr>Петров П.П.</nobr>)</span>
      <span class="auditorium"><b>ауд.&nbsp;1269</b>, наб. Северной Двины, д. 17</span>
    </div>
  </div>
  <div class="list col-md-2">
    <div class="dayofweek hidden-xs hidden-sm">вторник, 25.02.2026</div>
    <div class="timetable_sheet hidden-xs hidden-sm green">
      <span class="num_para">1</span>
      <span class="time_para">08:20&ndash;09:55</span>
      <span class="kindOfWork">Лекция</span>
      <span class="discipline">Химия (<nobr>Сидоров С.С.</nobr>)</span>
      <span class="auditorium"><b>ауд.&nbsp;2101</b>, наб. Северной Двины, д. 14</span>
    </div>
  </div>
</div>
</div>
```

**Step 2: Write failing tests**

```python
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
    assert first.time == "08:20–09:55"
    assert first.kind == "Лекция"
    assert "Математика" in first.subject
    assert first.teacher == "Иванов И.И."
    assert "4452" in first.room


def test_filter_by_teacher():
    html = FIXTURE.read_text()
    lessons = parse_schedule(html, teacher="Иванов")
    assert len(lessons) == 1
    assert lessons[0].teacher == "Иванов И.И."
```

**Step 3: Run tests to verify they fail**

```bash
cd /root/proj/reminder && python -m pytest tests/test_parser.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.parser'`

**Step 4: Implement parser**

```python
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
```

**Step 5: Run tests to verify they pass**

```bash
cd /root/proj/reminder && python -m pytest tests/test_parser.py -v
```
Expected: 3 passed

**Step 6: Commit**

```bash
git add src/parser.py tests/
git commit -m "feat: schedule HTML parser with teacher filtering"
```

---

### Task 3: Fetcher (HTTP client)

**Files:**
- Create: `src/fetcher.py`
- Create: `tests/test_fetcher.py`

**Step 1: Write failing test**

```python
# tests/test_fetcher.py
from unittest.mock import AsyncMock, patch

import pytest

from src.fetcher import fetch_schedule_html


@pytest.mark.asyncio
async def test_fetch_schedule_html():
    mock_response = AsyncMock()
    mock_response.text = "<html>schedule</html>"
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None

    with patch("src.fetcher.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        html = await fetch_schedule_html("19624")
        assert html == "<html>schedule</html>"
        mock_client.get.assert_called_once()
```

**Step 2: Run test, verify fail**

```bash
cd /root/proj/reminder && python -m pytest tests/test_fetcher.py -v
```

**Step 3: Implement fetcher**

```python
# src/fetcher.py
import httpx

BASE_URL = "https://ruz.narfu.ru/"


async def fetch_schedule_html(group_id: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(BASE_URL, params={"timetable": "", "group": group_id})
        resp.raise_for_status()
        return resp.text
```

**Step 4: Run test, verify pass**

```bash
cd /root/proj/reminder && python -m pytest tests/test_fetcher.py -v
```

**Step 5: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: async HTTP fetcher for schedule page"
```

---

### Task 4: Formatter

**Files:**
- Create: `src/formatter.py`
- Create: `tests/test_formatter.py`

**Step 1: Write failing test**

```python
# tests/test_formatter.py
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
    assert "понедельник, 24.02.2026" in text
    assert "Математика" in text
    assert "Иванов И.И." in text
    assert "08:20–09:55" in text
    assert "131318" in text


def test_format_empty():
    text = format_schedule([], group="131318")
    assert "нет" in text.lower() or "пусто" in text.lower()
```

**Step 2: Run test, verify fail**

**Step 3: Implement formatter**

```python
# src/formatter.py
from src.parser import Lesson


def format_schedule(lessons: list[Lesson], group: str = "") -> str:
    if not lessons:
        return f"Расписание группы {group}: занятий не найдено."

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
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add src/formatter.py tests/test_formatter.py
git commit -m "feat: schedule text formatter"
```

---

### Task 5: Notifier (Telegram + Email)

**Files:**
- Create: `src/notifier.py`
- Create: `tests/test_notifier.py`

**Step 1: Write failing test**

```python
# tests/test_notifier.py
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.notifier import send_telegram, send_email


@pytest.mark.asyncio
async def test_send_telegram():
    mock_bot = AsyncMock()
    with patch("src.notifier.Bot", return_value=mock_bot):
        await send_telegram("test message", token="fake-token", chat_id="123")
        mock_bot.send_message.assert_called_once()


def test_send_email():
    with patch("src.notifier.smtplib.SMTP") as mock_smtp_class:
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)
        mock_smtp_class.return_value = mock_smtp

        send_email(
            subject="Test",
            body="Hello",
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_user="user@test.com",
            smtp_password="pass",
            to_email="to@test.com",
        )
        mock_smtp.send_message.assert_called_once()
```

**Step 2: Run test, verify fail**

**Step 3: Implement notifier**

```python
# src/notifier.py
import smtplib
from email.mime.text import MIMEText

from telegram import Bot


async def send_telegram(text: str, token: str, chat_id: str) -> None:
    bot = Bot(token=token)
    # Telegram message limit is 4096 chars
    for i in range(0, len(text), 4096):
        await bot.send_message(chat_id=chat_id, text=text[i : i + 4096])


def send_email(
    subject: str,
    body: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_email: str,
) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
```

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add src/notifier.py tests/test_notifier.py
git commit -m "feat: Telegram and Email notification senders"
```

---

### Task 6: Scheduler

**Files:**
- Create: `src/scheduler.py`

**Step 1: Implement scheduler**

```python
# src/scheduler.py
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import settings
from src.fetcher import fetch_schedule_html
from src.formatter import format_schedule
from src.notifier import send_email, send_telegram
from src.parser import parse_schedule

logger = logging.getLogger(__name__)


async def scheduled_send() -> None:
    logger.info("Scheduled scan started")
    try:
        html = await fetch_schedule_html(settings.default_group)
        lessons = parse_schedule(html, teacher=settings.default_teacher)
        text = format_schedule(lessons, group=settings.default_group)

        await send_telegram(
            text,
            token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
        )
        logger.info("Telegram message sent")

        if settings.smtp_user and settings.email_to:
            send_email(
                subject=f"Расписание группы {settings.default_group}",
                body=text,
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                smtp_user=settings.smtp_user,
                smtp_password=settings.smtp_password,
                to_email=settings.email_to,
            )
            logger.info("Email sent")
    except Exception:
        logger.exception("Scheduled send failed")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    for hour, minute in settings.scan_time_list:
        scheduler.add_job(
            scheduled_send,
            "cron",
            hour=hour,
            minute=minute,
            id=f"send_{hour:02d}_{minute:02d}",
        )
    return scheduler
```

**Step 2: Commit**

```bash
git add src/scheduler.py
git commit -m "feat: APScheduler with configurable cron times"
```

---

### Task 7: Telegram Bot

**Files:**
- Create: `src/bot.py`

**Step 1: Implement bot**

```python
# src/bot.py
import json
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from src.config import settings
from src.fetcher import fetch_schedule_html
from src.formatter import format_schedule
from src.parser import parse_schedule

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("data/config.json")


def load_user_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {
        "group": settings.default_group,
        "teacher": settings.default_teacher,
    }


def save_user_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я бот расписания НАРФУ.\n\n"
        "Команды:\n"
        "/schedule — получить расписание\n"
        "/group <id> — сменить группу\n"
        "/teacher <фамилия> — фильтр по преподавателю\n"
        "/status — текущие настройки"
    )


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = load_user_config()
    await update.message.reply_text("Загружаю расписание...")
    try:
        html = await fetch_schedule_html(cfg["group"])
        lessons = parse_schedule(html, teacher=cfg.get("teacher", ""))
        text = format_schedule(lessons, group=cfg["group"])
        # Split long messages
        for i in range(0, len(text), 4096):
            await update.message.reply_text(text[i : i + 4096])
    except Exception:
        logger.exception("Failed to fetch schedule")
        await update.message.reply_text("Ошибка при загрузке расписания.")


async def cmd_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /group <id>\nПример: /group 19624")
        return
    cfg = load_user_config()
    cfg["group"] = context.args[0]
    save_user_config(cfg)
    settings.default_group = cfg["group"]
    await update.message.reply_text(f"Группа изменена: {cfg['group']}")


async def cmd_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = load_user_config()
    if not context.args:
        cfg["teacher"] = ""
        save_user_config(cfg)
        settings.default_teacher = ""
        await update.message.reply_text("Фильтр по преподавателю снят.")
        return
    cfg["teacher"] = " ".join(context.args)
    save_user_config(cfg)
    settings.default_teacher = cfg["teacher"]
    await update.message.reply_text(f"Преподаватель: {cfg['teacher']}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = load_user_config()
    teacher = cfg.get("teacher", "") or "все"
    times = settings.scan_times
    await update.message.reply_text(
        f"Группа: {cfg['group']}\n"
        f"Преподаватель: {teacher}\n"
        f"Расписание отправки: {times}\n"
        f"Часовой пояс: {settings.tz}"
    )


def create_bot_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("group", cmd_group))
    app.add_handler(CommandHandler("teacher", cmd_teacher))
    app.add_handler(CommandHandler("status", cmd_status))
    return app
```

**Step 2: Commit**

```bash
git add src/bot.py
git commit -m "feat: Telegram bot with /schedule /group /teacher /status commands"
```

---

### Task 8: Main Entrypoint (FastAPI + boot)

**Files:**
- Create: `src/main.py`

**Step 1: Implement main.py**

```python
# src/main.py
import asyncio
import logging

import uvicorn
from fastapi import FastAPI

from src.bot import create_bot_app
from src.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="NARFU Schedule Reminder")


@app.get("/health")
async def health():
    return {"status": "ok"}


async def main() -> None:
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    bot_app = create_bot_app()
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    logger.info("Telegram bot started")

    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="info")
    server = uvicorn.Server(config)
    logger.info("FastAPI server starting on :8001")

    try:
        await server.serve()
    finally:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
        scheduler.shutdown()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Commit**

```bash
git add src/main.py
git commit -m "feat: main entrypoint — FastAPI + bot + scheduler"
```

---

### Task 9: Docker

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

**Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

RUN mkdir -p data

EXPOSE 8001

CMD ["python", "-m", "src.main"]
```

**Step 2: Create docker-compose.yml**

```yaml
services:
  reminder:
    build: .
    container_name: narfu-reminder
    restart: unless-stopped
    ports:
      - "8001:8001"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    environment:
      - TZ=Europe/Moscow
```

**Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: Docker and docker-compose configuration"
```

---

### Task 10: Integration Test + Final Verification

**Step 1: Add pytest and pytest-asyncio to requirements**

Add to `requirements.txt`:
```
pytest==8.3.4
pytest-asyncio==0.24.0
```

**Step 2: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
```

**Step 3: Run all tests**

```bash
cd /root/proj/reminder && pip install -r requirements.txt && python -m pytest tests/ -v
```
Expected: All tests pass.

**Step 4: Test Docker build**

```bash
cd /root/proj/reminder && docker build -t narfu-reminder .
```
Expected: Successful build.

**Step 5: Final commit**

```bash
git add pytest.ini requirements.txt
git commit -m "feat: test infrastructure and final verification"
```

---

## Deployment Checklist

1. Create Telegram bot via @BotFather, get token
2. Send message to bot, get chat_id via `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Copy `.env.example` to `.env`, fill in values
4. `docker compose up -d`
5. Check health: `curl http://localhost:8001/health`
6. Send `/schedule` to bot to verify
