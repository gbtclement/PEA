import logging
from collections import defaultdict
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import replace
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.context import JobContext
from app.jobs.tiers import tier_tickers
from app.models import Security, SecurityFundamentals
from app.providers.base import DailyBar, Quote
from app.repositories.market_data import (
    delete_daily_prices, first_price_dates, fundamentals_due, incomplete_history_securities, last_two_closes,
    latest_price_dates, mark_history_complete, refreshable_securities, stored_close, ticker_ids, upsert_daily_bars,
    upsert_fundamentals, upsert_quotes,
)
from app.repositories.securities import update_classification
from app.services.market_calendar import CLOSE as PARIS_CLOSE
from app.services.market_calendar import PARIS, calendar_for_market

# En dessous de cette part de titres reçus, on considère que Yahoo est indisponible.
MIN_RESPONSE_RATIO = 0.2
# Écart de clôture sur le jour de recouvrement au-delà duquel l'historique a été réajusté (division, dividende).
ADJUSTMENT_TOLERANCE = 0.005
# Titres par appel au fournisseur pendant le rattrapage ; chaque paquet est validé à part (reprise après une panne).
BACKFILL_BATCH = 50  # ~450 Mo de pic mémoire pour le worker (900 Mo à 100)
# Sans cours depuis ce délai (ou, sans aucun cours, ajouté depuis ce délai), un titre que Yahoo ne renvoie pas est abandonné.
DEAD_AFTER = timedelta(days=30)
FUNDAMENTALS_DAYS = 5  # chaque action est relue une fois par semaine (jours ouvrés)

logger = logging.getLogger(__name__)


def _ensure_response(requested: int, received: int, what: str) -> None:
    if requested and received < max(1, requested * MIN_RESPONSE_RATIO):
        raise RuntimeError(f"Yahoo n'a renvoyé que {received}/{requested} {what} : source probablement indisponible")


def _at_place_close(quote: Quote, market: str) -> Quote:
    """Cours d'une séance passée (Yahoo le date à 17 h 35, heure de Paris) : heure de clôture de sa place.

    À 15 h 31, avant la première barre de New York, le cours de la veille daterait sinon de 17 h 35 au lieu de 22 h.
    """
    local = quote.as_of.astimezone(PARIS)
    if local.time() != PARIS_CLOSE:
        return quote  # cours de la séance en cours : son heure est la bonne
    return replace(quote, as_of=calendar_for_market(market).session_close(local.date()))


def refresh_quotes(ctx: JobContext, tier: int) -> int:
    with ctx.session_factory() as session:
        tickers = tier_tickers(session, tier, ctx.settings.tier2_size, ctx.now())
    if not tickers:
        return 0
    quotes = ctx.market.get_quotes(tickers)
    with ctx.session_factory() as session:
        ids = ticker_ids(session, list(quotes))
        markets = dict(session.execute(select(Security.yahoo_ticker, Security.market)
                                       .where(Security.yahoo_ticker.in_(list(quotes)))).all())
        quotes = {t: _at_place_close(q, markets.get(t, "")) for t, q in quotes.items()}
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
    by_start: dict[date, list[str]] = defaultdict(list)
    with ctx.session_factory() as session:
        last_dates = latest_price_dates(session)
        for security in refreshable_securities(session):
            if region is not None and calendar_for_market(security.market).code != region:
                continue
            if security.id not in last_dates:
                continue  # titre sans aucun cours : chargé en entier par le rattrapage, paquet par paquet
            ids[security.yahoo_ticker] = security.id
            # On repart du dernier jour connu (inclus) pour corriger une séance incomplète.
            by_start[last_dates[security.id]].append(security.yahoo_ticker)
    total = 0
    received: set[str] = set()
    readjusted: list[str] = []
    for start, tickers in sorted(by_start.items()):
        history = ctx.market.get_daily_history(sorted(tickers), start)
        received.update(history)
        with ctx.session_factory() as session:
            for ticker, bars in history.items():
                if _is_readjusted(bars, start, stored_close(session, ids[ticker], start)):
                    readjusted.append(ticker)
                    continue
                total += upsert_daily_bars(session, ids[ticker], bars)
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


def backfill_history(ctx: JobContext, guard: Callable[[], AbstractContextManager] = nullcontext,
                     pause: Callable[[], None] = lambda: None) -> int:
    """Rattrapage de l'historique complet : nouveaux titres en entier, anciens titres avant leur première date stockée.

    `guard()` entoure chaque paquet : le verrou des tâches lourdes est rendu entre deux paquets, et `pause()`
    (appelée hors du verrou) laisse à une tâche qui l'attend le temps de le prendre.
    """
    with ctx.session_factory() as session:
        incomplete = incomplete_history_securities(session)
        targets = [(s.yahoo_ticker, s.id) for s in incomplete]
        created = {s.id: s.created_at for s in incomplete}
        last_dates = latest_price_dates(session)
    total = 0
    for offset in range(0, len(targets), BACKFILL_BATCH):
        batch = dict(targets[offset:offset + BACKFILL_BATCH])
        with guard():
            total += _backfill_batch(ctx, batch, created, last_dates)
        if offset + BACKFILL_BATCH < len(targets):
            pause()
    return total


def _backfill_batch(ctx: JobContext, batch: dict[str, int], created: dict[int, datetime],
                    last_dates: dict[int, date]) -> int:
    cutoff = ctx.now().astimezone(PARIS).date() - DEAD_AFTER
    total = 0
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
        # Absent de la réponse depuis longtemps (plus coté, ou jamais connu de Yahoo) : rien à rattraper.
        done += [security_id for ticker, security_id in batch.items() if ticker not in history and (
            last_dates[security_id] < cutoff if security_id in last_dates
            else created[security_id].astimezone(PARIS).date() < cutoff)]
        mark_history_complete(session, done)
        session.commit()
    # Dernière clôture comme cours affiché : un titre ajouté bourse fermée apparaît sans attendre la séance suivante.
    _write_closing_quotes(ctx, [batch[ticker] for ticker in history])
    retry = len(batch) - len(done)
    if retry:
        logger.info("Historique complet non rattrapé pour %d titres (réessai au prochain passage)", retry)
    return total


def refresh_fundamentals(ctx: JobContext) -> int:
    with ctx.session_factory() as session:
        targets = fundamentals_due(session, FUNDAMENTALS_DAYS)
    count = 0
    for security_id, ticker in targets:
        fundamentals = ctx.market.get_fundamentals(ticker)
        with ctx.session_factory() as session:
            session.get(Security, security_id).fundamentals_checked_at = ctx.now()
            if fundamentals is None:
                session.commit()
                continue
            upsert_fundamentals(session, security_id, fundamentals)
            session.flush()
            update_classification(session.get(Security, security_id), fundamentals.sector, fundamentals.industry,
                                  session.get(SecurityFundamentals, security_id))
            session.commit()
        count += 1
    return count
