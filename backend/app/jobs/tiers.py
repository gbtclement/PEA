from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Security
from app.repositories.market_data import average_turnover
from app.repositories.orders import held_security_ids
from app.repositories.scores import alert_security_ids, favorite_security_ids, top_security_ids
from app.services.fx import currency_for_market, to_eur
from app.services.market_calendar import calendar_for_market

TOP_IN_T1 = 10
TURNOVER_WINDOW = timedelta(days=40)  # ≈ 28 séances : assez pour la moyenne sur 20
TOP_SCOPES: tuple[tuple[str, ...], ...] = ((), ("pea",), ("pea_pme",))  # top 10 de chaque façon de filtrer


def tier_tickers(session: Session, tier: int, tier2_size: int, now: datetime | None = None) -> list[str]:
    """T1 : indices, favoris, titres détenus, titres avec une alerte de prix et top 10 (tout, PEA, PEA-PME). T2 : les `tier2_size` titres les plus échangés. T3 : les autres.

    Avec `now`, seuls les titres dont la place est ouverte (les indices suivent l'Europe).
    """
    # Colonnes utiles seulement (pas d'objets complets) : T1 relit les quelque 18 000 titres chaque minute.
    candidates = session.execute(select(Security.id, Security.yahoo_ticker, Security.market, Security.kind,
                                        Security.currency).where(Security.active.is_(True))).all()
    if now is not None:
        candidates = [s for s in candidates if calendar_for_market(s.market).is_open(now)]
    priority_ids = (
        favorite_security_ids(session) | held_security_ids(session) | alert_security_ids(session)
        | {sid for scope in TOP_SCOPES for sid in top_security_ids(session, TOP_IN_T1, scope)}
    )
    tier1 = [s for s in candidates if s.kind == "index" or s.id in priority_ids]
    if tier == 1:
        return sorted(s.yahoo_ticker for s in tier1)
    tier1_ids = {s.id for s in tier1}
    since = (now or datetime.now(UTC)).date() - TURNOVER_WINDOW
    turnover = average_turnover(session, since)
    others = sorted(
        (s for s in candidates if s.id not in tier1_ids),
        # Montants en euros : 100 000 couronnes ne doivent pas passer devant 50 000 €.
        key=lambda s: (-(to_eur(turnover.get(s.id, 0.0), s.currency or currency_for_market(s.market)) or 0.0),
                       s.yahoo_ticker),
    )
    selected = others[:tier2_size] if tier == 2 else others[tier2_size:]
    return [s.yahoo_ticker for s in selected]
