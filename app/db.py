from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()
DB_URL, _connect_args = settings.db
IS_SQLITE = DB_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_async_engine(DB_URL, connect_args={"timeout": 30})

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")   # readers don't block during writes
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
else:
    if _connect_args.get("statement_cache_size") == 0:   # behind PgBouncer (Neon "-pooler" host)
        _connect_args["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid4()}__"
    engine = create_async_engine(
        DB_URL,
        connect_args=_connect_args,
        pool_size=5, max_overflow=5,
        pool_pre_ping=True,   # Neon suspends idle compute and drops connections; test before use
        pool_recycle=240,
    )

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_models() -> None:
    """Creates missing tables (safe to run on every start). Schema changes later: use Alembic."""
    from app import models  # noqa: F401  (registers tables on Base.metadata)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ping() -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
