from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import prompts as P
from app.ai.provider import AIError, get_ai
from app.api.common import TarotDrawRequest, quota_exceeded
from app.config import get_settings
from app.core import astro, tarot
from app.db import get_session
from app.models import Reading, User
from app.security import current_user
from app.services import economy

router = APIRouter(prefix="/api/tarot", tags=["tarot"])


def _reading_out(r: Reading, repeated: bool, reward: dict | None) -> dict:
    return {"reading_id": r.id, "spread": r.variant, "date": r.day.isoformat(), "question": r.question,
            "repeated": repeated, "reward": reward, **r.payload}


async def _todays_daily(session: AsyncSession, user_id: int) -> Reading | None:
    return await session.scalar(select(Reading).where(
        Reading.user_id == user_id, Reading.kind == "tarot", Reading.variant == "daily",
        Reading.day == economy.today_utc()).order_by(Reading.id.desc()).limit(1))


@router.post("/draw")
async def draw(body: TarotDrawRequest, user: User = Depends(current_user),
               session: AsyncSession = Depends(get_session)):
    uid = user.telegram_id
    positions = tarot.SPREADS[body.spread]

    # "daily" = card of the day. Reopening returns the same card instead of a new draw.
    if body.spread == "daily":
        if existing := await _todays_daily(session, uid):
            return _reading_out(existing, repeated=True, reward=None)
        if not await economy.bump_counter(session, uid, "tarot_daily", 1):
            raise HTTPException(status.HTTP_409_CONFLICT, {"code": "in_progress"})
    elif not await economy.consume_ai_quota(session, uid, "tarot"):
        raise quota_exceeded("tarot")
    await session.commit()  # release the write lock before the slow AI call

    drawn = [c.to_dict(get_settings().public_base_url.rstrip("/"), rev) for c, rev in tarot.draw(len(positions))]
    sign = astro.zodiac_sign(user.birth_date) if user.birth_date else None
    system, prompt = P.tarot_prompt(user.lang, body.spread, drawn, positions, sign, body.question)
    try:
        ai = await get_ai().complete_json(system, prompt, P.TarotAI, max_tokens=700 + 300 * len(positions))
    except AIError:
        await economy.release_counter(session, uid, "tarot_daily" if body.spread == "daily" else "ai:tarot")
        await session.commit()
        raise

    cards = []
    for i, (pos, card) in enumerate(zip(positions, drawn)):
        a = ai.cards[i] if i < len(ai.cards) else ai.cards[-1]
        cards.append({**card, "position": pos, "title": a.card_title, "keywords": a.keywords,
                      "interpretation": a.interpretation})

    reading = Reading(user_id=uid, kind="tarot", variant=body.spread, day=economy.today_utc(),
                      question=body.question,
                      payload={"cards": cards, "synthesis": ai.synthesis, "advice": ai.advice})
    session.add(reading)
    await session.flush()
    reward = await economy.grant_action_reward(session, uid, "tarot")
    await session.commit()
    return _reading_out(reading, repeated=False, reward=reward)


@router.get("/history")
async def history(limit: int = Query(20, le=100), offset: int = 0, user: User = Depends(current_user),
                  session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(Reading).where(Reading.user_id == user.telegram_id, Reading.kind == "tarot")
                                  .order_by(Reading.id.desc()).limit(limit).offset(offset))).all()
    return {"items": [_reading_out(r, repeated=False, reward=None) for r in rows]}
