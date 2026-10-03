"""Petits défauts du bloc D (univers étendu) relevés à la revue finale, corrigés le 2026-10-03."""
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

import app.jobs.scheduler as scheduler_module
from app.jobs.market import refresh_quotes
from app.jobs.tiers import tier_tickers
from app.jobs.universe import merge_listings, refresh_universe
from app.models import DailyPrice, Security, SecurityQuote
from app.providers.base import ListedSecurity, Quote
from app.providers.nordic import NordicListingProvider
from app.providers.six import SixListingProvider
from app.repositories.securities import SecurityUpsert, upsert_securities
from app.services.market_calendar import PARIS
from tests.factories import make_security
from tests.fakes import FakeListing, FakeMarket

LVMH = ListedSecurity("FR0000121014", "MC", "LVMH", "Euronext Paris", "MC.PA")
WORLD_PARIS = ListedSecurity("IE00B4L5Y983", "IWDA", "iShares Core MSCI World", "Euronext Amsterdam", "IWDA.AS", "etf", "EUR")
WORLD_XETRA = ListedSecurity("IE00B4L5Y983", "EUNL", "iShares Core MSCI World", "Xetra", "EUNL.DE", "etf", "EUR")
SHOPIFY_XETRA = ListedSecurity("CA82509L1076", "307", "SHOPIFY INC.", "Xetra", "307.DE", "stock", "EUR")
STRABAG_XETRA = ListedSecurity("AT000000STR1", "XD4", "STRABAG SE", "Xetra", "XD4.DE", "stock", "EUR")
APPLE_US = ListedSecurity(None, "AAPL", "Apple Inc.", "Nasdaq", "AAPL", "stock", "USD")


def by_ticker(db, ticker):
    return db.scalars(select(Security).where(Security.yahoo_ticker == ticker)).one_or_none()


# M-2 : une sous-liste vide ne doit pas passer pour une liste complète
def test_six_with_an_empty_share_list_falls_back_to_its_snapshot(tmp_path):
    from app.providers.listing_source import write_snapshot

    snapshot = tmp_path / "six.csv"
    write_snapshot(snapshot, [ListedSecurity("CH0038863350", "NESN", "Nestlé", "SIX Swiss Exchange", "NESN.SW", "stock", "CHF")])
    etfs = "ShortName;ValorSymbol;ISIN;TradingBaseCurrency;SecTypeDesc\n" + "".join(
        f"ETF {i};E{i};IE00000000{i:02d};USD;Exchange Traded Fund\n" for i in range(600))
    shares = "Company;ISIN;Symbol;Valor Number;Country;Traded Currency;Trading platform\n"  # en-tête seul

    provider = SixListingProvider(http_get=lambda url: shares if "equity_issuers" in url else etfs, sleep=lambda s: None,
                                  snapshot_path=snapshot)
    assert [s.yahoo_ticker for s in provider.fetch_listed()] == ["NESN.SW"]


def test_nordic_with_an_empty_main_market_falls_back_to_its_snapshot(tmp_path):
    from app.providers.listing_source import write_snapshot

    snapshot = tmp_path / "nordic.csv"
    write_snapshot(snapshot, [ListedSecurity("SE0011337708", "AAK", "AAK", "Nasdaq Stockholm", "AAK.ST", "stock", "SEK")])
    full = '{"data":{"instrumentListing":{"rows":[' + ",".join(
        f'{{"fullName":"S{i}","currency":"SEK","symbol":"S{i}","isin":"SE{i:010d}"}}' for i in range(200)) + "]}}}"
    empty = '{"data":{"instrumentListing":{"rows":[]}}}'

    def get(url):
        return empty if "market=STO" in url and "MAIN_MARKET" in url else full

    provider = NordicListingProvider(http_get=get, sleep=lambda s: None, snapshot_path=snapshot)
    assert [s.yahoo_ticker for s in provider.fetch_listed()] == ["AAK.ST"]


# M-3 : une source en panne garde ses titres, même si une autre place cote le même ISIN
def test_failed_source_keeps_its_isins(db, make_ctx):
    refresh_universe(make_ctx(listings=[FakeListing([LVMH]), FakeListing([WORLD_PARIS], source="euronext_etf")]))
    with pytest.raises(RuntimeError):
        refresh_universe(make_ctx(listings=[FakeListing([LVMH]), FakeListing([], source="euronext_etf"),
                                            FakeListing([WORLD_XETRA], source="xetra")]))
    kept = by_ticker(db, "IWDA.AS")
    assert kept is not None and (kept.source, kept.active) == ("euronext_etf", True)
    assert by_ticker(db, "EUNL.DE") is None


# M-4 : ticker d'une ligne, ISIN d'une autre : pas d'erreur d'unicité
def test_upsert_moves_an_isin_held_by_another_row(db):
    a = make_security(db, "A.PA", isin="FR0000000001")
    b = make_security(db, "B.PA", isin="FR0000000002")
    upsert_securities(db, [SecurityUpsert("A.PA", "A", "A", "stock", "Euronext Paris", "FR0000000002", "FR")])
    db.flush()
    db.expire_all()
    assert db.get(Security, a.id).isin == "FR0000000002" and db.get(Security, b.id).isin is None


# M-5 : action non européenne cotée à Francfort et à New York : une seule fois
def test_merge_drops_non_european_secondary_listings_when_the_us_list_answered():
    merged = {s.yahoo_ticker for _, s in merge_listings({"xetra": [SHOPIFY_XETRA, STRABAG_XETRA], "us": [APPLE_US]})}
    assert merged == {"AAPL", "XD4.DE"}
    assert "307.DE" in {s.yahoo_ticker for _, s in merge_listings({"xetra": [SHOPIFY_XETRA]})}  # sans liste US : gardée


# M-6 : cours américain d'avant la première barre du jour : heure de clôture de New York
def test_us_quote_of_a_past_session_uses_the_new_york_close(db, make_ctx):
    ny = make_security(db, "AAPL", market="Nasdaq", country="US")
    past = Quote(250.0, 248.0, 0.8, 1000, datetime(2026, 10, 1, 17, 35, tzinfo=PARIS))  # forme renvoyée par Yahoo
    now = datetime(2026, 10, 2, 13, 31, tzinfo=UTC)  # 15 h 31 à Paris : New York vient d'ouvrir
    refresh_quotes(make_ctx(market=FakeMarket(quotes={"AAPL": past}), now=now), 2)
    db.expire_all()
    assert db.get(SecurityQuote, ny.id).as_of == datetime(2026, 10, 1, 22, 0, tzinfo=PARIS)


# M-7 : le palier 2 compare des montants en euros
def test_tier2_ranks_turnover_in_euros(db):
    sek = make_security(db, "BIG.ST", market="Nasdaq Stockholm", country="SE")
    eur = make_security(db, "MID.PA")
    for i in range(20):
        day = date(2026, 10, 1) - timedelta(days=i)
        db.add(DailyPrice(security_id=sek.id, date=day, open=1, high=1, low=1, close=100.0, volume=1000))  # 100 000 SEK
        db.add(DailyPrice(security_id=eur.id, date=day, open=1, high=1, low=1, close=50.0, volume=1000))  # 50 000 EUR
    db.flush()
    afternoon = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)
    assert tier_tickers(db, 2, 1, afternoon) == ["MID.PA"]  # 100 000 SEK ≈ 8 700 € < 50 000 €


# M-8 : un passage de 22 h 30 manqué est rattrapé au démarrage
def test_bootstrap_catches_up_a_missed_us_evening(db, make_ctx, monkeypatch):
    names = []
    monkeypatch.setattr(scheduler_module, "run_job", lambda ctx, name, fn: names.append(name) or 0)
    monkeypatch.setattr(scheduler_module, "_refresh_tier", lambda ctx, tier: None)
    monkeypatch.setattr(scheduler_module, "history_backfill_job", lambda ctx: None)
    sec = make_security(db, "MC.PA")
    db.add(DailyPrice(security_id=sec.id, date=date(2026, 10, 1), open=1, high=1, low=1, close=1.0, volume=1))
    db.flush()
    from app.repositories.data_status import record_success

    europe_done = datetime(2026, 10, 2, 16, 20, tzinfo=UTC)  # passage européen du vendredi fait, pas celui de 22 h 30
    for job in ("universe", "daily_history", "fundamentals", "forecasts"):
        record_success(db, job, 1, europe_done)
    db.flush()
    scheduler_module.bootstrap_job(make_ctx(now=datetime(2026, 10, 3, 8, 0, tzinfo=UTC)))
    assert "daily_history_us" in names
