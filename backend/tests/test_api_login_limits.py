from sqlalchemy import select

from app.models import SecurityEvent
from tests.factories import make_user


def _login(client, email="jean@example.com", password="mauvais-mot-de-passe", **extra):
    return client.post("/api/auth/login", json={"email": email, "password": password, **extra})


def test_ten_failures_lock_the_account_even_with_the_right_password(anon_client, db):
    user = make_user(db, "jean@example.com")
    for _ in range(10):
        assert _login(anon_client, captcha="jeton-valide").status_code == 401
    locked = _login(anon_client, password="motdepasse-solide", captcha="jeton-valide")
    assert locked.status_code == 429 and locked.json()["detail"]["code"] == "account_locked"
    assert user.locked_until is not None
    kinds = [e.kind for e in db.scalars(select(SecurityEvent).order_by(SecurityEvent.id))]
    assert kinds.count("login_failed") == 10 and kinds.count("locked") == 1


def test_lock_looks_the_same_for_unknown_addresses(anon_client, db):
    make_user(db, "jean@example.com")
    for email in ("jean@example.com", "personne@example.com"):
        for _ in range(10):
            _login(anon_client, email=email, captcha="jeton-valide")
    real = _login(anon_client, email="jean@example.com", captcha="jeton-valide")
    unknown = _login(anon_client, email="personne@example.com", captcha="jeton-valide")
    assert (real.status_code, real.json()) == (unknown.status_code, unknown.json())


def test_success_clears_the_failures_of_the_account(anon_client, db):
    make_user(db, "jean@example.com")
    for _ in range(2):
        _login(anon_client)
    assert _login(anon_client, password="motdepasse-solide").status_code == 200
    events = [e.kind for e in db.scalars(select(SecurityEvent))]
    assert "login_ok" in events
    # les 2 échecs sont oubliés : 2 nouveaux échecs ne demandent pas encore le captcha
    anon_client.cookies.clear()
    for _ in range(2):
        assert _login(anon_client).status_code == 401


def test_captcha_is_required_after_three_failures(anon_client, db, fake_captcha):
    fake_captcha.required = True
    make_user(db, "jean@example.com")
    for _ in range(3):
        assert _login(anon_client).status_code == 401
    refused = _login(anon_client, password="motdepasse-solide")
    assert refused.status_code == 400 and refused.json()["detail"]["code"] == "captcha_required"
    assert _login(anon_client, password="motdepasse-solide", captcha="jeton-valide").status_code == 200


def test_thirty_failures_from_one_ip_give_429(anon_client, db):
    for i in range(30):
        _login(anon_client, email=f"inconnu{i}@example.com", captcha="jeton-valide")
    blocked = _login(anon_client, email="autre@example.com", captcha="jeton-valide")
    assert blocked.status_code == 429 and blocked.json()["detail"]["code"] == "too_many_requests"
