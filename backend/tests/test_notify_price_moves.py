from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.jobs.notifications import run_price_moves
from app.models import EmailLog, Favorite, MoveNotice, Order
from app.services.notifications.moves import notify_price_moves
from app.services.notifications.prefs import save_prefs
from tests.factories import make_quote, make_security

pytestmark = pytest.mark.usefixtures("app_secret")
OPEN = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)  # 11 h 30 à Paris, jeudi


def _fav(db, user, security):
    db.add(Favorite(user_id=user.id, security_id=security.id))
    db.flush()


def _mails(db):
    return db.scalars(select(EmailLog).where(EmailLog.kind == "price_move")).all()


def test_big_move_of_a_favorite_is_mailed(db, user):
    lvmh = make_security(db, "MC.PA", name="LVMH")
    kering = make_security(db, "KER.PA", name="Kering")
    calm = make_security(db, "OR.PA", name="L'Oréal")
    for security, change in ((lvmh, 6.2), (kering, -7.5), (calm, 1.0)):
        _fav(db, user, security)
        make_quote(db, security, 100.0, change_pct=change, as_of=OPEN)
    assert notify_price_moves(db, OPEN) == 1
    [mail] = _mails(db)
    assert "Kering" in mail.text and "LVMH" in mail.text and "L'Oréal" not in mail.text
    assert mail.text.index("Kering") < mail.text.index("LVMH")  # la plus forte variation d'abord


def test_same_title_is_signalled_once_a_day(db, user):
    lvmh = make_security(db, "MC.PA")
    _fav(db, user, lvmh)
    make_quote(db, lvmh, 100.0, change_pct=6.0, as_of=OPEN)
    notify_price_moves(db, OPEN)
    make_quote(db, lvmh, 100.0, change_pct=8.0, as_of=OPEN.replace(hour=12))
    assert notify_price_moves(db, OPEN.replace(hour=12)) == 0
    assert len(_mails(db)) == 1
    assert db.scalar(select(MoveNotice.day)) == date(2026, 10, 1)


def test_threshold_is_personal(db, user):
    lvmh = make_security(db, "MC.PA")
    _fav(db, user, lvmh)
    make_quote(db, lvmh, 100.0, change_pct=6.0, as_of=OPEN)
    save_prefs(db, user.id, {"move_threshold_pct": 10.0})
    assert notify_price_moves(db, OPEN) == 0


def test_open_positions_count_sold_out_ones_do_not(db, user):
    held = make_security(db, "AI.PA", name="Air Liquide")
    sold = make_security(db, "SAN.PA", name="Sanofi")
    db.add_all([
        Order(user_id=user.id, security_id=held.id, trade_date=date(2026, 9, 1), side="buy", quantity=2, unit_price=10, fee=1),
        Order(user_id=user.id, security_id=sold.id, trade_date=date(2026, 9, 1), side="buy", quantity=2, unit_price=10, fee=1),
        Order(user_id=user.id, security_id=sold.id, trade_date=date(2026, 9, 2), side="sell", quantity=2, unit_price=11, fee=1),
    ])
    db.flush()
    make_quote(db, held, 100.0, change_pct=-5.5, as_of=OPEN)
    make_quote(db, sold, 100.0, change_pct=-9.0, as_of=OPEN)
    notify_price_moves(db, OPEN)
    [mail] = _mails(db)
    assert "Air Liquide" in mail.text and "Sanofi" not in mail.text


def test_yesterdays_quote_is_ignored(db, user):
    lvmh = make_security(db, "MC.PA")
    _fav(db, user, lvmh)
    make_quote(db, lvmh, 100.0, change_pct=6.0, as_of=datetime(2026, 9, 30, 15, 0, tzinfo=UTC))
    assert notify_price_moves(db, OPEN) == 0


def test_job_waits_for_the_session(db, user, make_ctx):
    lvmh = make_security(db, "MC.PA")
    _fav(db, user, lvmh)
    make_quote(db, lvmh, 100.0, change_pct=6.0, as_of=OPEN)
    assert run_price_moves(make_ctx(now=datetime(2026, 10, 1, 19, 0, tzinfo=UTC))) == 0  # 21 h à Paris
    assert run_price_moves(make_ctx(now=OPEN)) == 1


def test_evening_moves_only_cover_places_still_open(db, user, make_ctx):
    lvmh = make_security(db, "MC.PA")
    apple = make_security(db, "AAPL", market="Nasdaq", country="US")
    evening = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)  # 19 h à Paris : seul New York est ouvert
    for s in (lvmh, apple):
        _fav(db, user, s)
        make_quote(db, s, 100.0, change_pct=6.0, as_of=evening)
    assert run_price_moves(make_ctx(now=evening)) == 1
    notices = set(db.scalars(select(MoveNotice.security_id)))
    assert notices == {apple.id}
