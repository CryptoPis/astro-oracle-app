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


@pytest.fixture(autouse=True)
def offline_geocoding(monkeypatch):
    """Readings geocode the birth city; tests never call the real Open-Meteo API."""
    from app.api import kundli as K
    from app.core.chart import Place

    async def fake(session, city):
        return Place("Tbilisi, Georgia", 41.72, 44.78, "Asia/Tbilisi") if city.lower() == "tbilisi" else None
    monkeypatch.setattr(K, "geocode", fake)


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
    # card names come from the dictionary in the user's language (ka), never from the AI's "card_title"
    from app.core.tarot import card_name
    lang = client.get("/api/user/profile", headers=auth(100)).json()["user"]["lang"]
    assert all(c["title"] == card_name(c["id"], lang) for c in t["cards"])
    s = client.post("/api/sphere", headers=auth(601), json={"question": "ვუყვარვარ?"}).json()   # own user: keeps 100's reward count
    assert s["topic"] == "love" and s["tone"] in ("yes", "wait", "no") and s["advice"] and s["answer"]


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
    assert r["chart"]["ascendant"]["d9"] and all(p["d9"] for p in r["chart"]["planets"])
    d = r["chart"]["dasha"]
    assert len(d["mahadashas"]) == 9 and len(d["antardashas"]) == 9 and d["current"]["maha"] and d["current"]["antar"]
    assert sum(p["current"] for p in d["mahadashas"]) == 1
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


def test_navamsa_and_dasha():
    from datetime import date, datetime, time, timezone
    from app.core.chart import Place, compute_chart, navamsa_sign
    assert navamsa_sign(0) == "Aries" and navamsa_sign(3.4) == "Taurus" and navamsa_sign(30) == "Capricorn"  # earth starts at Capricorn
    assert navamsa_sign(47.75) == "Gemini"  # Rohini pada 3
    c = compute_chart(date(1990, 8, 15), time(8, 0), Place("Tbilisi", 41.72, 44.78, "Asia/Tbilisi"),
                      datetime(2026, 10, 14, tzinfo=timezone.utc))
    d = c["dasha"]
    assert c["moon_nakshatra"]["name"] == "Rohini" and d["mahadashas"][0]["lord"] == "moon"  # Rohini is ruled by the Moon
    assert d["mahadashas"][0]["start"] == "1990-08-15" and d["mahadashas"][0]["end"].startswith("1994-10")
    assert d["current"] == {"maha": "jupiter", "maha_end": "2035-10-22", "antar": "ketu", "antar_end": "2027-09-04"}


def _db(fn):
    """Runs fn(session) on a separate engine (the app's pool lives in the TestClient's event loop)."""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.db import engine as app_engine

    async def go():
        eng = create_async_engine(app_engine.url)
        try:
            async with async_sessionmaker(eng, class_=AsyncSession)() as s:
                out = await fn(s)
                await s.commit()
                return out
        finally:
            await eng.dispose()
    return asyncio.run(go())


def test_sky(client):
    r = client.get("/api/sky", headers=auth(300))
    assert r.status_code == 200
    d = r.json()
    ids = [p["id"] for p in d["planets"]]
    assert ids == ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]
    for p in d["planets"]:
        assert 0 <= p["lon"] < 360 and 0 <= p["degree"] < 30 and p["sign"] in ("Aries", "Taurus", "Gemini", "Cancer", "Leo",
            "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces")
    assert not next(p for p in d["planets"] if p["id"] == "sun")["retro"]
    assert d["planet_of_day"] in ids and set(d["retrograde"]) <= set(ids)
    assert 0 <= d["moon"]["phase"] < 1 and 0 <= d["moon"]["illumination"] <= 100
    assert d["week"] == {"practices": 0, "streak": 0, "freeze_ready": True}
    assert client.get("/api/sky").status_code == 401


def test_sky_positions_known_date():
    from datetime import datetime, timezone
    from app.api.sky import sky_at
    d = sky_at(datetime(2024, 4, 8, 18, 0, tzinfo=timezone.utc))   # total solar eclipse: Sun and Moon together in Aries
    sun, moon, mercury = (next(p for p in d["planets"] if p["id"] == k) for k in ("sun", "moon", "mercury"))
    assert sun["sign"] == "Aries" and moon["sign"] == "Aries" and abs(sun["lon"] - moon["lon"]) < 1.5
    assert mercury["retro"] is True                                   # Mercury was retrograde (1-25 April 2024)
    assert d["moon"]["phase"] < 0.01 or d["moon"]["phase"] > 0.99    # new moon
    assert d["planet_of_day"] == "moon"                               # a Monday


def test_streak_freeze(client):
    from datetime import timedelta
    from sqlalchemy import update
    from app.models import User
    from app.services.economy import today_utc
    uid = 400
    client.post("/api/auth/verify", headers=auth(uid))

    def set_claim(days_ago, streak):
        async def fn(s):
            await s.execute(update(User).where(User.telegram_id == uid)
                            .values(last_daily_claim=today_utc() - timedelta(days=days_ago), streak=streak))
        _db(fn)

    set_claim(2, 5)   # missed yesterday
    p = client.get("/api/user/profile", headers=auth(uid)).json()["user"]
    assert p["streak"] == 5 and p["streak_freeze"] == {"ready": True, "saving": True}
    r = client.post("/api/user/daily-reward", headers=auth(uid)).json()["reward"]
    assert r["streak"] == 6 and r["freeze_used"] is True
    p = client.get("/api/user/profile", headers=auth(uid)).json()["user"]
    assert p["streak_freeze"] == {"ready": False, "saving": False}

    set_claim(2, 6)   # a second miss in the same week is not forgiven
    p = client.get("/api/user/profile", headers=auth(uid)).json()["user"]
    assert p["streak"] == 0 and p["streak_freeze"]["saving"] is False
    r = client.post("/api/user/daily-reward", headers=auth(uid)).json()["reward"]
    assert r["streak"] == 1 and r["freeze_used"] is False

    set_claim(1, 3)   # a normal day never spends anything
    r = client.post("/api/user/daily-reward", headers=auth(uid)).json()["reward"]
    assert r["streak"] == 4 and r["freeze_used"] is False


def test_share_image(client):
    png = _png()
    r = client.post("/api/share/image", headers=auth(100), files={"file": ("story.png", png, "image/png")})
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("https://astro.test/share/") and url.endswith(".png")
    img = client.get(url.replace("https://astro.test", ""))
    assert img.status_code == 200 and img.content == png and img.headers["content-type"] == "image/png"
    bad = client.post("/api/share/image", headers=auth(100), files={"file": ("x.png", b"<svg/>", "image/png")})
    assert bad.status_code == 415
    assert client.post("/api/share/image", files={"file": ("x.png", png, "image/png")}).status_code == 401
    assert client.get("/share/nope.png").status_code == 404


def test_profile_change_flows_everywhere(client):
    uid = 500
    v = client.post("/api/auth/verify", headers=auth(uid)).json()["user"]
    r = client.patch("/api/user/profile", headers=auth(uid), json={"birth_date": "1990-08-15"}).json()["user"]
    assert r["sign"]["id"] == "Leo" and r["life_path"] == 33   # 1+5+0+8+1+9+9+0 = 33, a master number
    # one user shape everywhere: PATCH, GET and verify return the same keys, streak fields included
    g = client.get("/api/user/profile", headers=auth(uid)).json()["user"]
    v2 = client.post("/api/auth/verify", headers=auth(uid)).json()["user"]
    assert set(r) == set(g) == set(v2) == set(v)
    for k in ("streak", "streak_freeze", "daily_reward_available", "sign", "life_path", "birth_date"):
        assert k in r
    assert client.get("/api/daily/energy", headers=auth(uid)).json()["sign"]["id"] == "Leo"
    assert client.get("/api/horoscope?period=day", headers=auth(uid)).json()["sign"]["id"] == "Leo"

    r = client.patch("/api/user/profile", headers=auth(uid),
                     json={"birth_date": "1995-03-14", "birth_time": "08:15", "birth_city": "Tbilisi"}).json()["user"]
    assert r["sign"]["id"] == "Pisces" and r["life_path"] == 5   # 1+4+0+3+1+9+9+5 = 32 -> 5
    assert (r["birth_time"], r["birth_city"]) == ("08:15", "Tbilisi")
    g = client.get("/api/user/profile", headers=auth(uid)).json()["user"]
    assert g["sign"]["id"] == "Pisces" and g["birth_date"] == "1995-03-14" and g["life_path"] == 5
    e = client.get("/api/daily/energy", headers=auth(uid)).json()
    assert e["sign"]["id"] == "Pisces"
    assert client.get("/api/horoscope?period=day", headers=auth(uid)).json()["sign"]["id"] == "Pisces"
    sky = client.get("/api/sky", headers=auth(uid))
    assert sky.status_code == 200 and sky.json()["week"]["streak"] == g["streak"]


def test_profile_rejects_invalid_dates(client):
    from datetime import timedelta
    from app.services.economy import today_utc
    uid = 501
    client.post("/api/auth/verify", headers=auth(uid))
    client.patch("/api/user/profile", headers=auth(uid), json={"birth_date": "1990-08-15"})
    for bad in ("1899-12-31", (today_utc() + timedelta(days=1)).isoformat(), "2001-02-30", "15.08.1990", ""):
        r = client.patch("/api/user/profile", headers=auth(uid), json={"birth_date": bad})
        assert r.status_code == 422, bad
        assert "birth_date" in str(r.json()["detail"]), bad
    assert "between 1900-01-01 and today" in str(client.patch("/api/user/profile", headers=auth(uid),
                                                              json={"birth_date": "1899-12-31"}).json()["detail"])
    assert client.patch("/api/user/profile", headers=auth(uid), json={"birth_time": "25:61"}).status_code == 422
    # nothing changed after the rejected requests
    assert client.get("/api/user/profile", headers=auth(uid)).json()["user"]["birth_date"] == "1990-08-15"


def test_purge_cache_command(client, monkeypatch):
    """/purge_cache reports failing shared AI texts; /purge_cache apply deletes exactly those; history stays."""
    import asyncio
    from datetime import date
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.bot import handlers
    from app.db import engine as app_engine
    from app.models import AICache, Reading, User

    loop_ka = " ".join(["შთამაგლუვება მოგიტანს სიმშვიდეს და შთამაგლუვება გაძლიერებს"] * 8)
    good_ka = {"quote": "რაც შენია, თავის დროზე შენამდე მოვა.", "affirmation": "მე ვენდობი საკუთარ გზას.", "focus": "მოთმინება"}

    class Msg:
        def __init__(self):
            self.replies = []

        async def answer(self, text, **kw):
            self.replies.append(text)

    class Cmd:
        def __init__(self, args):
            self.args = args

    async def go():
        eng = create_async_engine(app_engine.url)
        maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr(handlers, "SessionLocal", maker)
        try:
            async with maker() as s:
                s.add(User(telegram_id=700, lang="ka"))
                s.add_all([AICache(kind="energy", cache_key="T-good", payload=good_ka),
                           AICache(kind="horoscope", cache_key="T-bad", payload={"summary": loop_ka, "advice": "ok"})])
                await s.flush()
                s.add(Reading(user_id=700, kind="tarot", variant="daily", day=date(2026, 10, 20), payload={"cards": [{"interpretation": loop_ka}]}))
                await s.commit()
            dry = Msg()
            await handlers.cmd_purge_cache(dry, Cmd(None))
            async with maker() as s:
                left = set(await s.scalars(select(AICache.cache_key).where(AICache.cache_key.in_(["T-good", "T-bad"]))))
            assert left == {"T-good", "T-bad"}                    # dry run deletes nothing
            assert "horoscope/ka: 1" in dry.replies[0] and "Dry run" in dry.replies[0]
            done = Msg()
            await handlers.cmd_purge_cache(done, Cmd("apply"))
            async with maker() as s:
                left = set(await s.scalars(select(AICache.cache_key).where(AICache.cache_key.in_(["T-good", "T-bad"]))))
                readings = await s.scalar(select(func.count()).select_from(Reading).where(Reading.user_id == 700))
            assert left == {"T-good"} and readings == 1            # only the bad shared row is gone
            assert "Deleted " in done.replies[0]   # other rows from earlier tests (English mock text in ka) may fail too
        finally:
            await eng.dispose()
    asyncio.run(go())


def test_personal_horoscope_and_generic_fallback(client):
    uid = 800
    client.post("/api/auth/verify", headers=auth(uid))
    # no birth date: the generic sign reading still works
    r = client.get("/api/horoscope?period=day&sign=Leo", headers=auth(uid)).json()
    assert r["personal"] is False and r["horoscope"]["sections"]
    e = client.get("/api/daily/energy", headers=auth(uid)).json()
    assert e["personal"] is False and e["why"] is None
    # with birth data: a personal reading with real transit labels as "why" chips
    client.patch("/api/user/profile", headers=auth(uid), json={"birth_date": "1990-08-15", "birth_time": "08:00", "birth_city": "Tbilisi", "lang": "en"})
    r = client.get("/api/horoscope?period=day", headers=auth(uid)).json()
    assert r["personal"] is True and r["is_own_sign"]
    h = r["horoscope"]
    assert h["transits"] and all(t["nature"] in ("harmonious", "challenging", "blend") for t in h["transits"])
    assert all(s["why"][0] == h["transits"][0]["label"] for s in h["sections"])   # mock cites T1 -> its exact label
    assert all(c == h["transits"][0]["dignity"] for s in h["sections"] for c in s["why"][1:])   # + its dignity chip
    assert "your" in h["transits"][0]["label"]
    again = client.get("/api/horoscope?period=day", headers=auth(uid)).json()
    assert again["horoscope"] == h                                             # cached
    other = client.get("/api/horoscope?period=day&sign=Aries", headers=auth(uid)).json()
    assert other["personal"] is False                                          # someone else's sign: generic
    e = client.get("/api/daily/energy", headers=auth(uid)).json()
    assert e["personal"] is True and "your" in e["why"]


def _rows(kind: str) -> int:
    import asyncio
    from sqlalchemy import func, select
    from app.db import SessionLocal
    from app.models import AICache

    async def q():
        async with SessionLocal() as s:
            return await s.scalar(select(func.count()).select_from(AICache).where(AICache.kind == kind))
    return asyncio.run(q())


def test_personal_text_is_shared_by_matching_transits(client):
    """Two people with the same top transits (here: the same birth data) cost one AI call, not two."""
    body = {"birth_date": "1985-03-02", "birth_time": "14:30", "birth_city": "Tbilisi", "lang": "ru"}
    for uid in (810, 811):
        client.post("/api/auth/verify", headers=auth(uid))
        client.patch("/api/user/profile", headers=auth(uid), json=body)
    before = _rows("horoscope_personal")
    a = client.get("/api/horoscope?period=week", headers=auth(810)).json()
    assert _rows("horoscope_personal") == before + 1
    b = client.get("/api/horoscope?period=week", headers=auth(811)).json()
    assert a["personal"] and b["personal"] and _rows("horoscope_personal") == before + 1
    assert a["horoscope"]["sections"] == b["horoscope"]["sections"]


def test_personal_quota_and_ai_failure_fall_back_to_the_sign_text(client, monkeypatch):
    from app.ai import provider
    from app.services import economy
    uid = 820
    client.post("/api/auth/verify", headers=auth(uid))
    client.patch("/api/user/profile", headers=auth(uid), json={"birth_date": "1979-11-30", "lang": "en"})
    # 1) the daily cap is reached: no new personal text, the shared sign horoscope instead
    monkeypatch.setitem(economy.AI_DAILY_CAPS, "horoscope", 0)
    monkeypatch.setitem(economy.AI_DAILY_CAPS, "energy", 0)
    r = client.get("/api/horoscope?period=month", headers=auth(uid)).json()
    assert r["personal"] is False and r["is_own_sign"] and r["horoscope"]["sections"]
    assert client.get("/api/daily/energy", headers=auth(uid)).json()["personal"] is False
    # 2) the cap allows it but the AI (e.g. Groq's own rate limit) fails on the personal prompt
    monkeypatch.setitem(economy.AI_DAILY_CAPS, "horoscope", 40)
    real = provider.get_ai()

    class PersonalFails:
        async def complete_json(self, system, user, schema, **kw):
            if "T1:" in user or "transiting" in user:
                raise provider.AIError("rate limited")
            return await real.complete_json(system, user, schema, **kw)
    monkeypatch.setattr(provider, "_provider", PersonalFails())
    r = client.get("/api/horoscope?period=month", headers=auth(uid)).json()
    assert r["personal"] is False and r["horoscope"]["sections"]


def test_ai_call_counters_have_no_user_data(client):
    import asyncio
    from app.ai import stats
    from app.services.diag import format_report  # noqa: F401  (diag imports stats)
    uid = 830
    client.post("/api/auth/verify", headers=auth(uid))
    client.get("/api/horoscope?period=day&sign=Virgo", headers=auth(uid))   # may be cached; force one call:
    from app.ai.prompts import EnergyAI

    async def one_call():
        await stats.CountingProvider(provider_mock()).complete_json("Output language code: ka", "x", EnergyAI)
        await stats.flush()
        return await stats.today()
    today = asyncio.run(one_call())
    assert today.get("call:EnergyAI.ka", 0) >= 1
    assert all(k == "requests" or k.startswith("call:") for k in today)       # only feature names and counts
    assert "AI calls" in stats.format_line(today)


def provider_mock():
    from app.ai.provider import MockProvider
    return MockProvider()


def test_cache_version_and_purge_old(client, monkeypatch):
    """Every shared AI text is stored under the current version; /purge_cache old counts and deletes the older
    rows only (not geocoding, not the AI counters, never user readings)."""
    import asyncio
    from datetime import date
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.bot import handlers
    from app.db import engine as app_engine
    from app.models import AICache, Reading, User
    from app.services.content import CACHE_VERSION, vkey

    uid = 840
    client.post("/api/auth/verify", headers=auth(uid))
    client.patch("/api/user/profile", headers=auth(uid), json={"birth_date": "1992-02-11", "lang": "ka"})
    client.get("/api/numerology", headers=auth(uid))
    client.get("/api/moon/ritual", headers=auth(uid))
    assert vkey("numerology", "lp:1:ka") == f"{CACHE_VERSION}:lp:1:ka" and vkey("geo", "tbilisi") == "tbilisi"

    class Msg:
        def __init__(self):
            self.replies = []

        async def answer(self, text, **kw):
            self.replies.append(text)

    class Cmd:
        def __init__(self, args):
            self.args = args

    async def go():
        eng = create_async_engine(app_engine.url)
        maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr(handlers, "SessionLocal", maker)
        try:
            async with maker() as s:
                new_keys = set(await s.scalars(select(AICache.cache_key).where(AICache.kind.in_(["numerology", "moon", "pyear"]))))
                assert new_keys and all(k.startswith(f"{CACHE_VERSION}:") for k in new_keys)
                s.add(User(telegram_id=841, lang="ka"))
                s.add_all([AICache(kind="numerology", cache_key="lp:7:ka", payload={"title": "old"}),
                           AICache(kind="compat", cache_key="Leo:Aries:ka", payload={"title": "old"}),
                           AICache(kind="geo", cache_key="old-city", payload={"lat": 1}),
                           AICache(kind="ai_stats", cache_key="2026-10-19", payload={"requests": 3})])
                await s.flush()
                s.add(Reading(user_id=841, kind="numerology", variant="lp", day=date(2026, 10, 20), payload={"title": "old"}))
                await s.commit()
            dry = Msg()
            await handlers.cmd_purge_cache(dry, Cmd("old"))
            assert "numerology: 1" in dry.replies[0] and "compat: 1" in dry.replies[0] and "Dry run" in dry.replies[0]
            assert "geo" not in dry.replies[0] and "ai_stats" not in dry.replies[0]
            done = Msg()
            await handlers.cmd_purge_cache(done, Cmd("old apply"))
            async with maker() as s:
                keys = set(await s.scalars(select(AICache.cache_key)))
                readings = await s.scalar(select(func.count()).select_from(Reading).where(Reading.user_id == 841))
            assert "lp:7:ka" not in keys and "Leo:Aries:ka" not in keys            # old texts gone
            assert {"old-city", "2026-10-19"} <= keys and new_keys <= keys          # geo, counters, v2 texts kept
            assert readings == 1 and "Deleted " in done.replies[0]                 # history untouched
            again = Msg()
            await handlers.cmd_purge_cache(again, Cmd("old"))
            assert "Nothing to delete" in again.replies[0]                          # every pre-v2 text is gone
        finally:
            await eng.dispose()
    asyncio.run(go())
