from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.jobs.notifications import run_price_alerts
from app.jobs.tiers import tier_tickers
from app.models import EmailLog, PriceAlert
from app.services.notifications.prefs import save_prefs
from tests.factories import make_quote, make_security

pytestmark = pytest.mark.usefixtures("app_secret")
NOW = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)


def _alert(db, user, security, direction="above", price=105.0):
    alert = PriceAlert(user_id=user.id, security_id=security.id, direction=direction, price=price)
    db.add(alert)
    db.flush()
    return alert


def _mails(db):
    return db.scalars(select(EmailLog).where(EmailLog.kind == "price_alert")).all()


def test_alert_fires_once_and_disarms(db, user, make_ctx):
    security = make_security(db, "MC.PA", name="LVMH")
    make_quote(db, security, 100.0)
    alert = _alert(db, user, security)
    assert run_price_alerts(make_ctx(now=NOW)) == 0
    make_quote(db, security, 106.0)
    assert run_price_alerts(make_ctx(now=NOW)) == 1
    assert run_price_alerts(make_ctx(now=NOW)) == 0
    db.refresh(alert)
    assert alert.active is False and alert.triggered_at == NOW
    [mail] = _mails(db)
    assert mail.recipient == user.email and "LVMH" in mail.subject and "106,00 €" in mail.text
    assert "List-Unsubscribe" in mail.headers


def test_below_alert(db, user, make_ctx):
    security = make_security(db, "MC.PA")
    make_quote(db, security, 94.0)
    _alert(db, user, security, direction="below", price=95.0)
    assert run_price_alerts(make_ctx(now=NOW)) == 1


def test_alert_ignored_while_price_alerts_are_off(db, user, make_ctx):
    security = make_security(db, "MC.PA")
    make_quote(db, security, 106.0)
    alert = _alert(db, user, security)
    save_prefs(db, user.id, {"price_alert": False})
    assert run_price_alerts(make_ctx(now=NOW)) == 0
    db.refresh(alert)
    assert alert.active is True  # suspendue, pas consommée (Ruling 3)


def test_foreign_currency_alert_keeps_its_currency(db, user, make_ctx):
    security = make_security(db, "EQNR.OL", name="Equinor", market="Oslo Børs")
    make_quote(db, security, 301.5)
    _alert(db, user, security, price=300.0)
    run_price_alerts(make_ctx(now=NOW))
    [mail] = _mails(db)
    assert "301,50 NOK" in mail.text and "€" not in mail.text.split("--")[0]


def test_no_secret_nothing_is_consumed(db, user, make_ctx, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "app_secret", "")
    security = make_security(db, "MC.PA")
    make_quote(db, security, 106.0)
    alert = _alert(db, user, security)
    assert run_price_alerts(make_ctx(now=NOW)) == 0
    db.refresh(alert)
    assert alert.active is True


def test_alerted_security_is_refreshed_every_minute(db, user):
    security = make_security(db, "ALO.PA")
    _alert(db, user, security)
    assert "ALO.PA" in tier_tickers(db, 1, 10)
