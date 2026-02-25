import json
import logging
from pathlib import Path

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import settings
from src.fetcher import fetch_schedule_html
from src.formatter import format_schedule
from src.notifier import send_email
from src.parser import get_today_lessons, get_tomorrow_lessons, parse_group_name, parse_schedule

logger = logging.getLogger(__name__)

SUBSCRIBERS_PATH = Path("data/subscribers.json")

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["📋 Сегодня", "📅 Завтра", "⚙️ Меню"]],
    resize_keyboard=True,
)


def load_subscribers() -> dict[str, dict]:
    if SUBSCRIBERS_PATH.exists():
        return json.loads(SUBSCRIBERS_PATH.read_text())
    return {}


def save_subscribers(subs: dict[str, dict]) -> None:
    SUBSCRIBERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUBSCRIBERS_PATH.write_text(json.dumps(subs, ensure_ascii=False, indent=2))


def get_user_config(chat_id: str) -> dict:
    subs = load_subscribers()
    return subs.get(chat_id, {
        "groups": [{"id": settings.default_group, "teacher": ""}],
        "email": "",
    })


def save_user_config(chat_id: str, cfg: dict) -> None:
    subs = load_subscribers()
    subs[chat_id] = cfg
    save_subscribers(subs)


def ensure_migrated(cfg: dict) -> dict:
    """Migrate old single-group config to multi-group format."""
    if "groups" not in cfg:
        group = cfg.pop("group", settings.default_group)
        teacher = cfg.pop("teacher", "")
        cfg["groups"] = [{"id": group, "teacher": teacher}]
    return cfg


async def send_menu(message) -> None:
    keyboard = [
        [
            InlineKeyboardButton("📋 Сегодня", callback_data="schedule"),
            InlineKeyboardButton("📅 Завтра", callback_data="schedule_tomorrow"),
        ],
        [
            InlineKeyboardButton("➕ Добавить группу", callback_data="addgroup"),
            InlineKeyboardButton("➖ Удалить группу", callback_data="removegroup"),
        ],
        [
            InlineKeyboardButton("👤 Преподаватель", callback_data="teacher"),
            InlineKeyboardButton("📧 Email", callback_data="setemail"),
        ],
        [
            InlineKeyboardButton("ℹ️ Статус", callback_data="status"),
            InlineKeyboardButton("🔴 Отписаться", callback_data="stop"),
        ],
    ]
    await message.reply_text(
        "⚙️ Настройки бота:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    subs = load_subscribers()
    if chat_id not in subs:
        subs[chat_id] = {
            "groups": [{"id": settings.default_group, "teacher": ""}],
            "email": "",
        }
        save_subscribers(subs)

    await update.message.reply_text(
        "Привет! Я бот расписания САФУ.\n\n"
        "Кнопки внизу всегда доступны:\n"
        "📋 — получить расписание\n"
        "⚙️ — открыть меню настроек",
        reply_markup=MAIN_KEYBOARD,
    )
    await send_menu(update.message)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "schedule":
        await do_schedule(query.message, str(update.effective_chat.id), mode="today")
    elif data == "schedule_tomorrow":
        await do_schedule(query.message, str(update.effective_chat.id), mode="tomorrow")
    elif data == "addgroup":
        await query.message.reply_text(
            "Отправь ID группы (из URL, например 19624).\n"
            "Найди на ruz.narfu.ru свою группу, в URL будет ?group=XXXXX"
        )
        context.user_data["awaiting"] = "addgroup"
    elif data == "removegroup":
        await show_remove_group_buttons(query.message, str(update.effective_chat.id))
    elif data == "teacher":
        await show_teacher_group_buttons(query.message, str(update.effective_chat.id))
    elif data == "setemail":
        await query.message.reply_text(
            "Отправь email-адрес для рассылки.\n"
            "Или отправь 'нет' чтобы отключить."
        )
        context.user_data["awaiting"] = "email"
    elif data == "status":
        await do_status(query.message, str(update.effective_chat.id))
    elif data == "stop":
        await do_stop(query.message, str(update.effective_chat.id))
    elif data.startswith("rmgroup:"):
        group_id = data.split(":", 1)[1]
        await do_remove_group(query.message, str(update.effective_chat.id), group_id)
    elif data.startswith("teacherfor:"):
        group_id = data.split(":", 1)[1]
        await query.message.reply_text(
            f"Отправь фамилию преподавателя для группы {group_id}.\n"
            "Или отправь 'все' чтобы убрать фильтр."
        )
        context.user_data["awaiting"] = f"teacher:{group_id}"


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()

    # Handle persistent keyboard buttons
    if text == "📋 Сегодня":
        await do_schedule(update.message, chat_id, mode="today")
        return
    if text == "📅 Завтра":
        await do_schedule(update.message, chat_id, mode="tomorrow")
        return
    if text == "⚙️ Меню":
        await send_menu(update.message)
        return

    # Handle dialog inputs
    awaiting = context.user_data.get("awaiting", "")
    if awaiting == "addgroup":
        context.user_data["awaiting"] = ""
        await do_add_group(update.message, chat_id, text)
    elif awaiting == "email":
        context.user_data["awaiting"] = ""
        await do_set_email(update.message, chat_id, text)
    elif awaiting.startswith("teacher:"):
        group_id = awaiting.split(":", 1)[1]
        context.user_data["awaiting"] = ""
        await do_set_teacher(update.message, chat_id, group_id, text)


async def show_remove_group_buttons(message, chat_id: str) -> None:
    cfg = ensure_migrated(get_user_config(chat_id))
    if not cfg["groups"]:
        await message.reply_text("Нет добавленных групп.")
        return
    keyboard = [
        [InlineKeyboardButton(f"❌ Группа {g['id']}", callback_data=f"rmgroup:{g['id']}")]
        for g in cfg["groups"]
    ]
    await message.reply_text("Какую группу удалить?", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_teacher_group_buttons(message, chat_id: str) -> None:
    cfg = ensure_migrated(get_user_config(chat_id))
    if not cfg["groups"]:
        await message.reply_text("Сначала добавь группу.")
        return
    keyboard = [
        [InlineKeyboardButton(
            f"Группа {g['id']} (👤 {g.get('teacher') or 'все'})",
            callback_data=f"teacherfor:{g['id']}"
        )]
        for g in cfg["groups"]
    ]
    await message.reply_text(
        "Для какой группы настроить преподавателя?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def do_add_group(message, chat_id: str, group_id: str) -> None:
    cfg = ensure_migrated(get_user_config(chat_id))
    for g in cfg["groups"]:
        if g["id"] == group_id:
            await message.reply_text(f"Группа {group_id} уже добавлена.")
            return
    cfg["groups"].append({"id": group_id, "teacher": ""})
    save_user_config(chat_id, cfg)
    await message.reply_text(f"Группа {group_id} добавлена!")


async def do_remove_group(message, chat_id: str, group_id: str) -> None:
    cfg = ensure_migrated(get_user_config(chat_id))
    cfg["groups"] = [g for g in cfg["groups"] if g["id"] != group_id]
    save_user_config(chat_id, cfg)
    await message.reply_text(f"Группа {group_id} удалена.")


async def do_set_teacher(message, chat_id: str, group_id: str, teacher: str) -> None:
    cfg = ensure_migrated(get_user_config(chat_id))
    if teacher.lower() in ("все", "all", ""):
        teacher = ""
    for g in cfg["groups"]:
        if g["id"] == group_id:
            g["teacher"] = teacher
            break
    save_user_config(chat_id, cfg)
    label = teacher or "все"
    await message.reply_text(f"Группа {group_id}: преподаватель — {label}")


async def do_set_email(message, chat_id: str, email: str) -> None:
    cfg = ensure_migrated(get_user_config(chat_id))
    if email.lower() in ("нет", "no", "off", ""):
        cfg["email"] = ""
        save_user_config(chat_id, cfg)
        await message.reply_text("Email-рассылка отключена.")
    else:
        cfg["email"] = email
        save_user_config(chat_id, cfg)
        await message.reply_text(f"Email для рассылки: {email}")


async def do_schedule(message, chat_id: str, mode: str = "today") -> None:
    cfg = ensure_migrated(get_user_config(chat_id))
    if not cfg["groups"]:
        await message.reply_text("Нет добавленных групп. Используй /addgroup")
        return

    label = "на сегодня" if mode == "today" else "на завтра"
    await message.reply_text(f"Загружаю расписание {label}...")

    all_texts = []
    for g in cfg["groups"]:
        try:
            html = await fetch_schedule_html(g["id"])
            group_name = parse_group_name(html)
            all_lessons = parse_schedule(html, teacher=g.get("teacher", ""))
            if mode == "tomorrow":
                lessons = get_tomorrow_lessons(all_lessons)
            else:
                lessons = get_today_lessons(all_lessons)
            text = format_schedule(lessons, group=g["id"], group_name=group_name)
            all_texts.append(text)
            for i in range(0, len(text), 4096):
                await message.reply_text(text[i : i + 4096])
        except Exception:
            logger.exception("Failed to fetch schedule for group %s", g["id"])
            await message.reply_text(f"Ошибка при загрузке группы {g['id']}.")

    # Send one email with all groups combined
    email = cfg.get("email", "")
    if email and settings.smtp_user and settings.smtp_password and all_texts:
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
        except Exception:
            logger.exception("Failed to send email to %s", email)


async def do_status(message, chat_id: str) -> None:
    cfg = ensure_migrated(get_user_config(chat_id))
    subs = load_subscribers()
    subscribed = "да" if chat_id in subs else "нет"
    groups_text = ""
    for g in cfg.get("groups", []):
        t = g.get("teacher", "") or "все"
        groups_text += f"  • {g['id']} (👤 {t})\n"
    if not groups_text:
        groups_text = "  нет групп\n"
    email = cfg.get("email", "") or "не задан"

    keyboard = [
        [
            InlineKeyboardButton("➕ Группа", callback_data="addgroup"),
            InlineKeyboardButton("➖ Группа", callback_data="removegroup"),
        ],
        [
            InlineKeyboardButton("👤 Преподаватель", callback_data="teacher"),
            InlineKeyboardButton("📧 Email", callback_data="setemail"),
        ],
    ]
    await message.reply_text(
        f"Подписка: {subscribed}\n"
        f"Группы:\n{groups_text}"
        f"Email: {email}\n"
        f"Рассылка: {settings.scan_times}\n"
        f"Часовой пояс: {settings.tz}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def do_stop(message, chat_id: str) -> None:
    subs = load_subscribers()
    if chat_id in subs:
        del subs[chat_id]
        save_subscribers(subs)
        await message.reply_text("Ты отписан от рассылки. /start чтобы подписаться снова.")
    else:
        await message.reply_text("Ты и так не подписан. /start чтобы подписаться.")


# Command wrappers for text commands
async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mode = "today"
    if context.args and context.args[0].lower() in ("завтра", "tomorrow"):
        mode = "tomorrow"
    await do_schedule(update.message, str(update.effective_chat.id), mode=mode)


async def cmd_addgroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /addgroup <id>\nПример: /addgroup 19624")
        return
    await do_add_group(update.message, str(update.effective_chat.id), context.args[0])


async def cmd_removegroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await show_remove_group_buttons(update.message, str(update.effective_chat.id))
        return
    await do_remove_group(update.message, str(update.effective_chat.id), context.args[0])


async def cmd_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await show_teacher_group_buttons(update.message, str(update.effective_chat.id))
        return
    # /teacher groupid name
    chat_id = str(update.effective_chat.id)
    cfg = ensure_migrated(get_user_config(chat_id))
    if len(cfg["groups"]) == 1:
        teacher = " ".join(context.args)
        await do_set_teacher(update.message, chat_id, cfg["groups"][0]["id"], teacher)
    else:
        await update.message.reply_text("Укажи группу: /teacher <group_id> <фамилия>")


async def cmd_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    email = context.args[0] if context.args else ""
    await do_set_email(update.message, str(update.effective_chat.id), email)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await do_status(update.message, str(update.effective_chat.id))


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await do_stop(update.message, str(update.effective_chat.id))


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("start", "Старт / показать меню"),
        BotCommand("schedule", "Получить расписание"),
        BotCommand("addgroup", "Добавить группу"),
        BotCommand("removegroup", "Удалить группу"),
        BotCommand("teacher", "Фильтр по преподавателю"),
        BotCommand("email", "Настроить email"),
        BotCommand("status", "Текущие настройки"),
        BotCommand("stop", "Отписаться от рассылки"),
    ])


def create_bot_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("addgroup", cmd_addgroup))
    app.add_handler(CommandHandler("removegroup", cmd_removegroup))
    app.add_handler(CommandHandler("teacher", cmd_teacher))
    app.add_handler(CommandHandler("email", cmd_email))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    return app
