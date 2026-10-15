"""Live sky: where the seven classical planets stand right now (tropical zodiac, as in the horoscopes),
the moon phase, the planet of the day and retrogrades. Computed with astronomy-engine, no paid API.

Positions change slowly, so one computation per UTC hour is shared by every user (in-memory cache).
The "week" block is per user: streak, weekly freeze and practices done in the last 7 days.
"""
from datetime import datetime, timezone

import astronomy as A
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import astro
from app.core.chart import _tropical
from app.db import get_session
from app.models import User
from app.security import current_user
from app.services import economy

router = APIRouter(prefix="/api", tags=["sky"])

PLANETS = [("sun", A.Body.Sun), ("moon", A.Body.Moon), ("mercury", A.Body.Mercury), ("venus", A.Body.Venus),
           ("mars", A.Body.Mars), ("jupiter", A.Body.Jupiter), ("saturn", A.Body.Saturn)]
# traditional day rulers, Monday first (Moon-day, Mars-day, Mercury-day, Jupiter-day, Venus-day, Saturn-day, Sun-day)
DAY_RULER = ["moon", "mars", "mercury", "jupiter", "venus", "saturn", "sun"]

_cache: dict[str, dict] = {}


def sky_at(now: datetime) -> dict:
    t = A.Time.Make(now.year, now.month, now.day, now.hour, now.minute, now.second)
    t_next = t.AddDays(1)
    planets = []
    for pid, body in PLANETS:
        lon = _tropical(body, t)
        retro = False
        if pid not in ("sun", "moon"):
            retro = ((_tropical(body, t_next) - lon) + 540) % 360 - 180 < 0
        s = int(lon // 30)
        planets.append({"id": pid, "lon": round(lon, 2), "sign": astro.SIGNS[s], "degree": round(lon % 30, 1), "retro": retro})
    phase = astro.moon_phase("en", now)
    angle = A.MoonPhase(t)   # 0 new, 90 first quarter, 180 full, 270 last quarter
    return {"at": now.replace(minute=0, second=0, microsecond=0).isoformat(), "planets": planets,
            "moon": {"code": phase["code"], "illumination": phase["illumination"], "age_days": phase["age_days"],
                     "phase": round(angle / 360, 4)},
            "planet_of_day": DAY_RULER[now.weekday()],
            "retrograde": [p["id"] for p in planets if p["retro"]]}


def cached_sky(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    key = now.strftime("%Y-%m-%dT%H")
    if key not in _cache:
        _cache.clear()   # only the current hour is ever needed
        _cache[key] = sky_at(now)
    return _cache[key]


@router.get("/sky")
async def sky(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    state = await economy.streak_state(session, user)
    return {**cached_sky(),
            "week": {"practices": await economy.practices_this_week(session, user.telegram_id),
                     "streak": state["streak"], "freeze_ready": state["streak_freeze"]["ready"]}}
