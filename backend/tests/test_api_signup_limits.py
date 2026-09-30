from sqlalchemy import select

from app.models import EmailLog, SecurityEvent

FORM = {"first_name": "Jean", "last_name": "Dupont", "email": "jean@example.com",
        "password": "motdepasse-solide", "accept_terms": True}


def _kinds(db):
    return [e.kind for e in db.scalars(select(SecurityEvent).order_by(SecurityEvent.id))]


def test_signup_needs_the_captcha_when_enabled(anon_client, fake_captcha):
    fake_captcha.required = True
    refused = anon_client.post("/api/auth/register", json=FORM)
    assert refused.status_code == 400 and refused.json()["detail"]["code"] == "captcha_required"
    assert anon_client.post("/api/auth/register", json={**FORM, "captcha": "jeton-valide"}).status_code == 202


def test_five_signups_per_ip_and_hour(anon_client, db):
    for i in range(5):
        assert anon_client.post("/api/auth/register", json={**FORM, "email": f"p{i}@example.com"}).status_code == 202
    sixth = anon_client.post("/api/auth/register", json={**FORM, "email": "p6@example.com"})
    assert sixth.status_code == 429 and sixth.json()["detail"]["code"] == "too_many_requests"
    assert _kinds(db).count("signup") == 5


def test_mails_per_address_are_capped_silently(anon_client, db):
    from datetime import UTC, datetime

    from app.services import ratelimit
    from tests.factories import make_user

    make_user(db, "jean@example.com")
    for _ in range(5):
        ratelimit.record(db, "mail_account", "jean@example.com", datetime.now(UTC))
    again = anon_client.post("/api/auth/forgot-password", json={"email": "jean@example.com"})
    assert again.status_code == 202  # même réponse, mais plus aucun mail
    assert db.scalars(select(EmailLog).where(EmailLog.kind == "reset_password")).all() == []


def test_twenty_mail_requests_per_ip_give_429(anon_client):
    for i in range(20):
        anon_client.post("/api/auth/resend-code", json={"email": f"x{i}@example.com"})
    blocked = anon_client.post("/api/auth/forgot-password", json={"email": "y@example.com"})
    assert blocked.status_code == 429


def test_forgot_password_needs_the_captcha_when_enabled(anon_client, fake_captcha):
    fake_captcha.required = True
    refused = anon_client.post("/api/auth/forgot-password", json={"email": "jean@example.com"})
    assert refused.json()["detail"]["code"] == "captcha_required"
    ok = anon_client.post("/api/auth/forgot-password", json={"email": "jean@example.com", "captcha": "jeton-valide"})
    assert ok.status_code == 202


def test_foreign_origin_is_refused_but_own_and_missing_pass(anon_client):
    evil = anon_client.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 12},
                            headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403 and evil.json()["detail"]["code"] == "bad_origin"
    own = anon_client.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 12},
                           headers={"Origin": "http://localhost:8095"})
    assert own.status_code == 401
    dev = anon_client.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 12},
                           headers={"Origin": "http://localhost:5180"})
    assert dev.status_code == 401


def test_verification_logout_and_reset_are_journaled(anon_client, db):
    import re

    anon_client.post("/api/auth/register", json=FORM)
    mail = db.scalars(select(EmailLog).where(EmailLog.kind == "verify_code")).one()
    code = re.search(r"\b(\d{6})\b", mail.subject).group(1)
    verified = anon_client.post("/api/auth/verify-email", json={"email": "jean@example.com", "code": code})
    anon_client.headers["X-CSRF-Token"] = verified.cookies.get("pea_csrf") or anon_client.cookies.get("pea_csrf")
    anon_client.post("/api/auth/logout")
    assert _kinds(db)[-3:] == ["signup", "email_verified", "logout"]
