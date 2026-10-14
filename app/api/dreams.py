from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import prompts as P
from app.ai.provider import AIError, get_ai
from app.api.common import DreamRequest, quota_exceeded
from app.core import astro
from app.db import get_session
from app.models import DreamEntry, User
from app.security import current_user
from app.services import economy

router = APIRouter(prefix="/api/dreams", tags=["dreams"])


def _out(e: DreamEntry) -> dict:
    return {"id": e.id, "text": e.dream_text, "created_at": e.created_at.isoformat() + "Z", **e.analysis}


@router.post("/analyze")
async def analyze(body: DreamRequest, user: User = Depends(current_user),
                  session: AsyncSession = Depends(get_session)):
    uid = user.telegram_id
    if not await economy.consume_ai_quota(session, uid, "dream"):
        raise quota_exceeded("dream")
    await session.commit()

    sign = astro.zodiac_sign(user.birth_date) if user.birth_date else None
    system, prompt = P.dream_prompt(user.lang, body.text.strip(), sign, astro.moon_phase("en")["name"])
    try:
        ai = await get_ai().complete_json(system, prompt, P.DreamAI, max_tokens=900)
    except AIError:
        await economy.release_counter(session, uid, "ai:dream")
        await session.commit()
        raise

    analysis = ai.model_dump()
    entry_id = None
    if body.save:
        entry = DreamEntry(user_id=uid, dream_text=body.text.strip(), analysis=analysis)
        session.add(entry)
        await session.flush()
        entry_id = entry.id
    reward = await economy.grant_action_reward(session, uid, "dream")
    await session.commit()
    return {"id": entry_id, "saved": body.save, "analysis": analysis, "reward": reward}


@router.get("")
async def journal(limit: int = Query(20, le=100), offset: int = 0, user: User = Depends(current_user),
                  session: AsyncSession = Depends(get_session)):
    base = select(DreamEntry).where(DreamEntry.user_id == user.telegram_id)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = (await session.scalars(base.order_by(DreamEntry.id.desc()).limit(limit).offset(offset))).all()
    return {"total": total, "items": [_out(e) for e in rows]}


@router.delete("/{entry_id}")
async def remove(entry_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    res = await session.execute(delete(DreamEntry).where(DreamEntry.id == entry_id,
                                                         DreamEntry.user_id == user.telegram_id))
    if res.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    await session.commit()
    return {"ok": True}
