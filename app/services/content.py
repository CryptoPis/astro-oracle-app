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
# Quota: a personal text is generated only when someone opens it (never by the morning cron), and it is cached by
# what the text depends on (sign, period, language and the signature of the top transits), not by the person.
# Two people whose top transits match share one AI call.
def _notes(natal: dict) -> str:
    if not natal["time_known"]:
        return "Birth time unknown: houses and ascendant are not used; the natal Moon position is approximate."
    if not natal["place_known"]:
        return "Birth city unknown: houses and ascendant are not used."
    return ""


def personal_key(tr: dict, natal: dict, sign: str, period: str, day: date, lang: str) -> str:
    accuracy = "t" if natal["time_known"] else "n"
    accuracy += "p" if natal["place_known"] else "-"
    return f"{sign}:{period}:{astro.period_key(period, day)}:{lang}:{accuracy}:{transits.signature(tr)}"


def personal_plan(natal: dict, sign: str, period: str, day: date, lang: str) -> dict:
    """The transits of the period and the shared cache key of their reading (computed once per request)."""
    tr = transits.transits_for(natal, period, day)
    return {"natal": natal, "sign": sign, "period": period, "day": day, "lang": lang, "tr": tr,
            "key": personal_key(tr, natal, sign, period, day, lang)}


def _chips(tr: dict, lang: str) -> dict[str, list[str]]:
    """T-id -> 'why' chips: the aspect label, plus the planet's essential dignity when it has one."""
    out = {}
    for it in tr["transits"]:
        chips = [transits.label(it, lang)]
        if (d := transits.dignity_label(it, lang)) is not None:
            chips.append(d)
        out[it["id"]] = chips
    return out


async def get_personal_horoscope(session: AsyncSession, plan: dict) -> tuple[dict, bool]:
    natal, sign, period, day, lang, tr = (plan[k] for k in ("natal", "sign", "period", "day", "lang", "tr"))
    pkey = astro.period_key(period, day)
    chips = _chips(tr, lang)
    moon = astro.moon_phase("en")
    moon_desc = f"{moon['name']}, Moon in {tr['moon_sign']}" if period == "day" else moon["name"]

    async def gen():
        lines = [transits.describe_for_ai(it, lang) for it in tr["transits"]] or ["(no close aspects this period: describe a calm, steady time)"]
        system, user = P.personal_horoscope_prompt(lang, sign, period, pkey, moon_desc, lines, tr["retrograde"], _notes(natal))
        result = (await get_ai().complete_json(system, user, P.HoroscopeAI, max_tokens=1200)).model_dump()
        for sec in result["sections"]:   # ids -> exact, localized labels computed here, never written by the AI
            sec["why"] = list(dict.fromkeys(c for i in sec.get("why", []) for c in chips.get(i, [])))
        result["retrograde"] = [transits.retro_label(p, lang) for p in tr["retrograde"]]
        return result

    payload, hit = await cached_ai(session, "horoscope_personal", plan["key"], gen)
    # per person (not cached): the exact dates of this chart's transits
    transit_list = [{"label": chips[it["id"]][0], "nature": it["nature"], "date": it.get("date"),
                     "dignity": transits.dignity_label(it, lang)} for it in tr["transits"]]
    return {"period_key": pkey, **payload, "transits": transit_list}, hit


def energy_plan(natal: dict, lang: str, day: date) -> dict | None:
    tr = transits.transits_for(natal, "day", day, limit=1)
    if not tr["transits"]:
        return None
    return {"tr": tr, "lang": lang, "day": day, "key": f"{day.isoformat()}:{lang}:{transits.signature(tr)}"}


async def get_personal_energy(session: AsyncSession, plan: dict) -> dict:
    """Daily energy from the person's strongest transit of the day (shared by everyone with the same one)."""
    tr, lang, day = plan["tr"], plan["lang"], plan["day"]
    it = tr["transits"][0]
    moon = astro.moon_phase("en")

    async def gen():
        system, user = P.personal_energy_prompt(lang, transits.describe_for_ai(it, lang), f"{moon['name']}, in {tr['moon_sign']}", day.isoformat())
        return (await get_ai().complete_json(system, user, P.EnergyAI, fast=True, max_tokens=300)).model_dump()

    payload, _ = await cached_ai(session, "energy_personal", plan["key"], gen)
    return {**payload, "why": transits.label(it, lang)}


async def is_cached(session: AsyncSession, kind: str, key: str) -> bool:
    return await session.scalar(select(AICache.id).where(AICache.kind == kind, AICache.cache_key == key)) is not None
