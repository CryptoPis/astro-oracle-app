"""Daily AI call counters for the Groq quota, shown in /diag. No user data: only the day, the feature (the
response schema), the language and how many raw model requests were made (retries and model fallbacks included).

Stored as one AICache row per UTC day (kind "ai_stats", key "2026-10-20"), so the numbers survive restarts of
the free Render instance. Writing is best-effort: a failed write never breaks a reading.
"""
import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone

log = logging.getLogger(__name__)
KIND = "ai_stats"

_pending: Counter = Counter()
_locks: dict[int, asyncio.Lock] = {}   # one per event loop (a Lock is bound to the loop that first uses it)
_tasks: set[asyncio.Task] = set()


def _day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def count(name: str, n: int = 1) -> None:
    """Counts in memory; flush() adds the counts to today's row."""
    _pending[name] += n


async def flush() -> None:
    if not _pending:
        return
    lock = _locks.setdefault(id(asyncio.get_running_loop()), asyncio.Lock())
    async with lock:
        todo = dict(_pending)
        _pending.clear()
        try:
            from sqlalchemy import select

            from app.db import SessionLocal
            from app.models import AICache
            from app.services.economy import _insert
            day = _day()
            async with SessionLocal() as session:
                row = await session.scalar(select(AICache).where(AICache.kind == KIND, AICache.cache_key == day))
                if row is None:
                    await session.execute(_insert(session)(AICache).values(kind=KIND, cache_key=day, payload=todo)
                                          .on_conflict_do_nothing(index_elements=["kind", "cache_key"]))
                else:
                    merged = Counter(row.payload or {})
                    merged.update(todo)
                    row.payload = dict(merged)   # a new dict, so SQLAlchemy sees the JSON change
                await session.commit()
        except Exception as e:   # the counters are a diagnostic, never a reason to fail a request
            log.warning("ai_stats flush failed: %s", type(e).__name__)
            _pending.update(todo)


async def today() -> dict:
    """Today's counters (stored + not yet flushed)."""
    out: Counter = Counter()
    try:
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import AICache
        async with SessionLocal() as session:
            row = await session.scalar(select(AICache.payload).where(AICache.kind == KIND, AICache.cache_key == _day()))
        out.update(row or {})
    except Exception:
        pass
    out.update(_pending)
    return dict(out)


def format_line(counters: dict) -> str:
    calls = sum(v for k, v in counters.items() if k.startswith("call:"))
    requests = counters.get("requests", 0)
    top = sorted(((k[5:], v) for k, v in counters.items() if k.startswith("call:")), key=lambda x: -x[1])[:6]
    return f"{calls} AI calls, {requests} model requests" + (" · " + ", ".join(f"{k} {v}" for k, v in top) if top else "")


class CountingProvider:
    """Wraps the real provider: one 'call:<schema>.<lang>' per answer; GroqProvider counts raw 'requests'."""

    def __init__(self, inner):
        self.inner = inner

    async def complete_json(self, system, user, schema, **kw):
        from app.ai.provider import lang_of
        count(f"call:{schema.__name__}.{lang_of(system)}")
        try:
            return await self.inner.complete_json(system, user, schema, **kw)
        finally:   # in the background: the reader never waits for the counters
            task = asyncio.create_task(flush())
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)

    async def list_models(self) -> list[str]:
        return await self.inner.list_models()
