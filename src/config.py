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
