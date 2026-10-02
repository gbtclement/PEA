import logging
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.context import JobContext
from app.jobs.tiers import tier_tickers
from app.models import Security, SecurityFundamentals
from app.providers.base import DailyBar, Quote
from app.repositories.market_data import (
    delete_daily_prices, first_price_dates, incomplete_history_securities, last_two_closes, latest_price_dates,
    mark_history_complete, refreshable_securities, stored_close, ticker_ids, upsert_daily_bars, upsert_fundamentals,
    upsert_quotes,
)
from app.repositories.securities import update_classification
from app.services.market_calendar import PARIS, calendar_for_market

# En dessous de cette part de titres reçus, on considère que Yahoo est indisponible.
MIN_RESPONSE_RATIO = 0.2
# Écart de clôture sur le jour de recouvrement au-delà duquel l'historique a été réajusté (division, dividende).
ADJUSTMENT_TOLERANCE = 0.005
# Titres par appel au fournisseur pendant le rattrapage ; chaque paquet est validé à part (reprise après une panne).
BACKFILL_BATCH = 100
# Sans cours depuis ce délai, un titre que Yahoo ne renvoie plus est considéré comme radié.
DEAD_AFTER = timedelta(days=30)

logger = logging.getLogger(__name__)


def _ensure_response(requested: int, received: int, what: str) -> None:
    if requested and received < max(1, requested * MIN_RESPONSE_RATIO):
        raise RuntimeError(f"Yahoo n'a renvoyé que {received}/{requested} {what} : source probablement indisponible")


def refresh_quotes(ctx: JobContext, tier: int) -> int:
    with ctx.session_factory() as session:
        tickers = tier_tickers(session, tier, ctx.settings.tier2_size, ctx.now())
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
        markets = dict(session.execute(select(Security.id, Security.market).where(Security.id.in_(security_ids))).all())
        for security_id, rows in last_two_closes(session, security_ids).items():
            last = rows[0]
            previous = rows[1].close if len(rows) > 1 else None
            quotes[security_id] = Quote(
                price=last.close,
                previous_close=previous,
                change_pct=(last.close / previous - 1) * 100 if previous else None,
                volume=last.volume,
                as_of=calendar_for_market(markets[security_id]).session_close(last.date),
            )
        upsert_quotes(session, quotes, only_if_newer=True)
        session.commit()


def refresh_daily_history(ctx: JobContext, region: str | None = None) -> int:
    """Clôtures du jour ; `region` (europe, us) limite le passage aux titres d'une séance."""
    ids: dict[str, int] = {}
    # Clé None : titre sans aucun cours, chargé en entier (period="max").
    by_start: dict[date | None, list[str]] = defaultdict(list)
    with ctx.session_factory() as session:
        last_dates = latest_price_dates(session)
        for security in refreshable_securities(session):
            if region is not None and calendar_for_market(security.market).code != region:
                continue
            ids[security.yahoo_ticker] = security.id
            # On repart du dernier jour connu (inclus) pour corriger une séance incomplète.
            by_start[last_dates.get(security.id)].append(security.yahoo_ticker)
    total = 0
    received: set[str] = set()
    readjusted: list[str] = []
    for start, tickers in sorted(by_start.items(), key=lambda item: (item[0] is not None, item[0] or date.min)):
        history = ctx.market.get_daily_history(sorted(tickers), start)
        received.update(history)
        with ctx.session_factory() as session:
            complete: list[int] = []
            for ticker, bars in history.items():
                if start is not None and _is_readjusted(bars, start, stored_close(session, ids[ticker], start)):
                    readjusted.append(ticker)
                    continue
                total += upsert_daily_bars(session, ids[ticker], bars)
                if start is None:
                    complete.append(ids[ticker])
            mark_history_complete(session, complete)
            session.commit()
    if readjusted:
        history = ctx.market.get_daily_history(sorted(readjusted), None)
        with ctx.session_factory() as session:
            for ticker, bars in history.items():
                delete_daily_prices(session, ids[ticker])
                total += upsert_daily_bars(session, ids[ticker], bars)
            mark_history_complete(session, [ids[t] for t in history])
            session.commit()
    _write_closing_quotes(ctx, [ids[t] for t in received])
    _ensure_response(len(ids), len(received), "historiques")
    return total


def _junction_readjusted(session: Session, security_id: int, bars: list[DailyBar], first: date) -> bool:
    """Compare la série Yahoo aux cours stockés sur leur première date commune (à partir de la première stockée)."""
    overlap = next((bar for bar in bars if bar.date >= first), None)
    if overlap is None:
        return False  # Yahoo ne couvre que l'avant : rien à comparer, on ajoute les cours antérieurs
    stored = stored_close(session, security_id, overlap.date)
    if stored is None:
        return True  # pas de date commune vérifiable : la série Yahoo complète fait foi
    return _is_readjusted(bars, overlap.date, stored)


def backfill_history(ctx: JobContext) -> int:
    """Rattrapage de l'historique complet : ajoute les cours antérieurs à la première date stockée."""
    today = ctx.now().astimezone(PARIS).date()
    with ctx.session_factory() as session:
        targets = [(s.yahoo_ticker, s.id) for s in incomplete_history_securities(session)]
        last_dates = latest_price_dates(session)
    total = 0
    for offset in range(0, len(targets), BACKFILL_BATCH):
        batch = dict(targets[offset:offset + BACKFILL_BATCH])
        history = ctx.market.get_daily_history(sorted(batch), None)
        with ctx.session_factory() as session:
            firsts = first_price_dates(session, list(batch.values()))
            done: list[int] = []
            for ticker, bars in history.items():
                security_id = batch[ticker]
                first = firsts.get(security_id)
                try:
                    with session.begin_nested():  # un titre refusé n'empêche pas les autres
                        if first is not None and _junction_readjusted(session, security_id, bars, first):
                            # Yahoo a réajusté les cours depuis (dividende, division) : on remplace toute la série.
                            delete_daily_prices(session, security_id)
                            written = upsert_daily_bars(session, security_id, bars)
                        else:
                            written = upsert_daily_bars(session, security_id,
                                                        [b for b in bars if first is None or b.date < first])
                except Exception:
                    logger.warning("Rattrapage de l'historique impossible pour %s", ticker, exc_info=True)
                    continue
                total += written
                done.append(security_id)
            # Titre absent de la réponse et sans cours depuis longtemps : plus coté, rien à rattraper.
            done += [security_id for ticker, security_id in batch.items() if ticker not in history
                     and security_id in last_dates and today - last_dates[security_id] > DEAD_AFTER]
            mark_history_complete(session, done)
            session.commit()
        retry = len(batch) - len(done)
        if retry:
            logger.info("Historique complet non rattrapé pour %d titres (réessai au prochain passage)", retry)
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
