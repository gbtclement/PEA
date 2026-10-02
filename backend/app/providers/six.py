"""SIX Swiss Exchange : émetteurs d'actions cotées et ETF (fichiers CSV publics)."""
import csv

from app.providers.base import ListedSecurity
from app.providers.listing_source import SourceListing

SHARES_URL = "https://www.six-group.com/sheldon/equity_issuers/v1/equity_issuers.csv"
ETFS_URL = ("https://www.six-group.com/fqs/ref.csv?select=ShortName,ValorSymbol,ISIN,TradingBaseCurrency,SecTypeDesc"
            "&where=PortalSegment=FU&orderby=ShortName&page=1&pagesize=99999")
MARKET = "SIX Swiss Exchange"


def _rows(text: str, first_column: str) -> list[dict[str, str]]:
    lines = text.lstrip("﻿").splitlines()
    if not lines or not lines[0].startswith(first_column):
        raise ValueError("Format de fichier SIX inattendu")
    return list(csv.DictReader(lines, delimiter=";"))


def _listed(symbol: str, name: str, isin: str, currency: str, kind: str) -> ListedSecurity:
    return ListedSecurity(isin=isin.strip() or None, symbol=symbol.strip(), name=name.strip(), market=MARKET,
                          yahoo_ticker=f"{symbol.strip()}.SW", kind=kind, currency=currency.strip() or None)


def parse_six_shares(text: str) -> list[ListedSecurity]:
    return [_listed(r["Symbol"], r["Company"], r["ISIN"], r.get("Traded Currency") or "", "stock")
            for r in _rows(text, "Company;") if r.get("Symbol")]


def parse_six_etfs(text: str) -> list[ListedSecurity]:
    return [_listed(r["ValorSymbol"], r["ShortName"], r["ISIN"], r.get("TradingBaseCurrency") or "", "etf")
            for r in _rows(text, "ShortName;") if r.get("ValorSymbol") and r.get("SecTypeDesc") == "Exchange Traded Fund"]


class SixListingProvider(SourceListing):
    source = "six"
    min_rows = 500

    def fetch_live(self) -> list[ListedSecurity]:
        return parse_six_shares(self._get(SHARES_URL)) + parse_six_etfs(self._get(ETFS_URL))
