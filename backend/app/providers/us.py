"""Actions et ETF américains : fichier public `nasdaqtraded.txt` de Nasdaq Trader (NYSE, NYSE American, NYSE Arca, Nasdaq)."""
import csv
import re

from app.providers.base import ListedSecurity
from app.providers.listing_source import SourceListing

NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
EXCHANGES = {"N": "NYSE", "A": "NYSE American", "P": "NYSE Arca", "Q": "Nasdaq"}
_EXPECTED_HEADER = "Nasdaq Traded|Symbol|Security Name|Listing Exchange"
# Bons de souscription, droits, unités (SPAC) et actions préférentielles : hors périmètre.
_EXCLUDED_NAME = re.compile(r"\b(warrants?|rights?|units?|preferred)\b", re.IGNORECASE)
_EXCLUDED_SYMBOL = re.compile(r"[$^=+]")


def parse_nasdaq_traded(text: str) -> list[ListedSecurity]:
    lines = text.lstrip("﻿").splitlines()
    if not lines or not lines[0].startswith(_EXPECTED_HEADER):
        raise ValueError("Format de fichier Nasdaq Trader inattendu")
    listed = []
    for row in csv.DictReader(lines, delimiter="|"):
        market = EXCHANGES.get(row.get("Listing Exchange") or "")
        symbol = (row.get("Symbol") or "").strip()
        name = (row.get("Security Name") or "").strip()
        if (row.get("Nasdaq Traded") != "Y" or row.get("Test Issue") != "N" or row.get("NextShares") == "Y"
                or market is None or not symbol or _EXCLUDED_SYMBOL.search(symbol) or _EXCLUDED_NAME.search(name)):
            continue
        kind = "etf" if row.get("ETF") == "Y" else "stock"
        listed.append(ListedSecurity(isin=None, symbol=symbol, name=name, market=market,
                                     yahoo_ticker=symbol.replace(".", "-"), kind=kind, currency="USD"))
    return listed


class UsListingProvider(SourceListing):
    source = "us"
    min_rows = 5000

    def fetch_live(self) -> list[ListedSecurity]:
        return parse_nasdaq_traded(self._get(NASDAQ_TRADED_URL))
