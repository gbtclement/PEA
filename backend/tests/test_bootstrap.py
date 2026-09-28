from datetime import UTC, datetime

from sqlalchemy import select

from app.models import EmailLog, Favorite, User
from app.models.user import LEGACY_EMAIL
from app.services.auth.bootstrap import bootstrap_admin, ensure_user
from tests.factories import make_security, make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _legacy(db):
    return make_user(db, LEGACY_EMAIL, first_name="Moi", last_name="", password=None, role="admin", is_premium=True)


def test_admin_takes_over_moi_and_keeps_data(db):
    moi = _legacy(db)
    security = make_security(db, "MC.PA")
    db.add(Favorite(user_id=moi.id, security_id=security.id))
    db.flush()
    bootstrap_admin(db, " Clement@Example.com ", NOW)
    db.flush()
    assert moi.email == "clement@example.com" and moi.role == "admin"
    assert db.scalars(select(Favorite)).one().user_id == moi.id
    mails = db.scalars(select(EmailLog)).all()
    assert [m.kind for m in mails] == ["reset_password"] and mails[0].recipient == "clement@example.com"


def test_running_twice_sends_one_mail(db):
    _legacy(db)
    bootstrap_admin(db, "clement@example.com", NOW)
    bootstrap_admin(db, "clement@example.com", NOW)
    assert len(db.scalars(select(EmailLog)).all()) == 1


def test_existing_account_is_promoted(db):
    user = make_user(db, "clement@example.com")
    bootstrap_admin(db, "clement@example.com", NOW)
    assert user.role == "admin" and user.is_premium
    assert db.scalars(select(EmailLog)).all() == []  # il a déjà un mot de passe


def test_without_admin_email_nothing_changes(db):
    moi = _legacy(db)
    assert "ADMIN_EMAIL" in bootstrap_admin(db, "", NOW)
    assert moi.email == LEGACY_EMAIL


def test_ensure_user_creates_then_updates(db):
    user = ensure_user(db, email="e2e@pea-radar.test", password="motdepasse-e2e-123", first_name="Test",
                       last_name="E2E", admin=False, now=NOW)
    again = ensure_user(db, email="e2e@pea-radar.test", password="autre-mot-de-passe", first_name="Test",
                        last_name="E2E", admin=True, now=NOW)
    assert again.id == user.id and again.role == "admin" and again.email_verified_at == NOW
    assert len(db.scalars(select(User)).all()) == 1


def test_unverified_signup_with_admin_address_is_not_promoted(db):
    """Quelqu'un s'inscrit avec l'adresse de l'admin sans valider le code : il ne doit pas devenir admin."""
    moi = _legacy(db)
    squatter = make_user(db, "clement@example.com", password="mot-de-passe-du-squatteur", verified=False)
    squatter_id = squatter.id
    bootstrap_admin(db, "clement@example.com", NOW)
    db.flush()
    admin = db.scalars(select(User).where(User.email == "clement@example.com")).one()
    assert admin.id == moi.id and admin.role == "admin" and admin.password_hash is None
    assert db.get(User, squatter_id) is None
    assert [m.kind for m in db.scalars(select(EmailLog)).all()] == ["reset_password"]
