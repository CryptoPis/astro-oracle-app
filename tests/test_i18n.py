"""Interface texts in ka/en/ru: no key may be missing in any language, every key the UI asks for must exist, the Georgian
and Russian texts must really be translated, and the boot picks one language for the app and the server's texts.

The app's table (I18N in frontend/app.html) and pickLang are read by Node (the same JavaScript the browser runs);
the chamber's own tables (TX in static/chamber/*.js) are parsed here.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "frontend" / "app.html"
CH = ROOT / "static" / "chamber"
LANGS = ("ka", "en", "ru")
GEORGIAN = re.compile(r"[ა-ჿ]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
NODE = shutil.which("node")


def node(js: str):
    if not NODE:
        pytest.skip("node is not installed")
    out = subprocess.run([NODE, "--input-type=module"], input=js, capture_output=True, text=True, timeout=30, encoding="utf-8")   # stdin: the table is too long for a command line
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def app_src() -> str:
    return APP.read_text(encoding="utf-8")


def i18n() -> dict:
    src = app_src()
    i = src.index("const I18N = {")
    j = src.index("\n};", i)
    return node(f"const I18N = {src[i + 13:j + 2]};\nconsole.log(JSON.stringify(I18N));")


def chamber_files():
    return sorted(CH.glob("*.js"))


def test_app_texts_have_the_same_keys_in_three_languages():
    tx = i18n()
    keys = set().union(*(tx[l] for l in LANGS))
    missing = {l: sorted(keys - set(tx[l])) for l in LANGS}
    assert not any(missing.values()), missing
    empty = [f"{l}.{k}" for l in LANGS for k, v in tx[l].items() if not str(v).strip()]
    assert not empty, empty


# texts that stay the same in every language (brand, currency, symbols)
SAME_EVERYWHERE = re.compile(r"^[\s\d$%+·×/:.,!?()\-–—…'\"«»„“”№#&*]*(Astro Oracle|\$AST|AST|D\d+|[A-Z]{1,3})?[\s\d$%+·×/:.,!?()\-–—…]*$")


def test_georgian_and_russian_texts_are_really_translated():
    tx = i18n()
    bad = []
    for k, en in tx["en"].items():
        en = str(en)
        if not re.search(r"[A-Za-z]{2}", en) or SAME_EVERYWHERE.match(en):
            continue
        if not GEORGIAN.search(str(tx["ka"][k])):
            bad.append(f"ka.{k} = {tx['ka'][k]!r}")
        if not CYRILLIC.search(str(tx["ru"][k])):
            bad.append(f"ru.{k} = {tx['ru'][k]!r}")
    assert not bad, bad


def used_app_keys():
    """(key, file) for every literal key the UI asks the app's table for: t("k"), B.t("k"), data-i18n="k"."""
    out = set()
    for f in [APP, *chamber_files()]:
        s = f.read_text(encoding="utf-8")
        for m in re.finditer(r'(?<![\w.])(?:B\.)?t\(\s*"(\w+)"\s*[,)]', s):
            out.add((m.group(1), f.name))
        for m in re.finditer(r'data-i18n(?:-ph|-aria)?="(\w+)"', s):
            out.add((m.group(1), f.name))
    return out


def test_every_key_the_ui_uses_exists():
    tx = i18n()
    chamber_tx = lang_blocks(CH / "stations.js")   # main.js's T() looks here first, then in the app's table
    missing = sorted(f"{k} ({f})" for k, f in used_app_keys() if k not in tx["en"] and not (f == "main.js" and k in chamber_tx["en"]))
    assert not missing, missing
    assert len(used_app_keys()) > 150   # the scan really finds the calls


def test_dynamic_key_families_are_complete():
    """Keys built at run time (t("nat_" + x), t("why_" + w)...) exist for every member in all three languages."""
    tx = i18n()
    families = {"nat_": ("harmonious", "challenging", "blend")}
    for prefix, members in families.items():
        for m in members:
            for l in LANGS:
                assert f"{prefix}{m}" in tx[l], f"{l}.{prefix}{m}"
    st = lang_blocks(CH / "stations.js")
    for why in ("forced", "reduced", "desktop", "weak", "slowBefore", "noWebgl", "slow", "lost", "error"):
        for l in LANGS:
            assert f"why_{why}" in st[l], f"stations.js {l}.why_{why}"


def _object_after(src: str, start: int) -> str:
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


def lang_blocks(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tx = _object_after(src, src.index("const TX = {"))
    out = {}
    for lang in LANGS:
        m = re.search(r"(?:^|\n|,)\s*" + lang + r": \{", tx)
        assert m, f"{path.name}: no {lang} block"
        out[lang] = dict(re.findall(r'(\w+): "((?:[^"\\]|\\.)*)"', _object_after(tx, m.end() - 1)))
    return out


def test_chamber_modules_use_only_keys_they_define_in_three_languages():
    """Every stage's own tx("k") / T("k") exists in its TX table in ka, en and ru (a missing one fell back to English)."""
    for f in chamber_files():
        s = f.read_text(encoding="utf-8")
        if "const TX = {" not in s:
            continue
        tx = lang_blocks(f)
        assert set(tx["ka"]) == set(tx["en"]) == set(tx["ru"]), f.name
        used = set(re.findall(r'(?<![\w.])tx\(\s*"(\w+)"', s))
        assert used <= set(tx["en"]), (f.name, sorted(used - set(tx["en"])))


def test_chamber_texts_are_never_hardcoded():
    """No user-visible English sentence is written straight into the chamber's DOM (it would ignore the language)."""
    bad = []
    for f in chamber_files():
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "const TX" in line or re.match(r"\s*(ka|en|ru):", line):
                continue
            if re.search(r'(textContent\s*=|el\([^)]*,\s*|toast\()\s*"[A-Z][a-z]+ [a-z]+', line):
                bad.append(f"{f.name}:{n}")
    assert not bad, bad



def pick(*cases):
    src = app_src()
    i, j = src.index("/* PICK_LANG"), src.index("/* /PICK_LANG */")
    body = src[i:j]
    return node(body + "\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map((c) => pickLang(...c))));")


def test_boot_language_follows_the_server_over_a_stale_device_choice():
    r = pick(["en", None, "ka", "en"],    # this device once chose English; the account is Georgian now: Georgian
             [None, None, "ru", "en"],    # nothing stored: the account's language
             ["ka", None, None, "en"],    # before the server answers: the stored choice
             [None, None, None, "ru"],    # first visit: Telegram's language
             [None, None, None, "de"],    # an unsupported one: Georgian
             ["ka", "ka", "en", "en"],    # a switch to Georgian whose save failed: kept, and sent again
             ["ka", "ka", "ka", "en"],    # the server already has it: nothing to send
             ["en", "", "ka", "en"])      # a cleared pending flag counts as none
    assert r == [{"lang": "ka", "push": False}, {"lang": "ru", "push": False}, {"lang": "ka", "push": False},
                 {"lang": "ru", "push": False}, {"lang": "ka", "push": False}, {"lang": "ka", "push": True},
                 {"lang": "ka", "push": False}, {"lang": "ka", "push": False}]


def test_boot_and_switch_use_the_rule():
    src = app_src()
    assert 'S.lang = pickLang(store.get("astro.lang"), store.get("astro.langPending"), null, tgLang).lang;' in src
    assert 'pickLang(store.get("astro.lang"), store.get("astro.langPending"), r.user && r.user.lang, tgLang)' in src
    assert '!store.get("astro.lang")) { S.lang = r.user.lang' not in src   # the old rule: a stored choice ignored the account
    assert not re.search(r'aria-label="[A-Z][a-z]+', src.split("<script")[0]), "a hardcoded English aria-label in the markup"
    # a switch marks itself pending until the server has it, and re-renders the gift (built from the texts, not data-i18n)
    assert 'store.set("astro.langPending", S.lang); applyI18n(); paintBacks(); syncDrawBtn(); renderGift();' in src
