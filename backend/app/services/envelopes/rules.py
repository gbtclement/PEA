"""Enveloppes d'investissement : registre et règles automatiques (fonctions pures).

Une correction manuelle prime toujours. Seules les enveloppes à règle sont stockées (table `security_envelopes`) ;
le compte-titres accepte tous les titres et n'est pas stocké. Ajouter une enveloppe = une entrée dans `ENVELOPES`
et, si elle a une règle, une fonction appelée par `compute_envelopes`.

PEA : siège dans l'UE ou l'EEE (approché par le préfixe ISIN) et société soumise à l'IS ; les foncières cotées
(SIIC/REIT) en sont généralement exonérées, d'où « à vérifier ». ETF et indices : listes de départ (`seeds/`).
PEA-PME : éligible PEA, moins de 5 000 salariés, CA ≤ 1,5 Md€ et capitalisation < 1 Md€. C'est une estimation.
"""
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

ELIGIBLE = "eligible"
TO_CHECK = "a_verifier"
NOT_ELIGIBLE = "non_eligible"
STATUSES = (ELIGIBLE, TO_CHECK, NOT_ELIGIBLE)

PEA, PEA_PME, CTO = "pea", "pea_pme", "cto"
ENVELOPES: dict[str, str] = {PEA: "PEA", PEA_PME: "PEA-PME", CTO: "Compte-titres"}
RULE_ENVELOPES = (PEA, PEA_PME)  # ordre de calcul : le PEA-PME dépend du PEA

PME_MAX_EMPLOYEES = 5_000
PME_MAX_REVENUE_EUR = 1_500_000_000
PME_MAX_MARKET_CAP_EUR = 1_000_000_000

EU_EEA_COUNTRIES = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    "IS", "LI", "NO",
})

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


@dataclass(frozen=True)
class SecurityFacts:
    kind: str  # stock | etf | index
    country: str | None
    industry: str | None
    employees: int | None = None
    revenue_eur: float | None = None
    market_cap_eur: float | None = None


@dataclass(frozen=True)
class EnvelopeStatus:
    status: str
    source: str  # auto | seed | manual
    override: str | None


def country_from_isin(isin: str | None) -> str | None:
    if not isin:
        return None
    normalized = isin.strip().upper()
    return normalized[:2] if _ISIN_RE.match(normalized) else None


def pea_status(facts: SecurityFacts) -> tuple[str, str]:
    if facts.kind == "index":
        return NOT_ELIGIBLE, "seed"
    if facts.kind == "etf":
        return ELIGIBLE, "seed"  # seuls des ETF éligibles figurent dans seeds/etfs.csv
    if facts.country is None:
        return TO_CHECK, "auto"
    if facts.country.upper() not in EU_EEA_COUNTRIES:
        return NOT_ELIGIBLE, "auto"
    if facts.industry and facts.industry.strip().upper().startswith("REIT"):
        return TO_CHECK, "auto"
    return ELIGIBLE, "auto"


def pea_pme_status(pea: str, facts: SecurityFacts) -> str:
    if facts.kind != "stock":
        return NOT_ELIGIBLE
    if pea != ELIGIBLE:
        return pea
    if facts.employees is None or facts.revenue_eur is None or facts.market_cap_eur is None:
        return TO_CHECK
    small = (facts.employees < PME_MAX_EMPLOYEES and facts.revenue_eur <= PME_MAX_REVENUE_EUR
             and facts.market_cap_eur < PME_MAX_MARKET_CAP_EUR)
    return ELIGIBLE if small else NOT_ELIGIBLE


def _with_override(status: str, source: str, override: str | None) -> EnvelopeStatus:
    if override in STATUSES:
        return EnvelopeStatus(override, "manual", override)
    return EnvelopeStatus(status, source, None)


def compute_envelopes(facts: SecurityFacts, overrides: Mapping[str, str | None]) -> dict[str, EnvelopeStatus]:
    pea = _with_override(*pea_status(facts), overrides.get(PEA))
    pea_pme = _with_override(pea_pme_status(pea.status, facts), "auto", overrides.get(PEA_PME))
    return {PEA: pea, PEA_PME: pea_pme}


def filtering_envelopes(codes: Iterable[str]) -> frozenset[str]:
    """Enveloppes qui filtrent les titres ; vide = tous les titres (rien de choisi, ou compte-titres coché)."""
    chosen = set(codes)
    if CTO in chosen:
        return frozenset()
    return frozenset(chosen & set(RULE_ENVELOPES))
