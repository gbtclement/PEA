from sqlalchemy import select

from app.core.config import get_settings
from app.models import EmailLog, SecurityEvent


def test_settings_round_trip_and_are_logged(admin_client, db):
    body = admin_client.get("/api/admin/settings").json()
    assert (body["ai_model"], body["ai_monthly_cost_limit_usd"]) == ("claude-opus-5", 5.0)
    assert {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5 (économique)"} in body["models"]
    saved = admin_client.put("/api/admin/settings", json={"ai_model": "claude-haiku-4-5", "ai_monthly_cost_limit_usd": 12.5})
    assert saved.json()["ai_model"] == "claude-haiku-4-5" and saved.json()["ai_monthly_cost_limit_usd"] == 12.5
    event = db.scalars(select(SecurityEvent).where(SecurityEvent.kind == "admin_settings_updated")).one()
    assert event.details == {"ai_model": "claude-haiku-4-5", "ai_monthly_cost_limit_usd": 12.5}


def test_settings_validation(admin_client):
    for payload in ({"ai_model": "gpt-4", "ai_monthly_cost_limit_usd": 5},
                    {"ai_model": "claude-opus-5", "ai_monthly_cost_limit_usd": -1}):
        assert admin_client.put("/api/admin/settings", json=payload).status_code == 422


def test_config_status_never_shows_values(admin_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-secret-valeur-123")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_password", "mot-de-passe-smtp")
    monkeypatch.setattr(settings, "turnstile_secret_key", "")
    response = admin_client.get("/api/admin/config-status")
    body = response.json()
    assert (body["claude"], body["smtp"], body["turnstile"]) == (True, True, False)
    assert body["google"] is True  # fake_google branché par les tests
    for secret in ("sk-ant-secret-valeur-123", "smtp.example.com", "mot-de-passe-smtp"):
        assert secret not in response.text
    for path in ("/api/admin/settings", "/api/assistant/status"):
        assert "sk-ant-secret-valeur-123" not in admin_client.get(path).text


def test_test_email_goes_to_the_admin_only(admin_client, db):
    assert admin_client.post("/api/admin/test-email").status_code == 202
    assert [m.recipient for m in db.scalars(select(EmailLog).where(EmailLog.kind == "test"))] == ["admin@example.com"]


def test_non_admin_gets_403(client):
    for method, path in (("GET", "/api/admin/settings"), ("GET", "/api/admin/config-status"),
                         ("POST", "/api/admin/test-email")):
        assert client.request(method, path).status_code == 403


def test_admin_check_accepts_an_admin(admin_client):
    assert admin_client.get("/api/auth/admin-check").status_code == 204


def test_admin_check_refuses_a_user(client):
    assert client.get("/api/auth/admin-check").status_code == 401


def test_admin_check_refuses_a_visitor(anon_client):
    assert anon_client.get("/api/auth/admin-check").status_code == 401
