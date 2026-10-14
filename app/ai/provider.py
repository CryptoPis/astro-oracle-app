"""AI provider layer.

- AsyncGroq instead of the legacy sync client. The old bot froze the event
  loop for every user during each AI call.
- JSON mode plus Pydantic validation, with one automatic repair retry.
- Switchable provider: AI_PROVIDER=groq | mock. Add OpenAI or Claude by
  implementing `complete_json` in another class.
"""
import json
import logging
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai import prompts as P
from app.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class AIError(Exception):
    pass


class AIProvider(Protocol):
    async def complete_json(self, system: str, user: str, schema: type[T], *,
                            fast: bool = False, max_tokens: int = 900, image: bytes | None = None) -> T: ...


class GroqProvider:
    def __init__(self, api_key: str, text_model: str, fast_model: str, vision_model: str, timeout: float):
        from groq import AsyncGroq
        self.client = AsyncGroq(api_key=api_key, timeout=timeout, max_retries=2)
        self.text_model, self.fast_model, self.vision_model = text_model, fast_model, vision_model

    async def complete_json(self, system, user, schema, *, fast=False, max_tokens=900, image=None):
        model = self.vision_model if image else (self.fast_model if fast else self.text_model)
        content = user
        if image:  # sent inline as base64; never as a Telegram file URL (that would leak the bot token)
            import base64
            content = [{"type": "text", "text": user},
                       {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image).decode()}}]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
        last_err: Exception | None = None
        for attempt in range(2):
            raw = ""
            try:
                resp = await self.client.chat.completions.create(
                    model=model, messages=messages, temperature=0.7 if attempt == 0 else 0.3,
                    max_tokens=max_tokens, response_format={"type": "json_object"})
                raw = resp.choices[0].message.content or ""
                return schema.model_validate(json.loads(raw))
            except (json.JSONDecodeError, ValidationError) as e:
                last_err = e
                log.warning("AI returned invalid JSON (attempt %s): %s", attempt + 1, e)
                messages = messages[:2] + [
                    {"role": "assistant", "content": raw[:4000]},
                    {"role": "user", "content": f"That JSON was invalid: {str(e)[:500]}. "
                                                "Return the corrected JSON object only."}]
            except Exception as e:  # network, rate limit, model errors
                log.exception("Groq call failed")
                raise AIError(str(e)) from e
        raise AIError(f"invalid AI output: {last_err}")


class MockProvider:
    """Offline provider for frontend work and tests. Never calls a network API."""

    _DATA = {
        P.HoroscopeAI: lambda: {
            "title": "Stars align in your favor", "summary": "A balanced day with room to grow.",
            "sections": [{"area": a, "title": a.title(), "text": f"Mock {a} text.", "score": 4}
                         for a in ("love", "career", "health", "finance")],
            "advice": "Trust the small signs.", "lucky_color": "Gold", "mood": "Hopeful"},
        P.TarotAI: lambda: {"cards": [{"position": "today", "card_title": "Mock card",
                                       "keywords": ["insight", "change", "courage"],
                                       "interpretation": "Mock interpretation."}],
                            "synthesis": "Mock synthesis.", "advice": "Mock advice."},
        P.DreamAI: lambda: {"title": "The Silver River", "mood": "Calm",
                            "symbols": [{"symbol": "Water", "meaning": "Emotions in motion."}],
                            "interpretation": "Mock dream interpretation.", "advice": "Rest well.",
                            "tags": ["emotion", "change"]},
        P.EnergyAI: lambda: {"quote": "Today the universe rewards patience.",
                             "affirmation": "I welcome what is meant for me.", "focus": "Patience"},
        P.NumerologyAI: lambda: {"title": "The Seeker", "essence": "Mock essence.",
                                 "strengths": ["insight", "depth", "intuition"], "challenges": ["isolation", "doubt"],
                                 "purpose": "Mock purpose.", "love": "Mock love.", "career": "Mock career.",
                                 "advice": "Mock advice."},
        P.PersonalYearAI: lambda: {"theme": "Inner search", "text": "Mock year text.", "advice": "Mock year advice."},
        P.MoonRitualAI: lambda: {"title": "Silver water", "intention": "Mock intention.",
                                 "steps": ["Light a candle.", "Pour a glass of water.", "Write one wish."],
                                 "affirmation": "I grow with the moon.", "avoid": "Avoid haste."},
        P.CompatAI: lambda: {"title": "Fire and air", "summary": "Mock summary.",
                             "areas": [{"area": a, "score": 4, "text": f"Mock {a}."} for a in ("love", "communication", "trust", "growth")],
                             "strengths": ["passion", "humor"], "challenges": ["impatience"], "advice": "Mock advice."},
        P.AdvisorAI: lambda: {"answer": "Mock astrologer answer.", "follow_ups": ["What about love?", "And career?"]},
        P.AuraAI: lambda: {"image_ok": True, "title": "Violet dawn",
                           "colors": [{"name": "Violet", "hex": "#8b6cff", "meaning": "Intuition."},
                                      {"name": "Gold", "hex": "#e2bd6a", "meaning": "Confidence."}],
                           "reading": "Mock aura reading.", "energy": "Calm", "advice": "Mock advice."},
        P.CoffeeAI: lambda: {"image_ok": True, "title": "The open road",
                             "symbols": [{"symbol": "Bird", "meaning": "News."}, {"symbol": "Road", "meaning": "A journey."}],
                             "past": "Mock past.", "present": "Mock present.", "future": "Mock future.", "advice": "Mock advice."},
        P.KundliAI: lambda: {"title": "Mock chart", "overview": "Mock overview.", "ascendant": "Mock lagna.",
                             "moon": "Mock moon.", "sun": "Mock sun.", "strengths": ["focus"], "challenges": ["doubt"],
                             "advice": "Mock advice."},
    }

    async def complete_json(self, system, user, schema, *, fast=False, max_tokens=900, image=None):
        data = self._DATA[schema]()
        if schema is P.TarotAI:  # mirror the requested positions
            positions = [line.split("position=")[1].split(":")[0]
                         for line in user.splitlines() if "position=" in line]
            data["cards"] = [{**data["cards"][0], "position": p} for p in positions] or data["cards"]
        return schema.model_validate(data)


_provider: AIProvider | None = None


def get_ai() -> AIProvider:
    global _provider
    if _provider is None:
        s = get_settings()
        if s.ai_provider == "mock":
            _provider = MockProvider()
        else:
            if not s.groq_api_key:
                raise RuntimeError("GROQ_API_KEY is not set (or set AI_PROVIDER=mock for offline dev)")
            _provider = GroqProvider(s.groq_api_key, s.groq_text_model, s.groq_fast_model,
                                     s.groq_vision_model, s.ai_timeout_seconds)
    return _provider
