from collections import defaultdict
from datetime import date, datetime, timedelta

from app.jobs.context import JobContext
from app.jobs.tiers import tier_tickers
from app.models import Security, SecurityFundamentals
from app.providers.base import DailyBar, Quote
from app.repositories.market_data import (
    delete_daily_prices, last_two_closes, latest_price_dates, refreshable_securities, stored_close, ticker_ids,
    upsert_daily_bars, upsert_fundamentals, upsert_quotes,
)
from app.repositories.securities import update_classification
from app.services.market_calendar import CLOSE, PARIS

# En dessous de cette part de titres reçus, on considère que Yahoo est indisponible.
MIN_RESPONSE_RATIO = 0.2
# Écart de clôture sur le jour de recouvrement au-delà duquel l'historique a été réajusté (division, dividende).
ADJUSTMENT_TOLERANCE = 0.005


def _ensure_response(requested: int, received: int, what: str) -> None:
    if requested and received < max(1, requested * MIN_RESPONSE_RATIO):
        raise RuntimeError(f"Yahoo n'a renvoyé que {received}/{requested} {what} : source probablement indisponible")


def refresh_quotes(ctx: JobContext, tier: int) -> int:
    with ctx.session_factory() as session:
        tickers = tier_tickers(session, tier, ctx.settings.tier2_size)
    if not tickers:
        return 0
    quotes = ctx.market.get_quotes(tickers)
    with ctx.session_factory() as session:
        ids = ticker_ids(session, list(quotes))
        count = upsert_quotes(session, {ids[t]: q for t, q in quotes.items() if t in ids})
        session.commit()
    _ensure_response(len(tickers), len(quotes), "cours")
    return count


def _is_readjusted(bars: list[DailyBar], start: date, previous_close: float | None) -> bool:
    overlap = next((bar for bar in bars if bar.date == start), None)
    if overlap is None or not previous_close:
        return False
    return abs(overlap.close / previous_close - 1) > ADJUSTMENT_TOLERANCE


def _write_closing_quotes(ctx: JobContext, security_ids: list[int]) -> None:
    """La clôture de la veille devient le cours affiché le soir et le week-end (sans écraser un cours plus récent)."""
    with ctx.session_factory() as session:
        quotes: dict[int, Quote] = {}
        for security_id, rows in last_two_closes(session, security_ids).items():
            last = rows[0]
            previous = rows[1].close if len(rows) > 1 else None
            quotes[security_id] = Quote(
                price=last.close,
                previous_close=previous,
                change_pct=(last.close / previous - 1) * 100 if previous else None,
                volume=last.volume,
                as_of=datetime.combine(last.date, CLOSE, tzinfo=PARIS),
            )
        upsert_quotes(session, quotes, only_if_newer=True)
        session.commit()


def refresh_daily_history(ctx: JobContext) -> int:
    today = ctx.now().astimezone(PARIS).date()
    default_start = today - timedelta(days=365 * ctx.settings.history_years)
    ids: dict[str, int] = {}
    by_start: dict[date, list[str]] = defaultdict(list)
    with ctx.session_factory() as session:
        last_dates = latest_price_dates(session)
        for security in refreshable_securities(session):
            ids[security.yahoo_ticker] = security.id
            # On repart du dernier jour connu (inclus) pour corriger une séance incomplète.
            by_start[last_dates.get(security.id, default_start)].append(security.yahoo_ticker)
    total = 0
    received: set[str] = set()
    readjusted: list[str] = []
    for start, tickers in sorted(by_start.items()):
        history = ctx.market.get_daily_history(sorted(tickers), start)
        received.update(history)
        with ctx.session_factory() as session:
            for ticker, bars in history.items():
                if start != default_start and _is_readjusted(bars, start, stored_close(session, ids[ticker], start)):
                    readjusted.append(ticker)
                    continue
                total += upsert_daily_bars(session, ids[ticker], bars)
            session.commit()
    if readjusted:
        history = ctx.market.get_daily_history(sorted(readjusted), default_start)
        with ctx.session_factory() as session:
            for ticker, bars in history.items():
                delete_daily_prices(session, ids[ticker])
                total += upsert_daily_bars(session, ids[ticker], bars)
            session.commit()
    _write_closing_quotes(ctx, [ids[t] for t in received])
    _ensure_response(len(ids), len(received), "historiques")
    return total


def refresh_fundamentals(ctx: JobContext) -> int:
    with ctx.session_factory() as session:
        targets = [(s.id, s.yahoo_ticker) for s in refreshable_securities(session) if s.kind == "stock"]
    count = 0
    for security_id, ticker in targets:
        fundamentals = ctx.market.get_fundamentals(ticker)
        if fundamentals is None:
            continue
        with ctx.session_factory() as session:
            upsert_fundamentals(session, security_id, fundamentals)
            session.flush()
            update_classification(session.get(Security, security_id), fundamentals.sector, fundamentals.industry,
                                  session.get(SecurityFundamentals, security_id))
            session.commit()
        count += 1
    return count
