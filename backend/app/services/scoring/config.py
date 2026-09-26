"""Pondérations du score mixte (spec §4). Modifier une valeur met le composant à l'échelle."""

MAX_POINTS: dict[str, float] = {
    "trend": 20,
    "momentum": 15,
    "rsi": 10,
    "macd": 5,
    "valuation": 15,
    "growth": 15,
    "solidity": 10,
    "dividend": 10,
}
