import pytest

from app.core.config import get_settings
from app.models import UserSettings


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_secret", "test-secret")
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")


def test_settings_default_not_configured(client):
    body = client.get("/api/assistant/settings").json()
    assert body["configured"] is False and body["source"] is None and body["model"] == "claude-opus-5"
    assert {"id": "claude-opus-5", "label": "Claude Opus 5 (recommandé)"} in body["models"]


def test_save_key_is_encrypted_and_never_returned(client, db):
    response = client.put("/api/assistant/settings", json={"api_key": "sk-ant-test-1234567890abcdef", "model": "claude-sonnet-5"})
    assert response.status_code == 200
    body = response.json()
    assert body == {**body, "configured": True, "source": "settings", "model": "claude-sonnet-5"}
    stored = db.query(UserSettings).one()
    assert stored.anthropic_key_enc and "sk-ant" not in stored.anthropic_key_enc


def test_settings_never_return_key(client):
    client.put("/api/assistant/settings", json={"api_key": "sk-ant-test-1234567890abcdef", "model": "claude-opus-5"})
    for response in (client.get("/api/assistant/settings"), client.get("/api/settings")):
        assert "sk-ant" not in response.text and "anthropic_key" not in response.text


def test_model_change_keeps_key_and_remove_key(client):
    client.put("/api/assistant/settings", json={"api_key": "sk-ant-test-1234567890abcdef", "model": "claude-opus-5"})
    assert client.put("/api/assistant/settings", json={"model": "claude-haiku-4-5"}).json()["configured"] is True
    body = client.put("/api/assistant/settings", json={"remove_key": True, "model": "claude-haiku-4-5"}).json()
    assert body["configured"] is False and body["model"] == "claude-haiku-4-5"


def test_env_key_is_used_when_none_saved(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-env-1234567890")
    assert client.get("/api/assistant/settings").json()["source"] == "env"


@pytest.mark.parametrize("payload", [
    {"api_key": "court", "model": "claude-opus-5"},
    {"api_key": "sk-ant avec espaces 1234567890", "model": "claude-opus-5"},
    {"model": "gpt-4"},
])
def test_invalid_payload_is_422(client, payload):
    assert client.put("/api/assistant/settings", json=payload).status_code == 422


def test_missing_app_secret_is_explained(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_secret", "")
    response = client.put("/api/assistant/settings", json={"api_key": "sk-ant-test-1234567890abcdef", "model": "claude-opus-5"})
    assert response.status_code == 503 and "APP_SECRET" in response.json()["detail"]
