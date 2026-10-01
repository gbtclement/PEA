# Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chaque membre choisit les mails N1 à N6, crée des alertes de prix depuis la fiche d'un titre et se désinscrit en un clic ; le worker envoie ces notifications. On solde aussi les points mineurs laissés par la relecture de `comptes-rgpd`.

**Architecture:** Un paquet `backend/app/services/notifications/` (préférences, jeton de désinscription, envoi `notify()`, un module par famille de mails) sans commit ; des tâches du worker dans `app/jobs/notifications.py` appelées par le planificateur ; des routes `/api/me/notifications`, `/api/me/price-alerts` et `/api/unsubscribe`. Côté site : une carte « Notifications » dans les Réglages, un bouton « Créer une alerte » sur la fiche d'un titre et une page `/desinscription`.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, APScheduler, Jinja2 ; React 19, TanStack Query, react-router 7, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-28-comptes-utilisateurs-design.md` (sections 1.2, 4.1, 5.1, 5.2, 6.4, 8, 10, 11 : étape 5 `notifications`).

**Branche :** `notifications`, créée depuis `comptes-rgpd` (la PR #6 n'est pas encore fusionnée : la PR de ce lot visera `master` si #6 l'est, sinon `comptes-rgpd`).

## Global Constraints

- Textes affichés et mails en français simple ; identifiants de code en anglais ; commits en anglais, conventional commits.
- Notifications (spec 5.1) : N1 forte variation (activé, seuil 5 %), N2 seuil de prix (activé), N3 récap du soir (désactivé), N4 récap de la semaine (désactivé), N5 rappel du compteur d'ordres (activé), N6 changement de score d'un favori (désactivé).
- Déclenchement (spec 5.1) : N1 « en séance, toutes les 15 min ; un mail regroupant les titres concernés ; au plus une fois par titre et par jour » ; N2 « après chaque mise à jour des cours ; l'alerte se désactive une fois déclenchée et peut être réarmée » ; N3 « 18 h 45 les jours de bourse » ; N4 « samedi 9 h » ; N5 « 1er octobre, 1er novembre, 1er décembre à 9 h, s'il manque des ordres selon ses réglages de frais » ; N6 « après le passage du soir » (entrée ou sortie du top 10, ± 10 points).
- « Au plus 50 alertes actives par utilisateur. »
- Chaque notification porte `List-Unsubscribe` et `List-Unsubscribe-Post: List-Unsubscribe=One-Click` ; le pied de mail a « Gérer mes notifications » et l'avertissement « outil d'aide à la décision, pas un conseil en investissement » (spec 5.2).
- Les mails de compte (C1 à C8) ne dépendent jamais des préférences.
- Seuls les comptes validés reçoivent des notifications.
- L'API n'envoie jamais de mail ; les services ne font jamais de commit ; `enqueue()` reste le seul point d'entrée de la file (CLAUDE.md).
- Aucun jeton en clair en base (CLAUDE.md) : voir Ruling 1.
- Tests backend : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` ; frontend depuis `frontend` : `npx vitest --run`, `npx tsc -b`, `npm run lint`, `npm run build`.

## Rulings (décisions du plan, écarts à la spec)

1. **Jeton de désinscription signé, pas stocké.** La spec prévoit une colonne `unsubscribe_token`, mais CLAUDE.md interdit tout jeton en clair en base, et le mail doit contenir le jeton à chaque envoi. Le jeton est donc `<user_id>.<HMAC-SHA256(APP_SECRET, "unsubscribe:<user_id>")>`, sans colonne. Sans `APP_SECRET`, aucune notification ne part (message dans les logs du worker).
2. **Préférences créées à la demande.** Tant qu'un compte n'a rien réglé, il n'a pas de ligne `notification_prefs` : les valeurs par défaut s'appliquent.
3. **N2 suspendu quand N2 est désactivé** : les alertes restent armées et ne sont pas évaluées.
4. **N5 seulement pour qui a déjà saisi au moins un ordre** : un compte sans portefeuille ne reçoit pas « il vous manque 12 ordres ».
5. **N4 : performance sur 5 séances** calculée avec `perf_1w` des positions, pondérée par leur valeur.
6. **Deux tables techniques en plus de la spec 1.2** : `score_snapshots` (scores et rang du top 10 de chaque soir, gardés 14 jours, pour N4 et N6) et `move_notices` (titres déjà signalés par N1 dans la journée, gardés 7 jours).
7. **`/api/me/notifications` passe par `get_account_user()`** : se retirer des mails (droit d'opposition, spec 6.4) reste possible avec des CGU périmées. Les alertes de prix passent par `get_current_user()`.

## Review Focus

1. **Aucun doublon quand une tâche repasse** (redémarrage du worker, rattrapage) : N1 une fois par titre et par jour, N2 une fois puis désarmée, N3 et N6 une fois par jour, N4 une fois par semaine, N5 une fois par mois. Tests : Task 5 `test_alert_fires_once_and_disarms`, Task 6 `test_same_title_is_signalled_once_a_day`, Task 7 `test_daily_recap_once_per_day`, Task 8 `test_weekly_recap_once_per_week`.
2. **Lien de désinscription forgé ou d'un autre** : 404 sans rien modifier ; le clic unique d'un service de mail (POST sans cookie ni `Origin`) fonctionne. Tests : Task 4 `test_forged_or_unknown_links_are_404`, `test_one_click_disables_one_notification`.
3. **Préférence désactivée respectée, compte non validé jamais visé.** Tests : Task 1 `test_recipients_follow_prefs_and_skip_unverified`, Task 5 `test_alert_ignored_while_price_alerts_are_off`.
4. **Alertes d'un autre compte, limite de 50, seuil déjà franchi.** Tests : Task 2 `test_alerts_of_another_user_are_404`, `test_fifty_active_alerts_at_most`, `test_create_list_rearm_delete_alert`.
5. **Titre coté en couronnes (Oslo)** : l'alerte compare le cours dans sa devise et le mail affiche « NOK », pas « € ». Test : Task 5 `test_foreign_currency_alert_keeps_its_currency`.

---

# Bloc 1 — Socle backend (Tasks 1 à 4)

### Task 1: Tables, préférences et jeton de désinscription

**Files:**
- Create: `backend/app/models/notifications.py`, `backend/alembic/versions/f1a3c5e7b9d1_notifications.py`, `backend/app/services/notifications/__init__.py` (vide), `backend/app/services/notifications/prefs.py`, `backend/app/services/notifications/unsubscribe.py`, `backend/tests/test_notification_prefs.py`
- Modify: `backend/app/models/__init__.py`, `backend/tests/factories.py` (`make_quote`), `backend/tests/conftest.py` (fixture `app_secret`)

**Interfaces:**
- Produces:
  - modèles `NotificationPrefs`, `PriceAlert`, `ScoreSnapshot`, `MoveNotice` (exportés par `app.models`) ;
  - `prefs.KINDS: tuple[str, ...] = ("price_move", "price_alert", "daily_recap", "weekly_recap", "order_reminder", "score_change")`, `prefs.DEFAULTS: dict[str, bool]`, `prefs.DEFAULT_THRESHOLD = 5.0` ;
  - `get_prefs(db, user_id) -> NotificationPrefs` (ligne existante, ou objet non enregistré avec les valeurs par défaut) ;
  - `save_prefs(db, user_id, values: dict) -> NotificationPrefs` (crée la ligne si besoin, pas de commit) ;
  - `recipients(db, kind: str) -> list[tuple[User, NotificationPrefs]]` (comptes validés qui ont `kind` activé, triés par adresse) ;
  - `make_token(user_id: uuid.UUID, secret: str) -> str`, `read_token(token: str | None, secret: str) -> uuid.UUID | None` ;
  - `tests.factories.make_quote(db, security, price, *, change_pct=None, previous_close=None, as_of=None) -> SecurityQuote` ;
  - fixture pytest `app_secret` (met `"secret-de-test"` dans `get_settings().app_secret`).

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_notification_prefs.py` :

```python
import uuid

from app.models import NotificationPrefs
from app.services.notifications.prefs import get_prefs, recipients, save_prefs
from app.services.notifications.unsubscribe import make_token, read_token
from tests.factories import make_user


def test_defaults_without_a_row(db, user):
    prefs = get_prefs(db, user.id)
    assert (prefs.price_move, prefs.price_alert, prefs.daily_recap, prefs.weekly_recap, prefs.order_reminder,
            prefs.score_change) == (True, True, False, False, True, False)
    assert prefs.move_threshold_pct == 5.0
    assert db.get(NotificationPrefs, user.id) is None  # rien n'est écrit tant que le membre n'a rien réglé


def test_save_creates_then_updates_the_row(db, user):
    save_prefs(db, user.id, {"daily_recap": True, "move_threshold_pct": 3.0})
    save_prefs(db, user.id, {"price_move": False})
    row = db.get(NotificationPrefs, user.id)
    assert (row.daily_recap, row.price_move, row.move_threshold_pct) == (True, False, 3.0)


def test_recipients_follow_prefs_and_skip_unverified(db, user):
    other = make_user(db, "autre@example.com")
    make_user(db, "pasvalide@example.com", verified=False)
    save_prefs(db, other.id, {"price_move": False, "daily_recap": True})
    assert [u.email for u, _ in recipients(db, "price_move")] == ["moi@example.com"]
    assert [u.email for u, _ in recipients(db, "daily_recap")] == ["autre@example.com"]


def test_unsubscribe_token_round_trip():
    user_id = uuid.uuid4()
    token = make_token(user_id, "s3cret")
    assert read_token(token, "s3cret") == user_id
    assert read_token(token, "autre-secret") is None
    assert read_token(token[:-1] + ("A" if token[-1] != "A" else "B"), "s3cret") is None
    assert read_token(make_token(uuid.uuid4(), "s3cret").split(".")[0] + "." + token.split(".")[1], "s3cret") is None
    assert read_token("n'importe quoi", "s3cret") is None
    assert read_token(token, "") is None
    assert read_token(None, "s3cret") is None
```

- [ ] **Step 2: Vérifier l'échec** — `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_notification_prefs.py`. Expected: FAIL (`ImportError: cannot import name 'NotificationPrefs'`).

- [ ] **Step 3: Implémentation**

`backend/app/models/notifications.py` :

```python
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotificationPrefs(Base):
    """Choix des mails N1 à N6. Pas de ligne tant que le membre n'a rien réglé : valeurs par défaut (spec 5.1)."""

    __tablename__ = "notification_prefs"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    price_move: Mapped[bool] = mapped_column(default=True, server_default=text("true"))       # N1
    price_alert: Mapped[bool] = mapped_column(default=True, server_default=text("true"))      # N2
    daily_recap: Mapped[bool] = mapped_column(default=False, server_default=text("false"))    # N3
    weekly_recap: Mapped[bool] = mapped_column(default=False, server_default=text("false"))   # N4
    order_reminder: Mapped[bool] = mapped_column(default=True, server_default=text("true"))   # N5
    score_change: Mapped[bool] = mapped_column(default=False, server_default=text("false"))   # N6
    move_threshold_pct: Mapped[float] = mapped_column(Float, default=5.0, server_default="5")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PriceAlert(Base):
    """Seuil de prix personnel (N2), dans la devise du titre. Désactivée une fois déclenchée."""

    __tablename__ = "price_alerts"
    __table_args__ = (Index("ix_price_alerts_active", "active", "security_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(5))  # above | below
    price: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScoreSnapshot(Base):
    """Score de chaque titre et rang dans le top 10, photographiés chaque soir (N4, N6). Gardés 14 jours."""

    __tablename__ = "score_snapshots"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    total: Mapped[float] = mapped_column(Float)
    top_rank: Mapped[int | None] = mapped_column(Integer)


class MoveNotice(Base):
    """Titre déjà signalé par N1 à ce membre ce jour-là (au plus une fois par titre et par jour). Gardé 7 jours."""

    __tablename__ = "move_notices"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
```

`backend/app/models/__init__.py` : importer et exporter `MoveNotice, NotificationPrefs, PriceAlert, ScoreSnapshot` depuis `app.models.notifications`, en suivant le style des imports existants (et `__all__` s'il existe).

`backend/alembic/versions/f1a3c5e7b9d1_notifications.py` :

```python
"""notification preferences, price alerts, score snapshots

Revision ID: f1a3c5e7b9d1
Revises: e6b8d0f2a4c6
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a3c5e7b9d1"
down_revision: Union[str, Sequence[str], None] = "e6b8d0f2a4c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_prefs",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("price_move", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("price_alert", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("daily_recap", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("weekly_recap", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("order_reminder", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("score_change", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("move_threshold_pct", sa.Float(), nullable=False, server_default="5"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("security_id", sa.Integer(), sa.ForeignKey("securities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_price_alerts_user_id", "price_alerts", ["user_id"])
    op.create_index("ix_price_alerts_active", "price_alerts", ["active", "security_id"])
    op.create_table(
        "score_snapshots",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("security_id", sa.Integer(), sa.ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("top_rank", sa.Integer(), nullable=True),
    )
    op.create_table(
        "move_notices",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("security_id", sa.Integer(), sa.ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("move_notices")
    op.drop_table("score_snapshots")
    op.drop_index("ix_price_alerts_active", table_name="price_alerts")
    op.drop_index("ix_price_alerts_user_id", table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_table("notification_prefs")
```

`backend/app/services/notifications/prefs.py` :

```python
"""Préférences de notification (spec 4.1, 5.1). Pas de commit ici."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NotificationPrefs, User

KINDS = ("price_move", "price_alert", "daily_recap", "weekly_recap", "order_reminder", "score_change")  # N1 à N6
DEFAULTS = {"price_move": True, "price_alert": True, "daily_recap": False, "weekly_recap": False,
            "order_reminder": True, "score_change": False}
DEFAULT_THRESHOLD = 5.0


def _defaults(user_id: uuid.UUID) -> NotificationPrefs:
    return NotificationPrefs(user_id=user_id, **DEFAULTS, move_threshold_pct=DEFAULT_THRESHOLD)


def get_prefs(db: Session, user_id: uuid.UUID) -> NotificationPrefs:
    """La ligne du membre, ou un objet non enregistré avec les valeurs par défaut."""
    return db.get(NotificationPrefs, user_id) or _defaults(user_id)


def save_prefs(db: Session, user_id: uuid.UUID, values: dict) -> NotificationPrefs:
    row = db.get(NotificationPrefs, user_id)
    if row is None:
        row = _defaults(user_id)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    db.flush()
    return row


def recipients(db: Session, kind: str) -> list[tuple[User, NotificationPrefs]]:
    """Comptes validés qui ont activé `kind`, avec leurs préférences."""
    rows = db.execute(
        select(User, NotificationPrefs).outerjoin(NotificationPrefs, NotificationPrefs.user_id == User.id)
        .where(User.email_verified_at.is_not(None)).order_by(User.email)
    ).all()
    chosen = [(user, prefs or _defaults(user.id)) for user, prefs in rows]
    return [(user, prefs) for user, prefs in chosen if getattr(prefs, kind)]
```

`backend/app/services/notifications/unsubscribe.py` :

```python
"""Jeton des liens de désinscription : signé avec APP_SECRET, jamais stocké (Ruling 1 du plan)."""
import base64
import hashlib
import hmac
import uuid


def make_token(user_id: uuid.UUID, secret: str) -> str:
    if not secret:
        raise ValueError("APP_SECRET manquant : impossible de signer un lien de désinscription")
    mac = hmac.new(secret.encode(), f"unsubscribe:{user_id}".encode(), hashlib.sha256).digest()
    return f"{user_id.hex}.{base64.urlsafe_b64encode(mac[:16]).decode().rstrip('=')}"


def read_token(token: str | None, secret: str) -> uuid.UUID | None:
    """Le compte visé si la signature est bonne, sinon None."""
    if not secret or not token or "." not in token:
        return None
    raw_id = token.split(".", 1)[0]
    try:
        user_id = uuid.UUID(hex=raw_id)
    except ValueError:
        return None
    return user_id if hmac.compare_digest(make_token(user_id, secret), token) else None
```

`backend/tests/factories.py` : ajouter `SecurityQuote` à l'import `from app.models import …`, et `from datetime import UTC, datetime` est déjà là. Ajouter :

```python
def make_quote(db: Session, security: Security, price: float, *, change_pct: float | None = None,
               previous_close: float | None = None, as_of: datetime | None = None) -> SecurityQuote:
    quote = SecurityQuote(security_id=security.id, price=price, change_pct=change_pct, previous_close=previous_close,
                          volume=1000, as_of=as_of or datetime.now(UTC))
    db.merge(quote)
    db.flush()
    return db.get(SecurityQuote, security.id)
```

`backend/tests/conftest.py`, à la fin :

```python
@pytest.fixture
def app_secret(monkeypatch):
    """Clé de signature des liens (désinscription) : vide par défaut en test."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "app_secret", "secret-de-test")
```

(Si un test liste les tables ou les modèles, par exemple dans `tests/test_models*.py`, l'étendre aux quatre nouvelles tables.)

- [ ] **Step 4: Vérifier** — même commande, puis `pytest -q` complet. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: notification preferences, price alert and snapshot tables, signed unsubscribe token"
```

---

### Task 2: API des préférences et des alertes de prix

**Files:**
- Create: `backend/app/schemas/notifications.py`, `backend/app/services/notifications/price_alerts.py`, `backend/app/api/routes/notifications.py`, `backend/tests/test_api_notifications.py`
- Modify: `backend/app/main.py` (enregistrer le routeur)

**Interfaces:**
- Consumes: Task 1 (`get_prefs`, `save_prefs`, `PriceAlert`, `make_quote`).
- Produces:
  - `GET/PUT /api/me/notifications` (`NotificationPrefsOut` : les six booléens + `move_threshold_pct`) ;
  - `GET/POST /api/me/price-alerts`, `PATCH/DELETE /api/me/price-alerts/{id}` (`PriceAlertOut` : `id, security_id, symbol, name, currency, direction, price, current_price, active, triggered_at, created_at`) ;
  - `price_alerts.MAX_ACTIVE = 50`, `reached(direction, target, price) -> bool`, `current_price(db, security_id) -> float | None`, `AlertRefused(status, code, message)`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_notifications.py` :

```python
import uuid
from datetime import UTC, datetime

from app.models import PriceAlert
from tests.factories import make_quote, make_security, make_user

DEFAULTS = {"price_move": True, "price_alert": True, "daily_recap": False, "weekly_recap": False,
            "order_reminder": True, "score_change": False, "move_threshold_pct": 5.0}


def test_prefs_round_trip(client):
    assert client.get("/api/me/notifications").json() == DEFAULTS
    body = {**DEFAULTS, "daily_recap": True, "move_threshold_pct": 3}
    assert client.put("/api/me/notifications", json=body).status_code == 200
    assert client.get("/api/me/notifications").json() == {**body, "move_threshold_pct": 3.0}


def test_threshold_between_1_and_50(client):
    assert client.put("/api/me/notifications", json={**DEFAULTS, "move_threshold_pct": 0.5}).status_code == 422
    assert client.put("/api/me/notifications", json={**DEFAULTS, "move_threshold_pct": 51}).status_code == 422


def test_create_list_rearm_delete_alert(client, db):
    security = make_security(db, "MC.PA", name="LVMH")
    make_quote(db, security, 100.0)
    created = client.post("/api/me/price-alerts", json={"security_id": security.id, "direction": "above", "price": 110})
    assert created.status_code == 201
    alert = created.json()
    assert (alert["name"], alert["currency"], alert["price"], alert["current_price"], alert["active"]) == (
        "LVMH", "EUR", 110.0, 100.0, True)
    reached = client.post("/api/me/price-alerts", json={"security_id": security.id, "direction": "above", "price": 90})
    assert reached.status_code == 400 and reached.json()["detail"]["code"] == "already_reached"

    row = db.get(PriceAlert, uuid.UUID(alert["id"]))
    row.active, row.triggered_at = False, datetime.now(UTC)
    rearmed = client.patch(f"/api/me/price-alerts/{alert['id']}", json={"active": True, "price": 120})
    assert rearmed.status_code == 200
    assert (rearmed.json()["active"], rearmed.json()["triggered_at"], rearmed.json()["price"]) == (True, None, 120.0)

    assert client.delete(f"/api/me/price-alerts/{alert['id']}").status_code == 204
    assert client.get("/api/me/price-alerts").json() == []


def test_fifty_active_alerts_at_most(client, db, user):
    security = make_security(db, "MC.PA")
    make_quote(db, security, 100.0)
    db.add_all(PriceAlert(user_id=user.id, security_id=security.id, direction="above", price=200 + i) for i in range(50))
    db.flush()
    response = client.post("/api/me/price-alerts", json={"security_id": security.id, "direction": "below", "price": 50})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "alert_limit"


def test_alerts_of_another_user_are_404(client, db):
    security = make_security(db, "MC.PA")
    other = make_user(db, "autre@example.com")
    alert = PriceAlert(user_id=other.id, security_id=security.id, direction="above", price=150)
    db.add(alert)
    db.flush()
    assert client.get("/api/me/price-alerts").json() == []
    assert client.patch(f"/api/me/price-alerts/{alert.id}", json={"active": False}).status_code == 404
    assert client.delete(f"/api/me/price-alerts/{alert.id}").status_code == 404


def test_unknown_security_is_404(client):
    response = client.post("/api/me/price-alerts", json={"security_id": 999999, "direction": "above", "price": 10})
    assert response.status_code == 404


def test_visitors_get_401(anon_client):
    assert anon_client.get("/api/me/notifications").status_code == 401
    assert anon_client.get("/api/me/price-alerts").status_code == 401
```

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_api_notifications.py`. Expected: FAIL (404 sur les routes).

- [ ] **Step 3: Implémentation**

`backend/app/schemas/notifications.py` :

```python
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NotificationPrefsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    price_move: bool
    price_alert: bool
    daily_recap: bool
    weekly_recap: bool
    order_reminder: bool
    score_change: bool
    move_threshold_pct: float


class NotificationPrefsIn(BaseModel):
    price_move: bool
    price_alert: bool
    daily_recap: bool
    weekly_recap: bool
    order_reminder: bool
    score_change: bool
    move_threshold_pct: float = Field(ge=1, le=50)


class PriceAlertIn(BaseModel):
    security_id: int
    direction: Literal["above", "below"]
    price: float = Field(gt=0, lt=1_000_000)


class PriceAlertUpdate(BaseModel):
    direction: Literal["above", "below"] | None = None
    price: float | None = Field(default=None, gt=0, lt=1_000_000)
    active: bool | None = None


class PriceAlertOut(BaseModel):
    id: uuid.UUID
    security_id: int
    symbol: str
    name: str
    currency: str
    direction: str
    price: float
    current_price: float | None
    active: bool
    triggered_at: datetime | None
    created_at: datetime
```

`backend/app/services/notifications/price_alerts.py` :

```python
"""Alertes de prix (N2) : création, réarmement. Pas de commit ici."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, PriceAlert, SecurityQuote

MAX_ACTIVE = 50


class AlertRefused(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def reached(direction: str, target: float, price: float) -> bool:
    return price >= target if direction == "above" else price <= target


def current_price(db: Session, security_id: int) -> float | None:
    """Dernier cours connu, dans la devise du titre."""
    quote = db.get(SecurityQuote, security_id)
    if quote is not None:
        return quote.price
    return db.scalars(select(DailyPrice.close).where(DailyPrice.security_id == security_id)
                      .order_by(DailyPrice.date.desc()).limit(1)).first()


def check_new_threshold(db: Session, user_id: uuid.UUID, security_id: int, direction: str, price: float,
                        *, ignore: uuid.UUID | None = None) -> None:
    """Refuse une 51e alerte active, ou un seuil déjà franchi (elle partirait tout de suite)."""
    active = select(func.count()).select_from(PriceAlert).where(PriceAlert.user_id == user_id, PriceAlert.active.is_(True))
    if ignore is not None:
        active = active.where(PriceAlert.id != ignore)
    if db.scalar(active) >= MAX_ACTIVE:
        raise AlertRefused(400, "alert_limit", f"{MAX_ACTIVE} alertes actives au plus : supprimez-en une.")
    now_price = current_price(db, security_id)
    if now_price is not None and reached(direction, price, now_price):
        side = "au-dessus" if direction == "above" else "en dessous"
        raise AlertRefused(400, "already_reached", f"Le cours est déjà {side} de ce prix : choisissez un autre seuil.")
```

`backend/app/api/routes/notifications.py` :

```python
import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import fail
from app.core.current_user import get_account_user, get_current_user
from app.core.db import get_db
from app.models import PriceAlert, Security, User
from app.schemas.notifications import NotificationPrefsIn, NotificationPrefsOut, PriceAlertIn, PriceAlertOut, PriceAlertUpdate
from app.services.fx import currency_for_market
from app.services.notifications.prefs import get_prefs, save_prefs
from app.services.notifications.price_alerts import AlertRefused, check_new_threshold, current_price

router = APIRouter(tags=["notifications"])


@router.get("/me/notifications", response_model=NotificationPrefsOut)
def read_notification_prefs(db: Session = Depends(get_db), user: User = Depends(get_account_user)) -> NotificationPrefsOut:
    return NotificationPrefsOut.model_validate(get_prefs(db, user.id))


@router.put("/me/notifications", response_model=NotificationPrefsOut)
def write_notification_prefs(payload: NotificationPrefsIn, db: Session = Depends(get_db),
                             user: User = Depends(get_account_user)) -> NotificationPrefsOut:
    """Ouverte même avec des CGU périmées : se retirer des mails reste toujours possible (spec 6.4)."""
    row = save_prefs(db, user.id, payload.model_dump())
    db.commit()
    return NotificationPrefsOut.model_validate(row)


def _out(db: Session, alert: PriceAlert) -> PriceAlertOut:
    security = db.get(Security, alert.security_id)
    return PriceAlertOut(id=alert.id, security_id=security.id, symbol=security.symbol, name=security.name,
                         currency=currency_for_market(security.market), direction=alert.direction, price=alert.price,
                         current_price=current_price(db, security.id), active=alert.active,
                         triggered_at=alert.triggered_at, created_at=alert.created_at)


def _own(db: Session, user: User, alert_id: uuid.UUID) -> PriceAlert:
    alert = db.get(PriceAlert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise fail(404, "not_found", "Alerte introuvable.")
    return alert


@router.get("/me/price-alerts", response_model=list[PriceAlertOut])
def list_price_alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[PriceAlertOut]:
    rows = db.scalars(select(PriceAlert).where(PriceAlert.user_id == user.id)
                      .order_by(PriceAlert.active.desc(), PriceAlert.created_at.desc()))
    return [_out(db, alert) for alert in rows]


@router.post("/me/price-alerts", response_model=PriceAlertOut, status_code=201)
def create_price_alert(payload: PriceAlertIn, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> PriceAlertOut:
    if db.get(Security, payload.security_id) is None:
        raise fail(404, "not_found", "Titre introuvable.")
    try:
        check_new_threshold(db, user.id, payload.security_id, payload.direction, payload.price)
    except AlertRefused as refused:
        raise fail(refused.status, refused.code, refused.message)
    alert = PriceAlert(user_id=user.id, **payload.model_dump())
    db.add(alert)
    db.commit()
    return _out(db, alert)


@router.patch("/me/price-alerts/{alert_id}", response_model=PriceAlertOut)
def update_price_alert(alert_id: uuid.UUID, payload: PriceAlertUpdate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> PriceAlertOut:
    alert = _own(db, user, alert_id)
    changes = payload.model_dump(exclude_none=True)
    direction, price = changes.get("direction", alert.direction), changes.get("price", alert.price)
    if changes.get("active", alert.active):  # réarmer ou modifier une alerte active : mêmes règles qu'à la création
        try:
            check_new_threshold(db, user.id, alert.security_id, direction, price, ignore=alert.id)
        except AlertRefused as refused:
            raise fail(refused.status, refused.code, refused.message)
    if changes.get("active") and not alert.active:
        alert.triggered_at = None
    alert.direction, alert.price, alert.active = direction, price, changes.get("active", alert.active)
    db.commit()
    return _out(db, alert)


@router.delete("/me/price-alerts/{alert_id}", status_code=204)
def delete_price_alert(alert_id: uuid.UUID, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> Response:
    db.delete(_own(db, user, alert_id))
    db.commit()
    return Response(status_code=204)
```

`backend/app/main.py` : ajouter `notifications` à l'import `from app.api.routes import …` et au tuple des modules, juste après `me`.

- [ ] **Step 4: Vérifier** — `pytest -q tests/test_api_notifications.py`, puis `pytest -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: API for notification preferences and price alerts (50 active at most)"
```

---

### Task 3: Mails de notification : modèles, pied de page, en-têtes, `notify()`

**Files:**
- Create: `backend/app/services/notifications/send.py`, six paires de modèles dans `backend/app/services/mail/templates/` : `price_move`, `price_alert`, `daily_recap`, `weekly_recap`, `order_reminder`, `score_change` (`.html` et `.txt`), `backend/tests/test_notification_mails.py`
- Modify: `backend/app/services/mail/render.py`, `backend/app/services/mail/outbox.py` (`headers`), `backend/app/services/mail/templates/_layout.html`, `backend/app/services/mail/templates/_footer.txt`, `backend/tests/test_mail_render.py` (`CONTEXTS`)

**Interfaces:**
- Consumes: Task 1 (`make_token`, fixture `app_secret`).
- Produces:
  - `enqueue(db, kind, *, to, context, user_id=None, dedupe_key=None, headers=None)` ;
  - `notify(db, user: User, kind: str, context: dict, *, dedupe_key: str) -> int | None` : ajoute `first_name`, `manage_url`, `unsubscribe_url` et les en-têtes `List-Unsubscribe` / `List-Unsubscribe-Post` ;
  - `notifications_ready() -> bool` (faux si `APP_SECRET` est vide) ;
  - filtres Jinja `eur`, `price(currency)`, `pct`, `day`, `short` ;
  - contextes des modèles :
    - `price_move` : `threshold: float`, `items: [{security_id, name, change_pct, price, currency}]` ;
    - `price_alert` : `security_id, name, direction, target, price, currency` ;
    - `daily_recap` : `day: date, has_portfolio: bool, total_value, day_change, day_change_pct, gainers, losers` (listes de `{security_id, name, change_pct}`) ;
    - `weekly_recap` : `week_end: date, has_portfolio, total_value, week_change, week_change_pct, entered, left` (listes de `{security_id, name}`), `forecasts_checked: int, forecasts_right: int` ;
    - `order_reminder` : `year, count, min_orders, remaining, penalty_fee` ;
    - `score_change` : `items: [{security_id, name, before: int, after: int, change: "entered"|"left"|"up"|"down"}]`.

- [ ] **Step 1: Tests qui échouent**

`backend/tests/test_mail_render.py` : ajouter à `CONTEXTS` (le test paramétré sur `KINDS` couvre alors les six nouveaux mails) :

```python
    "price_move": {"first_name": "Jean", "threshold": 5.0, "unsubscribe_url": "u", "manage_url": "m",
                   "items": [{"security_id": 1, "name": "LVMH", "change_pct": 6.25, "price": 612.4, "currency": "EUR"}]},
    "price_alert": {"first_name": "Jean", "security_id": 1, "name": "Equinor", "direction": "above", "target": 300.0,
                    "price": 301.5, "currency": "NOK", "unsubscribe_url": "u", "manage_url": "m"},
    "daily_recap": {"first_name": "Jean", "day": date(2026, 10, 2), "has_portfolio": True, "total_value": 12345.6,
                    "day_change": -120.5, "day_change_pct": -0.97, "unsubscribe_url": "u", "manage_url": "m",
                    "gainers": [{"security_id": 1, "name": "LVMH", "change_pct": 2.1}],
                    "losers": [{"security_id": 2, "name": "Kering", "change_pct": -3.4}]},
    "weekly_recap": {"first_name": "Jean", "week_end": date(2026, 10, 3), "has_portfolio": True, "total_value": 12345.6,
                     "week_change": 210.0, "week_change_pct": 1.73, "entered": [{"security_id": 1, "name": "LVMH"}],
                     "left": [{"security_id": 2, "name": "Kering"}], "forecasts_checked": 10, "forecasts_right": 6,
                     "unsubscribe_url": "u", "manage_url": "m"},
    "order_reminder": {"first_name": "Jean", "year": 2026, "count": 8, "min_orders": 12, "remaining": 4,
                       "penalty_fee": 96.0, "unsubscribe_url": "u", "manage_url": "m"},
    "score_change": {"first_name": "Jean", "unsubscribe_url": "u", "manage_url": "m",
                     "items": [{"security_id": 1, "name": "LVMH", "before": 58, "after": 71, "change": "entered"}]},
```

et `from datetime import UTC, date, datetime` en tête.

`backend/tests/test_notification_mails.py` :

```python
import pytest
from sqlalchemy import select

from app.models import EmailLog
from app.services.mail.render import render
from app.services.notifications.send import notifications_ready, notify
from app.services.notifications.unsubscribe import read_token
from tests.test_mail_render import BASE, CONTEXTS


def test_notification_footer_has_manage_link_unsubscribe_and_warning():
    mail = render("daily_recap", CONTEXTS["daily_recap"], base_url=BASE)
    for body in (mail.html, mail.text):
        assert "Gérer mes notifications" in body
        assert "pas un conseil en investissement" in body
        assert "Ne plus recevoir ce mail" in body


def test_account_mails_keep_the_plain_footer():
    mail = render("welcome", CONTEXTS["welcome"], base_url=BASE)
    assert "Gérer mes notifications" not in mail.html and "Ne plus recevoir" not in mail.text


def test_french_number_formats():
    mail = render("daily_recap", CONTEXTS["daily_recap"], base_url=BASE)
    assert "12 345,60 €" in mail.text and "-0,97 %" in mail.text and "02/10/2026" in mail.text
    assert "+2,10 %" in mail.text
    assert "301,50 NOK" in render("price_alert", CONTEXTS["price_alert"], base_url=BASE).text


@pytest.mark.usefixtures("app_secret")
def test_notify_adds_unsubscribe_headers_and_dedupes(db, user):
    from app.core.config import get_settings

    assert notifications_ready()
    context = {"year": 2026, "count": 8, "min_orders": 12, "remaining": 4, "penalty_fee": 96.0}
    assert notify(db, user, "order_reminder", context, dedupe_key=f"order_reminder:{user.id}:2026-10") is not None
    assert notify(db, user, "order_reminder", context, dedupe_key=f"order_reminder:{user.id}:2026-10") is None
    row = db.scalar(select(EmailLog).where(EmailLog.kind == "order_reminder"))
    assert row.recipient == user.email and row.user_id == user.id
    assert row.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    link = row.headers["List-Unsubscribe"]
    assert link.startswith("<") and "/api/unsubscribe?jeton=" in link and "type=order_reminder" in link
    token = link.split("jeton=")[1].split("&")[0]
    assert read_token(token, get_settings().app_secret) == user.id
    assert "/desinscription?jeton=" in row.text and "/reglages#notifications" in row.text


def test_no_secret_no_notifications(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "app_secret", "")
    assert notifications_ready() is False
```

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_mail_render.py tests/test_notification_mails.py`. Expected: FAIL (`KeyError` sur les nouveaux types, `ImportError` sur `send`).

- [ ] **Step 3: Implémentation**

`render.py` :
- `from datetime import date, datetime`.
- Ajouter à `SUBJECTS` :

```python
    "price_move": "Forte variation de vos titres suivis",
    "price_alert": "Alerte de prix : {name}",
    "daily_recap": "Votre récap du soir PEA Radar",
    "weekly_recap": "Votre récap de la semaine PEA Radar",
    "order_reminder": "Compteur d'ordres : il vous manque {remaining} ordre(s)",
    "score_change": "Changement de score de vos favoris",
```

- Filtres, sous `_paris` :

```python
def _number(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _eur(value: float) -> str:
    return f"{_number(value)} €"


def _price(value: float, currency: str = "EUR") -> str:
    return f"{_number(value)} {'€' if currency == 'EUR' else currency}"


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{'+' if value > 0 else ''}{_number(value)} %"


def _day(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _short(value: float) -> str:
    return f"{value:g}".replace(".", ",")
```

et, après `_env.filters["paris"] = _paris` : `_env.filters.update(eur=_eur, price=_price, pct=_pct, day=_day, short=_short)`.

`outbox.py`, `enqueue` : paramètre `headers: dict[str, str] | None = None` après `dedupe_key`, et `headers=headers or {}` dans `.values(...)` à la place de `headers={}`.

`_layout.html` : remplacer la dernière ligne de tableau (le pied de page) par :

```html
    <tr><td style="padding:16px 28px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280">
      {% if unsubscribe_url is defined %}
      PEA Radar est un outil d'aide à la décision et d'apprentissage, pas un conseil en investissement. Cours différés.<br>
      <a href="{{ manage_url }}" style="color:#4f46e5">Gérer mes notifications</a> · <a href="{{ unsubscribe_url }}" style="color:#4f46e5">Ne plus recevoir ce mail</a>
      {% else %}
      Vous recevez ce mail car un compte PEA Radar utilise cette adresse. <a href="{{ base_url }}" style="color:#4f46e5">{{ base_url }}</a>
      {% endif %}
    </td></tr>
```

`_footer.txt` :

```
--
PEA Radar — {{ base_url }}
{% if unsubscribe_url is defined %}
PEA Radar est un outil d'aide à la décision et d'apprentissage, pas un conseil en investissement. Cours différés.
Gérer mes notifications : {{ manage_url }}
Ne plus recevoir ce mail : {{ unsubscribe_url }}
{% else %}
Vous recevez ce mail car un compte PEA Radar utilise cette adresse.
{% endif %}
```

Modèles (dans `templates/`) :

`price_move.html`
```html
{% extends "_layout.html" %}
{% block body %}
<p>{{ items|length }} titre(s) que vous suivez bougent aujourd'hui d'au moins {{ threshold|short }} % :</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse">
{% for item in items %}
  <tr>
    <td style="padding:6px 0;border-bottom:1px solid #e5e7eb"><a href="{{ base_url }}/titres/{{ item.security_id }}" style="color:#4f46e5">{{ item.name }}</a></td>
    <td style="padding:6px 0;border-bottom:1px solid #e5e7eb;text-align:right;font-weight:600;color:{{ '#16a34a' if item.change_pct > 0 else '#dc2626' }}">{{ item.change_pct|pct }}</td>
    <td style="padding:6px 0 6px 12px;border-bottom:1px solid #e5e7eb;text-align:right">{{ item.price|price(item.currency) }}</td>
  </tr>
{% endfor %}
</table>
<p style="font-size:13px;color:#6b7280">Vous ne recevrez pas d'autre mail pour ces titres aujourd'hui.</p>
{% endblock %}
```

`price_move.txt`
```
Bonjour {{ first_name }},

{{ items|length }} titre(s) que vous suivez bougent aujourd'hui d'au moins {{ threshold|short }} % :

{% for item in items %}
- {{ item.name }} : {{ item.change_pct|pct }} ({{ item.price|price(item.currency) }}) — {{ base_url }}/titres/{{ item.security_id }}
{% endfor %}

Vous ne recevrez pas d'autre mail pour ces titres aujourd'hui.

{% include "_footer.txt" %}
```

`price_alert.html`
```html
{% extends "_layout.html" %}
{% block body %}
<p><a href="{{ base_url }}/titres/{{ security_id }}" style="color:#4f46e5;font-weight:600">{{ name }}</a> est passé {{ "au-dessus" if direction == "above" else "en dessous" }} de votre seuil de {{ target|price(currency) }} : dernier cours {{ price|price(currency) }}.</p>
<p>L'alerte est maintenant désactivée. Vous pouvez la réarmer dans vos réglages.</p>
{% endblock %}
```

`price_alert.txt`
```
Bonjour {{ first_name }},

{{ name }} est passé {{ "au-dessus" if direction == "above" else "en dessous" }} de votre seuil de {{ target|price(currency) }} : dernier cours {{ price|price(currency) }}.
{{ base_url }}/titres/{{ security_id }}

L'alerte est maintenant désactivée. Vous pouvez la réarmer dans vos réglages.

{% include "_footer.txt" %}
```

`daily_recap.html`
```html
{% extends "_layout.html" %}
{% block body %}
<p>Voici votre récap de la séance du {{ day|day }}.</p>
{% if has_portfolio %}
<p>Valeur de votre portefeuille : <strong>{{ total_value|eur }}</strong><br>Variation du jour : <strong>{{ day_change|eur }}</strong> ({{ day_change_pct|pct }})</p>
{% endif %}
{% if gainers %}
<p style="margin-bottom:4px"><strong>Plus fortes hausses de vos favoris</strong></p>
<ul style="margin-top:0">
{% for item in gainers %}
  <li><a href="{{ base_url }}/titres/{{ item.security_id }}" style="color:#4f46e5">{{ item.name }}</a> : {{ item.change_pct|pct }}</li>
{% endfor %}
</ul>
{% endif %}
{% if losers %}
<p style="margin-bottom:4px"><strong>Plus fortes baisses de vos favoris</strong></p>
<ul style="margin-top:0">
{% for item in losers %}
  <li><a href="{{ base_url }}/titres/{{ item.security_id }}" style="color:#4f46e5">{{ item.name }}</a> : {{ item.change_pct|pct }}</li>
{% endfor %}
</ul>
{% endif %}
{% endblock %}
```

`daily_recap.txt`
```
Bonjour {{ first_name }},

Voici votre récap de la séance du {{ day|day }}.

{% if has_portfolio %}
Valeur de votre portefeuille : {{ total_value|eur }}
Variation du jour : {{ day_change|eur }} ({{ day_change_pct|pct }})

{% endif %}
{% if gainers %}
Plus fortes hausses de vos favoris :
{% for item in gainers %}
- {{ item.name }} : {{ item.change_pct|pct }}
{% endfor %}

{% endif %}
{% if losers %}
Plus fortes baisses de vos favoris :
{% for item in losers %}
- {{ item.name }} : {{ item.change_pct|pct }}
{% endfor %}

{% endif %}
{% include "_footer.txt" %}
```

`weekly_recap.html`
```html
{% extends "_layout.html" %}
{% block body %}
<p>Voici votre récap de la semaine qui se termine le {{ week_end|day }}.</p>
{% if has_portfolio %}
<p>Valeur de votre portefeuille : <strong>{{ total_value|eur }}</strong><br>Sur les 5 dernières séances : <strong>{{ week_change|eur }}</strong> ({{ week_change_pct|pct }})</p>
{% endif %}
{% if entered or left %}
<p style="margin-bottom:4px"><strong>Top 10 des actions éligibles</strong></p>
<ul style="margin-top:0">
{% for item in entered %}
  <li>Entrée : <a href="{{ base_url }}/titres/{{ item.security_id }}" style="color:#4f46e5">{{ item.name }}</a></li>
{% endfor %}
{% for item in left %}
  <li>Sortie : <a href="{{ base_url }}/titres/{{ item.security_id }}" style="color:#4f46e5">{{ item.name }}</a></li>
{% endfor %}
</ul>
{% else %}
<p>Le top 10 n'a pas changé cette semaine.</p>
{% endif %}
{% if forecasts_checked %}
<p>Prévisions à une semaine vérifiées : {{ forecasts_right }} sur {{ forecasts_checked }} dans le bon sens.</p>
{% endif %}
{% endblock %}
```

`weekly_recap.txt`
```
Bonjour {{ first_name }},

Voici votre récap de la semaine qui se termine le {{ week_end|day }}.

{% if has_portfolio %}
Valeur de votre portefeuille : {{ total_value|eur }}
Sur les 5 dernières séances : {{ week_change|eur }} ({{ week_change_pct|pct }})

{% endif %}
{% if entered or left %}
Top 10 des actions éligibles :
{% for item in entered %}
- Entrée : {{ item.name }}
{% endfor %}
{% for item in left %}
- Sortie : {{ item.name }}
{% endfor %}
{% else %}
Le top 10 n'a pas changé cette semaine.
{% endif %}

{% if forecasts_checked %}
Prévisions à une semaine vérifiées : {{ forecasts_right }} sur {{ forecasts_checked }} dans le bon sens.

{% endif %}
{% include "_footer.txt" %}
```

`order_reminder.html`
```html
{% extends "_layout.html" %}
{% block body %}
<p>En {{ year }}, vous avez passé {{ count }} ordre(s) sur les {{ min_orders }} prévus par vos réglages de frais : il vous en manque <strong>{{ remaining }}</strong> d'ici le 31 décembre.</p>
<p>Sans eux, votre banque risque de prélever environ <strong>{{ penalty_fee|eur }}</strong> de frais.</p>
<p><a href="{{ base_url }}/portefeuille" style="display:inline-block;background:#4f46e5;color:#ffffff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600">Voir mon portefeuille</a></p>
{% endblock %}
```

`order_reminder.txt`
```
Bonjour {{ first_name }},

En {{ year }}, vous avez passé {{ count }} ordre(s) sur les {{ min_orders }} prévus par vos réglages de frais : il vous en manque {{ remaining }} d'ici le 31 décembre.

Sans eux, votre banque risque de prélever environ {{ penalty_fee|eur }} de frais.

Voir mon portefeuille : {{ base_url }}/portefeuille

{% include "_footer.txt" %}
```

`score_change.html`
```html
{% extends "_layout.html" %}
{% block body %}
<p>Le score de certains de vos favoris a changé après la séance :</p>
<ul>
{% for item in items %}
  <li><a href="{{ base_url }}/titres/{{ item.security_id }}" style="color:#4f46e5">{{ item.name }}</a> : {% if item.change == "entered" %}entre dans le top 10{% elif item.change == "left" %}sort du top 10{% elif item.change == "up" %}gagne {{ item.after - item.before }} points{% else %}perd {{ item.before - item.after }} points{% endif %} ({{ item.before }} → {{ item.after }})</li>
{% endfor %}
</ul>
{% endblock %}
```

`score_change.txt`
```
Bonjour {{ first_name }},

Le score de certains de vos favoris a changé après la séance :

{% for item in items %}
- {{ item.name }} : {% if item.change == "entered" %}entre dans le top 10{% elif item.change == "left" %}sort du top 10{% elif item.change == "up" %}gagne {{ item.after - item.before }} points{% else %}perd {{ item.before - item.after }} points{% endif %} ({{ item.before }} → {{ item.after }})
{% endfor %}

{% include "_footer.txt" %}
```

`backend/app/services/notifications/send.py` :

```python
"""Envoi d'une notification N1 à N6 : lien de désinscription, en-têtes « un clic », file d'envoi."""
import logging
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User
from app.services.mail.outbox import enqueue
from app.services.notifications.unsubscribe import make_token

logger = logging.getLogger(__name__)


def notifications_ready() -> bool:
    """Sans APP_SECRET, pas de lien de désinscription possible : aucune notification ne part."""
    if get_settings().app_secret:
        return True
    logger.warning("APP_SECRET vide : les notifications ne sont pas envoyées.")
    return False


def notify(db: Session, user: User, kind: str, context: dict, *, dedupe_key: str) -> int | None:
    """Met la notification en file (pas de commit). None si `dedupe_key` a déjà servi."""
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    query = urlencode({"jeton": make_token(user.id, settings.app_secret), "type": kind})
    headers = {"List-Unsubscribe": f"<{base}/api/unsubscribe?{query}>",
               "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    context = {**context, "first_name": user.first_name, "manage_url": f"{base}/reglages#notifications",
               "unsubscribe_url": f"{base}/desinscription?{query}"}
    return enqueue(db, kind, to=user.email, user_id=user.id, context=context, dedupe_key=dedupe_key, headers=headers)
```

- [ ] **Step 4: Vérifier** — `pytest -q tests/test_mail_render.py tests/test_notification_mails.py`, puis `pytest -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: notification mail templates with unsubscribe footer and one-click headers"
```

---

### Task 4: Désinscription en un clic

**Files:**
- Create: `backend/app/api/routes/unsubscribe.py`, `backend/tests/test_api_unsubscribe.py`
- Modify: `backend/app/main.py`, `backend/app/schemas/notifications.py` (`UnsubscribeOut`)

**Interfaces:**
- Consumes: Task 1 (`read_token`, `save_prefs`, `KINDS`), Task 3 (`notify`).
- Produces: `GET /api/unsubscribe?jeton=…&type=…` → `{kind: str | null, label: str | null}` ; `POST /api/unsubscribe?jeton=…&type=…` → `{message}` (sans `type` : toutes les notifications). `404 bad_link` pour un lien faux. Événement de journal `unsubscribed` (`details.kind` : le type, ou `all`). `LABELS: dict[str, str]`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_unsubscribe.py` :

```python
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import SecurityEvent
from app.services.notifications.prefs import KINDS, get_prefs
from app.services.notifications.unsubscribe import make_token
from tests.factories import make_user

pytestmark = pytest.mark.usefixtures("app_secret")


def _token(user):
    return make_token(user.id, get_settings().app_secret)


def test_check_link(anon_client, user):
    response = anon_client.get(f"/api/unsubscribe?jeton={_token(user)}&type=daily_recap")
    assert response.json() == {"kind": "daily_recap", "label": "Récap du soir"}
    assert anon_client.get(f"/api/unsubscribe?jeton={_token(user)}").json() == {"kind": None, "label": None}


def test_one_click_disables_one_notification(anon_client, db, user):
    # Ce que font Gmail ou Outlook : un POST sans cookie ni en-tête Origin (RFC 8058).
    response = anon_client.post(f"/api/unsubscribe?jeton={_token(user)}&type=price_move",
                                content="List-Unsubscribe=One-Click",
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 200
    db.expire_all()
    prefs = get_prefs(db, user.id)
    assert prefs.price_move is False and prefs.price_alert is True
    event = db.scalar(select(SecurityEvent).where(SecurityEvent.kind == "unsubscribed"))
    assert event.user_id == user.id and event.details == {"kind": "price_move"}


def test_without_type_disables_everything(anon_client, db, user):
    assert anon_client.post(f"/api/unsubscribe?jeton={_token(user)}").status_code == 200
    db.expire_all()
    prefs = get_prefs(db, user.id)
    assert not any(getattr(prefs, kind) for kind in KINDS)


def test_forged_or_unknown_links_are_404(anon_client, db, user):
    other = make_user(db, "autre@example.com")
    forged = _token(other).split(".")[0] + "." + _token(user).split(".")[1]  # identifiant d'un autre, signature du mien
    for query in (f"jeton={forged}", "jeton=abc", f"jeton={_token(user)}&type=inconnu"):
        assert anon_client.get(f"/api/unsubscribe?{query}").status_code == 404
        response = anon_client.post(f"/api/unsubscribe?{query}")
        assert response.status_code == 404 and response.json()["detail"]["code"] == "bad_link"
    db.expire_all()
    assert get_prefs(db, other.id).price_move is True
```


- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_api_unsubscribe.py`. Expected: FAIL (404 partout, `test_check_link` en échec sur le JSON).

- [ ] **Step 3: Implémentation**

`schemas/notifications.py` :

```python
class UnsubscribeOut(BaseModel):
    kind: str | None
    label: str | None
```

`backend/app/api/routes/unsubscribe.py` :

```python
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.origin import check_origin
from app.api.routes.auth import client_ip, fail
from app.core.config import get_settings
from app.core.current_user import get_now
from app.core.db import get_db
from app.models import User
from app.schemas.auth import NoticeOut
from app.schemas.notifications import UnsubscribeOut
from app.services.notifications.prefs import KINDS, save_prefs
from app.services.notifications.unsubscribe import read_token
from app.services.security_log import log_event

router = APIRouter(tags=["notifications"])

LABELS = {"price_move": "Forte variation de vos titres", "price_alert": "Alertes de prix",
          "daily_recap": "Récap du soir", "weekly_recap": "Récap de la semaine",
          "order_reminder": "Rappel du compteur d'ordres", "score_change": "Changement de score de vos favoris"}


def _target(db: Session, jeton: str, kind: str | None) -> User:
    user_id = read_token(jeton, get_settings().app_secret)
    user = db.get(User, user_id) if user_id else None
    if user is None or (kind is not None and kind not in KINDS):
        raise fail(404, "bad_link", "Ce lien de désinscription n'est pas valable.")
    return user


@router.get("/unsubscribe", response_model=UnsubscribeOut)
def check_unsubscribe_link(jeton: str = Query(max_length=100), kind: str | None = Query(None, alias="type"),
                           db: Session = Depends(get_db)) -> UnsubscribeOut:
    _target(db, jeton, kind)
    return UnsubscribeOut(kind=kind, label=LABELS.get(kind) if kind else None)


@router.post("/unsubscribe", response_model=NoticeOut, dependencies=[Depends(check_origin)])
def unsubscribe(request: Request, jeton: str = Query(max_length=100), kind: str | None = Query(None, alias="type"),
                db: Session = Depends(get_db), now=Depends(get_now)) -> NoticeOut:
    """Lien du mail ou clic unique du service de mail (RFC 8058) : pas de session, le jeton signé suffit."""
    user = _target(db, jeton, kind)
    save_prefs(db, user.id, {kind: False} if kind else {k: False for k in KINDS})
    log_event(db, "unsubscribed", now=now, user_id=user.id, ip=client_ip(request), details={"kind": kind or "all"})
    db.commit()
    return NoticeOut(message=f"Vous ne recevrez plus « {LABELS[kind]} »." if kind
                     else "Vous ne recevrez plus aucune notification. Les mails liés à votre compte restent envoyés.")
```

`main.py` : ajouter `unsubscribe` à l'import et au tuple des modules, après `notifications`.

- [ ] **Step 4: Vérifier** — `pytest -q tests/test_api_unsubscribe.py`, puis `pytest -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: one-click unsubscribe with signed links (RFC 8058)"
```

**Fin du Bloc 1 : s'arrêter pour que l'utilisateur compacte.**

---

# Bloc 2 — Déclencheurs N1 à N6 (Tasks 5 à 8)

### Task 5: N2, alertes de prix après chaque mise à jour des cours

**Files:**
- Create: `backend/app/jobs/notifications.py`, `backend/tests/test_notify_price_alerts.py`
- Modify: `backend/app/services/notifications/price_alerts.py` (`check_price_alerts`), `backend/app/jobs/scheduler.py` (`quotes_job`), `backend/app/repositories/scores.py` (`alert_security_ids`), `backend/app/jobs/tiers.py`, `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: Task 1 (`recipients`, `PriceAlert`), Task 2 (`reached`), Task 3 (`notify`, `notifications_ready`).
- Produces:
  - `check_price_alerts(db, now) -> int` (pas de commit) ;
  - `app.jobs.notifications.run_price_alerts(ctx) -> int` ;
  - `app.jobs.scheduler._quietly(ctx, fn)` : lance une tâche de notification et journalise une erreur sans la propager ;
  - `alert_security_ids(session) -> set[int]` (titres ayant une alerte active, rafraîchis en T1).

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_notify_price_alerts.py` :

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.jobs.notifications import run_price_alerts
from app.jobs.tiers import tier_tickers
from app.models import EmailLog, PriceAlert
from app.services.notifications.prefs import save_prefs
from tests.factories import make_quote, make_security

pytestmark = pytest.mark.usefixtures("app_secret")
NOW = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)


def _alert(db, user, security, direction="above", price=105.0):
    alert = PriceAlert(user_id=user.id, security_id=security.id, direction=direction, price=price)
    db.add(alert)
    db.flush()
    return alert


def _mails(db):
    return db.scalars(select(EmailLog).where(EmailLog.kind == "price_alert")).all()


def test_alert_fires_once_and_disarms(db, user, make_ctx):
    security = make_security(db, "MC.PA", name="LVMH")
    make_quote(db, security, 100.0)
    alert = _alert(db, user, security)
    assert run_price_alerts(make_ctx(now=NOW)) == 0
    make_quote(db, security, 106.0)
    assert run_price_alerts(make_ctx(now=NOW)) == 1
    assert run_price_alerts(make_ctx(now=NOW)) == 0
    db.refresh(alert)
    assert alert.active is False and alert.triggered_at == NOW
    [mail] = _mails(db)
    assert mail.recipient == user.email and "LVMH" in mail.subject and "106,00 €" in mail.text
    assert "List-Unsubscribe" in mail.headers


def test_below_alert(db, user, make_ctx):
    security = make_security(db, "MC.PA")
    make_quote(db, security, 94.0)
    _alert(db, user, security, direction="below", price=95.0)
    assert run_price_alerts(make_ctx(now=NOW)) == 1


def test_alert_ignored_while_price_alerts_are_off(db, user, make_ctx):
    security = make_security(db, "MC.PA")
    make_quote(db, security, 106.0)
    alert = _alert(db, user, security)
    save_prefs(db, user.id, {"price_alert": False})
    assert run_price_alerts(make_ctx(now=NOW)) == 0
    db.refresh(alert)
    assert alert.active is True  # suspendue, pas consommée (Ruling 3)


def test_foreign_currency_alert_keeps_its_currency(db, user, make_ctx):
    security = make_security(db, "EQNR.OL", name="Equinor", market="Oslo Børs")
    make_quote(db, security, 301.5)
    _alert(db, user, security, price=300.0)
    run_price_alerts(make_ctx(now=NOW))
    [mail] = _mails(db)
    assert "301,50 NOK" in mail.text and "€" not in mail.text.split("--")[0]


def test_no_secret_nothing_is_consumed(db, user, make_ctx, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "app_secret", "")
    security = make_security(db, "MC.PA")
    make_quote(db, security, 106.0)
    alert = _alert(db, user, security)
    assert run_price_alerts(make_ctx(now=NOW)) == 0
    db.refresh(alert)
    assert alert.active is True


def test_alerted_security_is_refreshed_every_minute(db, user):
    security = make_security(db, "ALO.PA")
    _alert(db, user, security)
    assert "ALO.PA" in tier_tickers(db, 1, 10)
```

`backend/tests/test_scheduler.py`, ajouter (avec `import app.jobs.scheduler as scheduler_module`, `from zoneinfo import ZoneInfo` si absents) :

```python
def test_quotes_job_checks_price_alerts(make_ctx, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler_module, "_refresh_tier", lambda ctx, tier: None)
    monkeypatch.setattr(scheduler_module, "_refresh_scores", lambda ctx: None)
    monkeypatch.setattr(scheduler_module, "run_price_alerts", lambda ctx: calls.append(ctx) or 0)
    scheduler_module.quotes_job(make_ctx(now=datetime(2026, 9, 29, 10, 0, tzinfo=ZoneInfo("Europe/Paris"))), 1)
    assert len(calls) == 1
```

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_notify_price_alerts.py tests/test_scheduler.py`. Expected: FAIL (`ModuleNotFoundError: app.jobs.notifications`).

- [ ] **Step 3: Implémentation**

`price_alerts.py`, ajouter les imports `from datetime import datetime`, `Security` à l'import `from app.models import …`, `from app.services.fx import currency_for_market`, `from app.services.notifications.prefs import recipients`, `from app.services.notifications.send import notify`, puis :

```python
def check_price_alerts(db: Session, now: datetime) -> int:
    """N2 : chaque alerte active dont le seuil est franchi part une fois, puis se désactive (pas de commit)."""
    enabled: dict = {user.id: user for user, _ in recipients(db, "price_alert")}
    rows = db.execute(
        select(PriceAlert, SecurityQuote.price, Security)
        .join(SecurityQuote, SecurityQuote.security_id == PriceAlert.security_id)
        .join(Security, Security.id == PriceAlert.security_id)
        .where(PriceAlert.active.is_(True))
        .with_for_update(of=PriceAlert, skip_locked=True)
    ).all()
    sent = 0
    for alert, price, security in rows:
        user = enabled.get(alert.user_id)
        if user is None or not reached(alert.direction, alert.price, price):
            continue
        alert.active, alert.triggered_at = False, now
        notify(db, user, "price_alert",
               {"security_id": security.id, "name": security.name, "direction": alert.direction, "target": alert.price,
                "price": price, "currency": currency_for_market(security.market)},
               dedupe_key=f"price_alert:{alert.id}:{int(now.timestamp())}")
        sent += 1
    db.flush()
    return sent
```

`backend/app/jobs/notifications.py` :

```python
"""Tâches du worker qui envoient les notifications N1 à N6 (spec 5.1)."""
from app.jobs.context import JobContext
from app.services.notifications.price_alerts import check_price_alerts
from app.services.notifications.send import notifications_ready


def run_price_alerts(ctx: JobContext) -> int:
    if not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = check_price_alerts(db, ctx.now())
        db.commit()
    return sent
```

`scheduler.py` :
- `from app.jobs.notifications import run_price_alerts` ;
- sous `_refresh_scores`, ajouter :

```python
def _quietly(ctx: JobContext, fn) -> None:
    """Notifications : une panne est journalisée, sans bloquer la tâche qui les déclenche."""
    try:
        fn(ctx)
    except Exception:
        logging.getLogger(__name__).exception("Échec d'une tâche de notification (%s)", fn.__name__)
```

- `quotes_job` devient :

```python
def quotes_job(ctx: JobContext, tier: int) -> None:
    if is_market_open(ctx.now()):
        _refresh_tier(ctx, tier)
        _quietly(ctx, run_price_alerts)  # N2 : après chaque mise à jour des cours
        if tier == 2:
            _refresh_scores(ctx)
```

`repositories/scores.py` : importer `PriceAlert` et ajouter :

```python
def alert_security_ids(session: Session) -> set[int]:
    return set(session.scalars(select(PriceAlert.security_id).where(PriceAlert.active.is_(True))))
```

`jobs/tiers.py` : importer `alert_security_ids` et l'ajouter à l'union `priority_ids` ; docstring : « T1 : indices, favoris, titres détenus, titres avec une alerte de prix et top 10. »

- [ ] **Step 4: Vérifier** — mêmes tests, puis `pytest -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: price alerts (N2) checked after each quote refresh, alerted securities in tier 1"
```

---

### Task 6: N1, forte variation d'un favori ou d'une position

**Files:**
- Create: `backend/app/services/notifications/moves.py`, `backend/tests/test_notify_price_moves.py`
- Modify: `backend/app/jobs/notifications.py` (`run_price_moves`), `backend/app/jobs/scheduler.py` (tâche `price_moves` toutes les 15 min), `backend/tests/test_scheduler.py` (ensemble des tâches)

**Interfaces:**
- Consumes: Task 1 (`recipients`, `MoveNotice`, `make_quote`), Task 3 (`notify`).
- Produces: `followed_ids(db, user_id) -> set[int]` (favoris + positions ouvertes) ; `notify_price_moves(db, now) -> int` ; `run_price_moves(ctx) -> int` (rien hors séance) ; tâche planifiée `price_moves`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_notify_price_moves.py` :

```python
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.jobs.notifications import run_price_moves
from app.models import EmailLog, Favorite, MoveNotice, Order
from app.services.notifications.moves import notify_price_moves
from app.services.notifications.prefs import save_prefs
from tests.factories import make_quote, make_security

pytestmark = pytest.mark.usefixtures("app_secret")
OPEN = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)  # 11 h 30 à Paris, jeudi


def _fav(db, user, security):
    db.add(Favorite(user_id=user.id, security_id=security.id))
    db.flush()


def _mails(db):
    return db.scalars(select(EmailLog).where(EmailLog.kind == "price_move")).all()


def test_big_move_of_a_favorite_is_mailed(db, user):
    lvmh = make_security(db, "MC.PA", name="LVMH")
    kering = make_security(db, "KER.PA", name="Kering")
    calm = make_security(db, "OR.PA", name="L'Oréal")
    for security, change in ((lvmh, 6.2), (kering, -7.5), (calm, 1.0)):
        _fav(db, user, security)
        make_quote(db, security, 100.0, change_pct=change, as_of=OPEN)
    assert notify_price_moves(db, OPEN) == 1
    [mail] = _mails(db)
    assert "Kering" in mail.text and "LVMH" in mail.text and "L'Oréal" not in mail.text
    assert mail.text.index("Kering") < mail.text.index("LVMH")  # la plus forte variation d'abord


def test_same_title_is_signalled_once_a_day(db, user):
    lvmh = make_security(db, "MC.PA")
    _fav(db, user, lvmh)
    make_quote(db, lvmh, 100.0, change_pct=6.0, as_of=OPEN)
    notify_price_moves(db, OPEN)
    make_quote(db, lvmh, 100.0, change_pct=8.0, as_of=OPEN.replace(hour=12))
    assert notify_price_moves(db, OPEN.replace(hour=12)) == 0
    assert len(_mails(db)) == 1
    assert db.scalar(select(MoveNotice.day)) == date(2026, 10, 1)


def test_threshold_is_personal(db, user):
    lvmh = make_security(db, "MC.PA")
    _fav(db, user, lvmh)
    make_quote(db, lvmh, 100.0, change_pct=6.0, as_of=OPEN)
    save_prefs(db, user.id, {"move_threshold_pct": 10.0})
    assert notify_price_moves(db, OPEN) == 0


def test_open_positions_count_sold_out_ones_do_not(db, user):
    held = make_security(db, "AI.PA", name="Air Liquide")
    sold = make_security(db, "SAN.PA", name="Sanofi")
    db.add_all([
        Order(user_id=user.id, security_id=held.id, trade_date=date(2026, 9, 1), side="buy", quantity=2, unit_price=10, fee=1),
        Order(user_id=user.id, security_id=sold.id, trade_date=date(2026, 9, 1), side="buy", quantity=2, unit_price=10, fee=1),
        Order(user_id=user.id, security_id=sold.id, trade_date=date(2026, 9, 2), side="sell", quantity=2, unit_price=11, fee=1),
    ])
    db.flush()
    make_quote(db, held, 100.0, change_pct=-5.5, as_of=OPEN)
    make_quote(db, sold, 100.0, change_pct=-9.0, as_of=OPEN)
    notify_price_moves(db, OPEN)
    [mail] = _mails(db)
    assert "Air Liquide" in mail.text and "Sanofi" not in mail.text


def test_yesterdays_quote_is_ignored(db, user):
    lvmh = make_security(db, "MC.PA")
    _fav(db, user, lvmh)
    make_quote(db, lvmh, 100.0, change_pct=6.0, as_of=datetime(2026, 9, 30, 15, 0, tzinfo=UTC))
    assert notify_price_moves(db, OPEN) == 0


def test_job_waits_for_the_session(db, user, make_ctx):
    lvmh = make_security(db, "MC.PA")
    _fav(db, user, lvmh)
    make_quote(db, lvmh, 100.0, change_pct=6.0, as_of=OPEN)
    assert run_price_moves(make_ctx(now=datetime(2026, 10, 1, 19, 0, tzinfo=UTC))) == 0  # 21 h à Paris
    assert run_price_moves(make_ctx(now=OPEN)) == 1
```

`test_scheduler.py`, `test_build_scheduler_registers_jobs` : ajouter `"price_moves"` à l'ensemble attendu.

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_notify_price_moves.py tests/test_scheduler.py`. Expected: FAIL (`ModuleNotFoundError: …moves`).

- [ ] **Step 3: Implémentation**

`backend/app/services/notifications/moves.py` :

```python
"""N1 : forte variation d'un favori ou d'une position, au plus une fois par titre et par jour. Pas de commit ici."""
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Favorite, MoveNotice, Security, SecurityQuote
from app.repositories.orders import order_lines
from app.services.fx import currency_for_market
from app.services.market_calendar import PARIS
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify
from app.services.portfolio import compute_positions


def followed_ids(db: Session, user_id: uuid.UUID) -> set[int]:
    favorites = set(db.scalars(select(Favorite.security_id).where(Favorite.user_id == user_id)))
    held = {sid for sid, p in compute_positions(order_lines(db, user_id)).items() if p.quantity}
    return favorites | held


def notify_price_moves(db: Session, now: datetime) -> int:
    today = now.astimezone(PARIS).date()
    sent = 0
    for user, prefs in recipients(db, "price_move"):
        already = set(db.scalars(select(MoveNotice.security_id).where(MoveNotice.user_id == user.id,
                                                                      MoveNotice.day == today)))
        ids = followed_ids(db, user.id) - already
        if not ids:
            continue
        rows = db.execute(
            select(Security, SecurityQuote).join(SecurityQuote, SecurityQuote.security_id == Security.id)
            .where(Security.id.in_(ids), SecurityQuote.change_pct.is_not(None),
                   func.abs(SecurityQuote.change_pct) >= prefs.move_threshold_pct)
        ).all()
        moves = [(s, q) for s, q in rows if q.as_of.astimezone(PARIS).date() == today]  # cours du jour seulement
        if not moves:
            continue
        items = sorted(({"security_id": s.id, "name": s.name, "change_pct": q.change_pct, "price": q.price,
                         "currency": currency_for_market(s.market)} for s, q in moves),
                       key=lambda item: -abs(item["change_pct"]))
        notify(db, user, "price_move", {"threshold": prefs.move_threshold_pct, "items": items},
               dedupe_key=f"price_move:{user.id}:{now.astimezone(PARIS):%Y%m%d%H%M}")
        db.add_all(MoveNotice(user_id=user.id, security_id=s.id, day=today) for s, _ in moves)
        db.flush()
        sent += 1
    return sent
```

`jobs/notifications.py` : importer `is_market_open` (`app.services.market_calendar`) et `notify_price_moves`, puis :

```python
def run_price_moves(ctx: JobContext) -> int:
    """N1, toutes les 15 min en séance."""
    if not is_market_open(ctx.now()) or not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = notify_price_moves(db, ctx.now())
        db.commit()
    return sent
```

`scheduler.py` : importer `run_price_moves` ; ajouter

```python
def price_moves_job(ctx: JobContext) -> None:
    _quietly(ctx, run_price_moves)
```

et dans `build_scheduler`, après la boucle des cours :

```python
    scheduler.add_job(price_moves_job, IntervalTrigger(minutes=15, timezone=tz), args=[ctx], id="price_moves", **common)
```

- [ ] **Step 4: Vérifier** — mêmes tests, puis `pytest -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: big move mails (N1) every 15 minutes in session, once per title and day"
```

---

### Task 7: Valorisation partagée, N3 récap du soir et N5 rappel du compteur d'ordres

**Files:**
- Create: `backend/app/services/portfolio_value.py`, `backend/app/services/notifications/recaps.py`, `backend/app/services/notifications/reminders.py`, `backend/tests/test_notify_recaps.py`
- Modify: `backend/app/api/routes/portfolio.py` (utilise `value_portfolio`), `backend/app/jobs/notifications.py`, `backend/app/jobs/scheduler.py`, `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: Task 3 (`notify`, contextes `daily_recap` et `order_reminder`), Task 5 (`_quietly`).
- Produces:
  - `portfolio_value.eur_rate(security) -> float`, `last_close(db, security_id) -> float | None` ;
  - `ValuedPosition(position, security, quote, price, value)` ;
  - `PortfolioValue(positions, total, invested, day_change, realized)` avec la propriété `day_change_pct` ;
  - `value_portfolio(db, user_id, today) -> PortfolioValue` ;
  - `favorite_movers(db, user_id, today, n=3) -> tuple[list[dict], list[dict]]` ;
  - `send_daily_recaps(db, now) -> int`, `send_order_reminders(db, now) -> int` ;
  - `run_daily_recaps(ctx)`, `run_order_reminders(ctx)` ; tâches planifiées `daily_recap` (lun-ven 18 h 45) et `order_reminders` (1er octobre, novembre, décembre à 9 h).

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_notify_recaps.py` :

```python
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.models import EmailLog, Favorite, Order
from app.services.notifications.prefs import save_prefs
from app.services.notifications.recaps import send_daily_recaps
from app.services.notifications.reminders import send_order_reminders
from app.services.portfolio_value import value_portfolio
from tests.factories import make_quote, make_security, make_user

pytestmark = pytest.mark.usefixtures("app_secret")
EVENING = datetime(2026, 10, 1, 16, 45, tzinfo=UTC)  # jeudi 18 h 45 à Paris


def _buy(db, user, security, quantity=10, price=100.0, day=date(2026, 9, 1)):
    db.add(Order(user_id=user.id, security_id=security.id, trade_date=day, side="buy", quantity=quantity,
                 unit_price=price, fee=1.0))
    db.flush()


def _mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind)).all()


def test_value_portfolio_totals(db, user):
    lvmh = make_security(db, "MC.PA")
    _buy(db, user, lvmh)
    make_quote(db, lvmh, 110.0, previous_close=108.0, change_pct=1.85, as_of=EVENING)
    value = value_portfolio(db, user.id, date(2026, 10, 1))
    assert (value.total, value.invested, value.day_change) == (1100.0, 1001.0, 20.0)
    assert value.day_change_pct == round(20 / 1080 * 100, 2)


def test_daily_recap_with_portfolio_and_favorite_movers(db, user):
    save_prefs(db, user.id, {"daily_recap": True})
    lvmh = make_security(db, "MC.PA", name="LVMH")
    kering = make_security(db, "KER.PA", name="Kering")
    _buy(db, user, lvmh)
    make_quote(db, lvmh, 110.0, previous_close=108.0, change_pct=1.85, as_of=EVENING)
    db.add(Favorite(user_id=user.id, security_id=kering.id))
    make_quote(db, kering, 300.0, change_pct=-3.4, as_of=EVENING)
    assert send_daily_recaps(db, EVENING) == 1
    [mail] = _mails(db, "daily_recap")
    assert "1 100,00 €" in mail.text and "Kering : -3,40 %" in mail.text and "01/10/2026" in mail.text


def test_daily_recap_once_per_day(db, user):
    save_prefs(db, user.id, {"daily_recap": True})
    lvmh = make_security(db, "MC.PA")
    _buy(db, user, lvmh)
    make_quote(db, lvmh, 110.0, previous_close=108.0, change_pct=1.85, as_of=EVENING)
    send_daily_recaps(db, EVENING)
    send_daily_recaps(db, EVENING)
    assert len(_mails(db, "daily_recap")) == 1


def test_no_daily_recap_on_a_holiday_or_when_off_or_empty(db, user):
    lvmh = make_security(db, "MC.PA")
    _buy(db, user, lvmh)
    make_quote(db, lvmh, 110.0, change_pct=1.0, as_of=EVENING)
    assert send_daily_recaps(db, EVENING) == 0  # désactivé par défaut
    save_prefs(db, user.id, {"daily_recap": True})
    assert send_daily_recaps(db, datetime(2026, 12, 25, 17, 45, tzinfo=UTC)) == 0  # Noël : pas de séance
    empty = make_user(db, "vide@example.com")  # ni position ni favori : rien à raconter
    save_prefs(db, empty.id, {"daily_recap": True})
    assert send_daily_recaps(db, EVENING) == 1  # seulement `user`


def test_order_reminder_when_orders_are_missing(db, user):
    lvmh = make_security(db, "MC.PA")
    for day in (date(2026, 2, 1), date(2026, 5, 1), date(2026, 8, 1)):
        _buy(db, user, lvmh, quantity=1, day=day)
    first_oct = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
    assert send_order_reminders(db, first_oct) == 1
    assert send_order_reminders(db, first_oct) == 0  # une fois par mois
    [mail] = _mails(db, "order_reminder")
    assert "il vous manque 9" in mail.subject + mail.text and "96,00 €" in mail.text


def test_no_order_reminder_without_orders_or_when_on_track(db, user):
    first_oct = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
    assert send_order_reminders(db, first_oct) == 0  # aucun ordre saisi (Ruling 4)
    lvmh = make_security(db, "MC.PA")
    for day in range(1, 13):  # 12 ordres sur 12 : objectif atteint
        _buy(db, user, lvmh, quantity=1, day=date(2026, 9, day))
    assert send_order_reminders(db, first_oct) == 0
```

`test_scheduler.py`, ensemble attendu : ajouter `"daily_recap", "order_reminders"`.

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_notify_recaps.py tests/test_api_portfolio.py tests/test_scheduler.py`. Expected: FAIL (`ModuleNotFoundError`), `test_api_portfolio.py` passe encore.

- [ ] **Step 3: Implémentation**

`backend/app/services/portfolio_value.py` (déplace la valorisation du routeur, à l'identique) :

```python
"""Valeur du portefeuille d'un membre au dernier cours connu : page Portefeuille et récaps par mail."""
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPrice, Security, SecurityQuote
from app.repositories.orders import order_lines
from app.services.fx import currency_for_market, to_eur
from app.services.portfolio import Position, compute_positions


def eur_rate(security: Security) -> float:
    return to_eur(1.0, currency_for_market(security.market)) or 1.0


def last_close(db: Session, security_id: int) -> float | None:
    return db.scalars(select(DailyPrice.close).where(DailyPrice.security_id == security_id)
                      .order_by(DailyPrice.date.desc()).limit(1)).first()


@dataclass
class ValuedPosition:
    position: Position
    security: Security
    quote: SecurityQuote | None
    price: float | None  # en euros
    value: float


@dataclass
class PortfolioValue:
    positions: list[ValuedPosition]
    total: float
    invested: float
    day_change: float
    realized: float

    @property
    def day_change_pct(self) -> float | None:
        base = self.total - self.day_change
        return round(self.day_change / base * 100, 2) if base else None


def value_portfolio(db: Session, user_id: uuid.UUID, today: date) -> PortfolioValue:
    lines = order_lines(db, user_id)
    positions = compute_positions(lines)
    bought_today: dict[int, tuple[int, float]] = {}  # titres achetés aujourd'hui : (quantité, montant)
    for line in lines:
        if line.side == "buy" and line.trade_date == today:
            qty, amount = bought_today.get(line.security_id, (0, 0.0))
            bought_today[line.security_id] = (qty + line.quantity, amount + line.quantity * line.unit_price)
    open_positions = [p for p in positions.values() if p.quantity]
    valued: list[ValuedPosition] = []
    day_change = 0.0
    for p in open_positions:
        security = db.get(Security, p.security_id)
        quote = db.get(SecurityQuote, p.security_id)
        rate = eur_rate(security)
        native = quote.price if quote else last_close(db, p.security_id)
        price = round(native * rate, 4) if native is not None else None
        value = round(p.quantity * price, 2) if price is not None else round(p.cost, 2)
        if quote and quote.previous_close:
            # Les titres achetés aujourd'hui varient depuis leur prix d'achat, pas depuis la clôture de la veille.
            today_qty, today_amount = bought_today.get(p.security_id, (0, 0.0))
            kept_today = min(today_qty, p.quantity)
            average_buy = today_amount / today_qty if today_qty else 0.0
            day_change += (p.quantity - kept_today) * (quote.price - quote.previous_close) * rate
            day_change += kept_today * (quote.price * rate - average_buy)
        valued.append(ValuedPosition(position=p, security=security, quote=quote, price=price, value=value))
    return PortfolioValue(
        positions=valued, total=round(sum(v.value for v in valued), 2),
        invested=round(sum(p.cost for p in open_positions), 2), day_change=round(day_change, 2),
        realized=round(sum(p.realized_gain for p in positions.values()), 2),
    )
```

`backend/app/api/routes/portfolio.py` : supprimer `_rate`, `_last_close` et le calcul déplacé ; importer `from app.services.portfolio_value import eur_rate, value_portfolio` ; retirer les imports devenus inutiles (`DailyPrice`, `compute_positions`) ; `get_portfolio` devient :

```python
@router.get("/portfolio", response_model=PortfolioOut)
def get_portfolio(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> PortfolioOut:
    valued = value_portfolio(db, user.id, paris_today())
    rows: list[PositionOut] = []
    for v in valued.positions:
        p, security, quote = v.position, v.security, v.quote
        gain = round(v.value - p.cost, 2)
        rows.append(PositionOut(
            security_id=security.id, symbol=security.symbol, name=security.name, sector=security.sector,
            kind=security.kind, quantity=p.quantity, avg_cost=round(p.avg_cost, 4), price=v.price,
            change_pct=quote.change_pct if quote else None, value=v.value, gain=gain, gain_pct=_pct(gain, p.cost),
            weight=0.0,
        ))
    total, invested, day_change = valued.total, valued.invested, valued.day_change
    sectors: dict[str, float] = {}
    for r in rows:
        r.weight = round(r.value / total, 4) if total else 0.0
        key = "ETF" if r.kind == "etf" else (r.sector or "Autres")
        sectors[key] = sectors.get(key, 0.0) + r.value
    rows.sort(key=lambda r: -r.value)
    return PortfolioOut(
        total_value=total, invested=invested, gain=round(total - invested, 2), gain_pct=_pct(total - invested, invested),
        day_change=day_change, day_change_pct=_pct(day_change, total - day_change), realized_gain=valued.realized,
        positions=rows,
        sectors=[SectorOut(sector=k, value=round(v, 2), weight=round(v / total, 4) if total else 0.0)
                 for k, v in sorted(sectors.items(), key=lambda kv: -kv[1])],
        counter=counter_for(db, user.id),
    )
```

et, dans `get_portfolio_history`, `rates[sid] = eur_rate(db.get(Security, sid))`.

`backend/app/services/notifications/recaps.py` :

```python
"""N3 récap du soir (et N4, Task 8). Pas de commit ici."""
import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Favorite, Security, SecurityQuote
from app.services.market_calendar import PARIS, is_trading_day
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify
from app.services.portfolio_value import value_portfolio


def favorite_movers(db: Session, user_id: uuid.UUID, today: date, n: int = 3) -> tuple[list[dict], list[dict]]:
    """Plus fortes hausses et baisses du jour parmi les favoris."""
    rows = db.execute(
        select(Security, SecurityQuote).join(Favorite, Favorite.security_id == Security.id)
        .join(SecurityQuote, SecurityQuote.security_id == Security.id)
        .where(Favorite.user_id == user_id, SecurityQuote.change_pct.is_not(None))
    ).all()
    items = sorted(({"security_id": s.id, "name": s.name, "change_pct": q.change_pct}
                    for s, q in rows if q.as_of.astimezone(PARIS).date() == today), key=lambda i: i["change_pct"])
    gainers = [i for i in reversed(items) if i["change_pct"] > 0][:n]
    losers = [i for i in items if i["change_pct"] < 0][:n]
    return gainers, losers


def send_daily_recaps(db: Session, now: datetime) -> int:
    today = now.astimezone(PARIS).date()
    if not is_trading_day(today):
        return 0
    sent = 0
    for user, _ in recipients(db, "daily_recap"):
        valued = value_portfolio(db, user.id, today)
        gainers, losers = favorite_movers(db, user.id, today)
        if not valued.positions and not gainers and not losers:
            continue
        if notify(db, user, "daily_recap",
                  {"day": today, "has_portfolio": bool(valued.positions), "total_value": valued.total,
                   "day_change": valued.day_change, "day_change_pct": valued.day_change_pct,
                   "gainers": gainers, "losers": losers},
                  dedupe_key=f"daily_recap:{user.id}:{today}") is not None:
            sent += 1
    return sent
```

`backend/app/services/notifications/reminders.py` :

```python
"""N5 : rappel du compteur d'ordres, les 1er octobre, novembre et décembre. Pas de commit ici."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.orders import order_lines
from app.repositories.user_settings import get_user_settings
from app.services.market_calendar import PARIS
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify
from app.services.portfolio import order_counter


def send_order_reminders(db: Session, now: datetime) -> int:
    today = now.astimezone(PARIS).date()
    sent = 0
    for user, _ in recipients(db, "order_reminder"):
        dates = [line.trade_date for line in order_lines(db, user.id)]
        if not dates:  # aucun portefeuille suivi ici (Ruling 4)
            continue
        settings = get_user_settings(db, user.id)
        counter = order_counter(dates, today, settings.min_orders_per_year)
        if counter.remaining == 0:
            continue
        if notify(db, user, "order_reminder",
                  {"year": counter.year, "count": counter.count, "min_orders": counter.min_orders,
                   "remaining": counter.remaining, "penalty_fee": settings.penalty_fee},
                  dedupe_key=f"order_reminder:{user.id}:{today:%Y-%m}") is not None:
            sent += 1
    return sent
```

`jobs/notifications.py` : importer `send_daily_recaps`, `send_order_reminders`, puis :

```python
def run_daily_recaps(ctx: JobContext) -> int:
    if not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = send_daily_recaps(db, ctx.now())
        db.commit()
    return sent


def run_order_reminders(ctx: JobContext) -> int:
    if not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = send_order_reminders(db, ctx.now())
        db.commit()
    return sent
```

`scheduler.py` : importer les deux fonctions ; ajouter

```python
def daily_recap_job(ctx: JobContext) -> None:
    _quietly(ctx, run_daily_recaps)


def order_reminders_job(ctx: JobContext) -> None:
    _quietly(ctx, run_order_reminders)
```

et dans `build_scheduler` :

```python
    scheduler.add_job(daily_recap_job, CronTrigger(day_of_week="mon-fri", hour=18, minute=45, timezone=tz),
                      args=[ctx], id="daily_recap", **daily)
    scheduler.add_job(order_reminders_job, CronTrigger(month="10-12", day=1, hour=9, minute=0, timezone=tz),
                      args=[ctx], id="order_reminders", **daily)
```

- [ ] **Step 4: Vérifier** — `pytest -q tests/test_notify_recaps.py tests/test_api_portfolio.py tests/test_scheduler.py`, puis `pytest -q`. Expected: PASS (la page Portefeuille renvoie exactement les mêmes chiffres).

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: evening recap (N3) and order counter reminder (N5); portfolio valuation shared with the API"
```

---

### Task 8: Photos des scores, N6 changement de score et N4 récap de la semaine

**Files:**
- Create: `backend/app/services/notifications/scores.py`, `backend/tests/test_notify_scores.py`
- Modify: `backend/app/services/notifications/recaps.py` (`send_weekly_recaps`), `backend/app/jobs/notifications.py`, `backend/app/jobs/scheduler.py` (`evening_job`, tâche `weekly_recap`), `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: Task 1 (`ScoreSnapshot`), Task 7 (`value_portfolio`), `top_security_ids(session, limit)`.
- Produces:
  - `TOP_SIZE = 10`, `BIG_MOVE = 10.0` ;
  - `take_score_snapshot(db, day)` ;
  - `snapshot(db, day) -> dict[int, ScoreSnapshot]` ;
  - `previous_day(db, before: date) -> date | None` (dernière photo strictement avant `before`) ;
  - `score_changes(before, after, ids) -> list[dict]` ;
  - `notify_score_changes(db, day) -> int`, `send_weekly_recaps(db, now) -> int` ;
  - `run_score_notifications(ctx)` (photo puis N6, appelée par `evening_job`), `run_weekly_recaps(ctx)` ; tâche `weekly_recap` (samedi 9 h).

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_notify_scores.py` :

```python
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.models import EmailLog, Favorite, Forecast, Order, ScoreSnapshot, SecurityScore
from app.services.notifications.prefs import save_prefs
from app.services.notifications.recaps import send_weekly_recaps
from app.services.notifications.scores import notify_score_changes, take_score_snapshot
from tests.factories import make_quote, make_score, make_security

pytestmark = pytest.mark.usefixtures("app_secret")
MON, TUE = date(2026, 9, 28), date(2026, 9, 29)


def _mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind)).all()


def _set_total(db, security, total, top=True):
    score = db.get(SecurityScore, security.id)
    score.total, score.eligible_for_top = total, top
    db.flush()


def test_snapshot_keeps_totals_and_top_ranks(db):
    a, b = make_security(db, "A.PA"), make_security(db, "B.PA")
    make_score(db, a, total=80.0)
    make_score(db, b, total=50.0, eligible_for_top=False)
    take_score_snapshot(db, MON)
    take_score_snapshot(db, MON)  # rejouée : remplace, sans doublon
    rows = {r.security_id: r for r in db.scalars(select(ScoreSnapshot).where(ScoreSnapshot.day == MON))}
    assert (rows[a.id].total, rows[a.id].top_rank, rows[b.id].top_rank) == (80.0, 1, None)


def test_favorites_entering_the_top_or_moving_10_points(db, user):
    save_prefs(db, user.id, {"score_change": True})
    entering = make_security(db, "IN.PA", name="Entrant")
    jumping = make_security(db, "UP.PA", name="Bondissant")
    calm = make_security(db, "CALM.PA", name="Calme")
    stranger = make_security(db, "OUT.PA", name="Pas favori")
    make_score(db, entering, total=40.0, eligible_for_top=False)
    make_score(db, jumping, total=30.0, eligible_for_top=False)
    make_score(db, calm, total=60.0, eligible_for_top=False)
    make_score(db, stranger, total=20.0, eligible_for_top=False)
    db.add_all(Favorite(user_id=user.id, security_id=s.id) for s in (entering, jumping, calm))
    take_score_snapshot(db, MON)
    _set_total(db, entering, 70.0, top=True)
    _set_total(db, jumping, 42.0, top=False)
    _set_total(db, calm, 65.0, top=False)
    _set_total(db, stranger, 90.0, top=True)
    take_score_snapshot(db, TUE)
    assert notify_score_changes(db, TUE) == 1
    assert notify_score_changes(db, TUE) == 0  # une fois par jour
    [mail] = _mails(db, "score_change")
    assert "Entrant : entre dans le top 10" in mail.text and "Bondissant : gagne 12 points" in mail.text
    assert "Calme" not in mail.text and "Pas favori" not in mail.text


def test_no_previous_snapshot_no_mail(db, user):
    save_prefs(db, user.id, {"score_change": True})
    a = make_security(db, "A.PA")
    make_score(db, a)
    db.add(Favorite(user_id=user.id, security_id=a.id))
    take_score_snapshot(db, MON)
    assert notify_score_changes(db, MON) == 0


def test_weekly_recap_once_per_week(db, user):
    save_prefs(db, user.id, {"weekly_recap": True})
    old, new = make_security(db, "OLD.PA", name="Sortant"), make_security(db, "NEW.PA", name="Entrant")
    make_score(db, old, total=80.0, perf_1w=2.0)
    make_score(db, new, total=40.0, eligible_for_top=False)
    take_score_snapshot(db, date(2026, 9, 25))
    _set_total(db, old, 30.0, top=False)
    _set_total(db, new, 85.0, top=True)
    take_score_snapshot(db, date(2026, 10, 2))
    db.add(Order(user_id=user.id, security_id=old.id, trade_date=date(2026, 9, 1), side="buy", quantity=10,
                 unit_price=100, fee=1))
    make_quote(db, old, 102.0, as_of=datetime(2026, 10, 2, 15, 35, tzinfo=UTC))
    db.add(Forecast(security_id=new.id, as_of=date(2026, 9, 25), horizon="1w", expected_return=0.02, prob_up=0.6,
                    reliability="medium", signals=[], rank=1, base_close=10.0, actual_return=0.01,
                    resolved_on=date(2026, 10, 2)))
    db.flush()  # (si le modèle Forecast a d'autres colonnes obligatoires, les renseigner)
    saturday = datetime(2026, 10, 3, 7, 0, tzinfo=UTC)
    assert send_weekly_recaps(db, saturday) == 1
    assert send_weekly_recaps(db, saturday) == 0
    [mail] = _mails(db, "weekly_recap")
    assert "Entrée : Entrant" in mail.text and "Sortie : Sortant" in mail.text
    assert "1 sur 1 dans le bon sens" in mail.text and "1 020,00 €" in mail.text
```

`test_scheduler.py` : ensemble attendu + `"weekly_recap"` ; et

```python
def test_evening_job_snapshots_scores_then_notifies(make_ctx, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler_module, "run_job", lambda ctx, name, fn: calls.append(name))
    monkeypatch.setattr(scheduler_module, "_refresh_forecasts", lambda ctx: calls.append("forecasts"))
    monkeypatch.setattr(scheduler_module, "run_score_notifications", lambda ctx: calls.append("score_notifications"))
    scheduler_module.evening_job(make_ctx())
    assert calls[-1] == "score_notifications"
```

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_notify_scores.py tests/test_scheduler.py`. Expected: FAIL (`ModuleNotFoundError: …scores`).

- [ ] **Step 3: Implémentation**

`backend/app/services/notifications/scores.py` :

```python
"""Photo des scores chaque soir, et N6 : changement de score d'un favori. Pas de commit ici."""
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Favorite, ScoreSnapshot, Security, SecurityScore
from app.repositories.scores import top_security_ids
from app.services.notifications.prefs import recipients
from app.services.notifications.send import notify

TOP_SIZE = 10
BIG_MOVE = 10.0  # points de score


def take_score_snapshot(db: Session, day: date) -> None:
    db.execute(delete(ScoreSnapshot).where(ScoreSnapshot.day == day))
    ranks = {sid: rank for rank, sid in enumerate(top_security_ids(db, TOP_SIZE), start=1)}
    for sid, total in db.execute(select(SecurityScore.security_id, SecurityScore.total)
                                 .where(SecurityScore.total.is_not(None))):
        db.add(ScoreSnapshot(day=day, security_id=sid, total=total, top_rank=ranks.get(sid)))
    db.flush()


def snapshot(db: Session, day: date) -> dict[int, ScoreSnapshot]:
    return {row.security_id: row for row in db.scalars(select(ScoreSnapshot).where(ScoreSnapshot.day == day))}


def previous_day(db: Session, before: date) -> date | None:
    return db.scalar(select(func.max(ScoreSnapshot.day)).where(ScoreSnapshot.day < before))


def score_changes(before: dict[int, ScoreSnapshot], after: dict[int, ScoreSnapshot], ids: set[int]) -> list[dict]:
    items = []
    for sid in sorted(ids):
        old, new = before.get(sid), after.get(sid)
        if old is None or new is None:
            continue
        if new.top_rank and not old.top_rank:
            change = "entered"
        elif old.top_rank and not new.top_rank:
            change = "left"
        elif abs(new.total - old.total) >= BIG_MOVE:
            change = "up" if new.total > old.total else "down"
        else:
            continue
        items.append({"security_id": sid, "before": round(old.total), "after": round(new.total), "change": change})
    return items


def notify_score_changes(db: Session, day: date) -> int:
    prev = previous_day(db, day)
    if prev is None:
        return 0
    before, after = snapshot(db, prev), snapshot(db, day)
    sent = 0
    for user, _ in recipients(db, "score_change"):
        favorites = set(db.scalars(select(Favorite.security_id).where(Favorite.user_id == user.id)))
        items = score_changes(before, after, favorites)
        if not items:
            continue
        names = dict(db.execute(select(Security.id, Security.name).where(Security.id.in_([i["security_id"] for i in items]))).all())
        for item in items:
            item["name"] = names[item["security_id"]]
        if notify(db, user, "score_change", {"items": items}, dedupe_key=f"score_change:{user.id}:{day}") is not None:
            sent += 1
    return sent
```

`recaps.py`, ajouter les imports `from datetime import timedelta`, `from sqlalchemy import func`, `from app.models import Forecast, SecurityScore`, `from app.services.notifications.scores import previous_day, snapshot`, puis :

```python
def _names(db: Session, ids: set[int]) -> list[dict]:
    rows = db.execute(select(Security.id, Security.name).where(Security.id.in_(ids)).order_by(Security.name)).all()
    return [{"security_id": sid, "name": name} for sid, name in rows]


def send_weekly_recaps(db: Session, now: datetime) -> int:
    """N4, le samedi : performance sur 5 séances, top 10 entrées et sorties, prévisions à une semaine vérifiées."""
    today = now.astimezone(PARIS).date()
    latest = db.scalar(select(func.max(ScoreSnapshot.day)).where(ScoreSnapshot.day <= today))
    start = previous_day(db, latest - timedelta(days=6)) if latest else None
    top_now = {sid for sid, row in snapshot(db, latest).items() if row.top_rank} if latest else set()
    top_before = {sid for sid, row in snapshot(db, start).items() if row.top_rank} if start else top_now
    entered, left = _names(db, top_now - top_before), _names(db, top_before - top_now)
    checked = db.scalars(select(Forecast).where(Forecast.horizon == "1w", Forecast.rank <= 10,
                                                Forecast.actual_return.is_not(None),
                                                Forecast.resolved_on > today - timedelta(days=7))).all()
    right = sum(1 for f in checked if (f.actual_return > 0) == (f.expected_return > 0))
    sent = 0
    for user, _ in recipients(db, "weekly_recap"):
        valued = value_portfolio(db, user.id, today)
        week_change = 0.0
        for v in valued.positions:
            score = db.get(SecurityScore, v.security.id)
            if score is not None and score.perf_1w is not None:
                week_change += v.value * score.perf_1w / (100 + score.perf_1w)  # Ruling 5
        base = valued.total - week_change
        if notify(db, user, "weekly_recap",
                  {"week_end": today, "has_portfolio": bool(valued.positions), "total_value": valued.total,
                   "week_change": round(week_change, 2), "week_change_pct": round(week_change / base * 100, 2) if base else None,
                   "entered": entered, "left": left, "forecasts_checked": len(checked), "forecasts_right": right},
                  dedupe_key=f"weekly_recap:{user.id}:{today:%G-W%V}") is not None:
            sent += 1
    return sent
```

(importer aussi `ScoreSnapshot` depuis `app.models`.)

`jobs/notifications.py` : importer `take_score_snapshot`, `notify_score_changes`, `send_weekly_recaps`, `PARIS`, puis :

```python
def run_score_notifications(ctx: JobContext) -> int:
    """Après le passage du soir : photo des scores (N4, N6), puis N6."""
    day = ctx.now().astimezone(PARIS).date()
    with ctx.session_factory() as db:
        take_score_snapshot(db, day)
        db.commit()
        if not notifications_ready():
            return 0
        sent = notify_score_changes(db, day)
        db.commit()
    return sent


def run_weekly_recaps(ctx: JobContext) -> int:
    if not notifications_ready():
        return 0
    with ctx.session_factory() as db:
        sent = send_weekly_recaps(db, ctx.now())
        db.commit()
    return sent
```

`scheduler.py` : importer les deux ; à la fin du bloc `with HEAVY_JOBS_LOCK:` de `evening_job`, ajouter `_quietly(ctx, run_score_notifications)` ; ajouter

```python
def weekly_recap_job(ctx: JobContext) -> None:
    _quietly(ctx, run_weekly_recaps)
```

et dans `build_scheduler` :

```python
    scheduler.add_job(weekly_recap_job, CronTrigger(day_of_week="sat", hour=9, minute=0, timezone=tz),
                      args=[ctx], id="weekly_recap", **daily)
```

- [ ] **Step 4: Vérifier** — mêmes tests, puis `pytest -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: nightly score snapshots, score change mails (N6) and weekly recap (N4)"
```

**Fin du Bloc 2 : s'arrêter pour que l'utilisateur compacte.**

---

# Bloc 3 — Frontend (Tasks 9 à 11)

Avant la Task 9 : `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --wait api`, puis `cd frontend && npm run gen:api` pour régénérer `src/lib/api/schema.d.ts` avec les routes des Blocs 1 et 2.

### Task 9: Carte « Notifications » dans les Réglages

**Files:**
- Create: `frontend/src/features/settings/NotificationsCard.tsx`, `frontend/src/features/settings/NotificationsCard.test.tsx`
- Modify: `frontend/src/lib/api/client.ts` (types), `frontend/src/features/settings/SettingsPage.tsx`, `frontend/src/lib/api/schema.d.ts` (`npm run gen:api`)

**Interfaces:**
- Consumes: `GET/PUT /api/me/notifications`, `GET /api/me/price-alerts`, `PATCH/DELETE /api/me/price-alerts/{id}` (Task 2).
- Produces: `NotificationsCard` (ancre `id="notifications"`, clé de requête `["price-alerts"]`) ; types `NotificationPrefs = components["schemas"]["NotificationPrefsOut"]`, `PriceAlert = components["schemas"]["PriceAlertOut"]`.

- [ ] **Step 1: Test qui échoue** — `NotificationsCard.test.tsx` :

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { NotificationsCard } from "./NotificationsCard";

afterEach(() => vi.unstubAllGlobals());

const PREFS = { price_move: true, price_alert: true, daily_recap: false, weekly_recap: false, order_reminder: true,
  score_change: false, move_threshold_pct: 5 };
const FIRED = { id: "a1", security_id: 7, symbol: "EQNR", name: "Equinor", currency: "NOK", direction: "above", price: 300,
  current_price: 301.5, active: false, triggered_at: "2026-10-01T08:00:00Z", created_at: "2026-09-30T08:00:00Z" };

function api(alerts: unknown[] = []) {
  return mockFetch((url, init) => {
    if (url === "/api/me/notifications") return { body: init?.method === "PUT" ? JSON.parse(String(init.body)) : PREFS };
    if (url === "/api/me/price-alerts") return { body: alerts };
    return { status: 204, body: null };
  });
}

const sent = (fetchMock: ReturnType<typeof mockFetch>, method: string, url: string) =>
  fetchMock.mock.calls.filter(([u, init]) => String(u) === url && init?.method === method);

test("un interrupteur par mail, enregistré aussitôt", async () => {
  const fetchMock = api();
  renderWithProviders(<NotificationsCard />);
  const recap = await screen.findByRole("switch", { name: /Récap du soir/ });
  expect(recap).not.toBeChecked();
  expect(screen.getByRole("switch", { name: /Forte variation/ })).toBeChecked();
  await userEvent.click(recap);
  await waitFor(() => expect(sent(fetchMock, "PUT", "/api/me/notifications")).toHaveLength(1));
  expect(JSON.parse(String(sent(fetchMock, "PUT", "/api/me/notifications")[0][1]!.body))).toEqual({ ...PREFS, daily_recap: true });
});

test("seuil de forte variation enregistré en quittant le champ", async () => {
  const fetchMock = api();
  renderWithProviders(<NotificationsCard />);
  const field = await screen.findByLabelText("Seuil de forte variation (%)");
  await userEvent.clear(field);
  await userEvent.type(field, "3,5");
  await userEvent.tab();
  await waitFor(() => expect(JSON.parse(String(sent(fetchMock, "PUT", "/api/me/notifications")[0][1]!.body)).move_threshold_pct).toBe(3.5));
});

test("alertes de prix : réarmer ou supprimer", async () => {
  const fetchMock = api([FIRED]);
  renderWithProviders(<NotificationsCard />);
  expect(await screen.findByText(/Au-dessus de 300,00 NOK/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Réarmer l'alerte sur Equinor" }));
  await waitFor(() => expect(sent(fetchMock, "PATCH", "/api/me/price-alerts/a1")).toHaveLength(1));
  await userEvent.click(screen.getByRole("button", { name: "Supprimer l'alerte sur Equinor" }));
  await waitFor(() => expect(sent(fetchMock, "DELETE", "/api/me/price-alerts/a1")).toHaveLength(1));
});

test("sans alerte : explique comment en créer une", async () => {
  api();
  renderWithProviders(<NotificationsCard />);
  expect(await screen.findByText(/Créez-en une depuis la fiche d'un titre/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Vérifier l'échec** — `npx vitest --run src/features/settings/NotificationsCard.test.tsx`. Expected: FAIL (module absent).

- [ ] **Step 3: Implémentation**

`client.ts`, sous `DataExport` :

```ts
export type NotificationPrefs = components["schemas"]["NotificationPrefsOut"];
export type PriceAlert = components["schemas"]["PriceAlertOut"];
```

`NotificationsCard.tsx` :

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, apiSend, type NotificationPrefs, type PriceAlert } from "@/lib/api/client";
import { formatPrice } from "@/lib/format";

type Kind = Exclude<keyof NotificationPrefs, "move_threshold_pct">;

const ITEMS: { key: Kind; label: string; hint: string }[] = [
  { key: "price_move", label: "Forte variation d'un titre suivi",
    hint: "En séance : un mail quand un favori ou une position bouge d'au moins le seuil ci-dessous, une fois par titre et par jour." },
  { key: "price_alert", label: "Alertes de prix", hint: "Quand un titre franchit le seuil choisi sur sa fiche." },
  { key: "daily_recap", label: "Récap du soir",
    hint: "À 18 h 45 les jours de bourse : valeur du portefeuille, variation du jour, hausses et baisses de vos favoris." },
  { key: "weekly_recap", label: "Récap de la semaine",
    hint: "Le samedi à 9 h : performance, entrées et sorties du top 10, prévisions vérifiées." },
  { key: "order_reminder", label: "Rappel du compteur d'ordres",
    hint: "Les 1er octobre, novembre et décembre, s'il vous manque des ordres pour éviter les frais de votre banque." },
  { key: "score_change", label: "Changement de score d'un favori",
    hint: "Après la séance : entrée ou sortie du top 10, ou score qui bouge d'au moins 10 points." },
];

const unit = (currency: string) => (currency === "EUR" ? "€" : currency);
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "");

export function NotificationsCard() {
  const queryClient = useQueryClient();
  const prefs = useQuery({ queryKey: ["notifications"], queryFn: () => apiGet<NotificationPrefs>("/api/me/notifications") });
  const save = useMutation({
    mutationFn: (next: NotificationPrefs) => apiSend("PUT", "/api/me/notifications", next) as Promise<NotificationPrefs>,
    onSuccess: (data) => queryClient.setQueryData(["notifications"], data),
  });
  const data = prefs.data;
  return (
    <Card id="notifications">
      <CardHeader><CardTitle className="text-base">Notifications par mail</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {data && (
          <ul className="divide-y divide-border">
            {ITEMS.map((item) => (
              <li key={item.key} className="flex items-start justify-between gap-4 py-2">
                <label htmlFor={`notif-${item.key}`} className="min-w-0">
                  <span className="block font-medium">{item.label}</span>
                  <span className="block text-xs text-muted-foreground">{item.hint}</span>
                </label>
                <input id={`notif-${item.key}`} type="checkbox" role="switch" className="mt-1 size-4 accent-primary"
                       checked={data[item.key]} disabled={save.isPending}
                       onChange={(e) => save.mutate({ ...data, [item.key]: e.target.checked })} />
              </li>
            ))}
          </ul>
        )}
        {data && (
          <ThresholdField key={data.move_threshold_pct} value={data.move_threshold_pct}
                          onSave={(value) => save.mutate({ ...data, move_threshold_pct: value })} />
        )}
        {save.error && <p role="alert" className="text-sm text-destructive">{save.error.message}</p>}
        <PriceAlertList />
        <p className="text-xs text-muted-foreground">Les mails liés à votre compte (codes, sécurité) sont toujours envoyés.</p>
      </CardContent>
    </Card>
  );
}

function ThresholdField({ value, onSave }: { value: number; onSave: (value: number) => void }) {
  const [text, setText] = useState(String(value).replace(".", ","));
  function commit() {
    const next = Number(text.replace(",", "."));
    if (next >= 1 && next <= 50 && next !== value) onSave(next);
    else setText(String(value).replace(".", ","));
  }
  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor="notif-threshold">Seuil de forte variation (%)</label>
      <Input id="notif-threshold" inputMode="decimal" className="w-20" value={text}
             onChange={(e) => setText(e.target.value)} onBlur={commit} />
    </div>
  );
}

function PriceAlertList() {
  const queryClient = useQueryClient();
  const alerts = useQuery({ queryKey: ["price-alerts"], queryFn: () => apiGet<PriceAlert[]>("/api/me/price-alerts") });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["price-alerts"] });
  const rearm = useMutation({
    mutationFn: (alert: PriceAlert) => apiSend("PATCH", `/api/me/price-alerts/${alert.id}`, { active: true }), onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (alert: PriceAlert) => apiSend("DELETE", `/api/me/price-alerts/${alert.id}`), onSuccess: refresh,
  });
  const list = alerts.data ?? [];
  const error = rearm.error ?? remove.error;
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">Alertes de prix</h3>
      {list.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune alerte. Créez-en une depuis la fiche d'un titre, avec le bouton « Créer une alerte ».</p>
      ) : (
        <ul className="divide-y divide-border">
          {list.map((alert) => (
            <li key={alert.id} className="flex items-center justify-between gap-4 py-2 text-sm">
              <div className="min-w-0">
                <Link to={`/titres/${alert.security_id}`} className="font-medium hover:underline">{alert.name}</Link>
                <p className="text-xs text-muted-foreground">
                  {alert.direction === "above" ? "Au-dessus de" : "En dessous de"} {formatPrice(alert.price)} {unit(alert.currency)}
                  {alert.active ? " · active" : ` · déclenchée le ${day(alert.triggered_at)}`}
                </p>
              </div>
              <div className="flex gap-2">
                {!alert.active && (
                  <Button size="sm" variant="outline" aria-label={`Réarmer l'alerte sur ${alert.name}`}
                          disabled={rearm.isPending} onClick={() => rearm.mutate(alert)}>Réarmer</Button>
                )}
                <Button size="sm" variant="outline" aria-label={`Supprimer l'alerte sur ${alert.name}`}
                        disabled={remove.isPending} onClick={() => remove.mutate(alert)}>Supprimer</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
    </div>
  );
}
```

`SettingsPage.tsx` : importer `NotificationsCard` et le rendre juste avant `<FeeSettingsCard />` ; le sous-titre de l'en-tête devient « Votre profil, vos appareils, vos notifications et les frais de votre caisse régionale. »

- [ ] **Step 4: Vérifier** — `npx vitest --run && npx tsc -b && npm run lint`. Expected: tout passe, aucun nouvel avertissement de lint.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: notifications card in settings (six switches, move threshold, price alerts list)"
```

---

### Task 10: Bouton « Créer une alerte » sur la fiche d'un titre

**Files:**
- Create: `frontend/src/features/security/PriceAlertButton.tsx`, `frontend/src/features/security/PriceAlertButton.test.tsx`
- Modify: `frontend/src/features/security/SecurityPage.tsx`

**Interfaces:**
- Consumes: `POST /api/me/price-alerts` (Task 2), `useMe`, `loginPath`.
- Produces: `PriceAlertButton({ security: { id: number; name: string; price: number | null; currency: string } })`.

- [ ] **Step 1: Test qui échoue** — `PriceAlertButton.test.tsx` :

```tsx
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { PriceAlertButton } from "./PriceAlertButton";

afterEach(() => vi.unstubAllGlobals());

const SECURITY = { id: 7, name: "Equinor", price: 301.5, currency: "NOK" };

test("crée une alerte au-dessus d'un prix, dans la devise du titre", async () => {
  const fetchMock = mockFetch((url) => (url === "/api/me" ? { body: ME } : { status: 201, body: { id: "a1" } }));
  renderWithProviders(<PriceAlertButton security={SECURITY} />);
  await userEvent.click(await screen.findByRole("button", { name: "Créer une alerte" }));
  const dialog = await screen.findByRole("dialog");
  const price = within(dialog).getByLabelText("Prix (NOK)");
  expect(price).toHaveValue("301,50");
  await userEvent.clear(price);
  await userEvent.type(price, "320");
  await userEvent.click(within(dialog).getByRole("button", { name: "Créer l'alerte" }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find(([u, init]) => String(u) === "/api/me/price-alerts" && init?.method === "POST");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ security_id: 7, direction: "above", price: 320 });
  });
});

test("seuil déjà franchi : le message de l'API s'affiche", async () => {
  mockFetch((url) => (url === "/api/me" ? { body: ME }
    : { status: 400, body: { detail: { code: "already_reached", message: "Le cours est déjà au-dessus de ce prix." } } }));
  renderWithProviders(<PriceAlertButton security={SECURITY} />);
  await userEvent.click(await screen.findByRole("button", { name: "Créer une alerte" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Créer l'alerte" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("déjà au-dessus");
});

test("un visiteur est envoyé vers la connexion", async () => {
  mockFetch(() => ({ status: 401, body: { detail: { code: "not_authenticated", message: "" } } }));
  renderWithProviders(<PriceAlertButton security={SECURITY} />, { route: "/titres/7" });
  await userEvent.click(await screen.findByRole("button", { name: "Créer une alerte" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});
```

- [ ] **Step 2: Vérifier l'échec** — `npx vitest --run src/features/security/PriceAlertButton.test.tsx`. Expected: FAIL (module absent).

- [ ] **Step 3: Implémentation** — `PriceAlertButton.tsx` :

```tsx
import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useLocation, useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { loginPath } from "@/features/auth/redirect";
import { useMe } from "@/features/auth/useMe";
import { apiSend } from "@/lib/api/client";

type Security = { id: number; name: string; price: number | null; currency: string };

const toText = (value: number | null) => (value == null ? "" : value.toFixed(2).replace(".", ","));

export function PriceAlertButton({ security }: { security: Security }) {
  const { me } = useMe();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [price, setPrice] = useState(toText(security.price));
  const unit = security.currency === "EUR" ? "€" : security.currency;
  const create = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/price-alerts",
      { security_id: security.id, direction, price: Number(price.replace(",", ".")) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["price-alerts"] });
      toast.success("Alerte créée : un mail partira quand le seuil sera franchi.");
      setOpen(false);
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => (me === null ? navigate(loginPath(location)) : setOpen(true))}>
        <Bell className="size-4" aria-hidden />Créer une alerte
      </Button>
      <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) create.reset(); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Alerte de prix : {security.name}</DialogTitle>
            <DialogDescription>Un mail part une seule fois quand le cours franchit ce seuil, puis l'alerte se désactive.</DialogDescription>
          </DialogHeader>
          <form className="grid gap-3" onSubmit={submit}>
            <label className="text-sm">Quand le cours passe
              <select className="mt-1 block w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                      value={direction} onChange={(e) => setDirection(e.target.value as "above" | "below")}>
                <option value="above">au-dessus de</option>
                <option value="below">en dessous de</option>
              </select>
            </label>
            <div className="space-y-1">
              <label htmlFor="alert-price" className="text-sm">Prix ({unit})</label>
              <Input id="alert-price" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} required />
            </div>
            {create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
            <Button type="submit" disabled={create.isPending}>Créer l'alerte</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
```

(Si `lucide-react` n'a pas `Bell` dans la version installée, prendre `BellRing`.)

`SecurityPage.tsx` : importer `PriceAlertButton` et, dans le fragment `data.kind !== "index"`, après `<AskAiButton … />`, ajouter `<PriceAlertButton security={{ id: data.id, name: data.name, price: data.price, currency: data.currency }} />`.

- [ ] **Step 4: Vérifier** — `npx vitest --run && npx tsc -b && npm run lint`. Expected: tout passe.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: create a price alert from a security page"
```

---

### Task 11: Page `/desinscription`

**Files:**
- Create: `frontend/src/features/auth/UnsubscribePage.tsx`, `frontend/src/features/auth/UnsubscribePage.test.tsx`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Consumes: `GET/POST /api/unsubscribe` (Task 4), `AuthCard`, `usePageMeta`.
- Produces: route publique `/desinscription?jeton=…&type=…` (`noindex`).

- [ ] **Step 1: Test qui échoue** — `UnsubscribePage.test.tsx` :

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { UnsubscribePage } from "./UnsubscribePage";

afterEach(() => vi.unstubAllGlobals());

test("désinscription d'un seul mail", async () => {
  const fetchMock = mockFetch((url, init) => (init?.method === "POST"
    ? { body: { message: "Vous ne recevrez plus « Récap du soir »." } }
    : { body: url.startsWith("/api/unsubscribe") ? { kind: "daily_recap", label: "Récap du soir" } : null }));
  renderWithProviders(<UnsubscribePage />, { route: "/desinscription?jeton=t0k.en&type=daily_recap" });
  await userEvent.click(await screen.findByRole("button", { name: "Ne plus recevoir « Récap du soir »" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Vous ne recevrez plus « Récap du soir »");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/unsubscribe?jeton=t0k.en&type=daily_recap",
    expect.objectContaining({ method: "POST" })));
});

test("tout arrêter d'un coup", async () => {
  const fetchMock = mockFetch((url, init) => (init?.method === "POST"
    ? { body: { message: "Vous ne recevrez plus aucune notification." } } : { body: { kind: "daily_recap", label: "Récap du soir" } }));
  renderWithProviders(<UnsubscribePage />, { route: "/desinscription?jeton=t0k.en&type=daily_recap" });
  await userEvent.click(await screen.findByRole("button", { name: "Ne plus recevoir aucune notification" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/unsubscribe?jeton=t0k.en",
    expect.objectContaining({ method: "POST" })));
});

test("lien invalide", async () => {
  mockFetch(() => ({ status: 404, body: { detail: { code: "bad_link", message: "Ce lien n'est pas valable." } } }));
  renderWithProviders(<UnsubscribePage />, { route: "/desinscription?jeton=faux" });
  expect(await screen.findByRole("alert")).toHaveTextContent("n'est pas valable");
});
```

- [ ] **Step 2: Vérifier l'échec** — `npx vitest --run src/features/auth/UnsubscribePage.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Implémentation** — `UnsubscribePage.tsx` :

```tsx
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { apiGet, apiSend } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";

type LinkInfo = { kind: string | null; label: string | null };

/** Lien « Ne plus recevoir ce mail » des notifications : sans connexion, le jeton signé suffit. */
export function UnsubscribePage() {
  usePageMeta({ title: "Se désinscrire", description: "Ne plus recevoir une notification de PEA Radar.", noindex: true });
  const [params] = useSearchParams();
  const jeton = params.get("jeton") ?? "";
  const type = params.get("type");
  const one = new URLSearchParams(type ? { jeton, type } : { jeton }).toString();
  const all = new URLSearchParams({ jeton }).toString();
  const info = useQuery({ queryKey: ["unsubscribe", one], queryFn: () => apiGet<LinkInfo>(`/api/unsubscribe?${one}`), retry: false });
  const [done, setDone] = useState<string | null>(null);
  const send = useMutation({
    mutationFn: (query: string) => apiSend("POST", `/api/unsubscribe?${query}`) as Promise<{ message: string }>,
    onSuccess: (result) => setDone(result.message),
  });
  return (
    <AuthCard title="Se désinscrire">
      <div className="flex flex-col gap-4 text-sm">
        {info.isError && (
          <p role="alert" className="text-red-600">
            Ce lien de désinscription n'est pas valable. Connectez-vous pour gérer vos notifications dans les Réglages.
          </p>
        )}
        {done && <p role="status" className="font-medium">{done}</p>}
        {info.data && !done && (
          <>
            {info.data.label && (
              <Button disabled={send.isPending} onClick={() => send.mutate(one)}>Ne plus recevoir « {info.data.label} »</Button>
            )}
            <Button variant="outline" disabled={send.isPending} onClick={() => send.mutate(all)}>
              Ne plus recevoir aucune notification
            </Button>
          </>
        )}
        {send.error && <p role="alert" className="text-red-600">{send.error.message}</p>}
        <p className="text-xs text-muted-foreground">
          Les mails liés à votre compte (codes, sécurité) restent envoyés. Vous pouvez tout régler dans{" "}
          <Link to="/reglages#notifications" className="text-primary underline">vos réglages</Link>.
        </p>
      </div>
    </AuthCard>
  );
}
```

`router.tsx`, à côté de `/accepter-cgu` :

```tsx
  { path: "/desinscription", lazy: async () => ({ Component: (await import("@/features/auth/UnsubscribePage")).UnsubscribePage }) },
```

- [ ] **Step 4: Vérifier** — `npx vitest --run && npx tsc -b && npm run lint && npm run build`. Expected: tout passe.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: unsubscribe page reached from notification mails"
```

**Fin du Bloc 3 : s'arrêter pour que l'utilisateur compacte.**

---

# Bloc 4 — RGPD, restes de `comptes-rgpd`, documentation, PR (Tasks 12 à 14)

### Task 12: Notifications dans l'export et dans la purge

**Files:**
- Modify: `backend/app/services/privacy/export.py`, `backend/app/services/privacy/retention.py`, `backend/tests/test_privacy_export.py`, `backend/tests/test_privacy_retention.py`

**Interfaces:**
- Consumes: Task 1 (modèles).
- Produces: l'export contient `"notifications"` (préférences, ou `null`) et `"alertes_prix"` (avec le titre) ; `run_retention` renvoie aussi `score_snapshots` (plus de 14 jours) et `move_notices` (plus de 7 jours). Constantes `SNAPSHOT_TTL = timedelta(days=14)`, `MOVE_NOTICE_TTL = timedelta(days=7)`.

- [ ] **Step 1: Tests qui échouent**

`test_privacy_export.py` :

```python
def test_export_contains_notification_prefs_and_price_alerts(client, db, user, make_ctx):
    from app.models import PriceAlert
    from app.services.notifications.prefs import save_prefs

    security = make_security(db, "MC.PA", name="LVMH")
    save_prefs(db, user.id, {"daily_recap": True})
    db.add(PriceAlert(user_id=user.id, security_id=security.id, direction="above", price=700))
    db.flush()
    export_id = _ready(client, make_ctx)
    data = json.loads(client.get(f"/api/me/export/{export_id}").content)
    assert data["notifications"]["daily_recap"] is True
    assert data["alertes_prix"][0]["price"] == 700 and data["alertes_prix"][0]["titre"]["name"] == "LVMH"
```

`test_privacy_retention.py` (en suivant le style du fichier pour `NOW` et les imports) :

```python
def test_old_score_snapshots_and_move_notices_are_purged(db, user):
    from datetime import date

    from app.models import MoveNotice, ScoreSnapshot

    security = make_security(db, "MC.PA")
    today = NOW.astimezone(PARIS).date()
    db.add_all([
        ScoreSnapshot(day=today - timedelta(days=15), security_id=security.id, total=50),
        ScoreSnapshot(day=today - timedelta(days=13), security_id=security.id, total=50),
        MoveNotice(user_id=user.id, security_id=security.id, day=today - timedelta(days=8)),
        MoveNotice(user_id=user.id, security_id=security.id, day=today - timedelta(days=6)),
    ])
    db.flush()
    counts = run_retention(db, NOW)
    assert (counts["score_snapshots"], counts["move_notices"]) == (1, 1)
```

(importer `PARIS` depuis `app.services.market_calendar`, `make_security` depuis `tests.factories`, `timedelta` si absents.)

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_privacy_export.py tests/test_privacy_retention.py`. Expected: FAIL (`KeyError`).

- [ ] **Step 3: Implémentation**
- `export.py` : importer `NotificationPrefs, PriceAlert` ; dans `build_export`, charger `alerts = db.scalars(select(PriceAlert).where(PriceAlert.user_id == user.id).order_by(PriceAlert.created_at)).all()`, ajouter `{a.security_id for a in alerts}` à `ids`, puis ajouter au dictionnaire, après `"favoris"` :

```python
        "notifications": _row(prefs) if (prefs := db.get(NotificationPrefs, user.id)) else None,
        "alertes_prix": [{**_row(a), "titre": securities.get(a.security_id)} for a in alerts],
```

- `retention.py` : importer `MoveNotice, ScoreSnapshot` et `PARIS` ; constantes `SNAPSHOT_TTL = timedelta(days=14)` et `MOVE_NOTICE_TTL = timedelta(days=7)` ; dans `counts`, après `"email_log"` :

```python
        "score_snapshots": db.execute(delete(ScoreSnapshot).where(
            ScoreSnapshot.day < now.astimezone(PARIS).date() - SNAPSHOT_TTL)).rowcount,
        "move_notices": db.execute(delete(MoveNotice).where(
            MoveNotice.day < now.astimezone(PARIS).date() - MOVE_NOTICE_TTL)).rowcount,
```

- [ ] **Step 4: Vérifier** — mêmes tests, puis `pytest -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: notification preferences and price alerts in the data export; purge old snapshots and move notices"
```

---

### Task 13: Restes de la relecture de `comptes-rgpd`

Points mineurs relevés par la relecture finale de `comptes-rgpd`, repris ici parce que les notifications ajoutent des mails qui contiennent des montants et des noms de titres.

**Files:**
- Create: `backend/alembic/versions/a2b4c6d8e0f2_export_failed_and_single_pending.py`, `backend/tests/test_rgpd_followups.py`
- Modify:
  - `backend/app/jobs/privacy.py` ;
  - `backend/app/services/privacy/export.py`, `erasure.py`, `retention.py` ;
  - `backend/app/models/privacy.py` (index partiel) ;
  - `backend/app/api/routes/me.py` (export, suppression) ;
  - `backend/app/services/admin/users.py` (`count_admins`) ;
  - `backend/app/api/routes/auth.py` (`admin-check`) ;
  - `frontend/src/features/settings/DataCard.tsx`, `frontend/src/features/settings/DataCard.test.tsx`.

**Interfaces:**
- Produces:
  - `DataExport.status` peut valoir `failed` ;
  - index unique partiel `uq_data_exports_one_pending` sur `(user_id)` quand `status = 'pending'` ;
  - `services.admin.users.count_admins(db) -> int` (renommage public de `_admin_count`, avec `FOR UPDATE`) ;
  - `erasure.ERASED_ACCOUNT` ;
  - constantes `PENDING_EXPORT_TIMEOUT = timedelta(hours=1)` et `STUCK_ACCOUNT_DELETED = timedelta(days=7)` dans `retention.py`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_rgpd_followups.py` :

```python
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.jobs.privacy import build_pending_exports
from app.models import DataExport, EmailLog
from app.services.mail.outbox import enqueue
from app.services.privacy.erasure import ERASED_ACCOUNT, email_fingerprint, erase_account
from app.services.privacy.retention import run_retention
from tests.auth_helpers import sign_in
from tests.factories import make_user

NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def test_failing_export_is_marked_failed_and_the_others_are_built(db, user, make_ctx, monkeypatch):
    from app.jobs import privacy

    other = make_user(db, "autre@example.com")
    db.add_all([DataExport(user_id=user.id, created_at=NOW), DataExport(user_id=other.id, created_at=NOW)])
    db.flush()
    real = privacy.build_export

    def flaky(db, u, now):
        if u.id == user.id:
            raise ValueError("boum")
        return real(db, u, now)

    monkeypatch.setattr(privacy, "build_export", flaky)
    assert build_pending_exports(make_ctx(now=NOW)) == 1
    statuses = {row.user_id: row.status for row in db.scalars(select(DataExport))}
    assert statuses == {user.id: "failed", other.id: "ready"}


def test_a_failed_export_does_not_block_a_new_request(client, db, user):
    db.add(DataExport(user_id=user.id, created_at=datetime.now(UTC), status="failed"))
    db.flush()
    assert client.post("/api/me/export").status_code == 202


def test_only_one_pending_export_per_user(db, user):
    db.add_all([DataExport(user_id=user.id, created_at=NOW), DataExport(user_id=user.id, created_at=NOW)])
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_concurrent_request_gets_409(client, db, user, monkeypatch):
    from app.services.privacy import export

    db.add(DataExport(user_id=user.id, created_at=datetime.now(UTC)))
    db.flush()
    monkeypatch.setattr(export, "latest_export", lambda db, u: None)  # l'autre requête n'a pas encore vu la ligne
    response = client.post("/api/me/export")
    assert response.status_code == 409 and response.json()["detail"]["code"] == "export_pending"


def test_stuck_pending_export_becomes_failed(db, user):
    row = DataExport(user_id=user.id, created_at=NOW - timedelta(hours=2))
    db.add(row)
    db.flush()
    run_retention(db, NOW)
    db.refresh(row)
    assert row.status == "failed"


def test_erasure_fingerprints_each_row_with_its_own_address_and_erases_bodies(db, user):
    enqueue(db, "welcome", to="ancienne@example.com", user_id=user.id, context={"first_name": "Moi"})
    enqueue(db, "welcome", to=user.email, user_id=user.id, context={"first_name": "Moi"})
    for row in db.scalars(select(EmailLog).where(EmailLog.user_id == user.id)):
        row.status = "sent"
    db.flush()
    ids = [row.id for row in db.scalars(select(EmailLog).where(EmailLog.user_id == user.id))]
    email = user.email
    erase_account(db, user, now=NOW)
    rows = {row.id: row for row in db.scalars(select(EmailLog).where(EmailLog.id.in_(ids)))}
    assert {row.recipient for row in rows.values()} == {email_fingerprint("ancienne@example.com"), email_fingerprint(email)}
    assert all(row.html == row.text == ERASED_ACCOUNT for row in rows.values())


def test_account_deleted_mail_stuck_without_smtp_loses_the_address(db):
    enqueue(db, "account_deleted", to="parti@example.com", context={"first_name": "Parti"})
    row = db.scalar(select(EmailLog).where(EmailLog.kind == "account_deleted"))
    row.created_at = NOW - timedelta(days=8)
    db.flush()
    run_retention(db, NOW)
    db.refresh(row)
    assert row.recipient == email_fingerprint("parti@example.com") and row.status == "failed"


def test_self_delete_counts_admins_with_the_locking_helper(client, db, user, monkeypatch):
    from app.api.routes import me

    user.role = "admin"
    make_user(db, "admin2@example.com", role="admin")
    monkeypatch.setattr(me, "count_admins", lambda db: 1)
    response = client.request("DELETE", "/api/me", json={"confirm_email": user.email, "password": "motdepasse-solide"})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "last_admin"


def test_admin_documentation_needs_current_terms(anon_client, db):
    admin = make_user(db, "chef@example.com", role="admin", terms_version="2020-01-01")
    sign_in(anon_client, db, admin)
    assert anon_client.get("/api/auth/admin-check").status_code == 401
```

`DataCard.test.tsx`, ajouter :

```tsx
test("export échoué : message et nouveau bouton", async () => {
  mockFetch((url) => ({ body: url === "/api/me/export" ? { ...READY, status: "failed", expires_at: null } : ME }));
  renderWithProviders(<DataCard />);
  expect(await screen.findByText(/L'export précédent a échoué/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Exporter mes données" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_rgpd_followups.py` et `npx vitest --run src/features/settings/DataCard.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Implémentation**

Migration `a2b4c6d8e0f2_export_failed_and_single_pending.py` (`down_revision = "f1a3c5e7b9d1"`) :

```python
def upgrade() -> None:
    op.create_index("uq_data_exports_one_pending", "data_exports", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    op.drop_index("uq_data_exports_one_pending", table_name="data_exports")
```

(en-tête et imports comme la migration de la Task 1.) Dans `models/privacy.py`, déclarer le même index dans `__table_args__` de `DataExport` : `Index("uq_data_exports_one_pending", "user_id", unique=True, postgresql_where=text("status = 'pending'"))`.

`jobs/privacy.py` :

```python
import json
import logging

from sqlalchemy import select

from app.jobs.context import JobContext
from app.models import DataExport, User
from app.services.mail.outbox import enqueue
from app.services.privacy.export import EXPORT_TTL, build_export

logger = logging.getLogger(__name__)


def build_pending_exports(ctx: JobContext) -> int:
    """Toutes les 15 s : prépare les exports demandés, puis prévient par mail (C7). Un export qui plante passe à
    « failed » sans bloquer les autres (point de sauvegarde par ligne)."""
    now, done = ctx.now(), 0
    with ctx.session_factory() as db:
        rows = db.scalars(select(DataExport).where(DataExport.status == "pending").with_for_update(skip_locked=True)).all()
        for row in rows:
            try:
                with db.begin_nested():
                    user = db.get(User, row.user_id)
                    row.content = json.dumps(build_export(db, user, now), ensure_ascii=False, indent=2)
                    row.status, row.ready_at, row.expires_at = "ready", now, now + EXPORT_TTL
                    enqueue(db, "data_export_ready", to=user.email, user_id=user.id,
                            context={"first_name": user.first_name, "expires_at": row.expires_at})
            except Exception:
                logger.exception("Export %s impossible", row.id)
                row.status, row.content = "failed", None
                continue
            done += 1
        db.commit()
    return done
```

`export.py`, `request_export` : ignorer les exports échoués pour la limite d'un par jour :

```python
    last = latest_export(db, user)
    if last is not None and last.status == "pending":
        raise ExportRefused(409, "export_pending", "Votre export est déjà en préparation : vous recevrez un mail.")
    if last is not None and last.status != "failed" and last.created_at > now - ONE_PER:
        raise ExportRefused(429, "export_limit", "Un export par jour au plus : réessayez demain.")
```

`me.py`, `request_data_export` : entourer `export.request_export(db, user, now)` d'un `try` qui attrape aussi `IntegrityError` (déjà importé) : `db.rollback()` puis `raise fail(409, "export_pending", "Votre export est déjà en préparation : vous recevrez un mail.")`.

`services/admin/users.py` : renommer `_admin_count` en `count_admins` (définition et appel) ; `me.py` : `from app.services.admin.users import count_admins`, et dans `delete_account` remplacer `db.scalar(select(func.count()).select_from(User).where(User.role == "admin"))` par `count_admins(db)` (retirer `func` de l'import s'il ne sert plus).

`erasure.py` :

```python
ERASED_ACCOUNT = "Contenu effacé : le compte a été supprimé."
```

et remplacer la ligne `db.execute(update(EmailLog)…values(recipient=email_fingerprint(email)))` par :

```python
    for row in db.scalars(select(EmailLog).where(EmailLog.user_id == user.id)):  # chaque ligne garde SA propre empreinte
        if not row.recipient.startswith("supprimé:"):
            row.recipient = email_fingerprint(row.recipient)
        row.html = row.text = ERASED_ACCOUNT  # montants, titres et prénom ne restent pas
```

(importer `select`, retirer `update` s'il ne sert plus.)

`retention.py` : constantes `PENDING_EXPORT_TIMEOUT = timedelta(hours=1)`, `STUCK_ACCOUNT_DELETED = timedelta(days=7)` ; importer `update` et `email_fingerprint` ; au début de `run_retention`, avant `counts` :

```python
    db.execute(update(DataExport).where(DataExport.status == "pending",
                                        DataExport.created_at < now - PENDING_EXPORT_TIMEOUT).values(status="failed"))
    for row in db.scalars(select(EmailLog).where(EmailLog.kind == "account_deleted", EmailLog.status == "pending",
                                                 EmailLog.created_at < now - STUCK_ACCOUNT_DELETED)):
        row.recipient, row.status = email_fingerprint(row.recipient), "failed"  # sans SMTP, l'adresse ne reste pas
```

et la purge de `email_log` devient `EmailLog.created_at < now - EMAIL_LOG_TTL` sans condition sur le statut.

`auth.py`, `admin_check` : `if user is None or user.role != "admin" or user.terms_outdated: return Response(status_code=401)`.

`DataCard.tsx`, `ExportSection` : sous le lien de téléchargement, `{row?.status === "failed" && <p role="alert" className="text-sm text-destructive">L'export précédent a échoué : vous pouvez en demander un nouveau.</p>}`.

- [ ] **Step 4: Vérifier** — `pytest -q` et `cd frontend && npx vitest --run && npx tsc -b`. Expected: PASS (les tests existants de `test_privacy_*` et `test_api_account_deletion.py` restent verts).

- [ ] **Step 5: Commit**

```bash
git add backend frontend
git commit -m "fix: failed exports no longer stick, one pending export per user, per-row fingerprints and erased bodies on deletion, locked admin count, admin docs need current terms"
```

---

### Task 14: Documentation, bout en bout, vérification finale, PR

**Files:**
- Create: `frontend/e2e/notifications.spec.ts`
- Modify:
  - `frontend/e2e/seo.spec.ts` (`/desinscription` en `noindex`) ;
  - documentation admin : `frontend/public/documentation/comptes.md`, `api.md`, `base-de-donnees.md`, `registre.md` ;
  - guide : `frontend/public/guide/app/reglages.md`, `frontend/public/guide/faq.md`, et la page du guide qui décrit la fiche d'un titre (la trouver avec `grep -rl "J'ai acheté" frontend/public/guide`) ;
  - `frontend/src/features/legal/content.tsx` (confidentialité) ;
  - `CLAUDE.md`.

- [ ] **Step 1: E2E** — `frontend/e2e/notifications.spec.ts` :

```ts
import { expect, test } from "@playwright/test";

test("réglages des notifications gardés après rechargement", async ({ page }) => {
  await page.goto("/reglages#notifications");
  const recap = page.getByRole("switch", { name: /Récap du soir/ });
  const before = await recap.isChecked();
  await recap.click();
  await expect(recap).toBeChecked({ checked: !before });
  await page.reload();
  await expect(page.getByRole("switch", { name: /Récap du soir/ })).toBeChecked({ checked: !before });
  await page.getByRole("switch", { name: /Récap du soir/ }).click();  // remet l'état de départ
});

test("alerte créée sur une fiche, retrouvée puis supprimée dans les réglages", async ({ page }) => {
  await page.goto("/explorer");
  await page.getByRole("row").nth(1).click();
  const name = (await page.getByRole("heading", { level: 1 }).textContent())!.trim();
  await page.getByRole("button", { name: "Créer une alerte" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Quand le cours passe").selectOption("above");
  const price = dialog.getByLabel(/Prix/);
  const current = Number((await price.inputValue()).replace(",", "."));
  await price.fill(String(Math.ceil(current * 2)).replace(".", ","));
  await dialog.getByRole("button", { name: "Créer l'alerte" }).click();
  await expect(dialog).toBeHidden();
  await page.goto("/reglages#notifications");
  const remove = page.getByRole("button", { name: `Supprimer l'alerte sur ${name}` }).first();
  await expect(remove).toBeVisible();
  await remove.click();
  await expect(page.getByRole("button", { name: `Supprimer l'alerte sur ${name}` })).toHaveCount(0);
});
```

`seo.spec.ts` : ajouter `"/desinscription"` à `NOINDEX`.

Run : `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait api worker web && docker compose restart web && docker compose exec -T db psql -U pea -d pea_radar -qc "DELETE FROM rate_limit_hits;" && cd frontend && npx playwright test e2e/notifications.spec.ts e2e/seo.spec.ts`. Expected: PASS.

- [ ] **Step 2: Documentation**
- `comptes.md` :
  - nouvelle section « Notifications » (après « Durées de conservation ») :
    - tableau N1 à N6 : type interne (`price_move`…), défaut, horaire, tâche du worker (`price_moves`, `quotes_t*`, `daily_recap`, `weekly_recap`, `order_reminders`, `evening`) ;
    - jeton de désinscription signé (Ruling 1, sans `APP_SECRET` rien ne part) ;
    - `List-Unsubscribe` en un clic ;
    - alertes de prix : 50 actives au plus, désarmées une fois déclenchées, suspendues si N2 est désactivé ;
    - photos des scores (14 jours) et `move_notices` (7 jours) ;
    - `notify()`, seul point d'entrée des notifications ;
  - dans le journal de sécurité, ajouter `unsubscribed` (`details.kind` : type ou `all`) ;
  - dans la table des pages, ajouter `/desinscription` aux pages `noindex` ;
  - « Étape suivante » devient : « Toutes les étapes des comptes sont faites. Plus tard : abonnement Premium payant avec Stripe (CGV) » ;
  - dans « Export des données », ajouter le statut `failed` et « un export bloqué plus d'une heure passe à `failed` ».
- `api.md` :
  - routes `GET/PUT /me/notifications`, `GET/POST /me/price-alerts`, `PATCH/DELETE /me/price-alerts/{id}`, `GET/POST /unsubscribe` ;
  - codes `alert_limit`, `already_reached` et `bad_link`.
- `base-de-donnees.md` :
  - `notification_prefs`, `price_alerts`, `move_notices` : personnelles, oui ;
  - `score_snapshots` : personnelle, non ;
  - statut `failed` de `data_exports`.
- `registre.md` :
  - nouveau traitement « Notifications par mail » :
    - finalité : prévenir le membre des mouvements de ses titres et de son compteur d'ordres ;
    - base légale : exécution du contrat, avec opposition possible à tout moment (préférences, lien en un clic) ;
    - données : préférences, alertes de prix, favoris et positions, titres déjà signalés ;
    - destinataire : Brevo ;
    - conservation : jusqu'à la suppression du compte, titres signalés 7 jours ;
  - dans « Mails », mentionner N1 à N6 et l'effacement des contenus à la suppression.
- `content.tsx` (`PRIVACY`) :
  - « Données collectées », données saisies : ajouter « préférences de notification, alertes de prix » ;
  - tableau des finalités : ligne « Notifications par mail que vous avez choisies » → « Exécution du contrat (désactivables à tout moment) ».
- Guide :
  - `reglages.md`, section « Notifications » : les six interrupteurs, le seuil, les alertes (réarmer, supprimer), le lien « Ne plus recevoir ce mail » ;
  - page de la fiche d'un titre : le bouton « Créer une alerte » ;
  - `faq.md`, « Comment ne plus recevoir un mail ? ».
- `CLAUDE.md` :
  - la ligne d'état devient « étapes `comptes-socle` à `notifications` faites » ;
  - règle : « une notification N1 à N6 passe uniquement par `notify()` (`services/notifications/send.py`), jamais par `enqueue()` directement » ;
  - mettre à jour le nombre de tests.

- [ ] **Step 3: Vérification finale**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q
cd frontend && npx vitest --run && npx tsc -b && npm run lint && npm run build
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait api worker web && docker compose restart web
docker compose exec -T db psql -U pea -d pea_radar -qc "DELETE FROM rate_limit_hits;"
cd frontend && npm run e2e
docker compose up -d --wait api worker && docker compose restart web
```

Expected: tout passe.

- [ ] **Step 4: Commit, revue, PR**

```bash
git add -A CLAUDE.md frontend/public frontend/e2e frontend/src/features/legal
git commit -m "docs: notifications in the account docs, API, database, processing register, privacy policy and guide"
```

Revue de branche complète (skill d'exécution), corrections éventuelles, puis :

```bash
git push -u origin notifications
gh pr create --base master --head notifications --title "Notifications par mail (N1 à N6), alertes de prix, désinscription en un clic" --body "…"
```

(`--base comptes-rgpd` si la PR #6 n'est pas encore fusionnée.)

**Fin du Bloc 4.**
