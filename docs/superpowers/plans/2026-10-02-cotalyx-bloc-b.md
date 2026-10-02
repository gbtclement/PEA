# Cotalyx — Bloc B (enveloppes) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Le PEA devient une enveloppe parmi d'autres (PEA, PEA-PME, compte-titres). Chacun choisit ses enveloppes dans ses réglages ; le top 10, les classements et les prévisions s'y adaptent, l'Explorer filtre par enveloppe, et l'administrateur corrige les enveloppes titre par titre.

**Architecture:**
- Un registre de règles pures (`services/envelopes/rules.py`) calcule le statut de chaque enveloppe à règle (`pea`, `pea_pme`) à partir des faits d'un titre : type, pays, industrie, effectif, chiffre d'affaires, capitalisation.
- Les statuts sont stockés dans une nouvelle table `security_envelopes`, une ligne par titre et par enveloppe à règle, chargée avec le titre (`selectin`). Les colonnes `securities.eligibility*` disparaissent.
- Le compte-titres n'est pas stocké : il accepte tout.
- Les réglages de l'utilisateur gardent la liste de ses enveloppes. Aucune enveloppe choisie, ou le compte-titres coché, veut dire « tous les titres ».
- Le filtre s'applique à la lecture (top 10, classements, prévisions) ; le calcul des scores ne dépend plus du PEA.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, yfinance ; React 19, TanStack Query, Vitest, Playwright ; Docsify.

**Spec:** `docs/superpowers/specs/2026-10-01-cotalyx-design.md` (section « Bloc B — Enveloppes »).

## Global Constraints

- **Codes d'enveloppe :** `pea`, `pea_pme`, `cto`. **Libellés :** « PEA », « PEA-PME », « Compte-titres ».
- **Statuts :** `eligible`, `a_verifier`, `non_eligible`. **Sources :** `auto`, `seed`, `manual`.
- **Règle PEA-PME :**
  - éligible PEA, et moins de 5 000 salariés, et CA ≤ 1,5 Md€, et capitalisation < 1 Md€ ;
  - donnée manquante → `a_verifier` ;
  - ce n'est qu'une estimation, et l'interface la présente comme telle.
- **Correction manuelle :** elle prime toujours. Elle peut valoir `eligible`, `a_verifier` ou `non_eligible` ; `null` revient au calcul automatique.
- **Interface publique :**
  - badges « PEA » et « PEA-PME » uniquement ;
  - aucun badge, aucun filtre « à vérifier » ou « non éligible » (seule la carte admin montre ces statuts) ;
  - un titre « à vérifier » ne sort jamais dans un filtre d'enveloppe.
- **Visiteur sans compte :** tous les titres.
- **Score :** `eligible_for_top` = action, liquide, historique ≥ `min_history_days`, taux de données suffisant. Plus aucune condition PEA.
- **Prévisions :** elles gardent leur fenêtre actuelle.
- **Ne pas modifier :**
  - les migrations Alembic existantes ;
  - `.env` (ne jamais l'ouvrir ni l'afficher) ;
  - les fichiers sous `.superpowers/` et `docs/superpowers/`, sauf ce plan et le registre d'exécution.
- **Langues :** interface et commentaires en français, commits en anglais (conventional commits).
- **Fin de message de commit :** `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

**Commandes de test :**
- **Backend :** `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q <fichiers>`.
- **Frontend :** depuis `frontend/`, `npx vitest run <fichiers>` et `npx tsc -b`.

## Review Focus

1. **Migration de la prod :** un titre corrigé à la main avant le déploiement (`eligibility_override` renseigné) garde sa correction, qui devient une ligne `pea` de source `manual`. Les titres ETF et indices restent `seed`. Test dans la tâche 2.
2. **Utilisateur qui coche « PEA » et « Compte-titres » :** il voit tous les titres. Le compte-titres l'emporte, il n'y a pas d'intersection. Tests dans la tâche 4 (API) et la tâche 7 (texte du top 10).
3. **Correction manuelle du PEA :** passer une action en « non éligible PEA » la fait sortir aussitôt du top PEA et de son PEA-PME, sans attendre le recalcul des scores. Tests dans la tâche 2 (PEA-PME suit la correction) et la tâche 4 (top filtré).
4. **Fondamentaux Yahoo partiels :** une réponse sans effectif ni CA rend « à vérifier » en PEA-PME et ne fait jamais sortir l'action du PEA. Elle n'efface pas non plus des valeurs connues ni l'industrie connue. Test dans la tâche 3.
5. **Top 10 de l'utilisateur dans les mails :** le récap du samedi et l'alerte « entrée dans le top 10 » suivent le top 10 de l'utilisateur (ses enveloppes), pas le top 10 global. Test dans la tâche 4.

---

### Task 1: Règles des enveloppes (fonctions pures)

**Files:**
- Create: `backend/app/services/envelopes/__init__.py` (vide)
- Create: `backend/app/services/envelopes/rules.py`
- Create: `backend/tests/test_envelope_rules.py`
- Delete: `backend/app/services/eligibility/rules.py`, `backend/app/services/eligibility/__init__.py`, `backend/tests/test_eligibility.py`
- Modify: `backend/tests/test_seeds.py:2` (import de `EU_EEA_COUNTRIES` depuis le nouveau module)

Le module `services/eligibility` est encore importé par `repositories/securities.py` et `jobs/universe.py`. Dans cette tâche, ces deux fichiers importent depuis `app.services.envelopes.rules` les anciens noms `classify_eligibility` et `effective_eligibility`. Ces deux noms sont gardés dans le nouveau module jusqu'à la tâche 2, qui les supprime.

**Interfaces:**
- Produces (`app.services.envelopes.rules`) :
  - Constantes : `ELIGIBLE`, `TO_CHECK`, `NOT_ELIGIBLE`, `STATUSES`, `PEA`, `PEA_PME`, `CTO`, `ENVELOPES`, `RULE_ENVELOPES`, `EU_EEA_COUNTRIES`.
  - `country_from_isin(isin) -> str | None`.
  - `SecurityFacts` (dataclass figée).
  - `EnvelopeStatus(status, source, override)` (dataclass figée).
  - `pea_status(facts) -> tuple[str, str]`.
  - `pea_pme_status(pea: str, facts) -> str`.
  - `compute_envelopes(facts, overrides: Mapping[str, str | None]) -> dict[str, EnvelopeStatus]`.
  - `filtering_envelopes(codes) -> frozenset[str]` : un ensemble vide veut dire « pas de filtre ».

- [ ] **Step 1: Write the failing test**

`backend/tests/test_envelope_rules.py` :

```python
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


def test_pea_for_etf_and_index_comes_from_the_seed_lists():
    assert pea_status(SecurityFacts(kind="etf", country=None, industry=None)) == (ELIGIBLE, "seed")
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
    etf = SecurityFacts(kind="etf", country=None, industry=None)
    assert compute_envelopes(etf, {PEA_PME: ELIGIBLE})[PEA_PME] == EnvelopeStatus(ELIGIBLE, "manual", ELIGIBLE)
    assert compute_envelopes(etf, {PEA: "peut-être"})[PEA] == EnvelopeStatus(ELIGIBLE, "seed", None)


@pytest.mark.parametrize("codes, expected", [
    ([], frozenset()), (["cto"], frozenset()), (["pea", "cto"], frozenset()),  # compte-titres : tout
    (["pea"], frozenset({"pea"})), (["pea_pme", "pea"], frozenset({"pea", "pea_pme"})),
    (["inconnu"], frozenset()),
])
def test_filtering_envelopes(codes, expected):
    assert filtering_envelopes(codes) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_envelope_rules.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.envelopes'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/services/envelopes/rules.py` :

```python
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


# Anciens noms, utilisés jusqu'à la tâche 2 du bloc B (stockage par enveloppe).
def classify_eligibility(country: str | None, industry: str | None) -> str:
    return pea_status(SecurityFacts(kind="stock", country=country, industry=industry))[0]


def effective_eligibility(auto: str, override: str | None, auto_source: str = "auto") -> tuple[str, str]:
    if override in (ELIGIBLE, NOT_ELIGIBLE):
        return override, "override"
    return auto, auto_source
```

Ensuite :
- supprimer `backend/app/services/eligibility/` (les deux fichiers) et `backend/tests/test_eligibility.py` ;
- dans `backend/app/repositories/securities.py`, `backend/app/jobs/universe.py` et `backend/tests/test_seeds.py`, remplacer `from app.services.eligibility.rules import` par `from app.services.envelopes.rules import`.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_envelope_rules.py tests/test_seeds.py tests/test_universe.py tests/test_market_jobs.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services backend/app/repositories/securities.py backend/app/jobs/universe.py backend/tests
git commit -m "feat: envelope registry with PEA and PEA-PME rules"
```

---

### Task 2: Table `security_envelopes`, migration et lecture par enveloppe

Cette tâche remplace le stockage sans changer le comportement visible, à quatre exceptions près :
- **Cours suivis :** le worker suit les cours de tous les titres actifs.
- **SEO :** le sitemap et les fiches publiques listent tous les titres actifs.
- **Correction admin :** elle accepte aussi « à vérifier ».
- **PEA-PME :** il est calculé, mais pas encore affiché.

Les réponses de l'API gardent temporairement leurs champs `eligibility` (valeur = statut PEA) ; la tâche 5 les remplace.

**Files:**
- Create: `backend/app/models/envelope.py`
- Modify:
  - `backend/app/models/security.py` : retirer les colonnes `eligibility*`, ajouter la relation et les aides.
  - `backend/app/models/__init__.py`.
  - `backend/app/models/market.py` : `SecurityFundamentals.employees`, `revenue`, `revenue_currency`.
  - `backend/app/models/portfolio.py` : `UserSettings.envelopes`.
  - `backend/app/models/notifications.py` : `ScoreSnapshot.top_pool`.
- Create: `backend/alembic/versions/c5e7a9b1d3f5_security_envelopes.py`
- Create: `backend/app/repositories/envelopes.py`
- Modify: `backend/app/repositories/securities.py`, `backend/app/jobs/universe.py`, `backend/app/jobs/market.py:100-113`
- Modify (lecture du statut PEA) :
  - `backend/app/jobs/scoring.py:95-97` ;
  - `backend/app/repositories/screener.py:35-40` ;
  - `backend/app/api/routes/rankings.py:18-23` ;
  - `backend/app/repositories/market_data.py:11-17` ;
  - `backend/app/api/routes/seo.py:34-35` ;
  - `backend/app/api/routes/securities.py` ;
  - `backend/app/api/routes/security_detail.py:56` ;
  - `backend/app/api/routes/forecasts.py:58` ;
  - `backend/app/schemas/screener.py:35` ;
  - `backend/app/schemas/securities.py` ;
  - `backend/app/services/assistant/tools.py:74,88`.
- Modify: `backend/tests/factories.py`
- Test: `backend/tests/test_envelope_storage.py` (nouveau), `backend/tests/test_migration_envelopes.py` (nouveau)
- Adapter : `test_universe.py`, `test_market_jobs.py`, `test_api_favorites_eligibility.py`, `test_api_seo.py`, `test_api_securities.py`

**Interfaces:**
- Consumes: tout `app.services.envelopes.rules` (tâche 1).
- Produces :
  - `SecurityEnvelope` (modèle) : `security_id`, `envelope`, `status`, `source`, `override`.
  - Sur `Security` :
    - `Security.envelopes: list[SecurityEnvelope]`, chargée en `selectin` ;
    - `Security.envelope(code) -> SecurityEnvelope | None` ;
    - `Security.envelope_status(code) -> str | None` ;
    - `Security.eligible_envelopes -> list[str]`.
  - Dans `app.repositories.envelopes` :
    - `facts_for(security, fundamentals) -> SecurityFacts` ;
    - `refresh_envelopes(security, fundamentals) -> None` ;
    - `set_envelope_override(security, code, override, fundamentals) -> None` ;
    - `envelope_clause(codes) -> ColumnElement[bool] | None`.
  - `update_classification(security, sector, industry, fundamentals)` : nouveau paramètre.
  - Nouvelles colonnes, utilisées par les tâches 3 et 4 :
    - `UserSettings.envelopes: list[str]` (défaut `[]`) ;
    - `ScoreSnapshot.top_pool: bool` ;
    - `SecurityFundamentals.employees: int | None`, `revenue: float | None`, `revenue_currency: str | None`.
  - `make_security(..., eligibility="eligible", pea_pme=None)` : crée la ligne `pea` (et la ligne `pea_pme` si fournie).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_envelope_storage.py` :

```python
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
```

`backend/tests/test_migration_envelopes.py` (même méthode que `test_migration_accounts.py`, base jetable) :

```python
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

PREVIOUS = "b3c5d7e9f1a3"
NAME = "pea_radar_migration_envelopes_test"


@pytest.fixture
def migration_url():
    base = make_url(get_settings().test_database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {NAME}"))
    yield base.set(database=NAME).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)"))
    admin.dispose()


def _config(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    return cfg


def test_eligibility_columns_become_pea_rows(migration_url):
    cfg = _config(migration_url)
    command.upgrade(cfg, PREVIOUS)
    engine = create_engine(migration_url)
    with engine.begin() as conn:
        insert = ("INSERT INTO securities (id, yahoo_ticker, symbol, name, kind, market, eligibility, eligibility_source, "
                  "eligibility_override, active, created_at, updated_at) VALUES "
                  "(:id, :t, :t, :t, :kind, 'Euronext Paris', :e, :s, :o, true, now(), now())")
        conn.execute(text(insert), [
            {"id": 1, "t": "MC.PA", "kind": "stock", "e": "eligible", "s": "auto", "o": None},
            {"id": 2, "t": "GFC.PA", "kind": "stock", "e": "eligible", "s": "override", "o": "eligible"},
            {"id": 3, "t": "CW8.PA", "kind": "etf", "e": "eligible", "s": "seed", "o": None},
            {"id": 4, "t": "MMM.PA", "kind": "stock", "e": "non_eligible", "s": "auto", "o": None},
        ])
        conn.execute(text("INSERT INTO score_snapshots (day, security_id, total, top_rank) VALUES "
                          "('2026-10-01', 1, 80, 1), ('2026-10-01', 4, 50, NULL)"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT security_id, envelope, status, source, override FROM security_envelopes "
                                 "ORDER BY security_id")).all()
        assert [tuple(r) for r in rows] == [
            (1, "pea", "eligible", "auto", None),
            (2, "pea", "eligible", "manual", "eligible"),
            (3, "pea", "eligible", "seed", None),
            (4, "pea", "non_eligible", "auto", None),
        ]
        pool = dict(conn.execute(text("SELECT security_id, top_pool FROM score_snapshots")).all())
        assert pool == {1: True, 4: False}
    inspector = inspect(engine)
    assert not {"eligibility", "eligibility_source", "eligibility_override"} & {c["name"] for c in inspector.get_columns("securities")}
    assert {"employees", "revenue", "revenue_currency"} <= {c["name"] for c in inspector.get_columns("fundamentals")}
    assert "envelopes" in {c["name"] for c in inspector.get_columns("user_settings")}
    command.downgrade(cfg, PREVIOUS)
    with engine.connect() as conn:
        back = conn.execute(text("SELECT eligibility, eligibility_source, eligibility_override FROM securities WHERE id = 2")).one()
        assert tuple(back) == ("eligible", "override", "eligible")
    engine.dispose()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_envelope_storage.py tests/test_migration_envelopes.py`
Expected: FAIL (`ImportError: cannot import name 'SecurityEnvelope'`)

- [ ] **Step 3: Models**

`backend/app/models/envelope.py` :

```python
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityEnvelope(Base):
    """Statut d'un titre pour une enveloppe à règle (pea, pea_pme). Le compte-titres n'est pas stocké : il accepte tout."""

    __tablename__ = "security_envelopes"
    __table_args__ = (Index("ix_security_envelopes_envelope_status", "envelope", "status"),)

    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    envelope: Mapped[str] = mapped_column(String(16), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))  # eligible | a_verifier | non_eligible
    source: Mapped[str] = mapped_column(String(16), default="auto")  # auto | seed | manual
    override: Mapped[str | None] = mapped_column(String(16))
```

`backend/app/models/security.py` : supprimer les trois colonnes `eligibility*`, puis ajouter :

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.envelope import SecurityEnvelope


class Security(TimestampMixin, Base):
    ...  # colonnes existantes, sans eligibility / eligibility_source / eligibility_override
    active: Mapped[bool] = mapped_column(default=True)
    envelopes: Mapped[list[SecurityEnvelope]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", passive_deletes=True, order_by=SecurityEnvelope.envelope,
    )

    def envelope(self, code: str) -> SecurityEnvelope | None:
        return next((e for e in self.envelopes if e.envelope == code), None)

    def envelope_status(self, code: str) -> str | None:
        row = self.envelope(code)
        return row.status if row else None

    @property
    def eligible_envelopes(self) -> list[str]:
        """Codes des enveloppes à règle où le titre est éligible (« pea » avant « pea_pme »)."""
        return [e.envelope for e in self.envelopes if e.status == "eligible"]
```

Autres modèles :
- `backend/app/models/__init__.py` : importer `SecurityEnvelope` depuis `app.models.envelope` et l'ajouter à `__all__`.
- `SecurityFundamentals` (`models/market.py`), après `market_cap` :

```python
    employees: Mapped[int | None] = mapped_column(Integer)
    revenue: Mapped[float | None] = mapped_column(Float)  # chiffre d'affaires annuel, en `revenue_currency`
    revenue_currency: Mapped[str | None] = mapped_column(String(3))
```

(ajouter `Integer` à l'import `sqlalchemy` du fichier.)

- `UserSettings` (`models/portfolio.py`), après `fee_grid` :

```python
    envelopes: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))  # codes d'enveloppe ; vide = tous les titres
```

- `ScoreSnapshot` (`models/notifications.py`), après `top_rank`, avec la docstring mise à jour (« rang dans le top 10 global ») :

```python
    top_pool: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))  # candidat au top 10 (eligible_for_top) ce soir-là
```

(ajouter `Boolean` et `text` à l'import `sqlalchemy` si absents ; idem `text` dans `models/portfolio.py`.)

- [ ] **Step 4: Migration**

`backend/alembic/versions/c5e7a9b1d3f5_security_envelopes.py` :

```python
"""envelopes: security_envelopes, user envelopes, fundamentals size, snapshot top pool

Revision ID: c5e7a9b1d3f5
Revises: b3c5d7e9f1a3
Create Date: 2026-10-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e7a9b1d3f5"
down_revision: Union[str, Sequence[str], None] = "b3c5d7e9f1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_envelopes",
        sa.Column("security_id", sa.Integer(), sa.ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("envelope", sa.String(16), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("override", sa.String(16), nullable=True),
    )
    op.create_index("ix_security_envelopes_envelope_status", "security_envelopes", ["envelope", "status"])
    # L'ancienne éligibilité est celle du PEA ; « override » devient « manual ». Le PEA-PME est calculé par le worker.
    op.execute("""
        INSERT INTO security_envelopes (security_id, envelope, status, source, override)
        SELECT id, 'pea', eligibility,
               CASE eligibility_source WHEN 'override' THEN 'manual' ELSE eligibility_source END,
               eligibility_override
        FROM securities
    """)
    op.drop_index("ix_securities_eligibility", table_name="securities")
    op.drop_column("securities", "eligibility_override")
    op.drop_column("securities", "eligibility_source")
    op.drop_column("securities", "eligibility")
    op.add_column("fundamentals", sa.Column("employees", sa.Integer(), nullable=True))
    op.add_column("fundamentals", sa.Column("revenue", sa.Float(), nullable=True))
    op.add_column("fundamentals", sa.Column("revenue_currency", sa.String(3), nullable=True))
    op.add_column("user_settings", sa.Column("envelopes", postgresql.JSONB(), nullable=False,
                                             server_default=sa.text("'[]'::jsonb")))
    op.add_column("score_snapshots", sa.Column("top_pool", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE score_snapshots SET top_pool = (top_rank IS NOT NULL)")


def downgrade() -> None:
    op.drop_column("score_snapshots", "top_pool")
    op.drop_column("user_settings", "envelopes")
    op.drop_column("fundamentals", "revenue_currency")
    op.drop_column("fundamentals", "revenue")
    op.drop_column("fundamentals", "employees")
    op.add_column("securities", sa.Column("eligibility", sa.String(16), nullable=False, server_default="a_verifier"))
    op.add_column("securities", sa.Column("eligibility_source", sa.String(16), nullable=False, server_default="auto"))
    op.add_column("securities", sa.Column("eligibility_override", sa.String(16), nullable=True))
    op.create_index("ix_securities_eligibility", "securities", ["eligibility"])
    op.execute("""
        UPDATE securities s SET eligibility = e.status,
               eligibility_source = CASE e.source WHEN 'manual' THEN 'override' ELSE e.source END,
               eligibility_override = CASE WHEN e.override IN ('eligible', 'non_eligible') THEN e.override END
        FROM security_envelopes e WHERE e.security_id = s.id AND e.envelope = 'pea'
    """)
    op.drop_table("security_envelopes")
```

Avant d'écrire la migration :
- **Nom de l'index :** vérifier le nom exact de l'index `eligibility` dans la migration initiale, avec `grep -n "eligibility" backend/alembic/versions/d132b530c4d9_initial_schema.py`, et ajuster `ix_securities_eligibility` si besoin.
- **Colonnes NOT NULL :** vérifier que `securities` n'a pas d'autre colonne NOT NULL sans défaut, que le `INSERT` du test de migration devrait alors renseigner. Si c'est le cas, l'ajouter à ce test.

- [ ] **Step 5: Repository**

`backend/app/repositories/envelopes.py` :

```python
"""Statuts des enveloppes stockés par titre : recalcul, corrections manuelles, filtre SQL."""
from collections.abc import Iterable

from sqlalchemy import ColumnElement, exists

from app.models import Security, SecurityEnvelope, SecurityFundamentals
from app.services.envelopes.rules import ELIGIBLE, SecurityFacts, compute_envelopes, filtering_envelopes
from app.services.fx import to_eur


def facts_for(security: Security, fundamentals: SecurityFundamentals | None) -> SecurityFacts:
    f = fundamentals
    return SecurityFacts(
        kind=security.kind, country=security.country, industry=security.industry,
        employees=f.employees if f else None,
        revenue_eur=to_eur(f.revenue, f.revenue_currency or f.currency) if f else None,
        market_cap_eur=to_eur(f.market_cap, f.currency) if f else None,
    )


def refresh_envelopes(security: Security, fundamentals: SecurityFundamentals | None) -> None:
    """Recalcule toutes les enveloppes à règle du titre ; les corrections manuelles sont conservées."""
    overrides = {e.envelope: e.override for e in security.envelopes}
    for code, result in compute_envelopes(facts_for(security, fundamentals), overrides).items():
        row = security.envelope(code)
        if row is None:
            row = SecurityEnvelope(envelope=code)
            security.envelopes.append(row)
        row.status, row.source, row.override = result.status, result.source, result.override


def set_envelope_override(security: Security, code: str, override: str | None,
                          fundamentals: SecurityFundamentals | None) -> None:
    """Correction manuelle (None = revenir au calcul automatique ou à la liste de départ)."""
    refresh_envelopes(security, fundamentals)  # crée la ligne si elle manque encore
    security.envelope(code).override = override
    refresh_envelopes(security, fundamentals)


def envelope_clause(codes: Iterable[str]) -> ColumnElement[bool] | None:
    """Condition « éligible à au moins une de ces enveloppes » ; None = pas de filtre (rien choisi ou compte-titres)."""
    wanted = filtering_envelopes(codes)
    if not wanted:
        return None
    return exists().where(
        SecurityEnvelope.security_id == Security.id,
        SecurityEnvelope.envelope.in_(sorted(wanted)),
        SecurityEnvelope.status == ELIGIBLE,
    )
```

- [ ] **Step 6: Write path (univers, fondamentaux)**

`backend/app/repositories/securities.py` :
- Supprimer :
  - `fixed_eligibility` de `SecurityUpsert` ;
  - `_apply_eligibility` et `_FIXED_BY_KIND` ;
  - `set_eligibility_override` ;
  - l'import `app.services.envelopes.rules`.
- `upsert_securities` : charger les fondamentaux une fois, puis recalculer.

```python
def upsert_securities(session: Session, items: list[SecurityUpsert]) -> int:
    unique = {item.yahoo_ticker: item for item in items}
    existing = list(session.scalars(select(Security)))
    fundamentals = {f.security_id: f for f in session.scalars(select(SecurityFundamentals))}
    by_ticker = {s.yahoo_ticker: s for s in existing}
    by_isin = {s.isin: s for s in existing if s.isin}
    for item in unique.values():
        security = by_ticker.get(item.yahoo_ticker) or (by_isin.get(item.isin) if item.isin else None)
        if security is None:
            security = Security(industry=None)
            session.add(security)
        security.yahoo_ticker = item.yahoo_ticker
        security.symbol = item.symbol
        security.name = item.name
        security.kind = item.kind
        security.market = item.market
        security.isin = item.isin
        security.country = item.country
        security.active = True
        refresh_envelopes(security, fundamentals.get(security.id))
    session.flush()
    return len(unique)


def update_classification(security: Security, sector: str | None, industry: str | None,
                          fundamentals: SecurityFundamentals | None) -> None:
    """Met à jour secteur/industrie (fondamentaux) et recalcule les enveloppes.

    Une réponse Yahoo incomplète (sans secteur/industrie) ne doit pas effacer une classification connue.
    """
    security.sector = sector or security.sector
    security.industry = industry or security.industry
    refresh_envelopes(security, fundamentals)
```

- `search_securities` : garder le paramètre `eligibility` (filtre PEA) et `overridden`, réécrits ainsi :

```python
    if eligibility:
        stmt = stmt.where(exists().where(SecurityEnvelope.security_id == Security.id, SecurityEnvelope.envelope == "pea",
                                         SecurityEnvelope.status == eligibility))
    if overridden:
        stmt = stmt.where(exists().where(SecurityEnvelope.security_id == Security.id, SecurityEnvelope.override.is_not(None)))
```

(imports : `exists` depuis `sqlalchemy`, `SecurityEnvelope` et `SecurityFundamentals` depuis `app.models`, `refresh_envelopes` depuis `app.repositories.envelopes`.)

Autres fichiers :
- `backend/app/jobs/universe.py` : supprimer `_FIXED_BY_KIND`, l'argument `fixed_eligibility=` et les imports `ELIGIBLE` / `NOT_ELIGIBLE`. Ne garder que `country_from_isin`.
- `backend/app/jobs/market.py`, dans `refresh_fundamentals` :

```python
        with ctx.session_factory() as session:
            upsert_fundamentals(session, security_id, fundamentals)
            session.flush()
            update_classification(session.get(Security, security_id), fundamentals.sector, fundamentals.industry,
                                  session.get(SecurityFundamentals, security_id))
            session.commit()
```

(importer `SecurityFundamentals` depuis `app.models`.)

- [ ] **Step 7: Read path (statut PEA, comportement inchangé)**

- `jobs/scoring.py:96` : `s.eligibility == "eligible"` → `s.envelope_status("pea") == "eligible"`. La tâche 4 retire cette condition.
- `repositories/screener.py` (bloc `only_top`) : `Security.eligibility == "eligible"` → `envelope_clause(["pea"])`, après import depuis `app.repositories.envelopes`. La tâche 4 remplace `["pea"]` par les enveloppes de l'utilisateur.
- `api/routes/rankings.py:21` : `row[0].eligibility == "eligible"` → `row[0].envelope_status("pea") == "eligible"`.
- `repositories/market_data.py` : `refreshable_securities` suit tous les titres actifs.

```python
def refreshable_securities(session: Session) -> list[Security]:
    """Titres actifs dont on suit les cours : tous, quelle que soit leur enveloppe."""
    return list(session.scalars(select(Security).where(Security.active.is_(True))))
```

(retirer `or_` de l'import s'il n'est plus utilisé.)

- `api/routes/seo.py` : `_public_securities` devient `(Security.active.is_(True), Security.kind.in_(("stock", "etf")))`.
- `api/routes/securities.py` : supprimer l'import de `set_eligibility_override` et réécrire la route PATCH existante (même URL, provisoire).

```python
    security = db.get(Security, security_id)
    if security is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    set_envelope_override(security, "pea", update.override, db.get(SecurityFundamentals, security_id))
    db.commit()
```

- `schemas/securities.py` : `EligibilityUpdate.override` devient `Literal["eligible", "a_verifier", "non_eligible"] | None`. Dans `SecurityItem.build`, la ligne `pea` remplit les champs :

```python
        pea = security.envelope("pea")
        ...
            eligibility=pea.status if pea else "a_verifier",
            eligibility_source=pea.source if pea else "auto",
            eligibility_override=pea.override if pea else None,
```

- `schemas/screener.py:35` : `eligibility=security.envelope_status("pea") or "a_verifier",`.
- `api/routes/security_detail.py:56` : `eligibility_source=security.envelope("pea").source if security.envelope("pea") else "auto",`.
- `api/routes/forecasts.py:58` : `eligibility=s.envelope_status("pea") or "a_verifier",`.
- `services/assistant/tools.py:74` : `candidates.sort(key=lambda s: (s.envelope_status("pea") != "eligible", not s.yahoo_ticker.endswith(".PA")))`.
- `services/assistant/tools.py:88` : `"eligibility": s.envelope_status("pea"),`.

Pour finir, vérifier qu'aucune référence ne reste :
`grep -rn "\.eligibility\b\|eligibility_source\|eligibility_override\|services.eligibility" backend/app`.
Seuls les noms de champs des schémas Pydantic restent (`eligibility=`, `eligibility_source=`, `eligibility_override=`) ; ils seront remplacés à la tâche 5.

- [ ] **Step 8: Factories and existing tests**

`backend/tests/factories.py` :

```python
def make_security(
    db: Session,
    ticker: str,
    *,
    kind: str = "stock",
    eligibility: str = "eligible",  # statut PEA
    pea_pme: str | None = None,     # statut PEA-PME (aucune ligne si None)
    country: str | None = "FR",
    active: bool = True,
    isin: str | None = None,
    name: str | None = None,
    market: str = "Euronext Paris",
) -> Security:
    security = Security(
        yahoo_ticker=ticker, symbol=ticker.split(".")[0], name=name or ticker, kind=kind, market=market,
        country=country, isin=isin, active=active,
    )
    security.envelopes.append(SecurityEnvelope(envelope="pea", status=eligibility, source="auto"))
    if pea_pme is not None:
        security.envelopes.append(SecurityEnvelope(envelope="pea_pme", status=pea_pme, source="auto"))
    db.add(security)
    db.flush()
    return security
```

(importer `SecurityEnvelope`.)

Tests existants à adapter :
- **`test_universe.py` :**
  - lire `x.envelope_status("pea")` au lieu de `x.eligibility`, et `x.envelope("pea").source` au lieu de `x.eligibility_source` ;
  - dans `test_override_survives_refresh`, remplacer `lvmh.eligibility_override = "non_eligible"` par `set_envelope_override(lvmh, "pea", "non_eligible", None)` ;
  - attendre `("non_eligible", "manual")` au lieu de `("non_eligible", "override")`.
- **`test_market_jobs.py` :**
  - `stock.eligibility = "a_verifier"` → `stock.envelope("pea").status = "a_verifier"` ;
  - `stock.eligibility_override = "eligible"` → `set_envelope_override(stock, "pea", "eligible", None)` ;
  - lectures via `envelope_status("pea")` ;
  - la source attendue `"override"` devient `"manual"` ;
  - **remplacer** `test_history_skips_non_eligible` par `test_history_follows_every_active_security` : le titre `US.PA` non éligible **figure** dans `market.history_calls`, et un titre `active=False` n'y figure pas ;
  - à la ligne 32, le titre `excluded` du test des cotations est désormais suivi : inverser l'assertion correspondante.
- **`test_api_favorites_eligibility.py` :**
  - source `"override"` → `"manual"` ;
  - ajouter `admin_client.patch(..., json={"override": "a_verifier"})` → 200, et `body["eligibility"] == "a_verifier"` ;
  - le cas 422 (`"peut-être"`) reste.
- **`test_api_seo.py` :** le titre `XX.PA` non éligible **figure** désormais dans le sitemap. Renommer `test_sitemap_lists_public_pages_and_eligible_securities` en `test_sitemap_lists_public_pages_and_all_active_securities`, puis inverser l'assertion, ici et dans le second test (ligne 68).
- **`test_api_securities.py:65` :** le filtre `eligibility=non_eligible` reste valable, inchangé.

- [ ] **Step 9: Run tests to verify they pass**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: PASS (toute la suite)

- [ ] **Step 10: Commit**

```bash
git add backend
git commit -m "feat: store envelope statuses per security and track quotes for every security"
```

---

### Task 3: Données PEA-PME (effectif et chiffre d'affaires Yahoo)

**Files:**
- Modify: `backend/app/providers/base.py:53-66`, `backend/app/providers/yahoo.py:118-135`, `backend/app/repositories/market_data.py` (`upsert_fundamentals`)
- Modify: `backend/app/schemas/security_detail.py` (`FundamentalsOut` : `employees`, `revenue`, `revenue_currency`)
- Modify: `backend/tests/fakes.py` ou le helper `fundamentals()` de `test_market_jobs.py` (nouveaux champs avec défaut `None`)
- Test: `backend/tests/test_yahoo.py`, `backend/tests/test_market_jobs.py`

**Interfaces:**
- Consumes: `refresh_envelopes`, `update_classification(…, fundamentals)` (tâche 2), colonnes `SecurityFundamentals.employees/revenue/revenue_currency`.
- Produces: `Fundamentals.employees: int | None`, `Fundamentals.revenue: float | None`, `Fundamentals.revenue_currency: str | None` (dataclass, défauts `None`, en fin de dataclass).

- [ ] **Step 1: Write the failing tests**

Dans `backend/tests/test_yahoo.py` :

```python
def test_fundamentals_read_size_for_pea_pme():
    f = fundamentals_from_info({"fullTimeEmployees": 1234, "totalRevenue": 2.5e8, "financialCurrency": "USD",
                                "currency": "EUR", "marketCap": 4e8})
    assert (f.employees, f.revenue, f.revenue_currency, f.currency) == (1234, 2.5e8, "USD", "EUR")


def test_fundamentals_size_missing_or_garbage():
    f = fundamentals_from_info({"fullTimeEmployees": "n/a", "totalRevenue": None})
    assert (f.employees, f.revenue, f.revenue_currency) == (None, None, None)
```

(importer `fundamentals_from_info` depuis `app.providers.yahoo` s'il ne l'est pas déjà.)

Dans `backend/tests/test_market_jobs.py` :

```python
def test_fundamentals_compute_pea_pme(db, make_ctx):
    small = make_security(db, "ALCAR.PA")
    big = make_security(db, "MC.PA")
    market = FakeMarket(fundamentals={
        "ALCAR.PA": fundamentals(employees=800, revenue=9e7, revenue_currency="EUR", market_cap=3e8),
        "MC.PA": fundamentals(employees=200_000, revenue=8e10, revenue_currency="EUR", market_cap=3e11),
    })
    refresh_fundamentals(make_ctx(market=market, now=NOW))
    assert db.get(Security, small.id).eligible_envelopes == ["pea", "pea_pme"]
    assert db.get(Security, big.id).envelope_status("pea_pme") == "non_eligible"
    assert db.get(SecurityFundamentals, small.id).employees == 800


def test_partial_fundamentals_keep_known_size_and_never_drop_pea(db, make_ctx):
    stock = make_security(db, "ALCAR.PA")
    full = FakeMarket(fundamentals={"ALCAR.PA": fundamentals(employees=800, revenue=9e7, revenue_currency="EUR", market_cap=3e8)})
    refresh_fundamentals(make_ctx(market=full, now=NOW))
    partial = FakeMarket(fundamentals={"ALCAR.PA": fundamentals(employees=None, revenue=None, revenue_currency=None, market_cap=3e8)})
    refresh_fundamentals(make_ctx(market=partial, now=NOW))
    stored = db.get(SecurityFundamentals, stock.id)
    assert (stored.employees, stored.revenue) == (800, 9e7)  # une réponse incomplète n'efface pas une valeur connue
    refreshed = db.get(Security, stock.id)
    assert refreshed.eligible_envelopes == ["pea", "pea_pme"]


def test_unknown_size_is_to_check_for_pea_pme(db, make_ctx):
    stock = make_security(db, "ALNEW.PA")
    market = FakeMarket(fundamentals={"ALNEW.PA": fundamentals(employees=None, revenue=None, revenue_currency=None)})
    refresh_fundamentals(make_ctx(market=market, now=NOW))
    refreshed = db.get(Security, stock.id)
    assert (refreshed.envelope_status("pea"), refreshed.envelope_status("pea_pme")) == ("eligible", "a_verifier")
```

Le helper `fundamentals(...)` de `test_market_jobs.py` reçoit trois nouveaux paramètres, tous de défaut `None` : `employees`, `revenue` et `revenue_currency`. Il les transmet au `Fundamentals(...)` qu'il construit. Si le helper fixe `market_cap` en dur, l'exposer aussi comme paramètre.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_yahoo.py tests/test_market_jobs.py`
Expected: FAIL (`AttributeError: 'Fundamentals' object has no attribute 'employees'`)

- [ ] **Step 3: Implementation**

`providers/base.py`, en fin de `Fundamentals` :

```python
    employees: int | None = None
    revenue: float | None = None  # chiffre d'affaires annuel, en `revenue_currency`
    revenue_currency: str | None = None
```

`providers/yahoo.py`, dans `fundamentals_from_info`, avec `_int` (déjà défini dans le fichier ; s'il n'accepte pas une chaîne invalide, utiliser `_num` puis `int()`) :

```python
        employees=_int(info.get("fullTimeEmployees")),
        revenue=_num(info.get("totalRevenue")),
        revenue_currency=info.get("financialCurrency") or None,
```

Avant de l'utiliser, vérifier le comportement de `_int` sur `"n/a"`. S'il lève une exception, écrire plutôt :

```python
def _count(value: Any) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None
```

`repositories/market_data.py`, dans `upsert_fundamentals`, ajouter à la fin, avant `record.updated_at` :

```python
    # Effectif et CA bougent peu : une réponse Yahoo qui ne les donne pas ne doit pas effacer la valeur connue.
    record.employees = f.employees if f.employees is not None else record.employees
    if f.revenue is not None:
        record.revenue, record.revenue_currency = f.revenue, f.revenue_currency or f.currency
```

`schemas/security_detail.py`, dans `FundamentalsOut`, après `market_cap` :

```python
    employees: int | None
    revenue: float | None
    revenue_currency: str | None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_yahoo.py tests/test_yahoo_ondemand.py tests/test_market_jobs.py tests/test_api_security_detail.py tests/test_envelope_storage.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: employees and revenue from Yahoo for the PEA-PME rule"
```

---

### Task 4: Enveloppes de l'utilisateur, top 10, classements, mails, assistant

**Files:**
- Create: `backend/app/repositories/user_envelopes.py`
- Modify:
  - `backend/app/schemas/settings.py` ;
  - `backend/app/api/routes/settings.py` ;
  - `backend/app/repositories/screener.py` ;
  - `backend/app/api/routes/rankings.py` ;
  - `backend/app/jobs/scoring.py:95-98` ;
  - `backend/app/repositories/scores.py` (`top_security_ids`) ;
  - `backend/app/jobs/tiers.py` ;
  - `backend/app/services/notifications/scores.py` ;
  - `backend/app/services/notifications/recaps.py:54-80` ;
  - `backend/app/services/assistant/prompt.py` ;
  - `backend/app/services/assistant/tools.py:36,41,48` ;
  - `backend/app/api/routes/assistant.py:113`.
- Test: `backend/tests/test_api_envelopes.py` (nouveau) ; adapter `test_scoring_job.py`, `test_lot2_review_fixes.py`, `test_notify_scores.py`, `test_api_screener.py`, `test_assistant_chat.py` (si elle vérifie le prompt)

**Interfaces:**
- Consumes: `envelope_clause(codes)` (tâche 2), `filtering_envelopes` (tâche 1), `UserSettings.envelopes`, `ScoreSnapshot.top_pool`.
- Produces :
  - `user_envelopes(session, user_id: uuid.UUID | None) -> list[str]` (codes choisis, sans créer de ligne de réglages ; `[]` pour un visiteur) ;
  - routes `GET /api/settings/envelopes` et `PUT /api/settings/envelopes` → `EnvelopesOut {envelopes: list[str]}` ;
  - `screener_rows(..., envelopes: Sequence[str] = ())` ;
  - `top_security_ids(session, limit, envelopes=())` ;
  - `user_top_ids(db, rows: dict[int, ScoreSnapshot], envelopes, size=10) -> set[int]` ;
  - `score_changes(before, after, ids, top_before: set[int], top_after: set[int])` ;
  - `system_prompt(today, min_orders, envelopes, security)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_api_envelopes.py` :

```python
from app.models import UserSettings
from app.repositories.user_envelopes import user_envelopes
from tests.factories import make_score, make_security


def _choose(db, user, envelopes):
    db.merge(UserSettings(user_id=user.id, envelopes=envelopes))
    db.flush()


def test_envelopes_default_to_empty_and_are_saved(client, db, user):
    assert client.get("/api/settings/envelopes").json() == {"envelopes": []}
    body = client.put("/api/settings/envelopes", json={"envelopes": ["pea_pme", "pea", "pea"]}).json()
    assert body == {"envelopes": ["pea", "pea_pme"]}  # dédoublonné, dans l'ordre du registre
    assert user_envelopes(db, user.id) == ["pea", "pea_pme"]
    assert client.get("/api/settings/envelopes").json() == {"envelopes": ["pea", "pea_pme"]}


def test_envelopes_reject_unknown_codes(client, user):
    assert client.put("/api/settings/envelopes", json={"envelopes": ["livret_a"]}).status_code == 422


def test_envelopes_need_an_account(anon_client):
    assert anon_client.get("/api/settings/envelopes").status_code == 401


def test_saving_fees_keeps_envelopes(client, db, user):
    client.put("/api/settings/envelopes", json={"envelopes": ["pea"]})
    client.put("/api/settings", json={"min_orders_per_year": 10, "penalty_fee": 50, "fee_grid": [{"up_to": None, "rate": 0.001}]})
    assert user_envelopes(db, user.id) == ["pea"]


def _top_universe(db):
    foreign = make_security(db, "AAPL.PA", name="Apple", eligibility="non_eligible", country="US")
    pea = make_security(db, "MC.PA", name="LVMH")
    pme = make_security(db, "ALCAR.PA", name="Carmat", pea_pme="eligible")
    unsure = make_security(db, "GFC.PA", name="Gecina", eligibility="a_verifier")
    for security, total in ((foreign, 95), (pea, 90), (pme, 80), (unsure, 70)):
        make_score(db, security, total=total)
    return foreign, pea, pme, unsure


def _top_names(client):
    return [item["name"] for item in client.get("/api/rankings/top").json()]


def test_visitor_sees_every_security_in_the_top(anon_client, db):
    _top_universe(db)
    assert _top_names(anon_client) == ["Apple", "LVMH", "Carmat", "Gecina"]


def test_top_follows_the_user_envelopes(client, db, user):
    _top_universe(db)
    assert _top_names(client) == ["Apple", "LVMH", "Carmat", "Gecina"]  # rien de choisi : tout
    _choose(db, user, ["pea"])
    assert _top_names(client) == ["LVMH", "Carmat"]  # « à vérifier » exclu
    _choose(db, user, ["pea_pme"])
    assert _top_names(client) == ["Carmat"]
    _choose(db, user, ["pea", "cto"])
    assert _top_names(client) == ["Apple", "LVMH", "Carmat", "Gecina"]  # le compte-titres accepte tout


def test_manual_correction_leaves_the_pea_top_at_once(client, db, user, admin_client):
    _, pea, _, _ = _top_universe(db)
    _choose(db, user, ["pea"])
    admin_client.patch(f"/api/securities/{pea.id}/eligibility", json={"override": "non_eligible"})
    assert "LVMH" not in _top_names(client)


def test_movers_and_heatmap_follow_the_envelopes(client, db, user):
    from tests.factories import make_quote
    foreign, pea, _, _ = _top_universe(db)
    make_quote(db, foreign, change_pct=5.0)
    make_quote(db, pea, change_pct=-2.0)
    _choose(db, user, ["pea"])
    movers = client.get("/api/rankings/movers").json()
    assert [m["name"] for m in movers["gainers"] + movers["losers"]] == ["LVMH", "LVMH"]
```

Avant d'écrire ce test :
- **Fixtures :** vérifier dans `tests/conftest.py` le nom des fixtures de client connecté (`client` + `user`, `admin_client`, `anon_client`) et la signature de `make_quote`, puis ajuster les appels.
- **Comptes distincts :** dans `test_manual_correction_leaves_the_pea_top_at_once`, si `admin_client` et `client` partagent le même cookie, faire la correction directement avec `set_envelope_override(pea, "pea", "non_eligible", None)` suivi de `db.flush()`.

Dans `backend/tests/test_scoring_job.py`, ajouter :

```python
def test_non_pea_stock_can_enter_the_top(db, make_ctx):
    # même préparation que le test « liquid stock enters the top » du fichier, avec un titre US
    ...
```

Ce test copie la préparation du premier test du fichier qui vérifie `score.eligible_for_top is True` (lignes ~30-46). La seule différence est le titre : `make_security(db, "AAPL.PA", eligibility="non_eligible", country="US")`. Il vérifie que `db.get(SecurityScore, aapl.id).eligible_for_top is True`. Pour ne pas dupliquer, extraire la préparation dans un helper local `_liquid_history(db, security)` utilisé par les deux tests.

Dans `backend/tests/test_lot2_review_fixes.py`, les deux tests `test_non_eligible_security_leaves_top` et suivant vérifiaient que le top excluait un titre non PEA :
- le premier devient `test_pea_user_does_not_see_a_non_pea_security_in_the_top`, avec `_choose(db, user, ["pea"])` avant l'appel ;
- le second (`stale.eligible_for_top is False` pour un titre non éligible) devient : un titre **inactif** perd `eligible_for_top`. Remplacer `eligibility="non_eligible"` par `active=False`.

Dans `backend/tests/test_notify_scores.py`, ajouter :

```python
def test_weekly_recap_uses_the_user_top(db, user):
    save_prefs(db, user.id, {"weekly_recap": True})
    db.merge(UserSettings(user_id=user.id, envelopes=["pea"]))
    foreign = make_security(db, "AAPL.PA", name="Apple", eligibility="non_eligible", country="US")
    pea = make_security(db, "MC.PA", name="LVMH")
    make_score(db, foreign, total=95.0)
    make_score(db, pea, total=50.0, eligible_for_top=False)
    take_score_snapshot(db, date(2026, 9, 25))  # avant la fenêtre de 6 jours du récap : c'est la photo « avant »
    _set_total(db, pea, 60.0, top=True)
    take_score_snapshot(db, date(2026, 10, 2))
    send_weekly_recaps(db, datetime(2026, 10, 3, 7, 0, tzinfo=UTC))
    context = _mails(db, "weekly_recap")[0].context
    assert [i["name"] for i in context["entered"]] == ["LVMH"]  # Apple, hors PEA, n'est pas dans son top
    assert context["left"] == []
```

Avant d'écrire ce test :
- **Contexte du mail :** vérifier comment `EmailLog` expose le contexte du mail (champ `context` ou autre) dans un test existant du fichier, et s'aligner.
- **Imports :** importer `UserSettings` et `send_weekly_recaps` s'ils ne le sont pas déjà.
- **Snapshot :** le test existant `test_snapshot_keeps_totals_and_top_ranks` vérifie en plus `rows[a.id].top_pool is True and rows[b.id].top_pool is False`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_envelopes.py tests/test_scoring_job.py tests/test_notify_scores.py tests/test_lot2_review_fixes.py`
Expected: FAIL (404 sur `/api/settings/envelopes`, `ModuleNotFoundError: app.repositories.user_envelopes`)

- [ ] **Step 3: Réglages**

`backend/app/repositories/user_envelopes.py` :

```python
import uuid

from sqlalchemy.orm import Session

from app.models import UserSettings
from app.services.envelopes.rules import ENVELOPES


def user_envelopes(session: Session, user_id: uuid.UUID | None) -> list[str]:
    """Enveloppes choisies (ordre du registre) ; [] pour un visiteur ou un compte sans réglages. Ne crée aucune ligne."""
    if user_id is None:
        return []
    settings = session.get(UserSettings, user_id)
    chosen = set(settings.envelopes or []) if settings else set()
    return [code for code in ENVELOPES if code in chosen]
```

`backend/app/schemas/settings.py`, ajouter :

```python
from typing import Literal

EnvelopeCode = Literal["pea", "pea_pme", "cto"]


class EnvelopesIn(BaseModel):
    envelopes: list[EnvelopeCode] = Field(max_length=10)


class EnvelopesOut(BaseModel):
    envelopes: list[str]
```

`backend/app/api/routes/settings.py`, ajouter :

```python
@router.get("/settings/envelopes", response_model=EnvelopesOut)
def read_envelopes(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> EnvelopesOut:
    return EnvelopesOut(envelopes=user_envelopes(db, user.id))


@router.put("/settings/envelopes", response_model=EnvelopesOut)
def update_envelopes(payload: EnvelopesIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> EnvelopesOut:
    settings = get_user_settings(db, user.id)
    settings.envelopes = [code for code in ENVELOPES if code in set(payload.envelopes)]
    db.commit()
    return EnvelopesOut(envelopes=user_envelopes(db, user.id))
```

Ces deux routes doivent être déclarées **avant** toute route `/settings/{…}` éventuelle. Vérifier aussi `PRIVATE_API_PATHS` dans `seo.py` : `/api/settings` y figure-t-il déjà ? Sinon, rien à faire, la route exige un compte.

- [ ] **Step 4: Top, classements, score**

`repositories/screener.py` :
- ajouter le paramètre `envelopes: Sequence[str] = ()` ;
- appliquer le filtre dans **tous** les cas sauf `security_id` (une fiche s'affiche toujours).

```python
    if security_id is not None:
        stmt = stmt.where(Security.id == security_id)
    else:
        stmt = stmt.where(Security.kind == kind) if kind else stmt.where(Security.kind != "index")
        clause = envelope_clause(envelopes)
        if clause is not None:
            stmt = stmt.where(clause)
    if only_top:
        stmt = stmt.where(SecurityScore.eligible_for_top.is_(True), Security.kind == "stock").order_by(
            SecurityScore.total.desc(), SecurityScore.avg_turnover_eur.desc())
```

L'appel de l'Explorer (`/api/screener`) ne passe pas d'enveloppes : l'Explorer montre tout et filtre côté navigateur.

`api/routes/rankings.py` :

```python
def _liquid_stocks(db: Session, user: User | None) -> list:
    envelopes = user_envelopes(db, user.id if user else None)
    return [
        row for row in screener_rows(db, user.id if user else None, kind="stock", envelopes=envelopes)
        if row[2] is not None and row[2].liquid and row[1] is not None and row[1].change_pct is not None
    ]
```

Le reste du fichier :
- `get_movers` et `get_heatmap` appellent `_liquid_stocks(db, user)`.
- `get_top` passe `envelopes=user_envelopes(db, user.id if user else None)` à `screener_rows`.

`jobs/scoring.py:95-98` :

```python
            eligible_for_top = (
                s.kind == "stock" and liquid
                and len(bars) >= settings.min_history_days
                and result.total is not None and result.available_ratio >= settings.min_available_ratio
            )
```

Le commentaire de la ligne 118 devient : « Titres sortis du périmètre (inactifs, devenus indices) : ils ne peuvent plus figurer dans le top. »

`repositories/scores.py` :

```python
def top_security_ids(session: Session, limit: int, envelopes: Sequence[str] = ()) -> list[int]:
    stmt = (
        select(SecurityScore.security_id)
        .join(Security, Security.id == SecurityScore.security_id)
        .where(SecurityScore.eligible_for_top.is_(True), Security.active.is_(True))
        .order_by(SecurityScore.total.desc(), SecurityScore.avg_turnover_eur.desc())
        .limit(limit)
    )
    clause = envelope_clause(envelopes)
    return list(session.scalars(stmt.where(clause) if clause is not None else stmt))
```

`jobs/tiers.py` : le T1 contient le top 10 de chaque façon de filtrer (tout, PEA, PEA-PME).

```python
TOP_SCOPES: tuple[tuple[str, ...], ...] = ((), ("pea",), ("pea_pme",))
...
        | {sid for scope in TOP_SCOPES for sid in top_security_ids(session, TOP_IN_T1, scope)}
```

- [ ] **Step 5: Mails (top 10 de l'utilisateur)**

`services/notifications/scores.py` :

```python
def take_score_snapshot(db: Session, day: date) -> None:
    db.execute(delete(ScoreSnapshot).where(ScoreSnapshot.day == day))
    ranks = {sid: rank for rank, sid in enumerate(top_security_ids(db, TOP_SIZE), start=1)}
    for sid, total, pool in db.execute(select(SecurityScore.security_id, SecurityScore.total, SecurityScore.eligible_for_top)
                                       .where(SecurityScore.total.is_not(None))):
        db.add(ScoreSnapshot(day=day, security_id=sid, total=total, top_rank=ranks.get(sid), top_pool=pool))
    db.flush()


def user_top_ids(db: Session, rows: dict[int, ScoreSnapshot], envelopes: Sequence[str], size: int = TOP_SIZE) -> set[int]:
    """Top 10 d'un membre ce jour-là : candidats du soir, filtrés par ses enveloppes (statut actuel), meilleurs scores."""
    candidates = [row for row in rows.values() if row.top_pool]
    clause = envelope_clause(envelopes)
    if clause is not None:
        allowed = set(db.scalars(select(Security.id).where(Security.id.in_([r.security_id for r in candidates]), clause)))
        candidates = [row for row in candidates if row.security_id in allowed]
    return {row.security_id for row in sorted(candidates, key=lambda r: -r.total)[:size]}


def score_changes(before: dict[int, ScoreSnapshot], after: dict[int, ScoreSnapshot], ids: set[int],
                  top_before: set[int], top_after: set[int]) -> list[dict]:
    items = []
    for sid in sorted(ids):
        old, new = before.get(sid), after.get(sid)
        if old is None or new is None:
            continue
        if sid in top_after and sid not in top_before:
            change = "entered"
        elif sid in top_before and sid not in top_after:
            change = "left"
        elif abs(new.total - old.total) >= BIG_MOVE:
            change = "up" if new.total > old.total else "down"
        else:
            continue
        items.append({"security_id": sid, "before": round(old.total), "after": round(new.total), "change": change})
    return items
```

Dans `notify_score_changes`, pour chaque destinataire :

```python
        envelopes = user_envelopes(db, user.id)
        items = score_changes(before, after, favorites, user_top_ids(db, before, envelopes), user_top_ids(db, after, envelopes))
```

`services/notifications/recaps.py` : supprimer le calcul global de `top_now`, `top_before`, `entered` et `left` avant la boucle. Garder `latest`, `start` et les deux photos, puis calculer dans la boucle pour chaque membre :

```python
    after = snapshot(db, latest) if latest else {}
    before = snapshot(db, start) if start else after
    ...
    for user, _ in recipients(db, "weekly_recap"):
        envelopes = user_envelopes(db, user.id)
        top_now, top_before = user_top_ids(db, after, envelopes), user_top_ids(db, before, envelopes)
        entered, left = _names(db, top_now - top_before), _names(db, top_before - top_now)
```

Le `top_rank` stocké reste le rang dans le top global, en informatif. Les mails n'utilisent plus que `top_pool`.

- [ ] **Step 6: Assistant**

`services/assistant/prompt.py` :
- retirer la règle « Enveloppes : ne suppose pas… » de `BASE` ;
- garder la phrase sur les frais (« Les frais de courtage suivent la grille de l'utilisateur ; son courtier lui facture des frais s'il passe moins de {min_orders} ordres par an. ») comme règle à part : « - Frais : … ».

Puis :

```python
from app.services.envelopes.rules import ENVELOPES, filtering_envelopes


def _envelopes_rule(envelopes: list[str]) -> str:
    if not filtering_envelopes(envelopes):
        return ("\n- Enveloppes : l'utilisateur n'a pas restreint ses enveloppes ; ne suppose pas qu'il investit via un PEA. "
                "Si l'enveloppe compte pour la réponse, demande-la ou présente les cas (PEA, PEA-PME, compte-titres).")
    names = ", ".join(ENVELOPES[code] for code in envelopes)
    return (f"\n- Enveloppes : l'utilisateur investit via : {names}. Le top 10 que tu reçois est déjà filtré sur ces enveloppes. "
            "L'éligibilité d'un titre est déduite automatiquement : invite-le à la confirmer auprès de son courtier.")


def system_prompt(today: date, min_orders: int, envelopes: list[str], security: Security | None) -> str:
    text = BASE.format(today=today.strftime("%d/%m/%Y"), min_orders=min_orders) + _envelopes_rule(envelopes)
    ...
```

La règle des enveloppes s'ajoute **après** la liste des règles de `BASE`. Si `BASE` se termine par la règle « Quand tu utilises un outil… », l'insérer avant elle en découpant `BASE` en deux constantes. Dans tous les cas, la phrase doit rester dans la liste « Règles : ».

`api/routes/assistant.py:113` : `system=system_prompt(paris_today(), row.min_orders_per_year, row.envelopes or [], security),`. Ici `row` est le `UserSettings` déjà chargé ; vérifier son nom quelques lignes plus haut.

`services/assistant/tools.py` :
- l. 36 : « … variation du jour et enveloppes compatibles (PEA, PEA-PME). » ;
- l. 41 : « … fondamentaux, enveloppes compatibles. » ;
- l. 48 : « Top 10 actuel de l'application (actions les mieux notées, filtrées sur les enveloppes de l'utilisateur) avec les 3 principales raisons de chaque score. »

Tests :
- **`test_assistant_chat.py` :** si un test y appelle `system_prompt(...)` directement, ajouter l'argument `[]`.
- **Prompt (`tests/test_assistant_tools.py` ou le fichier de test du prompt) :** ajouter le test suivant.

```python
def test_prompt_mentions_the_chosen_envelopes():
    assert "PEA, PEA-PME" in system_prompt(date(2026, 10, 2), 12, ["pea", "pea_pme"], None)
    assert "ne suppose pas qu'il investit via un PEA" in system_prompt(date(2026, 10, 2), 12, ["cto"], None)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: PASS (toute la suite)

- [ ] **Step 8: Commit**

```bash
git add backend
git commit -m "feat: per-user envelopes drive the top 10, rankings, recaps and assistant"
```

---

### Task 5: API publique par enveloppe (champs, filtre, correction admin)

**Files:**
- Modify:
  - `backend/app/schemas/screener.py` : `eligibility` → `envelopes`.
  - `backend/app/schemas/security_detail.py` : retirer `eligibility_source`.
  - `backend/app/api/routes/security_detail.py:56`.
  - `backend/app/schemas/forecasts.py:24`.
  - `backend/app/api/routes/forecasts.py:58`.
  - `backend/app/schemas/securities.py`.
  - `backend/app/api/routes/securities.py`.
  - `backend/app/repositories/securities.py` (`search_securities`).
  - `backend/app/api/routes/status.py:17`.
  - `backend/app/services/assistant/tools.py:86-88`.
- Test: adapter `test_api_securities.py`, `test_api_favorites_eligibility.py` (renommé `test_api_favorites_envelopes.py`), `test_api_access.py`, `test_api_forecasts.py`, `test_api_screener.py`, `test_api_security_detail.py`, `test_lot2_review_fixes.py:87-89`, `test_api_envelopes.py`

**Interfaces:**
- Consumes: `Security.eligible_envelopes`, `set_envelope_override` (tâche 2).
- Produces (contrat utilisé par le frontend, tâches 6-7) :
  - `ScreenerRow.envelopes: list[str]` : codes **éligibles**, par exemple `["pea", "pea_pme"]`. Le champ `eligibility` disparaît. `SecurityDetail` et `TopItem` en héritent.
  - `ForecastSecurityOut.envelopes: list[str]` : remplace `eligibility`.
  - `SecurityItem.envelopes: list[EnvelopeStatusOut]`, avec `EnvelopeStatusOut {code, status, source, override}`, une entrée par enveloppe à règle. Les champs `eligibility`, `eligibility_source` et `eligibility_override` disparaissent.
  - `GET /api/securities?envelope=pea|pea_pme&overridden=true` : le paramètre `eligibility` disparaît.
  - `PATCH /api/securities/{id}/envelopes/{code}`, avec `code ∈ {pea, pea_pme}` et le corps `{"override": "eligible"|"a_verifier"|"non_eligible"|null}` → `SecurityItem`. L'ancienne route `PATCH /api/securities/{id}/eligibility` est supprimée.

- [ ] **Step 1: Write the failing tests**

Renommer `backend/tests/test_api_favorites_eligibility.py` en `backend/tests/test_api_favorites_envelopes.py` (`git mv`). Y remplacer les tests d'éligibilité par :

```python
def _pea(body):
    return next(e for e in body["envelopes"] if e["code"] == "pea")


def test_override_and_reset_an_envelope(admin_client, db):
    security = make_security(db, "GFC.PA", eligibility="a_verifier")
    body = admin_client.patch(f"/api/securities/{security.id}/envelopes/pea", json={"override": "eligible"}).json()
    assert _pea(body) == {"code": "pea", "status": "eligible", "source": "manual", "override": "eligible"}
    body = admin_client.patch(f"/api/securities/{security.id}/envelopes/pea", json={"override": None}).json()
    assert _pea(body)["source"] == "auto" and _pea(body)["override"] is None
    assert [e["code"] for e in body["envelopes"]] == ["pea", "pea_pme"]


def test_pea_pme_can_be_corrected_on_its_own(admin_client, db):
    security = make_security(db, "ALCAR.PA")
    body = admin_client.patch(f"/api/securities/{security.id}/envelopes/pea_pme", json={"override": "eligible"}).json()
    assert {e["code"]: e["status"] for e in body["envelopes"]} == {"pea": "eligible", "pea_pme": "eligible"}


def test_envelope_override_validation(admin_client, db):
    security = make_security(db, "GFC.PA")
    assert admin_client.patch(f"/api/securities/{security.id}/envelopes/pea", json={"override": "peut-être"}).status_code == 422
    assert admin_client.patch(f"/api/securities/{security.id}/envelopes/cto", json={"override": None}).status_code == 422
    assert admin_client.patch("/api/securities/999999/envelopes/pea", json={"override": None}).status_code == 404
    assert admin_client.patch(f"/api/securities/{security.id}/eligibility", json={"override": None}).status_code in (404, 405)
```

Les autres tests du fichier passent sur les nouvelles routes :
- le test d'ETF qui revient à `seed` (lignes 28-33) : `/envelopes/pea` et `_pea(body)["source"] == "seed"` ;
- le test de la ligne 45 : `/envelopes/pea`.

`backend/tests/test_api_screener.py` : ajouter

```python
def test_screener_rows_list_eligible_envelopes(client, db):
    make_security(db, "ALCAR.PA", name="Carmat", pea_pme="eligible")
    make_security(db, "AAPL.PA", name="Apple", eligibility="non_eligible", country="US")
    make_security(db, "GFC.PA", name="Gecina", eligibility="a_verifier")
    rows = {r["name"]: r for r in client.get("/api/screener").json()}
    assert rows["Carmat"]["envelopes"] == ["pea", "pea_pme"]
    assert rows["Apple"]["envelopes"] == [] and rows["Gecina"]["envelopes"] == []
    assert "eligibility" not in rows["Carmat"]
```

`backend/tests/test_api_securities.py:65` :

```python
    assert client.get("/api/securities", params={"envelope": "pea"}).json()["total"] == <nombre de titres non-indices éligibles PEA du jeu de données>
    assert client.get("/api/securities", params={"envelope": "livret"}).status_code == 422
```

Pour la première ligne, compter dans la fonction de préparation du fichier les titres non-indices dont le PEA est `eligible` (par défaut : tous sauf `MMM.PA` et l'indice), puis remplacer le texte entre chevrons par ce nombre.

Autres tests à adapter :
- **`test_api_access.py:17` :** `("PATCH", "/api/securities/1/envelopes/pea")`, et dans `test_eligibility_override_is_admin_only` (renommé `test_envelope_override_is_admin_only`), les deux URL passent à `/envelopes/pea`.
- **`test_lot2_review_fixes.py:89` :** `/envelopes/pea`.
- **`test_api_forecasts.py:77` :** `assert lvmh["security"]["envelopes"] == ["pea"]`.
- **`test_api_envelopes.py` :** l'appel `/eligibility` du test de correction passe à `/envelopes/pea`.
- **`test_api_security_detail.py` :** si un test lit `eligibility` ou `eligibility_source`, il lit désormais `envelopes == ["pea"]`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_favorites_envelopes.py tests/test_api_screener.py tests/test_api_securities.py`
Expected: FAIL (404 sur `/envelopes/pea`, `KeyError: 'envelopes'`)

- [ ] **Step 3: Implementation**

`schemas/screener.py` : le champ `eligibility: str` devient `envelopes: list[str]`, et `fields_from` utilise `envelopes=security.eligible_envelopes,`.

`schemas/security_detail.py` : retirer `eligibility_source: str` de `SecurityDetail`, puis retirer `eligibility_source=…` de l'appel dans `routes/security_detail.py`.

`schemas/forecasts.py:24` : `envelopes: list[str]`. Puis `routes/forecasts.py:58` : `envelopes=s.eligible_envelopes,`.

`schemas/securities.py` :

```python
from typing import Literal

from pydantic import BaseModel

from app.models import Security, SecurityQuote
from app.services.envelopes.rules import RULE_ENVELOPES, TO_CHECK


class EnvelopeStatusOut(BaseModel):
    code: str
    status: str
    source: str
    override: str | None


class SecurityItem(BaseModel):
    id: int
    yahoo_ticker: str
    symbol: str
    name: str
    kind: str
    market: str
    country: str | None
    sector: str | None
    envelopes: list[EnvelopeStatusOut]
    price: float | None
    change_pct: float | None
    as_of: datetime | None

    @classmethod
    def build(cls, security: Security, quote: SecurityQuote | None) -> "SecurityItem":
        envelopes = []
        for code in RULE_ENVELOPES:
            row = security.envelope(code)
            envelopes.append(EnvelopeStatusOut(code=code, status=row.status if row else TO_CHECK,
                                               source=row.source if row else "auto", override=row.override if row else None))
        return cls(
            id=security.id, yahoo_ticker=security.yahoo_ticker, symbol=security.symbol, name=security.name,
            kind=security.kind, market=security.market, country=security.country, sector=security.sector,
            envelopes=envelopes,
            price=quote.price if quote else None,
            change_pct=quote.change_pct if quote else None,
            as_of=quote.as_of if quote else None,
        )


class EnvelopeUpdate(BaseModel):
    override: Literal["eligible", "a_verifier", "non_eligible"] | None
```

(`EligibilityUpdate` disparaît ; garder l'import `datetime` et `SecurityList`.)

`repositories/securities.py`, dans `search_securities`, le paramètre `eligibility: str | None` devient `envelope: str | None` :

```python
    if envelope:
        stmt = stmt.where(exists().where(SecurityEnvelope.security_id == Security.id, SecurityEnvelope.envelope == envelope,
                                         SecurityEnvelope.status == ELIGIBLE))
```

(importer `ELIGIBLE` depuis `app.services.envelopes.rules`.)

Appelants à mettre à jour :
- `routes/status.py:17` : `envelope=None` ;
- `services/assistant/tools.py:86` : `envelope=None` ;
- `tools.py:88` : `"envelopes": s.eligible_envelopes,`.

`api/routes/securities.py` :

```python
@router.get("/securities", response_model=SecurityList)
def list_securities(
    q: str | None = Query(None, max_length=100),
    kind: Literal["stock", "etf", "index"] | None = None,
    envelope: Literal["pea", "pea_pme"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    overridden: bool = False,
    db: Session = Depends(get_db),
) -> SecurityList:
    rows, total = search_securities(db, q=q, kind=kind, envelope=envelope, limit=limit, offset=offset, overridden=overridden)
    return SecurityList(items=[SecurityItem.build(s, quote) for s, quote in rows], total=total)


@router.patch("/securities/{security_id}/envelopes/{code}", response_model=SecurityItem)
def update_envelope(
    security_id: int,
    code: Literal["pea", "pea_pme"],
    update: EnvelopeUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> SecurityItem:
    security = db.get(Security, security_id)
    if security is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    set_envelope_override(security, code, update.override, db.get(SecurityFundamentals, security_id))
    db.commit()
    return SecurityItem.build(security, db.get(SecurityQuote, security_id))
```

Supprimer l'ancienne route `update_eligibility`.

Vérifier ensuite que plus rien ne référence l'éligibilité :
`grep -rn "eligibility" backend/app` ne doit plus rien renvoyer, sauf `eligible_for_top` et les commentaires.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: PASS (toute la suite)

- [ ] **Step 5: Commit**

```bash
git add -A backend
git commit -m "feat: envelope fields, filter and admin correction route in the API"
```

---

### Task 6: Frontend — badges, Explorer, fiche, prévisions, carte admin

**Files:**
- Regenerate: `frontend/src/lib/api/schema.d.ts`
- Modify: `frontend/src/lib/api/client.ts` (types `EnvelopesOut`, `EnvelopeStatus`)
- Create: `frontend/src/lib/envelopes.ts`
- Create: `frontend/src/features/explorer/EnvelopeBadges.tsx`
- Delete: `frontend/src/features/explorer/EligibilityBadge.tsx`
- Create: `frontend/src/features/settings/useEnvelopes.ts`
- Modify:
  - `frontend/src/features/screener/filters.ts` ;
  - `frontend/src/features/screener/ScreenerFilters.tsx` ;
  - `frontend/src/features/screener/columns.tsx` ;
  - `frontend/src/features/security/SecurityPage.tsx` ;
  - `frontend/src/features/security/ScoreCard.tsx` ;
  - `frontend/src/features/forecasts/PredictionsView.tsx` ;
  - `frontend/src/app/Layout.tsx:34`.
- Create: `frontend/src/features/admin/EnvelopeOverridesCard.tsx` (+ `.test.tsx`)
- Delete: `frontend/src/features/admin/EligibilityOverridesCard.tsx`, `EligibilityOverridesCard.test.tsx`
- Modify: `frontend/src/features/admin/AdminPage.tsx`
- Test: `filters.test.ts`, `ScreenerPage.test.tsx`, `SecurityPage.test.tsx`, `ForecastsPage.test.tsx`, `HomePage.test.tsx` (fixtures `eligibility` → `envelopes`)

**Interfaces:**
- Consumes: contrat API de la tâche 5, `GET /api/settings/envelopes` (tâche 4).
- Produces :
  - **`lib/envelopes.ts` :**
    - `ENVELOPE_LABELS: Record<string, string>` ;
    - `RULE_ENVELOPES = ["pea", "pea_pme"] as const` ;
    - `STATUS_LABELS` ;
    - `filteringEnvelopes(codes: string[]): string[]` : vide si rien n'est choisi ou si `cto` est coché.
  - **`<EnvelopeBadges codes={string[]} />`.**
  - **`useEnvelopes()` :** renvoie `{ chosen: string[]; filtering: string[]; isPending: boolean }`. Il n'appelle l'API que pour un compte connecté.

- [ ] **Step 1: Regenerate API types**

Run (API de dev démarrée sur la branche) :
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build db api
cd frontend && npm run gen:api
```

Puis, dans `frontend/src/lib/api/client.ts`, à côté de `SettingsOut` :

```ts
export type EnvelopesOut = components["schemas"]["EnvelopesOut"];
export type EnvelopeStatus = components["schemas"]["EnvelopeStatusOut"];
```

`npx tsc -b` échoue alors sur les usages de `eligibility` : c'est attendu, et les étapes suivantes les corrigent.

- [ ] **Step 2: Write the failing tests**

`frontend/src/features/screener/filters.test.ts` :
- dans la fixture `row`, remplacer `eligibility: "eligible"` par `envelopes: ["pea"]` ;
- remplacer les deux assertions des lignes 43-46 par :

```ts
  const rows = [row({ isin: "FR0000121014", envelopes: ["pea", "pea_pme"] }),
                row({ id: 9, symbol: "X", name: "Étrangère", isin: null, envelopes: [] }),
                row({ id: 10, symbol: "Y", name: "Grande", isin: null, envelopes: ["pea"] })];
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("envelope=pea"))).map((r) => r.id)).toEqual([1, 10]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("envelope=pea_pme"))).map((r) => r.id)).toEqual([1]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("eligibility=non_eligible"))).map((r) => r.id)).toEqual([1, 9, 10]); // ancien lien : ignoré
```

`frontend/src/lib/envelopes.test.ts` (nouveau) :

```ts
import { filteringEnvelopes } from "./envelopes";

test("le compte-titres ou l'absence de choix veut dire tous les titres", () => {
  expect(filteringEnvelopes([])).toEqual([]);
  expect(filteringEnvelopes(["pea", "cto"])).toEqual([]);
  expect(filteringEnvelopes(["pea_pme", "pea"])).toEqual(["pea", "pea_pme"]);
});
```

Dans `frontend/src/features/screener/ScreenerPage.test.tsx`, remplacer `eligibility: "eligible"` par `envelopes: ["pea"]` dans la fixture, puis ajouter :

```tsx
test("le filtre Enveloppe propose Toutes, PEA et PEA-PME, sans « à vérifier »", async () => {
  // même rendu que le premier test du fichier
  const select = await screen.findByRole("combobox", { name: "Enveloppe" });
  expect([...select.querySelectorAll("option")].map((o) => o.textContent)).toEqual(["Enveloppe : toutes", "PEA", "PEA-PME"]);
});
```

Pour le rendu, reprendre le `renderWithProviders(...)` et le `mockFetch` du premier test du fichier ; le commentaire ci-dessus est à remplacer par ce code.

`frontend/src/features/security/SecurityPage.test.tsx` :
- dans la fixture, remplacer `eligibility: "eligible", eligibility_source: "auto"` par `envelopes: ["pea", "pea_pme"]` ;
- ajouter les assertions suivantes au test principal :

```tsx
  expect(screen.getByText("PEA")).toBeInTheDocument();
  expect(screen.getByText("PEA-PME")).toBeInTheDocument();
  expect(screen.getByText(/déduites automatiquement/)).toBeInTheDocument();
  expect(screen.queryByText(/Éligible PEA/)).not.toBeInTheDocument();
```

`frontend/src/features/forecasts/ForecastsPage.test.tsx` : le troisième paramètre de la fixture `security(id, name, eligibility)` devient `envelopes: string[] = ["pea"]`, et l'appel « Étranger » passe `[]`. Ajouter à `mockFetch` :

```ts
    if (url === "/api/me") return { body: PREMIUM_ME };
    if (url === "/api/settings/envelopes") return { body: { envelopes: chosen } };
```

`chosen` est une variable du test (`let chosen: string[] = ["pea"]`). Le test existant qui décochait « Éligibles PEA uniquement » devient :

```tsx
test("« Mes enveloppes uniquement » est coché par défaut quand l'utilisateur en a choisi", async () => {
  chosen = ["pea"];
  // rendu de la page des prévisions comme dans le test existant
  const box = await screen.findByRole("checkbox", { name: "Mes enveloppes uniquement" });
  expect(box).toBeChecked();
  expect(screen.queryByText("Étranger")).not.toBeInTheDocument();
  await userEvent.click(box);
  expect(await screen.findByText("Étranger")).toBeInTheDocument();
});

test("sans enveloppe choisie, pas de case et tous les titres", async () => {
  chosen = [];
  // même rendu
  expect(await screen.findByText("Étranger")).toBeInTheDocument();
  expect(screen.queryByRole("checkbox", { name: "Mes enveloppes uniquement" })).not.toBeInTheDocument();
});
```

Dans ces deux tests, les commentaires de rendu sont à remplacer par le rendu du test existant qu'ils remplacent.

`frontend/src/features/home/HomePage.test.tsx` : la fixture `eligibility: "eligible"` devient `envelopes: ["pea"]`.

`frontend/src/features/admin/EnvelopeOverridesCard.test.tsx` :

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { EnvelopeOverridesCard } from "./EnvelopeOverridesCard";

afterEach(() => vi.unstubAllGlobals());

const envelopes = (pea: string, peaPme: string, override: string | null = null) => [
  { code: "pea", status: pea, source: override ? "manual" : "auto", override },
  { code: "pea_pme", status: peaPme, source: "auto", override: null },
];
const GECINA = { id: 4, yahoo_ticker: "GFC.PA", symbol: "GFC", name: "Gecina", kind: "stock", market: "Euronext Paris",
  country: "FR", sector: "Real Estate", envelopes: envelopes("a_verifier", "a_verifier"), price: 90, change_pct: 0, as_of: null };

test("choisit l'enveloppe puis corrige le statut d'un titre", async () => {
  const fetchMock = mockFetch((url) => {
    if (url.includes("overridden=true")) return { body: { items: [], total: 0 } };
    if (url.includes("/envelopes/")) return { body: { ...GECINA, envelopes: envelopes("a_verifier", "eligible") } };
    return { body: { items: [GECINA], total: 1 } };
  });
  renderWithProviders(<EnvelopeOverridesCard />);
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Enveloppe à corriger" }), "pea_pme");
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher un titre" }), "gec");
  await userEvent.selectOptions(await screen.findByRole("combobox", { name: "PEA-PME : statut de Gecina" }), "eligible");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/securities/4/envelopes/pea_pme",
    expect.objectContaining({ method: "PATCH", body: JSON.stringify({ override: "eligible" }) })));
});

test("liste les corrections de l'enveloppe choisie", async () => {
  const corrected = { ...GECINA, envelopes: envelopes("non_eligible", "non_eligible", "non_eligible") };
  mockFetch((url) => url.includes("overridden=true") ? { body: { items: [corrected], total: 1 } } : { body: { items: [], total: 0 } });
  renderWithProviders(<EnvelopeOverridesCard />);
  expect(await screen.findByText("Gecina")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Enveloppe à corriger" }), "pea_pme");
  await waitFor(() => expect(screen.queryByText("Gecina")).not.toBeInTheDocument()); // pas de correction PEA-PME
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/envelopes.test.ts src/features/screener src/features/security src/features/forecasts src/features/admin src/features/home`
Expected: FAIL (modules `./envelopes` et `./EnvelopeOverridesCard` introuvables, textes absents)

- [ ] **Step 4: Implementation**

`frontend/src/lib/envelopes.ts` :

```ts
/** Enveloppes d'investissement : mêmes codes que le registre du backend (services/envelopes/rules.py). */
export const ENVELOPE_LABELS: Record<string, string> = { pea: "PEA", pea_pme: "PEA-PME", cto: "Compte-titres" };
export const RULE_ENVELOPES = ["pea", "pea_pme"] as const;
export const STATUS_LABELS: Record<string, string> = { eligible: "Éligible", a_verifier: "À vérifier", non_eligible: "Non éligible" };

/** Enveloppes qui filtrent les titres : aucune si rien n'est choisi ou si le compte-titres (tout titre) est coché. */
export function filteringEnvelopes(codes: string[]): string[] {
  if (codes.includes("cto")) return [];
  return RULE_ENVELOPES.filter((code) => codes.includes(code));
}
```

`frontend/src/features/explorer/EnvelopeBadges.tsx` :

```tsx
import { Badge } from "@/components/ui/badge";
import { ENVELOPE_LABELS } from "@/lib/envelopes";

/** Enveloppes où le titre est éligible (déduction automatique). Rien n'est affiché pour « à vérifier » ou « non éligible ». */
export function EnvelopeBadges({ codes }: { codes: string[] }) {
  return (
    <>
      {codes.map((code) => (
        <Badge key={code} variant="outline" className="border-green-200 bg-green-50 font-medium text-green-700">
          {ENVELOPE_LABELS[code] ?? code}
        </Badge>
      ))}
    </>
  );
}
```

`frontend/src/features/settings/useEnvelopes.ts` :

```ts
import { useQuery } from "@tanstack/react-query";
import { useMe } from "@/features/auth/useMe";
import { apiGet, type EnvelopesOut } from "@/lib/api/client";
import { filteringEnvelopes } from "@/lib/envelopes";

/** Enveloppes choisies dans les réglages ; un visiteur n'en a aucune (tous les titres). */
export function useEnvelopes() {
  const { me } = useMe();
  const query = useQuery({
    queryKey: ["envelopes"],
    queryFn: () => apiGet<EnvelopesOut>("/api/settings/envelopes"),
    enabled: !!me,
  });
  const chosen = query.data?.envelopes ?? [];
  return { chosen, filtering: filteringEnvelopes(chosen), isPending: me === undefined || (!!me && query.isPending) };
}
```

`features/screener/filters.ts` :
- le champ `eligibility: string | null` devient `envelope: string | null` ;
- `filtersFromParams` lit `envelope: params.get("envelope")` ;
- dans `filterRows`, la condition devient `&& (!f.envelope || r.envelopes.includes(f.envelope))`.

`features/screener/ScreenerFilters.tsx` :
- remplacer `ELIGIBILITY_LABELS` par `ENVELOPE_LABELS` importé de `@/lib/envelopes` ;
- `Select` reçoit une prop optionnelle `allLabel` (défaut `` `${label} : tous` ``), utilisée dans la première `<option>` ;
- le filtre devient :

```tsx
      <Select label="Enveloppe" allLabel="Enveloppe : toutes" value={filters.envelope} options={["pea", "pea_pme"]}
              labels={ENVELOPE_LABELS} onChange={(v) => onChange("envelope", v)} />
```

`features/screener/columns.tsx:38` : `<EnvelopeBadges codes={row.original.envelopes} />` (import depuis `@/features/explorer/EnvelopeBadges`).

`features/security/SecurityPage.tsx` :
- supprimer `ELIGIBILITY_TEXT` ;
- dans la description de `securityMeta`, la fin `${ELIGIBILITY_TEXT[…]}` devient `${envelopeText(data.envelopes)}`, avec :

```tsx
const envelopeText = (codes: string[]) =>
  codes.length ? `Enveloppes compatibles : ${codes.map((c) => ENVELOPE_LABELS[c]).join(", ")}.` : "";
```

- dans l'en-tête, `<EligibilityBadge status={data.eligibility} />` devient `<EnvelopeBadges codes={data.envelopes} />` ;
- juste après ce `<p>`, pour un titre autre qu'un indice, ajouter :

```tsx
          {data.kind !== "index" && (
            <p className="mt-1 text-xs text-muted-foreground">
              Enveloppes déduites automatiquement (pays du siège, taille de l'entreprise) : à confirmer auprès de votre banque ou courtier.
            </p>
          )}
```

`features/security/ScoreCard.tsx` : supprimer la ligne `if (detail.eligibility !== "eligible") …` de `exclusionReason`.

`features/forecasts/PredictionsView.tsx` :
- remplacer l'import d'`EligibilityBadge` par `EnvelopeBadges` ;
- colonne nom (ligne 45) : `<EnvelopeBadges codes={row.original.security.envelopes} />` ;
- état et filtre :

```tsx
  const { filtering } = useEnvelopes();
  const [mineOnly, setMineOnly] = useState<boolean | null>(null); // null = défaut : coché si des enveloppes sont choisies
  const onlyMine = filtering.length > 0 && (mineOnly ?? true);
  ...
      if (onlyMine && !row.security.envelopes.some((code) => filtering.includes(code))) return false;
  ...
  }, [data, search, onlyMine, filtering, direction, minReliability, horizon]);
```

- la case :

```tsx
        {filtering.length > 0 && (
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={onlyMine} onChange={(e) => setMineOnly(e.target.checked)} />
            Mes enveloppes uniquement
          </label>
        )}
```

`app/Layout.tsx:34` : « compatibilité PEA déduite du pays du siège, à confirmer auprès de votre courtier » → « enveloppes compatibles (PEA, PEA-PME) déduites automatiquement, à confirmer auprès de votre courtier ».

`features/admin/EnvelopeOverridesCard.tsx` :

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, apiSend, type SecurityItem, type SecurityList } from "@/lib/api/client";
import { ENVELOPE_LABELS, RULE_ENVELOPES, STATUS_LABELS } from "@/lib/envelopes";
import { useDebouncedValue } from "@/lib/useDebouncedValue";

type Code = (typeof RULE_ENVELOPES)[number];

function OverrideRow({ item, code }: { item: SecurityItem; code: Code }) {
  const queryClient = useQueryClient();
  const current = item.envelopes.find((e) => e.code === code);
  const mutation = useMutation({
    mutationFn: (override: string | null) => apiSend("PATCH", `/api/securities/${item.id}/envelopes/${code}`, { override }),
    onSettled: () => {
      for (const key of ["settings-search", "overrides", "screener", "security", "top", "movers", "heatmap"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
    },
  });
  return (
    <li className="flex items-center justify-between gap-4 py-2">
      <div className="min-w-0">
        <p className="truncate font-medium">{item.name}</p>
        <p className="text-xs text-muted-foreground">{item.symbol} · {item.market}</p>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{STATUS_LABELS[current?.status ?? "a_verifier"]}</span>
        <select
          aria-label={`${ENVELOPE_LABELS[code]} : statut de ${item.name}`}
          value={current?.override ?? ""}
          onChange={(e) => mutation.mutate(e.target.value || null)}
          className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
        >
          <option value="">Automatique</option>
          <option value="eligible">Éligible</option>
          <option value="a_verifier">À vérifier</option>
          <option value="non_eligible">Non éligible</option>
        </select>
      </div>
    </li>
  );
}

/** Corrections des enveloppes : communes à tous les comptes, donc réservées à l'administrateur. */
export function EnvelopeOverridesCard() {
  const [code, setCode] = useState<Code>("pea");
  const [search, setSearch] = useState("");
  const q = useDebouncedValue(search.trim(), 300);
  const results = useQuery({
    queryKey: ["settings-search", q],
    queryFn: () => apiGet<SecurityList>("/api/securities", { q, limit: 10 }),
    enabled: q.length >= 2,
  });
  const overrides = useQuery({
    queryKey: ["overrides"],
    queryFn: () => apiGet<SecurityList>("/api/securities", { overridden: "true", limit: 200 }),
  });
  const corrected = (overrides.data?.items ?? []).filter((item) => item.envelopes.some((e) => e.code === code && e.override));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Enveloppes — corrections manuelles</CardTitle>
        <p className="text-sm text-muted-foreground">
          Le PEA est déduit du pays du siège (code ISIN), le PEA-PME en plus de la taille de l'entreprise (effectif, chiffre
          d'affaires, capitalisation). Si votre banque ou votre courtier dit autre chose pour un titre, corrigez-le ici : votre
          choix est prioritaire et conservé lors des mises à jour. Corriger le PEA d'un titre recalcule aussi son PEA-PME.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <select aria-label="Enveloppe à corriger" value={code} onChange={(e) => setCode(e.target.value as Code)}
                  className="h-8 rounded-lg border border-input bg-white px-2 text-sm">
            {RULE_ENVELOPES.map((c) => <option key={c} value={c}>{ENVELOPE_LABELS[c]}</option>)}
          </select>
          <Input type="search" aria-label="Rechercher un titre" placeholder="Nom, ticker ou ISIN (2 caractères minimum)…"
                 className="w-96 bg-white" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {results.data && (
          <ul className="divide-y divide-border">
            {results.data.items.map((item) => <OverrideRow key={item.id} item={item} code={code} />)}
            {results.data.items.length === 0 && <li className="py-2 text-sm text-muted-foreground">Aucun titre trouvé.</li>}
          </ul>
        )}
        <div>
          <h3 className="mb-1 text-sm font-semibold">Corrections en cours ({ENVELOPE_LABELS[code]})</h3>
          {corrected.length ? (
            <ul className="divide-y divide-border">{corrected.map((item) => <OverrideRow key={item.id} item={item} code={code} />)}</ul>
          ) : (
            <p className="text-sm text-muted-foreground">Aucune correction pour l'instant.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

Ensuite :
- `features/admin/AdminPage.tsx` : remplacer `EligibilityOverridesCard` par `EnvelopeOverridesCard` (import et usage).
- Supprimer `EligibilityBadge.tsx`, `EligibilityOverridesCard.tsx` et leur test.
- Vérifier : `grep -rn "eligibility\|EligibilityBadge" frontend/src --include=*.ts --include=*.tsx | grep -v schema.d.ts` ne doit plus rien renvoyer.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx tsc -b && npx vitest run && npx oxlint`
Expected: PASS, 0 erreur de type, 0 erreur oxlint

- [ ] **Step 6: Commit**

```bash
git add -A frontend
git commit -m "feat: envelope badges, Explorer envelope filter, forecasts and admin envelope corrections"
```

---

### Task 7: Frontend — carte « Mes enveloppes » et top 10

**Files:**
- Create: `frontend/src/features/settings/EnvelopesCard.tsx`, `frontend/src/features/settings/EnvelopesCard.test.tsx`
- Modify: `frontend/src/features/settings/SettingsPage.tsx`, `frontend/src/features/home/TopList.tsx:23`
- Test: `frontend/src/features/home/HomePage.test.tsx`, `frontend/src/features/settings/SettingsPage.test.tsx`

**Interfaces:**
- Consumes: `useEnvelopes()`, `ENVELOPE_LABELS`, `filteringEnvelopes` (tâche 6) ; `GET/PUT /api/settings/envelopes` (tâche 4).
- Produces: `<EnvelopesCard />`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/features/settings/EnvelopesCard.test.tsx` :

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { EnvelopesCard } from "./EnvelopesCard";

afterEach(() => vi.unstubAllGlobals());

function api(envelopes: string[]) {
  return mockFetch((url, init) => {
    if (url === "/api/me") return { body: ME };
    if (url === "/api/settings/envelopes") return { body: init?.method === "PUT" ? JSON.parse(String(init.body)) : { envelopes } };
    return { body: null };
  });
}

test("coche ses enveloppes et les enregistre", async () => {
  const fetchMock = api([]);
  renderWithProviders(<EnvelopesCard />);
  const pea = await screen.findByRole("checkbox", { name: /^PEA(?!-PME)/ });
  expect(pea).not.toBeChecked();
  expect(screen.getByText("Vous verrez tous les titres.")).toBeInTheDocument();
  await userEvent.click(pea);
  await userEvent.click(screen.getByRole("checkbox", { name: /PEA-PME/ }));
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer mes enveloppes" }));
  await waitFor(() => {
    const put = fetchMock.mock.calls.find(([url, init]) => url === "/api/settings/envelopes" && init?.method === "PUT");
    expect(JSON.parse(put![1]!.body as string)).toEqual({ envelopes: ["pea", "pea_pme"] });
  });
});

test("compte-titres coché : le texte dit que tous les titres restent visibles", async () => {
  api(["pea", "cto"]);
  renderWithProviders(<EnvelopesCard />);
  expect(await screen.findByRole("checkbox", { name: /Compte-titres/ })).toBeChecked();
  expect(screen.getByText("Vous verrez tous les titres.")).toBeInTheDocument();
});
```

Dans `frontend/src/features/home/HomePage.test.tsx`, ajouter deux tests, avec le rendu du test existant et un `mockFetch` complété :

```tsx
test("visiteur : le top 10 porte sur toutes les actions", async () => {
  // mockFetch existant + "/api/me" → { status: 401, body: { detail: "x" } }
  expect(await screen.findByText("Actions les mieux notées par le score mixte (technique + fondamentaux).")).toBeInTheDocument();
});

test("membre avec le PEA : le top 10 le dit", async () => {
  // mockFetch existant + "/api/me" → ME, "/api/settings/envelopes" → { envelopes: ["pea"] }
  expect(await screen.findByText(/parmi les titres compatibles avec vos enveloppes \(PEA\)/)).toBeInTheDocument();
});
```

Les commentaires de ces deux tests sont à remplacer par le code de rendu et de `mockFetch` du test existant, complété des réponses indiquées.

Dans `SettingsPage.test.tsx`, ajouter `vi.mock("./EnvelopesCard", () => ({ EnvelopesCard: () => null }));` en tête, comme pour les autres cartes, pour ne pas perturber les tests de frais.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/features/settings src/features/home`
Expected: FAIL (`./EnvelopesCard` introuvable, ancien texte du top 10)

- [ ] **Step 3: Implementation**

`frontend/src/features/settings/EnvelopesCard.tsx` :

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiSend, type EnvelopesOut } from "@/lib/api/client";
import { ENVELOPE_LABELS, filteringEnvelopes } from "@/lib/envelopes";
import { useEnvelopes } from "./useEnvelopes";

const HINTS: Record<string, string> = {
  pea: "Actions européennes et ETF éligibles, avantage fiscal après 5 ans.",
  pea_pme: "Petites et moyennes entreprises européennes (moins de 5 000 salariés, capitalisation sous 1 Md€) : estimation.",
  cto: "Tous les titres, sans avantage fiscal.",
};

export function EnvelopesCard() {
  const { chosen, isPending } = useEnvelopes();
  return (
    <Card id="enveloppes">
      <CardHeader>
        <CardTitle className="text-base">Mes enveloppes</CardTitle>
        <p className="text-sm text-muted-foreground">
          Les comptes sur lesquels vous investissez. Le top 10, les classements et les prévisions ne montrent que les titres
          compatibles. Rien de coché, ou le compte-titres coché : tous les titres.
        </p>
      </CardHeader>
      <CardContent>
        {isPending ? <Skeleton className="h-24 w-full" /> : <EnvelopesForm key={chosen.join()} initial={chosen} />}
      </CardContent>
    </Card>
  );
}

function EnvelopesForm({ initial }: { initial: string[] }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>(initial);
  const save = useMutation({
    mutationFn: (envelopes: string[]) => apiSend("PUT", "/api/settings/envelopes", { envelopes }) as Promise<EnvelopesOut>,
    onSuccess: (data) => {
      queryClient.setQueryData(["envelopes"], data);
      for (const key of ["top", "movers", "heatmap"]) queryClient.invalidateQueries({ queryKey: [key] });
      toast.success("Enveloppes enregistrées.");
    },
  });
  const toggle = (code: string, on: boolean) =>
    setSelected((current) => Object.keys(ENVELOPE_LABELS).filter((c) => (c === code ? on : current.includes(c))));
  const scope = filteringEnvelopes(selected);
  return (
    <div className="space-y-3">
      <ul className="space-y-2">
        {Object.entries(ENVELOPE_LABELS).map(([code, label]) => (
          <li key={code} className="flex items-start gap-2">
            <input id={`envelope-${code}`} type="checkbox" className="mt-1 size-4 accent-primary"
                   checked={selected.includes(code)} onChange={(e) => toggle(code, e.target.checked)} />
            <label htmlFor={`envelope-${code}`}>
              <span className="block font-medium">{label}</span>
              <span className="block text-xs text-muted-foreground">{HINTS[code]}</span>
            </label>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">
        {scope.length
          ? `Vous verrez les titres compatibles avec : ${scope.map((c) => ENVELOPE_LABELS[c]).join(", ")}.`
          : "Vous verrez tous les titres."}
      </p>
      {save.error && <p role="alert" className="text-sm text-destructive">{save.error.message}</p>}
      <Button onClick={() => save.mutate(selected)} disabled={save.isPending}>Enregistrer mes enveloppes</Button>
    </div>
  );
}
```

Vérifier l'usage de `toast` dans `FeeSettingsCard.tsx` (déjà importé de `sonner`) ; si la carte des frais n'en affiche pas, retirer le toast pour rester cohérent.

`features/settings/SettingsPage.tsx` :
- importer `EnvelopesCard` et la placer juste avant `<FeeSettingsCard />` ;
- la phrase d'introduction (dans `usePageMeta` et dans le `<p>`) devient : « Votre profil, votre abonnement, vos appareils, vos notifications, vos enveloppes et les frais de votre courtier. »

`features/home/TopList.tsx:23` :

```tsx
  const { filtering } = useEnvelopes();
  ...
        <p className="text-sm text-muted-foreground">
          Actions les mieux notées par le score mixte (technique + fondamentaux)
          {filtering.length ? `, parmi les titres compatibles avec vos enveloppes (${filtering.map((c) => ENVELOPE_LABELS[c]).join(", ")}).` : "."}
        </p>
```

Le `queryKey` du top 10 reste `["top"]`. L'enregistrement des enveloppes l'invalide, et une déconnexion recharge déjà la page.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx tsc -b && npx vitest run && npx oxlint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: Mes enveloppes settings card and envelope-aware top 10"
```

---

### Task 8: Guide, documentation admin, e2e, vérification finale et PR

**Files:**
- Rename: `frontend/public/documentation/eligibilite.md` → `frontend/public/documentation/enveloppes.md` (`git mv`) et mettre à jour `frontend/public/documentation/_sidebar.md:11`
- Modify (documentation) : `api.md`, `base-de-donnees.md`, `score.md`, `donnees.md`, `comptes.md:225`, `assistant.md:27`, `architecture.md:110` (« éligibilité » → « enveloppes »)
- Modify (guide) : `guide/app/accueil.md`, `guide/app/explorer.md`, `guide/app/fiche-titre.md`, `guide/app/previsions.md`, `guide/app/reglages.md`, `guide/app/donnees.md`, `guide/app/assistant.md`, `guide/bourse/etf.md`, `guide/bourse/pea.md`, `guide/bourse/risques.md`, `guide/faq.md`, `guide/premiers-pas.md`, `guide/lexique.md`
- Modify: `frontend/src/docs.test.ts` (garde-fou)
- Modify: `CLAUDE.md`. Changer trois passages :
  - la ligne `services/eligibility/rules.py` devient `services/envelopes/rules.py` : registre des enveloppes (PEA par le pays ISIN, PEA-PME par la taille), statuts dans `security_envelopes`, correction manuelle prioritaire ;
  - dans « Points d'attention », « Éligibilité PEA » devient « Enveloppes (PEA, PEA-PME) » ;
  - la phrase du score devient : « Le top 10 exclut les titres peu liquides (`min_turnover_eur`) ou à l'historique trop court (< 200 jours) ; il est ensuite filtré à la lecture selon les enveloppes de l'utilisateur ».
  - Également : dans « Calculs … fonctions pures », « éligibilité » devient « enveloppes ».
- Modify: `README.md`, si une phrase y décrit l'éligibilité PEA comme un filtre du top 10 (`grep -n -i "éligib" README.md`).
- Test: `frontend/e2e/*.spec.ts` (parcours existants)

- [ ] **Step 1: Write the failing guard test**

Dans `frontend/src/docs.test.ts`, ajouter un test qui lit **tous** les `.md` de `public/guide` et `public/documentation`, avec la même méthode de lecture que le test existant du fichier :

```ts
test("le guide et la documentation ne parlent plus de l'ancien filtre d'éligibilité", () => {
  for (const [path, text] of allMarkdown()) {
    expect(text, path).not.toMatch(/Éligibles PEA uniquement|Éligibilité PEA — corrections|eligibility_override|\/eligibility\b|services\/eligibility/);
    expect(text, path).not.toMatch(/actions éligibles (au )?PEA (qui ont|les mieux)/i);
  }
});
```

`allMarkdown()` est un helper local qui renvoie `[chemin, contenu][]` pour les deux dossiers, avec `readdirSync` récursif et `readFileSync`. Avant de l'écrire, vérifier comment le test existant ouvre `comptes.md` et réutiliser ce chemin de base.

Run: `cd frontend && npx vitest run src/docs.test.ts`
Expected: FAIL (plusieurs pages citées)

- [ ] **Step 2: Documentation admin**

`documentation/enveloppes.md` (réécrit) :
- **Titre :** « Enveloppes ». Code : `backend/app/services/envelopes/rules.py` (règles), `backend/app/repositories/envelopes.py` (stockage, filtre).
- **Tableau des enveloppes :** code, libellé, règle. Il reprend le tableau B1 du spec : PEA (UE/EEE + IS, REIT « à vérifier », ETF/indices par liste de départ), PEA-PME (seuils 5 000 / 1,5 Md€ / 1 Md€, donnée manquante → `a_verifier`), compte-titres (tous, non stocké).
- **Stockage :** table `security_envelopes` (une ligne par titre et enveloppe à règle, `status`, `source` auto/seed/manual, `override`).
- **Recalcul :**
  - à chaque passage de la tâche `universe` et des fondamentaux ;
  - effectif (`fullTimeEmployees`) et CA (`totalRevenue`, devise `financialCurrency`) viennent de Yahoo ;
  - une réponse sans ces champs ne les efface pas.
- **Corrections manuelles :**
  - route `PATCH /api/securities/{id}/envelopes/{pea|pea_pme}` avec `{"override": "eligible"|"a_verifier"|"non_eligible"|null}`, admin seulement ;
  - carte « Enveloppes — corrections manuelles » de l'onglet Admin ;
  - corriger le PEA recalcule le PEA-PME.
- **Réglages utilisateur :**
  - `user_settings.envelopes` ;
  - routes `GET/PUT /api/settings/envelopes` ;
  - rien ou compte-titres = tous les titres ;
  - les mails (récap du samedi, entrée dans le top 10) suivent le top 10 du membre.
- **Avertissement conservé :** c'est une déduction ; le PEA-PME est une estimation (le critère du total de bilan n'est pas connu).
- **Migration d'octobre 2026 :** les anciennes colonnes `securities.eligibility*` sont devenues des lignes `pea` (« override » → `manual`). Les lignes `pea_pme` apparaissent au premier passage des fondamentaux (7 h 30 en semaine).

Les autres pages de la documentation :
- **`_sidebar.md` :** `[Enveloppes](enveloppes.md)`.
- **`api.md` :**
  - ligne 101 : `GET /securities?q=&kind=&envelope=&overridden=&limit=&offset=` ;
  - ligne 102 : « … fondamentaux, enveloppes, favori » ;
  - ligne 104 : la nouvelle route PATCH ;
  - ajouter `GET/PUT /settings/envelopes` dans la section des réglages ;
  - préciser que `/rankings/top`, `/rankings/movers` et `/market/heatmap` sont filtrés selon les enveloppes du compte connecté.
- **`base-de-donnees.md:17` :** retirer « éligibilité automatique et correction » de `securities`. Ajouter `security_envelopes`, la colonne `user_settings.envelopes`, `fundamentals.employees/revenue/revenue_currency` et `score_snapshots.top_pool`.
- **`score.md:43` :** la condition du top 10 devient « type `stock` (toutes enveloppes) ». Ajouter que le filtre par enveloppe se fait à la lecture, selon le compte.
- **`donnees.md` :**
  - ligne 5 : « Il n'existe aucune liste officielle complète des titres éligibles au PEA ni au PEA-PME… » ;
  - ligne 9 : « ETF éligibles PEA : `seeds/etfs.csv` » reste ;
  - ligne 43 : « Met à jour la liste des titres et leurs enveloppes ».
  - ajouter : le worker suit désormais les cours de **tous** les titres actifs.
- **`comptes.md:225` :** « Corrections des enveloppes (voir [Enveloppes](enveloppes.md)) ».
- **`assistant.md:27` :** « Cours, score détaillé, fondamentaux, enveloppes ». Ajouter que le prompt système reçoit les enveloppes choisies.

- [ ] **Step 3: Guide**

- **`guide/app/accueil.md` :**
  - ligne 17 : « Les 10 actions qui ont le meilleur **score** en ce moment, parmi celles compatibles avec vos enveloppes si vous en avez choisi (voir [Réglages](app/reglages.md)). Pour chacune : » ;
  - ligne 28 : remplacer la condition « être éligible au PEA » par « (si vous avez choisi des enveloppes) être compatible avec l'une d'elles ».
- **`guide/app/explorer.md` :**
  - ligne 13 : « éligibilité PEA » → « enveloppe (PEA, PEA-PME) » ;
  - ligne 38 : l'onglet ETF liste les ETF suivis par l'application, avec leur badge PEA quand ils sont éligibles ;
  - section « Badges d'éligibilité PEA » → « Badges d'enveloppe » :
    - badge **PEA** : siège dans l'UE/EEE, déduit ;
    - badge **PEA-PME** : en plus, moins de 5 000 salariés, CA ≤ 1,5 Md€, capitalisation < 1 Md€ (estimation) ;
    - pas de badge : non éligible ou à vérifier, par exemple une foncière cotée ou une société américaine ;
    - garder l'avertissement « déduction, à vérifier auprès de votre banque ou courtier ».
- **`guide/app/fiche-titre.md:7` :** « … et les badges d'enveloppe (PEA, PEA-PME), avec un rappel qu'ils sont déduits ».
- **`guide/app/previsions.md:28` :** « filtrer par nom, enveloppes (case « Mes enveloppes uniquement », cochée par défaut si vous en avez choisi), sens… ».
- **`guide/app/reglages.md` :**
  - nouvelle section « Mes enveloppes », avant la section des frais : à quoi elle sert, les trois cases, la règle « rien ou compte-titres = tout », les effets (top 10, classements, prévisions, mails du samedi et de changement de score) ;
  - la section « Corrections d'éligibilité » devient « Corrections d'enveloppe », même idée : admin seulement, signaler un badge faux.
- **`guide/app/donnees.md:30` :** « Liste des actions et leurs enveloppes ».
- **`guide/app/assistant.md:41` :** « … chiffres de l'entreprise, enveloppes ». Ajouter une phrase : l'assistant connaît vos enveloppes.
- **`guide/bourse/etf.md:38` :** « L'onglet **ETF** liste les ETF suivis par l'application ; le badge PEA indique ceux qu'on peut loger dans un PEA. »
- **`guide/bourse/pea.md` :**
  - ligne 23 : « C'est pourquoi Cotalyx affiche un badge PEA sur chaque titre compatible » ;
  - ajouter un paragraphe court sur le **PEA-PME** (plafond de versement propre, mêmes règles fiscales, réservé aux PME et ETI européennes ; l'application l'estime) et sur le **compte-titres** (tout titre, pas d'avantage fiscal).
- **`guide/bourse/risques.md:59` :** « Les **enveloppes** (PEA, PEA-PME) sont déduites, pas officielles. »
- **`guide/faq.md` :**
  - ligne 21 : retirer « éligibilité « à vérifier » » des raisons d'absence du top 10, et ajouter « ou elle n'est pas compatible avec les enveloppes choisies dans vos réglages » ;
  - ligne 41 : « badge » → « badge d'enveloppe » ;
  - ajouter une entrée « Quelle enveloppe choisir dans mes réglages ? », renvoyant vers [Le PEA](bourse/pea.md).
- **`guide/premiers-pas.md:15` :** « … les 10 actions les mieux notées en ce moment (parmi vos enveloppes si vous en avez choisi), avec… ». Ajouter une étape « Choisissez vos enveloppes dans Réglages ».
- **`guide/lexique.md` :**
  - ajouter les entrées **PEA-PME**, **Compte-titres (CTO)** et **Enveloppe** ;
  - la ligne 42 (« ETF éligible au PEA ») reste.

Run: `cd frontend && npx vitest run src/docs.test.ts`
Expected: PASS

- [ ] **Step 3b: Commit docs**

```bash
git add -A frontend/public frontend/src/docs.test.ts CLAUDE.md README.md
git commit -m "docs: envelopes in the user guide and admin documentation"
```

- [ ] **Step 4: Full verification**

Run, dans l'ordre :

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q
cd frontend && npx tsc -b && npx vitest run && npx oxlint && cd ..
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build api worker web
cd frontend && npm run e2e
```

Expected:
- **Suites :** pytest, vitest, tsc et oxlint passent.
- **Migration :** elle s'applique sur la base de dev (données réelles). Vérifier `SELECT envelope, status, count(*) FROM security_envelopes GROUP BY 1, 2;` : environ 1 750 `pea/eligible`, ~72 `a_verifier` et ~80 `non_eligible`, aux variations de l'univers près.
- **e2e :** les tests passent. Si un parcours e2e cherchait « Éligibles PEA » ou « Éligibilité », l'adapter aux nouveaux libellés et le noter.

À la fin, remettre la configuration normale : `docker compose up -d --build api worker web`.

Vérification manuelle dans le navigateur (http://localhost:8095), avec un compte de test :
- **Réglages :** cocher PEA ; le top 10 de l'accueil change et sa phrase dit « (PEA) ».
- **Explorer :** filtre « Enveloppe : toutes / PEA / PEA-PME » ; aucun badge « À vérifier ».
- **Fiche :** badges PEA / PEA-PME et ligne « déduites automatiquement ».
- **Admin :** « Enveloppes — corrections manuelles », choix PEA-PME puis statut.

- [ ] **Step 5: Push and PR**

```bash
git push -u origin enveloppes
gh pr create --base cotalyx --title "Cotalyx bloc B : enveloppes (PEA, PEA-PME, compte-titres)" --body "<résumé : enveloppes, réglages, top 10, Explorer, admin, migration, points à vérifier après déploiement>"
```

Pour `--base` :
- si la PR #10 (`cotalyx`) est déjà fusionnée dans `main` au moment de la PR, utiliser `--base main` ;
- sinon, garder `--base cotalyx` et l'indiquer à l'utilisateur.

Le corps de la PR doit dire que les badges PEA-PME n'apparaissent qu'après le premier passage des fondamentaux (7 h 30 en semaine). Il se termine par `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
