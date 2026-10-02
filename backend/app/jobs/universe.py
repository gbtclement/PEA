from app.jobs.context import JobContext
from app.repositories.securities import SecurityUpsert, deactivate_missing, upsert_securities
from app.seeds.loader import load_all_seeds
from app.services.envelopes.rules import country_from_isin


def refresh_universe(ctx: JobContext) -> int:
    listed = ctx.listing.fetch_listed()
    if not listed:
        raise RuntimeError("Liste Euronext vide : univers conservé tel quel")
    items = [
        SecurityUpsert(
            yahoo_ticker=s.yahoo_ticker, symbol=s.symbol, name=s.name, kind="stock",
            market=s.market, isin=s.isin, country=country_from_isin(s.isin),
        )
        for s in listed
    ]
    items += [
        SecurityUpsert(
            yahoo_ticker=s.yahoo_ticker, symbol=s.symbol, name=s.name, kind=s.kind, market=s.market,
            isin=None, country=s.country,
        )
        for s in load_all_seeds()
    ]
    with ctx.session_factory() as session:
        count = upsert_securities(session, items)
        deactivate_missing(session, {item.yahoo_ticker for item in items})
        session.commit()
    return count
