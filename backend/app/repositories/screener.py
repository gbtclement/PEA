import uuid
from collections.abc import Sequence

from sqlalchemy import Row, literal, select
from sqlalchemy.orm import Session

from app.models import Favorite, Security, SecurityFundamentals, SecurityQuote, SecurityScore
from app.repositories.envelopes import envelope_clause


def screener_rows(
    session: Session, user_id: uuid.UUID | None, *, kind: str | None = None, only_top: bool = False, limit: int | None = None,
    security_id: int | None = None, envelopes: Sequence[str] = (),
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
