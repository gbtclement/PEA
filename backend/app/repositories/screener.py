import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Numeric, Row, func, literal, or_, select
from sqlalchemy.orm import Session

from app.models import Favorite, Security, SecurityFundamentals, SecurityQuote, SecurityScore
from app.repositories.envelopes import envelope_clause
from app.repositories.securities import escape_like
from app.services.market_calendar import US_MARKETS


def screener_rows(
    session: Session, user_id: uuid.UUID | None, *, kind: str | None = None, only_top: bool = False, limit: int | None = None,
    security_id: int | None = None, envelopes: Sequence[str] = (), region: str | None = None,
) -> list[Row]:
    if user_id is None:
        is_favorite = literal(False).label("is_favorite")  # visiteur sans compte
    else:
        is_favorite = (
            select(Favorite.security_id)
            .where(Favorite.user_id == user_id, Favorite.security_id == Security.id)
            .exists()
            .label("is_favorite")
        )
    stmt = (
        select(Security, SecurityQuote, SecurityScore, SecurityFundamentals, is_favorite)
        .outerjoin(SecurityQuote, SecurityQuote.security_id == Security.id)
        .outerjoin(SecurityScore, SecurityScore.security_id == Security.id)
        .outerjoin(SecurityFundamentals, SecurityFundamentals.security_id == Security.id)
        .where(Security.active.is_(True))
    )
    if security_id is not None:
        stmt = stmt.where(Security.id == security_id)  # une fiche s'affiche toujours, quelle que soit l'enveloppe
    else:
        stmt = stmt.where(Security.kind == kind) if kind else stmt.where(Security.kind != "index")
        if not only_top:  # le top exige déjà 200 séances d'historique
            stmt = stmt.where(SecurityQuote.security_id.is_not(None))  # jamais coté sur Yahoo : absent des listes
        if region == "us":
            stmt = stmt.where(Security.market.in_(US_MARKETS))
        elif region == "europe":
            stmt = stmt.where(Security.market.not_in(US_MARKETS))
        # Les enveloppes sont lues à chaque requête : une correction manuelle sort le titre du top immédiatement.
        clause = envelope_clause(envelopes)
        if clause is not None:
            stmt = stmt.where(clause)
    if only_top:
        stmt = stmt.where(SecurityScore.eligible_for_top.is_(True), Security.kind == "stock").order_by(
            SecurityScore.total.desc(), SecurityScore.avg_turnover_eur.desc())
    else:
        stmt = stmt.order_by(Security.name, Security.id)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).all())


# --- Explorer et ETF : filtres, tri et pagination en SQL (bloc F) ---

ACCENTS, PLAIN = "àâäáãåçéèêëíìîïñóòôöõúùûüýÿœæ", "aaaaaaceeeeiiiinooooouuuuyyoa"
SORT_COLUMNS = {
    "price": SecurityQuote.price, "change_pct": SecurityQuote.change_pct, "perf_1w": SecurityScore.perf_1w,
    "perf_1m": SecurityScore.perf_1m, "perf_1y": SecurityScore.perf_1y, "score": SecurityScore.total,
    "pe": SecurityFundamentals.pe, "dividend_yield": SecurityFundamentals.dividend_yield,
}


@dataclass(frozen=True)
class ScreenerQuery:
    kind: str | None = None
    region: str | None = None
    q: str = ""
    sector: str | None = None
    country: str | None = None
    market: str | None = None
    envelope: str | None = None
    min_score: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    liquid: bool = False
    fav: bool = False
    sort: str = "name"
    order: str = "asc"


def _plain(column):
    """Minuscules sans accents, pour une recherche « moet » qui trouve « Moët »."""
    return func.translate(func.lower(column), ACCENTS, PLAIN)


def _listed(stmt, kind: str | None, region: str | None):
    stmt = stmt.where(Security.active.is_(True), SecurityQuote.security_id.is_not(None))  # jamais coté : absent
    stmt = stmt.where(Security.kind == kind) if kind else stmt.where(Security.kind != "index")
    if region == "us":
        stmt = stmt.where(Security.market.in_(US_MARKETS))
    elif region == "europe":
        stmt = stmt.where(Security.market.not_in(US_MARKETS))
    return stmt


def screener_page(session: Session, user_id: uuid.UUID | None, query: ScreenerQuery, *, limit: int,
                  offset: int) -> tuple[list[Row], int]:
    """Une page de l'Explorer et le nombre total de titres qui correspondent (tri stable : l'identifiant départage)."""
    is_favorite = (literal(False) if user_id is None else select(Favorite.security_id).where(
        Favorite.user_id == user_id, Favorite.security_id == Security.id).exists()).label("is_favorite")
    stmt = _listed(
        select(Security, SecurityQuote, SecurityScore, SecurityFundamentals, is_favorite)
        .outerjoin(SecurityQuote, SecurityQuote.security_id == Security.id)
        .outerjoin(SecurityScore, SecurityScore.security_id == Security.id)
        .outerjoin(SecurityFundamentals, SecurityFundamentals.security_id == Security.id),
        query.kind, query.region)
    if query.q.strip():
        pattern = f"%{escape_like(query.q.strip().lower())}%"
        stmt = stmt.where(or_(_plain(Security.name).like(_plain(literal(pattern)), escape="\\"),
                              func.lower(Security.symbol).like(pattern, escape="\\"),
                              func.lower(Security.isin).like(pattern, escape="\\")))
    for column, value in ((Security.sector, query.sector), (Security.country, query.country), (Security.market, query.market)):
        if value:
            stmt = stmt.where(column == value)
    clause = envelope_clause([query.envelope]) if query.envelope else None
    if clause is not None:
        stmt = stmt.where(clause)
    if query.min_score is not None:
        stmt = stmt.where(SecurityScore.total >= query.min_score)
    if query.min_price is not None:
        stmt = stmt.where(SecurityQuote.price >= query.min_price)
    if query.max_price is not None:
        stmt = stmt.where(SecurityQuote.price <= query.max_price)
    if query.liquid:
        stmt = stmt.where(SecurityScore.liquid.is_(True))
    if query.fav and user_id is not None:  # un visiteur n'a pas de favoris : filtre ignoré
        stmt = stmt.where(select(Favorite.security_id).where(
            Favorite.user_id == user_id, Favorite.security_id == Security.id).exists())
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    desc = query.order == "desc"
    if query.sort in SORT_COLUMNS:
        column = SORT_COLUMNS[query.sort]
        order = [(column.desc() if desc else column.asc()).nulls_last(), Security.id]
    else:  # nom, ordre naturel : chiffres d'abord (« 2CRSI » avant « 10X »), sans tenir compte des majuscules
        digits = func.nullif(func.substring(Security.name, "^[0-9]+"), "").cast(Numeric)
        direction = (lambda c: c.desc()) if desc else (lambda c: c.asc())
        order = [direction(digits).nulls_last(), direction(func.lower(Security.name)), Security.id]
    rows = session.execute(stmt.order_by(*order).limit(limit).offset(offset)).all()
    return list(rows), total


def screener_facets(session: Session, kind: str | None, region: str | None) -> dict[str, list[str]]:
    """Valeurs proposées par les filtres Secteur, Pays et Place (titres cotés de la région)."""
    def distinct(column) -> list[str]:
        stmt = _listed(select(column).distinct().outerjoin(SecurityQuote, SecurityQuote.security_id == Security.id),
                       kind, region).where(column.is_not(None))
        return sorted(session.scalars(stmt), key=lambda v: v.lower())
    return {"sectors": distinct(Security.sector), "countries": distinct(Security.country), "markets": distinct(Security.market)}
