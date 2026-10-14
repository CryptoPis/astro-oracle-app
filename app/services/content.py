"""AI content shared between users: horoscopes and daily energy.

The cache key is (sign, period, period_key, lang). That gives at most 12
signs x 3 languages x 3 periods of AI calls per day, no matter how many users
there are. The legacy bot made one call per user.
"""
import asyncio
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import prompts as P
from app.ai.provider import get_ai
from app.core import astro
from app.models import AICache
from app.services.economy import _insert

_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def cached_ai(session: AsyncSession, kind: str, key: str, generate) -> tuple[dict, bool]:
    """Returns (payload, from_cache). Concurrent requests for one key share a single AI call."""
    q = select(AICache.payload).where(AICache.kind == kind, AICache.cache_key == key)
    if (hit := await session.scalar(q)) is not None:
        return hit, True
    async with _locks[f"{kind}:{key}"]:
        if (hit := await session.scalar(q)) is not None:
            return hit, True
        payload = await generate()
        insert = _insert(session)
        await session.execute(insert(AICache).values(kind=kind, cache_key=key, payload=payload)
                              .on_conflict_do_nothing(index_elements=["kind", "cache_key"]))
        await session.commit()
    _locks.pop(f"{kind}:{key}", None)
    return payload, False


async def get_horoscope(session: AsyncSession, sign: str, period: str, lang: str, day: date) -> tuple[dict, bool]:
    pkey = astro.period_key(period, day)
    moon = astro.moon_phase("en")

    async def gen():
        system, user = P.horoscope_prompt(lang, sign, period, pkey, moon["name"])
        result = await get_ai().complete_json(system, user, P.HoroscopeAI)
        return result.model_dump()

    payload, hit = await cached_ai(session, "horoscope", f"{sign}:{period}:{pkey}:{lang}", gen)
    return {"period_key": pkey, **payload}, hit


async def get_daily_energy(session: AsyncSession, sign: str, lang: str, day: date) -> dict:
    moon = astro.moon_phase("en")

    async def gen():
        system, user = P.energy_prompt(lang, sign, moon["name"], day.isoformat())
        return (await get_ai().complete_json(system, user, P.EnergyAI, fast=True, max_tokens=300)).model_dump()

    payload, _ = await cached_ai(session, "energy", f"{sign}:{day.isoformat()}:{lang}", gen)
    return payload
