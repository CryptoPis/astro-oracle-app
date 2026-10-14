"""Run: pytest -q   (uses the mock AI provider and a throwaway SQLite DB)"""
import os
import tempfile
import time

_tmp = tempfile.mkdtemp()
os.environ.update({
    "BOT_TOKEN": "123456:TEST-TOKEN", "BOT_ENABLED": "false", "AI_PROVIDER": "mock",
    # set TEST_DATABASE_URL=postgresql://... to run the whole suite against PostgreSQL
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{_tmp}/test.db", "ENV": "production",
    "PUBLIC_BASE_URL": "https://astro.test", "CRON_SECRET": "cron-test-secret", "MORNING_PUSH_MODE": "off",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.security import sign_init_data  # noqa: E402

TOKEN = os.environ["BOT_TOKEN"]


def auth(uid: int, start_param: str | None = None, auth_date: int | None = None, token: str = TOKEN) -> dict:
    fields = {"user": {"id": uid, "first_name": f"U{uid}", "language_code": "ka"},
              "auth_date": auth_date or int(time.time()), "query_id": "AAH"}
    if start_param:
        fields["start_param"] = start_param
    return {"Authorization": f"tma {sign_init_data(fields, token)}"}


@pytest.fixture(scope="module")
def client():
    import asyncio
    from app.db import Base, engine
    from app import models  # noqa: F401

    async def reset():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    asyncio.run(reset())
    asyncio.run(engine.dispose())
    with TestClient(app) as c:
        yield c


def test_rejects_missing_tampered_expired(client):
    assert client.get("/api/user/profile").status_code == 401
    assert client.get("/api/user/profile", headers=auth(1, token="999:WRONG")).status_code == 401
    old = int(time.time()) - 3 * 86400
    assert client.get("/api/user/profile", headers=auth(1, auth_date=old)).status_code == 401
    h = auth(1)
    h["Authorization"] = h["Authorization"].replace("U1", "U2")  # tamper with user JSON
    assert client.get("/api/user/profile", headers=h).status_code == 401


def test_verify_and_referral(client):
    r = client.post("/api/auth/verify", headers=auth(100)).json()
    assert r["is_new"] and r["user"]["coins"] == 250 and r["user"]["lang"] == "ka"
    assert r["user"]["needs_onboarding"] is True
    r2 = client.post("/api/auth/verify", headers=auth(200, start_param="ref_100")).json()
    assert r2["referral_applied"] and r2["user"]["coins"] == 350
    assert client.get("/api/user/profile", headers=auth(100)).json()["user"]["coins"] == 500
    # a second verify must not pay the referral again
    assert client.post("/api/auth/verify", headers=auth(200, start_param="ref_100")).json()["is_new"] is False


def test_profile_update(client):
    r = client.patch("/api/user/profile", headers=auth(100), json={"birth_date": "1990-08-15", "lang": "en"}).json()
    assert r["user"]["sign"]["id"] == "Leo" and r["user"]["life_path"] == 33 and not r["user"]["needs_onboarding"]
    assert client.patch("/api/user/profile", headers=auth(100), json={"birth_date": "2999-01-01"}).status_code == 422


def test_daily_reward_once(client):
    r = client.post("/api/user/daily-reward", headers=auth(100))
    assert r.status_code == 200 and r.json()["reward"]["streak"] == 1 and r.json()["reward"]["coins_earned"] == 50
    assert client.post("/api/user/daily-reward", headers=auth(100)).status_code == 409


def test_horoscope_reward_and_cache(client):
    r = client.get("/api/horoscope?period=day", headers=auth(100)).json()
    assert r["sign"]["id"] == "Leo" and r["is_own_sign"] and r["reward"]["coins_earned"] == 20
    assert len(r["horoscope"]["sections"]) == 4
    r2 = client.get("/api/horoscope?period=day", headers=auth(100)).json()
    assert r2["reward"]["coins_earned"] == 0
    other = client.get("/api/horoscope?period=week&sign=pisces", headers=auth(100)).json()
    assert other["sign"]["id"] == "Pisces" and other["reward"] is None
    assert client.get("/api/horoscope?sign=Nope", headers=auth(100)).status_code == 400
    assert client.get("/api/horoscope", headers=auth(200)).status_code == 400  # no birth date


def test_tarot(client):
    d1 = client.post("/api/tarot/draw", headers=auth(100), json={"spread": "daily"}).json()
    d2 = client.post("/api/tarot/draw", headers=auth(100), json={"spread": "daily"}).json()
    assert d1["cards"][0]["id"] == d2["cards"][0]["id"] and d2["repeated"] and d1["reward"]["coins_earned"] == 50
    assert d1["cards"][0]["image_url"].startswith("https://astro.test/static/img/tarot/")
    t = client.post("/api/tarot/draw", headers=auth(100), json={"spread": "three", "question": "Career?"}).json()
    assert [c["position"] for c in t["cards"]] == ["past", "present", "future"]
    assert len({c["id"] for c in t["cards"]}) == 3
    assert len(client.get("/api/tarot/history", headers=auth(100)).json()["items"]) == 2
    coll = client.get("/api/tarot/collection", headers=auth(100)).json()
    assert coll["total"] == 22 and sum(coll["owned"].values()) == 4


def test_dreams(client):
    r = client.post("/api/dreams/analyze", headers=auth(100), json={"text": "I was flying over a silver river"}).json()
    assert r["saved"] and r["analysis"]["symbols"] and r["reward"]["coins_earned"] == 50
    j = client.get("/api/dreams", headers=auth(100)).json()
    assert j["total"] == 1
    assert client.delete(f"/api/dreams/{r['id']}", headers=auth(200)).status_code == 404  # not owner
    assert client.delete(f"/api/dreams/{r['id']}", headers=auth(100)).status_code == 200
    assert client.post("/api/dreams/analyze", headers=auth(100), json={"text": "short"}).status_code == 422


def test_energy_and_zodiac(client):
    e = client.get("/api/daily/energy", headers=auth(100)).json()
    assert e["quote"] and len(e["lucky_numbers"]) == 3 and e["sign"]["id"] == "Leo"
    assert client.get("/api/daily/energy", headers=auth(200)).json()["sign"] is None
    z = client.get("/api/zodiac", headers=auth(100)).json()["signs"]
    assert len(z) == 12 and sum(s["is_own"] for s in z) == 1


def test_ai_failure_refunds_quota(client, monkeypatch):
    from app.ai import provider

    class Boom:
        async def complete_json(self, *a, **k):
            raise provider.AIError("down")

    monkeypatch.setattr(provider, "_provider", Boom())
    before = client.get("/api/user/profile", headers=auth(100)).json()["user"]["coins"]
    r = client.post("/api/dreams/analyze", headers=auth(100), json={"text": "A long dream about doors"})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "ai_unavailable"
    assert client.get("/api/user/profile", headers=auth(100)).json()["user"]["coins"] == before


def test_numerology(client):
    assert client.get("/api/numerology", headers=auth(200)).json()["detail"]["code"] == "needs_birth_date"
    r = client.get("/api/numerology", headers=auth(100)).json()
    assert r["life_path"] == 33 and r["is_master"] and 1 <= r["personal_year"] <= 9
    assert r["reading"]["strengths"] and r["year_reading"]["theme"] and r["reward"]["coins_earned"] == 35
    assert client.get("/api/numerology", headers=auth(100)).json()["reward"]["coins_earned"] == 0


def test_sphere(client):
    earned = [client.post("/api/sphere", headers=auth(100), json={"question": "Will it work?"}).json() for _ in range(6)]
    assert all(e["tone"] in ("yes", "wait", "no") and e["answer"] for e in earned)
    assert [e["reward"]["coins_earned"] for e in earned] == [25] * 5 + [0]


def test_personal_year():
    from datetime import date
    from app.core.astro import personal_year_number
    assert personal_year_number(date(1990, 8, 15), 2026) == 6  # 1+5+8+2+0+2+6 = 24 -> 6


def _png(color=(120, 80, 200)) -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (64, 64), color).save(buf, "PNG"); return buf.getvalue()


def test_moon_ritual(client):
    r = client.get("/api/moon/ritual", headers=auth(100)).json()
    assert r["moon"]["code"] and len(r["ritual"]["steps"]) >= 3 and r["reward"]["coins_earned"] == 70
    assert client.get("/api/moon/ritual", headers=auth(100)).json()["reward"]["coins_earned"] == 0


def test_compatibility(client):
    from app.api.practices2 import compat_percent
    assert compat_percent("Aries", "Leo") > compat_percent("Aries", "Cancer")
    r = client.post("/api/compatibility", headers=auth(100), json={"partner_birth_date": "1992-03-25", "partner_name": "Nino"}).json()
    assert r["you"]["id"] == "Leo" and r["partner"]["id"] == "Aries" and r["partner"]["name"] == "Nino"
    assert 35 <= r["percent"] <= 97 and len(r["reading"]["areas"]) == 4 and r["reward"]["coins_earned"] == 100
    assert client.post("/api/compatibility", headers=auth(200), json={"partner_birth_date": "1992-03-25"}).status_code == 400


def test_advisor(client):
    r = client.post("/api/advisor", headers=auth(100), json={"message": "What awaits me in love?",
          "history": [{"role": "user", "text": "Hi"}, {"role": "assistant", "text": "Hello"}]}).json()
    assert r["answer"] and r["follow_ups"] and r["reward"]["coins_earned"] == 50 and r["messages_left"] == 14
    assert client.post("/api/advisor", headers=auth(100), json={"message": "x"}).status_code == 422


def test_vision(client, monkeypatch):
    r = client.post("/api/vision/aura", headers=auth(100), files={"file": ("me.png", _png(), "image/png")}).json()
    assert r["reading"]["colors"][0]["hex"].startswith("#") and r["reward"]["coins_earned"] == 60
    c = client.post("/api/vision/coffee", headers=auth(100), files={"file": ("cup.png", _png(), "image/png")}).json()
    assert c["reading"]["symbols"] and c["reward"]["coins_earned"] == 50
    bad = client.post("/api/vision/aura", headers=auth(100), files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "bad_photo"
    assert client.post("/api/vision/palm", headers=auth(100), files={"file": ("x.png", _png(), "image/png")}).status_code == 422
    from app.ai import provider, prompts as P

    class NotACup:
        async def complete_json(self, system, user, schema, **k):
            return schema.model_validate({"image_ok": False})
    monkeypatch.setattr(provider, "_provider", NotACup())
    r2 = client.post("/api/vision/coffee", headers=auth(100), files={"file": ("dog.png", _png(), "image/png")})
    assert r2.status_code == 422 and r2.json()["detail"]["code"] == "bad_photo"


def test_kundli(client, monkeypatch):
    from app.core.chart import Place
    from app.api import kundli as K

    async def fake_geo(session, city):
        return Place("Tbilisi, Georgia", 41.72, 44.78, "Asia/Tbilisi") if city.lower() == "tbilisi" else None
    monkeypatch.setattr(K, "geocode", fake_geo)
    r = client.get("/api/kundli", headers=auth(100)).json()  # no time/place yet: no lagna
    assert r["chart"]["ascendant"] is None and len(r["chart"]["planets"]) == 9 and r["reward"]["coins_earned"] == 100
    sun = next(p for p in r["chart"]["planets"] if p["id"] == "sun")
    assert sun["sign"] == "Cancer"  # sidereal sun on 15 Aug is in Cancer
    client.patch("/api/user/profile", headers=auth(100), json={"birth_time": "08:00", "birth_city": "Tbilisi"})
    r = client.get("/api/kundli", headers=auth(100)).json()
    assert r["chart"]["ascendant"]["sign"] == "Leo" and r["chart"]["place"]["tz"] == "Asia/Tbilisi"
    assert all(p["house"] for p in r["chart"]["planets"]) and r["reward"]["coins_earned"] == 0
    client.patch("/api/user/profile", headers=auth(100), json={"birth_city": "Nowhere-xyz"})
    r = client.get("/api/kundli", headers=auth(100)).json()
    assert r["city_not_found"] and r["chart"]["ascendant"] is None


def test_health_cron_gzip(client):
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/healthz?deep=1").json()["db"] == "ok"
    assert client.get("/cron/morning").status_code == 403
    assert client.get("/cron/morning?key=wrong").status_code == 403
    assert client.get("/cron/morning?key=cron-test-secret").status_code == 503  # bot disabled in tests
    r = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.headers.get("content-encoding") == "gzip"
    img = client.get("/static/img/zodiac/leo.webp")
    assert img.status_code == 200 and "max-age=604800" in img.headers["cache-control"]


def test_database_url_normalization():
    from app.config import normalize_database_url
    url, args = normalize_database_url(
        "postgresql://u:p@ep-cool-1-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
    assert url.startswith("postgresql+asyncpg://u:p@ep-cool-1-pooler") and "sslmode" not in url and "channel_binding" not in url
    assert "prepared_statement_cache_size=0" in url and args == {"ssl": "require", "statement_cache_size": 0}
    url, args = normalize_database_url("postgres://u:p@ep-x.eu-central-1.aws.neon.tech/db?sslmode=require")
    assert url == "postgresql+asyncpg://u:p@ep-x.eu-central-1.aws.neon.tech/db" and args == {"ssl": "require"}
    assert normalize_database_url("sqlite+aiosqlite:///x.db") == ("sqlite+aiosqlite:///x.db", {})


def test_groq_fallback_and_json_repair():
    import asyncio, json as _json
    from types import SimpleNamespace as NS
    from app.ai import prompts as P
    from app.ai.provider import GroqProvider, extract_json

    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    calls = []

    class Completions:
        async def create(self, **kw):
            calls.append(kw)
            if kw["model"] == "dead/model":
                e = Exception("The model `dead/model` has been decommissioned"); e.status_code = 400; raise e
            if "response_format" in kw and kw["model"] == "openai/gpt-oss-20b":
                raise Exception("response_format json_object is not supported")
            body = {"quote": "q", "affirmation": "a", "focus": "Patience"}
            return NS(choices=[NS(message=NS(content="Here you go: " + _json.dumps(body)))])

    client = NS(chat=NS(completions=Completions()))
    ai = GroqProvider("k", "dead/model", "dead/model", "v", 5, ["openai/gpt-oss-20b"], client=client)
    res = asyncio.run(ai.complete_json("sys", "user", P.EnergyAI, fast=True))
    assert res.focus == "Patience" and "dead/model" in ai.dead and "openai/gpt-oss-20b" in ai.no_json_mode
    assert calls[-1]["extra_body"] == {"reasoning_effort": "low"} and "response_format" not in calls[-1]
    n = len(calls); asyncio.run(ai.complete_json("sys", "user", P.EnergyAI, fast=True))
    assert len(calls) == n + 1  # the dead model is skipped from now on
