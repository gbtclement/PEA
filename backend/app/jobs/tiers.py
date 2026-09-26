from sqlalchemy.orm import Session

from app.repositories.market_data import average_turnover, refreshable_securities
from app.repositories.orders import held_security_ids
from app.repositories.scores import favorite_security_ids, top_security_ids

TOP_IN_T1 = 10


def tier_tickers(session: Session, tier: int, tier2_size: int) -> list[str]:
    """T1 : indices, favoris, titres détenus et top 10. T2 : les `tier2_size` titres les plus échangés. T3 : les autres."""
    candidates = refreshable_securities(session)
    priority_ids = favorite_security_ids(session) | held_security_ids(session) | set(top_security_ids(session, TOP_IN_T1))
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
