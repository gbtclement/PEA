import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.current_user import get_optional_user
from app.core.db import get_db
from app.models import User
from app.repositories.screener import screener_rows
from app.schemas.rankings import HeatmapItem, Movers, TopItem
from app.schemas.screener import ScreenerRow
from app.services.fx import to_eur

router = APIRouter(tags=["rankings"])
HEATMAP_SIZE = 200


def _liquid_eligible_stocks(db: Session, user_id: uuid.UUID | None) -> list:
    return [
        row for row in screener_rows(db, user_id, kind="stock")
        if row[0].envelope_status("pea") == "eligible" and row[2] is not None and row[2].liquid
        and row[1] is not None and row[1].change_pct is not None
    ]


@router.get("/rankings/top", response_model=list[TopItem])
def get_top(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[TopItem]:
    return [TopItem.build(row) for row in screener_rows(db, user.id if user else None, kind="stock", only_top=True, limit=limit)]


@router.get("/rankings/movers", response_model=Movers)
def get_movers(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Movers:
    rows = sorted(_liquid_eligible_stocks(db, user.id if user else None), key=lambda r: r[1].change_pct, reverse=True)
    return Movers(
        gainers=[ScreenerRow.build(r) for r in rows[:limit]],
        losers=[ScreenerRow.build(r) for r in reversed(rows[-limit:])],
    )


@router.get("/market/heatmap", response_model=list[HeatmapItem])
def get_heatmap(db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)) -> list[HeatmapItem]:
    items = []
    for security, quote, _score, fundamentals, _fav in _liquid_eligible_stocks(db, user.id if user else None):
        cap = to_eur(fundamentals.market_cap, fundamentals.currency) if fundamentals else None
        if cap:
            items.append(HeatmapItem(id=security.id, symbol=security.symbol, name=security.name,
                                     sector=security.sector or "Autres", market_cap_eur=cap,
                                     change_pct=quote.change_pct))
    return sorted(items, key=lambda i: i.market_cap_eur, reverse=True)[:HEATMAP_SIZE]
