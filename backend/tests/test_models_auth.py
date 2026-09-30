import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import AuthSession, EmailCode, EmailLog, Favorite, KnownDevice
from tests.factories import make_security, make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_user_has_uuid_and_defaults(db):
    user = make_user(db, "jean@example.com")
    assert isinstance(user.id, uuid.UUID)
    assert user.role == "user" and user.is_premium is False and user.failed_logins == 0
    assert user.email_verified_at is not None


def test_deleting_user_cascades(db):
    user = make_user(db, "jean@example.com")
    security = make_security(db, "MC.PA")
    db.add_all([
        Favorite(user_id=user.id, security_id=security.id),
        AuthSession(user_id=user.id, token_hash="a" * 64, csrf_token="c", device="Chrome sur Windows",
                    persistent=True, last_seen_at=NOW, expires_at=NOW + timedelta(days=30)),
        KnownDevice(user_id=user.id, token_hash="b" * 64),
        EmailCode(user_id=user.id, purpose="verify_email", code_hash="d" * 64, expires_at=NOW),
    ])
    log = EmailLog(user_id=user.id, kind="welcome", recipient=user.email, subject="s", html="h", text="t")
    db.add(log)
    db.flush()
    db.delete(user)
    db.flush()
    for model in (Favorite, AuthSession, KnownDevice, EmailCode):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    db.refresh(log)
    assert log.user_id is None  # l'historique d'envoi survit, sans lien vers le compte
