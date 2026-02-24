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
        "Привет! Я бот расписания САФУ.\n\n"
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
