import csv
import logging
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from app.providers.base import ListedSecurity
from app.providers.retry import with_retries

logger = logging.getLogger(__name__)

# Places retenues → suffixe Yahoo. L'ordre fixe la priorité quand un même ISIN est coté plusieurs fois.
MARKET_SUFFIXES: dict[str, str] = {
    "Euronext Paris": ".PA",
    "Euronext Amsterdam": ".AS",
    "Euronext Brussels": ".BR",
    "Euronext Milan": ".MI",
    "Euronext Lisbon": ".LS",
    "Euronext Dublin": ".IR",
    "Oslo Børs": ".OL",
    "Euronext Growth Paris": ".PA",
    "Euronext Growth Brussels": ".BR",
    "Euronext Growth Milan": ".MI",
    "Euronext Growth Lisbon": ".LS",
    "Euronext Growth Dublin": ".IR",
    "Euronext Growth Oslo": ".OL",
    "Euronext Expand Oslo": ".OL",
    "Euronext Access Paris": ".PA",
    "Euronext Access Brussels": ".BR",
    "Euronext Access Lisbon": ".LS",
    "Euronext Access Dublin": ".IR",
}
_PRIORITY = {market: rank for rank, market in enumerate(MARKET_SUFFIXES)}
_EXPECTED_HEADER = "Name;ISIN;Symbol;Market"
_HEADER_LINES = 4
SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "seeds" / "euronext_snapshot.csv"
FORM_DATA = {
    "args[fe_type]": "csv",
    "args[fe_decimal]": ".",
    "args[fe_date_format]": "d/m/Y",
    "args[fe_layout]": "ver",
}


def _primary_market(market: str) -> str:
    return market.split(",")[0].strip()


def yahoo_ticker_for(symbol: str, market: str) -> str | None:
    suffix = MARKET_SUFFIXES.get(_primary_market(market))
    return f"{symbol.strip()}{suffix}" if suffix else None


def parse_euronext_csv(text: str) -> list[ListedSecurity]:
    lines = text.lstrip("﻿").splitlines()
    if not lines or not lines[0].startswith(_EXPECTED_HEADER):
        raise ValueError("Format de fichier Euronext inattendu")
    best: dict[str, tuple[int, ListedSecurity]] = {}
    for row in csv.reader(lines[_HEADER_LINES:], delimiter=";"):
        if len(row) < 4:
            continue
        name, isin, symbol, market = (cell.strip() for cell in row[:4])
        ticker = yahoo_ticker_for(symbol, market)
        if not ticker or not isin:
            continue
        primary = _primary_market(market)
        rank = _PRIORITY[primary]
        current = best.get(isin)
        if current is None or rank < current[0]:
            best[isin] = (rank, ListedSecurity(isin=isin, symbol=symbol, name=name, market=primary, yahoo_ticker=ticker))
    return sorted((security for _, security in best.values()), key=lambda s: s.name)


class EuronextListingProvider:
    def __init__(
        self,
        url: str,
        snapshot_path: Path = SNAPSHOT_PATH,
        http_post: Callable[[str, dict[str, str]], str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._url = url
        self._snapshot_path = snapshot_path
        self._http_post = http_post or self._default_post
        self._sleep = sleep

    def fetch_listed(self) -> list[ListedSecurity]:
        try:
            text = with_retries(lambda: self._http_post(self._url, FORM_DATA), sleep=self._sleep)
            return parse_euronext_csv(text)
        except Exception:
            logger.warning("Liste Euronext indisponible, utilisation de l'instantané local", exc_info=True)
            return parse_euronext_csv(self._snapshot_path.read_text(encoding="utf-8"))

    @staticmethod
    def _default_post(url: str, data: dict[str, str]) -> str:
        response = httpx.post(url, data=data, headers={"User-Agent": "Mozilla/5.0 (PEA Radar)"}, timeout=60)
        response.raise_for_status()
        return response.text
