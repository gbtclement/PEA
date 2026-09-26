from dataclasses import dataclass, field

from app.services.scoring.components import (
    Component, dividend, growth, macd_component, momentum, rsi_component, solidity, trend, valuation,
)
from app.services.scoring.config import MAX_POINTS

_TECHNICAL_KEYS = ("trend", "momentum", "rsi", "macd")


@dataclass(frozen=True)
class ScoreInputs:
    price: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    perf_3m: float | None = None
    index_perf_3m: float | None = None
    rsi: float | None = None
    macd_line: list[float | None] = field(default_factory=list)
    signal_line: list[float | None] = field(default_factory=list)
    pe: float | None = None
    sector_median_pe: float | None = None
    eps_growth: float | None = None
    revenue_growth: float | None = None
    debt_to_equity: float | None = None
    profit_margin: float | None = None
    dividend_yield: float | None = None


@dataclass(frozen=True)
class ScoreResult:
    total: float | None
    technical: float | None
    fundamental: float | None
    components: list[Component]
    available_ratio: float

    @property
    def incomplete(self) -> bool:
        return self.available_ratio < 1


def _ratio(components: list[Component]) -> float | None:
    available = sum(c.max_points for c in components)
    return round(sum(c.points for c in components) / available * 100, 1) if available else None


def compute_score(inputs: ScoreInputs, kind: str = "stock") -> ScoreResult:
    technical = [c for c in (
        trend(inputs.price, inputs.sma50, inputs.sma200),
        momentum(inputs.perf_3m, inputs.index_perf_3m),
        rsi_component(inputs.rsi),
        macd_component(inputs.macd_line, inputs.signal_line),
    ) if c is not None]
    fundamental: list[Component] = []
    if kind != "etf":
        fundamental = [c for c in (
            valuation(inputs.pe, inputs.sector_median_pe),
            growth(inputs.eps_growth, inputs.revenue_growth),
            solidity(inputs.debt_to_equity, inputs.profit_margin),
            dividend(inputs.dividend_yield),
        ) if c is not None]
    components = technical + fundamental
    possible = sum(v for k, v in MAX_POINTS.items() if kind != "etf" or k in _TECHNICAL_KEYS)
    available = sum(c.max_points for c in components)
    return ScoreResult(
        total=_ratio(components),
        technical=_ratio(technical),
        fundamental=_ratio(fundamental),
        components=components,
        available_ratio=round(available / possible, 3) if possible else 0.0,
    )
