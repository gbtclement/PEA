from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.jobs.privacy import build_pending_exports
from app.models import DataExport, EmailLog
from app.services.mail.outbox import enqueue
from app.services.privacy.erasure import ERASED_ACCOUNT, email_fingerprint, erase_account
from app.services.privacy.retention import run_retention
from tests.auth_helpers import sign_in
from tests.factories import make_user

NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def test_failing_export_is_marked_failed_and_the_others_are_built(db, user, make_ctx, monkeypatch):
    from app.jobs import privacy

    other = make_user(db, "autre@example.com")
    db.add_all([DataExport(user_id=user.id, created_at=NOW), DataExport(user_id=other.id, created_at=NOW)])
    db.flush()
    real = privacy.build_export

    def flaky(db, u, now):
        if u.id == user.id:
            raise ValueError("boum")
        return real(db, u, now)

    monkeypatch.setattr(privacy, "build_export", flaky)
    assert build_pending_exports(make_ctx(now=NOW)) == 1
    statuses = {row.user_id: row.status for row in db.scalars(select(DataExport))}
    assert statuses == {user.id: "failed", other.id: "ready"}


def test_a_failed_export_does_not_block_a_new_request(client, db, user):
    db.add(DataExport(user_id=user.id, created_at=datetime.now(UTC), status="failed"))
    db.flush()
    assert client.post("/api/me/export").status_code == 202


def test_only_one_pending_export_per_user(db, user):
    db.add_all([DataExport(user_id=user.id, created_at=NOW), DataExport(user_id=user.id, created_at=NOW)])
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_concurrent_request_gets_409(client, db, user, monkeypatch):
    from app.services.privacy import export

    db.add(DataExport(user_id=user.id, created_at=datetime.now(UTC)))
    db.flush()
    monkeypatch.setattr(export, "latest_export", lambda db, u: None)  # l'autre requête n'a pas encore vu la ligne
    response = client.post("/api/me/export")
    assert response.status_code == 409 and response.json()["detail"]["code"] == "export_pending"


def test_stuck_pending_export_becomes_failed(db, user):
    row = DataExport(user_id=user.id, created_at=NOW - timedelta(hours=2))
    db.add(row)
    db.flush()
    run_retention(db, NOW)
    db.refresh(row)
    assert row.status == "failed"


def test_erasure_fingerprints_each_row_with_its_own_address_and_erases_bodies(db, user):
    enqueue(db, "welcome", to="ancienne@example.com", user_id=user.id, context={"first_name": "Moi"})
    enqueue(db, "welcome", to=user.email, user_id=user.id, context={"first_name": "Moi"})
    for row in db.scalars(select(EmailLog).where(EmailLog.user_id == user.id)):
        row.status = "sent"
    db.flush()
    ids = [row.id for row in db.scalars(select(EmailLog).where(EmailLog.user_id == user.id))]
    email = user.email
    erase_account(db, user, now=NOW)
    rows = {row.id: row for row in db.scalars(select(EmailLog).where(EmailLog.id.in_(ids)))}
    assert {row.recipient for row in rows.values()} == {email_fingerprint("ancienne@example.com"), email_fingerprint(email)}
    assert all(row.html == row.text == ERASED_ACCOUNT for row in rows.values())


def test_account_deleted_mail_stuck_without_smtp_loses_the_address(db):
    enqueue(db, "account_deleted", to="parti@example.com", context={"first_name": "Parti"})
    row = db.scalar(select(EmailLog).where(EmailLog.kind == "account_deleted"))
    row.created_at = NOW - timedelta(days=8)
    db.flush()
    run_retention(db, NOW)
    db.refresh(row)
    assert row.recipient == email_fingerprint("parti@example.com") and row.status == "failed"


def test_self_delete_counts_admins_with_the_locking_helper(client, db, user, monkeypatch):
    from app.api.routes import me

    user.role = "admin"
    make_user(db, "admin2@example.com", role="admin")
    monkeypatch.setattr(me, "count_admins", lambda db: 1)
    response = client.request("DELETE", "/api/me", json={"confirm_email": user.email, "password": "motdepasse-solide"})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "last_admin"


def test_admin_documentation_needs_current_terms(anon_client, db):
    admin = make_user(db, "chef@example.com", role="admin", terms_version="2020-01-01")
    sign_in(anon_client, db, admin)
    assert anon_client.get("/api/auth/admin-check").status_code == 401
