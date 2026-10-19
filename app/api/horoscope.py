import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import Period, resolve_sign, sign_info
from sqlalchemy import select

from app.core import astro, transits
from app.db import get_session
from app.models import AICache, Reading, User
from app.security import current_user
from app.services import content, economy

router = APIRouter(prefix="/api", tags=["astrology"])
log = logging.getLogger(__name__)


async def natal_of(session: AsyncSession, user: User) -> dict:
    """The user's natal chart; the city is geocoded once (kundli does the same) and never blocks the reading."""
    from app.api.kundli import resolve_place
    place = None
    if user.birth_city:
        try:
            place = await resolve_place(session, user)
        except Exception:
            log.warning("geocoding failed; reading without houses")
    return transits.natal_chart(user.birth_date, user.birth_time, place)


@router.get("/horoscope")
async def horoscope(period: Period = "day", sign: str | None = Query(None, description="e.g. Leo; defaults to the user's sign"),
                    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    sign = resolve_sign(user, sign)
    day = economy.today_utc()
    own = user.birth_date is not None and astro.zodiac_sign(user.birth_date) == sign

    # Own sign + birth date: a personal reading from the real transits to this person's natal chart, cached per
    # natal chart and period. If the daily AI cap is reached for a new one, fall back to the shared sign text.
    personal = False
    if own:
        natal = await natal_of(session, user)
        cached = await session.scalar(select(AICache.id).where(
            AICache.kind == "horoscope_personal", AICache.cache_key == content.personal_key(natal, period, day, user.lang)))
        if cached is not None or await economy.consume_ai_quota(session, user.telegram_id, "horoscope"):
            await session.commit()
            data, from_cache = await content.get_personal_horoscope(session, natal, sign, period, user.lang, day)
            personal = True
    if not personal:
        data, from_cache = await content.get_horoscope(session, sign, period, user.lang, day)

    # Coins only for reading your OWN sign, once per period.
    reward = None
    if own:
        reward = await economy.grant_action_reward(session, user.telegram_id, f"horoscope_{period}")
        if reward["coins_earned"]:
            session.add(Reading(user_id=user.telegram_id, kind="horoscope", variant=period, day=day,
                                payload={"sign": sign, **data}))
        await session.commit()

    return {"sign": sign_info(sign, user.lang), "period": period, "is_own_sign": own, "personal": personal,
            "horoscope": data, "moon": astro.moon_phase(user.lang), "reward": reward}


@router.get("/daily/energy")
async def daily_energy(sign: str | None = None, user: User = Depends(current_user),
                       session: AsyncSession = Depends(get_session)):
    """Home screen: energy quote, affirmation, lucky numbers, moon."""
    day = economy.today_utc()
    try:
        s = resolve_sign(user, sign)
    except Exception:
        s = None  # no birth date yet: generic message for everyone
    energy = None
    if user.birth_date and not sign:   # personal: from the strongest transit of the day
        energy = await content.get_personal_energy(session, await natal_of(session, user), user.lang, day)
    personal = energy is not None
    if energy is None:
        energy = await content.get_daily_energy(session, s or "all signs", user.lang, day)
    return {"date": day.isoformat(), "sign": s and sign_info(s, user.lang), "personal": personal, "why": energy.get("why"),
            "moon": astro.moon_phase(user.lang), "lucky_numbers": astro.lucky_numbers(user.telegram_id, day),
            **energy}


@router.get("/zodiac")
async def zodiac_list(user: User = Depends(current_user)):
    """Localized data for the 12-sign selector."""
    own = astro.zodiac_sign(user.birth_date) if user.birth_date else None
    return {"signs": [{**sign_info(s, user.lang), "is_own": s == own} for s in astro.SIGNS]}
