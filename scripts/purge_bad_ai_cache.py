"""Finds AI texts that fail the quality guard and removes them from the shared cache.

    python -m scripts.purge_bad_ai_cache --dry-run    # report only
    python -m scripts.purge_bad_ai_cache --apply      # delete failing ai_cache rows

- ai_cache (shared horoscopes, energy, numerology, moon rituals, compatibility, kundli): failing rows are
  deleted with --apply; the next request generates them again (now behind the guard).
- readings (users' tarot/horoscope history): only counted, never changed. Old tarot titles are fixed at
  display time anyway (the app shows card names from its own dictionary).
The language of each row is detected from its letters (Georgian / Cyrillic). Output shows ids, kinds and
reasons only, never the texts. Uses DATABASE_URL like the app. On Render's free plan (no Shell) send the
admin bot command /purge_cache (dry run) and /purge_cache apply instead.
"""
import argparse
import asyncio

from sqlalchemy import select

from app.ai.quality import payload_problems
from app.db import SessionLocal
from app.models import Reading
from app.services.cache_quality import detect_lang, format_scan, scan_bad_cache


async def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="report only")
    g.add_argument("--apply", action="store_true", help="delete failing ai_cache rows")
    a = ap.parse_args()
    async with SessionLocal() as session:
        print(format_scan(await scan_bad_cache(session, apply=a.apply), applied=a.apply))
        hist, hist_bad = 0, 0
        for (payload,) in (await session.execute(select(Reading.payload))).all():
            hist += 1
            lang = detect_lang(payload)
            hist_bad += bool(lang and payload_problems(payload, lang))
        print(f"readings (history, not changed): scanned {hist}, failing {hist_bad}")


if __name__ == "__main__":
    asyncio.run(main())
