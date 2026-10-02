import csv
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

SEEDS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class SeedSecurity:
    yahoo_ticker: str
    symbol: str
    name: str
    market: str
    country: str | None
    kind: str  # stock | etf | index


def _read(filename: str) -> list[dict[str, str]]:
    with (SEEDS_DIR / filename).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_extra_stocks() -> list[SeedSecurity]:
    return [
        SeedSecurity(row["yahoo_ticker"], row["symbol"], row["name"], row["market"], row["country"], "stock")
        for row in _read("extra_stocks.csv")
    ]


def load_etfs() -> list[SeedSecurity]:
    return [
        SeedSecurity(row["yahoo_ticker"], row["symbol"], row["name"], "Euronext Paris", None, "etf")
        for row in _read("etfs.csv")
    ]


def load_indices() -> list[SeedSecurity]:
    return [
        SeedSecurity(row["yahoo_ticker"], row["yahoo_ticker"], row["name"], "Indice", None, "index")
        for row in _read("indices.csv")
    ]


@lru_cache
def confirmed_pea_etfs() -> frozenset[str]:
    """ETF dont l'éligibilité au PEA est confirmée à la main (seeds/etfs.csv)."""
    return frozenset(row["yahoo_ticker"] for row in _read("etfs.csv"))


def load_all_seeds() -> list[SeedSecurity]:
    return load_extra_stocks() + load_etfs() + load_indices()
