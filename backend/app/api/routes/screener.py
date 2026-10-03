from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.cache import public_cache
from app.core.current_user import get_optional_user
from app.core.db import get_db
from app.models import User
from app.repositories.screener import ScreenerQuery, screener_facets, screener_page
from app.schemas.screener import ScreenerFacets, ScreenerPage, ScreenerRow

router = APIRouter(tags=["screener"])

SortKey = Literal["name", "price", "change_pct", "perf_1w", "perf_1m", "perf_1y", "score", "pe", "dividend_yield"]


@router.get("/screener", response_model=ScreenerPage, dependencies=[Depends(public_cache(60))])
def get_screener(
    kind: Literal["stock", "etf"] | None = None,
    region: Literal["europe", "us"] | None = None,
    q: str = Query("", max_length=100),
    sector: str | None = Query(None, max_length=128),
    country: str | None = Query(None, max_length=2),
    market: str | None = Query(None, max_length=64),
    envelope: Literal["pea", "pea_pme"] | None = None,
    min_score: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    liquid: bool = False,
    fav: bool = False,
    sort: SortKey = "name",
    order: Literal["asc", "desc"] = "asc",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ScreenerPage:
    """Une page de l'Explorer ou des ETF : filtres, tri et pagination côté serveur (des milliers de titres par région)."""
    query = ScreenerQuery(kind=kind, region=region, q=q, sector=sector, country=country, market=market, envelope=envelope,
                          min_score=min_score, min_price=min_price, max_price=max_price, liquid=liquid, fav=fav,
                          sort=sort, order=order)
    rows, total = screener_page(db, user.id if user else None, query, limit=limit, offset=offset)
    return ScreenerPage(items=[ScreenerRow.build(row) for row in rows], total=total)


@router.get("/screener/facets", response_model=ScreenerFacets, dependencies=[Depends(public_cache(600))])
def get_screener_facets(kind: Literal["stock", "etf"] | None = None, region: Literal["europe", "us"] | None = None,
                        db: Session = Depends(get_db)) -> ScreenerFacets:
    return ScreenerFacets(**screener_facets(db, kind, region))
