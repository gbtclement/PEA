"""Conversion approximative en euros, suffisante pour comparer des liquidités et des capitalisations."""

FX_TO_EUR: dict[str, float] = {"EUR": 1.0, "NOK": 0.085, "SEK": 0.087, "DKK": 0.134}


def currency_for_market(market: str) -> str:
    return "NOK" if "Oslo" in market else "EUR"


def to_eur(value: float | None, currency: str | None) -> float | None:
    if value is None:
        return None
    return value * FX_TO_EUR.get((currency or "EUR").upper(), 1.0)
