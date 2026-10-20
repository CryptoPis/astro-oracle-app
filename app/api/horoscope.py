import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import AIError
from app.api.common import Period, resolve_sign, sign_info
from app.astro_kb.context import day_correspondence
from app.core import astro, transits
from app.db import get_session
from app.models import Reading, User
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

    # Own sign + birth date: a personal reading from the real transits to this person's natal chart, cached by its
    # transit signature (shared with anyone whose top transits match). A new text costs one slot of the daily AI
    # cap; if the cap is reached or the AI fails, the shared sign text is shown instead.
    personal = False
    if own:
        plan = content.personal_plan(await natal_of(session, user), sign, period, day, user.lang)
        cached = await content.is_cached(session, "horoscope_personal", plan["key"])
        allowed = cached or await economy.consume_ai_quota(session, user.telegram_id, "horoscope")
        await session.commit()   # also when the cap was hit: never keep a write transaction open during an AI call
        if allowed:
            try:
                data, from_cache = await content.get_personal_horoscope(session, plan)
                personal = True
            except AIError:
                log.warning("personal horoscope: AI unavailable, using the sign text")
                if not cached:
                    await economy.release_counter(session, user.telegram_id, "ai:horoscope")
                    await session.commit()
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
        plan = content.energy_plan(await natal_of(session, user), user.lang, day)
        allowed = plan is not None and (await content.is_cached(session, "energy_personal", plan["key"])
                                         or await economy.consume_ai_quota(session, user.telegram_id, "energy"))
        await session.commit()
        if allowed:
            try:
                energy = await content.get_personal_energy(session, plan)
            except AIError:
                log.warning("personal energy: AI unavailable, using the generic text")
    personal = energy is not None
    if energy is None:
        energy = await content.get_daily_energy(session, s or "all signs", user.lang, day)
    return {"date": day.isoformat(), "sign": s and sign_info(s, user.lang), "personal": personal, "why": energy.get("why"),
            "moon": astro.moon_phase(user.lang), "lucky_numbers": astro.lucky_numbers(user.telegram_id, day),
            "day": day_correspondence(day, user.lang), **energy}


@router.get("/zodiac")
async def zodiac_list(user: User = Depends(current_user)):
    """Localized data for the 12-sign selector."""
    own = astro.zodiac_sign(user.birth_date) if user.birth_date else None
    return {"signs": [{**sign_info(s, user.lang), "is_own": s == own} for s in astro.SIGNS]}
