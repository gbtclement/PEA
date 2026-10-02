"""Socle commun des listes de titres : téléchargement, contrôle de taille, repli sur un instantané versionné."""
import csv
import logging
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from app.core.brand import APP_NAME
from app.providers.base import ListedSecurity
from app.providers.retry import with_retries

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "seeds" / "listings"
SNAPSHOT_FIELDS = ("isin", "symbol", "name", "market", "yahoo_ticker", "kind", "currency")
USER_AGENT = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36 ({APP_NAME})"


def write_snapshot(path: Path, items: list[ListedSecurity]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_FIELDS)
        writer.writeheader()
        for item in sorted(items, key=lambda s: s.yahoo_ticker):
            writer.writerow({field: getattr(item, field) or "" for field in SNAPSHOT_FIELDS})


def read_snapshot(path: Path) -> list[ListedSecurity]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            ListedSecurity(isin=row["isin"] or None, symbol=row["symbol"], name=row["name"], market=row["market"],
                           yahoo_ticker=row["yahoo_ticker"], kind=row["kind"], currency=row["currency"] or None)
            for row in csv.DictReader(handle)
        ]


class SourceListing:
    source = ""
    min_rows = 1  # en dessous, le fichier est jugé tronqué : il désactiverait la plupart des titres

    def __init__(self, http_get: Callable[[str], str] | None = None, sleep: Callable[[float], None] = time.sleep,
                 snapshot_path: Path | None = None) -> None:
        self._http_get = http_get or self._default_get
        self._sleep = sleep
        self._snapshot_path = snapshot_path or SNAPSHOT_DIR / f"{self.source}.csv"

    def fetch_live(self) -> list[ListedSecurity]:
        raise NotImplementedError

    def fetch_listed(self) -> list[ListedSecurity]:
        try:
            listed = with_retries(self.fetch_live, sleep=self._sleep)
            if len(listed) < self.min_rows:
                raise ValueError(f"Liste {self.source} incomplète ({len(listed)} titres)")
            return listed
        except Exception:
            logger.warning("Liste %s indisponible, utilisation de l'instantané local", self.source, exc_info=True)
            listed = read_snapshot(self._snapshot_path)
            if not listed:
                raise ValueError(f"Instantané {self.source} vide")
            return listed

    def _get(self, url: str) -> str:
        return self._http_get(url)

    @staticmethod
    def _default_get(url: str) -> str:
        response = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}, timeout=60, follow_redirects=True)
        response.raise_for_status()
        return response.text
