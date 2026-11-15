from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = Field(alias="NOTIFIER_DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    resend_api_key: str = Field(default="", alias="RESEND_API_KEY")
    email_from: str = Field(default="calendar@localhost", alias="EMAIL_FROM")
    smtp_url: str = Field(default="smtp://mailpit:1025", alias="SMTP_URL")
    email_mode: str = Field(default="mailpit", alias="EMAIL_MODE")
    notifier_channels: str = Field(default="email", alias="NOTIFIER_CHANNELS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
