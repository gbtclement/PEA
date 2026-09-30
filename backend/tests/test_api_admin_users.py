import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import AuthSession, EmailLog, Favorite, SecurityEvent, User
from app.services.auth.sessions import open_session
from tests.factories import make_security, make_user


def admin_of(db) -> User:
    return db.scalar(select(User).where(User.email == "admin@example.com"))


def mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind)).all()


def test_non_admin_gets_403_everywhere(client, db):
    other = make_user(db, "x@example.com")
    for method, path in (("GET", "/api/admin/users"), ("PATCH", f"/api/admin/users/{other.id}"),
                         ("DELETE", f"/api/admin/users/{other.id}")):
        response = client.request(method, path, json={})
        assert response.status_code == 403, path


def test_list_search_ignores_case_and_accents(admin_client, db):
    make_user(db, "helene@example.com", first_name="Hélène", last_name="Dupré")
    make_user(db, "paul@example.com", first_name="Paul", last_name="Martin")
    body = admin_client.get("/api/admin/users", params={"q": "HELENE"}).json()
    assert [u["email"] for u in body["items"]] == ["helene@example.com"] and body["total"] == 1
    assert admin_client.get("/api/admin/users", params={"q": "dupre"}).json()["total"] == 1
    assert admin_client.get("/api/admin/users", params={"q": "PAUL@EX"}).json()["total"] == 1
    assert admin_client.get("/api/admin/users", params={"q": "paul martin"}).json()["total"] == 1


def test_list_sorts_and_paginates_by_50(admin_client, db):
    for i in range(55):
        make_user(db, f"u{i:02d}@example.com", last_name=f"Nom{i:02d}")
    first = admin_client.get("/api/admin/users", params={"sort": "email", "order": "asc"}).json()
    assert (first["total"], first["page_size"], len(first["items"])) == (56, 50, 50)
    assert first["items"][0]["email"] == "admin@example.com"
    second = admin_client.get("/api/admin/users", params={"sort": "email", "order": "asc", "page": 2}).json()
    assert [u["email"] for u in second["items"]][-1] == "u54@example.com"
    assert admin_client.get("/api/admin/users", params={"sort": "password_hash"}).status_code == 422


def test_list_shows_methods_and_never_secrets(admin_client, db):
    google = make_user(db, "g@example.com", password=None)
    google.google_sub = "sub-123"
    db.flush()
    response = admin_client.get("/api/admin/users")
    row = next(u for u in response.json()["items"] if u["email"] == "g@example.com")
    assert (row["has_password"], row["has_google"], row["verified"]) == (False, True, True)
    assert "password_hash" not in response.text and "sub-123" not in response.text


def test_toggle_premium_sends_no_mail(admin_client, db):
    user = make_user(db, "p@example.com")
    body = admin_client.patch(f"/api/admin/users/{user.id}", json={"is_premium": True}).json()
    assert body["is_premium"] is True and mails(db, "security_alert") == []


def test_edit_names_alerts_the_user_and_is_logged(admin_client, db):
    user = make_user(db, "p@example.com")
    body = admin_client.patch(f"/api/admin/users/{user.id}", json={"first_name": " Paul ", "last_name": "Neuf"}).json()
    assert (body["first_name"], body["last_name"]) == ("Paul", "Neuf")
    assert [m.recipient for m in mails(db, "security_alert")] == ["p@example.com"]
    event = db.scalars(select(SecurityEvent).where(SecurityEvent.kind == "admin_user_updated")).one()
    assert event.user_id == user.id and event.actor_id == admin_of(db).id
    assert event.details == {"fields": ["first_name", "last_name"]}


def test_edit_email_marks_verified_and_alerts_both_addresses(admin_client, db):
    user = make_user(db, "old@example.com", verified=False)
    body = admin_client.patch(f"/api/admin/users/{user.id}", json={"email": "New@Example.com"}).json()
    assert body["email"] == "new@example.com" and body["verified"] is True
    assert sorted(m.recipient for m in mails(db, "security_alert")) == ["new@example.com", "old@example.com"]


@pytest.mark.parametrize("change", [{"role": "admin"}, {"email": "autre@example.com"}])
def test_role_or_email_change_signs_the_user_out(admin_client, db, change):
    user = make_user(db, "p@example.com")
    open_session(db, user, persistent=True, ip=None, user_agent="x", now=datetime.now(UTC), settings=get_settings())
    assert admin_client.patch(f"/api/admin/users/{user.id}", json=change).status_code == 200
    assert db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all() == []


def test_premium_or_name_change_keeps_the_sessions(admin_client, db):
    user = make_user(db, "p@example.com")
    open_session(db, user, persistent=True, ip=None, user_agent="x", now=datetime.now(UTC), settings=get_settings())
    admin_client.patch(f"/api/admin/users/{user.id}", json={"is_premium": True, "first_name": "Paul"})
    assert len(db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all()) == 1


def test_edit_email_to_a_taken_address_is_409(admin_client, db):
    user = make_user(db, "a1@example.com")
    make_user(db, "a2@example.com")
    response = admin_client.patch(f"/api/admin/users/{user.id}", json={"email": "a2@example.com"})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "email_taken"


def test_admin_guards(admin_client, db):
    me = admin_of(db)
    response = admin_client.patch(f"/api/admin/users/{me.id}", json={"role": "user", "first_name": "Changé"})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "self_demotion"
    db.refresh(me)
    assert (me.role, me.first_name) == ("admin", "Admin")  # rien n'est enregistré
    response = admin_client.request("DELETE", f"/api/admin/users/{me.id}", json={"confirm_email": me.email})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "self_delete"


def test_last_admin_cannot_be_demoted(admin_client, db):
    from app.services.admin.users import AdminError, update_user

    me = admin_of(db)
    other = make_user(db, "other-admin@example.com", role="admin")
    assert admin_client.patch(f"/api/admin/users/{other.id}", json={"role": "user"}).json()["role"] == "user"
    # Dernier admin : même par une autre voie que « soi-même », le rôle ne peut plus tomber à zéro.
    with pytest.raises(AdminError) as error:
        update_user(db, actor=other, target=me, changes={"role": "user"}, now=me.created_at)
    assert error.value.code == "last_admin"


def test_delete_requires_the_email_and_removes_everything(admin_client, db):
    user = make_user(db, "bye@example.com")
    security = make_security(db, "MC.PA")
    db.add(Favorite(user_id=user.id, security_id=security.id))
    db.flush()
    wrong = admin_client.request("DELETE", f"/api/admin/users/{user.id}", json={"confirm_email": "autre@example.com"})
    assert wrong.status_code == 400 and wrong.json()["detail"]["code"] == "confirm_mismatch"
    ok = admin_client.request("DELETE", f"/api/admin/users/{user.id}", json={"confirm_email": " BYE@example.com "})
    assert ok.status_code == 204
    db.expire_all()
    assert db.get(User, user.id) is None and db.scalars(select(Favorite)).all() == []
    deleted = mails(db, "account_deleted")
    assert [m.recipient for m in deleted] == ["bye@example.com"] and deleted[0].user_id is None
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.kind == "admin_user_deleted")).one()


def test_unknown_user_is_404(admin_client):
    assert admin_client.patch(f"/api/admin/users/{uuid.uuid4()}", json={"is_premium": True}).status_code == 404
