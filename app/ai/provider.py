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


def extract_json(raw: str) -> dict:
    """Parses a JSON object even if the model wrapped it in ```json fences or added a sentence around it."""
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    i, j = raw.find("{"), raw.rfind("}")
    if i == -1 or j <= i:
        raise json.JSONDecodeError("no JSON object found", raw, 0)
    return json.loads(raw[i:j + 1])


def _is_model_gone(e: Exception) -> bool:
    msg = str(e).lower()
    return getattr(e, "status_code", None) == 404 or any(k in msg for k in (
        "model_decommissioned", "decommissioned", "model_not_found", "does not exist", "not found",
        "no longer supported", "model_permission_blocked"))


class GroqProvider:
    """Groq with model fallback.

    - Each call tries the preferred model, then GROQ_FALLBACK_MODELS. A model that Groq reports as
      retired/missing is skipped for the rest of the process, so one dead model never breaks the app.
    - gpt-oss models are reasoning models: we ask for low reasoning effort (fast, cheap) and leave room
      for the hidden reasoning tokens.
    - If a model rejects JSON mode or reasoning_effort, the call is retried without that option.
    """

    def __init__(self, api_key: str, text_model: str, fast_model: str, vision_model: str, timeout: float,
                 fallbacks: list[str] | None = None, client=None):
        if client is None:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=api_key, timeout=timeout, max_retries=1)
        self.client = client
        self.text_model, self.fast_model, self.vision_model = text_model, fast_model, vision_model
        self.fallbacks = [m for m in (fallbacks or []) if m]
        self.dead: set[str] = set()
        self.no_json_mode: set[str] = set()
        self.no_reasoning_param: set[str] = set()

    def _chain(self, preferred: str, image: bool) -> list[str]:
        chain = [preferred] if image else [preferred, *self.fallbacks]
        seen, out = set(), []
        for m in chain:
            if m and m not in seen and m not in self.dead:
                seen.add(m); out.append(m)
        return out

    async def _call(self, model: str, messages: list, max_tokens: int, temperature: float) -> str:
        kwargs = {"model": model, "messages": messages, "temperature": temperature}
        reasoning = model.startswith("openai/gpt-oss")
        kwargs["max_tokens"] = max_tokens + (800 if reasoning else 0)
        if model not in self.no_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if reasoning and model not in self.no_reasoning_param:
            kwargs["extra_body"] = {"reasoning_effort": "low"}
        try:
            resp = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            msg = str(e).lower()
            if "response_format" in msg or "json_object" in msg or "json mode" in msg:
                self.no_json_mode.add(model)
                return await self._call(model, messages, max_tokens, temperature)
            if "reasoning" in msg and model not in self.no_reasoning_param:
                self.no_reasoning_param.add(model)
                return await self._call(model, messages, max_tokens, temperature)
            raise
        return resp.choices[0].message.content or ""

    async def complete_json(self, system, user, schema, *, fast=False, max_tokens=900, image=None):
        preferred = self.vision_model if image else (self.fast_model if fast else self.text_model)
        content = user
        if image:  # sent inline as base64; never as a Telegram file URL (that would leak the bot token)
            import base64
            content = [{"type": "text", "text": user},
                       {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image).decode()}}]
        base_messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
        last_err: Exception | None = None
        for model in self._chain(preferred, bool(image)):
            messages = list(base_messages)
            for attempt in range(2):
                raw = ""
                try:
                    raw = await self._call(model, messages, max_tokens, 0.7 if attempt == 0 else 0.3)
                    return schema.model_validate(extract_json(raw))
                except (json.JSONDecodeError, ValidationError) as e:
                    last_err = e
                    log.warning("AI %s returned invalid JSON (attempt %s): %s", model, attempt + 1, e)
                    messages = base_messages + [
                        {"role": "assistant", "content": raw[:4000]},
                        {"role": "user", "content": f"That JSON was invalid: {str(e)[:500]}. Return the corrected JSON object only."}]
                except Exception as e:
                    last_err = e
                    if _is_model_gone(e):
                        log.error("Groq model %s is unavailable (%s); switching to the next model", model, e)
                        self.dead.add(model)
                        break
                    log.exception("Groq call failed on %s", model)
                    raise AIError(str(e)) from e
        raise AIError(f"no working AI model: {last_err}")

    async def list_models(self) -> list[str]:
        res = await self.client.models.list()
        return sorted(m.id for m in res.data)


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
                                     s.groq_vision_model, s.ai_timeout_seconds, s.groq_fallback_models)
    return _provider
