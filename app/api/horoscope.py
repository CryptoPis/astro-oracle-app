from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import Period, resolve_sign, sign_info
from app.core import astro
from app.db import get_session
from app.models import Reading, User
from app.security import current_user
from app.services import content, economy

router = APIRouter(prefix="/api", tags=["astrology"])


@router.get("/horoscope")
async def horoscope(period: Period = "day", sign: str | None = Query(None, description="e.g. Leo; defaults to the user's sign"),
                    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    sign = resolve_sign(user, sign)
    day = economy.today_utc()
    data, from_cache = await content.get_horoscope(session, sign, period, user.lang, day)

    # Coins only for reading your OWN sign, once per period.
    reward = None
    own = user.birth_date is not None and astro.zodiac_sign(user.birth_date) == sign
    if own:
        reward = await economy.grant_action_reward(session, user.telegram_id, f"horoscope_{period}")
        if reward["coins_earned"]:
            session.add(Reading(user_id=user.telegram_id, kind="horoscope", variant=period, day=day,
                                payload={"sign": sign, **data}))
        await session.commit()

    return {"sign": sign_info(sign, user.lang), "period": period, "is_own_sign": own,
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
    energy = await content.get_daily_energy(session, s or "all signs", user.lang, day)
    return {"date": day.isoformat(), "sign": s and sign_info(s, user.lang),
            "moon": astro.moon_phase(user.lang), "lucky_numbers": astro.lucky_numbers(user.telegram_id, day),
            **energy}


@router.get("/zodiac")
async def zodiac_list(user: User = Depends(current_user)):
    """Localized data for the 12-sign selector."""
    own = astro.zodiac_sign(user.birth_date) if user.birth_date else None
    return {"signs": [{**sign_info(s, user.lang), "is_own": s == own} for s in astro.SIGNS]}
