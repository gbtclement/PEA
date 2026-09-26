from sqlalchemy import select

from app.jobs.universe import refresh_universe
from app.models import Security
from app.providers.base import ListedSecurity
from tests.fakes import FakeListing

LVMH = ListedSecurity("FR0000121014", "MC", "LVMH", "Euronext Paris", "MC.PA")
ASML = ListedSecurity("NL0010273215", "ASML", "ASML", "Euronext Amsterdam", "ASML.AS")
THREE_M = ListedSecurity("US88579Y1010", "MMM", "3M", "Euronext Paris", "MMM.PA")


def by_ticker(db, ticker: str) -> Security:
    return db.scalars(select(Security).where(Security.yahoo_ticker == ticker)).one()


def test_universe_classifies_listed_and_seeds(db, make_ctx):
    refresh_universe(make_ctx(listing=FakeListing([LVMH, ASML, THREE_M])))
    assert by_ticker(db, "MC.PA").eligibility == "eligible"
    assert by_ticker(db, "MC.PA").country == "FR"
    assert by_ticker(db, "ASML.AS").eligibility == "eligible"
    assert by_ticker(db, "MMM.PA").eligibility == "non_eligible"
    index = by_ticker(db, "^FCHI")
    assert (index.kind, index.eligibility, index.eligibility_source) == ("index", "non_eligible", "seed")
    etfs = db.scalars(select(Security).where(Security.kind == "etf")).all()
    assert etfs and all(e.eligibility == "eligible" and e.eligibility_source == "seed" for e in etfs)
    sap = by_ticker(db, "SAP.DE")
    assert (sap.country, sap.eligibility) == ("DE", "eligible")


def test_override_survives_refresh(db, make_ctx):
    ctx = make_ctx(listing=FakeListing([LVMH]))
    refresh_universe(ctx)
    lvmh = by_ticker(db, "MC.PA")
    lvmh.eligibility_override = "non_eligible"
    db.flush()
    refresh_universe(ctx)
    lvmh = by_ticker(db, "MC.PA")
    assert (lvmh.eligibility, lvmh.eligibility_source) == ("non_eligible", "override")


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
    import pytest

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
    assert by_ticker(db, "GFC.PA").eligibility == "a_verifier"
