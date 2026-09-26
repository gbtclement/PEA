from pydantic import BaseModel
from sqlalchemy import Row

from app.schemas.screener import ScreenerRow


class TopItem(ScreenerRow):
    technical: float | None
    fundamental: float | None
    reasons: list[str]

    @classmethod
    def build(cls, row: Row) -> "TopItem":
        score = row[2]
        components = sorted(score.components or [], key=lambda c: c.get("points", 0), reverse=True)
        return cls(**cls.fields_from(row), technical=score.technical, fundamental=score.fundamental,
                   reasons=[c["message"] for c in components[:3]])


class Movers(BaseModel):
    gainers: list[ScreenerRow]
    losers: list[ScreenerRow]


class HeatmapItem(BaseModel):
    id: int
    symbol: str
    name: str
    sector: str
    market_cap_eur: float
    change_pct: float
