import logging
import math
import time
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from datetime import time as dtime
from typing import Any

import pandas as pd
import yfinance as yf

from app.providers.base import DailyBar, Fundamentals, Quote
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
    return [
        DailyBar(
            date=index.date(), open=_num(row["Open"]), high=_num(row["High"]), low=_num(row["Low"]),
            close=float(row["Close"]), volume=_int(row["Volume"]),
        )
        for index, row in frame.iterrows()
    ]


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
    )


class YahooProvider:
    def __init__(
        self,
        chunk_size: int = 50,
        pause_seconds: float = 1.0,
        fundamentals_pause_seconds: float = 0.5,
        download: Callable[..., pd.DataFrame] | None = None,
        ticker_info: Callable[[str], dict[str, Any]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._chunk_size = chunk_size
        self._pause = pause_seconds
        self._fundamentals_pause = fundamentals_pause_seconds
        self._download = download or yf.download
        self._ticker_info = ticker_info or (lambda ticker: yf.Ticker(ticker).info)
        self._sleep = sleep
        self._now = now

    def _chunks(self, tickers: list[str]) -> Iterator[list[str]]:
        for start in range(0, len(tickers), self._chunk_size):
            if start:
                self._sleep(self._pause)
            yield tickers[start:start + self._chunk_size]

    def _download_frames(self, tickers: list[str], **kwargs: Any) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        for chunk in self._chunks(tickers):
            try:
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

    def get_daily_history(self, tickers: list[str], start: date) -> dict[str, list[DailyBar]]:
        frames = self._download_frames(tickers, start=start.isoformat(), interval="1d")
        return {ticker: bars_from_frame(frame) for ticker, frame in frames.items()}

    def get_fundamentals(self, ticker: str) -> Fundamentals | None:
        try:
            info = with_retries(lambda: self._ticker_info(ticker), sleep=self._sleep)
        except Exception:
            logger.warning("Fondamentaux Yahoo indisponibles pour %s", ticker, exc_info=True)
            return None
        finally:
            self._sleep(self._fundamentals_pause)
        return fundamentals_from_info(info) if info else None
