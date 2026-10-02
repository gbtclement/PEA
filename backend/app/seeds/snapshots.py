"""Rafraîchit les instantanés des listes de titres (repli quand une source est en panne).

Usage : python -m app.seeds.snapshots [euronext_etf us xetra six nordic]
"""
import sys

from app.providers.euronext import EuronextEtfListingProvider
from app.providers.listing_source import SNAPSHOT_DIR, write_snapshot
from app.providers.nordic import NordicListingProvider
from app.providers.six import SixListingProvider
from app.providers.us import UsListingProvider
from app.providers.xetra import XetraListingProvider

PROVIDERS = {p.source: p for p in (EuronextEtfListingProvider, UsListingProvider, XetraListingProvider,
                                   SixListingProvider, NordicListingProvider)}


def main(names: list[str]) -> int:
    failed = 0
    for name in names or list(PROVIDERS):
        provider = PROVIDERS[name]()
        try:
            listed = provider.fetch_live()  # jamais l'instantané : on le remplace
            if len(listed) < provider.min_rows:
                raise ValueError(f"{len(listed)} titres seulement")
        except Exception as exc:
            print(f"ÉCHEC {name} : {exc}")
            failed += 1
            continue
        write_snapshot(SNAPSHOT_DIR / f"{name}.csv", listed)
        print(f"{name} : {len(listed)} titres")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
