import os
from functools import lru_cache
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def normalize_database_url(url: str) -> tuple[str, dict]:
    """Turns a Neon/Render style URL into an async SQLAlchemy URL plus asyncpg connect args.

    postgresql://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
      -> postgresql+asyncpg://u:p@ep-x-pooler.../neondb  +  {"ssl": "require", ...}
    asyncpg does not understand libpq's sslmode/channel_binding, so they become connect args.
    """
    url = url.strip()
    if not url.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
        return url, {}
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    host = parts.hostname or ""
    connect_args: dict = {}
    if sslmode in ("require", "verify-ca", "verify-full") or host.endswith(".neon.tech"):
        connect_args["ssl"] = "require"
    if "-pooler" in host or "pgbouncer" in host:
        # PgBouncer in transaction mode cannot keep prepared statements between transactions.
        connect_args["statement_cache_size"] = 0
        query["prepared_statement_cache_size"] = "0"
    return urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), "")), connect_args


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "production"
    log_level: str = "INFO"

    bot_token: str
    bot_username: str = "astrogm2026bot"
    mini_app_short_name: str = "app"
    admin_ids: Annotated[list[int], NoDecode] = []
    # Public HTTPS address. On Render it is filled automatically from RENDER_EXTERNAL_URL.
    public_base_url: str = ""
    webhook_secret: str = ""
    cron_secret: str = ""
    init_data_max_age: int = 86400

    database_url: str = "sqlite+aiosqlite:///./data/astro.db"

    ai_provider: str = "groq"
    groq_api_key: str = ""
    # Groq retired the Llama 3.x / Llama 4 models on the free tier in 2026; these are the current ones.
    groq_text_model: str = "openai/gpt-oss-120b"
    groq_fast_model: str = "openai/gpt-oss-20b"
    groq_vision_model: str = "qwen/qwen3.8-27b"
    # Tried in order if a model is retired or unavailable (comma-separated).
    groq_fallback_models: Annotated[list[str], NoDecode] = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
    ai_timeout_seconds: float = 40
    # Per-language Groq model (empty = the text/fast models above). Picked with scripts/ai_benchmark.py.
    groq_model_ka: str = ""
    groq_model_ru: str = ""
    # Per-language provider: "" or groq = the default; anthropic | openai | gemini = a paid provider for that
    # language only (needs its key below; the adapters are stubs until implemented, see app/ai/provider.py).
    ai_provider_ka: str = ""
    ai_provider_ru: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    cors_origins: Annotated[list[str], NoDecode] = []

    bot_enabled: bool = True          # false = API only (tests, frontend dev)
    # internal = APScheduler inside the app; external = an outside cron (cron-job.org) calls /cron/morning;
    # off = no morning push.
    morning_push_mode: str = "internal"
    morning_push_hour: int = 9
    scheduler_timezone: str = "Asia/Tbilisi"

    dev_auth_bypass: bool = False
    dev_user_id: int = 1

    @field_validator("admin_ids", "cors_origins", "groq_fallback_models", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    @model_validator(mode="after")
    def _defaults(self):
        if not self.public_base_url:
            self.public_base_url = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8000")
        self.public_base_url = self.public_base_url.rstrip("/")
        return self

    @property
    def is_dev(self) -> bool:
        return self.env.lower() == "development"

    @property
    def webhook_enabled(self) -> bool:
        return self.public_base_url.startswith("https://") and bool(self.webhook_secret)

    @property
    def webapp_url(self) -> str:
        return f"{self.public_base_url}/"

    @property
    def db(self) -> tuple[str, dict]:
        return normalize_database_url(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
