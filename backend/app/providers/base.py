from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class ListedSecurity:
    isin: str
    symbol: str
    name: str
    market: str
    yahoo_ticker: str


@dataclass(frozen=True)
class Quote:
    price: float
    previous_close: float | None
    change_pct: float | None
    volume: int | None
    as_of: datetime


@dataclass(frozen=True)
class DailyBar:
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


@dataclass(frozen=True)
class IntradayBar:
    time: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    publisher: str | None
    published_at: datetime | None


@dataclass(frozen=True)
class Fundamentals:
    """Ratios en fraction (0,0328 = 3,28 %) ; dette/capitaux propres en ratio."""

    pe: float | None
    eps: float | None
    earnings_growth: float | None
    revenue_growth: float | None
    debt_to_equity: float | None
    profit_margin: float | None
    dividend_yield: float | None
    market_cap: float | None
    sector: str | None
    industry: str | None
    currency: str | None
    employees: int | None = None
    revenue: float | None = None  # chiffre d'affaires annuel, en `revenue_currency`
    revenue_currency: str | None = None


class ListingProvider(Protocol):
    def fetch_listed(self) -> list[ListedSecurity]: ...


class MarketDataProvider(Protocol):
    def get_quotes(self, tickers: list[str]) -> dict[str, Quote]: ...

    def get_daily_history(self, tickers: list[str], start: date | None) -> dict[str, list[DailyBar]]: ...  # None : tout l'historique

    def get_fundamentals(self, ticker: str) -> Fundamentals | None: ...

    def get_intraday(self, ticker: str, period: str, interval: str) -> list[IntradayBar]: ...

    def get_news(self, ticker: str) -> list[NewsItem]: ...
