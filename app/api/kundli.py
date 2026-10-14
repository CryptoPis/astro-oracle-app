import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import prompts as P
from app.ai.provider import get_ai
from app.api.common import quota_exceeded
from app.core.chart import Place, chart_summary, compute_chart
from app.db import get_session
from app.models import AICache, User
from app.security import current_user
from app.services import economy
from app.services.content import cached_ai
from app.services.geo import geocode

router = APIRouter(prefix="/api", tags=["kundli"])


async def resolve_place(session: AsyncSession, user: User) -> Place | None:
    if not user.birth_city:
        return None
    if user.birth_lat is None:
        place = await geocode(session, user.birth_city)
        if place is None:
            return None
        user.birth_lat, user.birth_lon, user.birth_tz = place.lat, place.lon, place.tz
        await session.commit()
        return place
    return Place(user.birth_city, user.birth_lat, user.birth_lon, user.birth_tz or "UTC")


@router.get("/kundli")
async def kundli(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if not user.birth_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"code": "needs_birth_date"})
    place = await resolve_place(session, user)
    chart = compute_chart(user.birth_date, user.birth_time, place)
    summary = chart_summary(chart)
    key = hashlib.sha256(f"{user.lang}|{summary}".encode()).hexdigest()[:40]

    cached = await session.scalar(select(AICache.id).where(AICache.kind == "kundli", AICache.cache_key == key))
    if cached is None:
        if not await economy.consume_ai_quota(session, user.telegram_id, "kundli"):
            raise quota_exceeded("kundli")
        await session.commit()

    async def gen():
        system, prompt = P.kundli_prompt(user.lang, summary)
        return (await get_ai().complete_json(system, prompt, P.KundliAI, max_tokens=1000)).model_dump()

    reading, _ = await cached_ai(session, "kundli", key, gen)
    reward = await economy.grant_action_reward(session, user.telegram_id, "kundli")
    await session.commit()
    return {"chart": chart, "reading": reading, "city_not_found": bool(user.birth_city and place is None), "reward": reward}
