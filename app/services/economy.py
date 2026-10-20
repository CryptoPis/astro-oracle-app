"""$AST off-chain points ledger, ported from legacy main.py with integrity fixes.

Fixes vs. the legacy bot:
- Every balance change writes a coin_transactions row.
- Counters and daily claims use single conditional UPDATEs, so double taps
  and parallel requests can't claim twice.
- Rewards are granted only AFTER the AI call succeeds (legacy paid first).
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActionCounter, CoinTransaction, User

WELCOME_BONUS = 250
DAILY_LOGIN_REWARD = 50
STREAK_REWARDS = {3: 100, 7: 300, 30: 1000}
REFERRAL_REWARD_INVITER = 250
REFERRAL_REWARD_NEW = 100

# coins per action / how many times per day it pays (same values as legacy)
COIN_REWARDS = {"horoscope_day": 20, "horoscope_week": 20, "horoscope_month": 20,
                "tarot": 50, "dream": 50, "advisor": 50, "aura": 60, "coffee": 50,
                "compatibility": 100, "kundli": 100, "moon": 70, "numerology": 35, "sphere": 25}
REWARD_LIMITS = {"horoscope_day": 1, "horoscope_week": 1, "horoscope_month": 1,
                 "tarot": 3, "dream": 3, "advisor": 3, "aura": 2, "coffee": 3,
                 "compatibility": 1, "kundli": 1, "moon": 1, "numerology": 1, "sphere": 5}

# Hard caps on paid AI calls per user per day (cost control, separate from coin rewards)
AI_DAILY_CAPS = {"tarot": 10, "dream": 10, "advisor": 15, "horoscope": 40, "vision": 8, "compat": 10, "kundli": 5,
                "energy": 3}


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _insert(session: AsyncSession):
    if session.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert


async def credit(session: AsyncSession, user_id: int, amount: int, reason: str) -> None:
    if amount == 0:
        return
    await session.execute(update(User).where(User.telegram_id == user_id)
                          .values(astro_coins=User.astro_coins + amount))
    session.add(CoinTransaction(user_id=user_id, amount=amount, reason=reason))


async def bump_counter(session: AsyncSession, user_id: int, action: str, cap: int) -> bool:
    """Atomically increments today's counter if it's below cap. Returns True if allowed."""
    day = today_utc()
    insert = _insert(session)
    await session.execute(insert(ActionCounter)
                          .values(user_id=user_id, action=action, day=day, count=0)
                          .on_conflict_do_nothing(index_elements=["user_id", "action", "day"]))
    res = await session.execute(
        update(ActionCounter)
        .where(ActionCounter.user_id == user_id, ActionCounter.action == action,
               ActionCounter.day == day, ActionCounter.count < cap)
        .values(count=ActionCounter.count + 1))
    return res.rowcount == 1


async def release_counter(session: AsyncSession, user_id: int, action: str) -> None:
    """Gives a quota slot back, e.g. when the AI call failed."""
    await session.execute(
        update(ActionCounter)
        .where(ActionCounter.user_id == user_id, ActionCounter.action == action,
               ActionCounter.day == today_utc(), ActionCounter.count > 0)
        .values(count=ActionCounter.count - 1))


async def counter_value(session: AsyncSession, user_id: int, action: str) -> int:
    res = await session.scalar(select(ActionCounter.count).where(
        ActionCounter.user_id == user_id, ActionCounter.action == action,
        ActionCounter.day == today_utc()))
    return res or 0


async def consume_ai_quota(session: AsyncSession, user_id: int, kind: str) -> bool:
    return await bump_counter(session, user_id, f"ai:{kind}", AI_DAILY_CAPS[kind])


async def grant_action_reward(session: AsyncSession, user_id: int, action: str) -> dict:
    """Pays the action's coin reward if today's limit isn't reached. Returns a summary for the UI."""
    limit = REWARD_LIMITS.get(action, 0)
    amount = COIN_REWARDS.get(action, 0)
    granted = 0
    if limit and await bump_counter(session, user_id, f"reward:{action}", limit):
        await credit(session, user_id, amount, f"mine_{action}")
        granted = amount
    used = await counter_value(session, user_id, f"reward:{action}")
    balance = await session.scalar(select(User.astro_coins).where(User.telegram_id == user_id))
    return {"coins_earned": granted, "used_today": used, "daily_limit": limit, "balance": balance}


# Soft streak: one missed day per ISO week is forgiven automatically (a "freeze"). The use is recorded as an
# action_counters row (action "streak_freeze", day = Monday of the week), so no table changes are needed.
FREEZE_ACTION = "streak_freeze"


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


async def freeze_used_this_week(session: AsyncSession, user_id: int, today: date | None = None) -> bool:
    used = await session.scalar(select(ActionCounter.count).where(
        ActionCounter.user_id == user_id, ActionCounter.action == FREEZE_ACTION,
        ActionCounter.day == week_start(today or today_utc())))
    return bool(used)


async def claim_daily(session: AsyncSession, user_id: int) -> dict | None:
    """Returns None if already claimed today. Streak continues if the last claim was yesterday, or the day
    before yesterday when this week's freeze is still unused (the freeze is then spent)."""
    today = today_utc()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    last = await session.scalar(select(User.last_daily_claim).where(User.telegram_id == user_id))
    use_freeze = last == two_days_ago and not await freeze_used_this_week(session, user_id, today)
    continues = [yesterday, two_days_ago] if use_freeze else [yesterday]
    res = await session.execute(
        update(User)
        .where(User.telegram_id == user_id,
               or_(User.last_daily_claim.is_(None), User.last_daily_claim < today))
        .values(streak=case((User.last_daily_claim.in_(continues), User.streak + 1), else_=1),
                last_daily_claim=today))
    if res.rowcount != 1:
        return None
    if use_freeze:
        insert = _insert(session)
        await session.execute(insert(ActionCounter)
                              .values(user_id=user_id, action=FREEZE_ACTION, day=week_start(today), count=1)
                              .on_conflict_do_nothing(index_elements=["user_id", "action", "day"]))
    streak = await session.scalar(select(User.streak).where(User.telegram_id == user_id))
    streak_bonus = STREAK_REWARDS.get(streak, 0)
    await credit(session, user_id, DAILY_LOGIN_REWARD, "daily_bonus")
    if streak_bonus:
        await credit(session, user_id, streak_bonus, f"streak_{streak}")
    balance = await session.scalar(select(User.astro_coins).where(User.telegram_id == user_id))
    return {"coins_earned": DAILY_LOGIN_REWARD + streak_bonus, "base": DAILY_LOGIN_REWARD,
            "streak_bonus": streak_bonus, "streak": streak, "balance": balance, "freeze_used": use_freeze}


def daily_available(user: User) -> bool:
    return user.last_daily_claim is None or user.last_daily_claim < today_utc()


async def streak_state(session: AsyncSession, user: User) -> dict:
    """Streak as the UI should show it, with the weekly freeze taken into account.
    freeze.ready: this week's freeze is unused; freeze.saving: a day was missed and the next claim will be saved."""
    today = today_utc()
    ready = not await freeze_used_this_week(session, user.telegram_id, today)
    saving = ready and user.last_daily_claim == today - timedelta(days=2)
    streak = user.streak if saving else effective_streak(user)
    return {"streak": streak, "streak_freeze": {"ready": ready, "saving": saving}}


async def practices_this_week(session: AsyncSession, user_id: int) -> int:
    """How many rewarded practices the user did in the last 7 days (from the reward counters)."""
    total = await session.scalar(select(func.coalesce(func.sum(ActionCounter.count), 0)).where(
        ActionCounter.user_id == user_id, ActionCounter.action.like("reward:%"),
        ActionCounter.day >= today_utc() - timedelta(days=6)))
    return int(total or 0)


def effective_streak(user: User) -> int:
    """The stored streak is stale if the user skipped a day. Show 0 in that case."""
    if user.last_daily_claim and user.last_daily_claim >= today_utc() - timedelta(days=1):
        return user.streak
    return 0
