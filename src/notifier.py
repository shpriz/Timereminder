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

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
