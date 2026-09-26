"""Frais de courtage Invest Store Intégral (grille par défaut de la caisse de Paris)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeeTier:
    up_to: float | None  # borne haute incluse ; None = sans limite
    rate: float


DEFAULT_GRID: tuple[FeeTier, ...] = (
    FeeTier(500.0, 0.0048),
    FeeTier(1000.0, 0.0018),
    FeeTier(None, 0.0012),
)


def broker_fee(amount: float, grid: tuple[FeeTier, ...] = DEFAULT_GRID) -> tuple[float, float]:
    """Retourne (frais en €, taux). Le taux de la tranche s'applique au montant total de l'ordre."""
    if amount <= 0:
        return 0.0, 0.0
    for tier in grid:
        if tier.up_to is None or amount <= tier.up_to:
            return round(amount * tier.rate, 2), tier.rate
    last = grid[-1]
    return round(amount * last.rate, 2), last.rate


def grid_from_json(data: list[dict]) -> tuple[FeeTier, ...]:
    return tuple(FeeTier(None if t.get("up_to") is None else float(t["up_to"]), float(t["rate"])) for t in data)


def grid_to_json(grid: tuple[FeeTier, ...]) -> list[dict]:
    return [{"up_to": t.up_to, "rate": t.rate} for t in grid]


DEFAULT_GRID_JSON = grid_to_json(DEFAULT_GRID)
