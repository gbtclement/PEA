from datetime import UTC, datetime

import pytest

from app.services.mail.render import KINDS, render

BASE = "https://pea-radar.example"
CONTEXTS = {
    "verify_code": {"first_name": "Jean", "code": "042917"},
    "welcome": {"first_name": "Jean"},
    "reset_password": {"first_name": "Jean", "token": "abc_123", "valid_minutes": 30},
    "security_alert": {"first_name": "Jean", "event": "password_reset"},
    "new_device": {"first_name": "Jean", "device": "Chrome sur Windows", "when": datetime(2026, 9, 28, 12, 5, tzinfo=UTC), "token": "tok"},
}


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_every_kind_renders_html_and_text(kind):
    mail = render(kind, CONTEXTS[kind], base_url=BASE)
    assert mail.subject and "Jean" in mail.text and "Jean" in mail.html
    assert "<" not in mail.text.replace("<https", "")  # texte brut, sans balise
    assert "pas un conseil" not in mail.text  # l'avertissement est réservé aux notifications (étape 5)


def test_code_is_in_subject_and_body():
    mail = render("verify_code", CONTEXTS["verify_code"], base_url=BASE)
    assert "042917" in mail.subject and "042917" in mail.html and "15 minutes" in mail.text


def test_links_use_public_base_url():
    assert f"{BASE}/reinitialiser?jeton=abc_123" in render("reset_password", CONTEXTS["reset_password"], base_url=BASE).text
    new_device = render("new_device", CONTEXTS["new_device"], base_url=BASE)
    assert f"{BASE}/ce-n-etait-pas-moi?jeton=tok" in new_device.html
    assert "28/09/2026 à 14:05" in new_device.text  # heure de Paris


def test_html_escapes_user_input():
    mail = render("welcome", {"first_name": "<script>alert(1)</script>"}, base_url=BASE)
    assert "<script>" not in mail.html and "&lt;script&gt;" in mail.html


def test_unknown_security_event_fails():
    with pytest.raises(KeyError):
        render("security_alert", {"first_name": "Jean", "event": "inconnu"}, base_url=BASE)


def test_long_reset_validity_is_shown_in_hours():
    mail = render("reset_password", {**CONTEXTS["reset_password"], "valid_minutes": 1440}, base_url=BASE)
    assert "24 heures" in mail.text and "24 heures" in mail.html
    assert "30 minutes" in render("reset_password", CONTEXTS["reset_password"], base_url=BASE).text
