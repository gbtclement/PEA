from datetime import UTC, datetime

import pytest

from app.core.config import get_settings
from app.models import AiUsage, Conversation
from app.repositories.app_settings import get_app_settings
from app.services.assistant.usage import add_cost, month_key, month_spent
from tests.fake_llm import text_turn

KEY = "sk-ant-test-1234567890abcdef"


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", KEY)


def this_month() -> str:
    return month_key(datetime.now(UTC))


def test_non_premium_sees_why_and_is_refused(client):
    status = client.get("/api/assistant/status").json()
    assert (status["available"], status["reason"]) == (False, "premium")
    for response in (client.get("/api/assistant/conversations"), client.post("/api/assistant/conversations", json={})):
        assert response.status_code == 403 and response.json()["detail"]["code"] == "premium_required"


def test_admin_is_always_premium(admin_client):
    assert admin_client.get("/api/assistant/status").json()["available"] is True
    assert admin_client.get("/api/assistant/conversations").status_code == 200


def test_premium_without_key_is_not_configured(client, user, monkeypatch):
    user.is_premium = True
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    assert client.get("/api/assistant/status").json()["reason"] == "not_configured"


def test_status_shows_spend_limit_and_model_label(client, db, user):
    user.is_premium = True
    get_app_settings(db).ai_model = "claude-sonnet-5"
    db.add(AiUsage(user_id=user.id, month=this_month(), cost_usd=1.25))
    db.flush()
    response = client.get("/api/assistant/status")
    assert response.json() == {"available": True, "reason": None, "spent_usd": 1.25, "limit_usd": 5.0,
                               "model": "Claude Sonnet 5 (plus rapide)"}
    assert KEY not in response.text


def test_limit_reached_refuses_new_questions(client, db, user, fake_llm):
    user.is_premium = True
    get_app_settings(db).ai_monthly_cost_limit_usd = 2.0
    db.add(AiUsage(user_id=user.id, month=this_month(), cost_usd=2.0))
    db.add(AiUsage(user_id=user.id, month="2000-01", cost_usd=99.0))  # un ancien mois ne compte pas
    db.flush()
    assert client.get("/api/assistant/status").json()["reason"] == "limit_reached"
    cid = client.post("/api/assistant/conversations", json={}).json()["id"]
    response = client.post(f"/api/assistant/conversations/{cid}/messages", json={"content": "Bonjour"})
    assert response.status_code == 429 and response.json()["detail"]["code"] == "ai_limit_reached"
    assert fake_llm.calls == []


def test_each_reply_adds_to_the_month(client, db, user, fake_llm):
    user.is_premium = True
    fake_llm.turns = [text_turn("Bonjour", input_tokens=1000, output_tokens=2000)]
    cid = client.post("/api/assistant/conversations", json={}).json()["id"]
    client.post(f"/api/assistant/conversations/{cid}/messages", json={"content": "Salut"})
    assert month_spent(db, user.id, datetime.now(UTC)) == pytest.approx(0.001 * 5 + 0.002 * 25, abs=1e-4)


def test_deleting_conversations_does_not_reset_the_spend(client, db, user):
    user.is_premium = True
    conv = Conversation(user_id=user.id, title="x", cost_usd=3.0)
    db.add(conv)
    add_cost(db, user.id, 3.0, datetime.now(UTC))
    db.flush()
    assert client.delete(f"/api/assistant/conversations/{conv.id}").status_code == 204
    assert month_spent(db, user.id, datetime.now(UTC)) == 3.0


def test_month_follows_paris_time():
    assert month_key(datetime(2026, 9, 30, 22, 30, tzinfo=UTC)) == "2026-10"  # 0 h 30 à Paris
