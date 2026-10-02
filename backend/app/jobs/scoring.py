from collections import defaultdict
from dataclasses import asdict
from datetime import timedelta

from sqlalchemy import select, update

from app.jobs.context import JobContext
from app.models import SecurityFundamentals, SecurityQuote, SecurityScore
from app.repositories.market_data import daily_series, refreshable_securities
from app.repositories.scores import sector_median_pe, upsert_score
from app.services.fx import currency_for_market, to_eur
from app.services.indicators import macd, performance, rsi, sma
from app.services.market_calendar import PARIS
from app.services.scoring.score import ScoreInputs, compute_score

HISTORY_WINDOW = timedelta(days=420)  # ≈ 290 séances : assez pour la moyenne 200 jours et la perf 1 an
SPARKLINE_POINTS = 63
INDEX_TICKER = "^FCHI"


_FUNDAMENTAL_FIELDS = ("pe", "eps", "earnings_growth", "revenue_growth", "debt_to_equity", "profit_margin", "market_cap")


def _has_fundamentals(f: SecurityFundamentals | None) -> bool:
    """Une ligne vide (Yahoo n'a rien renvoyé) ne permet pas de conclure à l'absence de dividende."""
    return f is not None and any(getattr(f, name) is not None for name in _FUNDAMENTAL_FIELDS)


def _last(values: list) -> float | None:
    return values[-1] if values else None


def refresh_scores(ctx: JobContext) -> int:
    now = ctx.now()
    today = now.astimezone(PARIS).date()
    settings = ctx.settings
    with ctx.session_factory() as session:
        securities = [s for s in refreshable_securities(session) if s.kind != "index" or s.yahoo_ticker == INDEX_TICKER]
        series = daily_series(session, today - HISTORY_WINDOW)
        quotes = {q.security_id: q for q in session.scalars(select(SecurityQuote))}
        fundamentals = {f.security_id: f for f in session.scalars(select(SecurityFundamentals))}

        pe_by_sector: dict[str | None, list[float]] = defaultdict(list)
        for s in securities:
            f = fundamentals.get(s.id)
            if s.kind == "stock" and f and f.pe and f.pe > 0:
                pe_by_sector[s.sector].append(f.pe)
        medians = sector_median_pe(pe_by_sector)

        def closes_for(security) -> list[float]:
            bars = series.get(security.id, [])
            closes = [b.close for b in bars]
            quote = quotes.get(security.id)
            if quote and (not bars or quote.as_of.astimezone(PARIS).date() > bars[-1].date):
                closes.append(quote.price)  # séance en cours
            return closes

        index = next((s for s in securities if s.yahoo_ticker == INDEX_TICKER), None)
        index_perf_3m = performance(closes_for(index), 63) if index else None

        count = 0
        processed: list[int] = []
        for s in securities:
            if s.kind == "index":
                continue
            processed.append(s.id)
            bars = series.get(s.id, [])
            closes = closes_for(s)
            f = fundamentals.get(s.id)
            macd_values = macd(closes)
            dividend_yield = None
            if _has_fundamentals(f):
                dividend_yield = f.dividend_yield if f.dividend_yield is not None else 0.0  # pas de dividende déclaré
            result = compute_score(ScoreInputs(
                price=_last(closes),
                sma50=_last(sma(closes, 50)),
                sma200=_last(sma(closes, 200)),
                perf_3m=performance(closes, 63),
                index_perf_3m=index_perf_3m,
                rsi=_last(rsi(closes)),
                macd_line=macd_values.macd[-10:],
                signal_line=macd_values.signal[-10:],
                pe=f.pe if f else None,
                sector_median_pe=medians.get(s.sector, medians.get(None)),
                eps_growth=f.earnings_growth if f else None,
                revenue_growth=f.revenue_growth if f else None,
                debt_to_equity=f.debt_to_equity if f else None,
                profit_margin=f.profit_margin if f else None,
                dividend_yield=dividend_yield,
            ), kind=s.kind)
            recent = bars[-20:]
            turnover = sum(b.close * (b.volume or 0) for b in recent) / len(recent) if recent else 0.0
            turnover_eur = to_eur(turnover, currency_for_market(s.market)) or 0.0
            liquid = turnover_eur >= settings.min_turnover_eur
            eligible_for_top = (
                s.kind == "stock" and liquid
                and len(bars) >= settings.min_history_days
                and result.total is not None and result.available_ratio >= settings.min_available_ratio
            )
            upsert_score(session, s.id, {
                "computed_at": now,
                "total": result.total,
                "technical": result.technical,
                "fundamental": result.fundamental,
                "components": [asdict(c) for c in result.components],
                "available_ratio": result.available_ratio,
                "liquid": liquid,
                "history_days": len(bars),
                "avg_turnover_eur": turnover_eur,
                "eligible_for_top": eligible_for_top,
                "perf_1w": performance(closes, 5),
                "perf_1m": performance(closes, 21),
                "perf_3m": performance(closes, 63),
                "perf_1y": performance(closes, 252),
                "sparkline": [round(c, 4) for c in closes[-SPARKLINE_POINTS:]],
            })
            count += 1
        # Titres sortis du périmètre (inactifs, devenus indices) : ils ne peuvent plus figurer dans le top.
        session.execute(
            update(SecurityScore)
            .where(SecurityScore.security_id.notin_(processed), SecurityScore.eligible_for_top.is_(True))
            .values(eligible_for_top=False)
        )
        session.commit()
    return count
