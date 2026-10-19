"""Quality guard, safe fallbacks, per-language model routing, card names and sphere answers."""
import asyncio
import os

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN")

from app.ai import prompts as P  # noqa: E402
from app.ai import quality  # noqa: E402
from app.ai.fallbacks import safe_payload  # noqa: E402
from app.ai.provider import GroqProvider, LanguageRouter, PaidProviderStub, lang_of  # noqa: E402
from app.core import sphere, tarot  # noqa: E402

GOOD_KA = ("ვარსკვლავი იმედის კარტია. რთული პერიოდი უკან რჩება და ძალა თანდათან გიბრუნდება. დღეს ნუ იჩქარებ: "
           "დაისვენე და დაიჯერე, რომ ყველაფერი კარგად იქნება. საღამოს ახლობელ ადამიანს დაურეკე.")
# what the phone showed: an invented word in a loop
LOOP_KA = " ".join(["შთამაგლუვება მოგიტანს სიმშვიდეს და შთამაგლუვება გაძლიერებს შენს გზაზე"] * 6)


def test_guard_accepts_natural_georgian_and_russian():
    assert quality.problems(GOOD_KA, "ka") == []
    assert quality.problems("Сегодня звёзды посылают тебе спокойную энергию. Не спеши и прислушайся к себе.", "ru") == []
    for schema in (P.TarotAI, P.HoroscopeAI, P.KundliAI, P.DreamAI):
        for lang in ("ka", "ru"):
            assert quality.is_ok(safe_payload(schema, lang).model_dump(), lang)


def test_guard_rejects_loops_foreign_script_and_runaway_sentences():
    assert any("repeated" in p or "loop" in p for p in quality.problems(LOOP_KA, "ka"))
    assert any(p.startswith("script share") for p in quality.problems(
        "Today the universe gives you energy, დღეს შენ გაქვს ძალა and you must trust the process fully now", "ka"))
    assert any("character loop" in p for p in quality.problems("ძალაძალაძალაძალა მოდის და აააააა", "ka"))
    long_one = " ".join(["სიტყვა"] * 30 + ["კიდევ", "ერთი"] * 20)
    assert any(p.startswith("sentence of") for p in quality.problems(long_one, "ka"))
    # a loop spread over several fields is caught on the joined payload
    payload = {"cards": [{"interpretation": "შენ ახლა ახალი გზის დასაწყისში დგახარ."} for _ in range(5)], "synthesis": "", "advice": ""}
    assert quality.payload_problems(payload, "ka")
    assert quality.problems(LOOP_KA, "en") == []   # English is not checked


class FakeCompletions:
    """Answers per model from a script; records which models were called and with which options."""

    def __init__(self, script):
        self.script, self.calls = script, []

    async def create(self, **kw):
        self.calls.append((kw["model"], kw.get("temperature"), "frequency_penalty" in kw))
        text = self.script[kw["model"]].pop(0)

        class R:
            choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]
        return R()


def fake_provider(script, lang_models=None):
    comp = FakeCompletions(script)
    client = type("Client", (), {"chat": type("Chat", (), {"completions": comp})()})()
    p = GroqProvider("k", "text-model", "fast-model", "vision", 10, fallbacks=["next-model"], client=client, lang_models=lang_models)
    return p, comp


def energy(text):
    import json
    return json.dumps({"quote": text, "affirmation": "მე ვენდობი საკუთარ გზას.", "focus": "მოთმინება"})


def test_language_model_routing_and_retry_chain():
    system, user = P.energy_prompt("ka", "Leo", "Full Moon", "2026-10-19")
    assert lang_of(system) == "ka" and lang_of(P.energy_prompt("ru", "Leo", "x", "y")[0]) == "ru"
    # per-language model is used for Georgian, the normal one for English
    p, comp = fake_provider({"ka-model": [energy(GOOD_KA)], "fast-model": [energy("Calm day.")]}, {"ka": "ka-model"})
    asyncio.run(p.complete_json(system, user, P.EnergyAI, fast=True))
    asyncio.run(p.complete_json(*P.energy_prompt("en", "Leo", "x", "y"), P.EnergyAI, fast=True))
    assert [c[0] for c in comp.calls] == ["ka-model", "fast-model"]
    # garbage -> retry on the same model with lower temperature and penalties -> succeeds
    p, comp = fake_provider({"text-model": [energy(LOOP_KA), energy(GOOD_KA)]})
    out = asyncio.run(p.complete_json(system, user, P.EnergyAI))
    assert out.quote == GOOD_KA and comp.calls == [("text-model", 0.7, False), ("text-model", 0.3, True)]
    # garbage twice -> next model in the chain
    p, comp = fake_provider({"text-model": [energy(LOOP_KA)] * 2, "next-model": [energy(GOOD_KA)]})
    assert asyncio.run(p.complete_json(system, user, P.EnergyAI)).quote == GOOD_KA
    assert [c[0] for c in comp.calls] == ["text-model", "text-model", "next-model"]
    # every model garbles -> the hand-written text, flagged so it is not cached
    p, comp = fake_provider({"text-model": [energy(LOOP_KA)] * 2, "next-model": [energy(LOOP_KA)] * 2})
    token = quality.fallback_used.set(False)
    out = asyncio.run(p.complete_json(system, user, P.EnergyAI))
    assert out == safe_payload(P.EnergyAI, "ka")
    quality.fallback_used.reset(token)


def test_paid_provider_slot_falls_back_to_default():
    p, comp = fake_provider({"text-model": [energy(GOOD_KA)]})
    router = LanguageRouter(p, {"ka": PaidProviderStub("anthropic")})
    out = asyncio.run(router.complete_json(*P.energy_prompt("ka", "Leo", "x", "y"), P.EnergyAI))
    assert out.quote == GOOD_KA and comp.calls[0][0] == "text-model"


def test_card_names_are_static_and_nominative():
    assert set(tarot.CARD_NAMES) == {c.slug for c in tarot.DECK}
    for slug, names in tarot.CARD_NAMES.items():
        assert set(names) == {"ka", "ru", "en"} and all(names.values())
        assert "(" not in names["ka"] and tarot.REVERSED_LABEL["ka"] not in names["ka"]
    assert tarot.card_name("sun", "ka") == "მზე" and tarot.card_name("world", "ru") == "Мир"
    assert "card_title" not in P.TAROT_SCHEMA   # the AI is no longer asked to name cards
    _, user = P.tarot_prompt("ka", "daily", [{"name": "The Sun", "local_name": "მზე", "reversed": True}], ["today"], None, None)
    assert '"მზე"' in user and "(reversed)" in user


def test_sphere_answers_and_topic_advice():
    for lang in ("ka", "en", "ru"):
        assert all(len(sphere.ANSWERS[lang][t]) == 8 for t in ("yes", "wait", "no"))
        assert len(sphere.ADVICE[lang]) == 12
        for tone in ("yes", "wait", "no"):
            for line in sphere.ANSWERS[lang][tone]:
                assert quality.problems(line, lang) == [] and len(line) < 70
    assert sphere.topic_of("ვუყვარვარ?") == "love" and sphere.topic_of("Does he love me?") == "love"
    assert sphere.topic_of("Любит ли он меня?") == "love"
    assert sphere.topic_of("ხელფასს მომიმატებენ?") == "money" and sphere.topic_of("Получу ли я работу?") == "work"
    assert sphere.topic_of("გამოცდას ჩავაბარებ?") == "work" and sphere.topic_of("") == "general"
    r = sphere.ask("ka", "ვუყვარვარ?")
    assert r["topic"] == "love" and r["tone"] in ("yes", "wait", "no") and r["advice"] == sphere.ADVICE["ka"][("love", r["tone"])]
    assert r["answer"] in sphere.ANSWERS["ka"][r["tone"]]
