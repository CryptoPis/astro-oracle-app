from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import astro
from app.models import Referral, User
from app.security import InitData
from app.services import economy

SUPPORTED_LANGS = ("ka", "ru", "en")


def guess_lang(code: str | None) -> str:
    code = (code or "").lower()[:2]
    return code if code in SUPPORTED_LANGS else "en"


def parse_ref(start_param: str | None) -> int | None:
    """Accepts 'ref_123' (Mini App startapp) or a bare '123' (legacy bot /start links)."""
    if not start_param:
        return None
    raw = start_param[4:] if start_param.startswith("ref_") else start_param
    return int(raw) if raw.isdigit() else None


async def apply_referral(session: AsyncSession, invitee: User, inviter_id: int | None) -> bool:
    if not inviter_id or inviter_id == invitee.telegram_id or invitee.referred_by:
        return False
    inviter = await session.get(User, inviter_id)
    if inviter is None:
        return False
    invitee.referred_by = inviter_id
    session.add(Referral(invitee_id=invitee.telegram_id, inviter_id=inviter_id))
    await session.flush()
    await economy.credit(session, inviter_id, economy.REFERRAL_REWARD_INVITER, "referral_inviter")
    await economy.credit(session, invitee.telegram_id, economy.REFERRAL_REWARD_NEW, "referral_new")
    return True


async def get_or_create(session: AsyncSession, tg_user: dict) -> tuple[User, bool]:
    uid = int(tg_user["id"])
    user = await session.get(User, uid)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user is None:
        user = User(telegram_id=uid, lang=guess_lang(tg_user.get("language_code")), astro_coins=0,
                    streak=0, last_seen_at=now)
        session.add(user)
        await session.flush()
        await economy.credit(session, uid, economy.WELCOME_BONUS, "welcome")
        is_new = True
    else:
        is_new = False
        user.last_seen_at = now
    user.username = tg_user.get("username") or user.username
    user.first_name = tg_user.get("first_name") or user.first_name
    user.photo_url = tg_user.get("photo_url") or user.photo_url
    user.is_premium = bool(tg_user.get("is_premium", False))
    return user, is_new


async def upsert_user(session: AsyncSession, init: InitData, with_referral: bool = True):
    user, is_new = await get_or_create(session, init.user)
    referred = False
    if is_new and with_referral:
        referred = await apply_referral(session, user, parse_ref(init.start_param))
    await session.flush()
    await session.refresh(user)
    return user, {"is_new": is_new, "referral_applied": referred}


def serialize_profile(user: User) -> dict:
    s = get_settings()
    sign = astro.zodiac_sign(user.birth_date) if user.birth_date else None
    return {
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "photo_url": user.photo_url,
        "lang": user.lang,
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "birth_time": user.birth_time.strftime("%H:%M") if user.birth_time else None,
        "birth_city": user.birth_city,
        "sign": sign and {"id": sign, "name": astro.SIGN_NAMES[sign][user.lang],
                          "emoji": astro.SIGN_EMOJI[sign], "element": astro.SIGN_ELEMENT[sign]},
        "life_path": astro.life_path_number(user.birth_date) if user.birth_date else None,
        "coins": user.astro_coins,
        "streak": economy.effective_streak(user),
        "daily_reward_available": economy.daily_available(user),
        "needs_onboarding": user.birth_date is None,
        "referral_link": f"https://t.me/{s.bot_username}/{s.mini_app_short_name}?startapp=ref_{user.telegram_id}",
    }
