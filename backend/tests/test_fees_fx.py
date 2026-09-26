import pytest

from app.services.fees import FeeTier, broker_fee
from app.services.fx import currency_for_market, to_eur


@pytest.mark.parametrize("amount, expected", [
    (400, (1.92, 0.0048)),
    (500, (2.40, 0.0048)),      # 500 € inclus dans la première tranche
    (500.01, (0.90, 0.0018)),
    (1000, (1.80, 0.0018)),
    (2000, (2.40, 0.0012)),
    (0, (0.0, 0.0)),
    (-10, (0.0, 0.0)),
])
def test_broker_fee_default_grid(amount, expected):
    assert broker_fee(amount) == expected


def test_broker_fee_custom_grid():
    assert broker_fee(100, (FeeTier(None, 0.01),)) == (1.0, 0.01)


def test_currency_for_market():
    assert currency_for_market("Oslo Børs") == "NOK"
    assert currency_for_market("Euronext Growth Oslo") == "NOK"
    assert currency_for_market("Euronext Paris") == "EUR"


def test_to_eur():
    assert to_eur(100.0, "EUR") == 100.0
    assert to_eur(100.0, "NOK") == pytest.approx(8.5)
    assert to_eur(100.0, None) == 100.0
    assert to_eur(None, "EUR") is None
