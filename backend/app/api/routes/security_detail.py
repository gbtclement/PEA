import logging
import math
import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import INTRADAY_CACHE, NEWS_CACHE, get_market_provider
from app.api.cache import public_cache
from app.core.current_user import get_optional_user
from app.core.db import get_db
from app.models import DailyPrice, User
from app.providers.base import MarketDataProvider
from app.repositories.market_data import all_daily_prices, price_date_range
from app.repositories.screener import screener_rows
from app.repositories.user_settings import user_fee_grid
from app.schemas.security_detail import (
    Bar, ComponentOut, FundamentalsOut, HistoryOut, LinePoint, MacdPoint, NewsOut, ScoreOut, SecurityDetail,
    SimulationOut,
)
from app.services.fees import broker_fee
from app.services.fx import security_currency, to_eur
from app.services.durations import Unit, date_before
from app.services.indicators import macd, rsi, sma
from app.services.price_window import choose_interval, groups

router = APIRouter(tags=["securities"])
logger = logging.getLogger(__name__)

Period = Literal["1D", "1W", "1M", "6M", "1Y", "5Y", "10Y", "MAX", "custom"]
INTRADAY = {"1D": ("1d", "5m"), "1W": ("5d", "30m")}
DAILY_WINDOW = {"1M": 31, "6M": 183, "1Y": 365, "5Y": 365 * 5 + 1, "10Y": 365 * 10 + 2, "MAX": None}
SIMULATION_WINDOW = {"1W": 7, "1M": 31, "6M": 183, "1Y": 365}


def _row_or_404(db: Session, user_id: uuid.UUID | None, security_id: int):
    rows = screener_rows(db, user_id, security_id=security_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    return rows[0]


@router.get("/securities/{security_id}", response_model=SecurityDetail, dependencies=[Depends(public_cache(30))])
def get_security(security_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)) -> SecurityDetail:
    row = _row_or_404(db, user.id if user else None, security_id)
    security, quote, score, fundamentals, _ = row
    score_detail = None
    if score is not None:
        score_detail = ScoreOut(
            total=score.total, technical=score.technical, fundamental=score.fundamental,
            available_ratio=score.available_ratio, liquid=score.liquid, eligible_for_top=score.eligible_for_top,
            history_days=score.history_days, computed_at=score.computed_at,
            components=[ComponentOut(**c) for c in score.components or []],
        )
    return SecurityDetail(
        **SecurityDetail.fields_from(row),
        industry=security.industry,
        as_of=quote.as_of if quote else None,
        fundamentals=FundamentalsOut.model_validate(fundamentals) if fundamentals else None,
        score_detail=score_detail,
    )


def _intraday(provider: MarketDataProvider, ticker: str, period: str) -> list[Bar]:
    yahoo_period, interval = INTRADAY[period]

    def load() -> list[Bar]:
        return [Bar(time=int(b.time.timestamp()), open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume)
                for b in provider.get_intraday(ticker, yahoo_period, interval)]

    try:
        return INTRADAY_CACHE.get_or_set((ticker, period), load)
    except Exception:
        logger.warning("Intraday indisponible pour %s", ticker, exc_info=True)
        return []


def _merge(rows: list[DailyPrice], time: str) -> Bar:
    """Une barre pour plusieurs séances : ouverture de la première, clôture de la dernière, extrêmes et volume cumulés."""
    highs = [r.high for r in rows if r.high is not None]
    lows = [r.low for r in rows if r.low is not None]
    volumes = [r.volume for r in rows if r.volume is not None]
    return Bar(time=time, open=rows[0].open, high=max(highs) if highs else None, low=min(lows) if lows else None,
               close=rows[-1].close, volume=sum(volumes) if volumes else None)


@router.get("/securities/{security_id}/history", response_model=HistoryOut, dependencies=[Depends(public_cache(60))])
def get_history(
    security_id: int,
    period: Period = "6M",
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    provider: MarketDataProvider = Depends(get_market_provider),
) -> HistoryOut:
    security = _row_or_404(db, user.id if user else None, security_id)[0]
    if period == "custom":
        if start is None or end is None:
            raise HTTPException(status_code=422, detail="Indiquez une date de début et une date de fin.")
        if end < start:
            raise HTTPException(status_code=422, detail="La date de fin doit suivre la date de début.")
    first_date, last_date = price_date_range(db, security_id)
    if period in INTRADAY:
        return HistoryOut(period=period, intraday=True, interval=INTRADAY[period][1], first_date=first_date,
                          last_date=last_date, bars=_intraday(provider, security.yahoo_ticker, period),
                          sma50=[], sma200=[], rsi=[], macd=[])
    prices = all_daily_prices(db, security_id)
    closes = [p.close for p in prices]
    if period == "custom":
        low, high = start, end
    else:
        days = DAILY_WINDOW[period]
        low = prices[-1].date - timedelta(days=days) if days is not None and prices else date.min
        high = date.max
    window = [i for i, p in enumerate(prices) if low <= p.date <= high]
    interval = choose_interval(prices[window[0]].date, prices[window[-1]].date, len(window)) if window else "day"
    # Chaque groupe : indices dans `prices`. Une barre groupée porte la date de sa première séance,
    # et les indicateurs leur valeur à la dernière séance du groupe (mêmes dates que les barres).
    buckets = [[window[j] for j in g] for g in groups([prices[i].date for i in window], interval)]
    times = [prices[b[0]].date.isoformat() for b in buckets]

    def line(values: list[float | None]) -> list[LinePoint]:
        return [LinePoint(time=t, value=values[b[-1]]) for b, t in zip(buckets, times) if values[b[-1]] is not None]

    m = macd(closes)
    return HistoryOut(
        period=period, intraday=False, interval=interval, first_date=first_date, last_date=last_date,
        bars=[_merge([prices[i] for i in b], t) for b, t in zip(buckets, times)],
        sma50=line(sma(closes, 50)), sma200=line(sma(closes, 200)), rsi=line(rsi(closes)),
        macd=[MacdPoint(time=t, macd=m.macd[b[-1]], signal=m.signal[b[-1]], histogram=m.histogram[b[-1]])
              for b, t in zip(buckets, times)
              if m.macd[b[-1]] is not None and m.signal[b[-1]] is not None and m.histogram[b[-1]] is not None],
    )


@router.get("/securities/{security_id}/news", response_model=list[NewsOut], dependencies=[Depends(public_cache(300))])
def get_news(
    security_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    provider: MarketDataProvider = Depends(get_market_provider),
) -> list[NewsOut]:
    ticker = _row_or_404(db, user.id if user else None, security_id)[0].yahoo_ticker
    try:
        items = NEWS_CACHE.get_or_set(ticker, lambda: provider.get_news(ticker))
    except Exception:
        logger.warning("Actualités indisponibles pour %s", ticker, exc_info=True)
        return []
    return [NewsOut(title=i.title, url=i.url, publisher=i.publisher, published_at=i.published_at) for i in items[:10]]


@router.get("/securities/{security_id}/simulate", response_model=SimulationOut)
def simulate(
    security_id: int,
    amount: float = Query(..., gt=0, le=1_000_000),
    period: Literal["1W", "1M", "6M", "1Y"] = "1M",
    duration: int | None = Query(None, ge=1, le=36500),
    unit: Unit = "days",
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> SimulationOut:
    """Boutons rapides (`period`) ou durée libre (`duration` + `unit`, prioritaire)."""
    prices = all_daily_prices(db, security_id)
    last = prices[-1].date if prices else date.today()
    first_day = date_before(last, duration, unit) if duration is not None else last - timedelta(days=SIMULATION_WINDOW[period])
    return simulate_since(db, user.id if user else None, security_id, amount, first_day)


def simulate_since(db: Session, user_id: uuid.UUID | None, security_id: int, amount: float, first_day: date) -> SimulationOut:
    """Achat simulé à la première clôture à partir de `first_day`, revendu au dernier cours, frais inclus."""
    row = _row_or_404(db, user_id, security_id)
    security, quote = row[0], row[1]
    rate = to_eur(1.0, security_currency(security)) or 1.0  # le simulateur compte en euros
    prices = all_daily_prices(db, security_id)
    empty = dict(shares=0, invested=0.0, buy_fee=0.0, sell_fee=0.0, current_value=0.0, gain=0.0, gain_pct=None)
    if not prices:
        return SimulationOut(start_date=None, start_price=None, current_price=None,
                             message="Pas assez d'historique pour simuler cet achat.", **empty)
    start = next((p for p in prices if p.date >= first_day), prices[-1])
    note = None
    if first_day < prices[0].date:
        note = f"Historique disponible depuis le {prices[0].date:%d/%m/%Y} : la simulation part de cette date."
    start_price = round(start.close * rate, 4)
    current_price = round((quote.price if quote else prices[-1].close) * rate, 4)
    shares = math.floor(amount / start_price) if start_price > 0 else 0
    if shares == 0:
        return SimulationOut(
            start_date=start.date, start_price=start_price, current_price=current_price,
            message=f"Le montant ne permet pas d'acheter une action (cours de {start_price:.2f} €).".replace(".", ",", 1),
            note=note, **empty,
        )
    grid = user_fee_grid(db, user_id)
    invested = round(shares * start_price, 2)
    buy_fee, _ = broker_fee(invested, grid)
    current_value = round(shares * current_price, 2)
    sell_fee, _ = broker_fee(current_value, grid)
    gain = round(current_value - sell_fee - invested - buy_fee, 2)
    return SimulationOut(
        start_date=start.date, start_price=start_price, current_price=current_price, shares=shares,
        invested=invested, buy_fee=buy_fee, sell_fee=sell_fee, current_value=current_value, gain=gain,
        gain_pct=round(gain / (invested + buy_fee) * 100, 2), message=None, note=note,
    )
