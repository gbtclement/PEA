from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import AiUsage, AuthSession, EmailLog, Favorite, Order, SecurityEvent, User
from app.services.auth.sessions import SESSION_COOKIE
from app.services.mail.outbox import enqueue, forget_secrets
from app.services.privacy.erasure import email_fingerprint
from tests.factories import make_security, make_user

PASSWORD = "motdepasse-solide"


def test_self_delete_needs_the_email_and_the_password(client, db, user):
    wrong_email = client.request("DELETE", "/api/me", json={"confirm_email": "autre@example.com", "password": PASSWORD})
    assert wrong_email.status_code == 400 and wrong_email.json()["detail"]["code"] == "confirm_mismatch"
    wrong_password = client.request("DELETE", "/api/me", json={"confirm_email": user.email, "password": "faux"})
    assert wrong_password.status_code == 400 and wrong_password.json()["detail"]["code"] == "wrong_password"
    assert db.get(User, user.id) is not None


def test_self_delete_erases_everything_and_anonymizes_logs(client, db, user):
    security = make_security(db, "AIR.PA")
    db.add_all([Favorite(user_id=user.id, security_id=security.id),
                AiUsage(user_id=user.id, month="2026-09", cost_usd=1.0)])
    enqueue(db, "welcome", to=user.email, user_id=user.id, context={"first_name": "Moi"})
    db.flush()
    user_id, email = user.id, user.email
    response = client.request("DELETE", "/api/me", json={"confirm_email": " MOI@example.com ", "password": PASSWORD})
    assert response.status_code == 204
    assert f"{SESSION_COOKIE}=" in response.headers["set-cookie"] and "Max-Age=0" in response.headers["set-cookie"]
    db.expire_all()
    assert db.get(User, user_id) is None
    for model in (Favorite, AiUsage, AuthSession, Order):
        assert db.scalars(select(model).where(model.user_id == user_id)).all() == [], model
    logs = db.scalars(select(EmailLog)).all()
    assert [(m.kind, m.recipient) for m in logs] == [("account_deleted", email)]  # « welcome » en attente retiré
    event = db.scalars(select(SecurityEvent).where(SecurityEvent.kind == "account_deleted")).one()
    assert event.user_id is None and email not in str(event.details)
    forget_secrets(logs[0])  # une fois C6 envoyé, l'adresse disparaît aussi de sa ligne
    assert logs[0].recipient == email_fingerprint(email)


def test_sent_mails_keep_their_line_with_a_fingerprint(client, db, user):
    row_id = enqueue(db, "welcome", to=user.email, user_id=user.id, context={"first_name": "Moi"})
    db.get(EmailLog, row_id).status = "sent"
    db.flush()
    client.request("DELETE", "/api/me", json={"confirm_email": user.email, "password": PASSWORD})
    db.expire_all()
    row = db.get(EmailLog, row_id)
    assert row.user_id is None and row.recipient == email_fingerprint("moi@example.com")


def test_google_account_without_password_must_have_signed_in_recently(client, db, user):
    user.password_hash, user.google_sub = None, "google-1"
    session = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).one()
    session.created_at = datetime.now(UTC) - timedelta(minutes=10)
    db.flush()
    stale = client.request("DELETE", "/api/me", json={"confirm_email": user.email})
    assert stale.status_code == 403 and stale.json()["detail"]["code"] == "reauth_required"
    session.created_at = datetime.now(UTC) - timedelta(minutes=2)
    db.flush()
    assert client.request("DELETE", "/api/me", json={"confirm_email": user.email}).status_code == 204


def test_last_admin_cannot_delete_itself(admin_client, db):
    admin = db.scalars(select(User).where(User.role == "admin")).one()
    response = admin_client.request("DELETE", "/api/me", json={"confirm_email": admin.email, "password": PASSWORD})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "last_admin"


def test_admin_deletion_uses_the_same_erasure(admin_client, db):
    target = make_user(db, "p@example.com")
    enqueue(db, "welcome", to=target.email, user_id=target.id, context={"first_name": "P"})
    db.flush()
    admin_client.request("DELETE", f"/api/admin/users/{target.id}", json={"confirm_email": "p@example.com"})
    assert [m.kind for m in db.scalars(select(EmailLog))] == ["account_deleted"]
