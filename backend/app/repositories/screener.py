from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from app.models import Favorite, Security, SecurityFundamentals, SecurityQuote, SecurityScore


def screener_rows(
    session: Session, user_id: int, *, kind: str | None = None, only_top: bool = False, limit: int | None = None,
    security_id: int | None = None,
) -> list[Row]:
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
        stmt = stmt.where(Security.id == security_id)
    elif kind:
        stmt = stmt.where(Security.kind == kind)
    else:
        stmt = stmt.where(Security.kind != "index")
    if only_top:
        # L'éligibilité est revérifiée ici : une correction manuelle doit sortir le titre du top immédiatement.
        stmt = stmt.where(
            SecurityScore.eligible_for_top.is_(True), Security.eligibility == "eligible", Security.kind == "stock",
        ).order_by(
            SecurityScore.total.desc(), SecurityScore.avg_turnover_eur.desc())
    else:
        stmt = stmt.order_by(Security.name, Security.id)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).all())
