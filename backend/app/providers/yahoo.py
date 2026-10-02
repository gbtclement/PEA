import logging
import math
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from datetime import time as dtime
from typing import Any

import pandas as pd
import yfinance as yf

from app.providers.base import DailyBar, Fundamentals, IntradayBar, NewsItem, Quote
from app.providers.retry import with_retries
from app.services.market_calendar import PARIS

logger = logging.getLogger(__name__)
_CLOSE_TIME = dtime(17, 35)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) or math.isinf(number) else number


def _int(value: Any) -> int | None:
    number = _num(value)
    return None if number is None else int(number)


def split_by_ticker(df: pd.DataFrame | None, tickers: list[str]) -> dict[str, pd.DataFrame]:
    if df is None or df.empty:
        return {}
    result: dict[str, pd.DataFrame] = {}
    if isinstance(df.columns, pd.MultiIndex):
        available = set(df.columns.get_level_values(0))
        for ticker in tickers:
            if ticker in available:
                sub = df[ticker].dropna(subset=["Close"])
                if not sub.empty:
                    result[ticker] = sub
    elif len(tickers) == 1:
        sub = df.dropna(subset=["Close"])
        if not sub.empty:
            result[tickers[0]] = sub
    return result


def bars_from_frame(frame: pd.DataFrame) -> list[DailyBar]:
    bars = []
    for index, row in frame.iterrows():
        close = _num(row["Close"])
        if close is None or close <= 0:
            continue  # vieilles séances mal ajustées par Yahoo (clôture infinie ou nulle)
        bars.append(DailyBar(
            date=index.date(), open=_num(row["Open"]), high=_num(row["High"]), low=_num(row["Low"]),
            close=close, volume=_int(row["Volume"]),
        ))
    return bars


def intraday_from_frame(frame: pd.DataFrame) -> list[IntradayBar]:
    bars = []
    for index, row in frame.iterrows():
        moment = index.to_pydatetime()
        moment = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
        bars.append(IntradayBar(time=moment, open=_num(row["Open"]), high=_num(row["High"]), low=_num(row["Low"]),
                                close=float(row["Close"]), volume=_int(row["Volume"])))
    return bars


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None
    return None


def parse_news(items: Any) -> list[NewsItem]:
    """Accepte l'ancien format yfinance (champs à plat) et le nouveau (sous-objet `content`)."""
    news = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else item
        title = content.get("title")
        url = (content.get("canonicalUrl") or {}).get("url") or content.get("link")
        if not title or not url:
            continue
        publisher = (content.get("provider") or {}).get("displayName") or content.get("publisher")
        published = _parse_datetime(content.get("pubDate") or content.get("providerPublishTime"))
        news.append(NewsItem(title=title, url=url, publisher=publisher, published_at=published))
    return news


def quote_from_frame(frame: pd.DataFrame, fetched_at: datetime) -> Quote:
    last = frame.iloc[-1]
    price = float(last["Close"])
    previous_close = float(frame.iloc[-2]["Close"]) if len(frame) > 1 else None
    change_pct = (price / previous_close - 1) * 100 if previous_close else None
    last_date = frame.index[-1].date()
    if last_date == fetched_at.astimezone(PARIS).date():
        as_of = fetched_at
    else:
        as_of = datetime.combine(last_date, _CLOSE_TIME, tzinfo=PARIS)
    return Quote(price=price, previous_close=previous_close, change_pct=change_pct,
                 volume=_int(last["Volume"]), as_of=as_of)


def fundamentals_from_info(info: dict[str, Any]) -> Fundamentals:
    def percent(key: str) -> float | None:  # Yahoo renvoie 3.28 pour 3,28 %
        value = _num(info.get(key))
        return None if value is None else value / 100

    return Fundamentals(
        pe=_num(info.get("trailingPE")),
        eps=_num(info.get("trailingEps")),
        earnings_growth=_num(info.get("earningsGrowth")),
        revenue_growth=_num(info.get("revenueGrowth")),
        debt_to_equity=percent("debtToEquity"),
        profit_margin=_num(info.get("profitMargins")),
        dividend_yield=percent("dividendYield"),
        market_cap=_num(info.get("marketCap")),
        sector=info.get("sector"),
        industry=info.get("industry"),
        currency=info.get("currency"),
        employees=_int(info.get("fullTimeEmployees")),
        revenue=_num(info.get("totalRevenue")),
        revenue_currency=info.get("financialCurrency") or None,
    )


class YahooProvider:
    def __init__(
        self,
        chunk_size: int = 50,
        pause_seconds: float = 1.0,
        fundamentals_pause_seconds: float = 0.5,
        download: Callable[..., pd.DataFrame] | None = None,
        ticker_info: Callable[[str], dict[str, Any]] | None = None,
        ticker_news: Callable[[str], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._chunk_size = chunk_size
        self._pause = pause_seconds
        self._fundamentals_pause = fundamentals_pause_seconds
        self._download = download or yf.download
        self._ticker_info = ticker_info or (lambda ticker: yf.Ticker(ticker).info)
        self._ticker_news = ticker_news or (lambda ticker: yf.Ticker(ticker).news)
        self._sleep = sleep
        self._now = now
        # Un seul appel Yahoo à la fois, toutes tâches confondues (limiteur de débit global).
        self._lock = threading.Lock()

    def _chunks(self, tickers: list[str]) -> Iterator[list[str]]:
        for start in range(0, len(tickers), self._chunk_size):
            if start:
                self._sleep(self._pause)
            yield tickers[start:start + self._chunk_size]

    def _download_frames(self, tickers: list[str], **kwargs: Any) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        for chunk in self._chunks(tickers):
            try:
                with self._lock:
                    df = with_retries(
                        lambda: self._download(chunk, group_by="ticker", auto_adjust=True, progress=False,
                                               threads=True, **kwargs),
                        sleep=self._sleep,
                    )
            except Exception:
                logger.warning("Échec du téléchargement Yahoo pour %d titres", len(chunk), exc_info=True)
                continue
            frames.update(split_by_ticker(df, chunk))
        return frames

    def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        fetched_at = self._now()
        frames = self._download_frames(tickers, period="5d", interval="1d")
        return {ticker: quote_from_frame(frame, fetched_at) for ticker, frame in frames.items()}

    def get_daily_history(self, tickers: list[str], start: date | None) -> dict[str, list[DailyBar]]:
        window = {"period": "max"} if start is None else {"start": start.isoformat()}  # None : tout l'historique Yahoo
        frames = self._download_frames(tickers, interval="1d", **window)
        return {ticker: bars_from_frame(frame) for ticker, frame in frames.items()}

    def get_fundamentals(self, ticker: str) -> Fundamentals | None:
        try:
            with self._lock:
                info = with_retries(lambda: self._ticker_info(ticker), sleep=self._sleep)
        except Exception:
            logger.warning("Fondamentaux Yahoo indisponibles pour %s", ticker, exc_info=True)
            return None
        finally:
            self._sleep(self._fundamentals_pause)
        # Yahoo renvoie parfois un dictionnaire presque vide : on l'ignore plutôt que d'effacer les données.
        if not info or not (info.get("quoteType") or info.get("symbol")):
            return None
        return fundamentals_from_info(info)

    def get_intraday(self, ticker: str, period: str, interval: str) -> list[IntradayBar]:
        frames = self._download_frames([ticker], period=period, interval=interval)
        return intraday_from_frame(frames[ticker]) if ticker in frames else []

    def get_news(self, ticker: str) -> list[NewsItem]:
        try:
            with self._lock:
                items = self._ticker_news(ticker)
        except Exception:
            logger.warning("Actualités Yahoo indisponibles pour %s", ticker, exc_info=True)
            return []
        return parse_news(items)
