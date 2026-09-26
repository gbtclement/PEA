from datetime import UTC, date, datetime

from sqlalchemy import func, select

from app.core.current_user import ensure_default_user
from app.models import DailyPrice, SecurityQuote, User
from tests.factories import make_security


def test_ensure_default_user_is_idempotent(db):
    first = ensure_default_user(db)
    second = ensure_default_user(db)
    assert first.id == second.id
    assert db.scalar(select(func.count(User.id))) == 1
    assert first.name == "Moi"


def test_security_with_quote_and_prices(db):
    security = make_security(db, "MC.PA", isin="FR0000121014", name="LVMH")
    db.add(SecurityQuote(security_id=security.id, price=612.4, previous_close=600.0, change_pct=2.07,
                         volume=1000, as_of=datetime(2026, 9, 25, 15, 35, tzinfo=UTC)))
    db.add(DailyPrice(security_id=security.id, date=date(2026, 9, 25), open=600, high=615, low=598,
                      close=612.4, volume=1000))
    db.flush()
    assert db.get(SecurityQuote, security.id).price == 612.4
    assert db.scalar(select(func.count()).select_from(DailyPrice)) == 1
