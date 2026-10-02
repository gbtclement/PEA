import pytest
from sqlalchemy import select

from app.jobs.universe import merge_listings, refresh_universe
from app.models import Security
from app.providers.base import ListedSecurity
from app.repositories.envelopes import set_envelope_override
from tests.fakes import FakeListing

LVMH = ListedSecurity("FR0000121014", "MC", "LVMH", "Euronext Paris", "MC.PA")
ASML = ListedSecurity("NL0010273215", "ASML", "ASML", "Euronext Amsterdam", "ASML.AS")
THREE_M = ListedSecurity("US88579Y1010", "MMM", "3M", "Euronext Paris", "MMM.PA")


def by_ticker(db, ticker: str) -> Security:
    return db.scalars(select(Security).where(Security.yahoo_ticker == ticker)).one()


def test_universe_classifies_listed_and_seeds(db, make_ctx):
    refresh_universe(make_ctx(listing=FakeListing([LVMH, ASML, THREE_M])))
    assert by_ticker(db, "MC.PA").envelope_status("pea") == "eligible"
    assert by_ticker(db, "MC.PA").country == "FR"
    assert by_ticker(db, "ASML.AS").envelope_status("pea") == "eligible"
    assert by_ticker(db, "MMM.PA").envelope_status("pea") == "non_eligible"
    index = by_ticker(db, "^FCHI")
    assert (index.kind, index.envelope_status("pea"), index.envelope("pea").source) == ("index", "non_eligible", "seed")
    etfs = db.scalars(select(Security).where(Security.kind == "etf")).all()
    assert etfs and all(e.envelope_status("pea") == "eligible" and e.envelope("pea").source == "seed" for e in etfs)
    sap = by_ticker(db, "SAP.DE")
    assert (sap.country, sap.envelope_status("pea")) == ("DE", "eligible")


def test_override_survives_refresh(db, make_ctx):
    ctx = make_ctx(listing=FakeListing([LVMH]))
    refresh_universe(ctx)
    lvmh = by_ticker(db, "MC.PA")
    set_envelope_override(lvmh, "pea", "non_eligible", None)
    db.flush()
    refresh_universe(ctx)
    lvmh = by_ticker(db, "MC.PA")
    assert (lvmh.envelope_status("pea"), lvmh.envelope("pea").source) == ("non_eligible", "manual")


def test_missing_securities_are_deactivated(db, make_ctx):
    refresh_universe(make_ctx(listing=FakeListing([LVMH, ASML])))
    refresh_universe(make_ctx(listing=FakeListing([LVMH])))
    assert by_ticker(db, "ASML.AS").active is False
    assert by_ticker(db, "MC.PA").active is True
    assert by_ticker(db, "^FCHI").active is True


def test_ticker_change_updates_same_row(db, make_ctx):
    refresh_universe(make_ctx(listing=FakeListing([LVMH])))
    first_id = by_ticker(db, "MC.PA").id
    renamed = ListedSecurity("FR0000121014", "MCX", "LVMH", "Euronext Paris", "MCX.PA")
    refresh_universe(make_ctx(listing=FakeListing([renamed])))
    assert by_ticker(db, "MCX.PA").id == first_id


def test_empty_listing_does_not_deactivate_universe(db, make_ctx):
    refresh_universe(make_ctx(listing=FakeListing([LVMH, ASML])))
    with pytest.raises(RuntimeError):
        refresh_universe(make_ctx(listing=FakeListing([])))
    assert by_ticker(db, "ASML.AS").active is True


def test_known_industry_is_used_for_classification(db, make_ctx):
    gecina = ListedSecurity("FR0010040865", "GFC", "Gecina", "Euronext Paris", "GFC.PA")
    ctx = make_ctx(listing=FakeListing([gecina]))
    refresh_universe(ctx)
    by_ticker(db, "GFC.PA").industry = "REIT - Office"
    db.flush()
    refresh_universe(ctx)
    assert by_ticker(db, "GFC.PA").envelope_status("pea") == "a_verifier"


SAP_XETRA = ListedSecurity("DE0007164600", "SAP", "SAP SE", "Xetra", "SAP.DE", "stock", "EUR")
SAP_SIX = ListedSecurity("DE0007164600", "SAP", "SAP SE", "SIX Swiss Exchange", "SAP.SW", "stock", "CHF")
APPLE_XETRA = ListedSecurity("US0378331005", "APC", "Apple Inc.", "Xetra", "APC.DE", "stock", "EUR")
APPLE_US = ListedSecurity(None, "AAPL", "Apple Inc.", "Nasdaq", "AAPL", "stock", "USD")
STRABAG_XETRA = ListedSecurity("AT000000STR1", "XD4", "STRABAG SE", "Xetra", "XD4.DE", "stock", "EUR")
WORLD_PARIS = ListedSecurity("IE00B4L5Y983", "IWDA", "iShares Core MSCI World", "Euronext Amsterdam", "IWDA.AS", "etf", "EUR")
WORLD_XETRA = ListedSecurity("IE00B4L5Y983", "EUNL", "iShares Core MSCI World", "Xetra", "EUNL.DE", "etf", "EUR")
PEA_ETF = ListedSecurity("FR0011869312", "PAEJ", "AM ASIP EXJ PEA", "Euronext Paris", "PAEJ.PA", "etf", "EUR")


def test_merge_prefers_home_listing():
    merged = merge_listings({"six": [SAP_SIX], "xetra": [SAP_XETRA]})
    assert [(source, s.yahoo_ticker) for source, s in merged] == [("xetra", "SAP.DE")]


def test_merge_drops_secondary_listing_of_covered_country():
    merged = {s.yahoo_ticker for _, s in merge_listings({"xetra": [APPLE_XETRA, STRABAG_XETRA], "us": [APPLE_US]})}
    assert merged == {"AAPL", "XD4.DE"}  # Vienne n'est pas suivie : Strabag reste via Xetra


def test_merge_keeps_one_etf_per_isin_by_source_priority():
    merged = merge_listings({"xetra": [WORLD_XETRA], "euronext_etf": [WORLD_PARIS]})
    assert [s.yahoo_ticker for _, s in merged] == ["IWDA.AS"]


def test_universe_reads_every_source(db, make_ctx):
    refresh_universe(make_ctx(listings=[FakeListing([LVMH]), FakeListing([APPLE_US], source="us"),
                                        FakeListing([PEA_ETF, WORLD_PARIS], source="euronext_etf")]))
    apple = by_ticker(db, "AAPL")
    assert (apple.source, apple.currency, apple.envelope_status("pea")) == ("us", "USD", "non_eligible")
    assert by_ticker(db, "MC.PA").source == "euronext"
    assert (by_ticker(db, "PAEJ.PA").envelope_status("pea"), by_ticker(db, "PAEJ.PA").envelope("pea").source) == ("eligible", "auto")
    assert by_ticker(db, "IWDA.AS").envelope_status("pea") == "a_verifier"


def test_failed_source_keeps_its_securities(db, make_ctx):
    refresh_universe(make_ctx(listings=[FakeListing([LVMH, ASML]), FakeListing([APPLE_US], source="us")]))
    with pytest.raises(RuntimeError, match="us"):
        refresh_universe(make_ctx(listings=[FakeListing([LVMH]), FakeListing([], source="us")]))
    assert by_ticker(db, "AAPL").active is True
    assert by_ticker(db, "ASML.AS").active is False  # Euronext a répondu : ASML a bien disparu


def test_confirmed_seed_etf_from_a_source_stays_eligible(db, make_ctx):
    cw8 = ListedSecurity("LU1681043599", "CW8", "AMUNDI MSCI WORLD SWAP", "Euronext Paris", "CW8.PA", "etf", "EUR")
    refresh_universe(make_ctx(listings=[FakeListing([LVMH]), FakeListing([cw8], source="euronext_etf")]))
    security = by_ticker(db, "CW8.PA")
    assert (security.source, security.isin) == ("euronext_etf", "LU1681043599")
    assert (security.envelope_status("pea"), security.envelope("pea").source) == ("eligible", "seed")
