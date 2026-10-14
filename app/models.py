"""Database models.

Changes vs. the legacy bot schema (astro_bot.db):
- birth_date is a real DATE (legacy stored "15.08.1990" as text).
- birth_time / lat / lon / tz added, ready for real natal charts later.
- Every coin movement goes through coin_transactions (legacy bypassed it for
  referrals, tasks and cashouts).
- Referrals are recorded (legacy paid out but never stored who invited whom).
- New tables: readings (tarot + horoscope history), dream_journal, ai_cache.
"""
from datetime import date, datetime, time

from sqlalchemy import (JSON, BigInteger, Date, DateTime, ForeignKey, Integer, String, Text,
                        Time, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    photo_url: Mapped[str | None] = mapped_column(String(512))
    is_premium: Mapped[bool] = mapped_column(default=False)

    lang: Mapped[str] = mapped_column(String(2), default="en")
    birth_date: Mapped[date | None] = mapped_column(Date)
    birth_time: Mapped[time | None] = mapped_column(Time)
    birth_city: Mapped[str | None] = mapped_column(String(128))
    birth_lat: Mapped[float | None]
    birth_lon: Mapped[float | None]
    birth_tz: Mapped[str | None] = mapped_column(String(64))

    astro_coins: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_daily_claim: Mapped[date | None] = mapped_column(Date)

    referred_by: Mapped[int | None] = mapped_column(BigInteger)
    is_blocked: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    amount: Mapped[int]
    reason: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ActionCounter(Base):
    """Per-user, per-day counters, used for coin limits ("reward:tarot") and
    AI cost quotas ("ai:dream")."""
    __tablename__ = "action_counters"
    __table_args__ = (UniqueConstraint("user_id", "action", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    action: Mapped[str] = mapped_column(String(32))
    day: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, default=0)


class AICache(Base):
    """AI output shared by all users with identical inputs, e.g. today's Leo
    horoscope in Georgian. The legacy bot cached per *user*, paying for one
    AI call per user per day for the same text."""
    __tablename__ = "ai_cache"
    __table_args__ = (UniqueConstraint("kind", "cache_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    cache_key: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Reading(Base):
    """History of tarot draws and horoscope views."""
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))            # tarot | horoscope
    variant: Mapped[str | None] = mapped_column(String(32))  # daily | three | day | week | month
    day: Mapped[date] = mapped_column(Date, index=True)
    question: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DreamEntry(Base):
    __tablename__ = "dream_journal"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    dream_text: Mapped[str] = mapped_column(Text)
    analysis: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Referral(Base):
    __tablename__ = "referrals"

    invitee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), primary_key=True)
    inviter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
