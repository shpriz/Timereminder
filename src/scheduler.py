import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.bot import load_subscribers, ensure_migrated
from src.config import settings
from src.fetcher import fetch_schedule_html
from src.formatter import format_schedule
from src.notifier import send_email, send_telegram
from src.parser import filter_by_date, parse_group_name, parse_schedule

logger = logging.getLogger(__name__)


async def scheduled_send(mode: str = "today") -> None:
    """Send schedule. mode='today' for morning, 'tomorrow' for evening."""
    if mode == "tomorrow":
        target = date.today() + timedelta(days=1)
        label = "на завтра"
    else:
        target = date.today()
        label = "на сегодня"

    logger.info("Scheduled send: %s (%s)", label, target)
    subs = load_subscribers()

    if not subs:
        logger.info("No subscribers, skipping")
        return

    for chat_id, cfg in subs.items():
        cfg = ensure_migrated(cfg)
        email = cfg.get("email", "")
        all_texts = []

        for g in cfg.get("groups", []):
            try:
                group_id = g["id"]
                teacher = g.get("teacher", "")

                html = await fetch_schedule_html(group_id)
                group_name = parse_group_name(html)
                all_lessons = parse_schedule(html, teacher=teacher)
                lessons = filter_by_date(all_lessons, target)
                text = format_schedule(lessons, group=group_id, group_name=group_name)
                all_texts.append(text)

                await send_telegram(
                    text,
                    token=settings.telegram_bot_token,
                    chat_id=chat_id,
                )
                logger.info("Telegram sent to %s for group %s", chat_id, group_id)

            except Exception:
                logger.exception("Failed to send group %s to %s", g["id"], chat_id)

        if email and settings.smtp_user and all_texts:
            try:
                send_email(
                    subject=f"Расписание {label}",
                    body="\n\n".join(all_texts),
                    smtp_host=settings.smtp_host,
                    smtp_port=settings.smtp_port,
                    smtp_user=settings.smtp_user,
                    smtp_password=settings.smtp_password,
                    to_email=email,
                )
                logger.info("Email sent to %s", email)
            except Exception:
                logger.exception("Failed to send email to %s", email)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    times = settings.scan_time_list

    if len(times) >= 2:
        # First time = morning (today), last time = evening (tomorrow)
        h, m = times[0]
        scheduler.add_job(
            scheduled_send,
            "cron",
            hour=h, minute=m,
            kwargs={"mode": "today"},
            id=f"send_today_{h:02d}_{m:02d}",
        )
        h, m = times[-1]
        scheduler.add_job(
            scheduled_send,
            "cron",
            hour=h, minute=m,
            kwargs={"mode": "tomorrow"},
            id=f"send_tomorrow_{h:02d}_{m:02d}",
        )
    elif len(times) == 1:
        h, m = times[0]
        scheduler.add_job(
            scheduled_send,
            "cron",
            hour=h, minute=m,
            kwargs={"mode": "today"},
            id=f"send_today_{h:02d}_{m:02d}",
        )

    return scheduler
