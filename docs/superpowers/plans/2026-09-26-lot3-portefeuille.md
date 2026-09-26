# PEA Radar — Lot 3 (Portefeuille) : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Suivre le PEA : saisie manuelle des ordres (frais calculés selon la grille des réglages), positions avec PRU frais inclus, plus/moins-values, répartition et évolution de la valeur, compteur X/12 ordres de l'année (page Portefeuille + carte sur l'accueil), bouton « + J'ai acheté » sur la fiche, réglages de la caisse régionale.

**Architecture:** Les calculs (positions/PRU, contrôle des ventes, compteur, valeur reconstituée jour par jour) sont des fonctions pures dans `services/portfolio.py`, sans base ni réseau. Deux nouvelles tables : `orders` et `user_settings` (grille de frais en JSON), toutes deux rattachées à `user_id`. Les routes relisent les ordres de l'utilisateur, appellent les fonctions pures et convertissent les cours hors euro (NOK) avec `services/fx`. Côté interface, un dossier `features/portfolio/` porte la page, le formulaire d'ordre (fenêtre modale) et la carte compteur réutilisée sur l'accueil.

**Tech Stack:** Lots 1 et 2 + composant `dialog` shadcn (Base UI), `sonner` (notifications), ECharts `PieChart` et `LineChart`.

**Spec:** `docs/superpowers/specs/2026-09-26-pea-radar-design.md` (sections 3.3 T1, 3.4 `orders`/`user_settings`, 5.2 carte compteur, 5.5 bouton « + J'ai acheté », 5.6, 5.8 paramètres caisse, 8 notifications, 9 tests) · Lots précédents : `docs/superpowers/plans/2026-09-26-lot1-socle.md`, `docs/superpowers/plans/2026-09-26-lot2-decouverte.md`

## Global Constraints

- Tout ce qui est listé dans les Global Constraints des lots 1 et 2 reste valable (Python 3.12, SQLAlchemy 2 sync, Alembic, React + Vite + TS, Tailwind v4, shadcn/ui, TanStack Query, français, thème clair, ≥ 1280 px, port web 8095, aucun appel réseau en test, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` dans chaque commit).
- Toutes les données personnelles portent `user_id` ; les routes obtiennent l'utilisateur par `get_current_user` uniquement.
- Compteur : achats + ventes de l'année civile ; défaut 12 ordres minimum, 96 € de frais en cas de non-respect ; rythme attendu = `ordres_min × jours écoulés / jours de l'année`.
- Grille par défaut Intégral : 0,48 % jusqu'à 500 € (inclus), 0,18 % de 500 à 1 000 €, 0,12 % au-delà ; le taux de la tranche s'applique au montant total de l'ordre.
- PRU = prix de revient unitaire **frais d'achat inclus** (moyenne pondérée) ; une vente ne change pas le PRU ; une vente supérieure à la quantité détenue est refusée.
- Les prix des ordres sont saisis en euros (le PEA se paie en euros) ; les cours hors euro sont convertis avec `to_eur`.
- Quantités entières (pas de fractions d'action sur un PEA).
- Commandes : backend `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` ; frontend `cd frontend && npm test`.

## Review Focus

1. **Vente supérieure à la quantité détenue, y compris indirectement** (modifier un achat à la baisse ou supprimer un achat dont dépend une vente plus récente) → refus 422 avec un message en français, rien n'est enregistré. *Tests : Task 3 `test_create_sell_more_than_held_is_refused`, `test_edit_buy_that_breaks_later_sell_is_refused`, `test_delete_buy_that_breaks_later_sell_is_refused`.*
2. **Position soldée puis rachetée** → le PRU repart du nouvel achat, la plus-value réalisée est conservée. *Test : Task 2 `test_full_sale_then_rebuy_resets_cost`.*
3. **Titre détenu sans cours ni clôture** → le portefeuille s'affiche, cours « — », valeur = montant investi. *Test : Task 4 `test_portfolio_position_without_price`.*
4. **Premier lancement, aucun ordre** → chiffres à zéro, historique vide, compteur 0/12, page avec un état vide et un bouton d'ajout. *Tests : Task 4 `test_portfolio_empty`, Task 7 `affiche un état vide sans ordre`.*
5. **Ordre daté dans le futur ; grille de frais incohérente** (bornes non croissantes, taux > 5 %, dernière tranche bornée) → 422. *Tests : Task 3 `test_order_in_future_is_refused`, Task 1 `test_settings_rejects_invalid_grid`.*

---

## Structure des fichiers

```
backend/app/
├── models/portfolio.py             Order, UserSettings
├── alembic/versions/<rev>_orders_and_user_settings.py
├── services/fees.py                (modifié) grid_from_json, grid_to_json, DEFAULT_GRID_JSON
├── services/portfolio.py           OrderLine, Position, OversellError, compute_positions, order_counter, value_history
├── repositories/user_settings.py   get_user_settings, user_fee_grid
├── repositories/orders.py          list_orders, order_lines, held_security_ids, closes_since
├── schemas/settings.py             FeeTierIn, SettingsOut, SettingsUpdate
├── schemas/portfolio.py            OrderIn, OrderOut, CounterOut, PositionOut, SectorOut, PortfolioOut, HistoryPointOut
├── api/routes/settings.py          GET/PUT /api/settings
├── api/routes/orders.py            GET/POST /api/orders, PUT/DELETE /api/orders/{id}, GET /api/orders/counter
├── api/routes/portfolio.py         GET /api/portfolio, GET /api/portfolio/history
├── api/routes/fees.py              (modifié) grille de l'utilisateur
├── api/routes/security_detail.py   (modifié) simulateur avec la grille de l'utilisateur
└── jobs/tiers.py                   (modifié) T1 inclut les titres détenus
frontend/src/
├── lib/api/client.ts               (modifié) POST, message d'erreur de l'API
├── components/charts/EChart.tsx    (modifié) PieChart, LineChart, Grid, Legend
├── components/ui/dialog.tsx        (shadcn)
├── app/Layout.tsx                  (modifié) <Toaster />
├── features/portfolio/
│   ├── api.ts                      types + hooks (portefeuille, ordres, compteur, mutations)
│   ├── charts.ts                   buildAllocationOption, buildHistoryOption
│   ├── OrderCounterCard.tsx        carte X/12 (accueil + portefeuille)
│   ├── SecurityPicker.tsx          recherche d'un titre
│   ├── OrderDialog.tsx             formulaire d'ordre (création / modification)
│   ├── PositionsTable.tsx
│   ├── OrdersHistory.tsx
│   └── PortfolioPage.tsx
├── features/settings/FeeSettingsCard.tsx
├── features/home/HomePage.tsx      (modifié) carte compteur
└── features/security/SecurityPage.tsx (modifié) « + J'ai acheté »
```

---

### Task 1: Tables `orders` / `user_settings`, grille de frais de l'utilisateur, route Réglages

**Files:**
- Create: `backend/app/models/portfolio.py`, `backend/app/repositories/user_settings.py`, `backend/app/schemas/settings.py`, `backend/app/api/routes/settings.py`, migration Alembic, `backend/tests/test_api_settings.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/services/fees.py`, `backend/app/api/routes/fees.py`, `backend/app/api/routes/security_detail.py` (simulate), `backend/app/main.py`, `backend/tests/test_fees_fx.py`

**Interfaces:**
- Produces: `Order`, `UserSettings` ; `grid_from_json(list[dict]) -> tuple[FeeTier, ...]`, `grid_to_json(grid) -> list[dict]`, `DEFAULT_GRID_JSON` ; `get_user_settings(session, user_id) -> UserSettings`, `user_fee_grid(session, user_id) -> tuple[FeeTier, ...]` ; `GET/PUT /api/settings` → `SettingsOut{min_orders_per_year, penalty_fee, fee_grid: [{up_to, rate}]}`.

- [ ] **Step 1: Tests qui échouent**

`backend/tests/test_fees_fx.py` (ajout) :
```python
from app.services.fees import DEFAULT_GRID, DEFAULT_GRID_JSON, broker_fee, grid_from_json, grid_to_json


def test_grid_json_round_trip():
    assert grid_from_json(grid_to_json(DEFAULT_GRID)) == DEFAULT_GRID
    assert DEFAULT_GRID_JSON == [{"up_to": 500.0, "rate": 0.0048}, {"up_to": 1000.0, "rate": 0.0018}, {"up_to": None, "rate": 0.0012}]


def test_custom_grid_is_used():
    grid = grid_from_json([{"up_to": 1000.0, "rate": 0.01}, {"up_to": None, "rate": 0.005}])
    assert broker_fee(800, grid) == (8.0, 0.01)
    assert broker_fee(2000, grid) == (10.0, 0.005)
```

`backend/tests/test_api_settings.py` :
```python
from app.core.current_user import ensure_default_user
from app.models import UserSettings
from tests.factories import make_security


def test_settings_defaults(client):
    body = client.get("/api/settings").json()
    assert body == {"min_orders_per_year": 12, "penalty_fee": 96.0, "fee_grid": [
        {"up_to": 500.0, "rate": 0.0048}, {"up_to": 1000.0, "rate": 0.0018}, {"up_to": None, "rate": 0.0012}]}


def test_settings_update_and_fee_estimate_uses_grid(client, db):
    payload = {"min_orders_per_year": 10, "penalty_fee": 80, "fee_grid": [{"up_to": 1000, "rate": 0.01}, {"up_to": None, "rate": 0.005}]}
    assert client.put("/api/settings", json=payload).status_code == 200
    user = ensure_default_user(db)
    assert db.get(UserSettings, user.id).min_orders_per_year == 10
    assert client.get("/api/fees/estimate", params={"amount": 800}).json() == {"amount": 800.0, "fee": 8.0, "rate": 0.01}


def test_settings_rejects_invalid_grid(client):
    base = {"min_orders_per_year": 12, "penalty_fee": 96}
    for grid in (
        [{"up_to": 1000, "rate": 0.01}, {"up_to": 500, "rate": 0.005}, {"up_to": None, "rate": 0.001}],  # bornes décroissantes
        [{"up_to": None, "rate": 0.2}],                                                                 # taux > 5 %
        [{"up_to": 500, "rate": 0.01}],                                                                 # dernière tranche bornée
        [{"up_to": None, "rate": 0.01}, {"up_to": None, "rate": 0.01}],                                 # tranche illimitée au milieu
        [],
    ):
        assert client.put("/api/settings", json={**base, "fee_grid": grid}).status_code == 422, grid
    assert client.put("/api/settings", json={**base, "min_orders_per_year": -1, "fee_grid": [{"up_to": None, "rate": 0.01}]}).status_code == 422
```

- [ ] **Step 2: Lancer — échec** (`ImportError: grid_from_json`, 404 sur `/api/settings`).

- [ ] **Step 3: Implémentation**

`services/fees.py` (ajout) :
```python
def grid_from_json(data: list[dict]) -> tuple[FeeTier, ...]:
    return tuple(FeeTier(None if t.get("up_to") is None else float(t["up_to"]), float(t["rate"])) for t in data)


def grid_to_json(grid: tuple[FeeTier, ...]) -> list[dict]:
    return [{"up_to": t.up_to, "rate": t.rate} for t in grid]


DEFAULT_GRID_JSON = grid_to_json(DEFAULT_GRID)
```

`models/portfolio.py` :
```python
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.services.fees import DEFAULT_GRID_JSON


class Order(Base):
    """Ordre saisi à la main. Prix et frais en euros."""

    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_user_date", "user_id", "trade_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="RESTRICT"), index=True)
    trade_date: Mapped[date] = mapped_column(Date)
    side: Mapped[str] = mapped_column(String(4))  # buy | sell
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    min_orders_per_year: Mapped[int] = mapped_column(Integer, default=12)
    penalty_fee: Mapped[float] = mapped_column(Float, default=96.0)
    fee_grid: Mapped[list] = mapped_column(JSONB, default=lambda: list(DEFAULT_GRID_JSON))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```
Exporter `Order`, `UserSettings` dans `models/__init__.py`. Migration : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm api alembic revision --autogenerate -m "orders and user settings"` puis relire le fichier (ajouter `server_default` : `'12'`, `'96'`, et le JSON par défaut pour `fee_grid` via `sa.text("'[...]'::jsonb")`), `alembic upgrade head`.

`repositories/user_settings.py` :
```python
from sqlalchemy.orm import Session

from app.models import UserSettings
from app.services.fees import DEFAULT_GRID_JSON, FeeTier, grid_from_json


def get_user_settings(session: Session, user_id: int) -> UserSettings:
    settings = session.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id, min_orders_per_year=12, penalty_fee=96.0, fee_grid=list(DEFAULT_GRID_JSON))
        session.add(settings)
        session.commit()
    return settings


def user_fee_grid(session: Session, user_id: int) -> tuple[FeeTier, ...]:
    return grid_from_json(get_user_settings(session, user_id).fee_grid)
```

`schemas/settings.py` :
```python
from pydantic import BaseModel, Field, model_validator


class FeeTierIn(BaseModel):
    up_to: float | None = Field(default=None, gt=0, le=10_000_000)
    rate: float = Field(ge=0, le=0.05)


class SettingsOut(BaseModel):
    min_orders_per_year: int
    penalty_fee: float
    fee_grid: list[FeeTierIn]


class SettingsUpdate(BaseModel):
    min_orders_per_year: int = Field(ge=0, le=100)
    penalty_fee: float = Field(ge=0, le=1000)
    fee_grid: list[FeeTierIn] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def check_grid(self) -> "SettingsUpdate":
        *bounded, last = self.fee_grid
        if last.up_to is not None:
            raise ValueError("La dernière tranche doit être sans limite.")
        bounds = [t.up_to for t in bounded]
        if any(b is None for b in bounds) or bounds != sorted(set(bounds)):
            raise ValueError("Les bornes des tranches doivent être croissantes.")
        return self
```

`api/routes/settings.py` :
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import User
from app.repositories.user_settings import get_user_settings
from app.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(tags=["settings"])


def _out(settings) -> SettingsOut:
    return SettingsOut(min_orders_per_year=settings.min_orders_per_year, penalty_fee=settings.penalty_fee, fee_grid=settings.fee_grid)


@router.get("/settings", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SettingsOut:
    return _out(get_user_settings(db, user.id))


@router.put("/settings", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SettingsOut:
    settings = get_user_settings(db, user.id)
    settings.min_orders_per_year = payload.min_orders_per_year
    settings.penalty_fee = payload.penalty_fee
    settings.fee_grid = [t.model_dump() for t in payload.fee_grid]
    db.commit()
    return _out(settings)
```
`fees.py` : ajouter `db`/`user` en dépendances et `broker_fee(amount, user_fee_grid(db, user.id))`. `simulate` : `grid = user_fee_grid(db, user.id)` passé aux deux `broker_fee`. Enregistrer `settings` dans `main.py`.

- [ ] **Step 4: Lancer — tout passe** (suite complète).
- [ ] **Step 5: Commit** `feat: orders and user settings tables, user fee grid and settings API`

---

### Task 2: Calculs purs du portefeuille

**Files:**
- Create: `backend/app/services/portfolio.py`, `backend/tests/test_portfolio_service.py`

**Interfaces:**
- Produces:
  - `OrderLine(id: int, security_id: int, trade_date: date, side: str, quantity: int, unit_price: float, fee: float)` (dataclass figée)
  - `Position(security_id, quantity=0, cost=0.0, realized_gain=0.0)` avec la propriété `avg_cost -> float | None`
  - `OversellError(security_id, trade_date, held, requested)` (sous-classe de `ValueError`)
  - `compute_positions(orders: Iterable[OrderLine]) -> dict[int, Position]` (lève `OversellError`)
  - `OrderCounter(year, count, min_orders, remaining, expected_by_now, behind)` ; `order_counter(dates: Iterable[date], today: date, min_orders: int) -> OrderCounter`
  - `HistoryPoint(day: date, value: float, invested: float)` ; `value_history(orders, closes: dict[int, list[tuple[date, float]]], rates: dict[int, float], until: date) -> list[HistoryPoint]`

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_portfolio_service.py` :
```python
from datetime import date

import pytest

from app.services.portfolio import OrderLine, OversellError, compute_positions, order_counter, value_history


def line(id_, side, qty, price, fee=0.0, day=date(2026, 1, 5), sid=1):
    return OrderLine(id=id_, security_id=sid, trade_date=day, side=side, quantity=qty, unit_price=price, fee=fee)


def test_average_cost_includes_buy_fees():
    positions = compute_positions([line(1, "buy", 10, 50, 2.4), line(2, "buy", 10, 60, 2.88, day=date(2026, 2, 1))])
    p = positions[1]
    assert p.quantity == 20
    assert p.cost == pytest.approx(1105.28)
    assert p.avg_cost == pytest.approx(55.264)


def test_sale_keeps_average_cost_and_books_realized_gain():
    p = compute_positions([line(1, "buy", 10, 50, 5), line(2, "sell", 4, 70, 1, day=date(2026, 3, 1))])[1]
    assert p.quantity == 6
    assert p.avg_cost == pytest.approx(50.5)
    assert p.realized_gain == pytest.approx(4 * 70 - 1 - 4 * 50.5)


def test_full_sale_then_rebuy_resets_cost():
    p = compute_positions([
        line(1, "buy", 10, 50, 5), line(2, "sell", 10, 60, 3, day=date(2026, 2, 1)),
        line(3, "buy", 5, 80, 2, day=date(2026, 3, 1)),
    ])[1]
    assert p.quantity == 5
    assert p.avg_cost == pytest.approx(80.4)
    assert p.realized_gain == pytest.approx(600 - 3 - 505)


def test_oversell_raises_with_details():
    with pytest.raises(OversellError) as error:
        compute_positions([line(1, "buy", 3, 50), line(2, "sell", 5, 60, day=date(2026, 2, 1))])
    assert (error.value.held, error.value.requested, error.value.trade_date) == (3, 5, date(2026, 2, 1))


def test_sell_before_buy_in_time_is_oversell_even_if_entered_later():
    with pytest.raises(OversellError):
        compute_positions([line(2, "buy", 5, 50, day=date(2026, 3, 1)), line(1, "sell", 5, 60, day=date(2026, 2, 1))])


def test_same_day_buy_then_sell_is_allowed():
    p = compute_positions([line(2, "sell", 5, 60), line(1, "buy", 5, 50)])[1]
    assert p.quantity == 0 and p.avg_cost is None


def test_order_counter_on_pace_and_behind():
    dates = [date(2026, m, 1) for m in range(1, 9)] + [date(2025, 12, 31)]
    counter = order_counter(dates, today=date(2026, 9, 26), min_orders=12)
    assert (counter.year, counter.count, counter.remaining) == (2026, 8, 4)
    assert counter.expected_by_now == pytest.approx(8.8)
    assert counter.behind is False
    assert order_counter(dates[:5], today=date(2026, 9, 26), min_orders=12).behind is True


def test_order_counter_goal_reached_and_zero_goal():
    counter = order_counter([date(2026, 1, 2)] * 14, today=date(2026, 3, 1), min_orders=12)
    assert (counter.remaining, counter.behind) == (0, False)
    assert order_counter([], today=date(2026, 3, 1), min_orders=0).behind is False


def test_value_history_rebuilds_daily_value():
    orders = [line(1, "buy", 10, 10, 1, day=date(2026, 1, 5)), line(2, "buy", 5, 20, 0, day=date(2026, 1, 7), sid=2)]
    closes = {1: [(date(2026, 1, 2), 9.0), (date(2026, 1, 5), 10.0), (date(2026, 1, 6), 11.0), (date(2026, 1, 7), 12.0)],
              2: [(date(2026, 1, 7), 21.0)]}
    points = value_history(orders, closes, rates={1: 1.0, 2: 0.5}, until=date(2026, 1, 7))
    assert [(p.day, p.value, p.invested) for p in points] == [
        (date(2026, 1, 5), 100.0, 101.0), (date(2026, 1, 6), 110.0, 101.0), (date(2026, 1, 7), 172.5, 201.0)]


def test_value_history_empty_and_missing_close_uses_cost():
    assert value_history([], {}, {}, until=date(2026, 1, 7)) == []
    points = value_history([line(1, "buy", 2, 10, 0, day=date(2026, 1, 5), sid=1), line(2, "buy", 1, 30, 0, day=date(2026, 1, 5), sid=2)],
                           {1: [(date(2026, 1, 5), 12.0)]}, {1: 1.0, 2: 1.0}, until=date(2026, 1, 5))
    assert [(p.value, p.invested) for p in points] == [(54.0, 50.0)]
```

- [ ] **Step 2: Lancer — échec** (`ModuleNotFoundError`).

- [ ] **Step 3: Implémentation** — `backend/app/services/portfolio.py` :
```python
"""Calculs du portefeuille : fonctions pures, sans base ni réseau. Montants en euros."""

import calendar
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OrderLine:
    id: int
    security_id: int
    trade_date: date
    side: str  # buy | sell
    quantity: int
    unit_price: float
    fee: float


@dataclass
class Position:
    security_id: int
    quantity: int = 0
    cost: float = 0.0  # prix de revient total des titres encore détenus, frais d'achat inclus
    realized_gain: float = 0.0

    @property
    def avg_cost(self) -> float | None:
        return self.cost / self.quantity if self.quantity else None


class OversellError(ValueError):
    def __init__(self, security_id: int, trade_date: date, held: int, requested: int) -> None:
        super().__init__(f"Vente de {requested} titres alors que {held} sont détenus au {trade_date}")
        self.security_id = security_id
        self.trade_date = trade_date
        self.held = held
        self.requested = requested


def sort_orders(orders: Iterable[OrderLine]) -> list[OrderLine]:
    """Ordre chronologique ; le même jour, les achats passent avant les ventes."""
    return sorted(orders, key=lambda o: (o.trade_date, o.side == "sell", o.id))


def _apply(positions: dict[int, Position], order: OrderLine) -> None:
    position = positions.setdefault(order.security_id, Position(order.security_id))
    if order.side == "buy":
        position.quantity += order.quantity
        position.cost += order.quantity * order.unit_price + order.fee
        return
    if order.quantity > position.quantity:
        raise OversellError(order.security_id, order.trade_date, position.quantity, order.quantity)
    sold_cost = position.cost * order.quantity / position.quantity
    position.realized_gain += order.quantity * order.unit_price - order.fee - sold_cost
    position.quantity -= order.quantity
    position.cost = position.cost - sold_cost if position.quantity else 0.0


def compute_positions(orders: Iterable[OrderLine]) -> dict[int, Position]:
    positions: dict[int, Position] = {}
    for order in sort_orders(orders):
        _apply(positions, order)
    return positions


@dataclass(frozen=True)
class OrderCounter:
    year: int
    count: int
    min_orders: int
    remaining: int
    expected_by_now: float
    behind: bool


def order_counter(dates: Iterable[date], today: date, min_orders: int) -> OrderCounter:
    count = sum(1 for d in dates if d.year == today.year)
    days_in_year = 366 if calendar.isleap(today.year) else 365
    expected = min_orders * today.timetuple().tm_yday / days_in_year
    return OrderCounter(
        year=today.year, count=count, min_orders=min_orders, remaining=max(0, min_orders - count),
        expected_by_now=round(expected, 1), behind=count < min(min_orders, math.floor(expected)),
    )


@dataclass(frozen=True)
class HistoryPoint:
    day: date
    value: float
    invested: float


def value_history(
    orders: Iterable[OrderLine], closes: dict[int, list[tuple[date, float]]], rates: dict[int, float], until: date,
) -> list[HistoryPoint]:
    """Valeur du portefeuille à chaque séance depuis le premier ordre (clôtures converties en euros).

    Sans clôture connue pour un titre, sa valeur est son prix de revient.
    """
    ordered = sort_orders(orders)
    if not ordered:
        return []
    start = ordered[0].trade_date
    days = sorted({d for series in closes.values() for d, _ in series if start <= d <= until})
    positions: dict[int, Position] = {}
    last_close: dict[int, float] = {}
    cursors = {sid: 0 for sid in closes}
    next_order = 0
    points: list[HistoryPoint] = []
    for day in days:
        while next_order < len(ordered) and ordered[next_order].trade_date <= day:
            _apply(positions, ordered[next_order])
            next_order += 1
        for sid, series in closes.items():
            while cursors[sid] < len(series) and series[cursors[sid]][0] <= day:
                last_close[sid] = series[cursors[sid]][1]
                cursors[sid] += 1
        value = sum(
            p.quantity * last_close[sid] * rates.get(sid, 1.0) if sid in last_close else p.cost
            for sid, p in positions.items() if p.quantity
        )
        invested = sum(p.cost for p in positions.values())
        points.append(HistoryPoint(day, round(value, 2), round(invested, 2)))
    return points
```

- [ ] **Step 4: Lancer — tout passe.**
- [ ] **Step 5: Commit** `feat: pure portfolio computations (positions, average cost, order counter, value history)`

---

### Task 3: API des ordres et compteur

**Files:**
- Create: `backend/app/repositories/orders.py`, `backend/app/schemas/portfolio.py`, `backend/app/api/routes/orders.py`, `backend/tests/test_api_orders.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: Task 1 `Order`, `get_user_settings`, `user_fee_grid` ; Task 2 `OrderLine`, `compute_positions`, `OversellError`, `order_counter`.
- Produces:
  - `list_orders(session, user_id) -> list[tuple[Order, Security]]` (plus récent d'abord) ; `order_lines(session, user_id) -> list[OrderLine]` ; `held_security_ids(session) -> set[int]` ; `closes_since(session, ids, since) -> dict[int, list[tuple[date, float]]]`
  - `OrderIn`, `OrderOut{id, security_id, symbol, name, trade_date, side, quantity, unit_price, fee, amount, note}`, `CounterOut{year, count, min_orders, remaining, expected_by_now, behind, penalty_fee}`
  - `paris_today() -> date` dans `routes/orders.py` (réutilisée par la Task 4) ; `counter_for(db, user_id) -> CounterOut`
  - Routes : `GET /api/orders`, `POST /api/orders` (201), `PUT /api/orders/{id}`, `DELETE /api/orders/{id}` (204), `GET /api/orders/counter`. Refus → 422 `{"detail": "<message en français>"}`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_orders.py` :
```python
from datetime import date, timedelta

from app.models import Order
from tests.factories import make_security


def buy(security_id, qty=10, price=50.0, day="2026-03-02", **extra):
    return {"security_id": security_id, "trade_date": day, "side": "buy", "quantity": qty, "unit_price": price, **extra}


def test_create_order_computes_fee_from_grid(client, db):
    s = make_security(db, "MC.PA", name="LVMH")
    body = client.post("/api/orders", json=buy(s.id, qty=10, price=40)).json()
    assert body["fee"] == 1.92 and body["amount"] == 400.0 and body["name"] == "LVMH"
    body = client.post("/api/orders", json=buy(s.id, qty=10, price=60)).json()
    assert body["fee"] == 1.08  # 600 € → tranche 0,18 %


def test_manual_fee_is_kept(client, db):
    s = make_security(db, "MC.PA")
    assert client.post("/api/orders", json=buy(s.id, fee=0)).json()["fee"] == 0.0


def test_list_orders_most_recent_first(client, db):
    s = make_security(db, "MC.PA")
    client.post("/api/orders", json=buy(s.id, day="2026-01-05"))
    client.post("/api/orders", json=buy(s.id, day="2026-02-05"))
    assert [o["trade_date"] for o in client.get("/api/orders").json()] == ["2026-02-05", "2026-01-05"]


def test_create_sell_more_than_held_is_refused(client, db):
    s = make_security(db, "MC.PA", name="LVMH")
    client.post("/api/orders", json=buy(s.id, qty=3))
    response = client.post("/api/orders", json={**buy(s.id, qty=5, day="2026-04-01"), "side": "sell"})
    assert response.status_code == 422
    assert "3" in response.json()["detail"] and "LVMH" in response.json()["detail"]
    assert db.query(Order).count() == 1


def test_edit_buy_that_breaks_later_sell_is_refused(client, db):
    s = make_security(db, "MC.PA")
    first = client.post("/api/orders", json=buy(s.id, qty=10)).json()
    client.post("/api/orders", json={**buy(s.id, qty=8, day="2026-04-01"), "side": "sell"})
    assert client.put(f"/api/orders/{first['id']}", json=buy(s.id, qty=5)).status_code == 422
    assert client.put(f"/api/orders/{first['id']}", json=buy(s.id, qty=12, price=45)).json()["quantity"] == 12


def test_delete_buy_that_breaks_later_sell_is_refused(client, db):
    s = make_security(db, "MC.PA")
    first = client.post("/api/orders", json=buy(s.id, qty=10)).json()
    sale = client.post("/api/orders", json={**buy(s.id, qty=8, day="2026-04-01"), "side": "sell"}).json()
    assert client.delete(f"/api/orders/{first['id']}").status_code == 422
    assert client.delete(f"/api/orders/{sale['id']}").status_code == 204
    assert client.delete(f"/api/orders/{first['id']}").status_code == 204
    assert client.delete(f"/api/orders/{first['id']}").status_code == 404


def test_order_in_future_is_refused(client, db):
    s = make_security(db, "MC.PA")
    future = (date.today() + timedelta(days=3)).isoformat()
    assert client.post("/api/orders", json=buy(s.id, day=future)).status_code == 422


def test_order_validation(client, db):
    s = make_security(db, "MC.PA")
    assert client.post("/api/orders", json=buy(s.id, qty=0)).status_code == 422
    assert client.post("/api/orders", json=buy(s.id, price=-1)).status_code == 422
    assert client.post("/api/orders", json={**buy(s.id), "side": "short"}).status_code == 422
    assert client.post("/api/orders", json=buy(999999)).status_code == 404


def test_counter_counts_this_year(client, db):
    s = make_security(db, "MC.PA")
    today = date.today()
    client.post("/api/orders", json=buy(s.id, day=today.isoformat()))
    client.post("/api/orders", json=buy(s.id, day=date(today.year - 1, 6, 1).isoformat()))
    body = client.get("/api/orders/counter").json()
    assert (body["year"], body["count"], body["min_orders"], body["remaining"], body["penalty_fee"]) == (today.year, 1, 12, 11, 96.0)
```

- [ ] **Step 2: Lancer — échec** (404).

- [ ] **Step 3: Implémentation**

`repositories/orders.py` :
```python
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, Order, Security
from app.services.portfolio import OrderLine


def list_orders(session: Session, user_id: int) -> list[tuple[Order, Security]]:
    stmt = (select(Order, Security).join(Security, Security.id == Order.security_id)
            .where(Order.user_id == user_id).order_by(Order.trade_date.desc(), Order.id.desc()))
    return [(o, s) for o, s in session.execute(stmt)]


def to_line(order: Order) -> OrderLine:
    return OrderLine(id=order.id, security_id=order.security_id, trade_date=order.trade_date, side=order.side,
                     quantity=order.quantity, unit_price=order.unit_price, fee=order.fee)


def order_lines(session: Session, user_id: int) -> list[OrderLine]:
    return [to_line(o) for o in session.scalars(select(Order).where(Order.user_id == user_id))]


def held_security_ids(session: Session) -> set[int]:
    signed = func.sum(case((Order.side == "buy", Order.quantity), else_=-Order.quantity))
    return set(session.scalars(select(Order.security_id).group_by(Order.security_id).having(signed > 0)))


def closes_since(session: Session, ids: set[int], since: date) -> dict[int, list[tuple[date, float]]]:
    result: dict[int, list[tuple[date, float]]] = {sid: [] for sid in ids}
    if not ids:
        return result
    stmt = (select(DailyPrice.security_id, DailyPrice.date, DailyPrice.close)
            .where(DailyPrice.security_id.in_(ids), DailyPrice.date >= since).order_by(DailyPrice.date))
    for sid, day, close in session.execute(stmt):
        result[sid].append((day, close))
    return result
```

`schemas/portfolio.py` (partie ordres ; la Task 4 complète) :
```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class OrderIn(BaseModel):
    security_id: int
    trade_date: date
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0, le=1_000_000)
    unit_price: float = Field(gt=0, le=1_000_000)
    fee: float | None = Field(default=None, ge=0, le=10_000)
    note: str | None = Field(default=None, max_length=200)


class OrderOut(BaseModel):
    id: int
    security_id: int
    symbol: str
    name: str
    trade_date: date
    side: str
    quantity: int
    unit_price: float
    fee: float
    amount: float
    note: str | None


class CounterOut(BaseModel):
    year: int
    count: int
    min_orders: int
    remaining: int
    expected_by_now: float
    behind: bool
    penalty_fee: float
```

`api/routes/orders.py` :
```python
from dataclasses import replace
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import Order, Security, User
from app.repositories.orders import list_orders, order_lines, to_line
from app.repositories.user_settings import get_user_settings, user_fee_grid
from app.schemas.portfolio import CounterOut, OrderIn, OrderOut
from app.services.fees import broker_fee
from app.services.market_calendar import PARIS
from app.services.portfolio import OrderLine, OversellError, compute_positions, order_counter

router = APIRouter(tags=["orders"])


def paris_today():
    return datetime.now(PARIS).date()


def _out(order: Order, security: Security) -> OrderOut:
    return OrderOut(id=order.id, security_id=order.security_id, symbol=security.symbol, name=security.name,
                    trade_date=order.trade_date, side=order.side, quantity=order.quantity, unit_price=order.unit_price,
                    fee=order.fee, amount=round(order.quantity * order.unit_price, 2), note=order.note)


def _check(db: Session, lines: list[OrderLine]) -> None:
    try:
        compute_positions(lines)
    except OversellError as error:
        security = db.get(Security, error.security_id)
        name = security.name if security else "ce titre"
        raise HTTPException(status_code=422, detail=(
            f"Vente impossible : vous ne détenez que {error.held} titre(s) {name} au "
            f"{error.trade_date:%d/%m/%Y} (vente de {error.requested})."
        )) from None


def _security_or_404(db: Session, security_id: int) -> Security:
    security = db.get(Security, security_id)
    if security is None:
        raise HTTPException(status_code=404, detail="Titre introuvable")
    return security


def _validate(db: Session, user: User, payload: OrderIn) -> tuple[Security, float]:
    security = _security_or_404(db, payload.security_id)
    if payload.trade_date > paris_today():
        raise HTTPException(status_code=422, detail="La date de l'ordre ne peut pas être dans le futur.")
    fee = payload.fee
    if fee is None:
        fee, _ = broker_fee(payload.quantity * payload.unit_price, user_fee_grid(db, user.id))
    return security, round(fee, 2)


def _owned_or_404(db: Session, user: User, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Ordre introuvable")
    return order


@router.get("/orders", response_model=list[OrderOut])
def get_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[OrderOut]:
    return [_out(o, s) for o, s in list_orders(db, user.id)]


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(payload: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OrderOut:
    security, fee = _validate(db, user, payload)
    candidate = OrderLine(id=2**62, security_id=security.id, trade_date=payload.trade_date, side=payload.side,
                          quantity=payload.quantity, unit_price=payload.unit_price, fee=fee)
    _check(db, [*order_lines(db, user.id), candidate])
    order = Order(user_id=user.id, **payload.model_dump(exclude={"fee"}), fee=fee)
    db.add(order)
    db.commit()
    return _out(order, security)


@router.put("/orders/{order_id}", response_model=OrderOut)
def update_order(order_id: int, payload: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OrderOut:
    order = _owned_or_404(db, user, order_id)
    security, fee = _validate(db, user, payload)
    edited = replace(to_line(order), security_id=security.id, trade_date=payload.trade_date, side=payload.side,
                     quantity=payload.quantity, unit_price=payload.unit_price, fee=fee)
    _check(db, [edited if line.id == order.id else line for line in order_lines(db, user.id)])
    for key, value in payload.model_dump(exclude={"fee"}).items():
        setattr(order, key, value)
    order.fee = fee
    db.commit()
    return _out(order, security)


@router.delete("/orders/{order_id}", status_code=204)
def delete_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    order = _owned_or_404(db, user, order_id)
    _check(db, [line for line in order_lines(db, user.id) if line.id != order.id])
    db.delete(order)
    db.commit()
    return Response(status_code=204)


def counter_for(db: Session, user_id: int) -> CounterOut:
    settings = get_user_settings(db, user_id)
    counter = order_counter((line.trade_date for line in order_lines(db, user_id)), paris_today(), settings.min_orders_per_year)
    return CounterOut(**counter.__dict__, penalty_fee=settings.penalty_fee)


@router.get("/orders/counter", response_model=CounterOut)
def get_counter(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CounterOut:
    return counter_for(db, user.id)
```
Enregistrer `orders` dans `main.py` **avant** toute route `/orders/{order_id}` en GET (il n'y en a pas ; `/orders/counter` est un GET, `/{order_id}` n'existe qu'en PUT/DELETE).

- [ ] **Step 4: Lancer — tout passe.**
- [ ] **Step 5: Commit** `feat: orders API with automatic fees, oversell protection and yearly order counter`

---

### Task 4: API du portefeuille et rafraîchissement prioritaire des titres détenus

**Files:**
- Create: `backend/app/api/routes/portfolio.py`, `backend/tests/test_api_portfolio.py`
- Modify: `backend/app/schemas/portfolio.py`, `backend/app/main.py`, `backend/app/jobs/tiers.py`, `backend/tests/test_scheduler.py` (ou le fichier de test des tiers existant)

**Interfaces:**
- Consumes: Task 3 `order_lines`, `closes_since`, `held_security_ids`, `paris_today`, `counter_for` ; Task 2 `compute_positions`, `value_history`.
- Produces: `GET /api/portfolio` → `PortfolioOut{total_value, invested, gain, gain_pct, day_change, day_change_pct, realized_gain, positions: PositionOut[], sectors: SectorOut[], counter: CounterOut}` ; `GET /api/portfolio/history` → `HistoryPointOut[]{date, value, invested}`.
  - `PositionOut{security_id, symbol, name, sector, kind, quantity, avg_cost, price, change_pct, value, gain, gain_pct, weight}` (prix et valeurs en euros ; `price` nul si aucun cours).
  - `SectorOut{sector, value, weight}` ; secteur absent → « Autres », ETF → « ETF ».

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_portfolio.py` :
```python
from datetime import UTC, date, datetime

import pytest

from app.models import DailyPrice, SecurityQuote
from tests.factories import make_security


def order(client, sid, side="buy", qty=10, price=50.0, day="2026-03-02", fee=None):
    body = {"security_id": sid, "trade_date": day, "side": side, "quantity": qty, "unit_price": price}
    if fee is not None:
        body["fee"] = fee
    assert client.post("/api/orders", json=body).status_code == 201


def quote(db, sid, price, previous):
    db.add(SecurityQuote(security_id=sid, price=price, previous_close=previous, change_pct=(price / previous - 1) * 100,
                         volume=1, as_of=datetime(2026, 3, 10, 16, 0, tzinfo=UTC)))
    db.flush()


def test_portfolio_empty(client):
    body = client.get("/api/portfolio").json()
    assert (body["total_value"], body["invested"], body["gain"], body["positions"], body["sectors"]) == (0, 0, 0, [], [])
    assert body["gain_pct"] is None and body["counter"]["count"] == 0
    assert client.get("/api/portfolio/history").json() == []


def test_portfolio_positions_values_and_day_change(client, db):
    lvmh = make_security(db, "MC.PA", name="LVMH")
    lvmh.sector = "Consumer Cyclical"
    total = make_security(db, "TTE.PA", name="TotalEnergies")
    total.sector = "Energy"
    order(client, lvmh.id, qty=10, price=50, fee=0)
    order(client, total.id, qty=5, price=100, fee=0)
    order(client, total.id, side="sell", qty=5, price=110, fee=0, day="2026-03-05")
    quote(db, lvmh.id, 60, 55)
    body = client.get("/api/portfolio").json()
    assert [p["symbol"] for p in body["positions"]] == ["MC"]
    p = body["positions"][0]
    assert (p["quantity"], p["avg_cost"], p["price"], p["value"], p["gain"], p["weight"]) == (10, 50.0, 60.0, 600.0, 100.0, 1.0)
    assert p["gain_pct"] == pytest.approx(20.0)
    assert (body["total_value"], body["invested"], body["gain"], body["realized_gain"]) == (600.0, 500.0, 100.0, 50.0)
    assert body["day_change"] == 50.0 and body["day_change_pct"] == pytest.approx(50 / 550 * 100)
    assert body["sectors"] == [{"sector": "Consumer Cyclical", "value": 600.0, "weight": 1.0}]


def test_portfolio_position_without_price(client, db):
    s = make_security(db, "NEW.PA", name="Nouvelle")
    order(client, s.id, qty=4, price=25, fee=1)
    p = client.get("/api/portfolio").json()["positions"][0]
    assert p["price"] is None and p["value"] == 101.0 and p["gain"] == 0.0 and p["change_pct"] is None


def test_portfolio_uses_last_close_and_converts_nok(client, db):
    s = make_security(db, "NOKIA.OL", name="Nordic", market="Oslo Børs", country="NO")
    order(client, s.id, qty=10, price=8.5, fee=0)
    db.add(DailyPrice(security_id=s.id, date=date(2026, 3, 3), close=100.0))
    db.flush()
    p = client.get("/api/portfolio").json()["positions"][0]
    assert p["price"] == pytest.approx(8.5) and p["value"] == pytest.approx(85.0)


def test_portfolio_history_rebuilt_from_closes(client, db):
    s = make_security(db, "MC.PA")
    order(client, s.id, qty=2, price=10, fee=0, day="2026-03-02")
    for day, close in ((date(2026, 2, 27), 9.0), (date(2026, 3, 2), 10.0), (date(2026, 3, 3), 12.0)):
        db.add(DailyPrice(security_id=s.id, date=day, close=close))
    db.flush()
    points = client.get("/api/portfolio/history").json()
    assert [(p["date"], p["value"], p["invested"]) for p in points][:2] == [("2026-03-02", 20.0, 20.0), ("2026-03-03", 24.0, 20.0)]
```
Tiers (dans le fichier de tests existant des tiers) :
```python
def test_tier1_includes_held_securities(db, client):
    held = make_security(db, "HELD.PA")
    client.post("/api/orders", json={"security_id": held.id, "trade_date": "2026-03-02", "side": "buy", "quantity": 1, "unit_price": 10})
    assert "HELD.PA" in tier_tickers(db, 1, tier2_size=150)
```

- [ ] **Step 2: Lancer — échec** (404 / assertion tiers).

- [ ] **Step 3: Implémentation**

`schemas/portfolio.py` (ajout) :
```python
class PositionOut(BaseModel):
    security_id: int
    symbol: str
    name: str
    sector: str | None
    kind: str
    quantity: int
    avg_cost: float
    price: float | None
    change_pct: float | None
    value: float
    gain: float
    gain_pct: float | None
    weight: float


class SectorOut(BaseModel):
    sector: str
    value: float
    weight: float


class PortfolioOut(BaseModel):
    total_value: float
    invested: float
    gain: float
    gain_pct: float | None
    day_change: float
    day_change_pct: float | None
    realized_gain: float
    positions: list[PositionOut]
    sectors: list[SectorOut]
    counter: CounterOut


class HistoryPointOut(BaseModel):
    date: date
    value: float
    invested: float
```

`api/routes/portfolio.py` :
```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.orders import counter_for, paris_today
from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import DailyPrice, Security, SecurityQuote, User
from app.repositories.orders import closes_since, order_lines
from app.schemas.portfolio import HistoryPointOut, PortfolioOut, PositionOut, SectorOut
from app.services.fx import currency_for_market, to_eur
from app.services.market_calendar import PARIS
from app.services.portfolio import compute_positions, sort_orders, value_history

router = APIRouter(tags=["portfolio"])


def _rate(security: Security) -> float:
    return to_eur(1.0, currency_for_market(security.market)) or 1.0


def _last_close(db: Session, security_id: int) -> float | None:
    return db.scalars(select(DailyPrice.close).where(DailyPrice.security_id == security_id)
                      .order_by(DailyPrice.date.desc()).limit(1)).first()


def _pct(part: float, base: float) -> float | None:
    return round(part / base * 100, 2) if base else None


@router.get("/portfolio", response_model=PortfolioOut)
def get_portfolio(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> PortfolioOut:
    lines = order_lines(db, user.id)
    positions = compute_positions(lines)
    realized = round(sum(p.realized_gain for p in positions.values()), 2)
    open_positions = [p for p in positions.values() if p.quantity]
    rows: list[PositionOut] = []
    day_change = 0.0
    for p in open_positions:
        security = db.get(Security, p.security_id)
        quote = db.get(SecurityQuote, p.security_id)
        rate = _rate(security)
        native = quote.price if quote else _last_close(db, p.security_id)
        price = round(native * rate, 4) if native is not None else None
        value = round(p.quantity * price, 2) if price is not None else round(p.cost, 2)
        if quote and quote.previous_close:
            day_change += p.quantity * (quote.price - quote.previous_close) * rate
        gain = round(value - p.cost, 2)
        rows.append(PositionOut(
            security_id=security.id, symbol=security.symbol, name=security.name, sector=security.sector, kind=security.kind,
            quantity=p.quantity, avg_cost=round(p.avg_cost, 4), price=price,
            change_pct=quote.change_pct if quote else None, value=value, gain=gain, gain_pct=_pct(gain, p.cost), weight=0.0,
        ))
    total = round(sum(r.value for r in rows), 2)
    invested = round(sum(p.cost for p in open_positions), 2)
    sectors: dict[str, float] = {}
    for r in rows:
        r.weight = round(r.value / total, 4) if total else 0.0
        key = "ETF" if r.kind == "etf" else (r.sector or "Autres")
        sectors[key] = sectors.get(key, 0.0) + r.value
    rows.sort(key=lambda r: -r.value)
    day_change = round(day_change, 2)
    return PortfolioOut(
        total_value=total, invested=invested, gain=round(total - invested, 2), gain_pct=_pct(total - invested, invested),
        day_change=day_change, day_change_pct=_pct(day_change, total - day_change), realized_gain=realized,
        positions=rows,
        sectors=[SectorOut(sector=k, value=round(v, 2), weight=round(v / total, 4) if total else 0.0)
                 for k, v in sorted(sectors.items(), key=lambda kv: -kv[1])],
        counter=counter_for(db, user.id),
    )


@router.get("/portfolio/history", response_model=list[HistoryPointOut])
def get_portfolio_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[HistoryPointOut]:
    lines = order_lines(db, user.id)
    if not lines:
        return []
    ids = {line.security_id for line in lines}
    closes = closes_since(db, ids, sort_orders(lines)[0].trade_date)
    rates: dict[int, float] = {}
    for sid in ids:
        security = db.get(Security, sid)
        rates[sid] = _rate(security)
        quote = db.get(SecurityQuote, sid)
        if quote is not None:
            day = quote.as_of.astimezone(PARIS).date()
            if not closes[sid] or closes[sid][-1][0] < day:
                closes[sid].append((day, quote.price))
    return [HistoryPointOut(date=p.day, value=p.value, invested=p.invested)
            for p in value_history(lines, closes, rates, paris_today())]
```
`jobs/tiers.py` : `priority_ids = favorite_security_ids(session) | held_security_ids(session) | set(top_security_ids(session, TOP_IN_T1))` et docstring « T1 : indices, favoris, titres détenus et top 10 ».

- [ ] **Step 4: Lancer — tout passe** (suite complète).
- [ ] **Step 5: Commit** `feat: portfolio summary and value history API, held securities refreshed in tier 1`

---

### Task 5: Fondations interface — client POST, types, notifications, fenêtre modale, graphiques

**Files:**
- Modify: `frontend/src/lib/api/client.ts`, `frontend/src/lib/api/schema.d.ts` (régénéré), `frontend/src/components/charts/EChart.tsx`, `frontend/src/app/Layout.tsx`
- Create: `frontend/src/components/ui/dialog.tsx` (`npx shadcn@latest add dialog`), `frontend/src/features/portfolio/api.ts`, `frontend/src/features/portfolio/charts.ts`, `frontend/src/features/portfolio/charts.test.ts`, `frontend/src/lib/api/client.test.ts`
- Dépendance : `npm install sonner`

**Interfaces:**
- Produces:
  - `apiSend(method: "POST" | "PUT" | "DELETE" | "PATCH", path, body?)` ; en cas d'erreur, `ApiError.message` = `detail` renvoyé par l'API quand c'est une chaîne, sinon « Erreur N sur … ».
  - Types : `OrderIn`, `OrderOut`, `CounterOut`, `PortfolioOut`, `PositionOut`, `HistoryPointOut`, `SettingsOut`.
  - `features/portfolio/api.ts` : `usePortfolio()`, `usePortfolioHistory()`, `useOrders()`, `useOrderCounter()`, `useSaveOrder()` (mutation `{id?: number, order: OrderIn}` → POST ou PUT), `useDeleteOrder()` ; toutes les mutations invalident `["portfolio"]`, `["portfolio-history"]`, `["orders"]`, `["order-counter"]`.
  - `charts.ts` : `buildAllocationOption(slices: {name: string; value: number}[])` (anneau ECharts), `buildHistoryOption(points: HistoryPointOut[])` (deux courbes « Valeur » et « Montant investi »).

- [ ] **Step 1: Tests qui échouent**

`lib/api/client.test.ts` :
```ts
import { ApiError, apiSend } from "./client";
import { mockFetch } from "@/test/utils";

afterEach(() => vi.unstubAllGlobals());

test("apiSend POST envoie le corps JSON", async () => {
  const fetchMock = mockFetch(() => ({ status: 201, body: { id: 1 } }));
  expect(await apiSend("POST", "/api/orders", { a: 1 })).toEqual({ id: 1 });
  expect(fetchMock).toHaveBeenCalledWith("/api/orders", expect.objectContaining({ method: "POST", body: '{"a":1}' }));
});

test("apiSend remonte le message d'erreur de l'API", async () => {
  mockFetch(() => ({ status: 422, body: { detail: "Vente impossible : vous ne détenez que 3 titre(s)." } }));
  await expect(apiSend("POST", "/api/orders", {})).rejects.toEqual(expect.objectContaining({ status: 422, message: "Vente impossible : vous ne détenez que 3 titre(s)." }));
});

test("apiSend garde un message générique pour les erreurs de validation", async () => {
  mockFetch(() => ({ status: 422, body: { detail: [{ msg: "x" }] } }));
  await expect(apiSend("POST", "/api/orders", {})).rejects.toBeInstanceOf(ApiError);
});
```

`features/portfolio/charts.test.ts` :
```ts
import { buildAllocationOption, buildHistoryOption } from "./charts";

test("anneau de répartition", () => {
  const option = buildAllocationOption([{ name: "LVMH", value: 600 }, { name: "Total", value: 400 }]);
  expect(option.series[0].type).toBe("pie");
  expect(option.series[0].radius).toEqual(["55%", "80%"]);
  expect(option.series[0].data).toEqual([{ name: "LVMH", value: 600 }, { name: "Total", value: 400 }]);
});

test("courbe d'évolution : valeur et montant investi", () => {
  const option = buildHistoryOption([{ date: "2026-03-02", value: 20, invested: 20 }, { date: "2026-03-03", value: 24, invested: 20 }]);
  expect(option.xAxis.data).toEqual(["2026-03-02", "2026-03-03"]);
  expect(option.series.map((s) => s.name)).toEqual(["Valeur", "Montant investi"]);
  expect(option.series[0].data).toEqual([20, 24]);
});
```

- [ ] **Step 2: Lancer — échec.**

- [ ] **Step 3: Implémentation**

`client.ts` :
```ts
async function errorFrom(response: Response, path: string): Promise<ApiError> {
  let message = `Erreur ${response.status} sur ${path}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") message = body.detail;
  } catch { /* corps absent ou non JSON */ }
  return new ApiError(response.status, message);
}

export async function apiSend(method: "POST" | "PUT" | "DELETE" | "PATCH", path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(path, { /* inchangé */ });
  if (!response.ok) throw await errorFrom(response, path);
  return response.status === 204 ? null : response.json();
}
```
+ exports de types listés ci-dessus. Régénérer `schema.d.ts` : lancer l'API de dev (`docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d api`), puis `npm run gen:api`.

`charts.ts` :
```ts
import type { HistoryPointOut } from "@/lib/api/client";
import { formatPrice } from "@/lib/format";

export const PALETTE = ["#6366f1", "#0ea5e9", "#16a34a", "#f59e0b", "#ec4899", "#8b5cf6", "#14b8a6", "#f97316", "#64748b"];

export function buildAllocationOption(slices: { name: string; value: number }[]) {
  return {
    color: PALETTE,
    tooltip: { trigger: "item" as const, formatter: (p: { name: string; value: number; percent: number }) => `${p.name}<br/>${formatPrice(p.value)} € (${formatPrice(p.percent)} %)` },
    legend: { type: "scroll" as const, orient: "vertical" as const, right: 0, top: "middle", textStyle: { color: "#52525b" } },
    series: [{
      type: "pie" as const, radius: ["55%", "80%"], center: ["35%", "50%"], avoidLabelOverlap: true,
      itemStyle: { borderColor: "#ffffff", borderWidth: 2 }, label: { show: false }, data: slices,
    }],
  };
}

export function buildHistoryOption(points: HistoryPointOut[]) {
  return {
    color: ["#6366f1", "#a1a1aa"],
    tooltip: { trigger: "axis" as const, valueFormatter: (v: number) => `${formatPrice(v)} €` },
    legend: { top: 0, textStyle: { color: "#52525b" } },
    grid: { left: 60, right: 16, top: 32, bottom: 28 },
    xAxis: { type: "category" as const, data: points.map((p) => p.date), boundaryGap: false, axisLine: { lineStyle: { color: "#e4e4e7" } }, axisLabel: { color: "#71717a" } },
    yAxis: { type: "value" as const, scale: true, splitLine: { lineStyle: { color: "#f4f4f5" } }, axisLabel: { color: "#71717a" } },
    series: [
      { name: "Valeur", type: "line" as const, data: points.map((p) => p.value), showSymbol: false, smooth: true, areaStyle: { opacity: 0.08 } },
      { name: "Montant investi", type: "line" as const, data: points.map((p) => p.invested), showSymbol: false, step: "end" as const, lineStyle: { type: "dashed" as const } },
    ],
  };
}
```
`EChart.tsx` : `echarts.use([TreemapChart, PieChart, LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])`.
`Layout.tsx` : `import { Toaster } from "sonner"` et `<Toaster position="bottom-right" richColors />` dans le conteneur racine.
`api.ts` : hooks TanStack Query (`queryKey` ci-dessus ; `refetchInterval: 60_000` pour `["portfolio"]`).

- [ ] **Step 4: Lancer — tout passe** (`npm test`, `npm run build`).
- [ ] **Step 5: Commit** `feat: portfolio API client, chart options, dialog and toast foundations`

---

### Task 6: Formulaire d'ordre

**Files:**
- Create: `frontend/src/features/portfolio/SecurityPicker.tsx`, `frontend/src/features/portfolio/OrderDialog.tsx`, `frontend/src/features/portfolio/OrderDialog.test.tsx`

**Interfaces:**
- Consumes: Task 5 `useSaveOrder`, `apiGet`, types.
- Produces:
  - `type PickedSecurity = { id: number; name: string; symbol: string }`
  - `SecurityPicker({ value: PickedSecurity | null, onChange })` : champ de recherche (`/api/securities?q=…&limit=8`, 2 caractères minimum, anti-rebond 300 ms), liste de boutons ; titre choisi affiché avec un bouton « Changer ».
  - `OrderDialog({ open, onOpenChange, security?: PickedSecurity, price?: number, order?: OrderOut })` : champs Date (défaut aujourd'hui), Sens (Achat / Vente), Titre, Quantité, Prix unitaire (€), Frais (€) — estimés par `/api/fees/estimate` sur `quantité × prix` tant que l'utilisateur ne les a pas modifiés, Note. Affiche le montant total. Envoi : `fee` = valeur saisie si modifiée à la main, sinon `null` (le serveur calcule). Succès → notification « Ordre enregistré » et fermeture ; erreur → message de l'API affiché dans la fenêtre (rôle `alert`).

- [ ] **Step 1: Tests qui échouent** — `OrderDialog.test.tsx` :
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { OrderDialog } from "./OrderDialog";

afterEach(() => vi.unstubAllGlobals());
const LVMH = { id: 1, name: "LVMH", symbol: "MC" };

test("préremplit le titre, estime les frais et enregistre l'achat", async () => {
  const fetchMock = mockFetch((url) => {
    if (url.startsWith("/api/fees/estimate")) return { body: { amount: 400, fee: 1.92, rate: 0.0048 } };
    return { status: 201, body: { id: 7 } };
  });
  const onOpenChange = vi.fn();
  renderWithProviders(<OrderDialog open onOpenChange={onOpenChange} security={LVMH} price={40} />);
  expect(screen.getByText("LVMH")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Quantité"), "10");
  await waitFor(() => expect(screen.getByLabelText("Frais (€)")).toHaveValue("1,92"));
  expect(screen.getByText(/400,00 €/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  const post = fetchMock.mock.calls.find(([url]) => url === "/api/orders")!;
  expect(JSON.parse(post[1]!.body as string)).toMatchObject({ security_id: 1, side: "buy", quantity: 10, unit_price: 40, fee: null });
});

test("frais saisis à la main envoyés tels quels", async () => {
  const fetchMock = mockFetch((url) => url.startsWith("/api/fees") ? { body: { amount: 400, fee: 1.92, rate: 0.0048 } } : { status: 201, body: { id: 7 } });
  renderWithProviders(<OrderDialog open onOpenChange={() => {}} security={LVMH} price={40} />);
  await userEvent.type(screen.getByLabelText("Quantité"), "10");
  const fee = screen.getByLabelText("Frais (€)");
  await userEvent.clear(fee);
  await userEvent.type(fee, "0");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url === "/api/orders")).toBe(true));
  const post = fetchMock.mock.calls.find(([url]) => url === "/api/orders")!;
  expect(JSON.parse(post[1]!.body as string).fee).toBe(0);
});

test("affiche le refus du serveur (vente trop grande)", async () => {
  mockFetch((url) => url.startsWith("/api/fees") ? { body: { amount: 60, fee: 0.29, rate: 0.0048 } }
    : { status: 422, body: { detail: "Vente impossible : vous ne détenez que 3 titre(s) LVMH au 02/03/2026 (vente de 5)." } });
  renderWithProviders(<OrderDialog open onOpenChange={() => {}} security={LVMH} price={12} />);
  await userEvent.selectOptions(screen.getByLabelText("Sens"), "sell");
  await userEvent.type(screen.getByLabelText("Quantité"), "5");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("vous ne détenez que 3");
});

test("recherche un titre quand aucun n'est prérempli", async () => {
  mockFetch((url) => url.startsWith("/api/securities")
    ? { body: { items: [{ id: 2, name: "TotalEnergies", symbol: "TTE", market: "Euronext Paris" }], total: 1 } }
    : { body: { amount: 0, fee: 0, rate: 0 } });
  renderWithProviders(<OrderDialog open onOpenChange={() => {}} />);
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher un titre" }), "tot");
  await userEvent.click(await screen.findByRole("button", { name: /TotalEnergies/ }));
  expect(screen.getByRole("button", { name: "Changer" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Lancer — échec.**

- [ ] **Step 3: Implémentation** — composants selon les interfaces ci-dessus. Détails obligatoires :
  - Saisie des nombres acceptant la virgule (`Number(v.replace(",", "."))`), champs en `inputMode="decimal"` ; bouton « Enregistrer » désactivé tant que titre, quantité entière > 0 et prix > 0 ne sont pas valides.
  - Frais affichés avec virgule (`formatPrice`), état `feeTouched` ; au premier changement manuel, l'estimation ne l'écrase plus.
  - En modification (`order` fourni) : champs préremplis, `feeTouched = true` (on garde les frais enregistrés), titre « Modifier l'ordre », envoi en PUT.
  - `<select aria-label="Sens">` avec `buy` « Achat » et `sell` « Vente » ; `<input type="date" aria-label="Date">` avec `max` = aujourd'hui.
- [ ] **Step 4: Lancer — tout passe.**
- [ ] **Step 5: Commit** `feat: order form with security search, automatic fees and server-side refusals`

---

### Task 7: Page Portefeuille

**Files:**
- Create: `frontend/src/features/portfolio/OrderCounterCard.tsx`, `PositionsTable.tsx`, `OrdersHistory.tsx`, `PortfolioPage.tsx`, `PortfolioPage.test.tsx`
- Modify: `frontend/src/app/router.tsx` (route `portefeuille` en `lazy`)

**Interfaces:**
- Consumes: Task 5 hooks et options, Task 6 `OrderDialog`.
- Produces: `OrderCounterCard()` (lit `useOrderCounter`) ; `PortfolioPage`.

Contenu de la page (spec 5.6) :
- En-tête « Portefeuille » (h1) + bouton « + Nouvel ordre ».
- 4 chiffres clés : Valeur totale, Montant investi, Plus/moins-value (€ et %, couleur), Variation du jour ; ligne discrète « Plus-values réalisées ».
- `OrderCounterCard` : « {count}/{min_orders} ordres en {year} », barre de progression, « Il en reste {remaining} d'ici le 31/12 pour éviter ≈ {penalty_fee} € de frais. » ; si `behind` : alerte « En retard sur le rythme : environ {floor(expected_by_now)} ordres attendus à cette date. » ; si `remaining == 0` : « Objectif atteint ✅ ».
- Deux anneaux (par titre, par secteur) et la courbe d'évolution.
- `PositionsTable` : Titre (lien vers la fiche), Quantité, PRU, Cours, Valeur, +/- value (€ et %), Poids.
- `OrdersHistory` : Date, Sens (badge Achat/Vente), Titre, Quantité, Prix, Frais, Montant ; boutons « Modifier » (ouvre `OrderDialog` avec `order`) et « Supprimer » (confirmation `window.confirm`, puis `useDeleteOrder` ; erreur → notification avec le message de l'API).
- Aucun ordre : carte « Aucun ordre pour l'instant » + explication + bouton « Ajouter mon premier ordre » (les graphiques et tableaux sont masqués).

- [ ] **Step 1: Tests qui échouent** — `PortfolioPage.test.tsx` :
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { PortfolioPage } from "./PortfolioPage";

vi.mock("@/components/charts/EChart", () => ({ EChart: () => <div data-testid="echart" /> }));
afterEach(() => vi.unstubAllGlobals());

const COUNTER = { year: 2026, count: 5, min_orders: 12, remaining: 7, expected_by_now: 8.8, behind: true, penalty_fee: 96 };
const EMPTY = { total_value: 0, invested: 0, gain: 0, gain_pct: null, day_change: 0, day_change_pct: null, realized_gain: 0, positions: [], sectors: [], counter: { ...COUNTER, count: 0, remaining: 12 } };
const FULL = {
  total_value: 600, invested: 500, gain: 100, gain_pct: 20, day_change: 50, day_change_pct: 9.09, realized_gain: 50,
  positions: [{ security_id: 1, symbol: "MC", name: "LVMH", sector: "Luxe", kind: "stock", quantity: 10, avg_cost: 50, price: 60, change_pct: 9.09, value: 600, gain: 100, gain_pct: 20, weight: 1 }],
  sectors: [{ sector: "Luxe", value: 600, weight: 1 }], counter: COUNTER,
};
const ORDERS = [{ id: 3, security_id: 1, symbol: "MC", name: "LVMH", trade_date: "2026-03-02", side: "buy", quantity: 10, unit_price: 50, fee: 2.4, amount: 500, note: null }];

function api(portfolio: unknown, orders: unknown[], onDelete?: () => { status: number; body: unknown }) {
  return mockFetch((url) => {
    if (url === "/api/portfolio") return { body: portfolio };
    if (url === "/api/portfolio/history") return { body: [] };
    if (url === "/api/orders/counter") return { body: (portfolio as typeof FULL).counter };
    if (url === "/api/orders/3") return onDelete ? onDelete() : { status: 204, body: null };
    if (url === "/api/orders") return { body: orders };
    return { body: { amount: 0, fee: 0, rate: 0 } };
  });
}

test("affiche un état vide sans ordre", async () => {
  api(EMPTY, []);
  renderWithProviders(<PortfolioPage />);
  expect(screen.getByRole("heading", { level: 1, name: "Portefeuille" })).toBeInTheDocument();
  expect(await screen.findByText("Aucun ordre pour l'instant")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ajouter mon premier ordre" })).toBeInTheDocument();
});

test("affiche chiffres clés, compteur en retard, positions et historique", async () => {
  api(FULL, ORDERS);
  renderWithProviders(<PortfolioPage />);
  expect(await screen.findByText("600,00 €")).toBeInTheDocument();
  expect(screen.getByText("5/12 ordres en 2026")).toBeInTheDocument();
  expect(screen.getByText(/En retard sur le rythme/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "LVMH" })).toHaveAttribute("href", "/titres/1");
  expect(await screen.findByText("Achat")).toBeInTheDocument();
});

test("supprimer un ordre refusé affiche le message du serveur", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const fetchMock = api(FULL, ORDERS, () => ({ status: 422, body: { detail: "Vente impossible : vous ne détenez que 0 titre(s) LVMH." } }));
  renderWithProviders(<PortfolioPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer l'ordre du 02/03/2026" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/orders/3", expect.objectContaining({ method: "DELETE" })));
});
```

- [ ] **Step 2: Lancer — échec.**
- [ ] **Step 3: Implémentation** selon le contenu ci-dessus ; route `{ path: "portefeuille", lazy: async () => ({ Component: (await import("@/features/portfolio/PortfolioPage")).PortfolioPage }) }`.
- [ ] **Step 4: Lancer — tout passe** (`npm test`, `npm run build`).
- [ ] **Step 5: Commit** `feat: portfolio page with key figures, order counter, allocation and value charts, positions and order history`

---

### Task 8: Accueil, fiche action et Réglages

**Files:**
- Create: `frontend/src/features/settings/FeeSettingsCard.tsx`
- Modify: `frontend/src/features/home/HomePage.tsx` (+ test), `frontend/src/features/security/SecurityPage.tsx` (+ test), `frontend/src/features/settings/SettingsPage.tsx` (+ test)

**Interfaces:**
- Consumes: `OrderCounterCard`, `OrderDialog`, `GET/PUT /api/settings`.

Détails :
- Accueil : colonne de droite = `OrderCounterCard` au-dessus de `Movers`.
- Fiche : bouton « + J'ai acheté » à côté de l'étoile ; ouvre `OrderDialog` avec `security = {id, name, symbol}` et `price = data.price` seulement si la devise est l'euro.
- Réglages : carte « Frais et obligations de la caisse régionale » : Ordres minimum par an, Frais en cas de non-respect (€), tranches (borne haute en € — vide pour la dernière — et taux en %, affiché ×100), boutons « Enregistrer » et « Revenir à la grille Intégral ». Succès → notification « Réglages enregistrés » et invalidation de `["settings"]`, `["order-counter"]`, `["portfolio"]`, `["fee"]` ; erreur → message de l'API. Le texte d'en-tête de la page devient « Réglages de l'application ».

- [ ] **Step 1: Tests qui échouent**
  - `HomePage.test.tsx` : ajouter `/api/orders/counter` au faux serveur, et `expect(await screen.findByText("3/12 ordres en 2026")).toBeInTheDocument()`.
  - `SecurityPage.test.tsx` : `await userEvent.click(screen.getByRole("button", { name: "+ J'ai acheté" }))` puis `expect(await screen.findByRole("dialog")).toHaveTextContent("Nouvel ordre")`.
  - `SettingsPage.test.tsx` :
```tsx
test("modifie la grille de frais", async () => {
  const fetchMock = mockFetch((url) => {
    if (url === "/api/settings") return { body: { min_orders_per_year: 12, penalty_fee: 96, fee_grid: [{ up_to: 500, rate: 0.0048 }, { up_to: 1000, rate: 0.0018 }, { up_to: null, rate: 0.0012 }] } };
    return { body: { items: [], total: 0 } };
  });
  renderWithProviders(<SettingsPage />);
  const minOrders = await screen.findByLabelText("Ordres minimum par an");
  await userEvent.clear(minOrders);
  await userEvent.type(minOrders, "10");
  const rate = screen.getByLabelText("Taux de la tranche 1 (%)");
  await userEvent.clear(rate);
  await userEvent.type(rate, "0,5");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer les frais" }));
  await waitFor(() => {
    const put = fetchMock.mock.calls.find(([url, init]) => url === "/api/settings" && init?.method === "PUT")!;
    expect(JSON.parse(put[1]!.body as string)).toEqual({ min_orders_per_year: 10, penalty_fee: 96,
      fee_grid: [{ up_to: 500, rate: 0.005 }, { up_to: 1000, rate: 0.0018 }, { up_to: null, rate: 0.0012 }] });
  });
});
```
- [ ] **Step 2: Lancer — échec.**
- [ ] **Step 3: Implémentation** (taux : `Math.round(pourcentage × 100) / 10000` pour éviter 0,005000000001).
- [ ] **Step 4: Lancer — tout passe** (`npm test`, `npm run build`).
- [ ] **Step 5: Commit** `feat: order counter on home, "J'ai acheté" button on security page, broker fee settings`

---

### Task 9: Vérification de bout en bout et documentation

**Files:**
- Modify: `frontend/e2e/smoke.spec.ts`, `README.md`

- [ ] **Step 1:** Ajouter au test de fumée : aller sur `/portefeuille`, vérifier le titre « Portefeuille » et le compteur (`/ordres en \d{4}/`).
- [ ] **Step 2:** Reconstruire la pile (`docker compose up -d --build`), appliquer la migration (le conteneur `api` exécute `alembic upgrade head` au démarrage), lancer `npm run e2e` → PASS.
- [ ] **Step 3:** Vérification manuelle par l'API : créer un achat, lire `/api/portfolio`, supprimer l'ordre.
- [ ] **Step 4:** README : section « Lot 3 — Portefeuille » (saisie d'ordres, PRU, compteur, réglages des frais).
- [ ] **Step 5: Commit** `test: portfolio smoke test and lot 3 README`
