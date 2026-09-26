from collections import defaultdict
from datetime import date, timedelta

from app.jobs.context import JobContext
from app.jobs.tiers import tier_tickers
from app.models import Security
from app.repositories.market_data import (
    latest_price_dates, refreshable_securities, ticker_ids, upsert_daily_bars, upsert_fundamentals, upsert_quotes,
)
from app.repositories.securities import update_classification
from app.services.market_calendar import PARIS


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
    return count


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
    for start, tickers in sorted(by_start.items()):
        history = ctx.market.get_daily_history(sorted(tickers), start)
        with ctx.session_factory() as session:
            for ticker, bars in history.items():
                total += upsert_daily_bars(session, ids[ticker], bars)
            session.commit()
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
            update_classification(session.get(Security, security_id), fundamentals.sector, fundamentals.industry)
            session.commit()
        count += 1
    return count
