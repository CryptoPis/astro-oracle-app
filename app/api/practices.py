"""Numerology and the magic sphere."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import prompts as P
from app.ai.provider import get_ai
from app.core import astro
from app.core import sphere as sphere_core
from app.db import get_session
from app.models import User
from app.security import current_user
from app.services import economy
from app.services.content import cached_ai

router = APIRouter(prefix="/api", tags=["practices"])


@router.get("/numerology")
async def numerology(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if not user.birth_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, {"code": "needs_birth_date"})
    lp = astro.life_path_number(user.birth_date)
    year = economy.today_utc().year
    py = astro.personal_year_number(user.birth_date, year)
    lang = user.lang

    async def gen_lp():
        system, prompt = P.numerology_prompt(lang, lp)
        return (await get_ai().complete_json(system, prompt, P.NumerologyAI, max_tokens=900)).model_dump()

    async def gen_py():
        system, prompt = P.personal_year_prompt(lang, py, year)
        return (await get_ai().complete_json(system, prompt, P.PersonalYearAI, fast=True, max_tokens=400)).model_dump()

    # Shared by everyone with the same number and language: 12 numbers x 3 languages in total.
    reading, _ = await cached_ai(session, "numerology", f"lp:{lp}:{lang}", gen_lp)
    year_reading, _ = await cached_ai(session, "pyear", f"py:{py}:{year}:{lang}", gen_py)
    reward = await economy.grant_action_reward(session, user.telegram_id, "numerology")
    await session.commit()
    return {"life_path": lp, "is_master": lp in (11, 22, 33), "personal_year": py, "year": year,
            "reading": reading, "year_reading": year_reading, "reward": reward}




class SphereRequest(BaseModel):
    question: str | None = Field(None, max_length=200)


@router.post("/sphere")
async def sphere(body: SphereRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if not await economy.bump_counter(session, user.telegram_id, "use:sphere", 50):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, {"code": "daily_quota"})
    result = sphere_core.ask(user.lang, body.question)   # hand-written answer + topic advice, no AI call
    reward = await economy.grant_action_reward(session, user.telegram_id, "sphere")
    await session.commit()
    return {**result, "question": body.question, "reward": reward}
