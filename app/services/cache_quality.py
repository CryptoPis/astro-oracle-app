"""Finds shared AI texts (ai_cache) that fail the quality guard; optionally deletes them.

Used by the admin bot command /purge_cache and by scripts/purge_bad_ai_cache.py. User history (readings) is
never touched here. The language of a row is detected from its letters (Georgian / Cyrillic), so it also
works for keys that do not contain the language (e.g. kundli's hashed keys).
"""
import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.quality import payload_problems, strings_in
from app.models import AICache

_KA = re.compile(r"[Ⴀ-ჿᲐ-Ჿ]")
_RU = re.compile(r"[Ѐ-ӿ]")


def detect_lang(payload) -> str | None:
    text = " ".join(strings_in(payload))
    ka, ru = len(_KA.findall(text)), len(_RU.findall(text))
    if max(ka, ru) < 20:
        return None
    return "ka" if ka >= ru else "ru"


@dataclass
class CacheScan:
    scanned: int = 0
    bad_ids: list[int] = field(default_factory=list)
    by_kind: Counter = field(default_factory=Counter)     # "horoscope/ka" -> rows
    reasons: Counter = field(default_factory=Counter)     # "word repeated" -> rows
    deleted: int = 0


async def scan_bad_cache(session: AsyncSession, apply: bool = False) -> CacheScan:
    out = CacheScan()
    for row in (await session.execute(select(AICache.id, AICache.kind, AICache.payload))).all():
        out.scanned += 1
        lang = detect_lang(row.payload)
        if lang and (found := payload_problems(row.payload, lang)):
            out.bad_ids.append(row.id)
            out.by_kind[f"{row.kind}/{lang}"] += 1
            out.reasons.update({" ".join(r.split(" ")[:2]) for r in found})
    if apply and out.bad_ids:
        res = await session.execute(delete(AICache).where(AICache.id.in_(out.bad_ids)))
        await session.commit()
        out.deleted = res.rowcount or 0
    return out


async def scan_old_versions(session: AsyncSession, apply: bool = False) -> CacheScan:
    """Shared AI texts written before the current CACHE_VERSION (they can no longer be read: their keys lack
    the version prefix). Only ai_cache rows; geocoding and the AI call counters are kept."""
    from sqlalchemy import func

    from app.services.content import CACHE_VERSION, UNVERSIONED
    old = AICache.kind.not_in(UNVERSIONED) & ~AICache.cache_key.startswith(f"{CACHE_VERSION}:")
    out = CacheScan(scanned=await session.scalar(select(func.count()).select_from(AICache)) or 0)
    for kind, n in (await session.execute(select(AICache.kind, func.count()).where(old).group_by(AICache.kind))).all():
        out.by_kind[kind] = n
    out.bad_ids = [i for (i,) in (await session.execute(select(AICache.id).where(old))).all()]
    if apply and out.bad_ids:
        res = await session.execute(delete(AICache).where(old))
        await session.commit()
        out.deleted = res.rowcount or 0
    return out


def format_old(scan: CacheScan, applied: bool) -> str:
    from app.services.content import CACHE_VERSION
    lines = [f"ai_cache: {scan.scanned} rows, {len(scan.bad_ids)} written before {CACHE_VERSION} (no longer used)"]
    lines += [f"• {k}: {n}" for k, n in sorted(scan.by_kind.items())]
    if applied:
        lines.append(f"Deleted {scan.deleted} rows. New texts come from the knowledge base.")
    elif scan.bad_ids:
        lines.append("Dry run: nothing deleted. Send /purge_cache old apply to delete them.")
    else:
        lines.append("Nothing to delete.")
    lines.append("User readings and history are never changed.")
    return "\n".join(lines)


def format_scan(scan: CacheScan, applied: bool) -> str:
    lines = [f"ai_cache: {scan.scanned} rows scanned, {len(scan.bad_ids)} fail the quality guard"]
    lines += [f"• {k}: {n}" for k, n in sorted(scan.by_kind.items())]
    lines += [f"  reason “{r}”: {n}" for r, n in scan.reasons.most_common(5)]
    if applied:
        lines.append(f"Deleted {scan.deleted} rows. They are generated again on the next request.")
    elif scan.bad_ids:
        lines.append("Dry run: nothing deleted. Send /purge_cache apply to delete exactly these rows.")
    else:
        lines.append("Nothing to delete.")
    lines.append("User readings and history are never changed.")
    return "\n".join(lines)
