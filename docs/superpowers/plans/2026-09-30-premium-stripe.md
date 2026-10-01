# Abonnement Premium (Stripe) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un membre s'abonne à Premium (mensuel ou annuel) par Stripe Checkout, gère son abonnement dans le portail Stripe, et Premium ouvre l'assistant IA et les prévisions ; l'état est tenu à jour par les webhooks et une synchronisation de nuit.

**Architecture:** Un paquet `backend/app/services/billing/` : une interface `BillingGateway` (seul point de contact avec Stripe, remplacée par `FakeBilling` en test), la règle d'accès (`access.py`), l'application d'un état Stripe avec ses mails (`state.py`), le paiement (`checkout.py`). Des routes `/api/billing/*`, des tâches worker dans `app/jobs/billing.py`. Côté site : une carte `PremiumCard` réutilisée aux endroits réservés, les pages `/premium`, `/premium/merci`, `/cgv`, et une carte « Abonnement » dans les Réglages.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, APScheduler, Jinja2, bibliothèque `stripe` (>= 15) ; React 19, TanStack Query, react-router 7, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-30-premium-stripe-design.md` (suite de `2026-09-28-comptes-utilisateurs-design.md` § 1.5, 4.3, 6.1).

**Branche :** `premium`, créée depuis `notifications` (PR #6 et #7 pas encore fusionnées : la PR de ce lot visera `notifications`, ou `master` si #6 et #7 le sont).

## Global Constraints

- Textes affichés et mails en français simple ; identifiants de code en anglais ; commits en anglais, conventional commits, avec la ligne `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Premium = rôle `admin`, ou `is_premium` (« Premium offert »), ou abonnement au statut `active`, `past_due` ou `trialing` (spec 1.5).
- Réservé Premium : routes de l'assistant, `GET /api/forecasts`, `GET /api/securities/{id}/forecast`. Restent ouverts aux connectés : `/api/forecasts/signals`, `/api/forecasts/track-record` (spec 2).
- Aucune donnée de carte ne passe par PEA Radar ; tout appel Stripe passe par `BillingGateway` (spec 7).
- Webhook : signature vérifiée (tolérance 5 min), idempotent (`stripe_events`), l'état appliqué est toujours relu chez Stripe (spec 4.1).
- Deux cases obligatoires avant le paiement : CGV acceptées et renonciation au droit de rétractation (spec 3.1).
- Mails P1 à P5 = mails de compte, non désinscriptibles (spec 5).
- L'état de la configuration n'affiche jamais une valeur du `.env` (spec 6) ; ne jamais ouvrir `.env`.
- L'API n'envoie jamais de mail ; les services ne font jamais de commit ; `enqueue()` reste le seul point d'entrée de la file (CLAUDE.md).
- Tests backend : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` ; frontend depuis `frontend` : `npx vitest --run < /dev/null`, `npx tsc -b < /dev/null`, `npm run lint < /dev/null` (32 lignes déjà présentes, aucune nouvelle), `npm run build < /dev/null`.
- Pas de Python sur l'hôte : scripts d'édition en node dans le scratchpad si besoin.

## Rulings (décisions du plan, écarts à la spec)

1. **Résiliation Stripe à la suppression de compte par une file, pas en attente.** La spec 8 fait attendre la suppression si Stripe est injoignable. Le plan supprime le compte tout de suite et met l'identifiant d'abonnement dans une table `stripe_cancellations` (aucune donnée personnelle), traitée chaque minute par le worker jusqu'à réussite. Plus simple (aucun appel réseau dans `erase_account`, appelé par 3 routes) et le compte disparaît sans délai. Filet de sécurité : un webhook pour un utilisateur introuvable résilie aussi l'abonnement (spec 4.1).
2. **Mail du client Stripe mis à jour la nuit et au paiement seulement.** La spec 3.5 le fait au changement de mail. Le plan le fait dans la synchronisation de nuit (et au passage en caisse, via `customer_update`) : aucun appel Stripe dans les routes de profil et d'admin. Coût : une facture Stripe peut partir vers l'ancienne adresse pendant au plus 24 h.
3. **`cancel_at` compte comme une résiliation programmée.** Les versions récentes de l'API Stripe peuvent programmer la fin par `cancel_at` au lieu de `cancel_at_period_end` ; `cancel_at_period_end` enregistré = l'un ou l'autre, et la date de fin affichée = `cancel_at` s'il existe, sinon `current_period_end`.
4. **La fin de période se lit sur l'élément d'abonnement.** Depuis l'API 2025-03-31, `current_period_end` est sur `items.data[0]` ; la lecture accepte aussi l'ancien emplacement. De même, l'abonnement d'une facture se lit dans `parent.subscription_details.subscription`, ou `subscription` (ancien format).
5. **Un nouvel essai raté n'écrase pas un abonnement actif.** Si Stripe signale un abonnement différent de celui enregistré, sans accès, alors que celui enregistré donne accès, il est ignoré.
6. **Lien et badge Premium dans le menu du compte** (bas de la barre latérale) plutôt que dans la liste de navigation : un seul composant sait déjà qui est connecté.
7. **`/premium/merci` est une page privée** (connexion obligatoire) : elle appelle `/api/billing/sync`, qui exige une session.
8. **Nouvelle version des CGU `2026-10-05`** (CGU et confidentialité parlent de Stripe) ; `CGV_VERSION = "2026-10-05"`.

## Review Focus

1. **Webhook falsifié, rejoué ou dans le désordre** : rien n'est appliqué sans signature valide ; un événement rejoué n'envoie pas un deuxième mail ; un « abonnement créé » reçu après « abonnement supprimé » ne rend pas Premium (l'état est relu chez Stripe). Tests : Task 7 `test_bad_or_missing_signature_is_rejected`, `test_same_event_twice_is_applied_once`, `test_state_is_read_back_from_stripe`.
2. **Payer deux fois** : double clic, deuxième onglet, ou Premium offert qui s'abonne. Tests : Task 5 `test_already_subscribed_or_offered_cannot_checkout`, `test_checkout_is_rate_limited`.
3. **Session Stripe d'un autre compte** passée à `/api/billing/sync` : 404 sans rien appliquer. Test : Task 6 `test_sync_refuses_a_session_of_another_user`.
4. **Suppression d'un compte abonné** : plus aucun prélèvement ensuite, même si Stripe est injoignable à ce moment. Tests : Task 9 `test_erasing_a_subscriber_queues_the_cancellation`, Task 8 `test_cancellations_are_retried_until_stripe_answers`.
5. **Membre gratuit** : le serveur refuse les données réservées (403) et le site ne les demande pas. Tests : Task 4 `test_free_member_gets_403_on_reserved_forecasts`, Task 10 `ForecastCard ne demande pas la prévision sans Premium`.

---

# Bloc 1 — Socle backend (Tasks 1 à 4)

### Task 1: Tables, règle Premium et configuration

**Files:**
- Create: `backend/app/models/billing.py`, `backend/alembic/versions/b3c5d7e9f1a3_billing.py`, `backend/app/services/billing/__init__.py` (vide), `backend/app/services/billing/access.py`, `backend/tests/test_billing_access.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/models/user.py`, `backend/app/core/config.py`, `backend/app/core/terms.py`, `backend/app/schemas/auth.py` (`MeOut`), `backend/tests/factories.py` (`make_subscription`)

**Interfaces:**
- Produces:
  - modèles `Subscription`, `StripeEvent`, `BillingConsent`, `StripeCancellation` (exportés par `app.models`) ; relation `User.subscription: Subscription | None` ;
  - `access.ACCESS_STATUSES = frozenset({"active", "past_due", "trialing"})`, `access.premium_source(user) -> Literal["admin", "offered", "subscription", "none"]`, `access.subscription_gives_access(sub: Subscription | None) -> bool` ;
  - `User.has_premium` = `premium_source(user) != "none"` ;
  - `Settings.stripe_secret_key`, `stripe_webhook_secret`, `stripe_price_monthly`, `stripe_price_yearly` (str, défaut `""`), propriété `Settings.stripe_configured: bool` ;
  - `app.core.terms.CGV_VERSION = "2026-10-05"` (TERMS_VERSION inchangée jusqu'à la Task 13) ;
  - `User.premium_source` (propriété) et `MeOut.premium_source: str` ;
  - `tests.factories.make_subscription(db, user, *, status="active", interval="month", period_end=None, cancel=False, sub_id=None, customer_id=None) -> Subscription`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_billing_access.py` :

```python
from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.services.billing.access import premium_source
from tests.factories import make_subscription, make_user


def test_admin_and_offered_premium(db):
    assert premium_source(make_user(db, "a@example.com", role="admin")) == "admin"
    assert premium_source(make_user(db, "o@example.com", is_premium=True)) == "offered"
    assert premium_source(make_user(db, "f@example.com")) == "none"


@pytest.mark.parametrize("status, source", [
    ("active", "subscription"), ("past_due", "subscription"), ("trialing", "subscription"),
    ("canceled", "none"), ("unpaid", "none"), ("incomplete", "none"), ("incomplete_expired", "none"), ("paused", "none"),
])
def test_each_stripe_status(db, status, source):
    user = make_user(db, "s@example.com")
    make_subscription(db, user, status=status)
    db.refresh(user)
    assert premium_source(user) == source
    assert user.has_premium is (source != "none")


def test_offered_wins_over_a_canceled_subscription(db):
    user = make_user(db, "o@example.com", is_premium=True)
    make_subscription(db, user, status="canceled")
    db.refresh(user)
    assert premium_source(user) == "offered"


def test_me_exposes_the_source(client, db, user):
    make_subscription(db, user)
    db.refresh(user)
    body = client.get("/api/me").json()
    assert (body["has_premium"], body["premium_source"]) == (True, "subscription")


def test_stripe_configured_needs_the_four_variables():
    full = dict(stripe_secret_key="sk_test_x", stripe_webhook_secret="whsec_x", stripe_price_monthly="price_m",
                stripe_price_yearly="price_y")
    assert Settings(**full).stripe_configured
    assert not Settings(**{**full, "stripe_price_yearly": ""}).stripe_configured


def test_user_deletion_cascades(db):
    user = make_user(db, "c@example.com")
    make_subscription(db, user, period_end=datetime(2026, 11, 1, tzinfo=UTC))
    db.delete(user)
    db.flush()
    from app.models import Subscription
    assert db.query(Subscription).count() == 0
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_billing_access.py`
Expected: FAIL (`ModuleNotFoundError: app.services.billing` ou `ImportError: make_subscription`).

- [ ] **Step 3: Modèles** — `backend/app/models/billing.py` :

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Subscription(Base):
    """Abonnement Stripe d'un compte (spec 1.1) : une ligne au plus, écrite uniquement à partir de l'état lu chez Stripe."""

    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(20))
    interval: Mapped[str | None] = mapped_column(String(5))  # month | year
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    renewal_notice_sent_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StripeEvent(Base):
    """Événements Stripe déjà traités (spec 1.2) : un événement livré deux fois n'est appliqué qu'une fois."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BillingConsent(Base):
    """Preuve des accords donnés avant le paiement (spec 1.3)."""

    __tablename__ = "billing_consents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cgv_version: Mapped[str] = mapped_column(String(20))
    withdrawal_waiver: Mapped[bool] = mapped_column(Boolean)
    interval: Mapped[str] = mapped_column(String(5))
    checkout_session_id: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StripeCancellation(Base):
    """Abonnements à résilier chez Stripe après la suppression d'un compte (Ruling 1) : aucune donnée personnelle."""

    __tablename__ = "stripe_cancellations"

    subscription_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Dans `backend/app/models/__init__.py`, ajouter l'import `from app.models.billing import BillingConsent, StripeCancellation, StripeEvent, Subscription` et les quatre noms dans `__all__` (ordre alphabétique conservé).

Dans `backend/app/models/user.py`, ajouter `relationship` à l'import `sqlalchemy.orm`, puis dans `User` (après `last_seen_at`) :

```python
    subscription: Mapped["Subscription | None"] = relationship(lazy="select", passive_deletes=True)  # noqa: F821
```

et remplacer la propriété `has_premium` :

```python
    @property
    def has_premium(self) -> bool:
        """Accès à l'assistant et aux prévisions : admin, Premium offert ou abonnement actif (spec 1.5)."""
        from app.services.billing.access import premium_source

        return premium_source(self) != "none"
```

Pour que la chaîne `"Subscription"` se résolve, `app/models/__init__.py` importe déjà `billing` : rien d'autre à faire.

- [ ] **Step 4: Règle d'accès** — `backend/app/services/billing/access.py` :

```python
"""Qui est Premium (spec 1.5). Aucun appel à Stripe : l'état vient de la table `subscriptions`."""
from typing import Literal

from app.models import Subscription, User

ACCESS_STATUSES = frozenset({"active", "past_due", "trialing"})  # past_due : l'accès continue pendant les relances
PremiumSource = Literal["admin", "offered", "subscription", "none"]


def subscription_gives_access(sub: Subscription | None) -> bool:
    return sub is not None and sub.status in ACCESS_STATUSES


def premium_source(user: User) -> PremiumSource:
    if user.role == "admin":
        return "admin"
    if user.is_premium:
        return "offered"
    if subscription_gives_access(user.subscription):
        return "subscription"
    return "none"
```

- [ ] **Step 5: Migration** — `backend/alembic/versions/b3c5d7e9f1a3_billing.py` :

```python
"""billing: subscriptions, stripe events, billing consents, stripe cancellations

Revision ID: b3c5d7e9f1a3
Revises: a2b4c6d8e0f2
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c5d7e9f1a3"
down_revision: Union[str, Sequence[str], None] = "a2b4c6d8e0f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=False, unique=True),
        sa.Column("stripe_subscription_id", sa.String(255), unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("interval", sa.String(5)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("renewal_notice_sent_for", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "stripe_events",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stripe_events_received_at", "stripe_events", ["received_at"])
    op.create_table(
        "billing_consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cgv_version", sa.String(20), nullable=False),
        sa.Column("withdrawal_waiver", sa.Boolean(), nullable=False),
        sa.Column("interval", sa.String(5), nullable=False),
        sa.Column("checkout_session_id", sa.String(255)),
        sa.Column("ip", sa.String(64)),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_billing_consents_user_id", "billing_consents", ["user_id"])
    op.create_table(
        "stripe_cancellations",
        sa.Column("subscription_id", sa.String(255), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("stripe_cancellations")
    op.drop_index("ix_billing_consents_user_id", table_name="billing_consents")
    op.drop_table("billing_consents")
    op.drop_index("ix_stripe_events_received_at", table_name="stripe_events")
    op.drop_table("stripe_events")
    op.drop_table("subscriptions")
```

- [ ] **Step 6: Configuration, versions, `MeOut`, fabrique**

`backend/app/core/config.py`, après `turnstile_secret_key` :

```python

    # Stripe (spec 7) : les quatre sont nécessaires, sinon /premium affiche « L'abonnement arrive bientôt ».
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_monthly: str = ""
    stripe_price_yearly: str = ""

    @property
    def stripe_configured(self) -> bool:
        return all((self.stripe_secret_key, self.stripe_webhook_secret, self.stripe_price_monthly, self.stripe_price_yearly))
```

`backend/app/core/terms.py`, ajouter :

```python
# Version des CGV acceptée avant un paiement (billing_consents.cgv_version).
CGV_VERSION = "2026-10-05"
```

`backend/app/schemas/auth.py`, dans `MeOut` après `has_premium` : `premium_source: str  # admin | offered | subscription | none`.

`MeOut` est construit par `MeOut.model_validate(user)` (`from_attributes`) dans `me.py`, `auth.py` et `google.py` : une propriété `User.premium_source` suffit, sans toucher aux routes. Dans `backend/app/models/user.py`, après `has_premium` :

```python
    @property
    def premium_source(self) -> str:
        from app.services.billing.access import premium_source

        return premium_source(self)
```

`backend/tests/factories.py`, ajouter :

```python
def make_subscription(db: Session, user: User, *, status: str = "active", interval: str = "month",
                      period_end: datetime | None = None, cancel: bool = False, sub_id: str | None = None,
                      customer_id: str | None = None) -> "Subscription":
    from app.models import Subscription

    row = Subscription(user_id=user.id, stripe_customer_id=customer_id or f"cus_{user.id.hex[:12]}",
                       stripe_subscription_id=sub_id or f"sub_{user.id.hex[:12]}", status=status, interval=interval,
                       current_period_end=period_end or datetime(2026, 11, 1, tzinfo=UTC), cancel_at_period_end=cancel)
    db.add(row)
    db.flush()
    return row
```

- [ ] **Step 7: Lancer les tests**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_billing_access.py tests/test_api_profile.py tests/test_api_assistant_access.py tests/test_models.py`
Expected: PASS.

Vérifier aussi la migration sur la base de développement : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api alembic upgrade head` puis `alembic downgrade -1` puis `alembic upgrade head`. Expected: aucune erreur.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models backend/alembic/versions/b3c5d7e9f1a3_billing.py backend/app/services/billing backend/app/core backend/app/schemas/auth.py backend/tests/factories.py backend/tests/test_billing_access.py
git commit -m "feat(billing): subscription tables and premium access rule"
```

### Task 2: Passerelle Stripe et faux Stripe

**Files:**
- Create: `backend/app/services/billing/gateway.py`, `backend/app/services/billing/stripe_gateway.py`, `backend/tests/fake_billing.py`, `backend/tests/test_billing_gateway.py`
- Modify: `backend/pyproject.toml` (dépendance `stripe>=15`), `backend/app/api/deps.py` (`get_billing_gateway`), `backend/tests/conftest.py` (fixture `fake_billing`, surcharge dans `_build_app`)

**Interfaces:**
- Consumes: `Settings.stripe_*` (Task 1).
- Produces (`app.services.billing.gateway`) :
  - `@dataclass(frozen=True) StripeSubscription(id: str, customer_id: str, user_id: str | None, status: str, interval: str | None, current_period_end: datetime | None, cancel_at_period_end: bool, ends_at: datetime | None, latest_invoice: str | None, price_amount: int | None, currency: str | None)` ;
  - `@dataclass(frozen=True) Plan(interval: str, amount: int, currency: str)` (montant en centimes) ;
  - `@dataclass(frozen=True) CheckoutInfo(session_id: str, user_id: str | None, customer_id: str | None, subscription_id: str | None)` ;
  - `@dataclass(frozen=True) StripeEventIn(id: str, type: str, subscription_id: str | None, customer_id: str | None, user_id: str | None)` ;
  - exceptions `BillingUnavailable`, `InvalidSignature` ;
  - `subscription_from_dict(data: dict) -> StripeSubscription`, `event_from_dict(data: dict) -> StripeEventIn` (fonctions pures) ;
  - `class BillingGateway(Protocol)` : `plans() -> list[Plan]` ; `create_checkout(*, interval: str, user_id: str, email: str, customer_id: str | None, success_url: str, cancel_url: str) -> tuple[str, str]` (identifiant de session, URL) ; `checkout_session(session_id: str) -> CheckoutInfo | None` (None si la session est inconnue) ; `subscription(subscription_id: str) -> StripeSubscription` ; `portal(customer_id: str, return_url: str) -> str` ; `cancel_now(subscription_id: str) -> None` ; `update_customer_email(customer_id: str, email: str) -> None` ; `parse_event(payload: bytes, signature: str | None) -> StripeEventIn` ; propriété `mode -> Literal["test", "live"]`.
- Produces (`app.api.deps`) : `get_billing_gateway() -> BillingGateway | None` (None si Stripe n'est pas configuré).
- Produces (tests) : `tests.fake_billing.FakeBilling` (voir code), fixture `fake_billing`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_billing_gateway.py` :

```python
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime

import pytest

from app.services.billing.gateway import InvalidSignature, event_from_dict, subscription_from_dict
from app.services.billing.stripe_gateway import StripeGateway

PERIOD_END = 1793491200  # 2026-11-01 00:00 UTC


def _sub(**over):
    data = {"id": "sub_1", "customer": "cus_1", "status": "active", "metadata": {"user_id": "u-1"},
            "cancel_at_period_end": False, "cancel_at": None, "latest_invoice": "in_1",
            "items": {"data": [{"current_period_end": PERIOD_END,
                                "price": {"unit_amount": 499, "currency": "eur", "recurring": {"interval": "month"}}}]}}
    data.update(over)
    return data


def test_subscription_reads_the_period_on_the_item():
    sub = subscription_from_dict(_sub())
    assert (sub.id, sub.customer_id, sub.user_id, sub.status, sub.interval) == ("sub_1", "cus_1", "u-1", "active", "month")
    assert sub.current_period_end == datetime(2026, 11, 1, tzinfo=UTC)
    assert (sub.cancel_at_period_end, sub.ends_at, sub.latest_invoice) == (False, None, "in_1")
    assert (sub.price_amount, sub.currency) == (499, "eur")


def test_subscription_legacy_period_and_cancel_at():
    data = _sub(current_period_end=PERIOD_END, cancel_at=PERIOD_END - 86400)
    data["items"]["data"][0].pop("current_period_end")
    sub = subscription_from_dict(data)
    assert sub.current_period_end == datetime(2026, 11, 1, tzinfo=UTC)
    assert sub.cancel_at_period_end is True  # Ruling 3
    assert sub.ends_at == datetime(2026, 10, 31, tzinfo=UTC)


def test_expanded_customer_and_invoice_objects():
    sub = subscription_from_dict(_sub(customer={"id": "cus_9"}, latest_invoice={"id": "in_9"}))
    assert (sub.customer_id, sub.latest_invoice) == ("cus_9", "in_9")


@pytest.mark.parametrize("obj, expected", [
    ({"object": "checkout.session", "id": "cs_1", "subscription": "sub_1", "customer": "cus_1",
      "client_reference_id": "u-1", "metadata": {}}, ("sub_1", "cus_1", "u-1")),
    ({"object": "subscription", "id": "sub_2", "customer": "cus_2", "metadata": {"user_id": "u-2"}}, ("sub_2", "cus_2", "u-2")),
    ({"object": "invoice", "id": "in_3", "customer": "cus_3",
      "parent": {"subscription_details": {"subscription": "sub_3", "metadata": {"user_id": "u-3"}}}}, ("sub_3", "cus_3", "u-3")),
    ({"object": "invoice", "id": "in_4", "customer": "cus_4", "subscription": "sub_4"}, ("sub_4", "cus_4", None)),
])
def test_event_targets(obj, expected):
    event = event_from_dict({"id": "evt_1", "type": "x", "data": {"object": obj}})
    assert (event.subscription_id, event.customer_id, event.user_id) == expected


def _signed(payload: bytes, secret: str, at: int | None = None) -> str:
    at = at or int(time.time())
    sig = hmac.new(secret.encode(), f"{at}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={at},v1={sig}"


def test_parse_event_checks_the_signature():
    gateway = StripeGateway(secret_key="sk_test_x", webhook_secret="whsec_test", price_monthly="p_m", price_yearly="p_y")
    payload = json.dumps({"id": "evt_1", "type": "invoice.paid", "data": {"object": {"object": "invoice", "customer": "cus_1",
                                                                                     "subscription": "sub_1"}}}).encode()
    assert gateway.parse_event(payload, _signed(payload, "whsec_test")).id == "evt_1"
    for bad in (None, "", _signed(payload, "whsec_other"), _signed(payload, "whsec_test", at=int(time.time()) - 600)):
        with pytest.raises(InvalidSignature):
            gateway.parse_event(payload, bad)


def test_mode_comes_from_the_key_prefix():
    assert StripeGateway(secret_key="sk_live_x", webhook_secret="w", price_monthly="m", price_yearly="y").mode == "live"
    assert StripeGateway(secret_key="sk_test_x", webhook_secret="w", price_monthly="m", price_yearly="y").mode == "test"
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_billing_gateway.py`
Expected: FAIL (`ModuleNotFoundError: app.services.billing.gateway`).

- [ ] **Step 3: Interface et lecture des objets Stripe** — `backend/app/services/billing/gateway.py` :

```python
"""Seul point de contact avec Stripe (spec 7) : types normalisés, lecture des objets Stripe, interface.

Les objets Stripe arrivent en dictionnaires (JSON du webhook, ou `to_dict()` de la bibliothèque) ; les fonctions de
lecture sont pures et acceptent l'ancien et le nouveau format de l'API (Rulings 3 et 4).
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol


class BillingUnavailable(Exception):
    """Stripe injoignable ou en erreur : rien n'est enregistré, l'utilisateur est invité à réessayer."""


class InvalidSignature(Exception):
    """Webhook sans signature Stripe valide."""


@dataclass(frozen=True)
class StripeSubscription:
    id: str
    customer_id: str
    user_id: str | None
    status: str
    interval: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    ends_at: datetime | None  # date de fin programmée (cancel_at), sinon None
    latest_invoice: str | None
    price_amount: int | None  # centimes
    currency: str | None


@dataclass(frozen=True)
class Plan:
    interval: str  # month | year
    amount: int  # centimes, TTC
    currency: str


@dataclass(frozen=True)
class CheckoutInfo:
    session_id: str
    user_id: str | None
    customer_id: str | None
    subscription_id: str | None


@dataclass(frozen=True)
class StripeEventIn:
    id: str
    type: str
    subscription_id: str | None
    customer_id: str | None
    user_id: str | None


def _id(value) -> str | None:
    """Un identifiant, ou l'objet « déplié » qui le contient."""
    if isinstance(value, dict):
        return value.get("id")
    return value or None


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if value else None


def subscription_from_dict(data: dict) -> StripeSubscription:
    items = (data.get("items") or {}).get("data") or [{}]
    item = items[0]
    price = item.get("price") or {}
    period_end = item.get("current_period_end") or data.get("current_period_end")
    cancel_at = data.get("cancel_at")
    return StripeSubscription(
        id=data["id"], customer_id=_id(data.get("customer")), user_id=(data.get("metadata") or {}).get("user_id"),
        status=data["status"], interval=(price.get("recurring") or {}).get("interval"),
        current_period_end=_ts(period_end), cancel_at_period_end=bool(data.get("cancel_at_period_end") or cancel_at),
        ends_at=_ts(cancel_at), latest_invoice=_id(data.get("latest_invoice")),
        price_amount=price.get("unit_amount"), currency=price.get("currency"),
    )


def event_from_dict(data: dict) -> StripeEventIn:
    obj = data["data"]["object"]
    kind = obj.get("object")
    user_id = (obj.get("metadata") or {}).get("user_id")
    if kind == "checkout.session":
        subscription_id, user_id = _id(obj.get("subscription")), obj.get("client_reference_id") or user_id
    elif kind == "subscription":
        subscription_id = obj["id"]
    elif kind == "invoice":
        details = (obj.get("parent") or {}).get("subscription_details") or {}
        subscription_id = _id(details.get("subscription")) or _id(obj.get("subscription"))
        user_id = (details.get("metadata") or {}).get("user_id")
    else:
        subscription_id = None
    return StripeEventIn(id=data["id"], type=data["type"], subscription_id=subscription_id,
                         customer_id=_id(obj.get("customer")), user_id=user_id)


class BillingGateway(Protocol):
    @property
    def mode(self) -> Literal["test", "live"]: ...

    def plans(self) -> list[Plan]: ...

    def create_checkout(self, *, interval: str, user_id: str, email: str, customer_id: str | None, success_url: str,
                        cancel_url: str) -> tuple[str, str]: ...

    def checkout_session(self, session_id: str) -> CheckoutInfo | None: ...

    def subscription(self, subscription_id: str) -> StripeSubscription: ...

    def portal(self, customer_id: str, return_url: str) -> str: ...

    def cancel_now(self, subscription_id: str) -> None: ...

    def update_customer_email(self, customer_id: str, email: str) -> None: ...

    def parse_event(self, payload: bytes, signature: str | None) -> StripeEventIn: ...
```

- [ ] **Step 4: Implémentation Stripe** — ajouter `"stripe>=15",` à la liste `dependencies` de `backend/pyproject.toml`, puis `backend/app/services/billing/stripe_gateway.py` :

```python
"""Implémentation de BillingGateway avec la bibliothèque officielle `stripe` (StripeClient, espace v1)."""
import json
from typing import Literal

import stripe

from app.services.billing.gateway import (
    BillingUnavailable, CheckoutInfo, InvalidSignature, Plan, StripeEventIn, StripeSubscription, event_from_dict,
    subscription_from_dict,
)

TOLERANCE_SECONDS = 300


class StripeGateway:
    def __init__(self, *, secret_key: str, webhook_secret: str, price_monthly: str, price_yearly: str):
        self._client = stripe.StripeClient(secret_key, max_network_retries=2)
        self._webhook_secret = webhook_secret
        self._prices = {"month": price_monthly, "year": price_yearly}
        self._live = secret_key.startswith(("sk_live_", "rk_live_"))

    @property
    def mode(self) -> Literal["test", "live"]:
        return "live" if self._live else "test"

    def _call(self, fn, *args, **kwargs) -> dict:
        try:
            return fn(*args, **kwargs).to_dict()
        except stripe.StripeError as error:
            raise BillingUnavailable(str(error)) from error

    def plans(self) -> list[Plan]:
        plans = []
        for interval, price_id in self._prices.items():
            price = self._call(self._client.v1.prices.retrieve, price_id)
            plans.append(Plan(interval=interval, amount=price["unit_amount"], currency=price["currency"]))
        return plans

    def create_checkout(self, *, interval: str, user_id: str, email: str, customer_id: str | None, success_url: str,
                        cancel_url: str) -> tuple[str, str]:
        params: dict = {
            "mode": "subscription",
            "line_items": [{"price": self._prices[interval], "quantity": 1}],
            "client_reference_id": user_id,
            "metadata": {"user_id": user_id},
            "subscription_data": {"metadata": {"user_id": user_id}},
            "locale": "fr",
            "billing_address_collection": "required",
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_id:
            params["customer"] = customer_id
            params["customer_update"] = {"address": "auto", "name": "auto"}
        else:
            params["customer_email"] = email
        session = self._call(self._client.v1.checkout.sessions.create, params=params)
        return session["id"], session["url"]

    def checkout_session(self, session_id: str) -> CheckoutInfo | None:
        try:
            s = self._client.v1.checkout.sessions.retrieve(session_id).to_dict()
        except stripe.InvalidRequestError:
            return None  # identifiant inconnu ou mal formé
        except stripe.StripeError as error:
            raise BillingUnavailable(str(error)) from error
        sub = s.get("subscription")
        return CheckoutInfo(session_id=s["id"], user_id=s.get("client_reference_id"), customer_id=s.get("customer"),
                            subscription_id=sub.get("id") if isinstance(sub, dict) else sub)

    def subscription(self, subscription_id: str) -> StripeSubscription:
        return subscription_from_dict(self._call(self._client.v1.subscriptions.retrieve, subscription_id))

    def portal(self, customer_id: str, return_url: str) -> str:
        return self._call(self._client.v1.billing_portal.sessions.create,
                          params={"customer": customer_id, "return_url": return_url})["url"]

    def cancel_now(self, subscription_id: str) -> None:
        try:
            self._client.v1.subscriptions.cancel(subscription_id)
        except stripe.InvalidRequestError as error:
            if getattr(error, "code", None) != "resource_missing" and "canceled" not in str(error):
                raise BillingUnavailable(str(error)) from error  # déjà résilié ou inconnu : rien à faire
        except stripe.StripeError as error:
            raise BillingUnavailable(str(error)) from error

    def update_customer_email(self, customer_id: str, email: str) -> None:
        self._call(self._client.v1.customers.update, customer_id, params={"email": email})

    def parse_event(self, payload: bytes, signature: str | None) -> StripeEventIn:
        if not signature:
            raise InvalidSignature("signature absente")
        try:
            stripe.WebhookSignature.verify_header(payload.decode("utf-8"), signature, self._webhook_secret,
                                                  tolerance=TOLERANCE_SECONDS)
        except stripe.SignatureVerificationError as error:
            raise InvalidSignature(str(error)) from error
        return event_from_dict(json.loads(payload))
```

Si `stripe.WebhookSignature.verify_header` n'existe pas sous ce nom dans la version installée, utiliser `stripe.Webhook.construct_event(payload, signature, secret, tolerance=...)` et ignorer l'objet renvoyé (on relit `json.loads(payload)`) : le test du Step 1 tranche.

Dans `backend/app/api/deps.py`, ajouter :

```python
def get_billing_gateway():
    """Stripe si les quatre variables sont renseignées, sinon None (spec 7) ; remplacé en test."""
    from app.services.billing.stripe_gateway import StripeGateway

    s = get_settings()
    if not s.stripe_configured:
        return None
    return StripeGateway(secret_key=s.stripe_secret_key, webhook_secret=s.stripe_webhook_secret,
                         price_monthly=s.stripe_price_monthly, price_yearly=s.stripe_price_yearly)
```

- [ ] **Step 5: Faux Stripe** — `backend/tests/fake_billing.py` :

```python
from dataclasses import replace
from datetime import UTC, datetime

from app.services.billing.gateway import (
    BillingUnavailable, CheckoutInfo, InvalidSignature, Plan, StripeEventIn, StripeSubscription,
)


class FakeBilling:
    """Remplace Stripe. `subs` = abonnements « chez Stripe » ; `down = True` simule une panne ; la signature valide est
    « bonne-signature », et le corps du webhook est un JSON {"id", "type", "subscription_id", "customer_id", "user_id"}."""

    mode = "test"

    def __init__(self) -> None:
        self.subs: dict[str, StripeSubscription] = {}
        self.sessions: dict[str, CheckoutInfo] = {}
        self.checkouts: list[dict] = []
        self.canceled: list[str] = []
        self.emails: dict[str, str] = {}
        self.portals: list[str] = []
        self.down = False
        self.prices = [Plan("month", 499, "eur"), Plan("year", 4900, "eur")]

    def _check(self) -> None:
        if self.down:
            raise BillingUnavailable("Stripe injoignable (faux)")

    def put(self, sub_id: str = "sub_1", *, customer_id: str = "cus_1", user_id: str | None = None, status: str = "active",
            interval: str = "month", period_end: datetime | None = None, cancel: bool = False,
            latest_invoice: str | None = "in_1") -> StripeSubscription:
        sub = StripeSubscription(id=sub_id, customer_id=customer_id, user_id=user_id, status=status, interval=interval,
                                 current_period_end=period_end or datetime(2026, 11, 1, tzinfo=UTC),
                                 cancel_at_period_end=cancel, ends_at=None, latest_invoice=latest_invoice,
                                 price_amount=499 if interval == "month" else 4900, currency="eur")
        self.subs[sub_id] = sub
        return sub

    def update(self, sub_id: str, **changes) -> StripeSubscription:
        self.subs[sub_id] = replace(self.subs[sub_id], **changes)
        return self.subs[sub_id]

    def plans(self) -> list[Plan]:
        self._check()
        return list(self.prices)

    def create_checkout(self, *, interval, user_id, email, customer_id, success_url, cancel_url):
        self._check()
        session_id = f"cs_{len(self.checkouts) + 1}"
        self.checkouts.append(dict(interval=interval, user_id=user_id, email=email, customer_id=customer_id,
                                   success_url=success_url, cancel_url=cancel_url, session_id=session_id))
        return session_id, f"https://checkout.stripe.test/{session_id}"

    def checkout_session(self, session_id):
        self._check()
        return self.sessions.get(session_id)

    def subscription(self, subscription_id):
        self._check()
        return self.subs[subscription_id]

    def portal(self, customer_id, return_url):
        self._check()
        self.portals.append(customer_id)
        return f"https://billing.stripe.test/{customer_id}"

    def cancel_now(self, subscription_id):
        self._check()
        self.canceled.append(subscription_id)
        if subscription_id in self.subs:
            self.update(subscription_id, status="canceled")

    def update_customer_email(self, customer_id, email):
        self._check()
        self.emails[customer_id] = email

    def parse_event(self, payload: bytes, signature):
        import json

        if signature != "bonne-signature":
            raise InvalidSignature("fausse signature")
        return StripeEventIn(**json.loads(payload))
```

Dans `backend/tests/conftest.py` : fixture

```python
@pytest.fixture
def fake_billing():
    from tests.fake_billing import FakeBilling

    return FakeBilling()
```

puis ajouter `fake_billing` aux paramètres de `_build_app`, `anon_client`, `client` et `admin_client`, et dans `_build_app` :

```python
    from app.api.deps import get_billing_gateway

    app.dependency_overrides[get_billing_gateway] = lambda: fake_billing
```

Une fixture `no_billing` (Stripe non configuré) sera ajoutée là où un test en a besoin : `app.dependency_overrides[get_billing_gateway] = lambda: None` sur `client.app`.

- [ ] **Step 6: Reconstruire l'image (nouvelle dépendance) et lancer**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml build api && docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_billing_gateway.py`
Expected: PASS (7 tests).

Puis toute la suite : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` → Expected: tout passe (les fixtures ont un paramètre de plus, rien d'autre ne change).

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app/services/billing backend/app/api/deps.py backend/tests/fake_billing.py backend/tests/conftest.py backend/tests/test_billing_gateway.py
git commit -m "feat(billing): Stripe gateway, event parsing and fake gateway for tests"
```

### Task 3: Appliquer un état Stripe, mails P1 à P5

**Files:**
- Create: `backend/app/services/billing/state.py`, 10 modèles de mail dans `backend/app/services/mail/templates/` (`premium_started`, `payment_failed`, `premium_cancel_scheduled`, `premium_ended`, `renewal_reminder`, chacun `.html` et `.txt`), `backend/tests/test_billing_state.py`
- Modify: `backend/app/services/mail/render.py` (`SUBJECTS`), `backend/app/services/security_log.py` (`EVENT_KINDS`)

**Interfaces:**
- Consumes: `Subscription`, `ACCESS_STATUSES`, `subscription_gives_access` (Task 1) ; `StripeSubscription` (Task 2) ; `enqueue()`, `log_event()`.
- Produces:
  - `state.apply_subscription(db, user: User, sub: StripeSubscription, *, now: datetime) -> Subscription` (pas de commit) ;
  - `state.mail_context(user: User, row: Subscription, amount: int | None = None, currency: str | None = None) -> dict` ;
  - types de mail `premium_started` (P1), `payment_failed` (P2), `premium_cancel_scheduled` (P3), `premium_ended` (P4), `renewal_reminder` (P5) ;
  - événements `subscription_started`, `subscription_ended`, `billing_consent` dans `EVENT_KINDS`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_billing_state.py` :

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import EmailLog, SecurityEvent, Subscription
from app.services.billing.state import apply_subscription, mail_context
from app.services.mail.render import render
from tests.factories import make_subscription, make_user
from tests.fake_billing import FakeBilling

NOW = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)


def _kinds(db):
    return [m.kind for m in db.scalars(select(EmailLog).order_by(EmailLog.id))]


@pytest.fixture
def stripe():
    return FakeBilling()


def test_first_activation_sends_p1_and_logs(db, user, stripe):
    row = apply_subscription(db, user, stripe.put(user_id=str(user.id)), now=NOW)
    assert (row.status, row.interval, row.stripe_customer_id) == ("active", "month", "cus_1")
    assert user.has_premium
    assert _kinds(db) == ["premium_started"]
    assert db.scalar(select(SecurityEvent.kind).where(SecurityEvent.user_id == user.id)) == "subscription_started"


def test_replayed_state_sends_nothing_more(db, user, stripe):
    sub = stripe.put()
    apply_subscription(db, user, sub, now=NOW)
    apply_subscription(db, user, sub, now=NOW)
    assert _kinds(db) == ["premium_started"]


def test_cancel_scheduled_sends_p3_once_and_undo_sends_nothing(db, user, stripe):
    apply_subscription(db, user, stripe.put(), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", cancel_at_period_end=True), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", cancel_at_period_end=True), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", cancel_at_period_end=False), now=NOW)
    assert _kinds(db) == ["premium_started", "premium_cancel_scheduled"]
    assert user.has_premium


def test_past_due_sends_p2_once_per_invoice_and_keeps_access(db, user, stripe):
    apply_subscription(db, user, stripe.put(), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="past_due", latest_invoice="in_2"), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="past_due", latest_invoice="in_2"), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="past_due", latest_invoice="in_3"), now=NOW)
    assert _kinds(db) == ["premium_started", "payment_failed", "payment_failed"]
    assert user.has_premium


def test_end_of_access_sends_p4_and_logs(db, user, stripe):
    apply_subscription(db, user, stripe.put(), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="canceled"), now=NOW)
    assert _kinds(db)[-1] == "premium_ended"
    assert not user.has_premium
    kinds = db.scalars(select(SecurityEvent.kind).where(SecurityEvent.user_id == user.id)).all()
    assert "subscription_ended" in kinds


def test_failed_new_attempt_does_not_override_an_active_subscription(db, user, stripe):
    apply_subscription(db, user, stripe.put("sub_1"), now=NOW)
    apply_subscription(db, user, stripe.put("sub_2", status="incomplete_expired"), now=NOW)  # Ruling 5
    assert db.get(Subscription, user.id).stripe_subscription_id == "sub_1"
    assert user.has_premium


def test_resubscribing_after_the_end_sends_p1_again(db, user, stripe):
    apply_subscription(db, user, stripe.put("sub_1"), now=NOW)
    apply_subscription(db, user, stripe.update("sub_1", status="canceled"), now=NOW)
    apply_subscription(db, user, stripe.put("sub_2"), now=NOW)
    assert _kinds(db) == ["premium_started", "premium_ended", "premium_started"]
    assert db.get(Subscription, user.id).stripe_subscription_id == "sub_2"


def test_offered_member_still_gets_subscription_mails(db, stripe):
    offered = make_user(db, "o@example.com", is_premium=True)
    apply_subscription(db, offered, stripe.put(), now=NOW)
    assert _kinds(db) == ["premium_started"]


@pytest.mark.parametrize("kind", ["premium_started", "payment_failed", "premium_cancel_scheduled", "premium_ended",
                                  "renewal_reminder"])
def test_premium_mails_render_as_account_mails(db, kind):
    user = make_user(db, "r@example.com", first_name="Rémi")
    row = make_subscription(db, user, interval="year", cancel=True)
    mail = render(kind, mail_context(user, row, amount=4900, currency="eur"), base_url=get_settings().public_base_url)
    assert "Rémi" in mail.text and "Ne plus recevoir" not in mail.text
    assert "/reglages#abonnement" in mail.text or "/premium" in mail.text
    assert "01/11/2026" in mail.text or kind == "premium_ended"
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_billing_state.py`
Expected: FAIL (`ModuleNotFoundError: app.services.billing.state`).

- [ ] **Step 3: Sujets et événements**

Dans `SUBJECTS` de `backend/app/services/mail/render.py`, ajouter à la fin :

```python
    "premium_started": "Bienvenue dans PEA Radar Premium",
    "payment_failed": "Le paiement de votre abonnement Premium a échoué",
    "premium_cancel_scheduled": "Votre abonnement Premium est résilié",
    "premium_ended": "Votre accès Premium est terminé",
    "renewal_reminder": "Votre abonnement Premium annuel sera renouvelé le {renews_on}",
```

Dans `EVENT_KINDS` de `backend/app/services/security_log.py`, ajouter `"subscription_started", "subscription_ended", "billing_consent",` après `"unsubscribed",`.

- [ ] **Step 4: Modèles de mail** (même gabarit `_layout.html` que les mails de compte : pas de `unsubscribe_url`, donc pas de lien de désinscription). Variables fournies par `mail_context` : `first_name`, `interval_label` (« mensuel » / « annuel »), `period_end` (date), `ends_on` (date), `renews_on` (texte jj/mm/aaaa), `amount` (texte « 49,00 € » ou `None`), `manage_url`, `premium_url`.

`premium_started.html` :

```html
{% extends "_layout.html" %}
{% block body %}
<p>Merci ! Votre abonnement Premium {{ interval_label }} est actif. Vous avez maintenant accès à :</p>
<ul>
  <li>l'assistant IA, pour poser vos questions sur vos titres et votre PEA ;</li>
  <li>la liste des prévisions court terme et le bloc prévision de chaque fiche.</li>
</ul>
{% if period_end %}<p>Prochaine échéance : {{ period_end | day }}.</p>{% endif %}
<p><a href="{{ manage_url }}" style="color:#4f46e5">Gérer mon abonnement</a> (carte, factures, résiliation).</p>
<p>PEA Radar reste un outil d'aide à la décision, pas un conseil en investissement.</p>
{% endblock %}
```

`premium_started.txt` :

```text
Bonjour {{ first_name }},

Merci ! Votre abonnement Premium {{ interval_label }} est actif. Vous avez maintenant accès à :
- l'assistant IA, pour poser vos questions sur vos titres et votre PEA ;
- la liste des prévisions court terme et le bloc prévision de chaque fiche.
{% if period_end %}
Prochaine échéance : {{ period_end | day }}.
{% endif %}

Gérer mon abonnement (carte, factures, résiliation) : {{ manage_url }}

PEA Radar reste un outil d'aide à la décision, pas un conseil en investissement.

{% include "_footer.txt" %}
```

`payment_failed.html` :

```html
{% extends "_layout.html" %}
{% block body %}
<p>Le dernier paiement de votre abonnement Premium n'est pas passé.</p>
<p>Votre accès continue pendant que notre prestataire de paiement réessaie. Pour le garder, mettez à jour votre carte :</p>
<p><a href="{{ manage_url }}" style="display:inline-block;background:#4f46e5;color:#ffffff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600">Mettre à jour ma carte</a></p>
{% if period_end %}<p>Période en cours jusqu'au {{ period_end | day }}.</p>{% endif %}
{% endblock %}
```

`payment_failed.txt` :

```text
Bonjour {{ first_name }},

Le dernier paiement de votre abonnement Premium n'est pas passé.

Votre accès continue pendant que notre prestataire de paiement réessaie. Pour le garder, mettez à jour votre carte : {{ manage_url }}
{% if period_end %}
Période en cours jusqu'au {{ period_end | day }}.
{% endif %}

{% include "_footer.txt" %}
```

`premium_cancel_scheduled.html` :

```html
{% extends "_layout.html" %}
{% block body %}
<p>Votre demande de résiliation est bien prise en compte. Vous gardez Premium jusqu'au {{ ends_on | day }} ; aucun autre prélèvement n'aura lieu.</p>
<p>Vous changez d'avis ? Vous pouvez annuler la résiliation avant cette date : <a href="{{ manage_url }}" style="color:#4f46e5">Gérer mon abonnement</a>.</p>
{% endblock %}
```

`premium_cancel_scheduled.txt` :

```text
Bonjour {{ first_name }},

Votre demande de résiliation est bien prise en compte. Vous gardez Premium jusqu'au {{ ends_on | day }} ; aucun autre prélèvement n'aura lieu.

Vous changez d'avis ? Vous pouvez annuler la résiliation avant cette date : {{ manage_url }}

{% include "_footer.txt" %}
```

`premium_ended.html` :

```html
{% extends "_layout.html" %}
{% block body %}
<p>Votre abonnement Premium est terminé : l'assistant IA et la liste des prévisions ne sont plus accessibles. Vos ordres, favoris et réglages sont conservés.</p>
<p><a href="{{ premium_url }}" style="color:#4f46e5">Me réabonner</a> · <a href="{{ manage_url }}" style="color:#4f46e5">Mes factures</a></p>
{% endblock %}
```

`premium_ended.txt` :

```text
Bonjour {{ first_name }},

Votre abonnement Premium est terminé : l'assistant IA et la liste des prévisions ne sont plus accessibles. Vos ordres, favoris et réglages sont conservés.

Me réabonner : {{ premium_url }}
Mes factures : {{ manage_url }}

{% include "_footer.txt" %}
```

`renewal_reminder.html` :

```html
{% extends "_layout.html" %}
{% block body %}
<p>Votre abonnement Premium annuel sera renouvelé automatiquement le {{ period_end | day }}{% if amount %}, pour {{ amount }}{% endif %}.</p>
<p>Vous n'avez rien à faire pour le garder. Pour l'arrêter, résiliez avant cette date : vous garderez Premium jusqu'au {{ period_end | day }}.</p>
<p><a href="{{ manage_url }}" style="color:#4f46e5">Gérer mon abonnement</a></p>
{% endblock %}
```

`renewal_reminder.txt` :

```text
Bonjour {{ first_name }},

Votre abonnement Premium annuel sera renouvelé automatiquement le {{ period_end | day }}{% if amount %}, pour {{ amount }}{% endif %}.

Vous n'avez rien à faire pour le garder. Pour l'arrêter, résiliez avant cette date : vous garderez Premium jusqu'au {{ period_end | day }}.

Gérer mon abonnement : {{ manage_url }}

{% include "_footer.txt" %}
```

- [ ] **Step 5: `state.py`** — `backend/app/services/billing/state.py` :

```python
"""Applique l'état d'un abonnement lu chez Stripe (spec 4.2) : une seule fonction pour le webhook, /sync et la nuit.

Les mails partent quand l'accès ou la résiliation change ; `dedupe_key` empêche un doublon si le même état revient.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Subscription, User
from app.services.billing.access import ACCESS_STATUSES, subscription_gives_access
from app.services.billing.gateway import StripeSubscription
from app.services.mail.outbox import enqueue
from app.services.security_log import log_event

PARIS = ZoneInfo("Europe/Paris")
INTERVAL_LABELS = {"month": "mensuel", "year": "annuel"}


def _day(value: datetime | None) -> date | None:
    return value.astimezone(PARIS).date() if value else None


def _amount(amount: int | None, currency: str | None) -> str | None:
    if amount is None:
        return None
    number = f"{amount / 100:,.2f}".replace(",", " ").replace(".", ",")
    return f"{number} €" if (currency or "eur").lower() == "eur" else f"{number} {currency.upper()}"


def mail_context(user: User, row: Subscription, amount: int | None = None, currency: str | None = None) -> dict:
    base = get_settings().public_base_url.rstrip("/")
    period_end = _day(row.current_period_end)
    return {
        "first_name": user.first_name, "interval_label": INTERVAL_LABELS.get(row.interval or "", ""),
        "period_end": period_end, "ends_on": period_end,
        "renews_on": period_end.strftime("%d/%m/%Y") if period_end else "",
        "amount": _amount(amount, currency),
        "manage_url": f"{base}/reglages#abonnement", "premium_url": f"{base}/premium",
    }


def apply_subscription(db: Session, user: User, sub: StripeSubscription, *, now: datetime) -> Subscription:
    row = db.get(Subscription, user.id)
    if (row is not None and row.stripe_subscription_id not in (None, sub.id) and sub.status not in ACCESS_STATUSES
            and subscription_gives_access(row)):
        return row  # Ruling 5 : un essai raté n'écrase pas l'abonnement en cours
    same = row is not None and row.stripe_subscription_id == sub.id
    had_access = subscription_gives_access(row)
    was_canceling = same and row.cancel_at_period_end
    if row is None:
        row = Subscription(user_id=user.id, stripe_customer_id=sub.customer_id, status=sub.status)
        db.add(row)
    row.stripe_customer_id, row.stripe_subscription_id, row.status = sub.customer_id, sub.id, sub.status
    row.interval, row.current_period_end = sub.interval, sub.current_period_end
    row.cancel_at_period_end, row.updated_at = sub.cancel_at_period_end, now
    db.flush()
    db.refresh(user, ["subscription"])
    has_access = sub.status in ACCESS_STATUSES
    context = mail_context(user, row, sub.price_amount, sub.currency)
    if sub.ends_at is not None:
        context["ends_on"] = _day(sub.ends_at)

    def send(kind: str, key: str) -> None:
        enqueue(db, kind, to=user.email, user_id=user.id, context=context, dedupe_key=key)

    if has_access and not had_access:
        send("premium_started", f"premium_started:{sub.id}")
        log_event(db, "subscription_started", now=now, user_id=user.id, details={"interval": sub.interval})
    if has_access and sub.cancel_at_period_end and not was_canceling:
        send("premium_cancel_scheduled", f"premium_cancel:{sub.id}:{context['ends_on']}")
    if sub.status == "past_due" and sub.latest_invoice:
        send("payment_failed", f"payment_failed:{sub.id}:{sub.latest_invoice}")
    if had_access and not has_access:
        send("premium_ended", f"premium_ended:{sub.id}")
        log_event(db, "subscription_ended", now=now, user_id=user.id, details={"status": sub.status})
    return row
```

Note : `test_replayed_state_sends_nothing_more` passe grâce à `had_access` ; `test_cancel_scheduled…` grâce à `was_canceling` et à `dedupe_key` ; P2 repose sur `dedupe_key` (une fois par facture).

- [ ] **Step 6: Lancer**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_billing_state.py tests/test_mail_render.py`
Expected: PASS. Si un test de `test_mail_render.py` vérifie la liste complète des types de mail ou la présence du pied « pas un conseil » selon le type, y ajouter les cinq nouveaux types comme mails de compte.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/billing/state.py backend/app/services/mail backend/app/services/security_log.py backend/tests/test_billing_state.py backend/tests/test_mail_render.py
git commit -m "feat(billing): apply Stripe subscription state with P1-P5 account mails"
```

### Task 4: Prévisions réservées à Premium

**Files:**
- Create: `backend/tests/test_api_premium_gates.py`
- Modify: `backend/app/api/routes/forecasts.py`, `backend/tests/test_api_forecasts.py`

**Interfaces:**
- Consumes: `require_premium()` (existant, s'appuie sur `User.has_premium` de la Task 1).
- Produces: `GET /api/forecasts` et `GET /api/securities/{id}/forecast` → 403 `premium_required` pour un membre gratuit.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_premium_gates.py` :

```python
from tests.factories import make_security, make_subscription


def test_free_member_gets_403_on_reserved_forecasts(client, db):
    security = make_security(db, "MC.PA")
    for path in ("/api/forecasts", f"/api/securities/{security.id}/forecast"):
        response = client.get(path)
        assert response.status_code == 403, path
        assert response.json()["detail"]["code"] == "premium_required"


def test_free_member_keeps_the_track_record(client):
    assert client.get("/api/forecasts/signals").status_code == 200
    assert client.get("/api/forecasts/track-record").status_code == 200


def test_subscriber_and_offered_member_see_forecasts(client, db, user):
    make_subscription(db, user)
    db.refresh(user)
    assert client.get("/api/forecasts").status_code == 200
    user.subscription.status = "canceled"
    user.is_premium = True
    db.flush()
    assert client.get("/api/forecasts").status_code == 200
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_premium_gates.py`
Expected: FAIL (`assert 200 == 403`).

- [ ] **Step 3: Protéger les deux routes** — dans `backend/app/api/routes/forecasts.py`, importer `require_premium` depuis `app.core.current_user` et remplacer, pour `list_forecasts` et `security_forecast` seulement, `_user: User = Depends(get_current_user)` par `_user: User = Depends(require_premium)`. `signal_statistics` et `track_record` gardent `get_current_user`.

- [ ] **Step 4: Adapter les anciens tests** — dans `backend/tests/test_api_forecasts.py`, ajouter après les imports une fixture automatique (ces tests décrivent le contenu, pas l'accès) :

```python
@pytest.fixture(autouse=True)
def premium_user(db, user):
    """Le contenu des prévisions est testé avec un compte Premium ; l'accès est testé dans test_api_premium_gates.py."""
    user.is_premium = True
    db.flush()
```

(`import pytest` s'il manque.) `tests/test_api_access.py` ne change pas : un visiteur reçoit toujours 401.

- [ ] **Step 5: Lancer**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: toute la suite passe.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/forecasts.py backend/tests/test_api_forecasts.py backend/tests/test_api_premium_gates.py
git commit -m "feat(billing): reserve forecast list and security forecast to Premium"
```

**Fin du Bloc 1 : s'arrêter ici** (l'utilisateur compacte la conversation avant le Bloc 2).

---

# Bloc 2 — API de paiement, webhook, worker, RGPD (Tasks 5 à 9)

### Task 5: Prix, résumé de l'abonnement et passage en caisse

**Files:**
- Create: `backend/app/schemas/billing.py`, `backend/app/api/routes/billing.py`, `backend/tests/test_api_billing_checkout.py`
- Modify: `backend/app/main.py` (routeur `billing`), `backend/app/api/deps.py` (`PLANS_CACHE`), `backend/app/services/ratelimit.py` (`checkout_user`), `backend/tests/conftest.py` (vider `PLANS_CACHE`), `backend/tests/test_api_access.py`

**Interfaces:**
- Consumes: `get_billing_gateway`, `BillingGateway`, `BillingUnavailable` (Task 2) ; `premium_source` (Task 1) ; `CGV_VERSION` (Task 1) ; `BillingConsent` (Task 1) ; `log_event(..., "billing_consent")` (Task 3).
- Produces:
  - `GET /api/billing/plans` → `PlansOut {configured: bool, plans: [PlanOut {interval, amount, currency}], yearly_saving_pct: int | None}` (public) ;
  - `GET /api/billing/subscription` → `SubscriptionOut {source, status, interval, current_period_end, cancel_at_period_end, has_customer}` (connecté) ;
  - `POST /api/billing/checkout` `CheckoutIn {interval: "month" | "year", accept_cgv: bool, waive_withdrawal: bool}` → `RedirectOut {url}` ;
  - codes d'erreur : 409 `already_premium`, 409 `premium_offered`, 422 `consent_required`, 429 `too_many_attempts`, 503 `billing_not_configured`, 503 `billing_unavailable` ;
  - dans `app.api.routes.billing` : `summary(user) -> SubscriptionOut`, `require_gateway(gateway)`, `unavailable() -> HTTPException` (réutilisés par la Task 6) ;
  - `app.api.deps.PLANS_CACHE = TTLCache(3600)`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_billing_checkout.py` :

```python
from sqlalchemy import select

from app.api.deps import get_billing_gateway
from app.models import BillingConsent, SecurityEvent
from tests.factories import make_subscription

BOTH = {"interval": "year", "accept_cgv": True, "waive_withdrawal": True}


def _no_stripe(test_client):
    test_client.app.dependency_overrides[get_billing_gateway] = lambda: None


def test_plans_are_public_with_the_yearly_saving(anon_client):
    body = anon_client.get("/api/billing/plans").json()
    assert body["configured"] is True
    assert [(p["interval"], p["amount"], p["currency"]) for p in body["plans"]] == [("month", 499, "eur"), ("year", 4900, "eur")]
    assert body["yearly_saving_pct"] == 18  # 49 € au lieu de 12 × 4,99 €


def test_plans_without_stripe_or_when_stripe_is_down(anon_client, fake_billing):
    fake_billing.down = True
    assert anon_client.get("/api/billing/plans").json() == {"configured": True, "plans": [], "yearly_saving_pct": None}
    _no_stripe(anon_client)
    assert anon_client.get("/api/billing/plans").json() == {"configured": False, "plans": [], "yearly_saving_pct": None}


def test_checkout_records_consent_and_returns_the_stripe_url(client, db, user, fake_billing):
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 200
    assert response.json() == {"url": "https://checkout.stripe.test/cs_1"}
    call = fake_billing.checkouts[0]
    assert (call["interval"], call["user_id"], call["email"], call["customer_id"]) == ("year", str(user.id), user.email, None)
    assert call["success_url"].endswith("/premium/merci?session_id={CHECKOUT_SESSION_ID}")
    assert call["cancel_url"].endswith("/premium")
    consent = db.scalar(select(BillingConsent).where(BillingConsent.user_id == user.id))
    assert (consent.withdrawal_waiver, consent.interval, consent.checkout_session_id) == (True, "year", "cs_1")
    assert db.scalar(select(SecurityEvent.kind).where(SecurityEvent.user_id == user.id)) == "billing_consent"


def test_checkout_reuses_the_stripe_customer(client, db, user, fake_billing):
    make_subscription(db, user, status="canceled", customer_id="cus_old")
    db.refresh(user)
    assert client.post("/api/billing/checkout", json=BOTH).status_code == 200
    assert fake_billing.checkouts[0]["customer_id"] == "cus_old"


def test_both_boxes_are_required(client, db, fake_billing):
    for payload in ({**BOTH, "accept_cgv": False}, {**BOTH, "waive_withdrawal": False}):
        response = client.post("/api/billing/checkout", json=payload)
        assert response.status_code == 422 and response.json()["detail"]["code"] == "consent_required"
    assert fake_billing.checkouts == [] and db.scalar(select(BillingConsent)) is None


def test_already_subscribed_or_offered_cannot_checkout(client, db, user):
    make_subscription(db, user)
    db.refresh(user)
    assert client.post("/api/billing/checkout", json=BOTH).json()["detail"]["code"] == "already_premium"
    user.subscription.status = "canceled"
    user.is_premium = True
    db.flush()
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "premium_offered"


def test_checkout_is_rate_limited(client):
    for _ in range(10):
        assert client.post("/api/billing/checkout", json=BOTH).status_code == 200
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 429 and response.json()["detail"]["code"] == "too_many_attempts"


def test_checkout_when_stripe_is_down_keeps_the_consent(client, db, fake_billing):
    fake_billing.down = True
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "billing_unavailable"
    assert db.scalar(select(BillingConsent)).checkout_session_id is None


def test_checkout_without_stripe(client):
    _no_stripe(client)
    response = client.post("/api/billing/checkout", json=BOTH)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "billing_not_configured"


def test_subscription_summary(client, db, user):
    assert client.get("/api/billing/subscription").json() == {
        "source": "none", "status": None, "interval": None, "current_period_end": None, "cancel_at_period_end": False,
        "has_customer": False}
    make_subscription(db, user, interval="year", cancel=True)
    db.refresh(user)
    body = client.get("/api/billing/subscription").json()
    assert (body["source"], body["status"], body["interval"], body["cancel_at_period_end"], body["has_customer"]) == (
        "subscription", "active", "year", True, True)
    assert body["current_period_end"].startswith("2026-11-01")
```

Dans `backend/tests/test_api_access.py`, ajouter à `PRIVATE` : `("GET", "/api/billing/subscription"), ("POST", "/api/billing/checkout"),` et à `PUBLIC` : `"/api/billing/plans"`.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_billing_checkout.py tests/test_api_access.py`
Expected: FAIL (404 sur `/api/billing/...`).

- [ ] **Step 3: Schémas** — `backend/app/schemas/billing.py` :

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PlanOut(BaseModel):
    interval: str
    amount: int  # centimes TTC
    currency: str


class PlansOut(BaseModel):
    configured: bool
    plans: list[PlanOut]
    yearly_saving_pct: int | None


class SubscriptionOut(BaseModel):
    source: str  # admin | offered | subscription | none
    status: str | None
    interval: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    has_customer: bool  # « Gérer mon abonnement » possible (factures d'un ancien abonnement comprises)


class CheckoutIn(BaseModel):
    interval: Literal["month", "year"]
    accept_cgv: bool
    waive_withdrawal: bool


class SyncIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=255)


class RedirectOut(BaseModel):
    url: str
```

- [ ] **Step 4: Limite, cache, routes**

`backend/app/services/ratelimit.py`, dans `LIMITS` : `"checkout_user": (10, ONE_HOUR),  # passages en caisse Stripe par compte`.

`backend/app/api/deps.py`, sous `NEWS_CACHE` : `PLANS_CACHE = TTLCache(3600)  # prix Stripe (spec 3.1)`.

`backend/tests/conftest.py`, dans `_build_app` : importer `PLANS_CACHE` avec `INTRADAY_CACHE, NEWS_CACHE` et ajouter `PLANS_CACHE.clear()`.

`backend/app/api/routes/billing.py` :

```python
"""Abonnement Premium (spec 3) : prix, résumé, passage en caisse. Le webhook et /sync, /portal suivent (Tasks 6 et 7)."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import PLANS_CACHE, get_billing_gateway
from app.api.routes.auth import client_ip, fail
from app.core.config import get_settings
from app.core.current_user import get_current_user, get_now
from app.core.db import get_db
from app.core.security import truncate_ip
from app.core.terms import CGV_VERSION
from app.models import BillingConsent, User
from app.schemas.billing import CheckoutIn, PlanOut, PlansOut, RedirectOut, SubscriptionOut
from app.services import ratelimit
from app.services.billing.access import premium_source
from app.services.billing.gateway import BillingGateway, BillingUnavailable
from app.services.security_log import log_event

router = APIRouter(prefix="/billing", tags=["billing"])
GatewayDep = Annotated[BillingGateway | None, Depends(get_billing_gateway)]


def unavailable() -> HTTPException:
    return fail(503, "billing_unavailable", "Paiement indisponible, réessayez dans quelques minutes.")


def require_gateway(gateway: BillingGateway | None) -> BillingGateway:
    if gateway is None:
        raise fail(503, "billing_not_configured", "L'abonnement n'est pas encore disponible.")
    return gateway


def summary(user: User) -> SubscriptionOut:
    row = user.subscription
    return SubscriptionOut(source=premium_source(user), status=row.status if row else None,
                           interval=row.interval if row else None,
                           current_period_end=row.current_period_end if row else None,
                           cancel_at_period_end=bool(row and row.cancel_at_period_end), has_customer=row is not None)


def _base_url() -> str:
    return get_settings().public_base_url.rstrip("/")


@router.get("/plans", response_model=PlansOut)
def billing_plans(gateway: GatewayDep) -> PlansOut:
    if gateway is None:
        return PlansOut(configured=False, plans=[], yearly_saving_pct=None)
    try:
        plans = PLANS_CACHE.get_or_set("plans", gateway.plans)
    except BillingUnavailable:
        return PlansOut(configured=True, plans=[], yearly_saving_pct=None)
    by_interval = {p.interval: p for p in plans}
    month, year = by_interval.get("month"), by_interval.get("year")
    saving = round((1 - year.amount / (12 * month.amount)) * 100) if month and year and month.amount else None
    return PlansOut(configured=True, plans=[PlanOut(interval=p.interval, amount=p.amount, currency=p.currency) for p in plans],
                    yearly_saving_pct=saving)


@router.get("/subscription", response_model=SubscriptionOut)
def billing_subscription(user: User = Depends(get_current_user)) -> SubscriptionOut:
    return summary(user)


@router.post("/checkout", response_model=RedirectOut)
def billing_checkout(payload: CheckoutIn, request: Request, gateway: GatewayDep, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user), now: datetime = Depends(get_now)) -> RedirectOut:
    gateway = require_gateway(gateway)
    source = premium_source(user)
    if source == "subscription":
        raise fail(409, "already_premium", "Vous êtes déjà abonné : gérez votre abonnement depuis les Réglages.")
    if source in ("offered", "admin"):
        raise fail(409, "premium_offered", "Premium vous est déjà offert : inutile de vous abonner.")
    if not (payload.accept_cgv and payload.waive_withdrawal):
        raise fail(422, "consent_required", "Cochez les deux cases pour continuer.")
    if ratelimit.over(db, "checkout_user", str(user.id), now):
        raise fail(429, "too_many_attempts", "Trop de tentatives de paiement : réessayez dans une heure.")
    ratelimit.record(db, "checkout_user", str(user.id), now)
    ip = client_ip(request)
    consent = BillingConsent(user_id=user.id, cgv_version=CGV_VERSION, withdrawal_waiver=True, interval=payload.interval,
                             ip=truncate_ip(ip), accepted_at=now)
    db.add(consent)
    log_event(db, "billing_consent", now=now, user_id=user.id, ip=ip,
              details={"cgv_version": CGV_VERSION, "interval": payload.interval})
    db.commit()  # la preuve de l'accord reste, même si Stripe ne répond pas (spec 3.2)
    customer_id = user.subscription.stripe_customer_id if user.subscription else None
    try:
        session_id, url = gateway.create_checkout(
            interval=payload.interval, user_id=str(user.id), email=user.email, customer_id=customer_id,
            success_url=f"{_base_url()}/premium/merci?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{_base_url()}/premium")
    except BillingUnavailable:
        raise unavailable()
    consent.checkout_session_id = session_id
    db.commit()
    return RedirectOut(url=url)
```

Vérifier que `truncate_ip` existe dans `app.core.security` (utilisé par `security_log.py`) ; `client_ip` et `fail` viennent de `app.api.routes.auth` comme dans `admin.py`.

`backend/app/main.py` : importer `billing` avec les autres routeurs et l'ajouter au tuple (après `notifications`).

- [ ] **Step 5: Lancer**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_billing_checkout.py tests/test_api_access.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/billing.py backend/app/api/routes/billing.py backend/app/main.py backend/app/api/deps.py backend/app/services/ratelimit.py backend/tests/conftest.py backend/tests/test_api_access.py backend/tests/test_api_billing_checkout.py
git commit -m "feat(billing): plans, subscription summary and Stripe checkout with consents"
```

### Task 6: Retour de paiement (`/sync`) et portail client

**Files:**
- Create: `backend/tests/test_api_billing_sync_portal.py`
- Modify: `backend/app/api/routes/billing.py`, `backend/tests/test_api_access.py`

**Interfaces:**
- Consumes: `summary`, `require_gateway`, `unavailable` (Task 5) ; `apply_subscription` (Task 3) ; `CheckoutInfo` (Task 2).
- Produces: `POST /api/billing/sync` `SyncIn {session_id}` → `SubscriptionOut` (404 `not_found` si la session est inconnue ou d'un autre compte) ; `POST /api/billing/portal` → `RedirectOut` (404 `no_customer`).

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_billing_sync_portal.py` :

```python
from sqlalchemy import select

from app.models import EmailLog, Subscription
from app.services.billing.gateway import CheckoutInfo
from tests.factories import make_subscription, make_user


def test_sync_applies_the_paid_subscription(client, db, user, fake_billing):
    fake_billing.sessions["cs_1"] = CheckoutInfo("cs_1", str(user.id), "cus_1", "sub_1")
    fake_billing.put("sub_1", user_id=str(user.id))
    response = client.post("/api/billing/sync", json={"session_id": "cs_1"})
    assert response.status_code == 200 and response.json()["source"] == "subscription"
    assert db.scalar(select(EmailLog.kind)) == "premium_started"
    assert client.get("/api/me").json()["has_premium"] is True


def test_sync_refuses_a_session_of_another_user(client, db, fake_billing):
    other = make_user(db, "autre@example.com")
    fake_billing.sessions["cs_1"] = CheckoutInfo("cs_1", str(other.id), "cus_1", "sub_1")
    fake_billing.put("sub_1", user_id=str(other.id))
    response = client.post("/api/billing/sync", json={"session_id": "cs_1"})
    assert response.status_code == 404 and response.json()["detail"]["code"] == "not_found"
    assert db.scalar(select(Subscription)) is None


def test_sync_unknown_session_or_not_yet_paid(client, user, fake_billing):
    assert client.post("/api/billing/sync", json={"session_id": "cs_inconnue"}).status_code == 404
    fake_billing.sessions["cs_2"] = CheckoutInfo("cs_2", str(user.id), None, None)
    assert client.post("/api/billing/sync", json={"session_id": "cs_2"}).json()["source"] == "none"


def test_sync_when_stripe_is_down(client, user, fake_billing):
    fake_billing.down = True
    response = client.post("/api/billing/sync", json={"session_id": "cs_1"})
    assert response.status_code == 503 and response.json()["detail"]["code"] == "billing_unavailable"


def test_portal_opens_for_a_customer(client, db, user, fake_billing):
    make_subscription(db, user, status="canceled", customer_id="cus_7")
    db.refresh(user)
    assert client.post("/api/billing/portal").json() == {"url": "https://billing.stripe.test/cus_7"}
    assert fake_billing.portals == ["cus_7"]


def test_portal_without_customer_or_when_stripe_is_down(client, db, user, fake_billing):
    response = client.post("/api/billing/portal")
    assert response.status_code == 404 and response.json()["detail"]["code"] == "no_customer"
    make_subscription(db, user)
    db.refresh(user)
    fake_billing.down = True
    assert client.post("/api/billing/portal").status_code == 503
```

Dans `tests/test_api_access.py`, ajouter à `PRIVATE` : `("POST", "/api/billing/sync"), ("POST", "/api/billing/portal"),`.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_billing_sync_portal.py`
Expected: FAIL (404/405 sur `/api/billing/sync`).

- [ ] **Step 3: Routes** — dans `backend/app/api/routes/billing.py`, compléter les imports (`SyncIn`, `apply_subscription` depuis `app.services.billing.state`) et ajouter :

```python
@router.post("/sync", response_model=SubscriptionOut)
def billing_sync(payload: SyncIn, gateway: GatewayDep, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user), now: datetime = Depends(get_now)) -> SubscriptionOut:
    """Retour de Stripe (/premium/merci) : applique l'abonnement sans attendre le webhook (spec 3.3)."""
    gateway = require_gateway(gateway)
    try:
        info = gateway.checkout_session(payload.session_id)
        if info is None or info.user_id != str(user.id):
            raise fail(404, "not_found", "Paiement introuvable.")
        if info.subscription_id:
            apply_subscription(db, user, gateway.subscription(info.subscription_id), now=now)
            db.commit()
    except BillingUnavailable:
        db.rollback()
        raise unavailable()
    return summary(user)


@router.post("/portal", response_model=RedirectOut)
def billing_portal(gateway: GatewayDep, user: User = Depends(get_current_user)) -> RedirectOut:
    gateway = require_gateway(gateway)
    if user.subscription is None:
        raise fail(404, "no_customer", "Aucun abonnement à gérer pour ce compte.")
    try:
        return RedirectOut(url=gateway.portal(user.subscription.stripe_customer_id, f"{_base_url()}/reglages#abonnement"))
    except BillingUnavailable:
        raise unavailable()
```

- [ ] **Step 4: Lancer**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_billing_sync_portal.py tests/test_api_access.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/billing.py backend/tests/test_api_billing_sync_portal.py backend/tests/test_api_access.py
git commit -m "feat(billing): checkout return sync and Stripe customer portal"
```

### Task 7: Webhook Stripe

**Files:**
- Create: `backend/app/services/billing/webhook.py`, `backend/tests/test_api_billing_webhook.py`
- Modify: `backend/app/api/routes/billing.py`

**Interfaces:**
- Consumes: `StripeEventIn`, `InvalidSignature`, `BillingUnavailable` (Task 2) ; `apply_subscription` (Task 3) ; `StripeEvent`, `Subscription` (Task 1).
- Produces: `webhook.HANDLED_TYPES: frozenset[str]` ; `webhook.handle_event(db, gateway, event: StripeEventIn, *, now) -> None` (pas de commit) ; `POST /api/billing/webhook` → 200 `{"received": true}` ; 400 `bad_signature` ; 500 `billing_unavailable` ; 503 `billing_not_configured`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_billing_webhook.py` :

```python
import json
import uuid

from sqlalchemy import select

from app.api.deps import get_billing_gateway
from app.models import EmailLog, StripeEvent, Subscription
from tests.factories import make_subscription


def _send(test_client, event_id="evt_1", type_="checkout.session.completed", subscription_id="sub_1",
          customer_id="cus_1", user_id=None, signature="bonne-signature"):
    body = json.dumps({"id": event_id, "type": type_, "subscription_id": subscription_id, "customer_id": customer_id,
                       "user_id": user_id})
    headers = {"Stripe-Signature": signature} if signature else {}
    return test_client.post("/api/billing/webhook", content=body, headers=headers)


def _mails(db):
    return db.scalars(select(EmailLog.kind)).all()


def test_bad_or_missing_signature_is_rejected(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id))
    for signature in ("fausse", None):
        response = _send(anon_client, user_id=str(user.id), signature=signature)
        assert response.status_code == 400 and response.json()["detail"]["code"] == "bad_signature"
    assert db.scalar(select(Subscription)) is None and db.scalar(select(StripeEvent)) is None


def test_checkout_completed_activates_premium(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id))
    assert _send(anon_client, user_id=str(user.id)).json() == {"received": True}
    db.refresh(user)
    assert user.has_premium and _mails(db) == ["premium_started"]


def test_same_event_twice_is_applied_once(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id))
    _send(anon_client, user_id=str(user.id))
    _send(anon_client, user_id=str(user.id))
    assert _mails(db) == ["premium_started"]
    assert len(db.scalars(select(StripeEvent)).all()) == 1


def test_state_is_read_back_from_stripe(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id), status="canceled")  # « créé » arrive après la suppression
    _send(anon_client, type_="customer.subscription.created", user_id=str(user.id))
    db.refresh(user)
    assert not user.has_premium and _mails(db) == []


def test_user_found_by_customer_id(anon_client, db, user, fake_billing):
    make_subscription(db, user, sub_id="sub_1", customer_id="cus_1")
    fake_billing.put("sub_1", customer_id="cus_1", status="past_due", latest_invoice="in_2")
    _send(anon_client, type_="invoice.payment_failed")
    assert _mails(db) == ["payment_failed"]


def test_unknown_user_gets_the_subscription_canceled(anon_client, db, fake_billing):
    fake_billing.put("sub_9", customer_id="cus_9")
    response = _send(anon_client, subscription_id="sub_9", customer_id="cus_9", user_id=str(uuid.uuid4()))
    assert response.status_code == 200 and fake_billing.canceled == ["sub_9"]


def test_other_event_types_are_acknowledged_only(anon_client, db, fake_billing):
    assert _send(anon_client, type_="customer.created", subscription_id=None).status_code == 200
    assert db.scalar(select(StripeEvent.type)) == "customer.created" and db.scalar(select(Subscription)) is None


def test_stripe_down_returns_500_and_event_is_not_marked(anon_client, db, user, fake_billing):
    fake_billing.put("sub_1", user_id=str(user.id))
    fake_billing.down = True
    response = _send(anon_client, user_id=str(user.id))
    assert response.status_code == 500 and db.scalar(select(StripeEvent)) is None


def test_webhook_without_stripe(anon_client):
    anon_client.app.dependency_overrides[get_billing_gateway] = lambda: None
    assert _send(anon_client).status_code == 503
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_billing_webhook.py`
Expected: FAIL (405 ou 404 sur `/api/billing/webhook`).

- [ ] **Step 3: Traitement** — `backend/app/services/billing/webhook.py` :

```python
"""Événements Stripe (spec 4.1) : l'état est toujours relu chez Stripe, l'ordre d'arrivée n'a donc pas d'importance."""
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StripeEvent, Subscription, User
from app.services.billing.access import ACCESS_STATUSES
from app.services.billing.gateway import BillingGateway, StripeEventIn, StripeSubscription
from app.services.billing.state import apply_subscription

logger = logging.getLogger(__name__)
HANDLED_TYPES = frozenset({
    "checkout.session.completed", "customer.subscription.created", "customer.subscription.updated",
    "customer.subscription.deleted", "invoice.paid", "invoice.payment_failed",
})


def _user(db: Session, event: StripeEventIn, sub: StripeSubscription) -> User | None:
    for raw in (event.user_id, sub.user_id):
        try:
            user = db.get(User, uuid.UUID(raw)) if raw else None
        except ValueError:
            user = None
        if user is not None:
            return user
    row = db.scalar(select(Subscription).where(Subscription.stripe_customer_id == (event.customer_id or sub.customer_id)))
    return db.get(User, row.user_id) if row else None


def handle_event(db: Session, gateway: BillingGateway, event: StripeEventIn, *, now: datetime) -> None:
    """Pas de commit ici. BillingUnavailable remonte : Stripe renverra l'événement plus tard."""
    if db.get(StripeEvent, event.id) is not None:
        return
    if event.type in HANDLED_TYPES and event.subscription_id:
        sub = gateway.subscription(event.subscription_id)
        user = _user(db, event, sub)
        if user is not None:
            apply_subscription(db, user, sub, now=now)
        elif sub.status in ACCESS_STATUSES:  # compte supprimé entre-temps : plus aucun prélèvement
            logger.warning("Abonnement Stripe %s sans compte : résiliation", sub.id)
            gateway.cancel_now(sub.id)
    db.add(StripeEvent(id=event.id, type=event.type, received_at=now))
```

- [ ] **Step 4: Route** — dans `backend/app/api/routes/billing.py`, ajouter les imports `from starlette.concurrency import run_in_threadpool`, `InvalidSignature` (gateway) et `handle_event` (webhook), puis :

```python
@router.post("/webhook")
async def billing_webhook(request: Request, gateway: GatewayDep, db: Session = Depends(get_db),
                          now: datetime = Depends(get_now)) -> dict:
    """Appelé par Stripe (pas de cookie, pas de CSRF) : seule la signature compte (spec 4.1)."""
    gateway = require_gateway(gateway)
    payload = await request.body()
    try:
        event = gateway.parse_event(payload, request.headers.get("Stripe-Signature"))
    except InvalidSignature:
        raise fail(400, "bad_signature", "Signature Stripe invalide.")

    def process() -> None:
        try:
            handle_event(db, gateway, event, now=now)
            db.commit()
        except BillingUnavailable:
            db.rollback()
            raise fail(500, "billing_unavailable", "Stripe injoignable : l'événement sera renvoyé.")

    await run_in_threadpool(process)
    return {"received": True}
```

- [ ] **Step 5: Lancer**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_billing_webhook.py`
Expected: PASS (9 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/billing/webhook.py backend/app/api/routes/billing.py backend/tests/test_api_billing_webhook.py
git commit -m "feat(billing): signed, idempotent Stripe webhook"
```

### Task 8: Tâches du worker : synchronisation de nuit, rappel P5, résiliations en attente

**Files:**
- Create: `backend/app/jobs/billing.py`, `backend/tests/test_billing_jobs.py`
- Modify: `backend/app/jobs/context.py` (`billing`), `backend/app/jobs/worker.py`, `backend/app/jobs/scheduler.py`, `backend/app/services/billing/stripe_gateway.py` (`gateway_from_settings`), `backend/app/api/deps.py` (s'en servir), `backend/tests/conftest.py` (`make_ctx(billing=...)`), `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `apply_subscription`, `mail_context` (Task 3) ; `StripeCancellation`, `Subscription` (Task 1) ; `BillingGateway` (Task 2).
- Produces:
  - `JobContext.billing: BillingGateway | None = None` ;
  - `stripe_gateway.gateway_from_settings(settings) -> StripeGateway | None` ;
  - `jobs.billing.sync_subscriptions(ctx) -> int`, `send_renewal_notices(ctx) -> int`, `process_cancellations(ctx) -> int` ;
  - tâches planifiées `billing_sync` (03:30), `renewal_notices` (09:00), `stripe_cancellations` (toutes les 60 s).

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_billing_jobs.py` :

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.jobs.billing import process_cancellations, send_renewal_notices, sync_subscriptions
from app.models import EmailLog, StripeCancellation, Subscription
from tests.factories import make_subscription, make_user
from tests.fake_billing import FakeBilling

NIGHT = datetime(2026, 10, 2, 1, 30, tzinfo=UTC)


def _mails(db, kind=None):
    query = select(EmailLog.kind)
    return db.scalars(query.where(EmailLog.kind == kind) if kind else query).all()


def test_nightly_sync_applies_stripe_state_and_pushes_the_email(db, make_ctx):
    stripe = FakeBilling()
    user = make_user(db, "a@example.com")
    make_subscription(db, user, sub_id="sub_1", customer_id="cus_1")
    stripe.put("sub_1", customer_id="cus_1", status="canceled")
    assert sync_subscriptions(make_ctx(now=NIGHT, billing=stripe)) == 1
    assert db.get(Subscription, user.id).status == "canceled"
    assert _mails(db) == ["premium_ended"]
    assert stripe.emails == {"cus_1": "a@example.com"}


def test_nightly_sync_skips_long_ended_subscriptions_and_survives_errors(db, make_ctx):
    stripe = FakeBilling()
    old = make_user(db, "old@example.com")
    row = make_subscription(db, old, status="canceled", sub_id="sub_old", customer_id="cus_old")
    row.updated_at = NIGHT - timedelta(days=30)
    broken = make_user(db, "b@example.com")
    make_subscription(db, broken, sub_id="sub_missing", customer_id="cus_b")  # inconnu du faux Stripe : KeyError
    ok = make_user(db, "ok@example.com")
    make_subscription(db, ok, sub_id="sub_ok", customer_id="cus_ok")
    stripe.put("sub_ok", customer_id="cus_ok")
    db.flush()
    assert sync_subscriptions(make_ctx(now=NIGHT, billing=stripe)) == 1
    assert set(stripe.emails) == {"cus_ok"}


def test_nightly_sync_without_stripe_does_nothing(db, make_ctx):
    make_subscription(db, make_user(db, "a@example.com"))
    assert sync_subscriptions(make_ctx(now=NIGHT)) == 0


def test_renewal_notice_once_per_period_and_yearly_only(db, make_ctx):
    soon = NIGHT + timedelta(days=20)
    yearly = make_user(db, "y@example.com")
    make_subscription(db, yearly, interval="year", period_end=soon, sub_id="sub_y", customer_id="cus_y")
    make_subscription(db, make_user(db, "m@example.com"), interval="month", period_end=soon, sub_id="sub_m", customer_id="cus_m")
    make_subscription(db, make_user(db, "c@example.com"), interval="year", period_end=soon, cancel=True, sub_id="sub_c",
                      customer_id="cus_c")
    make_subscription(db, make_user(db, "l@example.com"), interval="year", period_end=NIGHT + timedelta(days=60),
                      sub_id="sub_l", customer_id="cus_l")
    ctx = make_ctx(now=NIGHT, billing=FakeBilling())
    assert send_renewal_notices(ctx) == 1
    assert send_renewal_notices(ctx) == 0
    mail = db.scalar(select(EmailLog).where(EmailLog.kind == "renewal_reminder"))
    assert mail.recipient == "y@example.com" and "49,00 €" in mail.text
    assert db.get(Subscription, yearly.id).renewal_notice_sent_for == soon


def test_cancellations_are_retried_until_stripe_answers(db, make_ctx):
    stripe = FakeBilling()
    db.add(StripeCancellation(subscription_id="sub_gone"))
    db.flush()
    stripe.down = True
    assert process_cancellations(make_ctx(now=NIGHT, billing=stripe)) == 0
    row = db.get(StripeCancellation, "sub_gone")
    assert row.attempts == 1 and row.last_error
    stripe.down = False
    assert process_cancellations(make_ctx(now=NIGHT, billing=stripe)) == 1
    assert stripe.canceled == ["sub_gone"] and db.get(StripeCancellation, "sub_gone") is None
```

Dans `backend/tests/test_scheduler.py`, `test_build_scheduler_registers_jobs` : ajouter `"billing_sync", "renewal_notices", "stripe_cancellations"` à l'ensemble attendu.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_billing_jobs.py tests/test_scheduler.py`
Expected: FAIL (`ModuleNotFoundError: app.jobs.billing`).

- [ ] **Step 3: Contexte et fabrique**

`backend/app/jobs/context.py` : ajouter au dataclass `billing: "BillingGateway | None" = None` (import sous `TYPE_CHECKING` de `app.services.billing.gateway.BillingGateway`, avec `from typing import TYPE_CHECKING`).

`backend/app/services/billing/stripe_gateway.py`, à la fin :

```python
def gateway_from_settings(settings) -> "StripeGateway | None":
    """Stripe si les quatre variables sont renseignées, sinon None (spec 7)."""
    if not settings.stripe_configured:
        return None
    return StripeGateway(secret_key=settings.stripe_secret_key, webhook_secret=settings.stripe_webhook_secret,
                         price_monthly=settings.stripe_price_monthly, price_yearly=settings.stripe_price_yearly)
```

`backend/app/api/deps.py` : `get_billing_gateway()` devient `return gateway_from_settings(get_settings())` (import local).

`backend/app/jobs/worker.py` : `billing=gateway_from_settings(settings),` dans `JobContext(...)`.

`backend/tests/conftest.py`, fixture `make_ctx` : ajouter le paramètre `billing=None` à `_make` et `billing=billing` au `JobContext`.

- [ ] **Step 4: Tâches** — `backend/app/jobs/billing.py` :

```python
"""Abonnements côté worker (spec 4.3, 5 P5, Ruling 1). Chaque ligne a son point de sauvegarde : une erreur n'arrête pas
les autres."""
import logging
from datetime import timedelta

from sqlalchemy import or_, select

from app.jobs.context import JobContext
from app.models import StripeCancellation, Subscription, User
from app.services.billing.gateway import BillingUnavailable
from app.services.billing.state import apply_subscription, mail_context
from app.services.mail.outbox import enqueue

logger = logging.getLogger(__name__)
ENDED_RECENTLY = timedelta(days=7)
RENEWAL_NOTICE = timedelta(days=30)
FINISHED = ("canceled", "incomplete_expired")


def sync_subscriptions(ctx: JobContext) -> int:
    """Chaque nuit : relit chez Stripe les abonnements vivants (et ceux terminés depuis moins de 7 jours), et met à jour le
    mail des clients Stripe (Ruling 2)."""
    if ctx.billing is None:
        return 0
    now, done = ctx.now(), 0
    with ctx.session_factory() as db:
        rows = db.scalars(select(Subscription).where(
            Subscription.stripe_subscription_id.is_not(None),
            or_(Subscription.status.not_in(FINISHED), Subscription.updated_at > now - ENDED_RECENTLY))).all()
        for row in rows:
            try:
                with db.begin_nested():
                    user = db.get(User, row.user_id)
                    apply_subscription(db, user, ctx.billing.subscription(row.stripe_subscription_id), now=now)
                    ctx.billing.update_customer_email(row.stripe_customer_id, user.email)
            except Exception:
                logger.exception("Synchronisation Stripe impossible pour %s", row.stripe_subscription_id)
                continue
            done += 1
        db.commit()
    return done


def _yearly_amount(ctx: JobContext) -> tuple[int | None, str | None]:
    if ctx.billing is None:
        return None, None
    try:
        year = next((p for p in ctx.billing.plans() if p.interval == "year"), None)
    except BillingUnavailable:
        return None, None
    return (year.amount, year.currency) if year else (None, None)


def send_renewal_notices(ctx: JobContext) -> int:
    """Chaque matin : P5, 30 jours avant le renouvellement d'un abonnement annuel non résilié (article L215-1)."""
    now, sent = ctx.now(), 0
    with ctx.session_factory() as db:
        rows = db.scalars(select(Subscription).where(
            Subscription.interval == "year", Subscription.status == "active", Subscription.cancel_at_period_end.is_(False),
            Subscription.current_period_end > now, Subscription.current_period_end <= now + RENEWAL_NOTICE,
            or_(Subscription.renewal_notice_sent_for.is_(None),
                Subscription.renewal_notice_sent_for != Subscription.current_period_end))).all()
        amount, currency = _yearly_amount(ctx) if rows else (None, None)
        for row in rows:
            user = db.get(User, row.user_id)
            enqueue(db, "renewal_reminder", to=user.email, user_id=user.id, context=mail_context(user, row, amount, currency),
                    dedupe_key=f"renewal:{row.stripe_subscription_id}:{row.current_period_end.date().isoformat()}")
            row.renewal_notice_sent_for = row.current_period_end
            sent += 1
        db.commit()
    return sent


def process_cancellations(ctx: JobContext) -> int:
    """Toutes les minutes : résilie chez Stripe les abonnements des comptes supprimés, jusqu'à réussite (Ruling 1)."""
    if ctx.billing is None:
        return 0
    done = 0
    with ctx.session_factory() as db:
        for row in db.scalars(select(StripeCancellation).with_for_update(skip_locked=True)).all():
            try:
                ctx.billing.cancel_now(row.subscription_id)
            except BillingUnavailable as error:
                row.attempts += 1
                row.last_error = str(error)[:500]
                continue
            db.delete(row)
            done += 1
        db.commit()
    return done
```

Note : dans le test « survives errors », `FakeBilling.subscription` lève `KeyError` pour un abonnement inconnu ; le `except Exception` couvre ce cas comme une vraie erreur Stripe.

- [ ] **Step 5: Planification** — `backend/app/jobs/scheduler.py` : importer les trois fonctions, puis

```python
def billing_sync_job(ctx: JobContext) -> None:
    run_job(ctx, "billing_sync", sync_subscriptions)


def renewal_notices_job(ctx: JobContext) -> None:
    run_job(ctx, "renewal_notices", send_renewal_notices)


def cancellations_job(ctx: JobContext) -> None:
    # Toutes les minutes, comme la file des mails : pas de trace dans data_status.
    try:
        process_cancellations(ctx)
    except Exception:
        logging.getLogger(__name__).exception("Échec des résiliations Stripe en attente")
```

et dans `build_scheduler`, après `cleanup` :

```python
    scheduler.add_job(billing_sync_job, CronTrigger(hour=3, minute=30, timezone=tz), args=[ctx], id="billing_sync", **daily)
    scheduler.add_job(renewal_notices_job, CronTrigger(hour=9, minute=0, timezone=tz), args=[ctx], id="renewal_notices",
                      **daily)
    scheduler.add_job(cancellations_job, IntervalTrigger(seconds=60, timezone=tz), args=[ctx], id="stripe_cancellations",
                      **common)
```

Si une page de l'état des données (frontend ou API `/api/status`) liste les tâches connues de `data_status`, y ajouter `billing_sync` et `renewal_notices` avec un libellé (« Synchronisation des abonnements », « Rappels de renouvellement ») : `grep -rn "fundamentals" backend/app/api frontend/src --include=*.py --include=*.tsx` pour la trouver.

- [ ] **Step 6: Lancer**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_billing_jobs.py tests/test_scheduler.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/jobs backend/app/services/billing/stripe_gateway.py backend/app/api/deps.py backend/tests/conftest.py backend/tests/test_billing_jobs.py backend/tests/test_scheduler.py
git commit -m "feat(billing): nightly Stripe sync, yearly renewal reminder and queued cancellations"
```

### Task 9: Suppression de compte, export, conservation, Admin

**Files:**
- Create: `backend/tests/test_billing_privacy_admin.py`
- Modify: `backend/app/services/privacy/erasure.py`, `backend/app/services/privacy/export.py`, `backend/app/services/privacy/retention.py`, `backend/app/schemas/admin.py` (`AdminUserOut`, `ConfigStatusOut`), `backend/app/api/routes/admin.py`, `backend/app/services/admin/users.py` (`list_users` charge l'abonnement)

**Interfaces:**
- Consumes: `StripeCancellation`, `Subscription`, `BillingConsent`, `StripeEvent` (Task 1) ; `premium_source` (Task 1) ; `get_billing_gateway` (Task 2).
- Produces:
  - `erase_account()` met l'abonnement vivant dans `stripe_cancellations` ;
  - export : clés `abonnement` (`{formule, etat, fin_de_periode, resiliation_demandee}` ou `None`) et `accords_de_vente` (liste de `{version_cgv, renonciation_retractation, formule, accepte_le}`) ;
  - `retention.STRIPE_EVENTS_TTL = timedelta(days=30)`, compteur `stripe_events` ;
  - `AdminUserOut.premium_source: str`, `AdminUserOut.subscription_interval: str | None`, `AdminUserOut.subscription_status: str | None` ;
  - `ConfigStatusOut.stripe: bool`, `ConfigStatusOut.stripe_mode: str | None` (`test` | `live`), `ConfigStatusOut.stripe_last_webhook_at: datetime | None`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_billing_privacy_admin.py` :

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models import BillingConsent, StripeCancellation, StripeEvent, Subscription
from app.services.privacy.erasure import erase_account
from app.services.privacy.export import build_export
from app.services.privacy.retention import run_retention
from tests.factories import make_subscription, make_user

NOW = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)


def test_erasing_a_subscriber_queues_the_cancellation(db):
    user = make_user(db, "a@example.com")
    make_subscription(db, user, sub_id="sub_live")
    db.add(BillingConsent(user_id=user.id, cgv_version="2026-10-05", withdrawal_waiver=True, interval="month", accepted_at=NOW))
    db.flush()
    erase_account(db, user, now=NOW)
    assert db.get(StripeCancellation, "sub_live") is not None
    assert db.scalar(select(Subscription)) is None and db.scalar(select(BillingConsent)) is None


def test_erasing_an_ended_subscription_queues_nothing(db):
    user = make_user(db, "b@example.com")
    make_subscription(db, user, status="canceled", sub_id="sub_done")
    erase_account(db, user, now=NOW)
    assert db.scalar(select(StripeCancellation)) is None


def test_export_contains_the_subscription_without_stripe_ids(db):
    user = make_user(db, "c@example.com")
    make_subscription(db, user, interval="year", cancel=True, sub_id="sub_secret", customer_id="cus_secret")
    db.add(BillingConsent(user_id=user.id, cgv_version="2026-10-05", withdrawal_waiver=True, interval="year", accepted_at=NOW))
    db.flush()
    db.refresh(user)
    data = build_export(db, user, NOW)
    assert data["abonnement"] == {"formule": "year", "etat": "active", "fin_de_periode": "2026-11-01T00:00:00+00:00",
                                  "resiliation_demandee": True}
    assert data["accords_de_vente"][0]["version_cgv"] == "2026-10-05"
    assert "sub_secret" not in str(data) and "cus_secret" not in str(data)


def test_stripe_events_are_kept_30_days(db):
    db.add_all([StripeEvent(id="evt_old", type="x", received_at=NOW - timedelta(days=31)),
                StripeEvent(id="evt_new", type="x", received_at=NOW - timedelta(days=1))])
    db.flush()
    assert run_retention(db, NOW)["stripe_events"] == 1
    assert db.scalars(select(StripeEvent.id)).all() == ["evt_new"]


def test_admin_list_shows_the_premium_source(admin_client, db):
    subscriber = make_user(db, "s@example.com")
    make_subscription(db, subscriber, interval="year")
    make_user(db, "o@example.com", is_premium=True)
    items = {u["email"]: u for u in admin_client.get("/api/admin/users").json()["items"]}
    assert (items["s@example.com"]["premium_source"], items["s@example.com"]["subscription_interval"]) == ("subscription", "year")
    assert items["o@example.com"]["premium_source"] == "offered"
    assert items["admin@example.com"]["premium_source"] == "admin"


def test_config_status_shows_stripe_without_values(admin_client, db):
    db.add(StripeEvent(id="evt_1", type="invoice.paid", received_at=NOW))
    db.flush()
    body = admin_client.get("/api/admin/config-status").json()
    assert (body["stripe"], body["stripe_mode"]) == (True, "test")
    assert body["stripe_last_webhook_at"].startswith("2026-10-02")
    for secret in ("sk_", "whsec_", "price_"):
        assert secret not in str(body)
    assert get_settings().stripe_secret_key == "" or get_settings().stripe_secret_key not in str(body)
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_billing_privacy_admin.py`
Expected: FAIL (`KeyError: 'abonnement'`, pas de ligne `StripeCancellation`, etc.).

- [ ] **Step 3: Suppression** — dans `backend/app/services/privacy/erasure.py`, importer `StripeCancellation, Subscription` et, dans `erase_account` juste avant `db.delete(user)` :

```python
    sub = db.get(Subscription, user.id)
    if sub is not None and sub.stripe_subscription_id and sub.status not in ("canceled", "incomplete_expired"):
        # Résilié par le worker dès que Stripe répond (Ruling 1) : plus aucun prélèvement après la suppression.
        db.merge(StripeCancellation(subscription_id=sub.stripe_subscription_id))
```

Compléter la docstring : « l'abonnement Stripe vivant est mis en file de résiliation ; les lignes `subscriptions` et `billing_consents` partent avec le compte ».

- [ ] **Step 4: Export et conservation**

`backend/app/services/privacy/export.py` : importer `BillingConsent, Subscription`, puis dans `build_export`, avant le `return` :

```python
    sub = db.get(Subscription, user.id)
    consents = db.scalars(select(BillingConsent).where(BillingConsent.user_id == user.id).order_by(BillingConsent.accepted_at)).all()
```

et dans le dictionnaire renvoyé :

```python
        "abonnement": {"formule": sub.interval, "etat": sub.status, "resiliation_demandee": sub.cancel_at_period_end,
                       "fin_de_periode": _plain(sub.current_period_end)} if sub else None,
        "accords_de_vente": [{"version_cgv": c.cgv_version, "renonciation_retractation": c.withdrawal_waiver,
                              "formule": c.interval, "accepte_le": _plain(c.accepted_at)} for c in consents],
```

`_row(user)` exporte `is_premium` : le laisser (c'est « Premium offert »).

`backend/app/services/privacy/retention.py` : importer `StripeEvent`, ajouter `STRIPE_EVENTS_TTL = timedelta(days=30)` avec les autres durées, et dans `counts` :

```python
        "stripe_events": db.execute(delete(StripeEvent).where(StripeEvent.received_at < now - STRIPE_EVENTS_TTL)).rowcount,
```

- [ ] **Step 5: Admin**

`backend/app/schemas/admin.py` : dans `AdminUserOut`, après `is_premium` :

```python
    premium_source: str  # admin | offered | subscription | none
    subscription_interval: str | None = None
    subscription_status: str | None = None
```

dans `ConfigStatusOut` :

```python
    stripe: bool
    stripe_mode: str | None = None  # test | live, déduit du préfixe de la clé (jamais la clé)
    stripe_last_webhook_at: datetime | None = None
```

(`from datetime import datetime` s'il manque.) Ajouter aussi `"premium_source"` n'est pas une colonne triable : `SortKey` et `SORTS` ne changent pas.

`backend/app/api/routes/admin.py` :

```python
def _out(user: User) -> AdminUserOut:
    sub = user.subscription
    return AdminUserOut(**{k: getattr(user, k) for k in _USER_FIELDS}, verified=user.email_verified_at is not None,
                        premium_source=premium_source(user), subscription_interval=sub.interval if sub else None,
                        subscription_status=sub.status if sub else None)
```

et `admin_config_status` reçoit en plus `db: Session = Depends(get_db)` et `billing: BillingGateway | None = Depends(get_billing_gateway)` :

```python
    return ConfigStatusOut(..., stripe=billing is not None, stripe_mode=billing.mode if billing else None,
                           stripe_last_webhook_at=db.scalar(select(func.max(StripeEvent.received_at))))
```

(les champs existants inchangés ; imports `select`, `func`, `StripeEvent`, `premium_source`, `get_billing_gateway`, `BillingGateway`).

`backend/app/services/admin/users.py`, dans `list_users` : ajouter `.options(selectinload(User.subscription))` à la requête des éléments (import `from sqlalchemy.orm import selectinload`) pour éviter une requête par ligne.

- [ ] **Step 6: Lancer toute la suite**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tout passe. Si `test_api_admin_settings.py` compare le corps complet de `config-status`, y ajouter les trois nouveaux champs ; si `test_privacy_export.py` compare la liste des clés de l'export, y ajouter `abonnement` et `accords_de_vente` ; si `test_privacy_retention.py` compare le dictionnaire des compteurs, y ajouter `stripe_events`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/privacy backend/app/schemas/admin.py backend/app/api/routes/admin.py backend/app/services/admin/users.py backend/tests
git commit -m "feat(billing): cancel on erasure, export, retention and admin view of subscriptions"
```

**Fin du Bloc 2 : s'arrêter ici.**

---

# Bloc 3 — Site (Tasks 10 à 12)

Avant la Task 10 : `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --wait db api`, puis `cd frontend && npm run gen:api < /dev/null` pour régénérer `src/lib/api/schema.d.ts` avec les routes des Blocs 1 et 2 (ne jamais l'éditer à la main).

### Task 10: Carte « Réservé Premium » aux endroits réservés, lien et badge du menu

**Files:**
- Create: `frontend/src/features/premium/PremiumCard.tsx`, `frontend/src/features/premium/PremiumCard.test.tsx`
- Modify: `frontend/src/lib/api/schema.d.ts` (généré), `frontend/src/lib/api/client.ts` (types), `frontend/src/test/utils.tsx` (`ME`, `PREMIUM_ME`), `frontend/src/features/assistant/ChatView.tsx`, `frontend/src/features/assistant/ChatView.test.tsx`, `frontend/src/features/forecasts/shared.tsx`, `frontend/src/features/forecasts/ForecastsPage.tsx`, `frontend/src/features/forecasts/ForecastsPage.test.tsx`, `frontend/src/features/security/ForecastCard.tsx`, `frontend/src/features/security/SecurityPage.test.tsx`, `frontend/src/app/AccountMenu.tsx`, `frontend/src/app/AccountMenu.test.tsx`

**Interfaces:**
- Consumes: `MeOut.premium_source`, `has_premium` (Task 1) ; 403 des prévisions (Task 4).
- Produces:
  - `PremiumCard({ feature: string, compact?: boolean })` : `role="note"`, titre « Réservé aux membres Premium », lien « Découvrir Premium » vers `/premium` ;
  - `useForecasts(enabled = true)` ;
  - types `BillingPlans` (`PlansOut`), `BillingSubscription` (`SubscriptionOut`), `RedirectOut` dans `client.ts` ;
  - `test/utils.tsx` : `ME.premium_source = "none"`, `PREMIUM_ME = { ...ME, has_premium: true, premium_source: "subscription" }`.

- [ ] **Step 1: Types et données de test**

`frontend/src/lib/api/client.ts`, sous `PriceAlert` :

```ts
export type BillingPlans = components["schemas"]["PlansOut"];
export type BillingSubscription = components["schemas"]["SubscriptionOut"];
export type RedirectOut = components["schemas"]["RedirectOut"];
```

`frontend/src/test/utils.tsx` : ajouter `premium_source: "none"` à `ME`, puis

```ts
export const PREMIUM_ME = { ...ME, has_premium: true, premium_source: "subscription" };
```

- [ ] **Step 2: Tests qui échouent**

`frontend/src/features/premium/PremiumCard.test.tsx` :

```tsx
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { PremiumCard } from "./PremiumCard";

test("explique ce qui est réservé et mène à /premium", () => {
  renderWithProviders(<PremiumCard feature="La liste des prévisions" />);
  expect(screen.getByText("Réservé aux membres Premium")).toBeInTheDocument();
  expect(screen.getByText(/La liste des prévisions fait partie de l'offre Premium/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Découvrir Premium" })).toHaveAttribute("href", "/premium");
});
```

Dans `frontend/src/features/forecasts/ForecastsPage.test.tsx` : importer `ME, PREMIUM_ME`, donner à `renderPage` une option `me = PREMIUM_ME` et répondre à `/api/me` en premier :

```tsx
function renderPage(route = "/previsions", { empty = false, me = PREMIUM_ME as object } = {}) {
  const fetchMock = mockFetch((url) => {
    if (url === "/api/me") return { body: me };
    if (url.startsWith("/api/forecasts/signals")) return { body: empty ? { ...SIGNALS, as_of: null, signals: [] } : SIGNALS };
    if (url.startsWith("/api/forecasts/track-record")) return { body: TRACK };
    return { body: empty ? { as_of: null, round_trip_cost: null, rows: [] } : LIST };
  });
  renderWithProviders(<ForecastsPage />, { route });
  return fetchMock;
}
```

(adapter les appels existants qui utilisaient la valeur de retour de `renderPage`), puis ajouter :

```tsx
test("membre gratuit : la page s'ouvre sur le bulletin et les prédictions sont réservées", async () => {
  const fetchMock = renderPage("/previsions", { me: ME });
  expect(await screen.findByRole("button", { name: "Bulletin de notes", current: "page" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Prédictions" }));
  expect(await screen.findByText("Réservé aux membres Premium")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => String(url) === "/api/forecasts")).toBe(false);
});
```

Dans `frontend/src/features/security/SecurityPage.test.tsx` : les tests qui affichent la prévision passent `me: { body: PREMIUM_ME }` à `renderPage` ; ajouter :

```tsx
test("ForecastCard ne demande pas la prévision sans Premium", async () => {
  const fetchMock = renderPage(200, DETAIL, FORECAST, { body: ME });
  expect(await screen.findByText("Réservé aux membres Premium")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/forecast"))).toBe(false);
});
```

(si `renderPage` ne renvoie pas le mock, le faire renvoyer : `const fetchMock = mockFetch(...); ...; return fetchMock;`).

Dans `frontend/src/features/assistant/ChatView.test.tsx`, le test « non Premium » vérifie en plus le lien :

```tsx
  expect(screen.getByRole("link", { name: "Découvrir Premium" })).toHaveAttribute("href", "/premium");
```

Dans `frontend/src/app/AccountMenu.test.tsx` :

```tsx
test("membre gratuit : lien « Passer Premium » ; membre Premium : badge", async () => {
  mockFetch(() => ({ body: ME }));
  const { unmount } = renderWithProviders(<AccountMenu />);
  expect(await screen.findByRole("link", { name: "Passer Premium" })).toHaveAttribute("href", "/premium");
  unmount();
  vi.unstubAllGlobals();
  mockFetch(() => ({ body: PREMIUM_ME }));
  renderWithProviders(<AccountMenu />);
  expect(await screen.findByText("Premium")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Passer Premium" })).not.toBeInTheDocument();
});
```

(importer `PREMIUM_ME`.)

- [ ] **Step 3: Lancer, vérifier l'échec**

Run (dans `frontend`) : `npx vitest --run src/features/premium src/features/forecasts src/features/security/SecurityPage.test.tsx src/features/assistant/ChatView.test.tsx src/app/AccountMenu.test.tsx < /dev/null`
Expected: FAIL (module `./PremiumCard` introuvable, textes absents).

- [ ] **Step 4: Carte** — `frontend/src/features/premium/PremiumCard.tsx` :

```tsx
import { Sparkles } from "lucide-react";
import { Link } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** À la place d'une fonction réservée à Premium (spec 2) : le serveur refuse de toute façon ces données (403). */
export function PremiumCard({ feature, compact = false }: { feature: string; compact?: boolean }) {
  return (
    <div role="note" className={cn("rounded-xl border border-dashed border-primary/40 bg-primary/5 text-sm", compact ? "p-4" : "p-6")}>
      <p className="flex items-center gap-2 font-medium">
        <Sparkles className="size-4 text-primary" aria-hidden />
        Réservé aux membres Premium
      </p>
      <p className="mt-1 text-muted-foreground">{feature} fait partie de l'offre Premium, avec l'assistant IA et les prévisions court terme.</p>
      <Link to="/premium" className={cn(buttonVariants({ size: "sm" }), "mt-3")}>Découvrir Premium</Link>
    </div>
  );
}
```

- [ ] **Step 5: Endroits réservés**

`frontend/src/features/forecasts/shared.tsx` :

```tsx
export const useForecasts = (enabled = true) =>
  useQuery({ queryKey: ["forecasts"], queryFn: () => apiGet<ForecastList>("/api/forecasts"), staleTime: 300_000, enabled });
```

`frontend/src/features/forecasts/ForecastsPage.tsx` : importer `useMe` et `PremiumCard`, puis

```tsx
  const { me } = useMe();
  const premium = !!me?.has_premium;
  const fallback: View = premium ? "predictions" : "bulletin";  // un membre gratuit arrive sur le bilan (spec 2)
  const [params, setParams] = useSearchParams();
  const view: View = VIEWS.some((v) => v.key === params.get("vue")) ? (params.get("vue") as View) : fallback;
  const { data } = useForecasts(premium);
```

les boutons font `setParams(v.key === fallback ? {} : { vue: v.key }, { replace: true })`, et

```tsx
      {view === "predictions" && (premium ? <PredictionsView /> : <PremiumCard feature="La liste des prévisions" />)}
```

`frontend/src/features/security/ForecastCard.tsx` : importer `PremiumCard` ;

```tsx
  const premium = !!me?.has_premium;
  const { data, isPending } = useQuery({ ..., enabled: premium });
```

et dans le contenu, entre le cas visiteur (`me === null`) et `isPending` :

```tsx
        ) : me && !premium ? (
          <PremiumCard compact feature="La prévision de ce titre" />
```

`frontend/src/features/assistant/ChatView.tsx` : importer `PremiumCard` ; dans `Unavailable`, en tête :

```tsx
  if ((status.reason ?? "premium") === "premium") return <PremiumCard feature="L'assistant IA" />;
```

et supprimer l'entrée `premium` de `UNAVAILABLE` (l'indexation devient `UNAVAILABLE[status.reason as "not_configured" | "limit_reached"]`).

`frontend/src/app/AccountMenu.tsx` : importer `Sparkles` ; dans le bloc du nom, après l'adresse :

```tsx
        {me.has_premium ? (
          <span className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            <Sparkles className="size-3" aria-hidden />Premium
          </span>
        ) : (
          <Link to="/premium" className="text-xs font-medium text-primary hover:underline">Passer Premium</Link>
        )}
```

- [ ] **Step 6: Lancer**

Run (dans `frontend`) : `npx vitest --run < /dev/null && npx tsc -b < /dev/null && npm run lint < /dev/null`
Expected: tous les tests passent, `tsc` sans erreur, lint sans nouvel avertissement (32 lignes comme avant).

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(premium): premium card on reserved features, menu link and badge"
```

### Task 11: Pages `/premium` et `/premium/merci`

**Files:**
- Create: `frontend/src/features/premium/api.ts`, `frontend/src/features/premium/redirect.ts`, `frontend/src/features/premium/ManageSubscriptionButton.tsx`, `frontend/src/features/premium/PremiumPage.tsx`, `frontend/src/features/premium/PremiumPage.test.tsx`, `frontend/src/features/premium/PremiumThanksPage.tsx`, `frontend/src/features/premium/PremiumThanksPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`, `frontend/src/app/router.test.tsx` (si elle liste les routes)

**Interfaces:**
- Consumes: `GET /api/billing/plans`, `POST /api/billing/checkout`, `POST /api/billing/sync`, `POST /api/billing/portal` (Tasks 5 et 6) ; `PremiumCard` n'est pas utilisé ici.
- Produces:
  - `usePlans()`, `useSubscription(enabled = true)` (clé `["billing", "subscription"]`), `formatAmount(cents: number, currency: string): string` (« 4,99 € ») ;
  - `redirectTo(url: string): void` (seul appel à `window.location.assign`, remplacé dans les tests) ;
  - `ManageSubscriptionButton({ variant?: "default" | "outline" })` : POST `/api/billing/portal` puis `redirectTo(url)` ;
  - routes `/premium` (publique, indexable) et `/premium/merci` (privée, `noindex`).

- [ ] **Step 1: Tests qui échouent**

`frontend/src/features/premium/PremiumPage.test.tsx` :

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, PREMIUM_ME, mockFetch, renderWithProviders } from "@/test/utils";
import { PremiumPage } from "./PremiumPage";
import { redirectTo } from "./redirect";

vi.mock("./redirect", () => ({ redirectTo: vi.fn() }));
afterEach(() => { vi.unstubAllGlobals(); vi.mocked(redirectTo).mockReset(); });

const PLANS = { configured: true, yearly_saving_pct: 18,
                plans: [{ interval: "month", amount: 499, currency: "eur" }, { interval: "year", amount: 4900, currency: "eur" }] };

function renderPage(me: { status?: number; body: unknown }, plans: object = PLANS, checkout: { status?: number; body: unknown } = { body: { url: "https://checkout.stripe.test/cs_1" } }) {
  const fetchMock = mockFetch((url) => {
    if (url === "/api/me") return me;
    if (url === "/api/billing/plans") return { body: plans };
    if (url === "/api/billing/checkout") return checkout;
    return { body: { url: "https://billing.stripe.test/cus_1" } };
  });
  renderWithProviders(<PremiumPage />, { route: "/premium" });
  return fetchMock;
}

test("affiche les prix et l'économie de la formule annuelle", async () => {
  renderPage({ body: ME });
  expect(await screen.findByText("4,99 €")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Annuel/ }));
  expect(screen.getByText("49,00 €")).toBeInTheDocument();
  expect(screen.getByText(/18 %/)).toBeInTheDocument();
});

test("les deux cases sont obligatoires, puis Stripe s'ouvre", async () => {
  const fetchMock = renderPage({ body: ME });
  const subscribe = await screen.findByRole("button", { name: "S'abonner" });
  expect(subscribe).toBeDisabled();
  await userEvent.click(screen.getByRole("checkbox", { name: /CGV/ }));
  expect(subscribe).toBeDisabled();
  await userEvent.click(screen.getByRole("checkbox", { name: /droit de rétractation/ }));
  await userEvent.click(subscribe);
  await waitFor(() => expect(redirectTo).toHaveBeenCalledWith("https://checkout.stripe.test/cs_1"));
  const call = fetchMock.mock.calls.find(([url]) => url === "/api/billing/checkout");
  expect(JSON.parse(String(call![1]!.body))).toEqual({ interval: "month", accept_cgv: true, waive_withdrawal: true });
});

test("erreur de paiement affichée", async () => {
  renderPage({ body: ME }, PLANS, { status: 503, body: { detail: { code: "billing_unavailable", message: "Paiement indisponible, réessayez dans quelques minutes." } } });
  await userEvent.click(await screen.findByRole("checkbox", { name: /CGV/ }));
  await userEvent.click(screen.getByRole("checkbox", { name: /droit de rétractation/ }));
  await userEvent.click(screen.getByRole("button", { name: "S'abonner" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Paiement indisponible");
  expect(redirectTo).not.toHaveBeenCalled();
});

test("visiteur : créer un compte ou se connecter", async () => {
  renderPage({ status: 401, body: { detail: { code: "not_authenticated", message: "…" } } });
  expect(await screen.findByRole("link", { name: "Créer un compte" })).toHaveAttribute("href", "/inscription");
  expect(screen.getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", "/connexion?suite=%2Fpremium");
  expect(screen.queryByRole("button", { name: "S'abonner" })).not.toBeInTheDocument();
});

test("abonné : gérer son abonnement ; Premium offert : rien à acheter", async () => {
  renderPage({ body: PREMIUM_ME });
  expect(await screen.findByText("Vous êtes Premium.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Gérer mon abonnement" })).toBeInTheDocument();
});

test("Premium offert : pas de bouton d'achat", async () => {
  renderPage({ body: { ...ME, has_premium: true, premium_source: "offered" } });
  expect(await screen.findByText("Premium vous est offert.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "S'abonner" })).not.toBeInTheDocument();
});

test("Stripe pas configuré : l'abonnement arrive bientôt", async () => {
  renderPage({ body: ME }, { configured: false, plans: [], yearly_saving_pct: null });
  expect(await screen.findByText("L'abonnement arrive bientôt.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "S'abonner" })).not.toBeInTheDocument();
});
```

`frontend/src/features/premium/PremiumThanksPage.test.tsx` :

```tsx
import { screen, waitFor } from "@testing-library/react";
import { ME, PREMIUM_ME, mockFetch, renderWithProviders } from "@/test/utils";
import { PremiumThanksPage } from "./PremiumThanksPage";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

test("synchronise la session puis souhaite la bienvenue", async () => {
  let premium = false;
  const fetchMock = mockFetch((url) => {
    if (url === "/api/billing/sync") { premium = true; return { body: { source: "subscription" } }; }
    return { body: premium ? PREMIUM_ME : ME };
  });
  renderWithProviders(<PremiumThanksPage />, { route: "/premium/merci?session_id=cs_1" });
  expect(await screen.findByRole("heading", { name: "Bienvenue dans Premium" }, { timeout: 5000 })).toBeInTheDocument();
  const sync = fetchMock.mock.calls.find(([url]) => url === "/api/billing/sync");
  expect(JSON.parse(String(sync![1]!.body))).toEqual({ session_id: "cs_1" });
  expect(screen.getByRole("link", { name: "Ouvrir l'assistant IA" })).toHaveAttribute("href", "/assistant");
});

test("message rassurant si l'activation tarde", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockFetch(() => ({ body: ME }));
  renderWithProviders(<PremiumThanksPage />, { route: "/premium/merci" });
  expect(await screen.findByText("Paiement reçu, activation en cours…")).toBeInTheDocument();
  vi.advanceTimersByTime(31_000);
  await waitFor(() => expect(screen.getByText(/peut prendre quelques minutes/)).toBeInTheDocument());
});
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run (dans `frontend`) : `npx vitest --run src/features/premium < /dev/null`
Expected: FAIL (modules `./PremiumPage`, `./PremiumThanksPage`, `./redirect` introuvables).

- [ ] **Step 3: Petits modules**

`frontend/src/features/premium/redirect.ts` :

```ts
/** Ouvre une page Stripe (paiement ou portail) : navigation complète hors de l'application. Remplacé dans les tests. */
export function redirectTo(url: string): void {
  window.location.assign(url);
}
```

`frontend/src/features/premium/api.ts` :

```ts
import { useQuery } from "@tanstack/react-query";
import { apiGet, type BillingPlans, type BillingSubscription } from "@/lib/api/client";

export const usePlans = () =>
  useQuery({ queryKey: ["billing", "plans"], queryFn: () => apiGet<BillingPlans>("/api/billing/plans"), staleTime: 3_600_000 });

export const useSubscription = (enabled = true) =>
  useQuery({ queryKey: ["billing", "subscription"], queryFn: () => apiGet<BillingSubscription>("/api/billing/subscription"), enabled });

/** Centimes → « 4,99 € ». */
export function formatAmount(cents: number, currency: string): string {
  return (cents / 100).toLocaleString("fr-FR", { style: "currency", currency: currency.toUpperCase() }).replace(/ | /g, " ");
}
```

`frontend/src/features/premium/ManageSubscriptionButton.tsx` :

```tsx
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ApiError, apiSend, type RedirectOut } from "@/lib/api/client";
import { redirectTo } from "./redirect";

/** Ouvre le portail client Stripe : carte, factures, changement de formule, résiliation (spec 3.4). */
export function ManageSubscriptionButton({ variant = "outline" }: { variant?: "default" | "outline" }) {
  const portal = useMutation({
    mutationFn: () => apiSend("POST", "/api/billing/portal") as Promise<RedirectOut>,
    onSuccess: (data) => redirectTo(data.url),
  });
  return (
    <div className="space-y-1">
      <Button variant={variant} disabled={portal.isPending} onClick={() => portal.mutate()}>Gérer mon abonnement</Button>
      {portal.error && <p role="alert" className="text-sm text-destructive">{(portal.error as ApiError).message}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Page `/premium`** — `frontend/src/features/premium/PremiumPage.tsx` :

```tsx
import { useMutation } from "@tanstack/react-query";
import { Check, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { loginPath } from "@/features/auth/redirect";
import { useMe } from "@/features/auth/useMe";
import { ApiError, apiSend, type RedirectOut } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { usePageMeta } from "@/seo/usePageMeta";
import { formatAmount, usePlans } from "./api";
import { ManageSubscriptionButton } from "./ManageSubscriptionButton";
import { redirectTo } from "./redirect";

type Interval = "month" | "year";

const FEATURES = [
  "L'assistant IA : posez vos questions sur une action, un ETF ou votre portefeuille, en français.",
  "La liste des prévisions court terme (1 jour, 1 semaine, 1 mois) et le bloc prévision de chaque fiche.",
  "Tout le reste de PEA Radar, qui reste gratuit : classement, fiches, portefeuille, notifications.",
];

export function PremiumPage() {
  usePageMeta({ title: "Premium", description: "L'assistant IA et les prévisions court terme de PEA Radar, en abonnement mensuel ou annuel, résiliable à tout moment." });
  const { me } = useMe();
  const plans = usePlans();
  const [interval, setInterval] = useState<Interval>("month");
  const plan = plans.data?.plans.find((p) => p.interval === interval);
  const monthly = plans.data?.plans.find((p) => p.interval === "month");

  return (
    <section className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-2">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Sparkles className="size-6 text-primary" aria-hidden />PEA Radar Premium</h1>
        <p className="text-sm text-muted-foreground">Pour aller plus loin : l'assistant IA et les prévisions court terme.</p>
      </header>
      <ul className="space-y-2 text-sm">
        {FEATURES.map((f) => <li key={f} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />{f}</li>)}
      </ul>
      <p className="text-sm">
        Avant de vous abonner, regardez ce que valent les prévisions :{" "}
        <Link to="/previsions?vue=bulletin" className="font-medium text-primary">le bilan des prévisions passées</Link> est ouvert à tous les membres.
      </p>
      <Card>
        <CardContent className="space-y-4 pt-6">
          {plans.isPending ? <Skeleton className="h-24 w-full" /> : !plans.data?.configured ? (
            <p className="text-sm">L'abonnement arrive bientôt.</p>
          ) : !plan ? (
            <p className="text-sm text-muted-foreground">Prix indisponibles pour le moment : réessayez dans quelques minutes.</p>
          ) : (
            <>
              <div role="group" aria-label="Formule" className="flex gap-2">
                {(["month", "year"] as const).map((key) => (
                  <Button key={key} size="sm" variant={interval === key ? "default" : "outline"} aria-pressed={interval === key} onClick={() => setInterval(key)}>
                    {key === "month" ? "Mensuel" : `Annuel${plans.data?.yearly_saving_pct ? ` (−${plans.data.yearly_saving_pct} %)` : ""}`}
                  </Button>
                ))}
              </div>
              <p>
                <span className="text-3xl font-semibold tabular-nums">{formatAmount(plan.amount, plan.currency)}</span>
                <span className="text-muted-foreground"> {interval === "month" ? "par mois" : "par an"}, TTC</span>
              </p>
              {interval === "year" && monthly && (
                <p className="text-sm text-muted-foreground">
                  Soit {formatAmount(Math.round(plan.amount / 12), plan.currency)} par mois au lieu de {formatAmount(monthly.amount, monthly.currency)}.
                </p>
              )}
              <Action me={me} interval={interval} />
            </>
          )}
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">
        Paiement sécurisé par Stripe : PEA Radar ne voit jamais votre carte. Résiliable à tout moment depuis les Réglages, effet à la fin
        de la période payée. Voir les <Link to="/cgv" className="underline">conditions générales de vente</Link>. PEA Radar est un outil
        d'aide à la décision, pas un conseil en investissement.
      </p>
    </section>
  );
}

function Action({ me, interval }: { me: ReturnType<typeof useMe>["me"]; interval: Interval }) {
  const [cgv, setCgv] = useState(false);
  const [waiver, setWaiver] = useState(false);
  const checkout = useMutation({
    mutationFn: () => apiSend("POST", "/api/billing/checkout", { interval, accept_cgv: cgv, waive_withdrawal: waiver }) as Promise<RedirectOut>,
    onSuccess: (data) => redirectTo(data.url),
  });
  if (me === undefined) return null;
  if (me === null) {
    return (
      <div className="flex flex-wrap gap-2">
        <Link to="/inscription" className={buttonVariants()}>Créer un compte</Link>
        <Link to={loginPath({ pathname: "/premium", search: "" })} className={buttonVariants({ variant: "outline" })}>Se connecter</Link>
      </div>
    );
  }
  if (me.premium_source === "subscription") {
    return <div className="space-y-2"><p className="font-medium">Vous êtes Premium.</p><ManageSubscriptionButton /></div>;
  }
  if (me.premium_source === "offered" || me.premium_source === "admin") return <p className="font-medium">Premium vous est offert.</p>;
  return (
    <div className="space-y-3 text-sm">
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-0.5 size-4 accent-primary" checked={cgv} onChange={(e) => setCgv(e.target.checked)} />
        <span>J'ai lu et j'accepte les <Link to="/cgv" className="underline">CGV</Link>.</span>
      </label>
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-0.5 size-4 accent-primary" checked={waiver} onChange={(e) => setWaiver(e.target.checked)} />
        <span>Je demande l'accès immédiat à Premium et je renonce à mon droit de rétractation de 14 jours.</span>
      </label>
      <Button disabled={!cgv || !waiver || checkout.isPending} onClick={() => checkout.mutate()} className={cn("w-full sm:w-auto")}>S'abonner</Button>
      {checkout.error && <p role="alert" className="text-destructive">{(checkout.error as ApiError).message}</p>}
    </div>
  );
}
```

Si `@/components/ui/skeleton` n'existe pas, utiliser le squelette déjà employé ailleurs (`grep -rn "Skeleton" frontend/src/components/ui`). Le paramètre `vue=bulletin` doit correspondre à la clé du bulletin dans `ForecastsPage` (`bulletin`).

- [ ] **Step 5: Page `/premium/merci`** — `frontend/src/features/premium/PremiumThanksPage.tsx` :

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { apiGet, apiSend, type Me } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";

const SLOW_AFTER_MS = 30_000;

/** Retour de Stripe (spec 3.3) : applique le paiement sans attendre le webhook, puis attend que Premium soit actif. */
export function PremiumThanksPage() {
  usePageMeta({ title: "Merci", description: "Activation de votre abonnement Premium.", noindex: true });
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const sync = useMutation({ mutationFn: (id: string) => apiSend("POST", "/api/billing/sync", { session_id: id }) });
  const started = useRef(false);
  const [slow, setSlow] = useState(false);
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiGet<Me>("/api/me"),
    refetchInterval: (query) => (query.state.data?.has_premium ? false : 2000),
  });

  useEffect(() => {
    if (sessionId && !started.current) {
      started.current = true;
      sync.mutate(sessionId, { onSettled: () => me.refetch() });
    }
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (me.data?.has_premium) {
    return (
      <section className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">Bienvenue dans Premium</h1>
        <p className="text-sm text-muted-foreground">Votre abonnement est actif. Un mail de confirmation vous a été envoyé.</p>
        <div className="flex flex-wrap gap-2">
          <Link to="/assistant" className={buttonVariants()}>Ouvrir l'assistant IA</Link>
          <Link to="/previsions" className={buttonVariants({ variant: "outline" })}>Voir les prévisions</Link>
        </div>
      </section>
    );
  }
  return (
    <section className="mx-auto max-w-2xl space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight">Merci !</h1>
      <p role="status" className="text-sm">Paiement reçu, activation en cours…</p>
      {slow && (
        <p className="text-sm text-muted-foreground">
          L'activation peut prendre quelques minutes ; vous recevrez un mail de confirmation. Vous pouvez quitter cette page.
        </p>
      )}
    </section>
  );
}
```

- [ ] **Step 6: Routes** — `frontend/src/app/router.tsx` : dans les pages publiques, après `mentions-legales` :

```tsx
      { path: "premium", lazy: async () => ({ Component: (await import("@/features/premium/PremiumPage")).PremiumPage }) },
```

et dans les enfants de `RequireAuth`, après `reglages` :

```tsx
          { path: "premium/merci", lazy: async () => ({ Component: (await import("@/features/premium/PremiumThanksPage")).PremiumThanksPage }) },
```

Si `router.test.tsx` vérifie la liste des routes publiques ou privées, y ajouter `/premium` (publique) et `/premium/merci` (privée).

- [ ] **Step 7: Lancer**

Run (dans `frontend`) : `npx vitest --run < /dev/null && npx tsc -b < /dev/null && npm run lint < /dev/null`
Expected: tout passe, lint sans nouvel avertissement.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat(premium): pricing page with consents, Stripe checkout and thank-you page"
```

### Task 12: Carte « Abonnement » des Réglages et vue Admin

**Files:**
- Create: `frontend/src/features/settings/SubscriptionCard.tsx`, `frontend/src/features/settings/SubscriptionCard.test.tsx`
- Modify: `frontend/src/features/settings/SettingsPage.tsx`, `frontend/src/features/settings/SettingsPage.test.tsx` (faux serveur : `/api/billing/subscription`), `frontend/src/features/admin/UsersCard.tsx`, `frontend/src/features/admin/EditUserDialog.tsx`, `frontend/src/features/admin/ConfigStatusCard.tsx`, `frontend/src/features/admin/AdminPage.test.tsx`

**Interfaces:**
- Consumes: `useSubscription`, `ManageSubscriptionButton` (Task 11) ; `AdminUserOut.premium_source`, `subscription_interval`, `subscription_status`, `ConfigStatusOut.stripe*` (Task 9).
- Produces: `SubscriptionCard` (`id="abonnement"`) ; libellés Admin « Abonné (mensuel) », « Abonné (annuel) », « Offert », « Admin » ; interrupteur « Premium offert pour {nom} ».

- [ ] **Step 1: Tests qui échouent**

`frontend/src/features/settings/SubscriptionCard.test.tsx` :

```tsx
import { screen } from "@testing-library/react";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { SubscriptionCard } from "./SubscriptionCard";

afterEach(() => vi.unstubAllGlobals());

const base = { source: "subscription", status: "active", interval: "year", current_period_end: "2026-11-01T00:00:00Z",
               cancel_at_period_end: false, has_customer: true };

function show(body: object) {
  mockFetch(() => ({ body }));
  renderWithProviders(<SubscriptionCard />);
}

test("abonné : formule, renouvellement et gestion", async () => {
  show(base);
  expect(await screen.findByText(/Premium annuel/)).toBeInTheDocument();
  expect(screen.getByText(/Renouvellement le 01\/11\/2026/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Gérer mon abonnement" })).toBeInTheDocument();
});

test("résilié : date de fin", async () => {
  show({ ...base, cancel_at_period_end: true });
  expect(await screen.findByText(/Premium s'arrête le 01\/11\/2026/)).toBeInTheDocument();
});

test("paiement échoué : alerte carte", async () => {
  show({ ...base, status: "past_due" });
  expect(await screen.findByRole("alert")).toHaveTextContent("Mettez à jour votre carte");
});

test("Premium offert", async () => {
  show({ ...base, source: "offered", status: null, interval: null, current_period_end: null, has_customer: false });
  expect(await screen.findByText("Premium vous est offert.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Gérer mon abonnement" })).not.toBeInTheDocument();
});

test("gratuit, avec un ancien abonnement : lien Premium et factures", async () => {
  show({ ...base, source: "none", status: "canceled" });
  expect(await screen.findByText("Vous n'êtes pas abonné.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Découvrir Premium" })).toHaveAttribute("href", "/premium");
  expect(screen.getByRole("button", { name: "Gérer mon abonnement" })).toBeInTheDocument();
});
```

Dans `frontend/src/features/admin/AdminPage.test.tsx` : ajouter `premium_source: "none", subscription_interval: null, subscription_status: null` aux utilisateurs de test, remplacer le nom de l'interrupteur par `"Premium offert pour Paul Martin"`, et ajouter :

```tsx
test("colonne Premium : abonné, offert, admin", async () => {
  api({ "/api/admin/users": { items: [
    { ...PAUL, premium_source: "subscription", subscription_interval: "year", subscription_status: "active" },
    { ...PAUL, id: "u3", first_name: "Léa", premium_source: "offered", is_premium: true },
  ], total: 2, page: 1, page_size: 50 } });
  expect(await screen.findByText("Abonné (annuel)")).toBeInTheDocument();
  expect(screen.getByText("Offert")).toBeInTheDocument();
});
```

(adapter à la forme exacte de l'aide `api(...)` du fichier.) Et pour la configuration : le faux `config-status` renvoie `stripe: true, stripe_mode: "test", stripe_last_webhook_at: "2026-10-02T08:00:00Z"` ; vérifier `screen.getByText("Paiement (Stripe)")` et `screen.getByText(/mode test/)`.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run (dans `frontend`) : `npx vitest --run src/features/settings src/features/admin < /dev/null`
Expected: FAIL.

- [ ] **Step 3: Carte** — `frontend/src/features/settings/SubscriptionCard.tsx` :

```tsx
import { Link } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ManageSubscriptionButton } from "@/features/premium/ManageSubscriptionButton";
import { useSubscription } from "@/features/premium/api";

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR", { timeZone: "Europe/Paris" }) : "");

/** État de l'abonnement Premium (spec 3.4) ; tout se gère dans le portail Stripe. */
export function SubscriptionCard() {
  const { data } = useSubscription();
  return (
    <Card id="abonnement">
      <CardHeader>
        <CardTitle className="text-base">Abonnement</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {!data ? null : data.source === "offered" || data.source === "admin" ? (
          <p>Premium vous est offert.</p>
        ) : data.source === "subscription" ? (
          <>
            <p className="font-medium">Premium {data.interval === "year" ? "annuel" : "mensuel"}</p>
            <p className="text-muted-foreground">
              {data.cancel_at_period_end ? `Premium s'arrête le ${day(data.current_period_end)}.` : `Renouvellement le ${day(data.current_period_end)}.`}
            </p>
            {data.status === "past_due" && (
              <p role="alert" className="rounded-md border border-amber-300 bg-amber-50 p-2 text-amber-900">
                Le dernier paiement a échoué. Mettez à jour votre carte pour garder Premium.
              </p>
            )}
            <ManageSubscriptionButton />
          </>
        ) : (
          <>
            <p>Vous n'êtes pas abonné.</p>
            <div className="flex flex-wrap items-start gap-2">
              <Link to="/premium" className={buttonVariants({ size: "sm" })}>Découvrir Premium</Link>
              {data.has_customer && <ManageSubscriptionButton />}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/settings/SettingsPage.tsx` : importer `SubscriptionCard` et l'afficher juste après `<ProfileCard />` ; description et sous-titre : « Votre profil, votre abonnement, vos appareils, vos notifications et les frais de votre caisse régionale. » Dans `SettingsPage.test.tsx`, le faux serveur répond à `/api/billing/subscription` avec `{ source: "none", status: null, interval: null, current_period_end: null, cancel_at_period_end: false, has_customer: false }`.

- [ ] **Step 4: Admin**

`frontend/src/features/admin/UsersCard.tsx` : ajouter en haut

```tsx
const PREMIUM_LABELS: Record<string, string> = { offered: "Offert", admin: "Admin" };
const premiumLabel = (u: AdminUser) =>
  u.premium_source === "subscription" ? `Abonné (${u.subscription_interval === "year" ? "annuel" : "mensuel"})` : PREMIUM_LABELS[u.premium_source] ?? "";
```

et la cellule Premium devient :

```tsx
                  <TableCell>
                    <div className="flex items-center gap-2 whitespace-nowrap">
                      <input type="checkbox" role="switch" aria-label={`Premium offert pour ${name}`} className="size-4 accent-primary"
                             checked={u.is_premium || u.role === "admin"} disabled={u.role === "admin" || premium.isPending}
                             onChange={() => premium.mutate(u)} />
                      <span className="text-xs text-muted-foreground">{premiumLabel(u)}</span>
                    </div>
                  </TableCell>
```

`frontend/src/features/admin/EditUserDialog.tsx` : le libellé de la case devient « Premium offert », et sous la case, si `user.subscription_status` :

```tsx
      {user.subscription_status && (
        <p className="text-xs text-muted-foreground">
          Abonnement Stripe : {user.subscription_interval === "year" ? "annuel" : "mensuel"}, {user.subscription_status} (lecture seule).
        </p>
      )}
```

`frontend/src/features/admin/ConfigStatusCard.tsx` : ajouter à `ITEMS` (le type de clé devient `"claude" | "smtp" | "google" | "turnstile" | "app_secret" | "admin_email" | "stripe"`, car les nouveaux champs de `ConfigStatus` ne sont pas tous booléens) :

```tsx
  { key: "stripe", label: "Paiement (Stripe)", variables: "STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_MONTHLY, STRIPE_PRICE_YEARLY" },
```

et sous la liste :

```tsx
        {status.data?.stripe && (
          <p className="text-xs text-muted-foreground">
            Stripe en mode {status.data.stripe_mode === "live" ? "réel" : "test"} · dernier webhook reçu :{" "}
            {status.data.stripe_last_webhook_at ? new Date(status.data.stripe_last_webhook_at).toLocaleString("fr-FR", { timeZone: "Europe/Paris" }) : "aucun"}
          </p>
        )}
```

- [ ] **Step 5: Lancer**

Run (dans `frontend`) : `npx vitest --run < /dev/null && npx tsc -b < /dev/null && npm run lint < /dev/null && npm run build < /dev/null`
Expected: tout passe, lint sans nouvel avertissement, build OK.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(premium): subscription card in settings and subscription view in admin"
```

**Fin du Bloc 3 : s'arrêter ici.**

---

# Bloc 4 — Textes légaux, documentation, bout en bout (Tasks 13 et 14)

### Task 13: CGV, CGU et confidentialité, pied de page, SEO

**Files:**
- Modify: `frontend/src/features/legal/content.tsx` (`CGV`, `CGU`, `PRIVACY`, `LEGAL_UPDATED`), `frontend/src/features/legal/LegalPage.tsx`, `frontend/src/features/legal/LegalPage.test.tsx`, `frontend/src/app/router.tsx` (`/cgv`), `frontend/src/app/Layout.tsx` et `frontend/src/app/SignUpBanner.tsx` (`LEGAL_PAGES`), `frontend/src/features/auth/AuthFooter.tsx`, `backend/app/core/terms.py` (`TERMS_VERSION`), `backend/app/api/routes/seo.py` (`/premium`, `/cgv`), `backend/tests/test_api_seo.py`

**Interfaces:**
- Consumes: `CGV_VERSION` (Task 1).
- Produces: page `/cgv` (publique, indexable) ; `TERMS_VERSION = "2026-10-05"` ; `LEGAL_UPDATED = "5 octobre 2026"` ; `/premium` et `/cgv` dans le sitemap et autorisés par robots.txt.

- [ ] **Step 1: Tests qui échouent**

`frontend/src/features/legal/LegalPage.test.tsx`, ajouter :

```tsx
test("CGV : prix, résiliation, rétractation, pas un conseil", () => {
  renderWithProviders(<LegalPage kind="cgv" />);
  expect(screen.getByRole("heading", { level: 1, name: "Conditions générales de vente" })).toBeInTheDocument();
  expect(screen.getByText(/renonce expressément à son droit de rétractation/)).toBeInTheDocument();
  expect(screen.getByText(/effective à la fin de la période déjà payée/)).toBeInTheDocument();
  expect(screen.getByText(/pas un conseil en investissement/)).toBeInTheDocument();
});

test("confidentialité : Stripe sous-traitant, la carte n'est jamais vue", () => {
  renderWithProviders(<LegalPage kind="confidentialite" />);
  expect(screen.getByText(/Stripe/)).toBeInTheDocument();
  expect(screen.getByText(/ne voit jamais votre numéro de carte/)).toBeInTheDocument();
});
```

(adapter aux imports existants du fichier.) `backend/tests/test_api_seo.py`, ajouter :

```python
def test_premium_and_sales_terms_are_indexable(anon_client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "seo_indexing", True)
    robots = anon_client.get("/api/seo/robots.txt").text
    assert "Allow: /premium$" in robots and "Allow: /cgv" in robots
    sitemap = anon_client.get("/api/seo/sitemap.xml").text
    assert "/premium</loc>" in sitemap and "/cgv</loc>" in sitemap
```

(si les tests SEO existants passent `seo_indexing` autrement, suivre leur façon de faire.)

- [ ] **Step 2: Lancer, vérifier l'échec**

Run : `npx vitest --run src/features/legal < /dev/null` (dans `frontend`) et `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_seo.py`
Expected: FAIL.

- [ ] **Step 3: Textes** — dans `frontend/src/features/legal/content.tsx` :

`LEGAL_UPDATED = "5 octobre 2026"`.

CGU, section 1 : « PEA Radar est un outil d'aide à la décision et d'apprentissage pour le Plan d'Épargne en Actions (PEA). L'essentiel du site est gratuit ; l'assistant IA et la liste des prévisions font partie d'un abonnement payant, Premium. » Section 2 : « Les pages publiques (actions, ETF, pages légales, présentation de Premium) restent consultables sans compte. » Section 6 « Premium » :

```tsx
      <Section title="6. Premium">
        <p>
          Premium donne accès à l'assistant IA et à la liste des prévisions court terme. Il s'obtient par un abonnement payant,
          mensuel ou annuel, régi par les <Link className="underline" to="/cgv">conditions générales de vente</Link>. L'éditeur peut
          aussi l'offrir à certains comptes.
        </p>
      </Section>
```

PRIVACY : dans « Données collectées », ajouter `<li>Abonnement : formule, état et dates de l'abonnement Premium, et la preuve de vos accords avant paiement (version des CGV, date, renonciation au droit de rétractation). PEA Radar ne voit jamais votre numéro de carte : le paiement est traité par Stripe.</li>` ; dans les finalités, la ligne `["Abonnement Premium et facturation", "Exécution du contrat (CGV) ; obligation légale pour les factures"]` ; dans les durées, `["Abonnement et accords de vente", "Jusqu'à la suppression du compte"]` et `["Factures (chez Stripe)", "10 ans (obligation comptable)"]` ; dans les sous-traitants, `<li><strong>Stripe</strong> (Stripe Payments Europe, Irlande) : paiement de l'abonnement et factures.</li>` ; dans les transferts, ajouter Stripe à la liste des sociétés pouvant traiter des données aux États-Unis.

Nouvelle fonction `CGV` (même style que `CGU`) :

```tsx
export function CGV() {
  return (
    <>
      <Section title="1. Vendeur">
        <p>[À COMPLÉTER : nom ou société, statut, SIRET, adresse, adresse de contact].</p>
      </Section>
      <Section title="2. Objet">
        <p>
          Ces conditions régissent l'abonnement <strong>PEA Radar Premium</strong>, qui donne accès à l'assistant IA et à la liste
          des prévisions court terme, pour un utilisateur disposant d'un compte PEA Radar. Le reste du site reste régi par les{" "}
          <Link className="underline" to="/cgu">CGU</Link>.
        </p>
      </Section>
      <Section title="3. Prix et paiement">
        <List>
          <li>Les prix sont affichés sur la page <Link className="underline" to="/premium">Premium</Link>, en euros toutes taxes comprises. [À VÉRIFIER : mention « TVA non applicable, article 293 B du CGI » si le vendeur est en franchise de TVA.]</li>
          <li>Le paiement se fait par carte bancaire via Stripe, au début de chaque période (mois ou année). PEA Radar ne voit jamais les données de carte.</li>
          <li>Les factures sont disponibles depuis « Gérer mon abonnement », dans les Réglages.</li>
        </List>
      </Section>
      <Section title="4. Durée et renouvellement">
        <p>
          L'abonnement est conclu pour un mois ou un an et se renouvelle automatiquement pour la même durée. Pour la formule annuelle,
          un mail rappelle la date et le prix du renouvellement au moins 30 jours avant.
        </p>
      </Section>
      <Section title="5. Résiliation">
        <p>
          L'abonné peut résilier à tout moment depuis « Gérer mon abonnement ». La résiliation est effective à la fin de la période
          déjà payée : l'accès Premium continue jusque-là, sans remboursement au prorata. La suppression du compte met fin à
          l'abonnement immédiatement, sans remboursement de la période en cours.
        </p>
      </Section>
      <Section title="6. Droit de rétractation">
        <p>
          Premium est un service fourni dès la souscription. Avant de payer, l'abonné demande l'accès immédiat et renonce
          expressément à son droit de rétractation de 14 jours (article L221-28 du Code de la consommation), en cochant une case
          prévue à cet effet.
        </p>
      </Section>
      <Section title="7. Impayés">
        <p>
          En cas d'échec de paiement, Stripe réessaie pendant quelques jours et l'accès continue. Sans paiement au terme de ces
          tentatives, l'abonnement prend fin et l'accès Premium est retiré.
        </p>
      </Section>
      <Section title="8. Service">
        <List>
          <li>PEA Radar n'est <strong>pas un conseil en investissement</strong> : l'assistant et les prévisions sont des outils d'aide à la décision, sans garantie de résultat.</li>
          <li>L'assistant IA est soumis à une limite d'utilisation mensuelle.</li>
          <li>Le service peut évoluer (méthodes de prévision, modèle d'IA) et être interrompu pour maintenance.</li>
        </List>
      </Section>
      <Section title="9. Médiation et litiges">
        <p>
          En cas de litige, l'abonné peut recourir gratuitement au médiateur de la consommation : [À COMPLÉTER : nom et site du
          médiateur]. Ces conditions sont soumises au droit français.
        </p>
      </Section>
    </>
  );
}
```

- [ ] **Step 4: Page, routes, pied de page, version**

`LegalPage.tsx` : `type Kind = "cgu" | "cgv" | "confidentialite" | "mentions-legales";` et `cgv: { title: "Conditions générales de vente", description: "Les conditions de l'abonnement PEA Radar Premium.", Body: CGV },` (import `CGV`).

`router.tsx` : `{ path: "cgv", element: <LegalPage kind="cgv" /> },` après `cgu`.

`Layout.tsx` et `SignUpBanner.tsx` : ajouter `"/cgv"` à `LEGAL_PAGES` (lisible avant d'accepter les nouvelles CGU).

`AuthFooter.tsx` : lien `<Link to="/cgv" className="hover:text-foreground">CGV</Link>` après CGU. Ajouter aussi les liens légaux au pied de l'application dans `Layout.tsx` (sous la phrase actuelle) : « Mentions légales · CGU · CGV · Confidentialité », chacun un `Link`.

`backend/app/core/terms.py` : `TERMS_VERSION = "2026-10-05"` (CGU et confidentialité parlent de Stripe : tout le monde ré-accepte une fois).

`backend/app/api/routes/seo.py` : `PUBLIC_PATHS = ["/", "/explorer", "/etf", "/premium", "/cgv"]` et dans `robots` : ajouter `"Allow: /premium$", "Allow: /cgv"` à la liste `Allow` ; ajouter `"/api/billing/"` à `PRIVATE_API_PATHS` (l'API d'abonnement n'a rien à indexer).

- [ ] **Step 5: Lancer**

Run : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` puis, dans `frontend`, `npx vitest --run < /dev/null && npx tsc -b < /dev/null && npm run lint < /dev/null`
Expected: tout passe (les tests qui construisent un utilisateur utilisent `TERMS_VERSION` : aucune casse attendue ; si un test frontend fige « 1er octobre 2026 », le mettre à jour).

- [ ] **Step 6: Commit**

```bash
git add frontend/src backend/app/core/terms.py backend/app/api/routes/seo.py backend/tests/test_api_seo.py
git commit -m "feat(premium): sales terms page, updated terms and privacy, SEO for premium"
```

### Task 14: Documentation, `.env.example`, bout en bout, vérification finale, PR

**Files:**
- Create: `frontend/public/guide/app/premium.md`, `frontend/public/documentation/abonnement.md`, `frontend/e2e/premium.spec.ts`
- Modify: `frontend/public/guide/_sidebar.md`, `frontend/public/guide/faq.md`, `frontend/public/guide/app/reglages.md`, `frontend/public/documentation/_sidebar.md`, `frontend/public/documentation/api.md`, `frontend/public/documentation/base-de-donnees.md`, `frontend/public/documentation/comptes.md`, `frontend/public/documentation/registre.md`, `frontend/e2e/seo.spec.ts`, `.env.example`, `CLAUDE.md`

- [ ] **Step 1: `.env.example`** — ajouter, avec un commentaire par ligne et des valeurs vides :

```bash
# Abonnement Premium (Stripe). Les quatre sont nécessaires ; vides = « L'abonnement arrive bientôt ».
# Mode test : clés sk_test_… du tableau de bord Stripe (Développeurs > Clés API). Voir /documentation/ > Abonnement.
STRIPE_SECRET_KEY=
# Secret de signature du webhook (whsec_…), donné par Stripe à la création du point de terminaison, ou par « stripe listen ».
STRIPE_WEBHOOK_SECRET=
# Identifiants des deux prix récurrents du produit « PEA Radar Premium » (price_…).
STRIPE_PRICE_MONTHLY=
STRIPE_PRICE_YEARLY=
```

Ne pas ouvrir `.env`.

- [ ] **Step 2: Documentation admin** — `frontend/public/documentation/abonnement.md` (et une entrée « Abonnement (Stripe) » dans `_sidebar.md`) :
  - fonctionnement : Checkout, portail, webhook, synchronisation de nuit (03:30), rappel annuel P5 (09:00), résiliations en attente (chaque minute) ; tableau des mails P1 à P5 ;
  - qui est Premium (admin, offert, abonné `active` / `past_due` / `trialing`) ;
  - mise en place pas à pas : créer un compte Stripe ; produit « PEA Radar Premium » avec deux prix récurrents TTC en EUR (mensuel, annuel) ; copier les `price_…` ; portail client (Paramètres > Facturation > Portail client : autoriser changement de carte, factures, changement de formule entre les deux prix, résiliation **en fin de période**) ; e-mails clients (Paramètres > E-mails clients : reçus de paiement et factures) ; webhook (Développeurs > Webhooks : `https://<domaine>/api/billing/webhook`, événements `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`) ; renseigner les 4 variables puis `docker compose up -d --build api worker` ;
  - tester en local : `stripe login`, `stripe listen --forward-to localhost:8095/api/billing/webhook` (copier le `whsec_…` affiché dans `STRIPE_WEBHOOK_SECRET`), carte `4242 4242 4242 4242` (date future, CVC quelconque), carte refusée `4000 0000 0000 0341` pour tester P2, horloges de test Stripe pour avancer dans le temps ;
  - passer en mode réel : statut (micro-entreprise avec SIRET au minimum), activation du compte Stripe, clés `sk_live_…`, nouveau webhook en mode réel ; l'onglet Admin affiche « mode réel » ;
  - dépannage : état de la configuration (dernier webhook reçu), `docker compose logs worker | grep -i stripe` ;
  - rembourser : à la main dans le tableau de bord Stripe (hors application).

`comptes.md` : section Premium mise à jour (renvoi vers `abonnement.md`, « Premium offert » dans l'onglet Admin, colonne « Abonné (mensuel/annuel) »), événements `subscription_started`, `subscription_ended`, `billing_consent`, suppression d'un compte abonné (résiliation par file). `api.md` : les 6 routes `/api/billing/*`, leurs codes d'erreur, `premium_source` dans `/api/me`, 403 `premium_required` sur les deux routes de prévision. `base-de-donnees.md` : tables `subscriptions`, `stripe_events`, `billing_consents`, `stripe_cancellations`. `registre.md` : traitement « Abonnements et paiements » (finalité, base légale : exécution du contrat et obligation légale, données, destinataire Stripe, durées : compte / 30 jours pour `stripe_events` / 10 ans chez Stripe pour les factures).

- [ ] **Step 3: Guide** — `frontend/public/guide/app/premium.md` (entrée « Premium » dans `_sidebar.md`) : ce que contient Premium, ce qui reste gratuit (dont le bilan des prévisions), les deux formules, comment s'abonner (les deux cases expliquées simplement), gérer / résilier (Réglages > Abonnement > Gérer mon abonnement), que se passe-t-il si un paiement échoue, rappel annuel. Sans nom de fichier ni commande. `reglages.md` : la carte Abonnement. `faq.md` : « Premium est-il obligatoire ? », « Comment résilier ? », « Suis-je remboursé si je résilie ? » (non, accès jusqu'à la fin de la période), « PEA Radar voit-il ma carte ? » (non).

- [ ] **Step 4: Bout en bout** — `frontend/e2e/premium.spec.ts`. Le compte e2e (`global-setup.ts`, `ensure-user --admin`) est **admin, donc Premium** ; Stripe n'est pas configuré dans l'environnement e2e. Le cas « membre gratuit » est couvert par les tests Vitest (Task 10) et pytest (Task 4).

```ts
import { expect, test } from "@playwright/test";

test("admin : Premium offert, prévisions ouvertes", async ({ page }) => {
  await page.goto("/premium");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/PEA Radar Premium/);
  await expect(page.getByText("L'abonnement arrive bientôt.")).toBeVisible();
  await page.goto("/previsions");
  await expect(page.getByRole("button", { name: "Prédictions" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("Réservé aux membres Premium")).toHaveCount(0);
});

test("réglages : carte Abonnement", async ({ page }) => {
  await page.goto("/reglages#abonnement");
  await expect(page.getByRole("heading", { name: "Abonnement" })).toBeVisible();
  await expect(page.getByText("Premium vous est offert.")).toBeVisible();
});

test("visiteur : CGV et page Premium publiques", async ({ browser }) => {
  const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const page = await context.newPage();
  await page.goto("/cgv");
  await expect(page.getByRole("heading", { level: 1, name: "Conditions générales de vente" })).toBeVisible();
  await page.goto("/premium");
  await expect(page.getByText("L'abonnement arrive bientôt.")).toBeVisible();
  await context.close();
});
```

Note : sans Stripe configuré, `/premium` affiche « L'abonnement arrive bientôt. » avant le bloc d'action, donc « Premium vous est offert. » n'y apparaît pas ; c'est la carte des Réglages qui le montre. `seo.spec.ts` : ajouter `/premium/merci` à `NOINDEX`, et `/premium`, `/cgv` aux pages publiques indexables si le test les énumère.

- [ ] **Step 5: `CLAUDE.md`** — ligne « Comptes utilisateurs » : étapes `comptes-socle` à `notifications` faites, et **Premium payant (Stripe)** : spec `docs/superpowers/specs/2026-09-30-premium-stripe-design.md`. Dans « Contenu des dossiers » (backend) : `services/billing/` (passerelle Stripe `gateway.py` / `stripe_gateway.py`, règle d'accès `access.py`, `apply_subscription()` dans `state.py`, webhook), tâches `jobs/billing.py`. Dans « Conventions > Comptes » : `require_premium()` protège l'assistant **et** les prévisions (liste et bloc de fiche) ; tout appel à Stripe passe par `BillingGateway` (faux `tests/fake_billing.py`, fixture `fake_billing`) ; l'état d'un abonnement ne s'écrit que par `apply_subscription()`. Dans « Secrets » : ajouter les 4 variables Stripe. Mettre à jour les nombres de tests.

- [ ] **Step 6: Vérification complète**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q
cd frontend && npx vitest --run < /dev/null && npx tsc -b < /dev/null && npm run lint < /dev/null && npm run build < /dev/null
```

Puis bout en bout : `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait api worker web && docker compose restart web`, vider `rate_limit_hits` (`docker compose exec -T db psql -U pea -d pea_radar -c "DELETE FROM rate_limit_hits"`), `cd frontend && npm run e2e < /dev/null`, puis restaurer : `docker compose up -d --wait api worker && docker compose restart web`.
Expected: tout passe. Le compte e2e devra ré-accepter les CGU (nouvelle version) : si les tests e2e échouent sur `/accepter-cgu`, relancer `python -m app.cli ensure-user` (qui accepte la version en vigueur) comme le fait la mise en place e2e.

- [ ] **Step 7: Commit et PR**

```bash
git add .env.example CLAUDE.md frontend/public frontend/e2e
git commit -m "docs(premium): admin setup guide, user guide, registry and end-to-end tests"
git push -u origin premium
gh pr create --base notifications --title "Abonnement Premium (Stripe)" --body "..."
```

(base `master` si les PR #6 et #7 sont fusionnées ; corps de PR : résumé, tests, points à faire par l'utilisateur — compte Stripe, 4 variables, webhook, CGV à compléter, statut —, terminé par la ligne 🤖 Generated with [Claude Code](https://claude.com/claude-code).)

**Fin du Bloc 4.**
