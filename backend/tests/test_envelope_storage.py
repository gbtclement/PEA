from sqlalchemy import select

from app.models import Security, SecurityEnvelope, SecurityFundamentals
from app.repositories.envelopes import envelope_clause, refresh_envelopes, set_envelope_override
from tests.factories import make_security


def test_refresh_creates_one_row_per_rule_envelope(db):
    security = make_security(db, "MC.PA")
    db.add(SecurityFundamentals(security_id=security.id, market_cap=3e11, currency="EUR",
                                employees=200_000, revenue=8e10, revenue_currency="EUR"))
    db.flush()
    refresh_envelopes(security, db.get(SecurityFundamentals, security.id))
    db.flush()
    rows = {e.envelope: (e.status, e.source, e.override) for e in security.envelopes}
    assert rows == {"pea": ("eligible", "auto", None), "pea_pme": ("non_eligible", "auto", None)}
    assert security.eligible_envelopes == ["pea"]
    assert security.envelope_status("pea_pme") == "non_eligible" and security.envelope_status("cto") is None


def test_small_company_without_fundamentals_is_to_check_for_pea_pme(db):
    security = make_security(db, "ALCAR.PA")
    refresh_envelopes(security, None)
    assert security.envelope_status("pea_pme") == "a_verifier"
    assert security.eligible_envelopes == ["pea"]


def test_override_survives_refresh_and_reset_returns_to_auto(db):
    security = make_security(db, "MC.PA")
    set_envelope_override(security, "pea", "non_eligible", None)
    refresh_envelopes(security, None)
    pea = security.envelope("pea")
    assert (pea.status, pea.source, pea.override) == ("non_eligible", "manual", "non_eligible")
    assert security.envelope_status("pea_pme") == "non_eligible"  # suit la correction du PEA
    set_envelope_override(security, "pea", None, None)
    assert (pea.status, pea.source, pea.override) == ("eligible", "auto", None)


def test_envelope_clause(db):
    pea = make_security(db, "A.PA")
    foreign = make_security(db, "B.PA", eligibility="non_eligible", country="US")
    unsure = make_security(db, "C.PA", eligibility="a_verifier")
    pme = make_security(db, "D.PA", pea_pme="eligible")
    assert envelope_clause([]) is None and envelope_clause(["cto", "pea"]) is None

    def ids(codes):
        found = set(db.scalars(select(Security.id).where(envelope_clause(codes))))
        return found & {pea.id, foreign.id, unsure.id, pme.id}

    assert ids(["pea"]) == {pea.id, pme.id}  # « à vérifier » n'entre pas dans le filtre
    assert ids(["pea_pme"]) == {pme.id}
    assert ids(["pea_pme", "pea"]) == {pea.id, pme.id}


def test_deleting_a_security_deletes_its_envelopes(db):
    security = make_security(db, "MC.PA")
    db.delete(security)
    db.flush()
    assert db.scalars(select(SecurityEnvelope).where(SecurityEnvelope.security_id == security.id)).all() == []
