"""Xetra : fichier « All tradable instruments » de Deutsche Börse (lien à empreinte, lu sur la page des instruments)."""
import csv
import re

from app.providers.base import ListedSecurity
from app.providers.listing_source import SourceListing

INSTRUMENTS_PAGE = "https://www.xetra.com/xetra-en/instruments/instruments"
_CSV_LINK = re.compile(r'href="([^"]*t7-xetr-allTradableInstruments\.csv)"')
_KINDS = {"CS": "stock", "ETF": "etf"}
_PREAMBLE_LINES = 2


def find_csv_url(html: str) -> str:
    match = _CSV_LINK.search(html)
    if match is None:
        raise ValueError("Lien du fichier Xetra introuvable")
    url = match.group(1)
    return url if url.startswith("http") else f"https://www.xetra.com{url}"


def parse_xetra_csv(text: str) -> list[ListedSecurity]:
    lines = text.lstrip("﻿").splitlines()
    if len(lines) <= _PREAMBLE_LINES or "Mnemonic" not in lines[_PREAMBLE_LINES]:
        raise ValueError("Format de fichier Xetra inattendu")
    listed = []
    for row in csv.DictReader(lines[_PREAMBLE_LINES:], delimiter=";"):
        kind = _KINDS.get(row.get("Instrument Type") or "")
        mnemonic = (row.get("Mnemonic") or "").strip()
        if kind is None or row.get("Product Status") != "Active" or not mnemonic:
            continue
        listed.append(ListedSecurity(isin=(row.get("ISIN") or "").strip() or None, symbol=mnemonic,
                                     name=(row.get("Instrument") or "").strip(), market="Xetra",
                                     yahoo_ticker=f"{mnemonic}.DE", kind=kind,
                                     currency=(row.get("Currency") or "").strip() or None))
    return listed


class XetraListingProvider(SourceListing):
    source = "xetra"
    min_rows = 1000

    def fetch_live(self) -> list[ListedSecurity]:
        return parse_xetra_csv(self._get(find_csv_url(self._get(INSTRUMENTS_PAGE))))
