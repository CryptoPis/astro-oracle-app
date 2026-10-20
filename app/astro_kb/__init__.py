"""Astrology knowledge base: hand-written meanings (data only) for planets, signs, houses and aspects in ka/en/ru.

The JSON files are the source of truth so they can be enriched later (for example from a book the owner
provides, rewritten in our own words) without touching code. Keys starting with "_" are comments.
"""
import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent


@lru_cache
def load(name: str) -> dict:
    data = json.loads((_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def planet(pid: str, lang: str) -> dict:
    p = load("planets")[pid]
    return p.get(lang) or p["en"]


def aspect(aid: str, lang: str) -> dict:
    a = load("aspects")[aid]
    return a.get(lang) or a["en"]
