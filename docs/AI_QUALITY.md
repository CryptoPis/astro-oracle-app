# AI text quality (Georgian and Russian)

## The problem (2026-10-19)
On a real phone a Georgian tarot reading came back as nonsense: an invented word ("შთამაგლუვება") repeated
dozens of times, broken grammar, and the card title "მზის (რევერსი) შებრუნებული".

Root causes:
1. **Card names came from the AI.** The server stored the model's `card_title` (genitive "მზის" plus its own
   "(რევერსი)"), and the UI added "შებრუნებული" again.
2. **No output check.** Whatever the free model returned (JSON-valid but garbled) was shown and, for shared
   content (horoscopes, energy, numerology…), cached in `ai_cache` for every user with the same sign.
3. **English-only instructions** for Georgian output invite calques and invented words.

## What changed
- **Names are never generated.** Tarot cards: `app/core/tarot.py` `CARD_NAMES` (ka/en/ru, nominative); the UI
  renders "მზე · შებრუნებული". Signs, planets and moon phases were already static dictionaries.
- **Quality guard** `app/ai/quality.py`, applied to every ka/ru answer (each field and all fields together):
  a long word repeated more than a normal text allows, a repeated 3-word loop, a word glued to itself or a
  letter repeated 5+ times, fewer than 85% of letters in the target script, a sentence over 55 words.
- **Fallback chain** `app/ai/provider.py`: rejected → retry on the same model (temperature 0.3, frequency and
  presence penalties; dropped automatically if a model refuses them) → next model in `GROQ_FALLBACK_MODELS` →
  a short hand-written text (`app/ai/fallbacks.py`, all schemas × ka/en/ru). The hand-written text is never
  stored in `ai_cache`, so the next visitor gets a fresh attempt. Rejections are logged as
  `AI quality reject: model=… lang=… schema=… reasons=…` (no user text).
- **Georgian prompt rules in Georgian** (`KA_RULES` in `app/ai/prompts.py`): short everyday sentences, no
  invented words, no transliterated English, correct cases, two natural few-shot answers. Russian gets style
  rules too. JSON schemas are unchanged (the tarot `card_title` is now optional and ignored).
- **Per-language models**: `GROQ_MODEL_KA`, `GROQ_MODEL_RU` (empty = the current models). `/diag` shows them.
- **Paid provider slot**: `AI_PROVIDER_KA=anthropic|openai|gemini` + its key routes that language to a
  `PaidProviderStub` (no network calls yet; on failure the default Groq chain answers). Implementing an adapter
  means filling `complete_json` in that class; nothing else changes.
- **Sphere** answers are hand-written (`app/core/sphere.py`), never AI.

## Benchmark
`scripts/ai_benchmark.py` lists the models on the Groq account, runs 10 fixed Georgian prompts (tarot ×2,
horoscope ×2, dream, numerology, energy, moon ritual, compatibility, personal year) and 5 Russian ones through
each chat model with the app's own prompts and options, and records valid JSON, guard problems and latency.
Answers are saved to `dist/ai_bench/<model>/` for a human review.

**Status: not run yet.** The Groq key exists only on Render; there is no `.env` on the development machine,
and the key was not copied anywhere. To run it (the key stays in that terminal only):

    PowerShell:  $env:GROQ_API_KEY = "<key from console.groq.com/keys>"; python -m scripts.ai_benchmark
    bash:        GROQ_API_KEY=<key> python -m scripts.ai_benchmark

Then set the winner on Render: Environment → `GROQ_MODEL_KA=<model id>` (and `GROQ_MODEL_RU`). Until then
Georgian uses `openai/gpt-oss-120b` (text) / `openai/gpt-oss-20b` (fast), now behind the guard.

How to score the saved answers (native-speaker rubric, 1-5 each): grammar and cases; natural, everyday
phrasing; no invented or transliterated words; concrete content (not filler). A model is usable for Georgian
if it averages ≥ 4 with no answer below 3 and the guard rejects at most 1 of 10.

Honest expectation: free open models are weak in Georgian. The guard turns their worst failures into a
retry or a calm hand-written text, but it cannot make mediocre Georgian good. If the benchmark winner still
scores below 4, the planned step is a paid model for `ka` only (the slot above), which is the most reliable
way to natural Georgian.

## Cleaning old bad texts
`scripts/purge_bad_ai_cache.py` scans `ai_cache` (deletes failing rows with `--apply`) and counts failing
`readings` (user history is never changed). On Render: service → **Shell**:

    python -m scripts.purge_bad_ai_cache --dry-run
    python -m scripts.purge_bad_ai_cache --apply
