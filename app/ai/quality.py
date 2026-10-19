"""Output quality guard for AI text in Georgian and Russian.

Free models sometimes fall into loops in Georgian: an invented word repeated dozens of times, half-Latin text,
endless sentences. Every ka/ru answer is checked before it reaches a user or the shared cache; a rejected answer
is retried, then another model is tried, then a short hand-written text is used (see provider.py and
fallbacks.py). Checks are cheap heuristics, tuned so that normal readings pass:

- a long word (6+ letters) appearing more often than a normal text allows;
- a repeated 3-word sequence (a loop);
- a long word glued to itself or a letter repeated 5+ times;
- too many letters outside the target script (Georgian: Mkhedruli; Russian: Cyrillic);
- an absurdly long sentence.
"""
import re
from collections import Counter
from contextvars import ContextVar

# set by the provider when it had to return the hand-written fallback; the shared cache must not keep it
fallback_used: ContextVar[bool] = ContextVar("ai_fallback_used", default=False)

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_SENTENCE = re.compile(r"[.!?…;:\n]+")
_SCRIPT = {"ka": re.compile(r"[Ⴀ-ჿᲐ-Ჿⴀ-⴯]"), "ru": re.compile(r"[Ѐ-ӿ]")}

MIN_SCRIPT_SHARE = 0.85      # letters in the target script / all letters
MAX_SENTENCE_WORDS = 55
LONG_WORD = 6


def strings_in(obj) -> list[str]:
    """Every string value inside a JSON-like structure (keys are ignored)."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in strings_in(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in strings_in(v)]
    return []


def problems(text: str, lang: str, loop_min: int = 3) -> list[str]:
    """Reasons to reject `text` (empty list = looks fine). Only ka and ru are checked."""
    if lang not in _SCRIPT or not text.strip():
        return []
    out: list[str] = []
    words = [w.lower() for w in _WORD.findall(text)]
    n = len(words)
    if not n:
        return ["no words"]

    letters = sum(len(w) for w in words)
    in_script = len(_SCRIPT[lang].findall(text))
    if letters >= 20 and in_script / letters < MIN_SCRIPT_SHARE:
        out.append(f"script share {in_script / letters:.2f}")

    # a normal reading uses a content word a few times; a loop uses it dozens of times
    limit = max(4, int(n * 0.03) + 2)
    for w, c in Counter(w for w in words if len(w) >= LONG_WORD).most_common(3):
        if c > limit:
            out.append(f"word repeated {c}x (limit {limit})")
            break

    tri = Counter(zip(words, words[1:], words[2:]))
    if tri and (top := tri.most_common(1)[0])[1] >= loop_min:
        out.append(f"3-word loop repeated {top[1]}x")

    if re.search(r"(.)\1{4,}", text) or re.search(r"(\w{4,})\1{2,}", text):
        out.append("character loop")
    if any(len(w) > 30 for w in words):
        out.append("absurdly long word")

    longest = max((len(_WORD.findall(s)) for s in _SENTENCE.split(text)), default=0)
    if longest > MAX_SENTENCE_WORDS:
        out.append(f"sentence of {longest} words")
    return out


def payload_problems(payload, lang: str) -> list[str]:
    """Checks every field on its own and all of them together (loops often span fields)."""
    texts = strings_in(payload)
    found: list[str] = []
    for t in texts:
        found += problems(t, lang)
    joined = problems(" \n".join(texts), lang, loop_min=4)   # one phrase per card is fine, a loop is not
    found += [p for p in joined if p.startswith(("word repeated", "3-word loop"))]
    return sorted(set(found))


def is_ok(payload, lang: str) -> bool:
    return not payload_problems(payload, lang)
