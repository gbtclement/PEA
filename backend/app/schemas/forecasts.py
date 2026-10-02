from datetime import date, datetime

from pydantic import BaseModel


class SignalOut(BaseModel):
    key: str
    label: str
    bullish: bool


class HorizonForecastOut(BaseModel):
    expected_return: float
    prob_up: float
    reliability: str
    rank: int


class ForecastSecurityOut(BaseModel):
    id: int
    name: str
    symbol: str
    market: str
    envelopes: list[str]
    price: float | None
    change_pct: float | None


class ForecastRowOut(BaseModel):
    security: ForecastSecurityOut
    signals: list[SignalOut]
    horizons: dict[str, HorizonForecastOut | None]


class ForecastListOut(BaseModel):
    as_of: date | None
    round_trip_cost: float | None
    rows: list[ForecastRowOut]


class SignalStatOut(BaseModel):
    n: int
    mean: float
    median: float
    hit_rate: float
    mean_excess: float
    beat_index: float
    hit_after_fees: float
    reliability: str


class SignalStatsRowOut(BaseModel):
    key: str
    label: str
    description: str
    bullish: bool
    horizons: dict[str, SignalStatOut | None]


class SignalStatsOut(BaseModel):
    as_of: date | None
    computed_at: datetime | None
    round_trip_cost: float | None
    signals: list[SignalStatsRowOut]
    baseline: dict[str, SignalStatOut | None]


class BacktestOut(BaseModel):
    days: int
    picks: int
    hit_rate: float
    hit_after_fees: float
    mean_return: float
    mean_after_fees: float
    mean_excess: float
    baseline_mean: float
    edge: float


class RealTrackOut(BaseModel):
    picks: int
    hit_rate: float
    hit_after_fees: float
    mean_return: float
    mean_after_fees: float
    baseline_mean: float
    edge: float
    first_day: date


class TrackRecordOut(BaseModel):
    cutoff: date | None
    round_trip_cost: float | None
    simulated: dict[str, BacktestOut | None]
    real: dict[str, RealTrackOut | None]


class SecurityForecastOut(BaseModel):
    as_of: date | None
    signals: list[SignalOut]
    horizons: dict[str, HorizonForecastOut | None]
