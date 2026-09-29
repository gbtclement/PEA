from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from app.models import EmailLog, SecurityEvent, User
from app.services.auth.sessions import SESSION_COOKIE
from tests.factories import make_user


@pytest.fixture(autouse=True)
def app_secret(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "app_secret", "secret-de-test")


def _start(client, suite="/portefeuille"):
    response = client.get("/api/auth/google/start", params={"suite": suite, "remember": "1"}, follow_redirects=False)
    assert response.status_code == 302
    return parse_qs(urlsplit(response.headers["location"]).query)["state"][0]


def _callback(client, state, code="bon-code"):
    return client.get("/api/auth/google/callback", params={"state": state, "code": code}, follow_redirects=False)


def test_config_tells_the_frontend_what_is_enabled(anon_client):
    assert anon_client.get("/api/auth/config").json() == {"google": True, "turnstile_site_key": None}


def test_known_google_account_signs_in_and_goes_back(anon_client, db):
    user = make_user(db, "jean@gmail.com")
    user.google_sub = "google-123"
    db.flush()
    back = _callback(anon_client, _start(anon_client))
    assert back.status_code == 302 and back.headers["location"] == "/portefeuille"
    assert anon_client.cookies.get(SESSION_COOKIE)
    assert "login_ok" in [e.kind for e in db.scalars(select(SecurityEvent))]


def test_existing_address_is_linked_with_an_alert(anon_client, db):
    user = make_user(db, "jean@gmail.com")
    _callback(anon_client, _start(anon_client))
    assert user.google_sub == "google-123"
    alert = db.scalars(select(EmailLog).where(EmailLog.kind == "security_alert")).one()
    assert "Google" in alert.text


def test_linking_an_unverified_account_drops_its_password(anon_client, db):
    squatter = make_user(db, "jean@gmail.com", password="mot-de-passe-du-squatteur", verified=False)
    _callback(anon_client, _start(anon_client))
    assert squatter.email_verified_at is not None and squatter.password_hash is None


def test_new_google_account_is_created_only_after_finishing(anon_client, db, fake_google):
    back = _callback(anon_client, _start(anon_client))
    assert back.headers["location"] == "/finaliser-inscription"
    assert db.scalars(select(User)).all() == []
    assert anon_client.get("/api/auth/google/pending").json() == {"email": "jean@gmail.com", "first_name": "Jean",
                                                                   "last_name": "Dupont"}
    refused = anon_client.post("/api/auth/google/complete", json={"first_name": "Jean", "last_name": "Dupont",
                                                                  "accept_terms": False})
    assert refused.status_code == 422
    done = anon_client.post("/api/auth/google/complete", json={"first_name": "Jeannot", "last_name": "Dupont",
                                                               "accept_terms": True})
    assert done.status_code == 200 and done.json()["first_name"] == "Jeannot"
    user = db.scalars(select(User)).one()
    assert (user.google_sub, user.password_hash, user.terms_version is not None) == ("google-123", None, True)
    assert anon_client.get("/api/auth/google/pending").status_code == 404  # cookie consommé


def test_unverified_google_address_is_refused(anon_client, db, fake_google):
    from dataclasses import replace

    fake_google.identity = replace(fake_google.identity, email_verified=False)
    back = _callback(anon_client, _start(anon_client))
    assert back.headers["location"] == "/connexion?erreur=google_email"
    assert db.scalars(select(User)).all() == []


def test_callback_refuses_missing_or_mismatched_state(anon_client, db):
    make_user(db, "jean@gmail.com").google_sub = "google-123"
    db.flush()
    state = _start(anon_client)
    assert _callback(anon_client, "autre-state").headers["location"] == "/connexion?erreur=google"
    anon_client.cookies.clear()
    assert _callback(anon_client, state).headers["location"] == "/connexion?erreur=google"  # plus de cookie
    assert _callback(anon_client, _start(anon_client), code="mauvais-code").headers["location"] == "/connexion?erreur=google"
    assert anon_client.cookies.get(SESSION_COOKIE) is None


def test_state_cookie_cannot_be_replayed(anon_client, db):
    make_user(db, "jean@gmail.com").google_sub = "google-123"
    db.flush()
    state = _start(anon_client)
    oauth_cookie = anon_client.cookies.get("pea_oauth", path="/api/auth/google")
    assert _callback(anon_client, state).headers["location"] == "/portefeuille"
    anon_client.cookies.clear()
    anon_client.cookies.set("pea_oauth", oauth_cookie, path="/api/auth/google")
    assert _callback(anon_client, state).headers["location"] == "/connexion?erreur=google"


@pytest.mark.parametrize("suite", ["//evil.com", "https://evil.com", "/\\evil.com", ""])
def test_google_suite_is_kept_only_for_internal_paths(anon_client, db, suite):
    make_user(db, "jean@gmail.com").google_sub = "google-123"
    db.flush()
    assert _callback(anon_client, _start(anon_client, suite=suite)).headers["location"] == "/"


def test_google_is_404_when_not_configured(anon_client):
    from app.api.deps import get_google_client

    anon_client.app.dependency_overrides[get_google_client] = lambda: None
    assert anon_client.get("/api/auth/google/start").status_code == 404
    assert anon_client.get("/api/auth/config").json()["google"] is False
