from sqlalchemy.orm import Session

from app.repositories.market_data import average_turnover, refreshable_securities


def tier_tickers(session: Session, tier: int, tier2_size: int) -> list[str]:
    """T1 : indices (favoris, portefeuille et top 10 s'y ajouteront aux lots 2 et 3).
    T2 : les `tier2_size` titres les plus échangés. T3 : tous les autres."""
    candidates = refreshable_securities(session)
    if tier == 1:
        return sorted(s.yahoo_ticker for s in candidates if s.kind == "index")
    turnover = average_turnover(session)
    others = sorted(
        (s for s in candidates if s.kind != "index"),
        key=lambda s: (-turnover.get(s.id, 0.0), s.yahoo_ticker),
    )
    selected = others[:tier2_size] if tier == 2 else others[tier2_size:]
    return [s.yahoo_ticker for s in selected]
