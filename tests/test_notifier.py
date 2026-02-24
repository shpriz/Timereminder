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
