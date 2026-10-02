from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.market_data import average_turnover, refreshable_securities
from app.repositories.orders import held_security_ids
from app.repositories.scores import alert_security_ids, favorite_security_ids, top_security_ids
from app.services.market_calendar import calendar_for_market

TOP_IN_T1 = 10
TOP_SCOPES: tuple[tuple[str, ...], ...] = ((), ("pea",), ("pea_pme",))  # top 10 de chaque façon de filtrer


def tier_tickers(session: Session, tier: int, tier2_size: int, now: datetime | None = None) -> list[str]:
    """T1 : indices, favoris, titres détenus, titres avec une alerte de prix et top 10 (tout, PEA, PEA-PME). T2 : les `tier2_size` titres les plus échangés. T3 : les autres.

    Avec `now`, seuls les titres dont la place est ouverte (les indices suivent l'Europe).
    """
    candidates = refreshable_securities(session)
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
    turnover = average_turnover(session)
    others = sorted(
        (s for s in candidates if s.id not in tier1_ids),
        key=lambda s: (-turnover.get(s.id, 0.0), s.yahoo_ticker),
    )
    selected = others[:tier2_size] if tier == 2 else others[tier2_size:]
    return [s.yahoo_ticker for s in selected]
