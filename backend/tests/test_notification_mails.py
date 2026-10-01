import pytest
from sqlalchemy import select

from app.models import EmailLog
from app.services.mail.render import render
from app.services.notifications.send import notifications_ready, notify
from app.services.notifications.unsubscribe import read_token
from tests.test_mail_render import BASE, CONTEXTS


def test_notification_footer_has_manage_link_unsubscribe_and_warning():
    mail = render("daily_recap", CONTEXTS["daily_recap"], base_url=BASE)
    for body in (mail.html, mail.text):
        assert "Gérer mes notifications" in body
        assert "pas un conseil en investissement" in body
        assert "Ne plus recevoir ce mail" in body


def test_account_mails_keep_the_plain_footer():
    mail = render("welcome", CONTEXTS["welcome"], base_url=BASE)
    assert "Gérer mes notifications" not in mail.html and "Ne plus recevoir" not in mail.text


def test_french_number_formats():
    mail = render("daily_recap", CONTEXTS["daily_recap"], base_url=BASE)
    assert "12 345,60 €" in mail.text and "-0,97 %" in mail.text and "02/10/2026" in mail.text
    assert "+2,10 %" in mail.text
    assert "301,50 NOK" in render("price_alert", CONTEXTS["price_alert"], base_url=BASE).text


@pytest.mark.usefixtures("app_secret")
def test_notify_adds_unsubscribe_headers_and_dedupes(db, user):
    from app.core.config import get_settings

    assert notifications_ready()
    context = {"year": 2026, "count": 8, "min_orders": 12, "remaining": 4, "penalty_fee": 96.0}
    assert notify(db, user, "order_reminder", context, dedupe_key=f"order_reminder:{user.id}:2026-10") is not None
    assert notify(db, user, "order_reminder", context, dedupe_key=f"order_reminder:{user.id}:2026-10") is None
    row = db.scalar(select(EmailLog).where(EmailLog.kind == "order_reminder"))
    assert row.recipient == user.email and row.user_id == user.id
    assert row.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    link = row.headers["List-Unsubscribe"]
    assert link.startswith("<") and "/api/unsubscribe?jeton=" in link and "type=order_reminder" in link
    token = link.split("jeton=")[1].split("&")[0]
    assert read_token(token, get_settings().app_secret) == user.id
    assert "/desinscription?jeton=" in row.text and "/reglages#notifications" in row.text


def test_no_secret_no_notifications(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "app_secret", "")
    assert notifications_ready() is False
