"""Vérifie que chaque ticker des listes de départ existe sur Yahoo Finance.

Usage : python -m app.seeds.verify
"""

import sys

from app.providers.yahoo import YahooProvider
from app.seeds.loader import load_all_seeds


def main() -> int:
    seeds = load_all_seeds()
    quotes = YahooProvider().get_quotes([s.yahoo_ticker for s in seeds])
    missing = [s.yahoo_ticker for s in seeds if s.yahoo_ticker not in quotes]
    print(f"{len(seeds) - len(missing)}/{len(seeds)} titres trouvés sur Yahoo")
    for ticker in missing:
        print(f"INTROUVABLE : {ticker}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
