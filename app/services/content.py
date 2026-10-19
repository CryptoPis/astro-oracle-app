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
from app.ai import quality
from app.ai.provider import get_ai
from app.core import astro, transits
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
        token = quality.fallback_used.set(False)
        try:
            payload = await generate()
            used_fallback = quality.fallback_used.get()
        finally:
            quality.fallback_used.reset(token)
        if used_fallback:   # a safe placeholder text: show it now, ask the AI again next time
            _locks.pop(f"{kind}:{key}", None)
            return payload, False
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


# ───────── personal readings from real transits (app/core/transits.py) ─────────
def personal_key(natal: dict, period: str, day: date, lang: str) -> str:
    """One reading per natal chart, period and language (not per sign)."""
    return f"{natal['fingerprint']}:{period}:{astro.period_key(period, day)}:{lang}"


def _notes(natal: dict) -> str:
    if not natal["time_known"]:
        return "Birth time unknown: houses and ascendant are not used; the natal Moon position is approximate."
    if not natal["place_known"]:
        return "Birth city unknown: houses and ascendant are not used."
    return ""


async def get_personal_horoscope(session: AsyncSession, natal: dict, sign: str, period: str, lang: str, day: date) -> tuple[dict, bool]:
    pkey = astro.period_key(period, day)
    tr = transits.transits_for(natal, period, day)
    labels = {it["id"]: transits.label(it, lang) for it in tr["transits"]}
    moon = astro.moon_phase("en")
    moon_desc = f"{moon['name']}, Moon in {tr['moon_sign']}" if period == "day" else moon["name"]

    async def gen():
        lines = [transits.describe_for_ai(it, lang) for it in tr["transits"]] or ["(no close aspects this period: describe a calm, steady time)"]
        system, user = P.personal_horoscope_prompt(lang, sign, period, pkey, moon_desc, lines, tr["retrograde"], _notes(natal))
        result = (await get_ai().complete_json(system, user, P.HoroscopeAI, max_tokens=1200)).model_dump()
        for sec in result["sections"]:   # ids -> exact, localized labels computed here, never written by the AI
            sec["why"] = [labels[i] for i in sec.get("why", []) if i in labels]
        result["transits"] = [{"label": labels[it["id"]], "nature": it["nature"], "date": it.get("date")} for it in tr["transits"]]
        result["retrograde"] = [transits.retro_label(p, lang) for p in tr["retrograde"]]
        return result

    payload, hit = await cached_ai(session, "horoscope_personal", personal_key(natal, period, day, lang), gen)
    return {"period_key": pkey, **payload}, hit


async def get_personal_energy(session: AsyncSession, natal: dict, lang: str, day: date) -> dict | None:
    """Daily energy from the person's strongest transit of the day; None if there is none (generic is used)."""
    tr = transits.transits_for(natal, "day", day, limit=1)
    if not tr["transits"]:
        return None
    it = tr["transits"][0]
    moon = astro.moon_phase("en")

    async def gen():
        system, user = P.personal_energy_prompt(lang, transits.describe_for_ai(it, lang), f"{moon['name']}, in {tr['moon_sign']}", day.isoformat())
        out = (await get_ai().complete_json(system, user, P.EnergyAI, fast=True, max_tokens=300)).model_dump()
        out["why"] = transits.label(it, lang)
        return out

    payload, _ = await cached_ai(session, "energy_personal", f"{natal['fingerprint']}:{day.isoformat()}:{lang}", gen)
    return payload
