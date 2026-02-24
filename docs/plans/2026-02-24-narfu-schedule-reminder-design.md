# NARFU Schedule Reminder — Design Document

**Date:** 2026-02-24
**Status:** Approved

## Problem

Monitor NARFU university schedule (ruz.narfu.ru) and send full schedule to user 2x/day via Telegram + Email. Configurable group and teacher filter.

## Decisions

- **Stack:** Python 3.12 (FastAPI, python-telegram-bot, APScheduler, BeautifulSoup, httpx)
- **Notifications:** Telegram bot (primary) + Email via SMTP
- **Management:** Telegram bot commands (/group, /teacher, /schedule, /status)
- **Hosting:** Docker on VPS, ports 8000+
- **State:** No database. Config in .env + config.json (Docker volume). No change detection — always send full schedule.
- **Architecture:** Single container monolith

## Architecture

```
Docker Container
├── FastAPI :8001 (health check)
├── Telegram Bot (long polling)
├── APScheduler (2x/day cron)
├── Parser (httpx + BeautifulSoup → ruz.narfu.ru)
└── Notifier (Telegram message + SMTP email)
```

## Data Flow

1. Scheduler triggers at configured times (e.g., 07:00, 19:00 MSK)
2. Parser fetches HTML from ruz.narfu.ru/?timetable&group={id}
3. BeautifulSoup extracts lessons (date, time, subject, teacher, room)
4. Optionally filters by teacher surname
5. Formatter renders schedule as readable text
6. Notifier sends to Telegram chat + email

## Telegram Bot Commands

- `/start` — welcome message
- `/group <id>` — change tracked group
- `/teacher <name>` — change teacher filter (empty = all)
- `/schedule` — get schedule now
- `/status` — show current settings

## Configuration (.env)

```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAIL_TO=
DEFAULT_GROUP=19624
DEFAULT_TEACHER=
SCAN_TIMES=07:00,19:00
TZ=Europe/Moscow
```

## Project Structure

```
reminder/
├── src/
│   ├── __init__.py
│   ├── main.py          # entrypoint: FastAPI + boot all components
│   ├── parser.py         # parse ruz.narfu.ru HTML
│   ├── bot.py            # Telegram bot (long polling)
│   ├── scheduler.py      # APScheduler config
│   ├── notifier.py       # Telegram + Email send
│   ├── formatter.py      # schedule → text formatting
│   └── config.py         # load config from env
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```
