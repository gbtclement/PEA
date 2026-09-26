from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.orders import counter_for, paris_today
from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import DailyPrice, Security, SecurityQuote, User
from app.repositories.orders import closes_since, order_lines
from app.schemas.portfolio import HistoryPointOut, PortfolioOut, PositionOut, SectorOut
from app.services.fx import currency_for_market, to_eur
from app.services.market_calendar import PARIS
from app.services.portfolio import compute_positions, sort_orders, value_history

router = APIRouter(tags=["portfolio"])


def _rate(security: Security) -> float:
    return to_eur(1.0, currency_for_market(security.market)) or 1.0


def _last_close(db: Session, security_id: int) -> float | None:
    return db.scalars(select(DailyPrice.close).where(DailyPrice.security_id == security_id)
                      .order_by(DailyPrice.date.desc()).limit(1)).first()


def _pct(part: float, base: float) -> float | None:
    return round(part / base * 100, 2) if base else None


@router.get("/portfolio", response_model=PortfolioOut)
def get_portfolio(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> PortfolioOut:
    positions = compute_positions(order_lines(db, user.id))
    realized = round(sum(p.realized_gain for p in positions.values()), 2)
    open_positions = [p for p in positions.values() if p.quantity]
    rows: list[PositionOut] = []
    day_change = 0.0
    for p in open_positions:
        security = db.get(Security, p.security_id)
        quote = db.get(SecurityQuote, p.security_id)
        rate = _rate(security)
        native = quote.price if quote else _last_close(db, p.security_id)
        price = round(native * rate, 4) if native is not None else None
        value = round(p.quantity * price, 2) if price is not None else round(p.cost, 2)
        if quote and quote.previous_close:
            day_change += p.quantity * (quote.price - quote.previous_close) * rate
        gain = round(value - p.cost, 2)
        rows.append(PositionOut(
            security_id=security.id, symbol=security.symbol, name=security.name, sector=security.sector,
            kind=security.kind, quantity=p.quantity, avg_cost=round(p.avg_cost, 4), price=price,
            change_pct=quote.change_pct if quote else None, value=value, gain=gain, gain_pct=_pct(gain, p.cost),
            weight=0.0,
        ))
    total = round(sum(r.value for r in rows), 2)
    invested = round(sum(p.cost for p in open_positions), 2)
    sectors: dict[str, float] = {}
    for r in rows:
        r.weight = round(r.value / total, 4) if total else 0.0
        key = "ETF" if r.kind == "etf" else (r.sector or "Autres")
        sectors[key] = sectors.get(key, 0.0) + r.value
    rows.sort(key=lambda r: -r.value)
    day_change = round(day_change, 2)
    return PortfolioOut(
        total_value=total, invested=invested, gain=round(total - invested, 2), gain_pct=_pct(total - invested, invested),
        day_change=day_change, day_change_pct=_pct(day_change, total - day_change), realized_gain=realized,
        positions=rows,
        sectors=[SectorOut(sector=k, value=round(v, 2), weight=round(v / total, 4) if total else 0.0)
                 for k, v in sorted(sectors.items(), key=lambda kv: -kv[1])],
        counter=counter_for(db, user.id),
    )


@router.get("/portfolio/history", response_model=list[HistoryPointOut])
def get_portfolio_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[HistoryPointOut]:
    lines = order_lines(db, user.id)
    if not lines:
        return []
    ids = {line.security_id for line in lines}
    closes = closes_since(db, ids, sort_orders(lines)[0].trade_date)
    rates: dict[int, float] = {}
    for sid in ids:
        rates[sid] = _rate(db.get(Security, sid))
        quote = db.get(SecurityQuote, sid)
        if quote is not None:
            day = quote.as_of.astimezone(PARIS).date()
            if not closes[sid] or closes[sid][-1][0] < day:
                closes[sid].append((day, quote.price))
    return [HistoryPointOut(date=p.day, value=p.value, invested=p.invested)
            for p in value_history(lines, closes, rates, paris_today())]
