
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.cache import public_cache
from app.core.current_user import get_optional_user
from app.core.db import get_db
from app.models import User
from app.repositories.screener import screener_rows
from app.repositories.user_envelopes import user_envelopes
from app.schemas.rankings import HeatmapItem, Movers, TopItem
from app.schemas.screener import ScreenerRow
from app.services.fx import to_eur

router = APIRouter(tags=["rankings"])
HEATMAP_SIZE = 200


def _liquid_stocks(db: Session, user: User | None) -> list:
    """Actions liquides cotées aujourd'hui, filtrées par les enveloppes du membre (un visiteur voit tout)."""
    envelopes = user_envelopes(db, user.id if user else None)
    return [
        row for row in screener_rows(db, user.id if user else None, kind="stock", envelopes=envelopes)
        if row[2] is not None and row[2].liquid and row[1] is not None and row[1].change_pct is not None
    ]


@router.get("/rankings/top", response_model=list[TopItem], dependencies=[Depends(public_cache(60))])
def get_top(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[TopItem]:
    envelopes = user_envelopes(db, user.id if user else None)
    rows = screener_rows(db, user.id if user else None, kind="stock", only_top=True, limit=limit, envelopes=envelopes)
    return [TopItem.build(row) for row in rows]


@router.get("/rankings/movers", response_model=Movers, dependencies=[Depends(public_cache(60))])
def get_movers(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Movers:
    rows = sorted(_liquid_stocks(db, user), key=lambda r: r[1].change_pct, reverse=True)
    return Movers(
        gainers=[ScreenerRow.build(r) for r in rows[:limit]],
        losers=[ScreenerRow.build(r) for r in reversed(rows[-limit:])],
    )


@router.get("/market/heatmap", response_model=list[HeatmapItem], dependencies=[Depends(public_cache(120))])
def get_heatmap(db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)) -> list[HeatmapItem]:
    items = []
    for security, quote, _score, fundamentals, _fav in _liquid_stocks(db, user):
        cap = to_eur(fundamentals.market_cap, fundamentals.currency) if fundamentals else None
        if cap:
            items.append(HeatmapItem(id=security.id, symbol=security.symbol, name=security.name,
                                     sector=security.sector or "Autres", market_cap_eur=cap,
                                     change_pct=quote.change_pct))
    return sorted(items, key=lambda i: i.market_cap_eur, reverse=True)[:HEATMAP_SIZE]
