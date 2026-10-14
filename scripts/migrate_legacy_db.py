"""Import users and balances from the legacy bot database (astro_bot.db).

    python -m scripts.migrate_legacy_db /path/to/astro_bot.db

Safe to re-run: existing users in the new DB are skipped. Balances are
imported with one 'legacy_import' ledger entry each, so the new ledger stays
auditable. sol_address is intentionally NOT migrated (off-chain points only
for now). Keep a backup of the old file.
"""
import asyncio
import sqlite3
import sys
from datetime import date, datetime

from app.db import SessionLocal, init_models
from app.models import CoinTransaction, User


EMPTY = ("---", "NULL", "None", "null", "")


def parse_legacy_date(raw) -> date | None:
    if not raw or str(raw).strip() in EMPTY:
        return None
    try:
        return datetime.strptime(str(raw).split(" ")[0], "%d.%m.%Y").date()
    except ValueError:
        return None


async def main(path: str) -> None:
    await init_models()
    src = sqlite3.connect(path)
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT * FROM users").fetchall()
    imported = skipped = bad_dates = 0
    async with SessionLocal() as s:
        for r in rows:
            keys = r.keys()
            uid = int(r["telegram_id"])
            if await s.get(User, uid):
                skipped += 1
                continue
            bdate = parse_legacy_date(r["birth_date"])
            if r["birth_date"] and str(r["birth_date"]).strip() not in EMPTY and not bdate:
                bad_dates += 1
            coins = int(r["astro_coins"] or 0) if "astro_coins" in keys else 0
            lang = r["lang"] if r["lang"] in ("ka", "ru", "en") else "en"
            s.add(User(telegram_id=uid, lang=lang, birth_date=bdate, birth_city=r["city"] or None,
                       astro_coins=coins, streak=0))
            await s.flush()
            if coins:
                s.add(CoinTransaction(user_id=uid, amount=coins, reason="legacy_import"))
            imported += 1
        await s.commit()
    print(f"imported={imported} skipped_existing={skipped} unparseable_birth_dates={bad_dates}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.migrate_legacy_db /path/to/astro_bot.db")
    asyncio.run(main(sys.argv[1]))
