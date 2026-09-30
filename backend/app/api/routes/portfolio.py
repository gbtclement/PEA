from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.orders import counter_for, paris_today
from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import Security, SecurityQuote, User
from app.repositories.orders import closes_since, order_lines
from app.schemas.portfolio import HistoryPointOut, PortfolioOut, PositionOut, SectorOut
from app.services.market_calendar import PARIS
from app.services.portfolio import sort_orders, value_history
from app.services.portfolio_value import eur_rate, value_portfolio

router = APIRouter(tags=["portfolio"])


def _pct(part: float, base: float) -> float | None:
    return round(part / base * 100, 2) if base else None


@router.get("/portfolio", response_model=PortfolioOut)
def get_portfolio(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> PortfolioOut:
    valued = value_portfolio(db, user.id, paris_today())
    rows: list[PositionOut] = []
    for v in valued.positions:
        p, security, quote = v.position, v.security, v.quote
        gain = round(v.value - p.cost, 2)
        rows.append(PositionOut(
            security_id=security.id, symbol=security.symbol, name=security.name, sector=security.sector,
            kind=security.kind, quantity=p.quantity, avg_cost=round(p.avg_cost, 4), price=v.price,
            change_pct=quote.change_pct if quote else None, value=v.value, gain=gain, gain_pct=_pct(gain, p.cost),
            weight=0.0,
        ))
    total, invested, day_change = valued.total, valued.invested, valued.day_change
    sectors: dict[str, float] = {}
    for r in rows:
        r.weight = round(r.value / total, 4) if total else 0.0
        key = "ETF" if r.kind == "etf" else (r.sector or "Autres")
        sectors[key] = sectors.get(key, 0.0) + r.value
    rows.sort(key=lambda r: -r.value)
    return PortfolioOut(
        total_value=total, invested=invested, gain=round(total - invested, 2), gain_pct=_pct(total - invested, invested),
        day_change=day_change, day_change_pct=_pct(day_change, total - day_change), realized_gain=valued.realized,
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
        rates[sid] = eur_rate(db.get(Security, sid))
        quote = db.get(SecurityQuote, sid)
        if quote is not None:
            day = quote.as_of.astimezone(PARIS).date()
            if not closes[sid] or closes[sid][-1][0] < day:
                closes[sid].append((day, quote.price))
    return [HistoryPointOut(date=p.day, value=p.value, invested=p.invested)
            for p in value_history(lines, closes, rates, paris_today())]
