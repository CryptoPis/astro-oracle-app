"""Download the public-domain Rider–Waite (1909) Major Arcana scans once and
self-host them in static/img/tarot/<slug>.jpg.

    python -m scripts.fetch_tarot_images

Uses Wikimedia Commons' Special:FilePath redirect, which resolves a file
*name* to its real URL. The legacy code guessed the hashed /x/xy/ paths, and
some of those were wrong. Any card that fails is reported so you can add it
by hand.
"""
from pathlib import Path

import httpx

from app.core.tarot import DECK

OUT = Path(__file__).resolve().parent.parent / "static" / "img" / "tarot"
BASE = "https://commons.wikimedia.org/wiki/Special:FilePath/"
HEADERS = {"User-Agent": "AstroOracleBot/2.0 (asset fetch; contact via Telegram @astrogm2026bot)"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        for card in DECK:
            dest = OUT / f"{card.slug}.jpg"
            if dest.exists():
                continue
            r = client.get(BASE + card.commons_file, params={"width": 500})
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                dest.write_bytes(r.content)
                print("✓", card.name)
            else:
                failed.append(card.name)
                print("✗", card.name, r.status_code)
    if failed:
        print("\nFailed:", ", ".join(failed))


if __name__ == "__main__":
    main()
