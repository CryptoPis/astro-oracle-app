"""Builds the Mini App page from frontend/app.html.

    python -m scripts.build_frontend

Outputs:
  static/index.html   served by FastAPI at "/" (loads the Telegram SDK)
  dist/preview.html   standalone browser preview with images embedded (runs in demo mode)
"""
import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "app.html"

HEAD = """<!doctype html>
<html lang="ka">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
"""


def demo_kb() -> str:
    """The knowledge base the browser demo needs (the real app gets these from the API, so the page served to
    Telegram stays small): tarot meanings, the weekday correspondences (index = JS getDay) and the sphere lore."""
    import json
    from datetime import date, timedelta

    sys.path.insert(0, str(ROOT))
    from app.astro_kb import context, load

    langs = ("ka", "en", "ru")
    tarot = {slug: {side: {lg: {k: v[lg][k] for k in ("meaning", "challenging", "advice")} for lg in langs}
                    for side, v in ((s, card[s]) for s in ("upright", "reversed"))} for slug, card in load("tarot").items()}
    sunday = date(2026, 10, 18)
    days = [{lg: context.day_correspondence(sunday + timedelta(days=i), lg) for lg in langs} for i in range(7)]
    sphere = {tone: {lg: context.sphere_lore(tone, lg) for lg in langs} for tone in ("yes", "wait", "no")}
    return json.dumps({"tarot": tarot, "days": days, "sphere": sphere}, ensure_ascii=False, separators=(",", ":"))


CHAMBER_DIRS = ("static/chamber", "static/vendor")


def chamber_version() -> str:
    """Content hash of the oracle chamber's files: stamped into its import URL so phones never run stale modules."""
    import hashlib
    h = hashlib.sha256()
    for d in CHAMBER_DIRS:
        for f in sorted((ROOT / d).rglob("*")):
            if f.is_file():
                h.update(f.relative_to(ROOT).as_posix().encode()); h.update(f.read_bytes())
    return h.hexdigest()[:10]


def copy_chamber_for_preview() -> None:
    """dist/preview.html loads the chamber from dist/static/... (the real app serves it from /static/)."""
    import shutil
    for d in CHAMBER_DIRS:
        dest = ROOT / "dist" / d
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(ROOT / d, dest)


def chamber_kb() -> None:
    """static/chamber/kb.json: the knowledge-base texts the chamber shows itself (moon-phase folklore after Harley),
    generated from app/astro_kb so the KB stays the single source. Written before the version hash is taken."""
    import json
    data = json.loads((ROOT / "app" / "astro_kb" / "moon.json").read_text(encoding="utf-8"))
    moon = {k: {lg: v[lg] for lg in ("ka", "en", "ru")} for k, v in data.items() if not k.startswith("_")}
    out = json.dumps({"moon": moon}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    path = ROOT / "static" / "chamber" / "kb.json"
    if not path.exists() or path.read_text(encoding="utf-8") != out:
        path.write_text(out, encoding="utf-8")


def main() -> None:
    chamber_kb()
    src = SRC.read_text(encoding="utf-8").replace("__CHV__", chamber_version())
    head, body = src.split("<!--BODY-->", 1)

    (ROOT / "static" / "index.html").write_text(f"{HEAD}{head}</head>\n<body>{body}</body>\n</html>\n", encoding="utf-8")

    def inline(m: re.Match) -> str:
        path = ROOT / m.group(1)
        return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode()

    if "--no-preview" in sys.argv:   # production build (Render): only the page the app serves
        print("built static/index.html")
        return
    preview = re.sub(r"(static/img/[\w/.-]+\.webp)", inline, src).replace("<!--BODY-->", "")
    preview = preview.replace("/*DEMO_KB*/null", demo_kb())
    # without a charset a page served over HTTP is read as Windows-1252 (Georgian and ♌ become mojibake)
    preview = ('<!doctype html>\n<meta charset="utf-8">\n'
               '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + preview)
    (ROOT / "dist").mkdir(exist_ok=True)
    (ROOT / "dist" / "preview.html").write_text(preview, encoding="utf-8")
    copy_chamber_for_preview()
    print("built static/index.html and dist/preview.html")


if __name__ == "__main__":
    main()
