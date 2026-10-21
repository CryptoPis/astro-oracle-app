"""Oracle chamber (static/chamber/): the default UI stays light, texts are complete in ka/en/ru, three.js is pinned."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "static" / "chamber"
GEORGIAN = re.compile(r"[ა-ჿ]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def _object_after(src: str, start: int) -> str:
    """The text inside the {...} object that opens at or after `start` (braces inside strings are ignored)."""
    i = src.index("{", start)
    depth, j, quote = 0, i, None
    while j < len(src):
        ch = src[j]
        if quote:
            if ch == "\\":
                j += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[i + 1:j]
        j += 1
    raise AssertionError("unbalanced object")


def lang_blocks(src: str) -> dict[str, dict[str, str]]:
    """Reads the TX = { ka: {...}, en: {...}, ru: {...} } object of a chamber module."""
    tx = _object_after(src, src.index("const TX = {"))
    out = {}
    for lang in ("ka", "en", "ru"):
        m = re.search(r"(?:^|\n|,)\s*" + lang + r": \{", tx)
        assert m, f"no {lang} block"
        out[lang] = dict(re.findall(r'(\w+): "((?:[^"\\]|\\.)*)"', _object_after(tx, m.end() - 1)))
    return out


def test_chamber_texts_have_the_same_keys_in_three_languages():
    names = [p.name for p in CH.glob("*.js") if "const TX = {" in p.read_text(encoding="utf-8")]
    assert "stations.js" in names and len(names) >= 4
    for name in names:
        tx = lang_blocks((CH / name).read_text(encoding="utf-8"))
        assert tx["ka"] and set(tx["ka"]) == set(tx["en"]) == set(tx["ru"]), name
        for k, v in tx["ka"].items():
            assert GEORGIAN.search(v), f"{name} ka.{k} is not Georgian"
        for k, v in tx["ru"].items():
            assert CYRILLIC.search(v), f"{name} ru.{k} is not Russian"


def test_default_ui_does_not_load_the_chamber_or_three():
    page = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "three-0.160" not in page and "vendor/three" not in page and "THREE." not in page   # only the chamber module imports the 3D engine
    assert re.search(r'CHAMBER_URL = "\./static/chamber/main\.js\?v=[0-9a-f]{10}"', page), "the build stamps a content hash"
    src = (ROOT / "frontend" / "app.html").read_text(encoding="utf-8")
    assert 'import(CHAMBER_URL)' in src and 'UI === "chamber"' in src


def test_three_is_vendored_and_pinned():
    assert (ROOT / "static" / "vendor" / "three-0.160.0.module.min.js").stat().st_size > 500_000
    assert "three-0.160.0.module.min.js" in (CH / "main.js").read_text(encoding="utf-8")
    assert (ROOT / "static" / "vendor" / "three-LICENSE.txt").exists()


def test_chamber_images_are_small_webp_copies_with_credits():
    """Runtime images only (no originals): WebP, at most 1024 px, a 512 px copy for Medium, NASA credited."""
    from PIL import Image
    img = CH / "img"
    files = sorted(img.iterdir())
    assert files and all(f.suffix == ".webp" for f in files), [f.name for f in files if f.suffix != ".webp"]
    for f in files:
        with Image.open(f) as im:
            assert im.format == "WEBP" and max(im.size) <= 1024, (f.name, im.format, im.size)
    names = {f.name for f in files}
    for base in ("stone", "stone_n", "floor", "floor_n", "velvet", "velvet_n", "rug", "rug_n", "window", "dome", "moon"):
        assert {f"{base}_1024.webp", f"{base}_512.webp"} <= names, base
    credits = (ROOT / "docs" / "CREDITS_GRAPHICS.md").read_text(encoding="utf-8")
    assert "svs.gsfc.nasa.gov/4720" in credits and "NASA's Scientific Visualization Studio" in credits


def test_chamber_loads_its_images_lazily():
    """The room starts with procedural stand-ins; the WebP set is fetched only after the first frames."""
    full = (CH / "full.js").read_text(encoding="utf-8")
    assert "loadTextures()" in full and "frames === 2" in full and "frames === 50" in full
    assert ".webp" not in (CH / "room.js").read_text(encoding="utf-8")   # only tex.js builds image URLs
