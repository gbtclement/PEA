from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.screener import ScreenerRow


class FundamentalsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pe: float | None
    eps: float | None
    earnings_growth: float | None
    revenue_growth: float | None
    debt_to_equity: float | None
    profit_margin: float | None
    dividend_yield: float | None
    market_cap: float | None
    employees: int | None
    revenue: float | None
    revenue_currency: str | None
    currency: str | None
    updated_at: datetime | None


class ComponentOut(BaseModel):
    key: str
    label: str
    points: float
    max_points: float
    message: str
    group: str


class ScoreOut(BaseModel):
    total: float | None
    technical: float | None
    fundamental: float | None
    available_ratio: float
    liquid: bool
    eligible_for_top: bool
    history_days: int
    computed_at: datetime
    components: list[ComponentOut]


class SecurityDetail(ScreenerRow):
    isin: str | None
    industry: str | None
    currency: str
    as_of: datetime | None
    fundamentals: FundamentalsOut | None
    score_detail: ScoreOut | None


class Bar(BaseModel):
    time: str | int
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


class LinePoint(BaseModel):
    time: str
    value: float


class MacdPoint(BaseModel):
    time: str
    macd: float
    signal: float
    histogram: float


class HistoryOut(BaseModel):
    period: str
    intraday: bool
    interval: Literal["5m", "30m", "day", "week", "month"]  # durée d'une barre
    first_date: date | None  # bornes de tout l'historique stocké (champs de la période personnalisée)
    last_date: date | None
    bars: list[Bar]
    sma50: list[LinePoint]
    sma200: list[LinePoint]
    rsi: list[LinePoint]
    macd: list[MacdPoint]


class NewsOut(BaseModel):
    title: str
    url: str
    publisher: str | None
    published_at: datetime | None


class SimulationOut(BaseModel):
    start_date: date | None
    start_price: float | None
    current_price: float | None
    shares: int
    invested: float
    buy_fee: float
    sell_fee: float
    current_value: float
    gain: float
    gain_pct: float | None
    message: str | None
    note: str | None = None  # « historique disponible depuis le … » quand la durée dépasse l'historique


class FeeEstimate(BaseModel):
    amount: float
    fee: float
    rate: float
