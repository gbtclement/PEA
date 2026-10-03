"""Nasdaq Nordic (Stockholm, Helsinki, Copenhague, Islande) : écran des actions de l'API publique de nasdaq.com."""
import json

from app.providers.base import ListedSecurity
from app.providers.listing_source import SourceListing

SCREENER_URL = "https://api.nasdaq.com/api/nordic/screener/shares?category={category}&tableonly=false&market={market}"
MARKETS = {"STO": (".ST", "Nasdaq Stockholm"), "HEL": (".HE", "Nasdaq Helsinki"),
           "CPH": (".CO", "Nasdaq Copenhagen"), "ICE": (".IC", "Nasdaq Iceland")}
CATEGORIES = ("MAIN_MARKET", "FIRST_NORTH")
MIN_MAIN_MARKET = 10  # le plus petit, Reykjavik, compte une trentaine d'actions


def parse_nordic(text: str, market_code: str) -> list[ListedSecurity]:
    suffix, market = MARKETS[market_code]
    rows = ((json.loads(text).get("data") or {}).get("instrumentListing") or {}).get("rows")
    if rows is None:
        raise ValueError("Format de réponse Nasdaq Nordic inattendu")
    listed = []
    for row in rows:
        symbol = (row.get("symbol") or "").strip()
        if not symbol:
            continue
        listed.append(ListedSecurity(isin=(row.get("isin") or "").strip() or None, symbol=symbol,
                                     name=(row.get("fullName") or symbol).strip(), market=market,
                                     yahoo_ticker=f"{symbol.replace(' ', '-')}{suffix}", kind="stock",
                                     currency=(row.get("currency") or "").strip() or None))
    return listed


class NordicListingProvider(SourceListing):
    source = "nordic"
    min_rows = 300

    def fetch_live(self) -> list[ListedSecurity]:
        listed = []
        for market in MARKETS:
            for category in CATEGORIES:
                items = parse_nordic(self._get(SCREENER_URL.format(category=category, market=market)), market)
                # Le marché principal de chaque place doit répondre : sinon ses titres seraient désactivés.
                if category == "MAIN_MARKET" and len(items) < MIN_MAIN_MARKET:
                    raise ValueError(f"Liste Nasdaq Nordic incomplète ({market} : {len(items)} actions)")
                listed += items
        return listed
