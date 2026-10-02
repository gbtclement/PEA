import pytest

from app.services.envelopes.rules import (
    CTO, ELIGIBLE, ENVELOPES, NOT_ELIGIBLE, PEA, PEA_PME, RULE_ENVELOPES, TO_CHECK, EnvelopeStatus, SecurityFacts,
    compute_envelopes, country_from_isin, filtering_envelopes, pea_pme_status, pea_status,
)


def stock(country="FR", industry=None, employees=1_000, revenue_eur=200e6, market_cap_eur=500e6) -> SecurityFacts:
    return SecurityFacts(kind="stock", country=country, industry=industry, employees=employees,
                         revenue_eur=revenue_eur, market_cap_eur=market_cap_eur)


def test_registry():
    assert list(ENVELOPES) == [PEA, PEA_PME, CTO]
    assert ENVELOPES[PEA_PME] == "PEA-PME" and ENVELOPES[CTO] == "Compte-titres"
    assert RULE_ENVELOPES == (PEA, PEA_PME)  # PEA-PME dépend du PEA : calculé après


@pytest.mark.parametrize("isin, expected", [
    ("FR0000121014", "FR"), ("nl0010273215", "NL"), ("US88579Y1010", "US"),
    ("BAD", None), ("", None), (None, None), ("FR000012101X", None),
])
def test_country_from_isin(isin, expected):
    assert country_from_isin(isin) == expected


@pytest.mark.parametrize("country, industry, expected", [
    ("FR", "Luxury Goods", ELIGIBLE), ("DE", None, ELIGIBLE), ("NO", None, ELIGIBLE), ("IS", None, ELIGIBLE),
    ("US", None, NOT_ELIGIBLE), ("GB", None, NOT_ELIGIBLE), ("CH", None, NOT_ELIGIBLE),
    (None, None, TO_CHECK), ("FR", "REIT - Retail", TO_CHECK), ("FR", "REIT—Diversified", TO_CHECK),
])
def test_pea_for_stocks(country, industry, expected):
    assert pea_status(stock(country=country, industry=industry)) == (expected, "auto")


def test_pea_for_confirmed_etf_and_index_comes_from_the_seed_lists():
    assert pea_status(SecurityFacts(kind="etf", country=None, industry=None, confirmed_etf=True)) == (ELIGIBLE, "seed")
    assert pea_status(SecurityFacts(kind="index", country=None, industry=None)) == (NOT_ELIGIBLE, "seed")


@pytest.mark.parametrize("facts, expected", [
    (stock(), ELIGIBLE),
    (stock(employees=4_999), ELIGIBLE),
    (stock(employees=5_000), NOT_ELIGIBLE),             # moins de 5 000 salariés
    (stock(revenue_eur=1.5e9), ELIGIBLE),               # CA ≤ 1,5 Md€
    (stock(revenue_eur=1.5e9 + 1), NOT_ELIGIBLE),
    (stock(market_cap_eur=999_999_999), ELIGIBLE),
    (stock(market_cap_eur=1e9), NOT_ELIGIBLE),          # capitalisation < 1 Md€
    (stock(employees=None), TO_CHECK),
    (stock(revenue_eur=None), TO_CHECK),
    (stock(market_cap_eur=None), TO_CHECK),
    (stock(employees=None, market_cap_eur=5e9), TO_CHECK),  # donnée manquante : on ne conclut pas
    (SecurityFacts(kind="etf", country=None, industry=None), NOT_ELIGIBLE),
])
def test_pea_pme_when_pea_eligible(facts, expected):
    assert pea_pme_status(ELIGIBLE, facts) == expected


def test_pea_pme_follows_a_non_eligible_or_unsure_pea():
    assert pea_pme_status(NOT_ELIGIBLE, stock()) == NOT_ELIGIBLE
    assert pea_pme_status(TO_CHECK, stock()) == TO_CHECK


def test_compute_without_override():
    result = compute_envelopes(stock(), {})
    assert result == {PEA: EnvelopeStatus(ELIGIBLE, "auto", None), PEA_PME: EnvelopeStatus(ELIGIBLE, "auto", None)}


def test_manual_pea_override_also_drives_pea_pme():
    result = compute_envelopes(stock(), {PEA: NOT_ELIGIBLE})
    assert result[PEA] == EnvelopeStatus(NOT_ELIGIBLE, "manual", NOT_ELIGIBLE)
    assert result[PEA_PME] == EnvelopeStatus(NOT_ELIGIBLE, "auto", None)


def test_manual_override_accepts_the_three_statuses_and_ignores_garbage():
    assert compute_envelopes(stock(), {PEA_PME: TO_CHECK})[PEA_PME] == EnvelopeStatus(TO_CHECK, "manual", TO_CHECK)
    etf = SecurityFacts(kind="etf", country=None, industry=None, confirmed_etf=True)
    assert compute_envelopes(etf, {PEA_PME: ELIGIBLE})[PEA_PME] == EnvelopeStatus(ELIGIBLE, "manual", ELIGIBLE)
    assert compute_envelopes(etf, {PEA: "peut-être"})[PEA] == EnvelopeStatus(ELIGIBLE, "seed", None)


@pytest.mark.parametrize("codes, expected", [
    ([], frozenset()), (["cto"], frozenset()), (["pea", "cto"], frozenset()),  # compte-titres : tout
    (["pea"], frozenset({"pea"})), (["pea_pme", "pea"], frozenset({"pea", "pea_pme"})),
    (["inconnu"], frozenset()),
])
def test_filtering_envelopes(codes, expected):
    assert filtering_envelopes(codes) == expected


def test_etf_eligibility_needs_confirmation_or_pea_in_name():
    assert pea_status(SecurityFacts("etf", None, None, name="iShares Core MSCI World", confirmed_etf=True)) == (ELIGIBLE, "seed")
    assert pea_status(SecurityFacts("etf", None, None, name="AM ASIP EXJ PEA")) == (ELIGIBLE, "auto")
    assert pea_status(SecurityFacts("etf", "IE", None, name="iShares Core MSCI World")) == (TO_CHECK, "auto")
    assert pea_status(SecurityFacts("etf", None, None, name="Speaker Corp")) == (TO_CHECK, "auto")  # « PEA » doit être un mot
