"""Règle d'éligibilité PEA : siège dans l'UE ou l'EEE, soumis à l'impôt sur les sociétés.

Le pays du siège est approché par le préfixe du code ISIN. Les foncières cotées
(SIIC/REIT) sont exonérées d'IS et donc généralement exclues : on les marque « à vérifier ».
"""

import re

ELIGIBLE = "eligible"
TO_CHECK = "a_verifier"
NOT_ELIGIBLE = "non_eligible"

EU_EEA_COUNTRIES = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    "IS", "LI", "NO",
})

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def country_from_isin(isin: str | None) -> str | None:
    if not isin:
        return None
    normalized = isin.strip().upper()
    return normalized[:2] if _ISIN_RE.match(normalized) else None


def classify_eligibility(country: str | None, industry: str | None) -> str:
    if country is None:
        return TO_CHECK
    if country.upper() not in EU_EEA_COUNTRIES:
        return NOT_ELIGIBLE
    if industry and industry.strip().upper().startswith("REIT"):
        return TO_CHECK
    return ELIGIBLE


def effective_eligibility(auto: str, override: str | None, auto_source: str = "auto") -> tuple[str, str]:
    if override in (ELIGIBLE, NOT_ELIGIBLE):
        return override, "override"
    return auto, auto_source
