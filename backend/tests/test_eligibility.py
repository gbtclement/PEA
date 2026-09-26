import pytest

from app.services.eligibility.rules import (
    ELIGIBLE, NOT_ELIGIBLE, TO_CHECK, classify_eligibility, country_from_isin, effective_eligibility,
)


@pytest.mark.parametrize("isin, expected", [
    ("FR0000121014", "FR"),
    ("nl0010273215", "NL"),
    ("US88579Y1010", "US"),
    ("BAD", None),
    ("", None),
    (None, None),
    ("FR000012101X", None),  # le dernier caractère (clé) doit être un chiffre
])
def test_country_from_isin(isin, expected):
    assert country_from_isin(isin) == expected


@pytest.mark.parametrize("country, industry, expected", [
    ("FR", "Luxury Goods", ELIGIBLE),
    ("DE", None, ELIGIBLE),
    ("NO", None, ELIGIBLE),   # Norvège : EEE
    ("IS", None, ELIGIBLE),   # Islande : EEE
    ("US", None, NOT_ELIGIBLE),
    ("GB", None, NOT_ELIGIBLE),
    ("CH", None, NOT_ELIGIBLE),
    ("BM", None, NOT_ELIGIBLE),
    (None, None, TO_CHECK),
    ("FR", "REIT - Retail", TO_CHECK),       # SIIC : exonérée d'IS, exclue du PEA
    ("FR", "REIT—Diversified", TO_CHECK),
])
def test_classify_eligibility(country, industry, expected):
    assert classify_eligibility(country, industry) == expected


def test_override_wins():
    assert effective_eligibility(ELIGIBLE, NOT_ELIGIBLE) == (NOT_ELIGIBLE, "override")
    assert effective_eligibility(TO_CHECK, ELIGIBLE) == (ELIGIBLE, "override")


def test_no_override_keeps_auto_source():
    assert effective_eligibility(ELIGIBLE, None) == (ELIGIBLE, "auto")
    assert effective_eligibility(ELIGIBLE, None, auto_source="seed") == (ELIGIBLE, "seed")


def test_invalid_override_is_ignored():
    assert effective_eligibility(ELIGIBLE, "n'importe quoi") == (ELIGIBLE, "auto")
