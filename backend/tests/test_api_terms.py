import pytest
from sqlalchemy import select

from app.models import SecurityEvent, User
from app.services.auth.accounts import TERMS_VERSION


@pytest.fixture
def outdated(db, user):
    user.terms_version = "2026-09-28"
    db.flush()
    return user


def test_me_says_when_terms_are_outdated(client, outdated):
    assert client.get("/api/me").json()["terms_outdated"] is True


def test_up_to_date_account_is_not_outdated(client):
    assert client.get("/api/me").json()["terms_outdated"] is False


def test_outdated_terms_block_personal_routes_but_not_account_routes(client, outdated):
    for method, path in [("GET", "/api/orders"), ("PUT", "/api/favorites/1"), ("GET", "/api/settings"),
                         ("GET", "/api/assistant/status"), ("GET", "/api/portfolio")]:
        response = client.request(method, path)
        assert response.status_code == 403 and response.json()["detail"]["code"] == "terms_outdated", path
    for path in ["/api/me", "/api/me/sessions"]:
        assert client.get(path).status_code == 200, path


def test_accepting_updates_the_version_and_unblocks(client, db, outdated):
    refused = client.post("/api/me/accept-terms", json={"accept_terms": False})
    assert refused.status_code == 422
    body = client.post("/api/me/accept-terms", json={"accept_terms": True}).json()
    assert body["terms_outdated"] is False
    assert outdated.terms_version == TERMS_VERSION
    assert client.get("/api/orders").status_code == 200
    assert db.scalars(select(SecurityEvent.kind)).all() == ["terms_accepted"]


def test_admin_with_outdated_terms_is_blocked_too(admin_client, db):
    admin = db.scalars(select(User).where(User.role == "admin")).one()
    admin.terms_version = None
    db.flush()
    assert admin_client.get("/api/admin/users").json()["detail"]["code"] == "terms_outdated"
