from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = Field(alias="CALENDAR_DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    internal_api_token: str = Field(alias="INTERNAL_API_TOKEN")
    parent_email: str = Field(alias="PARENT_EMAIL")
    parent_password: str = Field(alias="PARENT_PASSWORD")
    app_timezone: str = Field(default="Asia/Jerusalem", alias="APP_TIMEZONE")
    web_origin: str = Field(alias="WEB_ORIGIN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    intake_url: str = Field(default="http://intake:8000", alias="INTAKE_URL")
    ideas_url: str = Field(default="http://ideas:8000", alias="IDEAS_URL")

    @property
    def cookie_secure(self) -> bool:
        return self.web_origin.startswith("https://")
