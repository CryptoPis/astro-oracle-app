"""Run: pytest -q   (uses the mock AI provider and a throwaway SQLite DB)"""
import os
import tempfile
import time

_tmp = tempfile.mkdtemp()
os.environ.update({
    "BOT_TOKEN": "123456:TEST-TOKEN", "BOT_ENABLED": "false", "AI_PROVIDER": "mock",
    "DATABASE_URL": f"sqlite+aiosqlite:///{_tmp}/test.db", "ENV": "production",
    "PUBLIC_BASE_URL": "https://astro.test",
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
