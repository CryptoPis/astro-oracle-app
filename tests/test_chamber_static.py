"""Oracle chamber (static/chamber/): the default UI stays light, texts are complete in ka/en/ru, three.js is pinned."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "static" / "chamber"
GEORGIAN = re.compile(r"[ა-ჿ]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def lang_blocks(src: str) -> dict[str, dict[str, str]]:
    """Reads the TX = { ka: {...}, en: {...}, ru: {...} } object of a chamber module."""
    out = {}
    for lang in ("ka", "en", "ru"):
        m = re.search(rf"\n  {lang}: \{{(.*?)\n  \}},", src, re.S)
        assert m, f"no {lang} block"
        out[lang] = dict(re.findall(r'(\w+): "((?:[^"\\]|\\.)*)"', m.group(1)))
    return out


def test_chamber_texts_have_the_same_keys_in_three_languages():
    for name in ("stations.js",) + tuple(p.name for p in CH.glob("*.js") if "const TX = {" in p.read_text(encoding="utf-8") and p.name != "stations.js"):
        tx = lang_blocks((CH / name).read_text(encoding="utf-8"))
        assert set(tx["ka"]) == set(tx["en"]) == set(tx["ru"]), name
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
