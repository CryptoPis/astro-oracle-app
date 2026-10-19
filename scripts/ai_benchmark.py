"""Benchmarks the Groq models available on this account for Georgian (and Russian) quality (dev tool).

    PowerShell:  $env:GROQ_API_KEY = "<your key>"; python -m scripts.ai_benchmark [--models a,b] [--langs ka,ru]
    bash:        GROQ_API_KEY=<your key> python -m scripts.ai_benchmark

Needs only GROQ_API_KEY in the environment (never printed, never written anywhere). For every chat model it runs fixed prompts built
with the app's own prompt builders (10 Georgian, 5 Russian), the same call options as the app (JSON mode,
low reasoning effort for gpt-oss), and records: valid JSON for the schema, quality-guard problems, latency.
Answers go to dist/ai_bench/<model>/<lang>-<n>.json for a human review; the summary to dist/ai_bench/summary.json.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from app.ai import prompts as P
from app.ai.provider import extract_json
from app.ai.quality import payload_problems
import os

OUT = Path(__file__).resolve().parent.parent / "dist" / "ai_bench"
SKIP = ("whisper", "guard", "tts", "playai", "compound", "orpheus", "allam")   # audio, safety, agent and other non-chat models

TAROT_ONE = [{"name": "The Star", "local_name": "ვარსკვლავი", "reversed": False}]
TAROT_THREE = [{"name": "The Tower", "local_name": "კოშკი", "reversed": False},
               {"name": "The Lovers", "local_name": "შეყვარებულები", "reversed": True},
               {"name": "The Sun", "local_name": "მზე", "reversed": False}]
CASES = {
    "ka": [
        ("tarot day", P.TarotAI, lambda: P.tarot_prompt("ka", "daily", TAROT_ONE, ["today"], "Leo", None)),
        ("tarot three", P.TarotAI, lambda: P.tarot_prompt("ka", "three", TAROT_THREE, ["past", "present", "future"], "Pisces", "ვუყვარვარ თუ არა?")),
        ("horoscope day", P.HoroscopeAI, lambda: P.horoscope_prompt("ka", "Leo", "day", "2026-10-19", "Waxing Crescent")),
        ("horoscope week", P.HoroscopeAI, lambda: P.horoscope_prompt("ka", "Pisces", "week", "2026-W43", "Waxing Crescent")),
        ("dream", P.DreamAI, lambda: P.dream_prompt("ka", "დამესიზმრა, რომ ზღვაში ვცურავდი და უცებ დელფინი გამოჩნდა, რომელიც ნაპირისკენ მიმიძღოდა.", "Cancer", "Full Moon")),
        ("numerology", P.NumerologyAI, lambda: P.numerology_prompt("ka", 7)),
        ("energy", P.EnergyAI, lambda: P.energy_prompt("ka", "Libra", "Waxing Crescent", "2026-10-19")),
        ("moon ritual", P.MoonRitualAI, lambda: P.moon_ritual_prompt("ka", "Waxing Crescent", 27, "2026-10-19")),
        ("compatibility", P.CompatAI, lambda: P.compat_prompt("ka", "Aries", "Cancer", 64)),
        ("personal year", P.PersonalYearAI, lambda: P.personal_year_prompt("ka", 5, 2026)),
    ],
    "ru": [
        ("tarot three", P.TarotAI, lambda: P.tarot_prompt("ru", "three", [{**c, "local_name": n} for c, n in zip(TAROT_THREE, ["Башня", "Влюблённые", "Солнце"])],
                                                         ["past", "present", "future"], "Pisces", "Любит ли он меня?")),
        ("horoscope day", P.HoroscopeAI, lambda: P.horoscope_prompt("ru", "Leo", "day", "2026-10-19", "Waxing Crescent")),
        ("dream", P.DreamAI, lambda: P.dream_prompt("ru", "Мне приснилось, что я плыву в море, и дельфин ведёт меня к берегу.", "Cancer", "Full Moon")),
        ("numerology", P.NumerologyAI, lambda: P.numerology_prompt("ru", 7)),
        ("energy", P.EnergyAI, lambda: P.energy_prompt("ru", "Libra", "Waxing Crescent", "2026-10-19")),
    ],
}


async def call(client, model: str, system: str, user: str, max_tokens: int = 1100) -> tuple[str, float]:
    kwargs = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
              "temperature": 0.7, "response_format": {"type": "json_object"}}
    reasoning = model.startswith("openai/gpt-oss")
    kwargs["max_tokens"] = max_tokens + (800 if reasoning else 0)
    if reasoning:
        kwargs["extra_body"] = {"reasoning_effort": "low"}
    for attempt in range(4):
        t = time.perf_counter()
        try:
            r = await client.chat.completions.create(**kwargs)
            return r.choices[0].message.content or "", time.perf_counter() - t
        except Exception as e:
            msg = str(e).lower()
            if "rate" in msg or "429" in msg:
                await asyncio.sleep(20 * (attempt + 1))
                continue
            if "response_format" in msg or "json" in msg and "mode" in msg:
                kwargs.pop("response_format", None)
                continue
            raise
    raise RuntimeError("rate limited")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="")
    ap.add_argument("--langs", default="ka,ru")
    a = ap.parse_args()
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        sys.exit("Set GROQ_API_KEY in this terminal first (see the docstring). Nothing was called.")
    from groq import AsyncGroq
    client = AsyncGroq(api_key=key, timeout=90, max_retries=0)
    available = sorted(m.id for m in (await client.models.list()).data)
    print("available models:", ", ".join(available))
    models = [m for m in (a.models.split(",") if a.models else available) if m and not any(k in m for k in SKIP)]
    summary = {}
    for model in models:
        rows = []
        for lang in a.langs.split(","):
            for i, (name, schema, build) in enumerate(CASES[lang], 1):
                system, user = build()
                row = {"lang": lang, "case": name}
                try:
                    raw, sec = await call(client, model, system, user)
                    row["seconds"] = round(sec, 1)
                    data = schema.model_validate(extract_json(raw)).model_dump()
                    row["valid"] = True
                    row["problems"] = payload_problems(data, lang)
                    path = OUT / model.replace("/", "_") / f"{lang}-{i:02d}.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"case": name, "answer": data}, ensure_ascii=False, indent=1), encoding="utf-8")
                except Exception as e:
                    row["valid"] = False
                    row["error"] = f"{type(e).__name__}: {str(e)[:120]}"
                rows.append(row)
                print(f"{model:40} {lang} {name:15} valid={row['valid']!s:5} problems={row.get('problems', row.get('error'))} {row.get('seconds', '')}s")
                await asyncio.sleep(2)
        summary[model] = rows
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nmodel                                    lang  valid  clean  avg s")
    for model, rows in summary.items():
        for lang in a.langs.split(","):
            r = [x for x in rows if x["lang"] == lang]
            v = [x for x in r if x.get("valid")]
            clean = [x for x in v if not x["problems"]]
            avg = sum(x["seconds"] for x in v) / len(v) if v else 0
            print(f"{model:40} {lang}    {len(v):2}/{len(r)}  {len(clean):2}/{len(r)}  {avg:5.1f}")


if __name__ == "__main__":
    asyncio.run(main())
