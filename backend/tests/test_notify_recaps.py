from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.models import EmailLog, Favorite, Order
from app.services.notifications.prefs import save_prefs
from app.services.notifications.recaps import send_daily_recaps
from app.services.notifications.reminders import send_order_reminders
from app.services.portfolio_value import value_portfolio
from tests.factories import make_quote, make_security, make_user

pytestmark = pytest.mark.usefixtures("app_secret")
EVENING = datetime(2026, 10, 1, 16, 45, tzinfo=UTC)  # jeudi 18 h 45 à Paris


def _buy(db, user, security, quantity=10, price=100.0, day=date(2026, 9, 1)):
    db.add(Order(user_id=user.id, security_id=security.id, trade_date=day, side="buy", quantity=quantity,
                 unit_price=price, fee=1.0))
    db.flush()


def _mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind)).all()


def test_value_portfolio_totals(db, user):
    lvmh = make_security(db, "MC.PA")
    _buy(db, user, lvmh)
    make_quote(db, lvmh, 110.0, previous_close=108.0, change_pct=1.85, as_of=EVENING)
    value = value_portfolio(db, user.id, date(2026, 10, 1))
    assert (value.total, value.invested, value.day_change) == (1100.0, 1001.0, 20.0)
    assert value.day_change_pct == round(20 / 1080 * 100, 2)


def test_daily_recap_with_portfolio_and_favorite_movers(db, user):
    save_prefs(db, user.id, {"daily_recap": True})
    lvmh = make_security(db, "MC.PA", name="LVMH")
    kering = make_security(db, "KER.PA", name="Kering")
    _buy(db, user, lvmh)
    make_quote(db, lvmh, 110.0, previous_close=108.0, change_pct=1.85, as_of=EVENING)
    db.add(Favorite(user_id=user.id, security_id=kering.id))
    make_quote(db, kering, 300.0, change_pct=-3.4, as_of=EVENING)
    assert send_daily_recaps(db, EVENING) == 1
    [mail] = _mails(db, "daily_recap")
    assert "1 100,00 €" in mail.text and "Kering : -3,40 %" in mail.text and "01/10/2026" in mail.text


def test_daily_recap_once_per_day(db, user):
    save_prefs(db, user.id, {"daily_recap": True})
    lvmh = make_security(db, "MC.PA")
    _buy(db, user, lvmh)
    make_quote(db, lvmh, 110.0, previous_close=108.0, change_pct=1.85, as_of=EVENING)
    send_daily_recaps(db, EVENING)
    send_daily_recaps(db, EVENING)
    assert len(_mails(db, "daily_recap")) == 1


def test_no_daily_recap_on_a_holiday_or_when_off_or_empty(db, user):
    lvmh = make_security(db, "MC.PA")
    _buy(db, user, lvmh)
    make_quote(db, lvmh, 110.0, change_pct=1.0, as_of=EVENING)
    assert send_daily_recaps(db, EVENING) == 0  # désactivé par défaut
    save_prefs(db, user.id, {"daily_recap": True})
    assert send_daily_recaps(db, datetime(2026, 12, 25, 17, 45, tzinfo=UTC)) == 0  # Noël : pas de séance
    empty = make_user(db, "vide@example.com")  # ni position ni favori : rien à raconter
    save_prefs(db, empty.id, {"daily_recap": True})
    assert send_daily_recaps(db, EVENING) == 1  # seulement `user`


def test_order_reminder_when_orders_are_missing(db, user):
    lvmh = make_security(db, "MC.PA")
    for day in (date(2026, 2, 1), date(2026, 5, 1), date(2026, 8, 1)):
        _buy(db, user, lvmh, quantity=1, day=day)
    first_oct = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
    assert send_order_reminders(db, first_oct) == 1
    assert send_order_reminders(db, first_oct) == 0  # une fois par mois
    [mail] = _mails(db, "order_reminder")
    assert "il vous manque 9" in mail.subject + mail.text and "96,00 €" in mail.text


def test_no_order_reminder_without_orders_or_when_on_track(db, user):
    first_oct = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
    assert send_order_reminders(db, first_oct) == 0  # aucun ordre saisi (Ruling 4)
    lvmh = make_security(db, "MC.PA")
    for day in range(1, 13):  # 12 ordres sur 12 : objectif atteint
        _buy(db, user, lvmh, quantity=1, day=date(2026, 9, day))
    assert send_order_reminders(db, first_oct) == 0
