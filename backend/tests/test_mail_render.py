from datetime import UTC, date, datetime

import pytest

from app.services.mail.render import KINDS, render

BASE = "https://pea-radar.example"
PREMIUM = {"first_name": "Jean", "interval_label": "annuel", "period_end": date(2026, 11, 1), "ends_on": date(2026, 11, 1),
                "renews_on": "01/11/2026", "amount": "49,00 €", "manage_url": "m", "premium_url": "p", "cgv_url": "c"}
CONTEXTS = {
    "verify_code": {"first_name": "Jean", "code": "042917"},
    "welcome": {"first_name": "Jean"},
    "reset_password": {"first_name": "Jean", "token": "abc_123", "valid_minutes": 30},
    "security_alert": {"first_name": "Jean", "event": "password_reset"},
    "new_device": {"first_name": "Jean", "device": "Chrome sur Windows", "when": datetime(2026, 9, 28, 12, 5, tzinfo=UTC), "token": "tok"},
    "account_deleted": {"first_name": "Jean"},
    "inactivity_warning": {"first_name": "Jean", "delete_on": datetime(2029, 12, 31, 3, 30, tzinfo=UTC)},
    "data_export_ready": {"first_name": "Jean", "expires_at": datetime(2026, 10, 8, 8, 0, tzinfo=UTC)},
    "test": {"first_name": "Jean"},
    "price_move": {"first_name": "Jean", "threshold": 5.0, "unsubscribe_url": "u", "manage_url": "m",
                   "items": [{"security_id": 1, "name": "LVMH", "change_pct": 6.25, "price": 612.4, "currency": "EUR"}]},
    "price_alert": {"first_name": "Jean", "security_id": 1, "name": "Equinor", "direction": "above", "target": 300.0,
                    "price": 301.5, "currency": "NOK", "unsubscribe_url": "u", "manage_url": "m"},
    "daily_recap": {"first_name": "Jean", "day": date(2026, 10, 2), "has_portfolio": True, "total_value": 12345.6,
                    "day_change": -120.5, "day_change_pct": -0.97, "unsubscribe_url": "u", "manage_url": "m",
                    "gainers": [{"security_id": 1, "name": "LVMH", "change_pct": 2.1}],
                    "losers": [{"security_id": 2, "name": "Kering", "change_pct": -3.4}]},
    "weekly_recap": {"first_name": "Jean", "week_end": date(2026, 10, 3), "has_portfolio": True, "total_value": 12345.6,
                     "week_change": 210.0, "week_change_pct": 1.73, "entered": [{"security_id": 1, "name": "LVMH"}],
                     "left": [{"security_id": 2, "name": "Kering"}], "forecasts_checked": 10, "forecasts_right": 6,
                     "unsubscribe_url": "u", "manage_url": "m"},
    "order_reminder": {"first_name": "Jean", "year": 2026, "count": 8, "min_orders": 12, "remaining": 4,
                       "penalty_fee": 96.0, "unsubscribe_url": "u", "manage_url": "m"},
    "score_change": {"first_name": "Jean", "unsubscribe_url": "u", "manage_url": "m",
                     "items": [{"security_id": 1, "name": "LVMH", "before": 58, "after": 71, "change": "entered"}]},
    **{kind: PREMIUM for kind in ("premium_started", "payment_failed", "premium_canceling", "premium_ended", "renewal_reminder")},
}


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_every_kind_renders_html_and_text(kind):
    mail = render(kind, CONTEXTS[kind], base_url=BASE)
    assert mail.subject and "Jean" in mail.text and "Jean" in mail.html
    assert "<" not in mail.text.replace("<https", "")  # texte brut, sans balise
    # L'avertissement est réservé aux notifications (celles qui ont un lien de désinscription).
    assert ("pas un conseil" in mail.text) == ("unsubscribe_url" in CONTEXTS[kind])


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


def test_account_deleted_and_admin_alerts_render():
    deleted = render("account_deleted", {"first_name": "Jean"}, base_url=BASE)
    assert deleted.subject == "Votre compte Cotalyx a été supprimé" and "Jean" in deleted.text
    for event in ("admin_updated", "email_changed_by_admin", "password_changed", "email_changed"):
        mail = render("security_alert", {"first_name": "Jean", "event": event}, base_url=BASE)
        assert mail.text.strip()


def test_subjects_and_footer_use_new_name():
    mail = render("verify_code", CONTEXTS["verify_code"], base_url=BASE)
    assert mail.subject == "Votre code Cotalyx : 042917"
    assert "Cotalyx" in mail.html and "Cotalyx" in mail.text
    assert "PEA Radar" not in mail.html + mail.text
