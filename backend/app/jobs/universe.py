import logging

from app.jobs.context import JobContext
from app.providers.base import ListedSecurity
from app.repositories.securities import SecurityUpsert, deactivate_missing, upsert_securities
from app.seeds.loader import load_all_seeds
from app.services.envelopes.rules import country_from_isin

logger = logging.getLogger(__name__)

# Un même ISIN coté sur plusieurs places : la place d'origine d'abord, puis cet ordre (Euronext avant tout pour le PEA).
SOURCE_PRIORITY = ("euronext", "euronext_etf", "nordic", "six", "xetra", "us")
HOME_COUNTRIES: dict[str, frozenset[str]] = {
    "euronext": frozenset({"FR", "NL", "BE", "IT", "PT", "IE", "NO"}),
    "euronext_etf": frozenset(),
    "nordic": frozenset({"SE", "FI", "DK", "IS"}),
    "six": frozenset({"CH", "LI"}),
    "xetra": frozenset({"DE"}),
    "us": frozenset({"US"}),
}


def merge_listings(batches: dict[str, list[ListedSecurity]]) -> list[tuple[str, ListedSecurity]]:
    """Une cotation par ISIN et par ticker. Une action cotée hors de chez elle n'est gardée que si sa place n'est pas suivie."""
    # ISIN que les places d'origine listent vraiment : une action absente de sa liste d'origine (Redcare, néerlandaise,
    # cotée seulement à Francfort) est gardée ailleurs. La liste américaine n'a pas d'ISIN : un ISIN US suffit.
    listed_at_home = {item.isin for source, items in batches.items() for item in items
                      if item.isin and country_from_isin(item.isin) in HOME_COUNTRIES.get(source, frozenset())}
    candidates = []
    for rank, source in enumerate(SOURCE_PRIORITY):
        home = HOME_COUNTRIES[source]
        for item in batches.get(source, []):
            country = country_from_isin(item.isin)
            secondary = source != "euronext" and item.kind == "stock" and country not in home
            if secondary and ((country == "US" and "us" in batches) or item.isin in listed_at_home):
                continue  # cotation secondaire (Apple, SAP à Zurich) : la place d'origine la suit déjà
            candidates.append((country not in home, rank, source, item))
    candidates.sort(key=lambda c: (c[0], c[1]))
    seen_isins: set[str] = set()
    seen_tickers: set[str] = set()
    merged = []
    for _, _, source, item in candidates:
        if (item.isin and item.isin in seen_isins) or item.yahoo_ticker in seen_tickers:
            continue
        if item.isin:
            seen_isins.add(item.isin)
        seen_tickers.add(item.yahoo_ticker)
        merged.append((source, item))
    return merged


def _country(source: str, item: ListedSecurity) -> str | None:
    """Pays déduit de l'ISIN ; la liste américaine n'en donne pas : on retient alors la place de cotation."""
    return country_from_isin(item.isin) or ("US" if source == "us" else None)


def refresh_universe(ctx: JobContext) -> int:
    batches: dict[str, list[ListedSecurity]] = {}
    failed: list[str] = []
    for provider in ctx.listings:
        try:
            listed = provider.fetch_listed()
        except Exception:
            logger.warning("Liste %s indisponible (instantané compris)", provider.source, exc_info=True)
            listed = []
        if listed:
            batches[provider.source] = listed
        else:
            failed.append(provider.source)
    if not batches:
        raise RuntimeError("Aucune liste de titres disponible : univers conservé tel quel")
    items = [
        SecurityUpsert(yahoo_ticker=s.yahoo_ticker, symbol=s.symbol, name=s.name, kind=s.kind, market=s.market,
                       isin=s.isin, country=_country(source, s), currency=s.currency, source=source)
        for source, s in merge_listings(batches)
    ]
    listed_tickers = {item.yahoo_ticker for item in items}
    items += [
        SecurityUpsert(yahoo_ticker=s.yahoo_ticker, symbol=s.symbol, name=s.name, kind=s.kind, market=s.market,
                       isin=None, country=s.country, source="seed")
        for s in load_all_seeds() if s.yahoo_ticker not in listed_tickers  # une source prime sur la saisie manuelle
    ]
    with ctx.session_factory() as session:
        count = upsert_securities(session, items)
        deactivate_missing(session, {item.yahoo_ticker for item in items}, sources=set(batches) | {"seed"})
        session.commit()
    if failed:
        raise RuntimeError(f"Listes indisponibles ({', '.join(failed)}) : leurs titres sont conservés")
    return count
