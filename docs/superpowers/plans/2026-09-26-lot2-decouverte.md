# PEA Radar — Lot 2 (Découverte) : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Calculer le score mixte de chaque titre et livrer l'accueil (top 10, indices, hausses/baisses, carte du marché), l'explorateur complet (filtres, tris, URL), la page ETF, la fiche action (graphique TradingView, RSI/MACD, score détaillé, fondamentaux, simulateur, actualités, frais), les favoris et les réglages d'éligibilité.

**Architecture:** Les indicateurs, le score et les frais sont des fonctions pures (`services/`). Une tâche `scores` du worker calcule après chaque cycle T2 un enregistrement par titre (score, composants, performances, mini-courbe, liquidité) ; l'API ne fait que lire ces lignes. Seuls l'intraday et les actualités sont demandés à Yahoo à la demande, avec un cache mémoire. Côté interface, l'explorateur charge tous les titres en une fois et filtre/trie côté navigateur (tableau virtualisé) ; les pages lourdes (graphiques) sont chargées à la demande.

**Tech Stack:** Lot 1 + `lightweight-charts` 5, `echarts` 6 (import modulaire), `@tanstack/react-table`, `@tanstack/react-virtual`, `@playwright/test`.

**Spec:** `docs/superpowers/specs/2026-09-26-pea-radar-design.md` (sections 4, 5.2 à 5.5, 5.8, 3.3 T1, 6 non concerné) · Lot 1 : `docs/superpowers/plans/2026-09-26-lot1-socle.md`

## Global Constraints

- Tout ce qui est listé dans les Global Constraints du lot 1 reste valable (Python 3.12, SQLAlchemy 2 sync, Alembic, React + Vite + TS, Tailwind v4, shadcn/ui, TanStack Query, React Router, français pour l'utilisateur, thème clair, ≥ 1280 px, port web 8095, aucun appel réseau en test, ligne `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` dans chaque commit).
- Score sur 100 : technique 50 (tendance 20, dynamique 15, RSI 10, MACD 5) + fondamental 50 (valorisation 15, croissance 15, solidité 10, dividende 10) — règles exactes de la spec §4.2/§4.3.
- Top 10 : action `eligible`, montant moyen échangé sur 20 séances ≥ 500 000 €, ≥ 200 séances d'historique, ≤ 40 % des points manquants ; départage par liquidité.
- ETF : score technique uniquement, ramené sur 100, classement séparé.
- L'API ne contacte Yahoo à la demande que pour l'intraday (cache 60 s) et les actualités (cache 15 min).
- Commandes backend : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` ; frontend : `cd frontend && npm test`.
- Couleurs : hausse `#16a34a`, baisse `#dc2626`, principale indigo (variable `--primary`).

## Review Focus

1. **Titre sans historique, sans cours ou sans fondamentaux** → score absent ou partiel, les pages affichent « — » sans planter. *Tests : Task 5 `test_scores_handle_missing_data`, Task 14 `test_security_page_without_score`.*
2. **Premier démarrage : aucun score encore calculé** → l'accueil affiche un message d'attente, pas une liste vide muette ni une erreur. *Test : Task 11 `test_home_empty_state`.*
3. **Simulateur avec un montant inférieur au cours, nul ou négatif** → message clair ou 422, jamais de division par zéro. *Tests : Task 8 `test_simulate_amount_below_price`, `test_simulate_rejects_non_positive_amount`.*
4. **Yahoo en panne pour l'intraday ou les actualités** → liste vide, pas de 500. *Test : Task 8 `test_history_intraday_provider_failure`, `test_news_provider_failure`.*
5. **Séries plates ou nulles** (cours constant, cours à 0) → indicateurs et performances sans division par zéro. *Tests : Task 1 `test_rsi_constant_series`, `test_performance_zero_base`.*

---

## Structure des fichiers

```
backend/app/
├── core/config.py                 (modifié : seuils du top 10)
├── services/
│   ├── indicators.py              sma, ema, rsi, macd, performance
│   ├── fees.py                    grille de courtage et calcul des frais
│   ├── fx.py                      conversion approximative en euros
│   └── scoring/ config.py · components.py · score.py
├── models/ score.py · favorite.py
├── repositories/ scores.py · screener.py · market_data.py (modifié) · securities.py (modifié)
├── jobs/ scoring.py · tiers.py (modifié) · scheduler.py (modifié)
├── providers/ base.py · yahoo.py (modifiés : intraday, actualités)
├── services/cache.py              cache mémoire à durée de vie
├── api/deps.py                    fournisseur de marché + caches
├── api/routes/ screener.py · rankings.py · security_detail.py · favorites.py · fees.py · securities.py (modifié) · status.py (modifié)
└── schemas/ screener.py · rankings.py · security_detail.py · securities.py (modifié) · status.py (modifié)

frontend/src/
├── lib/ api/client.ts (modifié) · format.ts (modifié) · colors.ts
├── components/ Sparkline.tsx · ScoreGauge.tsx · FavoriteButton.tsx · charts/EChart.tsx
├── features/favorites/useToggleFavorite.ts
├── features/home/ HomePage.tsx · IndicesBar.tsx · TopList.tsx · Movers.tsx · MarketHeatmap.tsx
├── features/screener/ ScreenerPage.tsx · ScreenerTable.tsx · ScreenerFilters.tsx · filters.ts · columns.tsx · useScreener.ts
├── features/security/ SecurityPage.tsx · PriceChart.tsx · PriceChartPanel.tsx · ScoreCard.tsx · FundamentalsCard.tsx · SimulatorCard.tsx · NewsCard.tsx
├── features/settings/SettingsPage.tsx
└── features/explorer/ (ExplorerPage, SecuritiesTable, useSecurities supprimés ; EligibilityBadge conservé)
frontend/e2e/smoke.spec.ts · frontend/playwright.config.ts
```

---

### Task 1: Indicateurs techniques

**Files:**
- Create: `backend/app/services/indicators.py`
- Test: `backend/tests/test_indicators.py`

**Interfaces:**
- Produces: `sma(values: list[float], window: int) -> list[float | None]`, `ema(values, span) -> list[float | None]`, `rsi(values, period=14) -> list[float | None]` (lissage de Wilder), `macd(values, fast=12, slow=26, signal=9) -> Macd` (dataclass `Macd(macd, signal, histogram)` de listes alignées sur `values`), `performance(values, periods) -> float | None` (en %).

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_indicators.py` :
```python
import pytest

from app.services.indicators import ema, macd, performance, rsi, sma


def test_sma():
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2, 3, 4]
    assert sma([1, 2], 3) == [None, None]


def test_ema_seeded_with_sma():
    assert ema([1, 2, 3, 4, 5], 3) == [None, None, 2, 3, 4]


def test_rsi_all_gains():
    values = [float(i) for i in range(20)]
    assert rsi(values)[-1] == 100.0
    assert rsi(values)[13] is None


def test_rsi_balanced():
    values = [float(i % 2) for i in range(15)]  # +1, -1 alternés
    assert rsi(values)[14] == pytest.approx(50.0)


def test_rsi_constant_series():
    assert rsi([10.0] * 20)[-1] == 50.0


def test_macd_alignment_and_flat_series():
    result = macd([10.0] * 40)
    assert result.macd[24] is None and result.macd[25] == pytest.approx(0.0)
    assert result.signal[32] is None and result.signal[33] == pytest.approx(0.0)
    assert result.histogram[-1] == pytest.approx(0.0)
    assert len(result.macd) == len(result.signal) == len(result.histogram) == 40


def test_macd_rising_series_is_positive():
    result = macd([float(i) for i in range(60)])
    assert result.macd[-1] > 0


def test_performance():
    assert performance([100.0, 105.0, 110.0], 2) == pytest.approx(10.0)
    assert performance([100.0], 1) is None


def test_performance_zero_base():
    assert performance([0.0, 5.0], 1) is None
```

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_indicators.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.indicators'`.

- [ ] **Step 2: Implémenter**

`backend/app/services/indicators.py` :
```python
"""Indicateurs techniques calculés sur une série de clôtures (la plus ancienne en premier)."""

from dataclasses import dataclass


def sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= window:
            total -= values[i - window]
        if i >= window - 1:
            out[i] = total / window
    return out


def ema(values: list[float], span: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < span:
        return out
    k = 2 / (span + 1)
    previous = sum(values[:span]) / span
    out[span - 1] = previous
    for i in range(span, len(values)):
        previous = values[i] * k + previous * (1 - k)
        out[i] = previous
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(delta, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0.0)) / period
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


@dataclass(frozen=True)
class Macd:
    macd: list[float | None]
    signal: list[float | None]
    histogram: list[float | None]


def macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Macd:
    fast_ema, slow_ema = ema(values, fast), ema(values, slow)
    line = [f - s if f is not None and s is not None else None for f, s in zip(fast_ema, slow_ema)]
    signal_line: list[float | None] = [None] * len(values)
    start = next((i for i, v in enumerate(line) if v is not None), None)
    if start is not None:
        tail = ema([v for v in line[start:] if v is not None], signal)
        for offset, value in enumerate(tail):
            signal_line[start + offset] = value
    histogram = [m - s if m is not None and s is not None else None for m, s in zip(line, signal_line)]
    return Macd(line, signal_line, histogram)


def performance(values: list[float], periods: int) -> float | None:
    """Variation en % entre la valeur d'il y a `periods` séances et la dernière."""
    if len(values) <= periods:
        return None
    base = values[-1 - periods]
    if base == 0:
        return None
    return (values[-1] / base - 1) * 100
```

- [ ] **Step 3: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_indicators.py -q`
Expected: 9 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/indicators.py backend/tests/test_indicators.py
git commit -m "feat: technical indicators (SMA, EMA, RSI, MACD, performance)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Frais de courtage et conversion en euros

**Files:**
- Create: `backend/app/services/fees.py`, `backend/app/services/fx.py`
- Test: `backend/tests/test_fees_fx.py`

**Interfaces:**
- Produces: `FeeTier(up_to: float | None, rate: float)`, `DEFAULT_GRID: tuple[FeeTier, ...]`, `broker_fee(amount, grid=DEFAULT_GRID) -> tuple[float, float]` (frais arrondis au centime, taux) ; `currency_for_market(market: str) -> str`, `to_eur(value: float | None, currency: str | None) -> float | None`.

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_fees_fx.py` :
```python
import pytest

from app.services.fees import FeeTier, broker_fee
from app.services.fx import currency_for_market, to_eur


@pytest.mark.parametrize("amount, expected", [
    (400, (1.92, 0.0048)),
    (500, (2.40, 0.0048)),      # 500 € inclus dans la première tranche
    (500.01, (0.90, 0.0018)),
    (1000, (1.80, 0.0018)),
    (2000, (2.40, 0.0012)),
    (0, (0.0, 0.0)),
    (-10, (0.0, 0.0)),
])
def test_broker_fee_default_grid(amount, expected):
    assert broker_fee(amount) == expected


def test_broker_fee_custom_grid():
    assert broker_fee(100, (FeeTier(None, 0.01),)) == (1.0, 0.01)


def test_currency_for_market():
    assert currency_for_market("Oslo Børs") == "NOK"
    assert currency_for_market("Euronext Growth Oslo") == "NOK"
    assert currency_for_market("Euronext Paris") == "EUR"


def test_to_eur():
    assert to_eur(100.0, "EUR") == 100.0
    assert to_eur(100.0, "NOK") == pytest.approx(8.5)
    assert to_eur(100.0, None) == 100.0
    assert to_eur(None, "EUR") is None
```

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_fees_fx.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 2: Implémenter**

`backend/app/services/fees.py` :
```python
"""Frais de courtage Invest Store Intégral (grille par défaut de la caisse de Paris)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeeTier:
    up_to: float | None  # borne haute incluse ; None = sans limite
    rate: float


DEFAULT_GRID: tuple[FeeTier, ...] = (
    FeeTier(500.0, 0.0048),
    FeeTier(1000.0, 0.0018),
    FeeTier(None, 0.0012),
)


def broker_fee(amount: float, grid: tuple[FeeTier, ...] = DEFAULT_GRID) -> tuple[float, float]:
    """Retourne (frais en €, taux). Le taux de la tranche s'applique au montant total de l'ordre."""
    if amount <= 0:
        return 0.0, 0.0
    for tier in grid:
        if tier.up_to is None or amount <= tier.up_to:
            return round(amount * tier.rate, 2), tier.rate
    last = grid[-1]
    return round(amount * last.rate, 2), last.rate
```

`backend/app/services/fx.py` :
```python
"""Conversion approximative en euros, suffisante pour comparer des liquidités et des capitalisations."""

FX_TO_EUR: dict[str, float] = {"EUR": 1.0, "NOK": 0.085, "SEK": 0.087, "DKK": 0.134}


def currency_for_market(market: str) -> str:
    return "NOK" if "Oslo" in market else "EUR"


def to_eur(value: float | None, currency: str | None) -> float | None:
    if value is None:
        return None
    return value * FX_TO_EUR.get((currency or "EUR").upper(), 1.0)
```

- [ ] **Step 3: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_fees_fx.py -q`
Expected: 12 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/fees.py backend/app/services/fx.py backend/tests/test_fees_fx.py
git commit -m "feat: broker fee grid and EUR conversion helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Score mixte (fonctions pures)

**Files:**
- Create: `backend/app/services/scoring/__init__.py`, `config.py`, `components.py`, `score.py`
- Test: `backend/tests/test_scoring.py`

**Interfaces:**
- Produces:
  - `app.services.scoring.config.MAX_POINTS: dict[str, float]` (clés `trend, momentum, rsi, macd, valuation, growth, solidity, dividend`).
  - `app.services.scoring.components` : dataclass `Component(key, label, points, max_points, message, group)` ; fonctions `trend(price, sma50, sma200)`, `momentum(perf_3m, index_perf_3m)`, `rsi_component(value)`, `macd_component(macd_line, signal_line)`, `valuation(pe, sector_median_pe)`, `growth(eps_growth, revenue_growth)`, `solidity(debt_to_equity, profit_margin)`, `dividend(dividend_yield)` — chacune renvoie `Component | None` (`None` = donnée indisponible).
  - `app.services.scoring.score` : dataclass `ScoreInputs(price, sma50, sma200, perf_3m, index_perf_3m, rsi, macd_line, signal_line, pe, sector_median_pe, eps_growth, revenue_growth, debt_to_equity, profit_margin, dividend_yield)` (tous optionnels, listes vides par défaut) ; dataclass `ScoreResult(total, technical, fundamental, components, available_ratio)` ; `compute_score(inputs, kind="stock") -> ScoreResult`.

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_scoring.py` :
```python
import pytest

from app.services.scoring.components import (
    dividend, growth, macd_component, momentum, rsi_component, solidity, trend, valuation,
)
from app.services.scoring.score import ScoreInputs, compute_score


def test_trend():
    assert trend(110, 100, 90).points == 20
    assert trend(95, 100, 90).points == 7 + 6
    assert trend(80, 100, 110).points == 0
    assert trend(80, None, 110) is None
    assert trend(110, 100, 90).message.startswith("✅")


@pytest.mark.parametrize("diff, expected", [(-15, 0), (-10, 0), (0, 7.5), (10, 15), (20, 15)])
def test_momentum(diff, expected):
    assert momentum(5 + diff, 5).points == pytest.approx(expected)


def test_momentum_missing_index():
    assert momentum(5, None) is None


@pytest.mark.parametrize("value, expected", [(50, 10), (40, 10), (60, 10), (35, 6), (65, 6), (70, 6), (25, 4), (75, 0)])
def test_rsi_component(value, expected):
    assert rsi_component(value).points == expected


def test_macd_crossover_recent():
    macd_line = [-1, -1, -1, -1, -1, 1, 1]
    signal = [0, 0, 0, 0, 0, 0, 0]
    assert macd_component(macd_line, signal).points == 5


def test_macd_above_signal_without_recent_cross():
    macd_line = [1] * 10
    signal = [0] * 10
    assert macd_component(macd_line, signal).points == 3


def test_macd_below_signal():
    assert macd_component([-1] * 10, [0] * 10).points == 0


def test_macd_not_enough_data():
    assert macd_component([None, None, 1], [None, None, 0]) is None


@pytest.mark.parametrize("pe, expected", [(8, 15), (11.5, 7.5), (15, 0), (30, 0), (-5, 0)])
def test_valuation(pe, expected):
    assert valuation(pe, 10).points == pytest.approx(expected)


def test_valuation_missing():
    assert valuation(None, 10) is None
    assert valuation(12, None) is None


def test_growth_halves():
    full = growth(0.20, 0.15)
    assert (full.points, full.max_points) == (15, 15)
    half = growth(0.075, None)
    assert (half.points, half.max_points) == (pytest.approx(3.75), 7.5)
    assert growth(None, None) is None


def test_solidity():
    assert solidity(0.3, 0.12).points == 10
    assert solidity(2.5, -0.1).points == 0
    assert solidity(None, 0.05).max_points == 5


@pytest.mark.parametrize("value, expected", [(0.0, 0), (0.01, 5), (0.04, 10), (0.07, 7), (0.10, 5)])
def test_dividend(value, expected):
    assert dividend(value).points == pytest.approx(expected)


def test_dividend_missing():
    assert dividend(None) is None


PERFECT = dict(
    price=120, sma50=110, sma200=100, perf_3m=20, index_perf_3m=5, rsi=50,
    macd_line=[-1, -1, -1, -1, -1, 1, 1], signal_line=[0] * 7,
    pe=8, sector_median_pe=10, eps_growth=0.2, revenue_growth=0.2, debt_to_equity=0.2, profit_margin=0.2,
    dividend_yield=0.04,
)


def test_compute_score_perfect():
    result = compute_score(ScoreInputs(**PERFECT))
    assert result.total == 100
    assert result.technical == 100 and result.fundamental == 100
    assert result.available_ratio == 1.0
    assert len(result.components) == 8


def test_compute_score_without_fundamentals_is_normalized():
    technical_only = {k: v for k, v in PERFECT.items() if k in (
        "price", "sma50", "sma200", "perf_3m", "index_perf_3m", "rsi", "macd_line", "signal_line")}
    result = compute_score(ScoreInputs(**technical_only))
    assert result.total == 100
    assert result.fundamental is None
    assert result.available_ratio == 0.5


def test_compute_score_etf_ignores_fundamentals():
    result = compute_score(ScoreInputs(**PERFECT), kind="etf")
    assert result.available_ratio == 1.0
    assert result.fundamental is None
    assert {c.group for c in result.components} == {"technical"}


def test_compute_score_nothing_available():
    result = compute_score(ScoreInputs())
    assert result.total is None and result.available_ratio == 0.0
```

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_scoring.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.scoring'`.

- [ ] **Step 2: Implémenter**

Créer `backend/app/services/scoring/__init__.py` vide.

`backend/app/services/scoring/config.py` :
```python
"""Pondérations du score mixte (spec §4). Modifier une valeur met le composant à l'échelle."""

MAX_POINTS: dict[str, float] = {
    "trend": 20,
    "momentum": 15,
    "rsi": 10,
    "macd": 5,
    "valuation": 15,
    "growth": 15,
    "solidity": 10,
    "dividend": 10,
}
```

`backend/app/services/scoring/components.py` :
```python
"""Composants du score : chaque fonction renvoie None quand la donnée est indisponible."""

from dataclasses import dataclass

from app.services.scoring.config import MAX_POINTS

_DEFAULT_MAX = {"trend": 20, "momentum": 15, "rsi": 10, "macd": 5, "valuation": 15, "growth": 15, "solidity": 10, "dividend": 10}


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    points: float
    max_points: float
    message: str
    group: str  # technical | fundamental


def _lin(x: float, x_lo: float, x_hi: float, p_lo: float, p_hi: float) -> float:
    if x <= x_lo:
        return p_lo
    if x >= x_hi:
        return p_hi
    return p_lo + (x - x_lo) / (x_hi - x_lo) * (p_hi - p_lo)


def _fr(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _pct(fraction: float | None) -> str:
    return "n.d." if fraction is None else f"{fraction * 100:+.0f} %".replace(".", ",")


def _make(key: str, label: str, points: float, max_points: float, message: str, group: str) -> Component:
    scale = MAX_POINTS[key] / _DEFAULT_MAX[key]
    return Component(key, label, round(points * scale, 2), round(max_points * scale, 2), message, group)


def trend(price: float | None, sma50: float | None, sma200: float | None) -> Component | None:
    if price is None or sma50 is None or sma200 is None:
        return None
    points = 7 * (price > sma50) + 7 * (price > sma200) + 6 * (sma50 > sma200)
    if points >= 14:
        message = "✅ Tendance haussière (cours au-dessus des moyennes 50 et 200 jours)"
    elif points == 0:
        message = "❌ Tendance baissière (cours sous les moyennes 50 et 200 jours)"
    else:
        message = "⚠️ Tendance mitigée"
    return _make("trend", "Tendance", points, 20, message, "technical")


def momentum(perf_3m: float | None, index_perf_3m: float | None) -> Component | None:
    if perf_3m is None or index_perf_3m is None:
        return None
    diff = perf_3m - index_perf_3m
    points = _lin(diff, -10, 10, 0, 15)
    if diff >= 0:
        message = f"✅ Fait mieux que le CAC 40 sur 3 mois ({_fr(diff)} pts)"
    else:
        message = f"⚠️ Fait moins bien que le CAC 40 sur 3 mois ({_fr(diff)} pts)"
    return _make("momentum", "Dynamique 3 mois", points, 15, message, "technical")


def rsi_component(value: float | None) -> Component | None:
    if value is None:
        return None
    shown = _fr(value, 0)
    if 40 <= value <= 60:
        points, message = 10, f"✅ RSI équilibré ({shown})"
    elif 30 <= value < 40 or 60 < value <= 70:
        points, message = 6, f"⚠️ RSI proche d'une zone extrême ({shown})"
    elif value < 30:
        points, message = 4, f"⚠️ RSI en zone de survente ({shown}) : rebond possible mais risqué"
    else:
        points, message = 0, f"❌ RSI en surchauffe ({shown})"
    return _make("rsi", "RSI 14", points, 10, message, "technical")


def macd_component(macd_line: list[float | None], signal_line: list[float | None]) -> Component | None:
    pairs = [(m, s) for m, s in zip(macd_line, signal_line) if m is not None and s is not None]
    if len(pairs) < 6:
        return None
    recent_cross = any(pairs[i][0] > pairs[i][1] and pairs[i - 1][0] <= pairs[i - 1][1] for i in range(len(pairs) - 5, len(pairs)))
    if recent_cross:
        points, message = 5, "✅ Signal MACD haussier récent"
    elif pairs[-1][0] > pairs[-1][1]:
        points, message = 3, "✅ MACD au-dessus de son signal"
    else:
        points, message = 0, "⚠️ MACD sous son signal"
    return _make("macd", "MACD", points, 5, message, "technical")


def valuation(pe: float | None, sector_median_pe: float | None) -> Component | None:
    if pe is None or sector_median_pe is None or sector_median_pe <= 0:
        return None
    if pe <= 0:
        return _make("valuation", "Valorisation", 0, 15, "❌ Entreprise en perte (PER négatif)", "fundamental")
    ratio = pe / sector_median_pe
    points = _lin(ratio, 0.8, 1.5, 15, 0)
    detail = f"PER {_fr(pe)} contre {_fr(sector_median_pe)} pour le secteur"
    message = f"✅ Valorisation attractive ({detail})" if ratio <= 1 else f"⚠️ Valorisation élevée ({detail})"
    return _make("valuation", "Valorisation", points, 15, message, "fundamental")


def growth(eps_growth: float | None, revenue_growth: float | None) -> Component | None:
    halves = [g for g in (eps_growth, revenue_growth) if g is not None]
    if not halves:
        return None
    points = sum(_lin(g, 0, 0.15, 0, 7.5) for g in halves)
    max_points = 7.5 * len(halves)
    detail = f"bénéfices {_pct(eps_growth)}, chiffre d'affaires {_pct(revenue_growth)}"
    message = f"✅ Croissance solide ({detail})" if points >= max_points / 2 else f"⚠️ Croissance faible ({detail})"
    return _make("growth", "Croissance", points, max_points, message, "fundamental")


def solidity(debt_to_equity: float | None, profit_margin: float | None) -> Component | None:
    points = max_points = 0.0
    if debt_to_equity is not None:
        points += _lin(debt_to_equity, 0.5, 2.0, 5, 0)
        max_points += 5
    if profit_margin is not None:
        points += _lin(profit_margin, 0, 0.10, 0, 5)
        max_points += 5
    if max_points == 0:
        return None
    message = "✅ Bilan solide (dette maîtrisée, bonnes marges)" if points >= max_points / 2 else "⚠️ Bilan fragile (dette élevée ou marges faibles)"
    return _make("solidity", "Solidité", points, max_points, message, "fundamental")


def dividend(dividend_yield: float | None) -> Component | None:
    if dividend_yield is None:
        return None
    shown = _fr(dividend_yield * 100)
    if dividend_yield <= 0:
        points, message = 0, "⚠️ Pas de dividende"
    elif dividend_yield < 0.02:
        points, message = _lin(dividend_yield, 0, 0.02, 0, 10), f"⚠️ Dividende modeste ({shown} %)"
    elif dividend_yield <= 0.06:
        points, message = 10, f"✅ Dividende de {shown} %"
    elif dividend_yield <= 0.08:
        points, message = 7, f"✅ Dividende élevé ({shown} %)"
    else:
        points, message = 5, f"⚠️ Rendement très élevé ({shown} %) : à vérifier"
    return _make("dividend", "Dividende", points, 10, message, "fundamental")
```

`backend/app/services/scoring/score.py` :
```python
from dataclasses import dataclass, field

from app.services.scoring.components import (
    Component, dividend, growth, macd_component, momentum, rsi_component, solidity, trend, valuation,
)
from app.services.scoring.config import MAX_POINTS

_TECHNICAL_KEYS = ("trend", "momentum", "rsi", "macd")


@dataclass(frozen=True)
class ScoreInputs:
    price: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    perf_3m: float | None = None
    index_perf_3m: float | None = None
    rsi: float | None = None
    macd_line: list[float | None] = field(default_factory=list)
    signal_line: list[float | None] = field(default_factory=list)
    pe: float | None = None
    sector_median_pe: float | None = None
    eps_growth: float | None = None
    revenue_growth: float | None = None
    debt_to_equity: float | None = None
    profit_margin: float | None = None
    dividend_yield: float | None = None


@dataclass(frozen=True)
class ScoreResult:
    total: float | None
    technical: float | None
    fundamental: float | None
    components: list[Component]
    available_ratio: float

    @property
    def incomplete(self) -> bool:
        return self.available_ratio < 1


def _ratio(components: list[Component]) -> float | None:
    available = sum(c.max_points for c in components)
    return round(sum(c.points for c in components) / available * 100, 1) if available else None


def compute_score(inputs: ScoreInputs, kind: str = "stock") -> ScoreResult:
    technical = [c for c in (
        trend(inputs.price, inputs.sma50, inputs.sma200),
        momentum(inputs.perf_3m, inputs.index_perf_3m),
        rsi_component(inputs.rsi),
        macd_component(inputs.macd_line, inputs.signal_line),
    ) if c is not None]
    fundamental: list[Component] = []
    if kind != "etf":
        fundamental = [c for c in (
            valuation(inputs.pe, inputs.sector_median_pe),
            growth(inputs.eps_growth, inputs.revenue_growth),
            solidity(inputs.debt_to_equity, inputs.profit_margin),
            dividend(inputs.dividend_yield),
        ) if c is not None]
    components = technical + fundamental
    possible = sum(v for k, v in MAX_POINTS.items() if kind != "etf" or k in _TECHNICAL_KEYS)
    available = sum(c.max_points for c in components)
    return ScoreResult(
        total=_ratio(components),
        technical=_ratio(technical),
        fundamental=_ratio(fundamental),
        components=components,
        available_ratio=round(available / possible, 3) if possible else 0.0,
    )
```

- [ ] **Step 3: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_scoring.py -q`
Expected: tous PASSED.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/scoring backend/tests/test_scoring.py
git commit -m "feat: mixed score components and computation

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Tables `scores` et `favorites`

**Files:**
- Create: `backend/app/models/score.py`, `backend/app/models/favorite.py`, `backend/alembic/versions/<généré>_scores_and_favorites.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/core/config.py`, `backend/tests/factories.py`
- Test: `backend/tests/test_models_lot2.py`

**Interfaces:**
- Produces: modèles `SecurityScore` (table `scores`) et `Favorite` (table `favorites`) ; réglages `min_turnover_eur=500_000`, `top_size=10`, `min_history_days=200`, `min_available_ratio=0.6` ; fabrique `make_score(db, security, **fields) -> SecurityScore`.

- [ ] **Step 1: Test (échoue)**

`backend/tests/test_models_lot2.py` :
```python
from datetime import UTC, datetime

from app.core.current_user import ensure_default_user
from app.models import Favorite, SecurityScore
from tests.factories import make_score, make_security


def test_score_roundtrip(db):
    security = make_security(db, "MC.PA")
    make_score(db, security, total=72.5, components=[{"key": "trend", "points": 20}], sparkline=[1.0, 2.0])
    stored = db.get(SecurityScore, security.id)
    assert stored.total == 72.5
    assert stored.components[0]["key"] == "trend"
    assert stored.sparkline == [1.0, 2.0]


def test_favorite_roundtrip(db):
    user = ensure_default_user(db)
    security = make_security(db, "MC.PA")
    db.add(Favorite(user_id=user.id, security_id=security.id))
    db.flush()
    assert db.get(Favorite, (user.id, security.id)) is not None
```

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_models_lot2.py -q`
Expected: FAIL — `ImportError: cannot import name 'Favorite'`.

- [ ] **Step 2: Modèles et réglages**

`backend/app/models/score.py` :
```python
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityScore(Base):
    """Score mixte et indicateurs précalculés par la tâche `scores` du worker."""

    __tablename__ = "scores"

    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total: Mapped[float | None] = mapped_column(Float, index=True)
    technical: Mapped[float | None] = mapped_column(Float)
    fundamental: Mapped[float | None] = mapped_column(Float)
    components: Mapped[list] = mapped_column(JSONB, default=list)
    available_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    liquid: Mapped[bool] = mapped_column(default=False)
    history_days: Mapped[int] = mapped_column(default=0)
    avg_turnover_eur: Mapped[float] = mapped_column(Float, default=0.0)
    eligible_for_top: Mapped[bool] = mapped_column(default=False, index=True)
    perf_1w: Mapped[float | None] = mapped_column(Float)
    perf_1m: Mapped[float | None] = mapped_column(Float)
    perf_3m: Mapped[float | None] = mapped_column(Float)
    perf_1y: Mapped[float | None] = mapped_column(Float)
    sparkline: Mapped[list] = mapped_column(JSONB, default=list)
```

`backend/app/models/favorite.py` :
```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`backend/app/models/__init__.py` (remplacer) :
```python
from app.models.base import Base
from app.models.data_status import DataStatus
from app.models.favorite import Favorite
from app.models.market import DailyPrice, SecurityFundamentals, SecurityQuote
from app.models.score import SecurityScore
from app.models.security import Security
from app.models.user import User

__all__ = [
    "Base", "DataStatus", "DailyPrice", "Favorite", "Security", "SecurityFundamentals", "SecurityQuote",
    "SecurityScore", "User",
]
```

Dans `backend/app/core/config.py`, ajouter à la fin de la classe `Settings` :
```python
    min_turnover_eur: float = 500_000
    top_size: int = 10
    min_history_days: int = 200
    min_available_ratio: float = 0.6
```

Ajouter à la fin de `backend/tests/factories.py` :
```python
from datetime import UTC, datetime

from app.models import SecurityScore


def make_score(db: Session, security: Security, **fields) -> SecurityScore:
    values = dict(
        computed_at=datetime(2026, 9, 28, 8, 0, tzinfo=UTC), total=60.0, technical=60.0, fundamental=60.0,
        components=[], available_ratio=1.0, liquid=True, history_days=250, avg_turnover_eur=1_000_000.0,
        eligible_for_top=True, perf_1w=1.0, perf_1m=2.0, perf_3m=3.0, perf_1y=4.0, sparkline=[1.0, 2.0],
    )
    values.update(fields)
    score = SecurityScore(security_id=security.id, **values)
    db.add(score)
    db.flush()
    return score
```

- [ ] **Step 3: Vérifier et générer la migration**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_models_lot2.py -q`
Expected: 2 passed.

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db && docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic revision --autogenerate -m "scores and favorites"`
Expected: fichier `backend/alembic/versions/*_scores_and_favorites.py` avec `create_table('scores'` et `create_table('favorites'` (et rien d'autre).

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic upgrade head`
Expected: `Running upgrade d132b530c4d9 -> …, scores and favorites`.

- [ ] **Step 4: Commit**

```bash
git add backend
git commit -m "feat: scores and favorites tables

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Tâche `scores` du worker et niveau T1 enrichi

**Files:**
- Create: `backend/app/repositories/scores.py`, `backend/app/jobs/scoring.py`
- Modify: `backend/app/repositories/market_data.py`, `backend/app/jobs/tiers.py`, `backend/app/jobs/scheduler.py`
- Test: `backend/tests/test_scoring_job.py`

**Interfaces:**
- Consumes: `sma, rsi, macd, performance` (Task 1), `currency_for_market, to_eur` (Task 2), `ScoreInputs, compute_score` (Task 3), `SecurityScore, Favorite` (Task 4), `refreshable_securities` (lot 1), `run_job`, `HEAVY_JOBS_LOCK`, `quotes_job`, `daily_job`, `bootstrap_job` (lot 1).
- Produces:
  - `app.repositories.market_data.daily_series(session, since: date) -> dict[int, list[DailyPrice]]` (triées par date).
  - `app.repositories.scores` : `upsert_score(session, security_id, values: dict) -> None`, `top_security_ids(session, limit) -> list[int]`, `favorite_security_ids(session) -> set[int]`, `sector_median_pe(fundamentals_by_sector: dict[str | None, list[float]]) -> dict[str | None, float]` (clé `None` = médiane globale).
  - `app.jobs.scoring.refresh_scores(ctx) -> int`.
  - T1 = indices + favoris + top 10 ; T2/T3 excluent les titres déjà en T1.
  - Le planificateur lance `scores` après chaque cycle T2, après l'historique quotidien et au démarrage.

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_scoring_job.py` :
```python
from datetime import UTC, date, datetime, timedelta

from app.core.current_user import ensure_default_user
from app.jobs.scheduler import quotes_job
from app.jobs.scoring import refresh_scores
from app.jobs.tiers import tier_tickers
from app.models import DailyPrice, DataStatus, Favorite, SecurityFundamentals, SecurityQuote, SecurityScore
from app.providers.base import Quote
from tests.factories import make_score, make_security
from tests.fakes import FakeMarket

NOW = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)  # lundi 10h à Paris
LAST_DAY = date(2026, 9, 25)


def add_series(db, security, days: int, start: float = 100.0, step: float = 0.5, volume: int = 10_000) -> None:
    for i in range(days):
        day = LAST_DAY - timedelta(days=days - 1 - i)
        close = start + step * i
        db.add(DailyPrice(security_id=security.id, date=day, open=close, high=close, low=close, close=close, volume=volume))
    db.flush()


def add_fundamentals(db, security, **fields) -> None:
    values = dict(pe=10.0, eps=2.0, earnings_growth=0.2, revenue_growth=0.2, debt_to_equity=0.3,
                  profit_margin=0.15, dividend_yield=0.04, market_cap=1e10, currency="EUR")
    values.update(fields)
    db.add(SecurityFundamentals(security_id=security.id, **values))
    db.flush()


def setup_market(db):
    cac = make_security(db, "^FCHI", kind="index", eligibility="non_eligible", country=None)
    add_series(db, cac, 260, start=7000, step=1)
    return cac


def test_scores_liquid_stock_enters_top(db, make_ctx):
    setup_market(db)
    stock = make_security(db, "A.PA")
    add_series(db, stock, 260)
    add_fundamentals(db, stock)
    refresh_scores(make_ctx(now=NOW))
    score = db.get(SecurityScore, stock.id)
    assert score.total is not None and score.total > 50
    assert score.liquid is True and score.history_days == 260
    assert score.eligible_for_top is True
    assert score.perf_1w is not None and score.perf_1y is not None
    assert len(score.sparkline) == 63
    assert {c["key"] for c in score.components} >= {"trend", "valuation"}


def test_scores_illiquid_or_short_history_excluded_from_top(db, make_ctx):
    setup_market(db)
    illiquid = make_security(db, "B.PA")
    add_series(db, illiquid, 260, volume=10)
    young = make_security(db, "C.PA")
    add_series(db, young, 50)
    refresh_scores(make_ctx(now=NOW))
    assert db.get(SecurityScore, illiquid.id).eligible_for_top is False
    assert db.get(SecurityScore, illiquid.id).liquid is False
    assert db.get(SecurityScore, young.id).eligible_for_top is False


def test_scores_convert_nok_turnover(db, make_ctx):
    setup_market(db)
    oslo = make_security(db, "X.OL", market="Oslo Børs", country="NO")
    add_series(db, oslo, 260, start=100, step=0, volume=10_000)  # 1 M NOK ≈ 85 000 €
    refresh_scores(make_ctx(now=NOW))
    assert db.get(SecurityScore, oslo.id).liquid is False


def test_scores_etf_has_no_fundamental(db, make_ctx):
    setup_market(db)
    etf = make_security(db, "CW8.PA", kind="etf")
    add_series(db, etf, 260)
    refresh_scores(make_ctx(now=NOW))
    score = db.get(SecurityScore, etf.id)
    assert score.fundamental is None and score.eligible_for_top is False
    assert score.available_ratio == 1.0


def test_scores_use_newer_quote(db, make_ctx):
    setup_market(db)
    stock = make_security(db, "A.PA")
    add_series(db, stock, 260)
    db.add(SecurityQuote(security_id=stock.id, price=500.0, previous_close=229.5, change_pct=100.0, volume=1, as_of=NOW))
    db.flush()
    refresh_scores(make_ctx(now=NOW))
    assert db.get(SecurityScore, stock.id).sparkline[-1] == 500.0


def test_scores_handle_missing_data(db, make_ctx):
    stock = make_security(db, "EMPTY.PA")
    refresh_scores(make_ctx(now=NOW))
    score = db.get(SecurityScore, stock.id)
    assert score.total is None and score.eligible_for_top is False and score.sparkline == []


def test_no_dividend_counts_as_zero_when_fundamentals_known(db, make_ctx):
    setup_market(db)
    stock = make_security(db, "A.PA")
    add_series(db, stock, 260)
    add_fundamentals(db, stock, dividend_yield=None)
    refresh_scores(make_ctx(now=NOW))
    dividend = next(c for c in db.get(SecurityScore, stock.id).components if c["key"] == "dividend")
    assert dividend["points"] == 0


def test_tier1_includes_favorites_and_top(db):
    user = ensure_default_user(db)
    make_security(db, "^FCHI", kind="index", eligibility="non_eligible", country=None)
    fav = make_security(db, "FAV.PA")
    top = make_security(db, "TOP.PA")
    other = make_security(db, "OTH.PA")
    db.add(Favorite(user_id=user.id, security_id=fav.id))
    make_score(db, top, total=90, eligible_for_top=True)
    make_score(db, other, total=10, eligible_for_top=False)
    db.flush()
    assert tier_tickers(db, 1, tier2_size=10) == ["FAV.PA", "TOP.PA", "^FCHI"]
    assert "FAV.PA" not in tier_tickers(db, 2, tier2_size=10)


def test_quotes_job_tier2_triggers_scores(db, make_ctx):
    make_security(db, "A.PA")
    market = FakeMarket(quotes={"A.PA": Quote(10.0, 9.0, 11.1, 1, NOW)})
    quotes_job(make_ctx(market=market, now=NOW), 2)
    assert db.get(DataStatus, "scores") is not None
```

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_scoring_job.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.jobs.scoring'`.

- [ ] **Step 2: Dépôts**

Ajouter à `backend/app/repositories/market_data.py` :
```python
def daily_series(session: Session, since: date) -> dict[int, list[DailyPrice]]:
    rows = session.scalars(
        select(DailyPrice).where(DailyPrice.date >= since).order_by(DailyPrice.security_id, DailyPrice.date)
    )
    result: dict[int, list[DailyPrice]] = {}
    for row in rows:
        result.setdefault(row.security_id, []).append(row)
    return result
```

`backend/app/repositories/scores.py` :
```python
from statistics import median

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Favorite, SecurityScore


def upsert_score(session: Session, security_id: int, values: dict) -> None:
    row = {"security_id": security_id, **values}
    stmt = pg_insert(SecurityScore).values(row)
    session.execute(stmt.on_conflict_do_update(
        index_elements=["security_id"], set_={k: stmt.excluded[k] for k in values},
    ))


def top_security_ids(session: Session, limit: int) -> list[int]:
    stmt = (
        select(SecurityScore.security_id)
        .where(SecurityScore.eligible_for_top.is_(True))
        .order_by(SecurityScore.total.desc(), SecurityScore.avg_turnover_eur.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def favorite_security_ids(session: Session) -> set[int]:
    return set(session.scalars(select(Favorite.security_id)))


def sector_median_pe(pe_by_sector: dict[str | None, list[float]]) -> dict[str | None, float]:
    """Médiane des PER positifs par secteur (au moins 3 valeurs) ; la clé None porte la médiane globale."""
    everything = [pe for values in pe_by_sector.values() for pe in values]
    medians: dict[str | None, float] = {}
    if everything:
        medians[None] = median(everything)
    for sector, values in pe_by_sector.items():
        if sector is not None and len(values) >= 3:
            medians[sector] = median(values)
    return medians
```

- [ ] **Step 3: Tâche de calcul**

`backend/app/jobs/scoring.py` :
```python
from collections import defaultdict
from dataclasses import asdict
from datetime import timedelta

from sqlalchemy import select

from app.jobs.context import JobContext
from app.models import SecurityFundamentals, SecurityQuote
from app.repositories.market_data import daily_series, refreshable_securities
from app.repositories.scores import sector_median_pe, upsert_score
from app.services.fx import currency_for_market, to_eur
from app.services.indicators import macd, performance, rsi, sma
from app.services.market_calendar import PARIS
from app.services.scoring.score import ScoreInputs, compute_score

HISTORY_WINDOW = timedelta(days=420)  # ≈ 290 séances : assez pour la moyenne 200 jours et la perf 1 an
SPARKLINE_POINTS = 63
INDEX_TICKER = "^FCHI"


def _last(values: list) -> float | None:
    return values[-1] if values else None


def refresh_scores(ctx: JobContext) -> int:
    now = ctx.now()
    today = now.astimezone(PARIS).date()
    settings = ctx.settings
    with ctx.session_factory() as session:
        securities = [s for s in refreshable_securities(session) if s.kind != "index" or s.yahoo_ticker == INDEX_TICKER]
        series = daily_series(session, today - HISTORY_WINDOW)
        quotes = {q.security_id: q for q in session.scalars(select(SecurityQuote))}
        fundamentals = {f.security_id: f for f in session.scalars(select(SecurityFundamentals))}

        pe_by_sector: dict[str | None, list[float]] = defaultdict(list)
        for s in securities:
            f = fundamentals.get(s.id)
            if s.kind == "stock" and f and f.pe and f.pe > 0:
                pe_by_sector[s.sector].append(f.pe)
        medians = sector_median_pe(pe_by_sector)

        def closes_for(security) -> list[float]:
            bars = series.get(security.id, [])
            closes = [b.close for b in bars]
            quote = quotes.get(security.id)
            if quote and (not bars or quote.as_of.astimezone(PARIS).date() > bars[-1].date):
                closes.append(quote.price)  # séance en cours
            return closes

        index = next((s for s in securities if s.yahoo_ticker == INDEX_TICKER), None)
        index_perf_3m = performance(closes_for(index), 63) if index else None

        count = 0
        for s in securities:
            if s.kind == "index":
                continue
            bars = series.get(s.id, [])
            closes = closes_for(s)
            f = fundamentals.get(s.id)
            macd_values = macd(closes)
            dividend_yield = None
            if f is not None:
                dividend_yield = f.dividend_yield if f.dividend_yield is not None else 0.0  # pas de dividende déclaré
            result = compute_score(ScoreInputs(
                price=_last(closes),
                sma50=_last(sma(closes, 50)),
                sma200=_last(sma(closes, 200)),
                perf_3m=performance(closes, 63),
                index_perf_3m=index_perf_3m,
                rsi=_last(rsi(closes)),
                macd_line=macd_values.macd[-10:],
                signal_line=macd_values.signal[-10:],
                pe=f.pe if f else None,
                sector_median_pe=medians.get(s.sector, medians.get(None)),
                eps_growth=f.earnings_growth if f else None,
                revenue_growth=f.revenue_growth if f else None,
                debt_to_equity=f.debt_to_equity if f else None,
                profit_margin=f.profit_margin if f else None,
                dividend_yield=dividend_yield,
            ), kind=s.kind)
            recent = bars[-20:]
            turnover = sum(b.close * (b.volume or 0) for b in recent) / len(recent) if recent else 0.0
            turnover_eur = to_eur(turnover, currency_for_market(s.market)) or 0.0
            liquid = turnover_eur >= settings.min_turnover_eur
            eligible_for_top = (
                s.kind == "stock" and s.eligibility == "eligible" and liquid
                and len(bars) >= settings.min_history_days
                and result.total is not None and result.available_ratio >= settings.min_available_ratio
            )
            upsert_score(session, s.id, {
                "computed_at": now,
                "total": result.total,
                "technical": result.technical,
                "fundamental": result.fundamental,
                "components": [asdict(c) for c in result.components],
                "available_ratio": result.available_ratio,
                "liquid": liquid,
                "history_days": len(bars),
                "avg_turnover_eur": turnover_eur,
                "eligible_for_top": eligible_for_top,
                "perf_1w": performance(closes, 5),
                "perf_1m": performance(closes, 21),
                "perf_3m": performance(closes, 63),
                "perf_1y": performance(closes, 252),
                "sparkline": [round(c, 4) for c in closes[-SPARKLINE_POINTS:]],
            })
            count += 1
        session.commit()
    return count
```

- [ ] **Step 4: Niveau T1 et planificateur**

`backend/app/jobs/tiers.py` (remplacer) :
```python
from sqlalchemy.orm import Session

from app.repositories.market_data import average_turnover, refreshable_securities
from app.repositories.scores import favorite_security_ids, top_security_ids

TOP_IN_T1 = 10


def tier_tickers(session: Session, tier: int, tier2_size: int) -> list[str]:
    """T1 : indices, favoris et top 10. T2 : les `tier2_size` titres les plus échangés. T3 : les autres."""
    candidates = refreshable_securities(session)
    priority_ids = favorite_security_ids(session) | set(top_security_ids(session, TOP_IN_T1))
    tier1 = [s for s in candidates if s.kind == "index" or s.id in priority_ids]
    if tier == 1:
        return sorted(s.yahoo_ticker for s in tier1)
    tier1_ids = {s.id for s in tier1}
    turnover = average_turnover(session)
    others = sorted(
        (s for s in candidates if s.id not in tier1_ids),
        key=lambda s: (-turnover.get(s.id, 0.0), s.yahoo_ticker),
    )
    selected = others[:tier2_size] if tier == 2 else others[tier2_size:]
    return [s.yahoo_ticker for s in selected]
```

Dans `backend/app/jobs/scheduler.py` :
- ajouter l'import `from app.jobs.scoring import refresh_scores` ;
- ajouter la fonction :
```python
def _refresh_scores(ctx: JobContext) -> None:
    run_job(ctx, "scores", refresh_scores)
```
- remplacer `quotes_job` par :
```python
def quotes_job(ctx: JobContext, tier: int) -> None:
    if is_market_open(ctx.now()):
        _refresh_tier(ctx, tier)
        if tier == 2:
            _refresh_scores(ctx)
```
- dans `daily_job`, ajouter `_refresh_scores(ctx)` après `run_job(ctx, "daily_history", refresh_daily_history)` ;
- dans `bootstrap_job`, ajouter `_refresh_scores(ctx)` juste après la boucle `for tier in (1, 2, 3): _refresh_tier(ctx, tier)`.

- [ ] **Step 5: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tous PASSED (les tests du lot 1 sur les niveaux restent valides : sans favori ni score, T1 = indices).

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: scores worker job, favorites and top 10 in tier 1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Intraday, actualités et cache mémoire

**Files:**
- Create: `backend/app/services/cache.py`
- Modify: `backend/app/providers/base.py`, `backend/app/providers/yahoo.py`, `backend/tests/fakes.py`
- Test: `backend/tests/test_cache.py`, `backend/tests/test_yahoo_ondemand.py`

**Interfaces:**
- Produces:
  - `app.providers.base` : `IntradayBar(time: datetime, open, high, low, close, volume)`, `NewsItem(title, url, publisher, published_at)` ; `MarketDataProvider.get_intraday(ticker, period, interval) -> list[IntradayBar]`, `get_news(ticker) -> list[NewsItem]`.
  - `app.providers.yahoo` : `intraday_from_frame(frame) -> list[IntradayBar]`, `parse_news(items) -> list[NewsItem]` ; `YahooProvider(..., ticker_news=None)`.
  - `app.services.cache.TTLCache(ttl_seconds, clock=time.monotonic)` avec `get_or_set(key, factory)` et `clear()`.
  - `FakeMarket(intraday=..., news=..., fail_on_demand=False)`.

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_cache.py` :
```python
from app.services.cache import TTLCache


def test_cache_reuses_value_until_expiry():
    now = [0.0]
    cache = TTLCache(60, clock=lambda: now[0])
    calls = []
    factory = lambda: calls.append(1) or len(calls)  # noqa: E731
    assert cache.get_or_set("k", factory) == 1
    now[0] = 59
    assert cache.get_or_set("k", factory) == 1
    now[0] = 61
    assert cache.get_or_set("k", factory) == 2


def test_cache_clear():
    cache = TTLCache(60)
    cache.get_or_set("k", lambda: 1)
    cache.clear()
    assert cache.get_or_set("k", lambda: 2) == 2
```

`backend/tests/test_yahoo_ondemand.py` :
```python
from datetime import UTC, datetime

import pandas as pd

from app.providers.yahoo import YahooProvider, intraday_from_frame, parse_news


def intraday_frame() -> pd.DataFrame:
    index = pd.DatetimeIndex(["2026-09-25 09:00", "2026-09-25 09:05"], tz="Europe/Paris")
    return pd.DataFrame({"Open": [10, 11], "High": [11, 12], "Low": [9, 10], "Close": [10.5, 11.5], "Volume": [100, 200]},
                        index=index)


def test_intraday_from_frame_converts_to_utc():
    bars = intraday_from_frame(intraday_frame())
    assert bars[0].time == datetime(2026, 9, 25, 7, 0, tzinfo=UTC)
    assert (bars[1].close, bars[1].volume) == (11.5, 200)


def test_get_intraday_uses_download():
    seen = {}

    def fake_download(tickers, **kwargs):
        seen.update(kwargs)
        return pd.concat({tickers[0]: intraday_frame()}, axis=1)

    provider = YahooProvider(download=fake_download, sleep=lambda s: None)
    bars = provider.get_intraday("MC.PA", "1d", "5m")
    assert (seen["period"], seen["interval"]) == ("1d", "5m")
    assert len(bars) == 2


def test_parse_news_new_format():
    items = [{"content": {"title": "LVMH publie", "pubDate": "2026-09-25T08:00:00Z",
                          "canonicalUrl": {"url": "https://ex.com/a"}, "provider": {"displayName": "Reuters"}}}]
    news = parse_news(items)
    assert news[0].title == "LVMH publie"
    assert news[0].url == "https://ex.com/a"
    assert news[0].publisher == "Reuters"
    assert news[0].published_at == datetime(2026, 9, 25, 8, 0, tzinfo=UTC)


def test_parse_news_legacy_format_and_invalid_items():
    items = [
        {"title": "Ancien format", "link": "https://ex.com/b", "publisher": "AFP", "providerPublishTime": 1790000000},
        {"content": {"title": "Sans lien"}},
        "n'importe quoi",
    ]
    news = parse_news(items)
    assert len(news) == 1
    assert news[0].publisher == "AFP" and news[0].published_at is not None


def test_get_news_returns_empty_on_error():
    def failing(ticker):
        raise ConnectionError("KO")

    provider = YahooProvider(ticker_news=failing, sleep=lambda s: None)
    assert provider.get_news("MC.PA") == []
```

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_cache.py tests/test_yahoo_ondemand.py -q`
Expected: FAIL — `ModuleNotFoundError` / `ImportError`.

- [ ] **Step 2: Implémenter**

`backend/app/services/cache.py` :
```python
import threading
import time
from collections.abc import Callable, Hashable
from typing import Any


class TTLCache:
    """Cache mémoire minimal : chaque valeur expire `ttl_seconds` après son calcul."""

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._values: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        now = self._clock()
        with self._lock:
            cached = self._values.get(key)
            if cached and now - cached[0] < self._ttl:
                return cached[1]
        value = factory()
        with self._lock:
            self._values[key] = (now, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
```

Dans `backend/app/providers/base.py`, ajouter après `DailyBar` :
```python
@dataclass(frozen=True)
class IntradayBar:
    time: datetime
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    publisher: str | None
    published_at: datetime | None
```
et ajouter au protocole `MarketDataProvider` :
```python
    def get_intraday(self, ticker: str, period: str, interval: str) -> list[IntradayBar]: ...

    def get_news(self, ticker: str) -> list[NewsItem]: ...
```

Dans `backend/app/providers/yahoo.py` :
- compléter l'import : `from app.providers.base import DailyBar, Fundamentals, IntradayBar, NewsItem, Quote` ;
- ajouter après `bars_from_frame` :
```python
def intraday_from_frame(frame: pd.DataFrame) -> list[IntradayBar]:
    bars = []
    for index, row in frame.iterrows():
        moment = index.to_pydatetime()
        moment = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
        bars.append(IntradayBar(time=moment, open=_num(row["Open"]), high=_num(row["High"]), low=_num(row["Low"]),
                                close=float(row["Close"]), volume=_int(row["Volume"])))
    return bars


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None
    return None


def parse_news(items: Any) -> list[NewsItem]:
    """Accepte l'ancien format yfinance (champs à plat) et le nouveau (sous-objet `content`)."""
    news = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        content = item.get("content") if isinstance(item.get("content"), dict) else item
        title = content.get("title")
        url = (content.get("canonicalUrl") or {}).get("url") or content.get("link")
        if not title or not url:
            continue
        publisher = (content.get("provider") or {}).get("displayName") or content.get("publisher")
        published = _parse_datetime(content.get("pubDate") or content.get("providerPublishTime"))
        news.append(NewsItem(title=title, url=url, publisher=publisher, published_at=published))
    return news
```
- dans `YahooProvider.__init__`, ajouter le paramètre `ticker_news: Callable[[str], Any] | None = None` (après `ticker_info`) et la ligne `self._ticker_news = ticker_news or (lambda ticker: yf.Ticker(ticker).news)` ;
- ajouter les méthodes :
```python
    def get_intraday(self, ticker: str, period: str, interval: str) -> list[IntradayBar]:
        frames = self._download_frames([ticker], period=period, interval=interval)
        return intraday_from_frame(frames[ticker]) if ticker in frames else []

    def get_news(self, ticker: str) -> list[NewsItem]:
        try:
            with self._lock:
                items = self._ticker_news(ticker)
        except Exception:
            logger.warning("Actualités Yahoo indisponibles pour %s", ticker, exc_info=True)
            return []
        return parse_news(items)
```

Dans `backend/tests/fakes.py`, remplacer la classe `FakeMarket` par :
```python
class FakeMarket:
    def __init__(
        self,
        quotes: dict[str, Quote] | None = None,
        history: dict[str, list[DailyBar]] | None = None,
        fundamentals: dict[str, Fundamentals] | None = None,
        intraday: dict[str, list[IntradayBar]] | None = None,
        news: dict[str, list[NewsItem]] | None = None,
        fail_on_demand: bool = False,
    ) -> None:
        self.quotes = quotes or {}
        self.history = history or {}
        self.fundamentals = fundamentals or {}
        self.intraday = intraday or {}
        self.news = news or {}
        self.fail_on_demand = fail_on_demand
        self.quote_calls: list[list[str]] = []
        self.history_calls: list[tuple[list[str], date]] = []
        self.fundamental_calls: list[str] = []
        self.intraday_calls: list[tuple[str, str, str]] = []

    def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        self.quote_calls.append(list(tickers))
        return {t: q for t, q in self.quotes.items() if t in tickers}

    def get_daily_history(self, tickers: list[str], start: date) -> dict[str, list[DailyBar]]:
        self.history_calls.append((list(tickers), start))
        return {t: bars for t, bars in self.history.items() if t in tickers}

    def get_fundamentals(self, ticker: str) -> Fundamentals | None:
        self.fundamental_calls.append(ticker)
        return self.fundamentals.get(ticker)

    def get_intraday(self, ticker: str, period: str, interval: str) -> list[IntradayBar]:
        self.intraday_calls.append((ticker, period, interval))
        if self.fail_on_demand:
            raise ConnectionError("Yahoo KO")
        return self.intraday.get(ticker, [])

    def get_news(self, ticker: str) -> list[NewsItem]:
        if self.fail_on_demand:
            raise ConnectionError("Yahoo KO")
        return self.news.get(ticker, [])
```
et compléter son import : `from app.providers.base import DailyBar, Fundamentals, IntradayBar, ListedSecurity, NewsItem, Quote`.

- [ ] **Step 3: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tous PASSED.

- [ ] **Step 4: Commit**

```bash
git add backend
git commit -m "feat: intraday and news from Yahoo, in-memory TTL cache

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: API — explorateur, classement, hausses/baisses, carte du marché

**Files:**
- Create: `backend/app/api/deps.py`, `backend/app/repositories/screener.py`, `backend/app/schemas/screener.py`, `backend/app/schemas/rankings.py`, `backend/app/api/routes/screener.py`, `backend/app/api/routes/rankings.py`
- Modify: `backend/app/main.py`, `backend/app/schemas/status.py`, `backend/app/api/routes/status.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_api_screener.py`

**Interfaces:**
- Consumes: modèles (lots 1–2), `get_current_user` (lot 1), `to_eur` (Task 2), `YahooProvider` (Task 6).
- Produces:
  - `app.api.deps` : `get_market_provider() -> MarketDataProvider` (singleton), `INTRADAY_CACHE = TTLCache(60)`, `NEWS_CACHE = TTLCache(900)`.
  - `GET /api/screener?kind=stock|etf` → `list[ScreenerRow]` ; `ScreenerRow {id, yahoo_ticker, symbol, name, kind, market, country, sector, eligibility, price, change_pct, perf_1w, perf_1m, perf_1y, score, pe, dividend_yield, liquid, is_favorite, sparkline: list[float]}`.
  - `GET /api/rankings/top?limit=1..50` (défaut 10) → `list[TopItem]` = `ScreenerRow` + `technical`, `fundamental`, `reasons: list[str]` (3 messages des composants qui rapportent le plus de points).
  - `GET /api/rankings/movers?limit=1..20` (défaut 5) → `Movers {gainers: list[ScreenerRow], losers: list[ScreenerRow]}` (actions éligibles et liquides).
  - `GET /api/market/heatmap` → `list[HeatmapItem {id, symbol, name, sector, market_cap_eur, change_pct}]` (200 plus grosses capitalisations éligibles et liquides ; secteur `Autres` si inconnu).
  - `IndexQuote` gagne le champ `id`.
  - `repositories.screener` : `screener_rows(session, user_id, kind=None, only_top=False, limit=None) -> list[Row]` (colonnes `Security, SecurityQuote, SecurityScore, SecurityFundamentals, is_favorite`).
  - Fixtures de test : `fake_market` (un `FakeMarket` injecté dans l'API) ; les caches sont vidés à chaque test.

- [ ] **Step 1: Tests (échouent)**

Dans `backend/tests/conftest.py`, remplacer la fixture `client` par :
```python
@pytest.fixture
def fake_market():
    from tests.fakes import FakeMarket

    return FakeMarket()


@pytest.fixture
def client(db, fake_market):
    from app.api.deps import INTRADAY_CACHE, NEWS_CACHE, get_market_provider

    INTRADAY_CACHE.clear()
    NEWS_CACHE.clear()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_market_provider] = lambda: fake_market
    with TestClient(app) as test_client:
        yield test_client
```

`backend/tests/test_api_screener.py` :
```python
from datetime import UTC, datetime

from app.core.current_user import ensure_default_user
from app.models import Favorite, SecurityFundamentals, SecurityQuote
from tests.factories import make_score, make_security

AS_OF = datetime(2026, 9, 25, 15, 35, tzinfo=UTC)


def quote(db, security, price, change):
    db.add(SecurityQuote(security_id=security.id, price=price, previous_close=price, change_pct=change, volume=1, as_of=AS_OF))


def seed(db):
    user = ensure_default_user(db)
    lvmh = make_security(db, "MC.PA", name="LVMH")
    total = make_security(db, "TTE.PA", name="TotalEnergies")
    small = make_security(db, "SMA.PA", name="Petite")
    etf = make_security(db, "CW8.PA", name="Amundi World", kind="etf")
    make_security(db, "^FCHI", name="CAC 40", kind="index", eligibility="non_eligible", country=None)
    quote(db, lvmh, 600, 2.5)
    quote(db, total, 60, -1.5)
    quote(db, small, 5, 9.0)
    make_score(db, lvmh, total=80, components=[
        {"key": "trend", "label": "Tendance", "points": 20, "max_points": 20, "message": "✅ Tendance", "group": "technical"},
        {"key": "rsi", "label": "RSI", "points": 6, "max_points": 10, "message": "⚠️ RSI", "group": "technical"},
        {"key": "valuation", "label": "Valorisation", "points": 12, "max_points": 15, "message": "✅ Valo", "group": "fundamental"},
        {"key": "macd", "label": "MACD", "points": 0, "max_points": 5, "message": "⚠️ MACD", "group": "technical"},
    ])
    make_score(db, total, total=70)
    make_score(db, small, total=95, liquid=False, eligible_for_top=False)
    make_score(db, etf, total=50, eligible_for_top=False)
    db.add(SecurityFundamentals(security_id=lvmh.id, pe=20.0, dividend_yield=0.02, market_cap=3e11, currency="EUR"))
    db.add(SecurityFundamentals(security_id=total.id, pe=8.0, market_cap=1e11, currency="EUR"))
    db.add(Favorite(user_id=user.id, security_id=total.id))
    db.flush()
    return lvmh, total, small, etf


def test_screener_stocks(client, db):
    seed(db)
    rows = client.get("/api/screener", params={"kind": "stock"}).json()
    assert [r["symbol"] for r in rows] == ["MC", "SMA", "TTE"]
    lvmh = rows[0]
    assert (lvmh["price"], lvmh["score"], lvmh["pe"], lvmh["dividend_yield"]) == (600, 80, 20.0, 0.02)
    assert lvmh["sparkline"] == [1.0, 2.0] and lvmh["is_favorite"] is False
    assert rows[2]["is_favorite"] is True


def test_screener_default_excludes_indices(client, db):
    seed(db)
    symbols = {r["symbol"] for r in client.get("/api/screener").json()}
    assert "CW8" in symbols and "^FCHI" not in symbols


def test_top_ranking_order_and_reasons(client, db):
    seed(db)
    top = client.get("/api/rankings/top").json()
    assert [t["symbol"] for t in top] == ["MC", "TTE"]
    assert top[0]["reasons"] == ["✅ Tendance", "✅ Valo", "⚠️ RSI"]


def test_top_ranking_limit_validation(client):
    assert client.get("/api/rankings/top", params={"limit": 0}).status_code == 422


def test_movers_only_liquid_eligible_stocks(client, db):
    seed(db)
    movers = client.get("/api/rankings/movers").json()
    assert [m["symbol"] for m in movers["gainers"]] == ["MC", "TTE"]
    assert [m["symbol"] for m in movers["losers"]] == ["TTE", "MC"]


def test_heatmap(client, db):
    seed(db)
    items = client.get("/api/market/heatmap").json()
    assert [i["symbol"] for i in items] == ["MC", "TTE"]
    assert items[0]["sector"] == "Autres"
    assert items[0]["market_cap_eur"] == 3e11


def test_status_indices_have_id(client, db):
    seed(db)
    index = client.get("/api/status").json()["indices"][0]
    assert isinstance(index["id"], int)
```

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_api_screener.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.deps'`.

- [ ] **Step 2: Dépendances de l'API**

`backend/app/api/deps.py` :
```python
from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import MarketDataProvider
from app.providers.yahoo import YahooProvider
from app.services.cache import TTLCache

INTRADAY_CACHE = TTLCache(60)
NEWS_CACHE = TTLCache(900)


@lru_cache
def get_market_provider() -> MarketDataProvider:
    """Seul accès de l'API à Yahoo : intraday et actualités, à la demande et mis en cache."""
    settings = get_settings()
    return YahooProvider(chunk_size=settings.yahoo_chunk_size, pause_seconds=settings.yahoo_pause_seconds)
```

- [ ] **Step 3: Dépôt et schémas**

`backend/app/repositories/screener.py` :
```python
from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from app.models import Favorite, Security, SecurityFundamentals, SecurityQuote, SecurityScore


def screener_rows(
    session: Session, user_id: int, *, kind: str | None = None, only_top: bool = False, limit: int | None = None,
) -> list[Row]:
    is_favorite = (
        select(Favorite.security_id)
        .where(Favorite.user_id == user_id, Favorite.security_id == Security.id)
        .exists()
        .label("is_favorite")
    )
    stmt = (
        select(Security, SecurityQuote, SecurityScore, SecurityFundamentals, is_favorite)
        .outerjoin(SecurityQuote, SecurityQuote.security_id == Security.id)
        .outerjoin(SecurityScore, SecurityScore.security_id == Security.id)
        .outerjoin(SecurityFundamentals, SecurityFundamentals.security_id == Security.id)
        .where(Security.active.is_(True))
    )
    stmt = stmt.where(Security.kind == kind) if kind else stmt.where(Security.kind != "index")
    if only_top:
        stmt = stmt.where(SecurityScore.eligible_for_top.is_(True)).order_by(
            SecurityScore.total.desc(), SecurityScore.avg_turnover_eur.desc())
    else:
        stmt = stmt.order_by(Security.name, Security.id)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).all())
```

`backend/app/schemas/screener.py` :
```python
from pydantic import BaseModel
from sqlalchemy import Row


class ScreenerRow(BaseModel):
    id: int
    yahoo_ticker: str
    symbol: str
    name: str
    kind: str
    market: str
    country: str | None
    sector: str | None
    eligibility: str
    price: float | None
    change_pct: float | None
    perf_1w: float | None
    perf_1m: float | None
    perf_1y: float | None
    score: float | None
    pe: float | None
    dividend_yield: float | None
    liquid: bool
    is_favorite: bool
    sparkline: list[float]

    @classmethod
    def fields_from(cls, row: Row) -> dict:
        security, quote, score, fundamentals, is_favorite = row
        return dict(
            id=security.id, yahoo_ticker=security.yahoo_ticker, symbol=security.symbol, name=security.name,
            kind=security.kind, market=security.market, country=security.country, sector=security.sector,
            eligibility=security.eligibility,
            price=quote.price if quote else None,
            change_pct=quote.change_pct if quote else None,
            perf_1w=score.perf_1w if score else None,
            perf_1m=score.perf_1m if score else None,
            perf_1y=score.perf_1y if score else None,
            score=score.total if score else None,
            pe=fundamentals.pe if fundamentals else None,
            dividend_yield=fundamentals.dividend_yield if fundamentals else None,
            liquid=bool(score and score.liquid),
            is_favorite=bool(is_favorite),
            sparkline=list(score.sparkline) if score and score.sparkline else [],
        )

    @classmethod
    def build(cls, row: Row) -> "ScreenerRow":
        return cls(**cls.fields_from(row))
```

`backend/app/schemas/rankings.py` :
```python
from pydantic import BaseModel
from sqlalchemy import Row

from app.schemas.screener import ScreenerRow


class TopItem(ScreenerRow):
    technical: float | None
    fundamental: float | None
    reasons: list[str]

    @classmethod
    def build(cls, row: Row) -> "TopItem":
        score = row[2]
        components = sorted(score.components or [], key=lambda c: c.get("points", 0), reverse=True)
        return cls(**cls.fields_from(row), technical=score.technical, fundamental=score.fundamental,
                   reasons=[c["message"] for c in components[:3]])


class Movers(BaseModel):
    gainers: list[ScreenerRow]
    losers: list[ScreenerRow]


class HeatmapItem(BaseModel):
    id: int
    symbol: str
    name: str
    sector: str
    market_cap_eur: float
    change_pct: float
```

- [ ] **Step 4: Routes**

`backend/app/api/routes/screener.py` :
```python
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import User
from app.repositories.screener import screener_rows
from app.schemas.screener import ScreenerRow

router = APIRouter(tags=["screener"])


@router.get("/screener", response_model=list[ScreenerRow])
def get_screener(
    kind: Literal["stock", "etf"] | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScreenerRow]:
    return [ScreenerRow.build(row) for row in screener_rows(db, user.id, kind=kind)]
```

`backend/app/api/routes/rankings.py` :
```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import User
from app.repositories.screener import screener_rows
from app.schemas.rankings import HeatmapItem, Movers, TopItem
from app.schemas.screener import ScreenerRow
from app.services.fx import to_eur

router = APIRouter(tags=["rankings"])
HEATMAP_SIZE = 200


def _liquid_eligible_stocks(db: Session, user_id: int) -> list:
    return [
        row for row in screener_rows(db, user_id, kind="stock")
        if row[0].eligibility == "eligible" and row[2] is not None and row[2].liquid
        and row[1] is not None and row[1].change_pct is not None
    ]


@router.get("/rankings/top", response_model=list[TopItem])
def get_top(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TopItem]:
    return [TopItem.build(row) for row in screener_rows(db, user.id, kind="stock", only_top=True, limit=limit)]


@router.get("/rankings/movers", response_model=Movers)
def get_movers(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Movers:
    rows = sorted(_liquid_eligible_stocks(db, user.id), key=lambda r: r[1].change_pct, reverse=True)
    return Movers(
        gainers=[ScreenerRow.build(r) for r in rows[:limit]],
        losers=[ScreenerRow.build(r) for r in reversed(rows[-limit:])],
    )


@router.get("/market/heatmap", response_model=list[HeatmapItem])
def get_heatmap(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[HeatmapItem]:
    items = []
    for security, quote, _score, fundamentals, _fav in _liquid_eligible_stocks(db, user.id):
        cap = to_eur(fundamentals.market_cap, fundamentals.currency) if fundamentals else None
        if cap:
            items.append(HeatmapItem(id=security.id, symbol=security.symbol, name=security.name,
                                     sector=security.sector or "Autres", market_cap_eur=cap,
                                     change_pct=quote.change_pct))
    return sorted(items, key=lambda i: i.market_cap_eur, reverse=True)[:HEATMAP_SIZE]
```

Dans `backend/app/schemas/status.py`, ajouter `id: int` en première ligne de `IndexQuote`. Dans `backend/app/api/routes/status.py`, passer `id=s.id` à la construction de chaque `IndexQuote`.

`backend/app/main.py` (remplacer) :
```python
from fastapi import FastAPI

from app.api.routes import health, rankings, screener, securities, status


def create_app() -> FastAPI:
    app = FastAPI(title="PEA Radar API")
    for module in (health, securities, status, screener, rankings):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
```

- [ ] **Step 5: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tous PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: screener, top 10, movers and heatmap endpoints

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: API — fiche d'un titre (détail, historique, actualités, simulateur, frais)

**Files:**
- Create: `backend/app/schemas/security_detail.py`, `backend/app/api/routes/security_detail.py`, `backend/app/api/routes/fees.py`
- Modify: `backend/app/repositories/market_data.py`, `backend/app/main.py`
- Test: `backend/tests/test_api_security_detail.py`

**Interfaces:**
- Consumes: `screener_rows` (Task 7, filtrée par id), `get_market_provider`, `INTRADAY_CACHE`, `NEWS_CACHE` (Task 7), `sma, rsi, macd` (Task 1), `broker_fee` (Task 2).
- Produces:
  - `market_data.all_daily_prices(session, security_id) -> list[DailyPrice]` (tri croissant).
  - `GET /api/securities/{id}` → `SecurityDetail` (404 si inconnu) : champs de `ScreenerRow` + `isin, industry, eligibility_source, as_of, fundamentals: FundamentalsOut | None, score_detail: ScoreOut | None`.
  - `GET /api/securities/{id}/history?period=1D|1W|1M|6M|1Y|5Y` → `HistoryOut {period, intraday, bars: [{time, open, high, low, close, volume}], sma50, sma200, rsi: [{time, value}], macd: [{time, macd, signal, histogram}]}` ; `time` = `"AAAA-MM-JJ"` (quotidien) ou secondes Unix (intraday).
  - `GET /api/securities/{id}/news` → `list[NewsOut {title, url, publisher, published_at}]`.
  - `GET /api/securities/{id}/simulate?amount>0&period=1W|1M|6M|1Y` → `SimulationOut {start_date, start_price, current_price, shares, invested, buy_fee, sell_fee, current_value, gain, gain_pct, message}`.
  - `GET /api/fees/estimate?amount>=0` → `FeeEstimate {amount, fee, rate}`.

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_api_security_detail.py` :
```python
from datetime import UTC, date, datetime, timedelta

from app.models import DailyPrice, SecurityFundamentals, SecurityQuote
from app.providers.base import IntradayBar, NewsItem
from tests.factories import make_score, make_security

LAST = date(2026, 9, 25)


def with_history(db, days=300, start=100.0, step=1.0):
    security = make_security(db, "MC.PA", name="LVMH", isin="FR0000121014")
    for i in range(days):
        close = start + step * i
        db.add(DailyPrice(security_id=security.id, date=LAST - timedelta(days=days - 1 - i),
                          open=close, high=close, low=close, close=close, volume=10))
    db.flush()
    return security


def test_detail(client, db):
    security = with_history(db)
    db.add(SecurityFundamentals(security_id=security.id, pe=20.0, market_cap=3e11, currency="EUR"))
    make_score(db, security, total=75, components=[
        {"key": "trend", "label": "Tendance", "points": 20, "max_points": 20, "message": "✅", "group": "technical"}])
    body = client.get(f"/api/securities/{security.id}").json()
    assert body["name"] == "LVMH" and body["isin"] == "FR0000121014"
    assert body["fundamentals"]["pe"] == 20.0
    assert body["score_detail"]["total"] == 75
    assert body["score_detail"]["components"][0]["key"] == "trend"


def test_security_detail_404(client):
    assert client.get("/api/securities/999999").status_code == 404


def test_security_page_without_score(client, db):
    security = make_security(db, "NEW.PA")
    body = client.get(f"/api/securities/{security.id}").json()
    assert body["score_detail"] is None and body["fundamentals"] is None and body["price"] is None


def test_history_daily_with_indicators(client, db):
    security = with_history(db)
    body = client.get(f"/api/securities/{security.id}/history", params={"period": "1M"}).json()
    assert body["intraday"] is False
    assert body["bars"][-1]["time"] == "2026-09-25"
    assert 20 <= len(body["bars"]) <= 32
    assert len(body["sma200"]) == len(body["bars"])  # 300 séances : la moyenne 200 jours existe sur tout le mois
    assert body["rsi"][-1]["value"] == 100.0
    assert set(body["macd"][-1]) == {"time", "macd", "signal", "histogram"}


def test_history_5y_returns_everything(client, db):
    security = with_history(db)
    assert len(client.get(f"/api/securities/{security.id}/history", params={"period": "5Y"}).json()["bars"]) == 300


def test_history_intraday(client, db, fake_market):
    security = with_history(db)
    moment = datetime(2026, 9, 25, 7, 0, tzinfo=UTC)
    fake_market.intraday["MC.PA"] = [IntradayBar(moment, 1, 2, 0.5, 1.5, 10)]
    body = client.get(f"/api/securities/{security.id}/history", params={"period": "1D"}).json()
    assert body["intraday"] is True
    assert body["bars"] == [{"time": int(moment.timestamp()), "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}]
    assert fake_market.intraday_calls == [("MC.PA", "1d", "5m")]
    client.get(f"/api/securities/{security.id}/history", params={"period": "1D"})
    assert len(fake_market.intraday_calls) == 1  # servi par le cache


def test_history_intraday_provider_failure(client, db, fake_market):
    security = with_history(db)
    fake_market.fail_on_demand = True
    response = client.get(f"/api/securities/{security.id}/history", params={"period": "1W"})
    assert response.status_code == 200 and response.json()["bars"] == []


def test_history_invalid_period(client, db):
    security = with_history(db)
    assert client.get(f"/api/securities/{security.id}/history", params={"period": "2Y"}).status_code == 422


def test_news(client, db, fake_market):
    security = with_history(db)
    fake_market.news["MC.PA"] = [NewsItem("Titre", "https://ex.com", "Reuters", None)]
    assert client.get(f"/api/securities/{security.id}/news").json() == [
        {"title": "Titre", "url": "https://ex.com", "publisher": "Reuters", "published_at": None}]


def test_news_provider_failure(client, db, fake_market):
    security = with_history(db)
    fake_market.fail_on_demand = True
    response = client.get(f"/api/securities/{security.id}/news")
    assert response.status_code == 200 and response.json() == []


def test_simulate(client, db):
    security = with_history(db)  # le 25/09 : 399 € ; un mois avant (25/08) : 368 €
    db.add(SecurityQuote(security_id=security.id, price=400.0, previous_close=399, change_pct=0.25, volume=1,
                         as_of=datetime(2026, 9, 28, 8, 0, tzinfo=UTC)))
    db.flush()
    body = client.get(f"/api/securities/{security.id}/simulate", params={"amount": 1000, "period": "1M"}).json()
    assert body["start_date"] == "2026-08-25" and body["start_price"] == 368.0
    assert body["shares"] == 2 and body["invested"] == 736.0
    assert body["buy_fee"] == 1.32 and body["current_value"] == 800.0 and body["sell_fee"] == 1.44
    assert body["gain"] == 61.24
    assert body["message"] is None


def test_simulate_amount_below_price(client, db):
    security = with_history(db)
    body = client.get(f"/api/securities/{security.id}/simulate", params={"amount": 50, "period": "1M"}).json()
    assert body["shares"] == 0 and body["gain"] == 0
    assert "ne permet pas" in body["message"]


def test_simulate_rejects_non_positive_amount(client, db):
    security = with_history(db)
    for amount in (0, -100):
        assert client.get(f"/api/securities/{security.id}/simulate", params={"amount": amount, "period": "1M"}).status_code == 422


def test_simulate_without_history(client, db):
    security = make_security(db, "NEW.PA")
    body = client.get(f"/api/securities/{security.id}/simulate", params={"amount": 500, "period": "1Y"}).json()
    assert body["shares"] == 0 and "historique" in body["message"]


def test_fee_estimate(client):
    assert client.get("/api/fees/estimate", params={"amount": 400}).json() == {"amount": 400.0, "fee": 1.92, "rate": 0.0048}
    assert client.get("/api/fees/estimate", params={"amount": -1}).status_code == 422
```

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_api_security_detail.py -q`
Expected: FAIL (404 sur les nouvelles routes).

- [ ] **Step 2: Dépôt**

Ajouter à `backend/app/repositories/market_data.py` :
```python
def all_daily_prices(session: Session, security_id: int) -> list[DailyPrice]:
    return list(session.scalars(
        select(DailyPrice).where(DailyPrice.security_id == security_id).order_by(DailyPrice.date)
    ))
```

- [ ] **Step 3: Schémas**

`backend/app/schemas/security_detail.py` :
```python
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.screener import ScreenerRow


class FundamentalsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pe: float | None
    eps: float | None
    earnings_growth: float | None
    revenue_growth: float | None
    debt_to_equity: float | None
    profit_margin: float | None
    dividend_yield: float | None
    market_cap: float | None
    currency: str | None
    updated_at: datetime | None


class ComponentOut(BaseModel):
    key: str
    label: str
    points: float
    max_points: float
    message: str
    group: str


class ScoreOut(BaseModel):
    total: float | None
    technical: float | None
    fundamental: float | None
    available_ratio: float
    liquid: bool
    eligible_for_top: bool
    history_days: int
    computed_at: datetime
    components: list[ComponentOut]


class SecurityDetail(ScreenerRow):
    isin: str | None
    industry: str | None
    eligibility_source: str
    as_of: datetime | None
    fundamentals: FundamentalsOut | None
    score_detail: ScoreOut | None


class Bar(BaseModel):
    time: str | int
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


class LinePoint(BaseModel):
    time: str
    value: float


class MacdPoint(BaseModel):
    time: str
    macd: float
    signal: float
    histogram: float


class HistoryOut(BaseModel):
    period: str
    intraday: bool
    bars: list[Bar]
    sma50: list[LinePoint]
    sma200: list[LinePoint]
    rsi: list[LinePoint]
    macd: list[MacdPoint]


class NewsOut(BaseModel):
    title: str
    url: str
    publisher: str | None
    published_at: datetime | None


class SimulationOut(BaseModel):
    start_date: date | None
    start_price: float | None
    current_price: float | None
    shares: int
    invested: float
    buy_fee: float
    sell_fee: float
    current_value: float
    gain: float
    gain_pct: float | None
    message: str | None


class FeeEstimate(BaseModel):
    amount: float
    fee: float
    rate: float
```

- [ ] **Step 4: Routes**

`backend/app/api/routes/security_detail.py` :
```python
import logging
import math
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import INTRADAY_CACHE, NEWS_CACHE, get_market_provider
from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import User
from app.providers.base import MarketDataProvider
from app.repositories.market_data import all_daily_prices
from app.repositories.screener import screener_rows
from app.schemas.security_detail import (
    Bar, ComponentOut, FundamentalsOut, HistoryOut, LinePoint, MacdPoint, NewsOut, ScoreOut, SecurityDetail,
    SimulationOut,
)
from app.services.fees import broker_fee
from app.services.indicators import macd, rsi, sma

router = APIRouter(tags=["securities"])
logger = logging.getLogger(__name__)

Period = Literal["1D", "1W", "1M", "6M", "1Y", "5Y"]
INTRADAY = {"1D": ("1d", "5m"), "1W": ("5d", "30m")}
DAILY_WINDOW = {"1M": 31, "6M": 183, "1Y": 365, "5Y": None}
SIMULATION_WINDOW = {"1W": 7, "1M": 31, "6M": 183, "1Y": 365}


def _row_or_404(db: Session, user_id: int, security_id: int):
    rows = [r for r in screener_rows(db, user_id) if r[0].id == security_id]
    rows = rows or [r for r in screener_rows(db, user_id, kind="index") if r[0].id == security_id]
    if not rows:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    return rows[0]


@router.get("/securities/{security_id}", response_model=SecurityDetail)
def get_security(security_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SecurityDetail:
    row = _row_or_404(db, user.id, security_id)
    security, quote, score, fundamentals, _ = row
    score_detail = None
    if score is not None:
        score_detail = ScoreOut(
            total=score.total, technical=score.technical, fundamental=score.fundamental,
            available_ratio=score.available_ratio, liquid=score.liquid, eligible_for_top=score.eligible_for_top,
            history_days=score.history_days, computed_at=score.computed_at,
            components=[ComponentOut(**c) for c in score.components or []],
        )
    return SecurityDetail(
        **SecurityDetail.fields_from(row),
        isin=security.isin, industry=security.industry, eligibility_source=security.eligibility_source,
        as_of=quote.as_of if quote else None,
        fundamentals=FundamentalsOut.model_validate(fundamentals) if fundamentals else None,
        score_detail=score_detail,
    )


def _intraday(provider: MarketDataProvider, ticker: str, period: str) -> list[Bar]:
    yahoo_period, interval = INTRADAY[period]

    def load() -> list[Bar]:
        return [Bar(time=int(b.time.timestamp()), open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume)
                for b in provider.get_intraday(ticker, yahoo_period, interval)]

    try:
        return INTRADAY_CACHE.get_or_set((ticker, period), load)
    except Exception:
        logger.warning("Intraday indisponible pour %s", ticker, exc_info=True)
        return []


@router.get("/securities/{security_id}/history", response_model=HistoryOut)
def get_history(
    security_id: int,
    period: Period = "6M",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: MarketDataProvider = Depends(get_market_provider),
) -> HistoryOut:
    security = _row_or_404(db, user.id, security_id)[0]
    if period in INTRADAY:
        return HistoryOut(period=period, intraday=True, bars=_intraday(provider, security.yahoo_ticker, period),
                          sma50=[], sma200=[], rsi=[], macd=[])
    prices = all_daily_prices(db, security_id)
    closes = [p.close for p in prices]
    days = DAILY_WINDOW[period]
    start = 0
    if days is not None and prices:
        first_day = prices[-1].date - timedelta(days=days)
        start = next((i for i, p in enumerate(prices) if p.date >= first_day), len(prices))
    times = [p.date.isoformat() for p in prices]

    def line(values: list[float | None]) -> list[LinePoint]:
        return [LinePoint(time=times[i], value=v) for i, v in enumerate(values) if i >= start and v is not None]

    macd_values = macd(closes)
    return HistoryOut(
        period=period, intraday=False,
        bars=[Bar(time=times[i], open=p.open, high=p.high, low=p.low, close=p.close, volume=p.volume)
              for i, p in enumerate(prices) if i >= start],
        sma50=line(sma(closes, 50)), sma200=line(sma(closes, 200)), rsi=line(rsi(closes)),
        macd=[MacdPoint(time=times[i], macd=m, signal=s, histogram=h)
              for i, (m, s, h) in enumerate(zip(macd_values.macd, macd_values.signal, macd_values.histogram))
              if i >= start and m is not None and s is not None and h is not None],
    )


@router.get("/securities/{security_id}/news", response_model=list[NewsOut])
def get_news(
    security_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: MarketDataProvider = Depends(get_market_provider),
) -> list[NewsOut]:
    ticker = _row_or_404(db, user.id, security_id)[0].yahoo_ticker
    try:
        items = NEWS_CACHE.get_or_set(ticker, lambda: provider.get_news(ticker))
    except Exception:
        logger.warning("Actualités indisponibles pour %s", ticker, exc_info=True)
        return []
    return [NewsOut(title=i.title, url=i.url, publisher=i.publisher, published_at=i.published_at) for i in items[:10]]


@router.get("/securities/{security_id}/simulate", response_model=SimulationOut)
def simulate(
    security_id: int,
    amount: float = Query(..., gt=0, le=1_000_000),
    period: Literal["1W", "1M", "6M", "1Y"] = "1M",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SimulationOut:
    row = _row_or_404(db, user.id, security_id)
    quote = row[1]
    prices = all_daily_prices(db, security_id)
    empty = dict(shares=0, invested=0.0, buy_fee=0.0, sell_fee=0.0, current_value=0.0, gain=0.0, gain_pct=None)
    if not prices:
        return SimulationOut(start_date=None, start_price=None, current_price=None,
                             message="Pas assez d'historique pour simuler cet achat.", **empty)
    first_day = prices[-1].date - timedelta(days=SIMULATION_WINDOW[period])
    start = next((p for p in prices if p.date >= first_day), prices[0])
    current_price = quote.price if quote else prices[-1].close
    shares = math.floor(amount / start.close) if start.close > 0 else 0
    if shares == 0:
        return SimulationOut(
            start_date=start.date, start_price=start.close, current_price=current_price,
            message=f"Le montant ne permet pas d'acheter une action (cours de {start.close:.2f} €).".replace(".", ",", 1),
            **empty,
        )
    invested = round(shares * start.close, 2)
    buy_fee, _ = broker_fee(invested)
    current_value = round(shares * current_price, 2)
    sell_fee, _ = broker_fee(current_value)
    gain = round(current_value - sell_fee - invested - buy_fee, 2)
    return SimulationOut(
        start_date=start.date, start_price=start.close, current_price=current_price, shares=shares,
        invested=invested, buy_fee=buy_fee, sell_fee=sell_fee, current_value=current_value, gain=gain,
        gain_pct=round(gain / (invested + buy_fee) * 100, 2), message=None,
    )
```

`backend/app/api/routes/fees.py` :
```python
from fastapi import APIRouter, Query

from app.schemas.security_detail import FeeEstimate
from app.services.fees import broker_fee

router = APIRouter(tags=["fees"])


@router.get("/fees/estimate", response_model=FeeEstimate)
def estimate_fee(amount: float = Query(..., ge=0, le=1_000_000)) -> FeeEstimate:
    fee, rate = broker_fee(amount)
    return FeeEstimate(amount=amount, fee=fee, rate=rate)
```

Dans `backend/app/main.py`, importer `fees, security_detail` et les ajouter au tuple des routeurs, **`security_detail` avant `securities`** n'est pas nécessaire (chemins distincts) : `(health, securities, security_detail, status, screener, rankings, fees)`.

- [ ] **Step 5: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tous PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: security detail, history with indicators, news, simulator and fee estimate endpoints

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: API — favoris et corrections d'éligibilité

**Files:**
- Create: `backend/app/api/routes/favorites.py`
- Modify: `backend/app/repositories/securities.py`, `backend/app/schemas/securities.py`, `backend/app/api/routes/securities.py`, `backend/app/main.py`
- Test: `backend/tests/test_api_favorites_eligibility.py`

**Interfaces:**
- Consumes: `get_current_user` (lot 1), `_apply_eligibility` (lot 1, rendu utilisable via une fonction publique).
- Produces:
  - `PUT /api/favorites/{security_id}` et `DELETE /api/favorites/{security_id}` → 204 (idempotents ; 404 si titre inconnu).
  - `PATCH /api/securities/{security_id}/eligibility` corps `{"override": "eligible" | "non_eligible" | null}` → `SecurityItem`.
  - `GET /api/securities?overridden=true` → uniquement les titres corrigés.
  - `SecurityItem` gagne `eligibility_source` et `eligibility_override`.
  - `repositories.securities.set_eligibility_override(security, override) -> None`.

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_api_favorites_eligibility.py` :
```python
from app.core.current_user import ensure_default_user
from app.models import Favorite, Security
from tests.factories import make_security


def test_add_and_remove_favorite(client, db):
    security = make_security(db, "MC.PA")
    user = ensure_default_user(db)
    assert client.put(f"/api/favorites/{security.id}").status_code == 204
    assert client.put(f"/api/favorites/{security.id}").status_code == 204  # idempotent
    assert db.get(Favorite, (user.id, security.id)) is not None
    assert client.delete(f"/api/favorites/{security.id}").status_code == 204
    assert client.delete(f"/api/favorites/{security.id}").status_code == 204
    assert db.get(Favorite, (user.id, security.id)) is None


def test_favorite_unknown_security(client):
    assert client.put("/api/favorites/999999").status_code == 404


def test_override_and_reset_eligibility(client, db):
    security = make_security(db, "GFC.PA")
    security.industry = "REIT - Office"
    db.flush()
    body = client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "eligible"}).json()
    assert (body["eligibility"], body["eligibility_source"], body["eligibility_override"]) == ("eligible", "override", "eligible")
    body = client.patch(f"/api/securities/{security.id}/eligibility", json={"override": None}).json()
    assert (body["eligibility"], body["eligibility_source"], body["eligibility_override"]) == ("a_verifier", "auto", None)


def test_override_on_etf_resets_to_seed(client, db):
    etf = make_security(db, "CW8.PA", kind="etf")
    client.patch(f"/api/securities/{etf.id}/eligibility", json={"override": "non_eligible"})
    body = client.patch(f"/api/securities/{etf.id}/eligibility", json={"override": None}).json()
    assert (body["eligibility"], body["eligibility_source"]) == ("eligible", "seed")


def test_override_validation(client, db):
    security = make_security(db, "MC.PA")
    assert client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "peut-être"}).status_code == 422
    assert client.patch("/api/securities/999999/eligibility", json={"override": None}).status_code == 404


def test_list_overridden_only(client, db):
    a = make_security(db, "A.PA")
    make_security(db, "B.PA")
    client.patch(f"/api/securities/{a.id}/eligibility", json={"override": "non_eligible"})
    items = client.get("/api/securities", params={"overridden": "true"}).json()["items"]
    assert [i["symbol"] for i in items] == ["A"]
```

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest tests/test_api_favorites_eligibility.py -q`
Expected: FAIL.

- [ ] **Step 2: Dépôt**

Dans `backend/app/repositories/securities.py` :
- ajouter l'import `from app.services.eligibility.rules import ELIGIBLE, NOT_ELIGIBLE` (en complétant la ligne existante d'import des règles) ;
- ajouter :
```python
_FIXED_BY_KIND = {"etf": ELIGIBLE, "index": NOT_ELIGIBLE}


def set_eligibility_override(security: Security, override: str | None) -> None:
    """Correction manuelle (None = revenir au calcul automatique ou à la liste de départ)."""
    security.eligibility_override = override
    _apply_eligibility(security, _FIXED_BY_KIND.get(security.kind))
```
- ajouter le paramètre `overridden: bool = False` à `search_securities` (après `eligibility`) et, après le filtre d'éligibilité :
```python
    if overridden:
        stmt = stmt.where(Security.eligibility_override.is_not(None))
```

- [ ] **Step 3: Schéma et routes**

Dans `backend/app/schemas/securities.py`, ajouter à `SecurityItem` les champs `eligibility_source: str` et `eligibility_override: str | None` (après `eligibility`) et, dans `build`, `eligibility_source=security.eligibility_source, eligibility_override=security.eligibility_override`. Ajouter :
```python
class EligibilityUpdate(BaseModel):
    override: Literal["eligible", "non_eligible"] | None
```
(avec `from typing import Literal`).

Dans `backend/app/api/routes/securities.py` :
- ajouter le paramètre de requête `overridden: bool = False` à `list_securities` et le transmettre à `search_securities(..., overridden=overridden, ...)` ;
- ajouter :
```python
@router.patch("/securities/{security_id}/eligibility", response_model=SecurityItem)
def update_eligibility(security_id: int, update: EligibilityUpdate, db: Session = Depends(get_db)) -> SecurityItem:
    security = db.get(Security, security_id)
    if security is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    set_eligibility_override(security, update.override)
    db.commit()
    quote = db.get(SecurityQuote, security_id)
    return SecurityItem.build(security, quote)
```
(imports : `HTTPException`, `Security`, `SecurityQuote`, `set_eligibility_override`, `EligibilityUpdate`).

`backend/app/api/routes/favorites.py` :
```python
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import Favorite, Security, User

router = APIRouter(tags=["favorites"])


def _ensure_security(db: Session, security_id: int) -> None:
    if db.get(Security, security_id) is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")


@router.put("/favorites/{security_id}", status_code=204)
def add_favorite(security_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    _ensure_security(db, security_id)
    if db.get(Favorite, (user.id, security_id)) is None:
        db.add(Favorite(user_id=user.id, security_id=security_id))
        db.commit()
    return Response(status_code=204)


@router.delete("/favorites/{security_id}", status_code=204)
def remove_favorite(security_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    favorite = db.get(Favorite, (user.id, security_id))
    if favorite is not None:
        db.delete(favorite)
        db.commit()
    return Response(status_code=204)
```

Dans `backend/app/main.py`, ajouter `favorites` au tuple des routeurs.

- [ ] **Step 4: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tous PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: favorites and manual eligibility override endpoints

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Fondations frontend (types, composants partagés, favoris)

**Files:**
- Create: `frontend/src/lib/colors.ts`, `frontend/src/components/Sparkline.tsx`, `frontend/src/components/ScoreGauge.tsx`, `frontend/src/components/FavoriteButton.tsx`, `frontend/src/components/charts/EChart.tsx`, `frontend/src/features/favorites/useToggleFavorite.ts`
- Modify: `frontend/package.json`, `frontend/src/lib/api/schema.d.ts` (régénéré), `frontend/src/lib/api/client.ts`, `frontend/src/lib/format.ts`
- Test: `frontend/src/components/shared.test.tsx`, `frontend/src/lib/format.test.ts`, `frontend/src/lib/colors.test.ts`

**Interfaces:**
- Produces:
  - `client.ts` : `apiSend(method: "PUT" | "DELETE" | "PATCH", path, body?) -> Promise<unknown>` ; types `ScreenerRow, TopItem, Movers, HeatmapItem, SecurityDetail, HistoryOut, NewsOut, SimulationOut, FeeEstimate, ComponentOut`.
  - `format.ts` : `formatRatioPct(fraction)`, `formatCompactEur(value)`, `formatDate(isoDate)`, `formatNumber(value, digits=2)`.
  - `colors.ts` : `changeColor(pct: number | null) -> string` (gris à 0, vert/rouge saturés à ±3 %), `scoreColor(score: number | null) -> string`.
  - `<Sparkline values={number[]} width? height? />`, `<ScoreGauge score={number | null} size? />`, `<FavoriteButton securityId isFavorite />`, `<EChart option className onItemClick? />`.
  - `useToggleFavorite()` → mutation `{ securityId, favorite }` qui invalide `screener`, `top`, `security`.

- [ ] **Step 1: Dépendances et types**

Run (dans `frontend/`) :
```bash
npm install lightweight-charts echarts @tanstack/react-table @tanstack/react-virtual
```
Run (racine) : `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db api`, puis (dans `frontend/`) `npm run gen:api`.
Expected: `schema.d.ts` contient `ScreenerRow`, `TopItem`, `SecurityDetail`, `HistoryOut`, `SimulationOut`.

- [ ] **Step 2: Tests (échouent)**

Ajouter à `frontend/src/lib/format.test.ts` :
```ts
import { formatCompactEur, formatDate, formatRatioPct } from "./format";

test("formatRatioPct convertit une fraction", () => {
  expect(formatRatioPct(0.0328)).toMatch(/^3,28\s%$/u);
  expect(formatRatioPct(null)).toBe("—");
});

test("formatCompactEur", () => {
  expect(formatCompactEur(195_600_000_000)).toMatch(/^195,6\sMd\s€$/u);
  expect(formatCompactEur(undefined)).toBe("—");
});

test("formatDate", () => {
  expect(formatDate("2026-09-25")).toBe("25/09/2026");
});
```

`frontend/src/lib/colors.test.ts` :
```ts
import { changeColor, scoreColor } from "./colors";

test("changeColor", () => {
  expect(changeColor(0)).toBe("rgb(228, 228, 231)");
  expect(changeColor(3)).toBe("rgb(22, 163, 74)");
  expect(changeColor(10)).toBe("rgb(22, 163, 74)");
  expect(changeColor(-3)).toBe("rgb(220, 38, 38)");
  expect(changeColor(null)).toBe("rgb(228, 228, 231)");
});

test("scoreColor", () => {
  expect(scoreColor(80)).toBe("#16a34a");
  expect(scoreColor(55)).toBe("#d97706");
  expect(scoreColor(30)).toBe("#dc2626");
  expect(scoreColor(null)).toBe("#a1a1aa");
});
```

`frontend/src/components/shared.test.tsx` :
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { FavoriteButton } from "./FavoriteButton";
import { ScoreGauge } from "./ScoreGauge";
import { Sparkline } from "./Sparkline";

afterEach(() => vi.unstubAllGlobals());

test("Sparkline trace une courbe verte si la série monte", () => {
  const { container } = render(<Sparkline values={[1, 3, 2, 4]} />);
  const line = container.querySelector("polyline")!;
  expect(line.getAttribute("points")!.split(" ")).toHaveLength(4);
  expect(line).toHaveAttribute("stroke", "#16a34a");
});

test("Sparkline vide ne dessine rien", () => {
  const { container } = render(<Sparkline values={[]} />);
  expect(container.querySelector("polyline")).toBeNull();
});

test("ScoreGauge affiche le score arrondi", () => {
  render(<ScoreGauge score={72.6} />);
  expect(screen.getByLabelText("Score 73 sur 100")).toHaveTextContent("73");
});

test("ScoreGauge sans score", () => {
  render(<ScoreGauge score={null} />);
  expect(screen.getByLabelText("Score indisponible")).toHaveTextContent("—");
});

test("FavoriteButton ajoute puis retire", async () => {
  const fetchMock = mockFetch(() => ({ status: 204, body: null }));
  const { rerender } = renderWithProviders(<FavoriteButton securityId={7} isFavorite={false} />);
  await userEvent.click(screen.getByRole("button", { name: "Ajouter aux favoris" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/favorites/7", expect.objectContaining({ method: "PUT" })));
  rerender(<FavoriteButton securityId={7} isFavorite />);
  await userEvent.click(screen.getByRole("button", { name: "Retirer des favoris" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/favorites/7", expect.objectContaining({ method: "DELETE" })));
});
```

Le `rerender` de `renderWithProviders` doit garder les fournisseurs : modifier `frontend/src/test/utils.tsx` pour que `renderWithProviders` passe `wrapper` à `render` :
```tsx
export function renderWithProviders(ui: ReactElement, { route = "/" }: { route?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  return render(ui, { wrapper: Wrapper });
}
```
(import `type ReactNode`). Et `mockFetch` doit accepter une réponse sans corps pour 204 : remplacer la construction de la réponse par
`return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });`

Run (dans `frontend/`) : `npm test`
Expected: FAIL (modules introuvables).

- [ ] **Step 3: Implémenter**

Ajouter à `frontend/src/lib/api/client.ts` :
```ts
export type ScreenerRow = components["schemas"]["ScreenerRow"];
export type TopItem = components["schemas"]["TopItem"];
export type Movers = components["schemas"]["Movers"];
export type HeatmapItem = components["schemas"]["HeatmapItem"];
export type SecurityDetail = components["schemas"]["SecurityDetail"];
export type HistoryOut = components["schemas"]["HistoryOut"];
export type NewsOut = components["schemas"]["NewsOut"];
export type SimulationOut = components["schemas"]["SimulationOut"];
export type FeeEstimate = components["schemas"]["FeeEstimate"];
export type ComponentOut = components["schemas"]["ComponentOut"];

export async function apiSend(method: "PUT" | "DELETE" | "PATCH", path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(path, {
    method,
    headers: { Accept: "application/json", ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new ApiError(response.status, `Erreur ${response.status} sur ${path}`);
  return response.status === 204 ? null : response.json();
}
```

Ajouter à `frontend/src/lib/format.ts` :
```ts
const compact = new Intl.NumberFormat("fr-FR", { notation: "compact", maximumFractionDigits: 1 });

export function formatNumber(value: number | null | undefined, digits = 2): string {
  return value == null ? "—" : new Intl.NumberFormat("fr-FR", { maximumFractionDigits: digits }).format(value);
}

export function formatRatioPct(fraction: number | null | undefined): string {
  return fraction == null ? "—" : `${number2.format(fraction * 100)} %`;
}

export function formatCompactEur(value: number | null | undefined): string {
  return value == null ? "—" : `${compact.format(value)} €`;
}

export function formatDate(isoDate: string | null | undefined): string {
  if (!isoDate) return "—";
  const [year, month, day] = isoDate.slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
}
```

`frontend/src/lib/colors.ts` :
```ts
const NEUTRAL = [228, 228, 231];
const UP = [22, 163, 74];
const DOWN = [220, 38, 38];

export function changeColor(pct: number | null | undefined): string {
  const value = Math.max(-3, Math.min(3, pct ?? 0));
  const target = value >= 0 ? UP : DOWN;
  const t = Math.abs(value) / 3;
  const mix = NEUTRAL.map((c, i) => Math.round(c + (target[i] - c) * t));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "#a1a1aa";
  if (score >= 70) return "#16a34a";
  if (score >= 50) return "#d97706";
  return "#dc2626";
}
```

`frontend/src/components/Sparkline.tsx` :
```tsx
export function Sparkline({ values, width = 96, height = 28 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return <svg width={width} height={height} aria-hidden />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values
    .map((v, i) => `${((i / (values.length - 1)) * width).toFixed(1)},${(height - 2 - ((v - min) / range) * (height - 4)).toFixed(1)}`)
    .join(" ");
  const color = values[values.length - 1] >= values[0] ? "#16a34a" : "#dc2626";
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
```

`frontend/src/components/ScoreGauge.tsx` :
```tsx
import { scoreColor } from "@/lib/colors";

export function ScoreGauge({ score, size = 44 }: { score: number | null | undefined; size?: number }) {
  const radius = size / 2 - 4;
  const circumference = 2 * Math.PI * radius;
  const value = score == null ? 0 : Math.max(0, Math.min(100, score));
  const label = score == null ? "Score indisponible" : `Score ${Math.round(value)} sur 100`;
  return (
    <div aria-label={label} role="img" className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e4e4e7" strokeWidth={4} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={scoreColor(score)} strokeWidth={4}
          strokeDasharray={circumference} strokeDashoffset={circumference * (1 - value / 100)} strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-xs font-semibold">{score == null ? "—" : Math.round(value)}</span>
    </div>
  );
}
```

`frontend/src/features/favorites/useToggleFavorite.ts` :
```ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiSend } from "@/lib/api/client";

export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ securityId, favorite }: { securityId: number; favorite: boolean }) =>
      apiSend(favorite ? "PUT" : "DELETE", `/api/favorites/${securityId}`),
    onSettled: () => {
      for (const key of ["screener", "top", "security"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
}
```

`frontend/src/components/FavoriteButton.tsx` :
```tsx
import { Star } from "lucide-react";
import { useToggleFavorite } from "@/features/favorites/useToggleFavorite";
import { cn } from "@/lib/utils";

export function FavoriteButton({ securityId, isFavorite }: { securityId: number; isFavorite: boolean }) {
  const toggle = useToggleFavorite();
  return (
    <button
      type="button"
      aria-pressed={isFavorite}
      aria-label={isFavorite ? "Retirer des favoris" : "Ajouter aux favoris"}
      onClick={(event) => {
        event.stopPropagation();
        toggle.mutate({ securityId, favorite: !isFavorite });
      }}
      className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-amber-500"
    >
      <Star className={cn("size-4", isFavorite && "fill-amber-400 text-amber-500")} />
    </button>
  );
}
```

`frontend/src/components/charts/EChart.tsx` :
```tsx
import { useEffect, useRef } from "react";
import { TreemapChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([TreemapChart, TooltipComponent, CanvasRenderer]);

type Props = {
  option: echarts.EChartsCoreOption;
  className?: string;
  onItemClick?: (data: unknown) => void;
};

export function EChart({ option, className, onItemClick }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const element = ref.current!;
    const chart = echarts.init(element);
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onItemClick) return;
    const handler = (params: { data?: unknown }) => onItemClick(params.data);
    chart.on("click", handler);
    return () => {
      chart.off("click", handler);
    };
  }, [onItemClick]);

  return <div ref={ref} className={className} />;
}
```

- [ ] **Step 4: Vérifier**

Run (dans `frontend/`) : `npm test && npm run build`
Expected: tests verts, build sans erreur.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: shared frontend building blocks (sparkline, score gauge, favorites, echarts wrapper)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Page d'accueil

**Files:**
- Create: `frontend/src/features/home/HomePage.tsx`, `IndicesBar.tsx`, `TopList.tsx`, `Movers.tsx`, `MarketHeatmap.tsx`, `heatmapOption.ts`
- Modify: `frontend/src/app/router.tsx`
- Test: `frontend/src/features/home/HomePage.test.tsx`, `frontend/src/features/home/heatmapOption.test.ts`

**Interfaces:**
- Consumes: `/api/status` (indices avec `id`), `/api/rankings/top`, `/api/rankings/movers`, `/api/market/heatmap`, `/api/securities/{id}/history?period=1D` ; `Sparkline`, `ScoreGauge`, `FavoriteButton`, `EChart`, `changeColor` (Task 10).
- Produces: `HomePage` (titre h1 « Accueil ») ; `buildHeatmapOption(items: HeatmapItem[]) -> EChartsCoreOption` ; route `/` chargée à la demande.

- [ ] **Step 1: Tests (échouent)**

`frontend/src/features/home/heatmapOption.test.ts` :
```ts
import { buildHeatmapOption } from "./heatmapOption";

test("regroupe par secteur et colore selon la variation", () => {
  const option = buildHeatmapOption([
    { id: 1, symbol: "MC", name: "LVMH", sector: "Luxe", market_cap_eur: 300, change_pct: 3 },
    { id: 2, symbol: "RMS", name: "Hermès", sector: "Luxe", market_cap_eur: 200, change_pct: -3 },
    { id: 3, symbol: "TTE", name: "TotalEnergies", sector: "Énergie", market_cap_eur: 100, change_pct: 0 },
  ]) as { series: { data: { name: string; children: { name: string; value: number; itemStyle: { color: string } }[] }[] }[] };
  const sectors = option.series[0].data;
  expect(sectors.map((s) => s.name)).toEqual(["Luxe", "Énergie"]);
  expect(sectors[0].children[0]).toMatchObject({ name: "MC", value: 300, itemStyle: { color: "rgb(22, 163, 74)" } });
  expect(sectors[0].children[1].itemStyle.color).toBe("rgb(220, 38, 38)");
});
```

`frontend/src/features/home/HomePage.test.tsx` :
```tsx
import { screen } from "@testing-library/react";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { HomePage } from "./HomePage";

vi.mock("@/components/charts/EChart", () => ({ EChart: () => <div data-testid="echart" /> }));
afterEach(() => vi.unstubAllGlobals());

const row = (id: number, symbol: string, name: string, change: number) => ({
  id, yahoo_ticker: `${symbol}.PA`, symbol, name, kind: "stock", market: "Euronext Paris", country: "FR", sector: "Luxe",
  eligibility: "eligible", price: 100, change_pct: change, perf_1w: 1, perf_1m: 2, perf_1y: 3, score: 80, pe: 15,
  dividend_yield: 0.02, liquid: true, is_favorite: false, sparkline: [1, 2, 3],
});

function api(top: unknown[]) {
  return mockFetch((url) => {
    if (url.startsWith("/api/rankings/top")) return { body: top };
    if (url.startsWith("/api/rankings/movers")) return { body: { gainers: [row(3, "AIR", "Airbus", 4.2)], losers: [row(4, "KER", "Kering", -3.1)] } };
    if (url.startsWith("/api/market/heatmap")) return { body: [] };
    if (url.startsWith("/api/status")) return { body: { market_open: true, jobs: [], indices: [{ id: 9, yahoo_ticker: "^FCHI", name: "CAC 40", price: 7500, change_pct: 0.8, as_of: null }] } };
    return { body: { period: "1D", intraday: true, bars: [], sma50: [], sma200: [], rsi: [], macd: [] } };
  });
}

test("affiche le top 10 avec raisons, les indices et les mouvements", async () => {
  api([{ ...row(1, "MC", "LVMH", 2.1), technical: 80, fundamental: 70, reasons: ["✅ Tendance haussière", "✅ Dividende de 2 %", "⚠️ RSI"] }]);
  renderWithProviders(<HomePage />);
  expect(screen.getByRole("heading", { level: 1, name: "Accueil" })).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: /LVMH/ })).toHaveAttribute("href", "/titres/1");
  expect(screen.getByText("✅ Tendance haussière")).toBeInTheDocument();
  expect(await screen.findByText("CAC 40")).toBeInTheDocument();
  expect(await screen.findByText("Airbus")).toBeInTheDocument();
  expect(screen.getByText("Kering")).toBeInTheDocument();
});

test("test_home_empty_state : message d'attente sans classement", async () => {
  api([]);
  renderWithProviders(<HomePage />);
  expect(await screen.findByText(/Le classement sera disponible/)).toBeInTheDocument();
});
```

Run (dans `frontend/`) : `npm test`
Expected: FAIL (modules introuvables).

- [ ] **Step 2: Implémenter**

`frontend/src/features/home/heatmapOption.ts` :
```ts
import type { HeatmapItem } from "@/lib/api/client";
import { changeColor } from "@/lib/colors";
import { formatPct } from "@/lib/format";

type Leaf = { name: string; value: number; id: number; fullName: string; change: number; itemStyle: { color: string } };

export function buildHeatmapOption(items: HeatmapItem[]) {
  const sectors = new Map<string, Leaf[]>();
  for (const item of items) {
    const leaves = sectors.get(item.sector) ?? [];
    leaves.push({ name: item.symbol, value: item.market_cap_eur, id: item.id, fullName: item.name, change: item.change_pct,
                  itemStyle: { color: changeColor(item.change_pct) } });
    sectors.set(item.sector, leaves);
  }
  return {
    tooltip: {
      formatter: (info: { data?: Partial<Leaf> & { name: string } }) =>
        info.data?.fullName ? `${info.data.fullName}<br/>${formatPct(info.data.change)}` : info.data?.name ?? "",
    },
    series: [{
      type: "treemap",
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      width: "100%",
      height: "100%",
      label: { show: true, formatter: "{b}", fontSize: 11, color: "#18181b" },
      upperLabel: { show: true, height: 18, color: "#52525b", fontSize: 11 },
      levels: [
        { itemStyle: { borderColor: "#ffffff", borderWidth: 2, gapWidth: 2 } },
        { itemStyle: { borderColor: "#ffffff", borderWidth: 1, gapWidth: 1 } },
      ],
      data: [...sectors.entries()].map(([name, children]) => ({ name, children })),
    }],
  };
}
```

`frontend/src/features/home/IndicesBar.tsx` :
```tsx
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Sparkline } from "@/components/Sparkline";
import { apiGet, type HistoryOut, type StatusResponse } from "@/lib/api/client";
import { formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

function IndexCard({ index }: { index: StatusResponse["indices"][number] }) {
  const { data } = useQuery({
    queryKey: ["history", index.id, "1D"],
    queryFn: () => apiGet<HistoryOut>(`/api/securities/${index.id}/history`, { period: "1D" }),
    refetchInterval: 120_000,
  });
  const change = index.change_pct ?? 0;
  return (
    <Card className="flex flex-row items-center justify-between gap-4 px-5 py-4">
      <div>
        <p className="text-sm font-medium text-muted-foreground">{index.name}</p>
        <p className="mt-0.5 text-lg font-semibold">{formatPrice(index.price)}</p>
        <p className={cn("text-sm font-medium", change > 0 && "text-up", change < 0 && "text-down")}>{formatPct(index.change_pct)}</p>
      </div>
      <Sparkline values={(data?.bars ?? []).map((b) => b.close)} width={110} height={40} />
    </Card>
  );
}

export function IndicesBar() {
  const { data } = useQuery({ queryKey: ["status"], queryFn: () => apiGet<StatusResponse>("/api/status"), refetchInterval: 60_000 });
  if (!data?.indices.length) return null;
  return (
    <div className="grid grid-cols-3 gap-4">
      {data.indices.map((index) => <IndexCard key={index.id} index={index} />)}
    </div>
  );
}
```

`frontend/src/features/home/TopList.tsx` :
```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FavoriteButton } from "@/components/FavoriteButton";
import { ScoreGauge } from "@/components/ScoreGauge";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkline } from "@/components/Sparkline";
import { apiGet, type TopItem } from "@/lib/api/client";
import { formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

export function TopList() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["top"],
    queryFn: () => apiGet<TopItem[]>("/api/rankings/top", { limit: 10 }),
    refetchInterval: 60_000,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">🏆 Top 10 du moment</CardTitle>
        <p className="text-sm text-muted-foreground">Actions éligibles PEA les mieux notées par le score mixte (technique + fondamentaux).</p>
      </CardHeader>
      <CardContent className="px-0">
        {isPending ? (
          <div className="space-y-3 px-6">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
        ) : isError ? (
          <p role="alert" className="px-6 text-sm text-down">Impossible de charger le classement.</p>
        ) : data.length === 0 ? (
          <p className="px-6 text-sm text-muted-foreground">
            Le classement sera disponible une fois les données chargées (quelques minutes au premier démarrage).
          </p>
        ) : (
          <ol className="divide-y divide-border">
            {data.map((item, index) => (
              <li key={item.id} className="flex items-center gap-4 px-6 py-3">
                <span className="w-5 text-sm font-semibold text-muted-foreground">{index + 1}</span>
                <ScoreGauge score={item.score} />
                <div className="min-w-0 flex-1">
                  <Link to={`/titres/${item.id}`} className="font-medium hover:text-primary">
                    {item.name} <span className="text-xs font-normal text-muted-foreground">{item.symbol}</span>
                  </Link>
                  <ul className="mt-1 flex flex-wrap gap-1.5">
                    {item.reasons.map((reason) => (
                      <li key={reason} className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">{reason}</li>
                    ))}
                  </ul>
                </div>
                <Sparkline values={item.sparkline} />
                <div className="w-24 text-right">
                  <p className="font-medium">{formatPrice(item.price)}</p>
                  <p className={cn("text-xs font-medium", (item.change_pct ?? 0) > 0 && "text-up", (item.change_pct ?? 0) < 0 && "text-down")}>
                    {formatPct(item.change_pct)}
                  </p>
                </div>
                <FavoriteButton securityId={item.id} isFavorite={item.is_favorite} />
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/home/Movers.tsx` :
```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type Movers as MoversData, type ScreenerRow } from "@/lib/api/client";
import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

function MoverList({ title, rows }: { title: string; rows: ScreenerRow[] }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <ul className="space-y-1.5">
        {rows.map((row) => (
          <li key={row.id} className="flex items-center justify-between text-sm">
            <Link to={`/titres/${row.id}`} className="truncate hover:text-primary">{row.name}</Link>
            <span className={cn("font-medium", (row.change_pct ?? 0) >= 0 ? "text-up" : "text-down")}>{formatPct(row.change_pct)}</span>
          </li>
        ))}
        {rows.length === 0 && <li className="text-sm text-muted-foreground">—</li>}
      </ul>
    </div>
  );
}

export function Movers() {
  const { data } = useQuery({ queryKey: ["movers"], queryFn: () => apiGet<MoversData>("/api/rankings/movers", { limit: 5 }), refetchInterval: 60_000 });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">🔥 Hausses et baisses du jour</CardTitle></CardHeader>
      <CardContent className="space-y-5">
        <MoverList title="Plus fortes hausses" rows={data?.gainers ?? []} />
        <MoverList title="Plus fortes baisses" rows={data?.losers ?? []} />
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/home/MarketHeatmap.tsx` :
```tsx
import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { EChart } from "@/components/charts/EChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type HeatmapItem } from "@/lib/api/client";
import { buildHeatmapOption } from "./heatmapOption";

export function MarketHeatmap() {
  const navigate = useNavigate();
  const { data } = useQuery({ queryKey: ["heatmap"], queryFn: () => apiGet<HeatmapItem[]>("/api/market/heatmap"), refetchInterval: 120_000 });
  const option = useMemo(() => buildHeatmapOption(data ?? []), [data]);
  const onItemClick = useCallback((item: unknown) => {
    const id = (item as { id?: number } | undefined)?.id;
    if (id) navigate(`/titres/${id}`);
  }, [navigate]);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Carte du marché</CardTitle>
        <p className="text-sm text-muted-foreground">Taille = capitalisation · couleur = variation du jour. Cliquez sur une case pour ouvrir la fiche.</p>
      </CardHeader>
      <CardContent>
        <EChart option={option} onItemClick={onItemClick} className="h-[420px] w-full" />
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/home/HomePage.tsx` :
```tsx
import { IndicesBar } from "./IndicesBar";
import { MarketHeatmap } from "./MarketHeatmap";
import { Movers } from "./Movers";
import { TopList } from "./TopList";

export function HomePage() {
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Accueil</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Les actions à surveiller aujourd'hui. Outil d'aide à la décision, pas un conseil en investissement.
        </p>
      </header>
      <IndicesBar />
      <div className="grid grid-cols-[2fr_1fr] gap-6">
        <TopList />
        <Movers />
      </div>
      <MarketHeatmap />
    </section>
  );
}
```

Dans `frontend/src/app/router.tsx`, remplacer la route `index` par une route chargée à la demande :
```tsx
      { index: true, lazy: async () => ({ Component: (await import("@/features/home/HomePage")).HomePage }) },
```

Dans `frontend/src/app/router.test.tsx`, compléter le gestionnaire de `mockFetch` pour qu'il renvoie `[]` pour les URL commençant par `/api/rankings/top`, `/api/market/heatmap` et `/api/screener`, et `{ gainers: [], losers: [] }` pour `/api/rankings/movers` ; ajouter `vi.mock("@/components/charts/EChart", () => ({ EChart: () => null }));` en tête.

- [ ] **Step 3: Vérifier**

Run (dans `frontend/`) : `npm test && npm run build`
Expected: tests verts, build sans erreur.

- [ ] **Step 4: Commit**

```bash
git add frontend
git commit -m "feat: home page with top 10, indices, movers and market heatmap

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Explorateur complet et page ETF

**Files:**
- Create: `frontend/src/features/screener/filters.ts`, `useScreener.ts`, `columns.tsx`, `ScreenerFilters.tsx`, `ScreenerTable.tsx`, `ScreenerPage.tsx`
- Delete: `frontend/src/features/explorer/ExplorerPage.tsx`, `ExplorerPage.test.tsx`, `SecuritiesTable.tsx`, `useSecurities.ts`
- Modify: `frontend/src/app/router.tsx`
- Test: `frontend/src/features/screener/filters.test.ts`, `frontend/src/features/screener/ScreenerPage.test.tsx`

**Interfaces:**
- Consumes: `/api/screener?kind=`, `ScreenerRow` (Task 10), `EligibilityBadge` (lot 1), `Sparkline`, `ScoreGauge`, `FavoriteButton`.
- Produces:
  - `filters.ts` : type `ScreenerFilters {q, sector, country, market, minScore, minPrice, maxPrice, liquidOnly, favoritesOnly}` ; `filtersFromParams(params: URLSearchParams) -> ScreenerFilters` ; `filterRows(rows, filters) -> ScreenerRow[]` ; `SORT_KEYS`.
  - `ScreenerPage({ kind: "stock" | "etf", title, description })` : filtres et tri dans l'URL (`q, sector, country, market, minScore, minPrice, maxPrice, liquid=1, fav=1, sort, dir`), tableau virtualisé, clic sur une ligne → `/titres/:id`.
  - Routes : `/explorer` → `ScreenerPage kind="stock" title="Explorer"`, `/etf` → `ScreenerPage kind="etf" title="ETF"`.

- [ ] **Step 1: Tests (échouent)**

`frontend/src/features/screener/filters.test.ts` :
```ts
import type { ScreenerRow } from "@/lib/api/client";
import { filterRows, filtersFromParams } from "./filters";

const row = (over: Partial<ScreenerRow>): ScreenerRow => ({
  id: 1, yahoo_ticker: "MC.PA", symbol: "MC", name: "LVMH", kind: "stock", market: "Euronext Paris", country: "FR",
  sector: "Luxe", eligibility: "eligible", price: 600, change_pct: 1, perf_1w: 1, perf_1m: 1, perf_1y: 1, score: 80,
  pe: 20, dividend_yield: 0.02, liquid: true, is_favorite: false, sparkline: [], ...over,
});
const rows = [
  row({}),
  row({ id: 2, symbol: "TTE", name: "TotalEnergies", sector: "Énergie", price: 60, score: 55, is_favorite: true }),
  row({ id: 3, symbol: "SMA", name: "Petite", sector: "Tech", country: "IT", market: "Euronext Milan", price: 5, score: null, liquid: false }),
];

test("filtersFromParams lit l'URL", () => {
  const f = filtersFromParams(new URLSearchParams("q=tot&minScore=50&liquid=1&fav=1&maxPrice=100"));
  expect(f).toMatchObject({ q: "tot", minScore: 50, liquidOnly: true, favoritesOnly: true, maxPrice: 100, minPrice: null });
});

test("filtre par texte sur nom ou symbole, sans tenir compte des accents", () => {
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("q=energies"))).map((r) => r.id)).toEqual([2]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("q=mc"))).map((r) => r.id)).toEqual([1]);
});

test("filtre par secteur, pays, place et score minimum", () => {
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("sector=Tech"))).map((r) => r.id)).toEqual([3]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("country=IT"))).map((r) => r.id)).toEqual([3]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("market=Euronext Milan"))).map((r) => r.id)).toEqual([3]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("minScore=60"))).map((r) => r.id)).toEqual([1]);
});

test("filtre par prix, liquidité et favoris", () => {
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("minPrice=10&maxPrice=100"))).map((r) => r.id)).toEqual([2]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("liquid=1"))).map((r) => r.id)).toEqual([1, 2]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("fav=1"))).map((r) => r.id)).toEqual([2]);
});

test("paramètres invalides ignorés", () => {
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("minScore=abc")))).toHaveLength(3);
});
```

`frontend/src/features/screener/ScreenerPage.test.tsx` :
```tsx
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { ScreenerPage } from "./ScreenerPage";

afterEach(() => vi.unstubAllGlobals());

const row = (id: number, symbol: string, name: string, score: number | null, change: number) => ({
  id, yahoo_ticker: `${symbol}.PA`, symbol, name, kind: "stock", market: "Euronext Paris", country: "FR", sector: "Luxe",
  eligibility: "eligible", price: 100 + id, change_pct: change, perf_1w: 1, perf_1m: 2, perf_1y: 3, score, pe: 15,
  dividend_yield: 0.02, liquid: true, is_favorite: false, sparkline: [1, 2],
});
const ROWS = [row(1, "MC", "LVMH", 80, 2.07), row(2, "AIR", "Airbus", 60, -1.2), row(3, "BN", "Danone", null, 0.5)];

function renderPage(route = "/explorer") {
  mockFetch(() => ({ body: ROWS }));
  return renderWithProviders(
    <Routes>
      <Route path="/explorer" element={<ScreenerPage kind="stock" title="Explorer" description="d" />} />
      <Route path="/titres/:id" element={<p>Fiche ouverte</p>} />
    </Routes>,
    { route },
  );
}

const names = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[1].textContent);

test("liste triée par nom par défaut avec variations colorées", async () => {
  renderPage();
  await screen.findByText("LVMH");
  expect(names()[0]).toContain("Airbus");
  expect(screen.getByText(/\+2,07/)).toHaveClass("text-up");
  expect(screen.getByText("3 titres")).toBeInTheDocument();
});

test("tri par score décroissant en cliquant sur l'en-tête", async () => {
  renderPage();
  await screen.findByText("LVMH");
  await userEvent.click(screen.getByRole("button", { name: /Score/ }));
  await waitFor(() => expect(names()[0]).toContain("LVMH"));
});

test("filtres lus depuis l'URL", async () => {
  renderPage("/explorer?minScore=70");
  await screen.findByText("LVMH");
  expect(screen.queryByText("Airbus")).not.toBeInTheDocument();
  expect(screen.getByText("1 titre")).toBeInTheDocument();
});

test("recherche texte", async () => {
  renderPage();
  await screen.findByText("LVMH");
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher" }), "dan");
  await waitFor(() => expect(names()).toEqual([expect.stringContaining("Danone")]));
});

test("clic sur une ligne ouvre la fiche", async () => {
  renderPage();
  await userEvent.click(await screen.findByText("LVMH"));
  expect(await screen.findByText("Fiche ouverte")).toBeInTheDocument();
});

test("message si rien ne correspond", async () => {
  renderPage("/explorer?q=zzzz");
  expect(await screen.findByText(/Aucun titre ne correspond/)).toBeInTheDocument();
});
```

Run (dans `frontend/`) : `npm test`
Expected: FAIL.

- [ ] **Step 2: Filtres**

`frontend/src/features/screener/filters.ts` :
```ts
import type { ScreenerRow } from "@/lib/api/client";

export type ScreenerFilters = {
  q: string;
  sector: string | null;
  country: string | null;
  market: string | null;
  minScore: number | null;
  minPrice: number | null;
  maxPrice: number | null;
  liquidOnly: boolean;
  favoritesOnly: boolean;
};

export const SORT_KEYS = ["name", "price", "change_pct", "perf_1w", "perf_1m", "perf_1y", "score", "pe", "dividend_yield"] as const;
export type SortKey = (typeof SORT_KEYS)[number];

function numberParam(params: URLSearchParams, key: string): number | null {
  const raw = params.get(key);
  if (raw === null || raw.trim() === "") return null;
  const value = Number(raw.replace(",", "."));
  return Number.isFinite(value) ? value : null;
}

export function filtersFromParams(params: URLSearchParams): ScreenerFilters {
  return {
    q: params.get("q") ?? "",
    sector: params.get("sector"),
    country: params.get("country"),
    market: params.get("market"),
    minScore: numberParam(params, "minScore"),
    minPrice: numberParam(params, "minPrice"),
    maxPrice: numberParam(params, "maxPrice"),
    liquidOnly: params.get("liquid") === "1",
    favoritesOnly: params.get("fav") === "1",
  };
}

export const normalize = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function filterRows(rows: ScreenerRow[], f: ScreenerFilters): ScreenerRow[] {
  const q = normalize(f.q.trim());
  return rows.filter((r) =>
    (!q || normalize(r.name).includes(q) || normalize(r.symbol).includes(q))
    && (!f.sector || r.sector === f.sector)
    && (!f.country || r.country === f.country)
    && (!f.market || r.market === f.market)
    && (f.minScore === null || (r.score !== null && r.score >= f.minScore))
    && (f.minPrice === null || (r.price !== null && r.price >= f.minPrice))
    && (f.maxPrice === null || (r.price !== null && r.price <= f.maxPrice))
    && (!f.liquidOnly || r.liquid)
    && (!f.favoritesOnly || r.is_favorite));
}
```

`frontend/src/features/screener/useScreener.ts` :
```ts
import { useQuery } from "@tanstack/react-query";
import { apiGet, type ScreenerRow } from "@/lib/api/client";

export function useScreener(kind: "stock" | "etf") {
  return useQuery({
    queryKey: ["screener", kind],
    queryFn: () => apiGet<ScreenerRow[]>("/api/screener", { kind }),
    refetchInterval: 60_000,
  });
}
```

- [ ] **Step 3: Colonnes, filtres, tableau, page**

`frontend/src/features/screener/columns.tsx` :
```tsx
import type { ColumnDef } from "@tanstack/react-table";
import { FavoriteButton } from "@/components/FavoriteButton";
import { ScoreGauge } from "@/components/ScoreGauge";
import { Sparkline } from "@/components/Sparkline";
import { EligibilityBadge } from "@/features/explorer/EligibilityBadge";
import type { ScreenerRow } from "@/lib/api/client";
import { formatNumber, formatPct, formatPrice, formatRatioPct } from "@/lib/format";
import { cn } from "@/lib/utils";

function Change({ value }: { value: number | null }) {
  return (
    <span className={cn("font-medium", value != null && value > 0 && "text-up", value != null && value < 0 && "text-down")}>
      {formatPct(value)}
    </span>
  );
}

// Les valeurs absentes deviennent `undefined` pour rester en fin de liste dans les deux sens de tri.
const numeric = (key: keyof ScreenerRow) => ({
  accessorFn: (row: ScreenerRow) => (row[key] as number | null) ?? undefined,
  sortUndefined: "last" as const,
});

export type ColumnSpec = ColumnDef<ScreenerRow> & { width: string; align?: "right" };

export function buildColumns(kind: "stock" | "etf"): ColumnSpec[] {
  const columns: ColumnSpec[] = [
    { id: "favorite", header: "", width: "40px", enableSorting: false,
      cell: ({ row }) => <FavoriteButton securityId={row.original.id} isFavorite={row.original.is_favorite} /> },
    { id: "name", accessorKey: "name", header: "Nom", width: "minmax(220px, 2fr)",
      cell: ({ row }) => (
        <div className="min-w-0">
          <div className="truncate font-medium">{row.original.name}</div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {row.original.symbol} · {row.original.market}
            {row.original.eligibility !== "eligible" && <EligibilityBadge status={row.original.eligibility} />}
          </div>
        </div>
      ) },
    { id: "price", header: "Cours", width: "90px", align: "right", ...numeric("price"),
      cell: ({ row }) => <span className="font-medium">{formatPrice(row.original.price)}</span> },
    { id: "change_pct", header: "1 j", width: "80px", align: "right", ...numeric("change_pct"),
      cell: ({ row }) => <Change value={row.original.change_pct} /> },
    { id: "perf_1w", header: "1 sem", width: "80px", align: "right", ...numeric("perf_1w"),
      cell: ({ row }) => <Change value={row.original.perf_1w} /> },
    { id: "perf_1m", header: "1 mois", width: "80px", align: "right", ...numeric("perf_1m"),
      cell: ({ row }) => <Change value={row.original.perf_1m} /> },
    { id: "perf_1y", header: "1 an", width: "85px", align: "right", ...numeric("perf_1y"),
      cell: ({ row }) => <Change value={row.original.perf_1y} /> },
    { id: "score", header: "Score", width: "70px", align: "right", ...numeric("score"),
      cell: ({ row }) => <ScoreGauge score={row.original.score} size={36} /> },
  ];
  if (kind === "stock") {
    columns.push(
      { id: "pe", header: "PER", width: "70px", align: "right", ...numeric("pe"),
        cell: ({ row }) => formatNumber(row.original.pe, 1) },
      { id: "dividend_yield", header: "Rendement", width: "95px", align: "right", ...numeric("dividend_yield"),
        cell: ({ row }) => formatRatioPct(row.original.dividend_yield) },
    );
  }
  columns.push({ id: "trend", header: "3 mois", width: "110px", enableSorting: false,
    cell: ({ row }) => <Sparkline values={row.original.sparkline} /> });
  return columns;
}
```

`frontend/src/features/screener/ScreenerFilters.tsx` :
```tsx
import { Input } from "@/components/ui/input";
import type { ScreenerRow } from "@/lib/api/client";
import type { ScreenerFilters as Filters } from "./filters";

type Props = {
  rows: ScreenerRow[];
  filters: Filters;
  onChange: (key: string, value: string | null) => void;
  count: number;
};

const unique = (values: (string | null)[]) => [...new Set(values.filter((v): v is string => !!v))].sort((a, b) => a.localeCompare(b, "fr"));

function Select({ label, value, options, onChange }: { label: string; value: string | null; options: string[]; onChange: (v: string | null) => void }) {
  return (
    <select
      aria-label={label}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
    >
      <option value="">{label} : tous</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

export function ScreenerFilters({ rows, filters, onChange, count }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        type="search" aria-label="Rechercher" placeholder="Nom ou ticker…" className="w-60 bg-white"
        value={filters.q} onChange={(e) => onChange("q", e.target.value || null)}
      />
      <Select label="Secteur" value={filters.sector} options={unique(rows.map((r) => r.sector))} onChange={(v) => onChange("sector", v)} />
      <Select label="Pays" value={filters.country} options={unique(rows.map((r) => r.country))} onChange={(v) => onChange("country", v)} />
      <Select label="Place" value={filters.market} options={unique(rows.map((r) => r.market))} onChange={(v) => onChange("market", v)} />
      <Input type="number" aria-label="Score minimum" placeholder="Score min" className="w-28 bg-white" min={0} max={100}
             value={filters.minScore ?? ""} onChange={(e) => onChange("minScore", e.target.value || null)} />
      <Input type="number" aria-label="Prix minimum" placeholder="Prix min" className="w-24 bg-white" min={0}
             value={filters.minPrice ?? ""} onChange={(e) => onChange("minPrice", e.target.value || null)} />
      <Input type="number" aria-label="Prix maximum" placeholder="Prix max" className="w-24 bg-white" min={0}
             value={filters.maxPrice ?? ""} onChange={(e) => onChange("maxPrice", e.target.value || null)} />
      <label className="flex items-center gap-1.5 text-sm">
        <input type="checkbox" checked={filters.liquidOnly} onChange={(e) => onChange("liquid", e.target.checked ? "1" : null)} />
        Liquides uniquement
      </label>
      <label className="flex items-center gap-1.5 text-sm">
        <input type="checkbox" checked={filters.favoritesOnly} onChange={(e) => onChange("fav", e.target.checked ? "1" : null)} />
        Favoris
      </label>
      <span className="ml-auto text-sm text-muted-foreground">{count} {count > 1 ? "titres" : "titre"}</span>
    </div>
  );
}
```

`frontend/src/features/screener/ScreenerTable.tsx` :
```tsx
import { useRef } from "react";
import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type SortingState } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp } from "lucide-react";
import type { ScreenerRow } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { ColumnSpec } from "./columns";

type Props = {
  rows: ScreenerRow[];
  columns: ColumnSpec[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  onRowClick: (row: ScreenerRow) => void;
};

const ROW_HEIGHT = 56;

export function ScreenerTable({ rows, columns, sorting, onSortingChange, onRowClick }: Props) {
  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: (updater) => onSortingChange(typeof updater === "function" ? updater(sorting) : updater),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  const scrollRef = useRef<HTMLDivElement>(null);
  const tableRows = table.getRowModel().rows;
  const virtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
    initialRect: { width: 1200, height: 800 },
  });
  const template = columns.map((c) => c.width).join(" ");

  return (
    <div role="table" aria-rowcount={tableRows.length + 1} className="text-sm">
      <div role="row" className="grid items-center border-b border-border px-4 py-2 text-xs font-medium text-muted-foreground"
           style={{ gridTemplateColumns: template }}>
        {table.getHeaderGroups()[0].headers.map((header) => {
          const spec = header.column.columnDef as ColumnSpec;
          const sorted = header.column.getIsSorted();
          return (
            <div role="columnheader" key={header.id} className={cn(spec.align === "right" && "text-right")}>
              {header.column.getCanSort() ? (
                <button type="button" onClick={header.column.getToggleSortingHandler()}
                        className={cn("inline-flex items-center gap-1 hover:text-foreground", sorted && "text-foreground")}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {sorted === "asc" && <ArrowUp className="size-3" />}
                  {sorted === "desc" && <ArrowDown className="size-3" />}
                </button>
              ) : flexRender(header.column.columnDef.header, header.getContext())}
            </div>
          );
        })}
      </div>
      <div ref={scrollRef} className="h-[calc(100vh-270px)] min-h-[400px] overflow-y-auto">
        <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
          {virtualizer.getVirtualItems().map((item) => {
            const row = tableRows[item.index];
            return (
              <div role="row" key={row.id} onClick={() => onRowClick(row.original)}
                   className="absolute inset-x-0 grid cursor-pointer items-center border-b border-border px-4 hover:bg-muted/60"
                   style={{ gridTemplateColumns: template, height: ROW_HEIGHT, transform: `translateY(${item.start}px)` }}>
                {row.getVisibleCells().map((cell) => (
                  <div role="cell" key={cell.id}
                       className={cn("truncate", (cell.column.columnDef as ColumnSpec).align === "right" && "flex justify-end")}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

`frontend/src/features/screener/ScreenerPage.tsx` :
```tsx
import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router";
import type { SortingState } from "@tanstack/react-table";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { buildColumns } from "./columns";
import { filterRows, filtersFromParams, SORT_KEYS } from "./filters";
import { ScreenerFilters } from "./ScreenerFilters";
import { ScreenerTable } from "./ScreenerTable";
import { useScreener } from "./useScreener";

type Props = { kind: "stock" | "etf"; title: string; description: string };

export function ScreenerPage({ kind, title, description }: Props) {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { data, isPending, isError } = useScreener(kind);
  const filters = filtersFromParams(params);
  const columns = useMemo(() => buildColumns(kind), [kind]);
  const rows = useMemo(() => filterRows(data ?? [], filters), [data, params]); // eslint-disable-line react-hooks/exhaustive-deps

  const sortKey = params.get("sort");
  const sorting: SortingState = SORT_KEYS.includes(sortKey as never)
    ? [{ id: sortKey as string, desc: params.get("dir") !== "asc" }]
    : [{ id: "name", desc: false }];

  const update = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };
  const onSortingChange = (next: SortingState) => {
    const updated = new URLSearchParams(params);
    if (next.length === 0) {
      updated.delete("sort");
      updated.delete("dir");
    } else {
      updated.set("sort", next[0].id);
      updated.set("dir", next[0].desc ? "desc" : "asc");
    }
    setParams(updated, { replace: true });
  };

  return (
    <section>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </header>
      <ScreenerFilters rows={data ?? []} filters={filters} onChange={update} count={rows.length} />
      <Card className="mt-4 overflow-hidden py-0">
        {isPending ? (
          <div className="space-y-3 p-6">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        ) : isError ? (
          <p role="alert" className="p-6 text-sm text-down">Impossible de charger les titres. Vérifiez que l'application est bien démarrée.</p>
        ) : rows.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">
            {data.length === 0 ? "Les titres sont en cours de chargement (premier démarrage)." : "Aucun titre ne correspond à ces filtres."}
          </p>
        ) : (
          <ScreenerTable rows={rows} columns={columns} sorting={sorting} onSortingChange={onSortingChange}
                         onRowClick={(row) => navigate(`/titres/${row.id}`)} />
        )}
      </Card>
    </section>
  );
}
```

Supprimer `frontend/src/features/explorer/ExplorerPage.tsx`, `ExplorerPage.test.tsx`, `SecuritiesTable.tsx`, `useSecurities.ts` (conserver `EligibilityBadge.tsx`).

Dans `frontend/src/app/router.tsx`, remplacer l'import d'`ExplorerPage` par `import { ScreenerPage } from "@/features/screener/ScreenerPage";` et les routes `explorer` et `etf` par :
```tsx
      { path: "explorer", element: <ScreenerPage kind="stock" title="Explorer" description="Toutes les actions européennes avec leur score, leurs performances et leur éligibilité au PEA." /> },
      { path: "etf", element: <ScreenerPage kind="etf" title="ETF" description="Les ETF éligibles au PEA, classés par score technique." /> },
```

- [ ] **Step 4: Vérifier**

Run (dans `frontend/`) : `npm test && npm run build`
Expected: tests verts, build sans erreur.

- [ ] **Step 5: Commit**

```bash
git add -A frontend
git commit -m "feat: full screener (filters, sorting, URL state, virtualized table) for stocks and ETFs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Graphique de cours (TradingView Lightweight Charts)

**Files:**
- Create: `frontend/src/features/security/PriceChart.tsx`, `frontend/src/features/security/PriceChartPanel.tsx`
- Test: `frontend/src/features/security/PriceChartPanel.test.tsx`

**Interfaces:**
- Consumes: `/api/securities/{id}/history?period=`, `HistoryOut` (Task 10).
- Produces: `<PriceChart history showSma50 showSma200 showRsi showMacd />` (bougies + volume, moyennes, panneaux RSI et MACD) ; `<PriceChartPanel securityId />` (sélecteur de période 1J/1S/1M/6M/1A/5A, cases MM50/MM200/RSI/MACD désactivées en intraday, message si aucune donnée).

- [ ] **Step 1: Test (échoue)**

`frontend/src/features/security/PriceChartPanel.test.tsx` :
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { PriceChartPanel } from "./PriceChartPanel";

const series = () => ({ setData: vi.fn(), priceScale: () => ({ applyOptions: vi.fn() }) });
const chart = {
  addSeries: vi.fn(() => series()),
  panes: vi.fn(() => [{ setHeight: vi.fn() }, { setHeight: vi.fn() }, { setHeight: vi.fn() }]),
  timeScale: () => ({ fitContent: vi.fn() }),
  remove: vi.fn(),
};
vi.mock("lightweight-charts", () => ({
  createChart: vi.fn(() => chart),
  CandlestickSeries: "Candlestick", HistogramSeries: "Histogram", LineSeries: "Line",
}));
afterEach(() => { vi.unstubAllGlobals(); chart.addSeries.mockClear(); });

const DAILY = {
  period: "6M", intraday: false,
  bars: [{ time: "2026-09-24", open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }, { time: "2026-09-25", open: 1.5, high: 2, low: 1, close: 1.8, volume: 12 }],
  sma50: [{ time: "2026-09-25", value: 1.2 }], sma200: [], rsi: [{ time: "2026-09-25", value: 55 }],
  macd: [{ time: "2026-09-25", macd: 0.1, signal: 0.05, histogram: 0.05 }],
};

test("charge 6 mois par défaut puis change de période", async () => {
  const fetchMock = mockFetch(() => ({ body: DAILY }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("period=6M"), expect.anything()));
  await waitFor(() => expect(chart.addSeries).toHaveBeenCalledWith("Candlestick", expect.anything()));
  await userEvent.click(screen.getByRole("button", { name: "1A" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("period=1Y"), expect.anything()));
});

test("RSI ajouté dans un panneau séparé quand on coche la case", async () => {
  mockFetch(() => ({ body: DAILY }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  await waitFor(() => expect(chart.addSeries).toHaveBeenCalled());
  chart.addSeries.mockClear();
  await userEvent.click(screen.getByRole("checkbox", { name: "RSI" }));
  await waitFor(() => expect(chart.addSeries).toHaveBeenCalledWith("Line", expect.anything(), 1));
});

test("message quand il n'y a pas de données", async () => {
  mockFetch(() => ({ body: { ...DAILY, period: "1D", intraday: true, bars: [], sma50: [], rsi: [], macd: [] } }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  await userEvent.click(screen.getByRole("button", { name: "1J" }));
  expect(await screen.findByText(/Pas de données pour cette période/)).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "RSI" })).toBeDisabled();
});
```

Run (dans `frontend/`) : `npm test`
Expected: FAIL.

- [ ] **Step 2: Implémenter**

`frontend/src/features/security/PriceChart.tsx` :
```tsx
import { useEffect, useRef } from "react";
import { CandlestickSeries, createChart, HistogramSeries, LineSeries, type Time } from "lightweight-charts";
import type { HistoryOut } from "@/lib/api/client";

const UP = "#16a34a";
const DOWN = "#dc2626";
const priceFormat = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

type Props = { history: HistoryOut; showSma50: boolean; showSma200: boolean; showRsi: boolean; showMacd: boolean };

export function PriceChart({ history, showSma50, showSma200, showRsi, showMacd }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const chart = createChart(ref.current!, {
      autoSize: true,
      layout: { background: { color: "#ffffff" }, textColor: "#52525b", attributionLogo: true, panes: { separatorColor: "#e4e4e7" } },
      grid: { vertLines: { color: "#f4f4f5" }, horzLines: { color: "#f4f4f5" } },
      localization: { locale: "fr-FR", priceFormatter: (p: number) => priceFormat.format(p) },
      timeScale: { timeVisible: history.intraday, borderColor: "#e4e4e7" },
      rightPriceScale: { borderColor: "#e4e4e7" },
    });
    const t = (time: string | number) => time as Time;

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP, downColor: DOWN, borderVisible: false, wickUpColor: UP, wickDownColor: DOWN,
    });
    candles.setData(history.bars.map((b) => ({
      time: t(b.time), open: b.open ?? b.close, high: b.high ?? b.close, low: b.low ?? b.close, close: b.close,
    })));

    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume" });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volume.setData(history.bars.map((b) => ({
      time: t(b.time), value: b.volume ?? 0,
      color: b.close >= (b.open ?? b.close) ? "rgba(22, 163, 74, 0.3)" : "rgba(220, 38, 38, 0.3)",
    })));

    const lineOptions = { lineWidth: 2 as const, priceLineVisible: false, lastValueVisible: false };
    if (showSma50) chart.addSeries(LineSeries, { ...lineOptions, color: "#6366f1" }).setData(history.sma50.map((p) => ({ time: t(p.time), value: p.value })));
    if (showSma200) chart.addSeries(LineSeries, { ...lineOptions, color: "#f59e0b" }).setData(history.sma200.map((p) => ({ time: t(p.time), value: p.value })));

    let pane = 0;
    if (showRsi) {
      pane += 1;
      chart.addSeries(LineSeries, { ...lineOptions, lineWidth: 1, color: "#8b5cf6" }, pane)
        .setData(history.rsi.map((p) => ({ time: t(p.time), value: p.value })));
    }
    if (showMacd) {
      pane += 1;
      chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, pane)
        .setData(history.macd.map((p) => ({ time: t(p.time), value: p.histogram, color: p.histogram >= 0 ? "rgba(22,163,74,0.5)" : "rgba(220,38,38,0.5)" })));
      chart.addSeries(LineSeries, { ...lineOptions, lineWidth: 1, color: "#0ea5e9" }, pane).setData(history.macd.map((p) => ({ time: t(p.time), value: p.macd })));
      chart.addSeries(LineSeries, { ...lineOptions, lineWidth: 1, color: "#f97316" }, pane).setData(history.macd.map((p) => ({ time: t(p.time), value: p.signal })));
    }
    chart.panes().slice(1).forEach((p) => p.setHeight(110));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [history, showSma50, showSma200, showRsi, showMacd]);

  const height = 420 + (showRsi ? 110 : 0) + (showMacd ? 110 : 0);
  return <div ref={ref} style={{ height }} className="w-full" />;
}
```

`frontend/src/features/security/PriceChartPanel.tsx` :
```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, type HistoryOut } from "@/lib/api/client";
import { PriceChart } from "./PriceChart";

const PERIODS = [
  { value: "1D", label: "1J" }, { value: "1W", label: "1S" }, { value: "1M", label: "1M" },
  { value: "6M", label: "6M" }, { value: "1Y", label: "1A" }, { value: "5Y", label: "5A" },
] as const;

export function PriceChartPanel({ securityId }: { securityId: number }) {
  const [period, setPeriod] = useState<(typeof PERIODS)[number]["value"]>("6M");
  const [toggles, setToggles] = useState({ sma50: true, sma200: true, rsi: false, macd: false });
  const { data, isPending, isError } = useQuery({
    queryKey: ["history", securityId, period],
    queryFn: () => apiGet<HistoryOut>(`/api/securities/${securityId}/history`, { period }),
    refetchInterval: period === "1D" ? 60_000 : false,
  });
  const intraday = data?.intraday ?? (period === "1D" || period === "1W");
  const toggle = (key: keyof typeof toggles, label: string) => (
    <label className="flex items-center gap-1.5 text-sm">
      <input type="checkbox" aria-label={label} disabled={intraday} checked={toggles[key] && !intraday}
             onChange={(e) => setToggles({ ...toggles, [key]: e.target.checked })} />
      {label}
    </label>
  );

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <Button key={p.value} size="sm" variant={p.value === period ? "default" : "outline"} onClick={() => setPeriod(p.value)}>
                {p.label}
              </Button>
            ))}
          </div>
          <div className="flex gap-4">
            {toggle("sma50", "MM50")}
            {toggle("sma200", "MM200")}
            {toggle("rsi", "RSI")}
            {toggle("macd", "MACD")}
          </div>
        </div>
        {isPending ? (
          <Skeleton className="h-[420px] w-full" />
        ) : isError ? (
          <p role="alert" className="py-20 text-center text-sm text-down">Impossible de charger le graphique.</p>
        ) : data.bars.length === 0 ? (
          <p className="py-20 text-center text-sm text-muted-foreground">Pas de données pour cette période (bourse fermée ou source indisponible).</p>
        ) : (
          <PriceChart history={data} showSma50={toggles.sma50 && !intraday} showSma200={toggles.sma200 && !intraday}
                      showRsi={toggles.rsi && !intraday} showMacd={toggles.macd && !intraday} />
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Vérifier**

Run (dans `frontend/`) : `npm test && npm run build`
Expected: tests verts, build sans erreur.

- [ ] **Step 4: Commit**

```bash
git add frontend
git commit -m "feat: TradingView price chart with volume, moving averages, RSI and MACD panes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Fiche d'un titre

**Files:**
- Create: `frontend/src/features/security/SecurityPage.tsx`, `ScoreCard.tsx`, `FundamentalsCard.tsx`, `SimulatorCard.tsx`, `NewsCard.tsx`
- Modify: `frontend/src/app/router.tsx`
- Test: `frontend/src/features/security/SecurityPage.test.tsx`

**Interfaces:**
- Consumes: `/api/securities/{id}`, `/news`, `/simulate`, `/api/fees/estimate`, `PriceChartPanel` (Task 13), `ScoreGauge`, `FavoriteButton`, `EligibilityBadge`, formats (Task 10).
- Produces: route `/titres/:id` chargée à la demande ; `SecurityPage`.

- [ ] **Step 1: Test (échoue)**

`frontend/src/features/security/SecurityPage.test.tsx` :
```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { SecurityPage } from "./SecurityPage";

vi.mock("./PriceChartPanel", () => ({ PriceChartPanel: () => <div data-testid="chart" /> }));
afterEach(() => vi.unstubAllGlobals());

const DETAIL = {
  id: 1, yahoo_ticker: "MC.PA", symbol: "MC", name: "LVMH", kind: "stock", market: "Euronext Paris", country: "FR",
  sector: "Consumer Cyclical", industry: "Luxury Goods", isin: "FR0000121014", eligibility: "eligible",
  eligibility_source: "auto", price: 612.4, change_pct: 2.07, as_of: "2026-09-25T15:35:00Z", perf_1w: 1, perf_1m: 2,
  perf_1y: 3, score: 72, pe: 18, dividend_yield: 0.0328, liquid: true, is_favorite: false, sparkline: [],
  fundamentals: { pe: 18.07, eps: 33.9, earnings_growth: 0.008, revenue_growth: -0.029, debt_to_equity: 0.53,
                  profit_margin: 0.137, dividend_yield: 0.0328, market_cap: 195_600_000_000, currency: "EUR", updated_at: null },
  score_detail: { total: 72, technical: 80, fundamental: 64, available_ratio: 1, liquid: true, eligible_for_top: true,
                  history_days: 1250, computed_at: "2026-09-25T15:40:00Z",
                  components: [{ key: "trend", label: "Tendance", points: 20, max_points: 20, message: "✅ Tendance haussière", group: "technical" }] },
};

function renderPage(detailStatus = 200, detail: object = DETAIL) {
  const fetchMock = mockFetch((url) => {
    if (url.startsWith("/api/securities/1/news")) return { body: [{ title: "LVMH accélère", url: "https://ex.com/a", publisher: "Reuters", published_at: null }] };
    if (url.startsWith("/api/securities/1/simulate")) return { body: { start_date: "2026-08-25", start_price: 368, current_price: 400, shares: 2, invested: 736, buy_fee: 1.32, sell_fee: 1.44, current_value: 800, gain: 61.24, gain_pct: 8.3, message: null } };
    if (url.startsWith("/api/fees/estimate")) return { body: { amount: 500, fee: 2.4, rate: 0.0048 } };
    return { status: detailStatus, body: detail };
  });
  renderWithProviders(<Routes><Route path="/titres/:id" element={<SecurityPage />} /></Routes>, { route: "/titres/1" });
  return fetchMock;
}

test("en-tête, score détaillé, fondamentaux et actualités", async () => {
  renderPage();
  expect(await screen.findByRole("heading", { level: 1, name: "LVMH" })).toBeInTheDocument();
  expect(screen.getByText("Éligible PEA")).toBeInTheDocument();
  expect(screen.getByText("✅ Tendance haussière")).toBeInTheDocument();
  expect(screen.getByText(/195,6\sMd\s€/u)).toBeInTheDocument();
  expect(screen.getByText(/Luxury Goods/)).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: /LVMH accélère/ })).toHaveAttribute("href", "https://ex.com/a");
  expect(screen.getByTestId("chart")).toBeInTheDocument();
});

test("simulateur et aide sur les frais", async () => {
  const fetchMock = renderPage();
  await screen.findByRole("heading", { level: 1, name: "LVMH" });
  expect(await screen.findByText(/≈ 2,40 € de frais \(0,48 %\)/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Simuler" }));
  expect(await screen.findByText(/\+61,24 €/)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("amount=500"), expect.anything());
});

test("test_security_page_without_score : titre sans score ni fondamentaux", async () => {
  renderPage(200, { ...DETAIL, score: null, fundamentals: null, score_detail: null, price: null, change_pct: null });
  expect(await screen.findByText(/Score pas encore calculé/)).toBeInTheDocument();
  expect(screen.getByText(/Données fondamentales indisponibles/)).toBeInTheDocument();
});

test("titre introuvable", async () => {
  renderPage(404, { detail: "Titre introuvable" });
  expect(await screen.findByText("Titre introuvable.")).toBeInTheDocument();
});
```

Run (dans `frontend/`) : `npm test`
Expected: FAIL.

- [ ] **Step 2: Implémenter**

`frontend/src/features/security/ScoreCard.tsx` :
```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreGauge } from "@/components/ScoreGauge";
import type { SecurityDetail } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";

export function ScoreCard({ detail }: { detail: SecurityDetail }) {
  const score = detail.score_detail;
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Score mixte</CardTitle></CardHeader>
      <CardContent>
        {!score || score.total == null ? (
          <p className="text-sm text-muted-foreground">Score pas encore calculé (historique ou données insuffisants).</p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <ScoreGauge score={score.total} size={64} />
              <div className="text-sm">
                <p>Technique : <strong>{formatNumber(score.technical, 0)}</strong>/100 · Fondamental : <strong>{formatNumber(score.fundamental, 0)}</strong>/100</p>
                {score.available_ratio < 1 && <p className="text-amber-700">Données incomplètes : score calculé sur {Math.round(score.available_ratio * 100)} % des critères.</p>}
                {!score.eligible_for_top && detail.kind === "stock" && (
                  <p className="text-muted-foreground">Hors top 10 : {!score.liquid ? "titre peu échangé" : score.history_days < 200 ? "historique trop court" : detail.eligibility !== "eligible" ? "éligibilité PEA non confirmée" : "données insuffisantes"}.</p>
                )}
              </div>
            </div>
            <ul className="space-y-2.5">
              {score.components.map((c) => (
                <li key={c.key}>
                  <div className="flex justify-between text-sm"><span>{c.message}</span><span className="text-muted-foreground">{formatNumber(c.points, 1)}/{formatNumber(c.max_points, 1)}</span></div>
                  <div className="mt-1 h-1.5 rounded-full bg-muted">
                    <div className="h-1.5 rounded-full bg-primary" style={{ width: `${(c.points / c.max_points) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/security/FundamentalsCard.tsx` :
```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SecurityDetail } from "@/lib/api/client";
import { formatCompactEur, formatNumber, formatRatioPct } from "@/lib/format";

export function FundamentalsCard({ detail }: { detail: SecurityDetail }) {
  const f = detail.fundamentals;
  const rows: [string, string][] = f ? [
    ["PER", formatNumber(f.pe, 1)],
    ["Bénéfice par action", formatNumber(f.eps, 2)],
    ["Croissance des bénéfices", formatRatioPct(f.earnings_growth)],
    ["Croissance du chiffre d'affaires", formatRatioPct(f.revenue_growth)],
    ["Dette / capitaux propres", formatNumber(f.debt_to_equity, 2)],
    ["Marge nette", formatRatioPct(f.profit_margin)],
    ["Rendement du dividende", formatRatioPct(f.dividend_yield)],
    ["Capitalisation", f.currency && f.currency !== "EUR" ? `${formatNumber(f.market_cap, 0)} ${f.currency}` : formatCompactEur(f.market_cap)],
  ] : [];
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Données fondamentales</CardTitle></CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-muted-foreground">{detail.sector ?? "Secteur inconnu"} · {detail.industry ?? "—"}</p>
        {!f ? (
          <p className="text-sm text-muted-foreground">Données fondamentales indisponibles pour ce titre.</p>
        ) : (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {rows.map(([label, value]) => (
              <div key={label} className="flex justify-between border-b border-border py-1">
                <dt className="text-muted-foreground">{label}</dt><dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/security/SimulatorCard.tsx` :
```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, type FeeEstimate, type SimulationOut } from "@/lib/api/client";
import { formatDate, formatPrice, formatRatioPct } from "@/lib/format";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { cn } from "@/lib/utils";

const PERIODS = [{ value: "1W", label: "1 semaine" }, { value: "1M", label: "1 mois" }, { value: "6M", label: "6 mois" }, { value: "1Y", label: "1 an" }];

export function SimulatorCard({ securityId }: { securityId: number }) {
  const [amount, setAmount] = useState("500");
  const [period, setPeriod] = useState("1M");
  const [request, setRequest] = useState<{ amount: number; period: string } | null>(null);
  const value = Number(amount.replace(",", "."));
  const debounced = useDebouncedValue(value, 300);
  const fee = useQuery({
    queryKey: ["fee", debounced],
    queryFn: () => apiGet<FeeEstimate>("/api/fees/estimate", { amount: debounced }),
    enabled: Number.isFinite(debounced) && debounced > 0,
  });
  const simulation = useQuery({
    queryKey: ["simulate", securityId, request],
    queryFn: () => apiGet<SimulationOut>(`/api/securities/${securityId}/simulate`, request!),
    enabled: request !== null,
  });
  const result = simulation.data;

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Et si j'avais investi…</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (value > 0) setRequest({ amount: value, period }); }}>
          <Input aria-label="Montant" inputMode="decimal" className="w-28 bg-white" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <span>€ il y a</span>
          <select aria-label="Période" value={period} onChange={(e) => setPeriod(e.target.value)} className="h-8 rounded-lg border border-input bg-white px-2">
            {PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <Button type="submit" size="sm">Simuler</Button>
        </form>
        {fee.data && (
          <p className="text-muted-foreground">
            Pour {formatPrice(fee.data.amount)} € : ≈ {formatPrice(fee.data.fee)} € de frais ({formatRatioPct(fee.data.rate)}).
            {fee.data.amount <= 500 && " À partir de 500 €, le taux passe à 0,18 %."}
          </p>
        )}
        {result && (result.message ? (
          <p className="text-amber-700">{result.message}</p>
        ) : (
          <div className="rounded-lg bg-muted p-3">
            <p>{result.shares} action{result.shares > 1 ? "s" : ""} achetée{result.shares > 1 ? "s" : ""} le {formatDate(result.start_date)} à {formatPrice(result.start_price)} € (frais {formatPrice(result.buy_fee)} €)</p>
            <p>Valeur aujourd'hui : {formatPrice(result.current_value)} € (frais de revente {formatPrice(result.sell_fee)} €)</p>
            <p className={cn("mt-1 text-base font-semibold", result.gain >= 0 ? "text-up" : "text-down")}>
              {result.gain >= 0 ? "+" : ""}{formatPrice(result.gain)} € ({result.gain_pct != null ? `${result.gain_pct >= 0 ? "+" : ""}${formatPrice(result.gain_pct)} %` : "—"})
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/security/NewsCard.tsx` :
```tsx
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type NewsOut } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";

export function NewsCard({ securityId }: { securityId: number }) {
  const { data, isPending } = useQuery({
    queryKey: ["news", securityId],
    queryFn: () => apiGet<NewsOut[]>(`/api/securities/${securityId}/news`),
    staleTime: 900_000,
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Actualités récentes</CardTitle></CardHeader>
      <CardContent>
        {isPending ? <p className="text-sm text-muted-foreground">Chargement…</p> : !data?.length ? (
          <p className="text-sm text-muted-foreground">Aucune actualité récente.</p>
        ) : (
          <ul className="space-y-3">
            {data.map((item) => (
              <li key={item.url}>
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="group flex items-start gap-1.5 text-sm font-medium hover:text-primary">
                  {item.title}<ExternalLink className="mt-0.5 size-3 shrink-0 opacity-50 group-hover:opacity-100" />
                </a>
                <p className="text-xs text-muted-foreground">{item.publisher ?? "Source inconnue"}{item.published_at && ` · ${formatDateTime(item.published_at)}`}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/security/SecurityPage.tsx` :
```tsx
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { FavoriteButton } from "@/components/FavoriteButton";
import { Skeleton } from "@/components/ui/skeleton";
import { EligibilityBadge } from "@/features/explorer/EligibilityBadge";
import { ApiError, apiGet, type SecurityDetail } from "@/lib/api/client";
import { formatDateTime, formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { FundamentalsCard } from "./FundamentalsCard";
import { NewsCard } from "./NewsCard";
import { PriceChartPanel } from "./PriceChartPanel";
import { ScoreCard } from "./ScoreCard";
import { SimulatorCard } from "./SimulatorCard";

export function SecurityPage() {
  const id = Number(useParams().id);
  const { data, isPending, error } = useQuery({
    queryKey: ["security", id],
    queryFn: () => apiGet<SecurityDetail>(`/api/securities/${id}`),
    refetchInterval: 60_000,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !data) {
    return (
      <section className="py-20 text-center">
        <p className="text-lg font-medium">{error instanceof ApiError && error.status === 404 ? "Titre introuvable." : "Impossible de charger ce titre."}</p>
        <Link to="/explorer" className="mt-2 inline-block text-sm text-primary">Retour à l'explorateur</Link>
      </section>
    );
  }
  const change = data.change_pct ?? 0;
  return (
    <section className="space-y-6">
      <header className="flex items-start justify-between gap-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{data.name}</h1>
            <FavoriteButton securityId={data.id} isFavorite={data.is_favorite} />
          </div>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            {data.symbol} · {data.market}{data.isin && ` · ${data.isin}`} <EligibilityBadge status={data.eligibility} />
          </p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-semibold">{formatPrice(data.price)} €</p>
          <p className={cn("text-sm font-medium", change > 0 && "text-up", change < 0 && "text-down")}>{formatPct(data.change_pct)} aujourd'hui</p>
          <p className="text-xs text-muted-foreground">Mis à jour {formatDateTime(data.as_of)}</p>
        </div>
      </header>
      <PriceChartPanel securityId={data.id} />
      <div className="grid grid-cols-2 gap-6">
        <ScoreCard detail={data} />
        <FundamentalsCard detail={data} />
        <SimulatorCard securityId={data.id} />
        <NewsCard securityId={data.id} />
      </div>
    </section>
  );
}
```

Dans `frontend/src/app/router.tsx`, ajouter la route (dans `children`) :
```tsx
      { path: "titres/:id", lazy: async () => ({ Component: (await import("@/features/security/SecurityPage")).SecurityPage }) },
```

- [ ] **Step 3: Vérifier**

Run (dans `frontend/`) : `npm test && npm run build`
Expected: tests verts, build sans erreur.

- [ ] **Step 4: Commit**

```bash
git add frontend
git commit -m "feat: security page with chart, score breakdown, fundamentals, simulator, fees and news

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Réglages — corrections d'éligibilité

**Files:**
- Create: `frontend/src/features/settings/SettingsPage.tsx`
- Modify: `frontend/src/app/router.tsx`
- Test: `frontend/src/features/settings/SettingsPage.test.tsx`

**Interfaces:**
- Consumes: `GET /api/securities?q=&limit=10`, `GET /api/securities?overridden=true&limit=200`, `PATCH /api/securities/{id}/eligibility` (Task 9), `apiSend` (Task 10), `EligibilityBadge`.
- Produces: `SettingsPage` (h1 « Réglages ») ; route `/reglages`.

- [ ] **Step 1: Test (échoue)**

`frontend/src/features/settings/SettingsPage.test.tsx` :
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { SettingsPage } from "./SettingsPage";

afterEach(() => vi.unstubAllGlobals());

const GECINA = { id: 4, yahoo_ticker: "GFC.PA", symbol: "GFC", name: "Gecina", kind: "stock", market: "Euronext Paris",
  country: "FR", sector: "Real Estate", eligibility: "a_verifier", eligibility_source: "auto", eligibility_override: null,
  price: 90, change_pct: 0, as_of: null };

test("recherche un titre et corrige son éligibilité", async () => {
  const fetchMock = mockFetch((url) => {
    if (url.includes("overridden=true")) return { body: { items: [], total: 0 } };
    if (url.includes("/eligibility")) return { body: { ...GECINA, eligibility: "eligible", eligibility_source: "override", eligibility_override: "eligible" } };
    return { body: { items: [GECINA], total: 1 } };
  });
  renderWithProviders(<SettingsPage />);
  expect(screen.getByRole("heading", { level: 1, name: "Réglages" })).toBeInTheDocument();
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher un titre" }), "gec");
  const select = await screen.findByRole("combobox", { name: "Éligibilité de Gecina" });
  await userEvent.selectOptions(select, "eligible");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/securities/4/eligibility",
    expect.objectContaining({ method: "PATCH", body: JSON.stringify({ override: "eligible" }) })));
});

test("liste les corrections existantes", async () => {
  mockFetch((url) => url.includes("overridden=true")
    ? { body: { items: [{ ...GECINA, eligibility: "eligible", eligibility_source: "override", eligibility_override: "eligible" }], total: 1 } }
    : { body: { items: [], total: 0 } });
  renderWithProviders(<SettingsPage />);
  expect(await screen.findByText("Gecina")).toBeInTheDocument();
});
```

Run (dans `frontend/`) : `npm test`
Expected: FAIL.

- [ ] **Step 2: Implémenter**

`frontend/src/features/settings/SettingsPage.tsx` :
```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EligibilityBadge } from "@/features/explorer/EligibilityBadge";
import { apiGet, apiSend, type SecurityItem, type SecurityList } from "@/lib/api/client";
import { useDebouncedValue } from "@/lib/useDebouncedValue";

function OverrideRow({ item }: { item: SecurityItem }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (override: string | null) => apiSend("PATCH", `/api/securities/${item.id}/eligibility`, { override }),
    onSettled: () => {
      for (const key of ["settings-search", "overrides", "screener", "security", "top"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  return (
    <li className="flex items-center justify-between gap-4 py-2">
      <div className="min-w-0">
        <p className="truncate font-medium">{item.name}</p>
        <p className="text-xs text-muted-foreground">{item.symbol} · {item.market}</p>
      </div>
      <div className="flex items-center gap-3">
        <EligibilityBadge status={item.eligibility} />
        <select
          aria-label={`Éligibilité de ${item.name}`}
          value={item.eligibility_override ?? ""}
          onChange={(e) => mutation.mutate(e.target.value || null)}
          className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
        >
          <option value="">Automatique</option>
          <option value="eligible">Éligible</option>
          <option value="non_eligible">Non éligible</option>
        </select>
      </div>
    </li>
  );
}

export function SettingsPage() {
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

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Réglages</h1>
        <p className="mt-1 text-sm text-muted-foreground">Les réglages des frais et de l'assistant IA arriveront avec les lots suivants.</p>
      </header>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Éligibilité PEA — corrections manuelles</CardTitle>
          <p className="text-sm text-muted-foreground">
            L'éligibilité est déduite automatiquement du pays du siège (code ISIN). Si l'application Crédit Agricole
            dit autre chose pour un titre, corrigez-le ici : votre choix est prioritaire et conservé lors des mises à jour.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input type="search" aria-label="Rechercher un titre" placeholder="Nom, ticker ou ISIN (2 caractères minimum)…"
                 className="w-96 bg-white" value={search} onChange={(e) => setSearch(e.target.value)} />
          {results.data && (
            <ul className="divide-y divide-border">
              {results.data.items.map((item) => <OverrideRow key={item.id} item={item} />)}
              {results.data.items.length === 0 && <li className="py-2 text-sm text-muted-foreground">Aucun titre trouvé.</li>}
            </ul>
          )}
          <div>
            <h3 className="mb-1 text-sm font-semibold">Corrections en cours</h3>
            {overrides.data?.items.length ? (
              <ul className="divide-y divide-border">{overrides.data.items.map((item) => <OverrideRow key={item.id} item={item} />)}</ul>
            ) : (
              <p className="text-sm text-muted-foreground">Aucune correction pour l'instant.</p>
            )}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
```

Dans `frontend/src/app/router.tsx`, importer `SettingsPage` et remplacer la route `reglages` par `{ path: "reglages", element: <SettingsPage /> }`.

- [ ] **Step 3: Vérifier**

Run (dans `frontend/`) : `npm test && npm run build`
Expected: tests verts, build sans erreur.

- [ ] **Step 4: Commit**

```bash
git add frontend
git commit -m "feat: settings page with manual PEA eligibility overrides

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Test de fumée Playwright, vérification de bout en bout, README

**Files:**
- Create: `frontend/playwright.config.ts`, `frontend/e2e/smoke.spec.ts`
- Modify: `frontend/package.json`, `frontend/vite.config.ts`, `README.md`

**Interfaces:**
- Consumes: l'application complète sur `http://localhost:8095`.

- [ ] **Step 1: Playwright**

Run (dans `frontend/`) : `npm install -D @playwright/test && npx playwright install chromium`

`frontend/playwright.config.ts` :
```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8095", viewport: { width: 1440, height: 900 } },
});
```

`frontend/e2e/smoke.spec.ts` :
```ts
import { expect, test } from "@playwright/test";

test("l'accueil, l'explorateur et une fiche s'affichent", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Accueil" })).toBeVisible();
  await expect(page.getByText("Top 10 du moment")).toBeVisible();

  await page.getByRole("link", { name: "Explorer" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Explorer" })).toBeVisible();
  await page.getByRole("searchbox", { name: "Rechercher" }).fill("LVMH");
  await page.getByRole("row").filter({ hasText: "LVMH" }).first().click();

  await expect(page.getByRole("heading", { level: 1, name: /LVMH/i })).toBeVisible();
  await expect(page.getByText("Score mixte")).toBeVisible();
});
```

Dans `frontend/package.json`, ajouter le script `"e2e": "playwright test"`. Dans `frontend/vite.config.ts`, ajouter `exclude: ["e2e/**", "node_modules/**"]` à l'objet `test` (Vitest ne doit pas exécuter les tests Playwright).

- [ ] **Step 2: Démarrage complet**

Run (racine) : `docker compose up -d --build`
Attendre dans les journaux du worker `Fin de la tâche scores` : `docker compose logs worker | grep "tâche scores"`.

Run: `curl -s "http://localhost:8095/api/rankings/top" | head -c 600`
Expected: une liste de 10 titres avec `score` et `reasons` (si les fondamentaux ne sont pas encore chargés, les scores sont techniques uniquement et `available_ratio` vaut 0,5 : le top peut être vide — attendre la fin de la tâche `fundamentals`, environ une heure, ou vérifier que la réponse est `[]` et que l'accueil affiche le message d'attente).

- [ ] **Step 3: Test de fumée et vérification visuelle**

Run (dans `frontend/`) : `npm run e2e`
Expected: `1 passed`.

Vérifier visuellement (navigateur à 1440 px) : l'accueil (indices, top 10, hausses/baisses, carte du marché cliquable), l'explorateur (filtres, tri par en-tête, défilement fluide de ~1 800 lignes), la page ETF, une fiche (graphique en chandeliers avec MM50/MM200, RSI et MACD activables, périodes 1J→5A, score, fondamentaux, simulateur, actualités), les favoris (étoile), les réglages (correction d'éligibilité puis retour « Automatique »).

- [ ] **Step 4: README**

Dans `README.md`, ajouter après la section « Développement » :
````markdown
## Fonctionnalités (lot 2)

- **Accueil** : top 10 du score mixte, indices, plus fortes hausses/baisses, carte du marché.
- **Explorer / ETF** : tous les titres, filtres (secteur, pays, place, score, prix, liquidité, favoris) et tris, conservés dans l'URL.
- **Fiche d'un titre** : graphique TradingView (bougies, volume, moyennes 50/200 jours, RSI, MACD), score détaillé, fondamentaux, simulateur « et si j'avais investi », frais estimés, actualités.
- **Réglages** : corrections manuelles de l'éligibilité PEA.

Le score est recalculé toutes les 5 minutes pendant la séance. Il sert à trier et à comprendre, pas à prédire.

## Test de fumée

```bash
cd frontend && npx playwright install chromium   # une fois
npm run e2e                                        # l'application doit tourner sur http://localhost:8095
```
````

- [ ] **Step 5: Commit**

```bash
git add frontend README.md
git commit -m "test: Playwright smoke test and lot 2 README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
