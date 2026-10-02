from datetime import UTC, datetime

import pytest

from app.jobs.fx import refresh_fx
from app.models import FxRate
from app.providers.base import Quote
from app.repositories.fx import load_rates
from app.services import fx
from tests.factories import make_security
from tests.fakes import FakeMarket


@pytest.fixture(autouse=True)
def _fresh_rates():
    fx.reset()
    yield
    fx.reset()


def quote(price: float) -> Quote:
    return Quote(price, None, None, None, datetime(2026, 10, 2, 16, 0, tzinfo=UTC))


def test_pence_are_hundredths_of_pounds():
    fx.set_rates({"GBP": 1.2})
    assert fx.to_eur(250.0, "GBp") == pytest.approx(3.0)
    assert fx.to_eur(250.0, "GBX") == pytest.approx(3.0)
    assert fx.to_eur(2.5, "GBP") == pytest.approx(3.0)


def test_fallback_table_without_store():
    assert fx.to_eur(100.0, "USD") == pytest.approx(100 * fx.FALLBACK_TO_EUR["USD"])
    assert fx.to_eur(100.0, None) == 100.0
    assert fx.to_eur(100.0, "XYZ") == 100.0  # devise inconnue : comptée en euros, comme avant


def test_store_is_read_and_cached():
    calls = []
    fx.use_store(lambda: calls.append(1) or {"USD": 0.5})
    assert fx.to_eur(10.0, "USD") == 5.0
    assert fx.to_eur(10.0, "USD") == 5.0
    assert len(calls) == 1


def test_broken_store_keeps_previous_rates():
    def broken():
        raise RuntimeError("base KO")

    fx.use_store(broken)
    assert fx.to_eur(100.0, "USD") == pytest.approx(100 * fx.FALLBACK_TO_EUR["USD"])


def test_refresh_fx_stores_inverted_rates(db, make_ctx):
    market = FakeMarket(quotes={"EURUSD=X": quote(1.25), "EURGBP=X": quote(0.8)})
    assert refresh_fx(make_ctx(market=market)) == 2
    assert load_rates(db) == {"USD": pytest.approx(0.8), "GBP": pytest.approx(1.25)}
    assert fx.to_eur(10.0, "USD") == pytest.approx(8.0)


def test_refresh_fx_keeps_last_rates_when_yahoo_fails(db, make_ctx):
    refresh_fx(make_ctx(market=FakeMarket(quotes={"EURUSD=X": quote(1.25)})))
    with pytest.raises(RuntimeError):
        refresh_fx(make_ctx(market=FakeMarket(quotes={})))
    db.expire_all()
    assert db.get(FxRate, "USD").rate_to_eur == pytest.approx(0.8)
    assert fx.to_eur(10.0, "USD") == pytest.approx(8.0)


def test_security_currency_prefers_the_listing(db):
    us = make_security(db, "AAPL", market="Nasdaq")
    assert fx.security_currency(us) == "USD"
    us.currency = "EUR"
    assert fx.security_currency(us) == "EUR"
    assert fx.currency_for_market("Nasdaq Stockholm") == "SEK"
    assert fx.currency_for_market("Oslo Børs") == "NOK"


def test_every_listing_currency_has_a_rate():
    # Un ETF coté en yens compté 1 pour 1 paraîtrait ~170 fois plus liquide qu'il ne l'est.
    for code in ("JPY", "AUD", "CAD", "SGD"):
        assert code in fx.FX_PAIRS
        assert 0 < fx.rate_to_eur(code) < 1
