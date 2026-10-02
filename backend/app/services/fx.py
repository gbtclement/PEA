"""Conversion en euros : cours de change du jour (table fx_rates), repli sur la dernière valeur puis sur une table fixe."""
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Security

logger = logging.getLogger(__name__)

# Valeur d'une unité en euros (octobre 2026), utilisée tant qu'aucun cours du jour n'est connu.
FALLBACK_TO_EUR: dict[str, float] = {
    "EUR": 1.0, "USD": 0.89, "GBP": 1.17, "CHF": 1.07, "SEK": 0.087, "DKK": 0.134, "NOK": 0.085, "PLN": 0.23,
    "ISK": 0.0066, "JPY": 0.0056, "AUD": 0.62, "CAD": 0.62, "SGD": 0.69,
}
FX_PAIRS: dict[str, str] = {code: f"EUR{code}=X" for code in FALLBACK_TO_EUR if code != "EUR"}
_PENCE = ("GBp", "GBX")  # cotations londoniennes en pence
CACHE_SECONDS = 600
MARKET_CURRENCIES: dict[str, str] = {
    "NYSE": "USD", "NYSE American": "USD", "NYSE Arca": "USD", "Nasdaq": "USD",
    "SIX Swiss Exchange": "CHF", "Nasdaq Stockholm": "SEK", "Nasdaq Copenhagen": "DKK", "Nasdaq Iceland": "ISK",
}

_rates: dict[str, float] = dict(FALLBACK_TO_EUR)
_loader: Callable[[], dict[str, float]] | None = None
_loaded_at = float("-inf")


def use_store(loader: Callable[[], dict[str, float]] | None) -> None:
    """Branche la lecture des cours stockés (API et worker) ; relue au plus toutes les 10 minutes."""
    global _loader, _loaded_at
    _loader, _loaded_at = loader, float("-inf")


def set_rates(rates: dict[str, float]) -> None:
    _rates.update(rates)


def reset() -> None:
    global _loader, _loaded_at
    _rates.clear()
    _rates.update(FALLBACK_TO_EUR)
    _loader, _loaded_at = None, float("-inf")


def _current() -> dict[str, float]:
    global _loaded_at
    if _loader is not None and time.monotonic() - _loaded_at > CACHE_SECONDS:
        _loaded_at = time.monotonic()
        try:
            _rates.update(_loader())
        except Exception:
            logger.warning("Cours de change illisibles, dernières valeurs conservées", exc_info=True)
    return _rates


def rate_to_eur(currency: str | None) -> float | None:
    if currency in _PENCE:
        pound = _current().get("GBP")
        return pound / 100 if pound is not None else None
    return _current().get((currency or "EUR").upper())


def to_eur(value: float | None, currency: str | None) -> float | None:
    if value is None:
        return None
    rate = rate_to_eur(currency)
    return value * (rate if rate is not None else 1.0)


def currency_for_market(market: str) -> str:
    if "Oslo" in market:
        return "NOK"
    return MARKET_CURRENCIES.get(market, "EUR")


def security_currency(security: "Security") -> str:
    return security.currency or currency_for_market(security.market)
