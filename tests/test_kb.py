"""The source-based knowledge base (app/astro_kb): every entry complete in ka/en/ru, with a source note."""
import re

import pytest

from app.astro_kb import load
from app.core.tarot import DECK

LANGS = ("en", "ka", "ru")
GEORGIAN = re.compile(r"[ა-ჿ]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LATIN = re.compile(r"[A-Za-z]{3,}")


def check_text(entry: dict, fields: tuple[str, ...], where: str):
    for lang in LANGS:
        assert lang in entry, f"{where}: no {lang}"
        for f in fields:
            text = entry[lang][f] if isinstance(entry[lang], dict) else entry[lang]
            assert isinstance(text, str) and len(text.strip()) >= 3, f"{where}.{lang}.{f} empty"
            if lang == "ka":
                assert GEORGIAN.search(text) and not LATIN.search(text), f"{where}.ka.{f} is not Georgian: {text!r}"
            if lang == "ru":
                assert CYRILLIC.search(text) and not LATIN.search(text), f"{where}.ru.{f} is not Russian: {text!r}"


FOUR = ("meaning", "supportive", "challenging", "advice")


def test_tarot_all_22_cards_upright_and_reversed():
    kb = load("tarot")
    assert set(kb) == {c.slug for c in DECK} and len(kb) == 22
    for slug, card in kb.items():
        for side in ("upright", "reversed"):
            assert card[side]["source"].startswith("Waite"), (slug, side)
            check_text(card[side], FOUR, f"{slug}.{side}")
        assert card["upright"]["en"]["meaning"] != card["reversed"]["en"]["meaning"]


def test_aura_colors():
    kb = load("aura")
    assert {"red", "orange", "yellow", "green", "blue", "violet", "pink", "gold", "brown", "gray", "black", "white"} <= set(kb)
    for cid, c in kb.items():
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", c["hex"]) and c["source"], cid
        check_text(c, ("name", *FOUR), cid)


def test_moon_phases():
    kb = load("moon")
    assert list(kb) == ["new_moon", "waxing_crescent", "first_quarter", "waxing_gibbous", "full_moon",
                        "waning_gibbous", "last_quarter", "waning_crescent"]
    for pid, phase in kb.items():
        assert "Harley" in phase["source"]
        check_text(phase, ("lore", "supportive", "challenging", "advice"), pid)


def test_numbers_1_to_9_and_master_numbers():
    kb = load("numbers")
    assert set(kb) == {*map(str, range(1, 10)), "11", "22", "33"}
    for n, entry in kb.items():
        assert entry["planet"] in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
        assert entry["source"].startswith("Modern" if len(n) == 2 else "Sepharial"), n   # 11/22/33 marked as modern
        check_text(entry, FOUR, n)


def test_transit_pairs_and_dignity_labels():
    tr = load("transits")
    for key, entry in tr.items():
        assert entry["source"], key
        check_text(entry, FOUR, key)
    dig = load("dignities")
    for kind in ("domicile", "exaltation", "detriment", "fall"):
        lab = dig["labels"][kind]
        assert GEORGIAN.search(lab["ka"]) and CYRILLIC.search(lab["ru"]) and lab["meaning_en"]


@pytest.mark.parametrize("name", ["planets", "aspects"])
def test_planets_and_aspects_have_sources_and_advice(name):
    for key, entry in load(name).items():
        assert entry["source"], key
        check_text(entry, ("name", "advice"), key)


def test_coffee_symbols_and_rules():
    kb = load("coffee")
    for lang in LANGS:
        assert len(kb["rules"][lang]) >= 3
    assert len(kb["symbols"]) >= 40
    for sid, s in kb["symbols"].items():
        assert s["tone"] in ("good", "bad", "neutral"), sid
        for lang in LANGS:
            name, meaning = s[lang]
            assert name and meaning, (sid, lang)
        assert GEORGIAN.search(s["ka"][1]) and CYRILLIC.search(s["ru"][1]), sid


def test_dreams_method_and_symbols():
    kb = load("dreams")
    for lang in LANGS:
        assert len(kb["method"][lang]) >= 4
    assert len(kb["symbols"]) >= 20
    for sid, s in kb["symbols"].items():
        assert all(s["stems"][lang] for lang in LANGS), sid
        check_text(s, ("meaning", "question"), sid)


def test_correspondences_cover_the_week():
    kb = load("correspondences")
    assert sorted(c["weekday"] for c in kb.values()) == list(range(7))
    for pid, c in kb.items():
        assert "Agrippa" in c["source"] and re.fullmatch(r"#[0-9a-f]{6}", c["color"])
        check_text(c, ("color_name", "keyword", "tip"), pid)


def test_sphere_lore():
    kb = load("sphere")
    for tone in ("yes", "wait", "no"):
        check_text(kb[tone], ("cloud", "lore"), tone)


def test_prompts_carry_the_kb_meanings():
    from datetime import date

    from app.ai import prompts as P
    tarot = load("tarot")
    drawn = [{"id": "tower", "name": "The Tower", "local_name": "კოშკი", "reversed": True},
             {"id": "star", "name": "The Star", "local_name": "ვარსკვლავი", "reversed": False}]
    system, user = P.tarot_prompt("ka", "three", drawn, ["past", "present"], None, None)
    assert tarot["tower"]["reversed"]["ka"]["challenging"] in user and tarot["star"]["upright"]["ka"]["meaning"] in user
    assert "Waite" in system and "(reversed)" in user
    # dreams: Georgian stems find the symbols, Freud's method is given as one perspective
    _, user = P.dream_prompt("ka", "ვფრინავდი ზღვის თავზე და კბილი ამტკივდა", None, "Full Moon")
    dreams = load("dreams")["symbols"]
    for sid in ("flying", "water", "teeth"):
        assert dreams[sid]["ka"]["question"] in user, sid
    assert "Freud" in user
    _, user = P.numerology_prompt("ru", 22)
    assert load("numbers")["22"]["ru"]["challenging"] in user
    _, user = P.moon_ritual_prompt("en", "Full Moon", 99, "2026-10-26", "full_moon")
    assert load("moon")["full_moon"]["en"]["lore"] in user
    _, user = P.aura_prompt("ka")
    assert load("aura")["violet"]["hex"] in user and load("aura")["violet"]["ka"]["name"] in user
    _, user = P.coffee_prompt("ru")
    assert load("coffee")["symbols"]["anchor"]["ru"][1] in user
    _, user = P.energy_prompt("en", "Leo", "Full Moon", "2026-10-20")      # a Tuesday: the day of Mars
    assert "Day of mars" in user and "red" in user


def test_day_correspondence_and_sphere_lore():
    from datetime import date

    from app.astro_kb.context import day_correspondence, sphere_lore
    d = day_correspondence(date(2026, 10, 25), "ka")                     # Sunday: the Sun, gold
    assert d["planet"] == "sun" and d["color"] == "#e8b84a" and GEORGIAN.search(d["keyword"])
    assert sphere_lore("no", "ru")["cloud"] and "Sepharial" not in sphere_lore("yes", "en")["lore"]
