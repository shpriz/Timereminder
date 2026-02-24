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
