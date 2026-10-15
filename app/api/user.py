from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import ProfileUpdate
from app.core import astro
from app.db import get_session
from app.models import User
from app.security import InitData, current_user, require_init_data
from app.services import economy
from app.services.users import serialize_profile, upsert_user

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
user_router = APIRouter(prefix="/api/user", tags=["user"])


@auth_router.post("/verify")
async def verify(init: InitData = Depends(require_init_data),
                 session: AsyncSession = Depends(get_session)):
    """Call once on app start. Validates initData, creates or updates the user,
    and applies a referral from `startapp=ref_<id>` on first launch."""
    user, flags = await upsert_user(session, init, with_referral=True)
    await session.commit()
    if user.is_blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account blocked")
    return {"ok": True, **flags, "user": {**serialize_profile(user), **await economy.streak_state(session, user)},
            "moon": astro.moon_phase(user.lang),
            "economy": {"daily_reward": economy.DAILY_LOGIN_REWARD,
                        "streak_rewards": economy.STREAK_REWARDS,
                        "action_rewards": economy.COIN_REWARDS,
                        "action_limits": economy.REWARD_LIMITS}}


@user_router.get("/profile")
async def get_profile(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return {"user": {**serialize_profile(user), **await economy.streak_state(session, user)}}


@user_router.patch("/profile")
async def update_profile(body: ProfileUpdate, user: User = Depends(current_user),
                         session: AsyncSession = Depends(get_session)):
    changes = body.model_dump(exclude_unset=True)
    if "birth_city" in changes and changes["birth_city"] != user.birth_city:
        user.birth_lat = user.birth_lon = user.birth_tz = None  # re-geocoded on the next chart request
    for field_name, value in changes.items():
        setattr(user, field_name, value)
    await session.commit()
    await session.refresh(user)
    return {"user": serialize_profile(user)}


@user_router.post("/daily-reward")
async def daily_reward(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    result = await economy.claim_daily(session, user.telegram_id)
    if result is None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            {"code": "already_claimed", "message": "Daily reward already claimed today."})
    await session.commit()
    return {"ok": True, "reward": result}
