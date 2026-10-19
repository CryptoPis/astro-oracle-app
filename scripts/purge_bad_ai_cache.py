"""Finds AI texts that fail the quality guard and removes them from the shared cache.

    python -m scripts.purge_bad_ai_cache --dry-run    # report only
    python -m scripts.purge_bad_ai_cache --apply      # delete failing ai_cache rows

- ai_cache (shared horoscopes, energy, numerology, moon rituals, compatibility, kundli): failing rows are
  deleted with --apply; the next request generates them again (now behind the guard).
- readings (users' tarot/horoscope history): only counted, never changed. Old tarot titles are fixed at
  display time anyway (the app shows card names from its own dictionary).
The language of each row is detected from its letters (Georgian / Cyrillic). Output shows ids, kinds and
reasons only, never the texts. Uses DATABASE_URL like the app (on Render: run it in the service Shell).
"""
import argparse
import asyncio
import re
from collections import Counter

from sqlalchemy import delete, select

from app.ai.quality import payload_problems, strings_in
from app.db import SessionLocal
from app.models import AICache, Reading

_KA = re.compile(r"[Ⴀ-ჿᲐ-Ჿ]")
_RU = re.compile(r"[Ѐ-ӿ]")


def detect_lang(payload) -> str | None:
    text = " ".join(strings_in(payload))
    ka, ru = len(_KA.findall(text)), len(_RU.findall(text))
    if max(ka, ru) < 20:
        return None
    return "ka" if ka >= ru else "ru"


async def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="report only")
    g.add_argument("--apply", action="store_true", help="delete failing ai_cache rows")
    a = ap.parse_args()
    async with SessionLocal() as session:
        bad_ids, by_kind, reasons, scanned = [], Counter(), Counter(), 0
        for row in (await session.execute(select(AICache.id, AICache.kind, AICache.payload))).all():
            scanned += 1
            lang = detect_lang(row.payload)
            if lang and (found := payload_problems(row.payload, lang)):
                bad_ids.append(row.id)
                by_kind[f"{row.kind}/{lang}"] += 1
                reasons.update(r.split(" ")[0] + " " + r.split(" ")[1] if " " in r else r for r in found)
        print(f"ai_cache: scanned {scanned}, failing {len(bad_ids)}")
        for k, n in sorted(by_kind.items()):
            print(f"  {k}: {n}")
        for r, n in reasons.most_common():
            print(f"  reason '{r}': {n}")

        hist, hist_bad = 0, 0
        for (payload,) in (await session.execute(select(Reading.payload))).all():
            hist += 1
            lang = detect_lang(payload)
            hist_bad += bool(lang and payload_problems(payload, lang))
        print(f"readings (history, not changed): scanned {hist}, failing {hist_bad}")

        if a.apply and bad_ids:
            await session.execute(delete(AICache).where(AICache.id.in_(bad_ids)))
            await session.commit()
            print(f"deleted {len(bad_ids)} ai_cache rows")
        elif a.dry_run:
            print("dry run: nothing deleted")


if __name__ == "__main__":
    asyncio.run(main())
