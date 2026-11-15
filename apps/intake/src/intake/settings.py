from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    internal_api_token: str = Field(alias="INTERNAL_API_TOKEN")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_provider: str = Field(default="fake", alias="LLM_PROVIDER")
    app_timezone: str = Field(default="Asia/Jerusalem", alias="APP_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
