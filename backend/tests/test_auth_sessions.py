from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.current_user import get_now
from app.models import AuthSession
from app.services.auth.sessions import SESSION_COOKIE, open_session, resolve_session, revoke_user_sessions
from app.core.security import token_hash
from tests.auth_helpers import sign_in
from tests.factories import make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
SETTINGS = Settings(session_days=30, session_short_hours=12)


def test_open_session_stores_only_a_hash(db):
    user = make_user(db)
    new = open_session(db, user, persistent=True, ip="203.0.113.9", user_agent=None, now=NOW, settings=SETTINGS)
    assert new.session.token_hash == token_hash(new.token) and new.token not in new.session.token_hash
    assert new.session.ip == "203.0.113.0/24" and new.session.expires_at == NOW + timedelta(days=30)
    assert user.last_login_at == NOW


def test_short_session_and_sliding_expiry(db):
    user = make_user(db)
    new = open_session(db, user, persistent=False, ip=None, user_agent=None, now=NOW, settings=SETTINGS)
    assert new.session.expires_at == NOW + timedelta(hours=12)
    later = NOW + timedelta(hours=11)
    assert resolve_session(db, new.token, now=later, settings=SETTINGS) is not None
    assert new.session.expires_at == later + timedelta(hours=12)  # prolongée à chaque activité
    assert resolve_session(db, new.token, now=later + timedelta(hours=13), settings=SETTINGS) is None


def test_resolve_rejects_unknown_and_revoked(db):
    user = make_user(db)
    new = open_session(db, user, persistent=True, ip=None, user_agent=None, now=NOW, settings=SETTINGS)
    assert resolve_session(db, "inconnu", now=NOW, settings=SETTINGS) is None
    assert resolve_session(db, None, now=NOW, settings=SETTINGS) is None
    revoke_user_sessions(db, user.id)
    assert resolve_session(db, new.token, now=NOW, settings=SETTINGS) is None


def test_me_requires_a_session(anon_client):
    response = anon_client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"


def test_me_returns_the_signed_in_user(anon_client, db):
    user = make_user(db, "jean@example.com", first_name="Jean")
    sign_in(anon_client, db, user)
    body = anon_client.get("/api/me").json()
    assert body == {"id": str(user.id), "email": "jean@example.com", "first_name": "Jean", "last_name": "Dupont",
                    "role": "user", "is_premium": False, "has_password": True, "has_google": False,
                    "has_premium": False, "premium_source": "none", "terms_outdated": False}
    assert "password_hash" not in body


def test_expired_session_is_401(anon_client, db):
    user = make_user(db)
    sign_in(anon_client, db, user, persistent=False)
    anon_client.app.dependency_overrides[get_now] = lambda: datetime.now(UTC) + timedelta(days=2)
    assert anon_client.get("/api/me").status_code == 401
