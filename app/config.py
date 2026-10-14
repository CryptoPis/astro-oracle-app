from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing import Annotated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "production"
    log_level: str = "INFO"

    bot_token: str
    bot_username: str = "astrogm2026bot"
    mini_app_short_name: str = "app"
    admin_ids: Annotated[list[int], NoDecode] = []
    public_base_url: str = "http://localhost:8000"
    webhook_secret: str = ""
    init_data_max_age: int = 86400

    database_url: str = "sqlite+aiosqlite:///./data/astro.db"

    ai_provider: str = "groq"
    groq_api_key: str = ""
    groq_text_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    ai_timeout_seconds: float = 30

    cors_origins: Annotated[list[str], NoDecode] = []

    bot_enabled: bool = True          # false = API only (tests, frontend dev)
    morning_push_enabled: bool = True
    morning_push_hour: int = 9
    scheduler_timezone: str = "Asia/Tbilisi"

    dev_auth_bypass: bool = False
    dev_user_id: int = 1

    @field_validator("admin_ids", "cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    @property
    def is_dev(self) -> bool:
        return self.env.lower() == "development"

    @property
    def webhook_enabled(self) -> bool:
        return self.public_base_url.startswith("https://") and bool(self.webhook_secret)

    @property
    def webapp_url(self) -> str:
        return f"{self.public_base_url.rstrip('/')}/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
