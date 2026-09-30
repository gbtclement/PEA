# Comptes : admin, Premium, clé Claude dans `.env`, réglages — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner à PEA Radar un onglet Admin (utilisateurs, Premium, assistant, état de la configuration), réserver l'assistant aux membres Premium avec une limite de coût mensuelle, lire la clé Claude uniquement dans `.env`, protéger `/documentation/` et réorganiser les réglages utilisateur (profil, mot de passe, mail, appareils).

**Architecture:** Backend FastAPI existant. Deux nouvelles tables : `app_settings` (une ligne : modèle par défaut, limite de coût) et `ai_usage` (coût cumulé par utilisateur et par mois, indépendant des conversations supprimées). Les routes `/api/admin/*` passent par `require_admin()`, celles de l'assistant par `require_premium()`. Les routes de profil `/api/me/*` réutilisent les codes par mail (`change_email`) et les sessions existantes. nginx protège `/documentation/` par `auth_request` vers `/api/auth/admin-check`. Côté React : page `/admin` (réservée aux admins), réglages découpés en cartes, assistant qui explique pourquoi il est indisponible.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, React 19, react-router 7, TanStack Query, Vitest, Playwright, nginx 1.27 (`ngx_http_auth_request_module`, présent dans l'image officielle).

**Spec:** `docs/superpowers/specs/2026-09-28-comptes-utilisateurs-design.md` (sections 1.1, 1.2 `app_settings`, 1.3, 4.1 profil et appareils, 4.2, 4.3, 5.1 C4 et C6, 8, 11 étape 3).

**Branche :** `comptes-admin`, créée depuis `comptes-securite` (PR empilée : elle vise `comptes-securite` tant que les étapes 1 et 2 ne sont pas fusionnées).

## Global Constraints

- Interface, messages d'erreur, commentaires et docstrings en **français** ; identifiants en anglais ; commits en anglais, *conventional commits*, terminés par `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Erreurs d'API : `{"detail": {"code", "message"}}` (helper `fail()` de `app/api/routes/auth.py`).
- **Aucun secret en base ni saisi dans l'interface** : la clé Claude vient uniquement de `ANTHROPIC_API_KEY`. L'état de la configuration n'affiche **jamais** de valeur, seulement ✓ / ✗.
- Toutes les routes `/api/admin/*` passent par `require_admin()` ; l'assistant par `require_premium()`. Les admins sont toujours Premium.
- Garde-fous admin (spec 4.2, verbatim) : un admin ne peut ni se supprimer, ni retirer son propre rôle admin, ni retirer le dernier admin ; pas de création de compte.
- Changer le mail d'un utilisateur par l'admin le marque comme validé et envoie C4 aux deux adresses.
- Suppression par l'admin : confirmation en retapant le mail, suppression du compte et de toutes ses données, mail C6.
- Limite de coût mensuelle par utilisateur en dollars, défaut 5 ; mois civil à l'heure de Paris.
- Pagination côté serveur, 50 par page ; recherche insensible à la casse et aux accents sur mail, nom, prénom.
- `/documentation/` : 200 si la session est admin, sinon redirection vers `/connexion?suite=/documentation/`.
- Aucun test n'appelle Google, Cloudflare, Have I Been Pwned, Anthropic ni un vrai SMTP.
- Ports : web 8095, API de dev 8000, Vite 5180, Mailpit 8025. Jamais 8080, 8081, 5173.
- Commandes backend **toujours dans Docker**, depuis la racine : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q …`. Frontend : `cd frontend && npx vitest --run …`.
- La base réelle (`pgdata`) est partagée avec l'API de dev qui migre au démarrage : la migration de cette étape est d'abord vérifiée sur une base jetable.

## Rulings (décisions prises là où la spec se tait)

1. **Coût mensuel dans une table à part (`ai_usage`)** : si la limite se calculait sur `messages.cost_usd`, supprimer ses conversations remettrait le compteur à zéro. `ai_usage` est alimentée à chaque réponse et reprise de l'historique par la migration.
2. **La limite s'applique aussi aux admins** : elle protège la clé ; l'admin peut la relever. Une réponse en cours n'est jamais coupée : la limite est vérifiée avant chaque question, la dernière réponse peut donc la dépasser un peu.
3. **La clé saisie auparavant dans les Réglages est perdue** à la migration (colonne supprimée, jamais déchiffrée). La documentation dit de la remettre dans `ANTHROPIC_API_KEY`. Le modèle choisi par « Moi » devient le modèle par défaut d'`app_settings`.
4. **Changement de mail par l'utilisateur** : mot de passe actuel demandé si le compte en a un ; si la nouvelle adresse est déjà prise, la réponse est la même (202) mais aucun code n'est envoyé (pas de révélation d'un compte). Code C1 à la nouvelle adresse, C4 à l'ancienne une fois le code validé.
5. **Changement de mot de passe** : les autres sessions sont fermées, C4 envoyé. Un compte Google sans mot de passe peut en ajouter un sans mot de passe actuel.
6. **Mail C4 « modification par un admin »** : envoyé quand l'admin change le prénom, le nom, le mail ou le rôle ; pas pour la bascule Premium (qui n'est pas une question de sécurité).
7. **Recherche sans accents** : `translate(lower(col), 'àâäáãéèêëíìîïóòôöõúùûüçñ', 'aaaaaeeeeiiiiooooouuuucn')` en SQL, sans l'extension `unaccent` (la base de test est créée par `create_all`).
8. **Correction d'éligibilité** : la carte, commune à tous les comptes, passe des Réglages à l'onglet Admin.
9. **E2E de la documentation** : la vérification CSP de `/documentation/` est remplacée par la vérification de la redirection d'un visiteur (la doc et le guide partagent les mêmes fichiers Docsify et le même motif de `config.js`, le guide reste vérifié).

## Review Focus

1. **Contournement de la limite de coût en supprimant ses conversations** : supprimer toutes ses conversations ne doit pas rendre de budget. Test : Task 2 `test_deleting_conversations_does_not_reset_the_spend`.
2. **Dernier admin ou soi-même** : `PATCH role=user` sur soi, sur le dernier admin, et `DELETE` sur soi doivent être refusés, même dans une seule requête qui modifie aussi d'autres champs (rien ne doit être enregistré). Test : Task 3 `test_admin_guards`.
3. **Fuite d'une valeur de `.env`** : ni `/api/admin/config-status` ni `/api/admin/settings` ni `/api/assistant/status` ne doivent contenir la clé. Test : Task 4 `test_config_status_never_shows_values`.
4. **Changement de mail vers une adresse déjà prise** : ni 409, ni code envoyé, et la validation ne doit pas pouvoir voler l'adresse si elle a été prise entre-temps. Test : Task 5 `test_email_change_to_taken_address_sends_nothing` et `test_email_verify_refuses_an_address_taken_meanwhile`.
5. **Session d'un autre utilisateur** : `DELETE /api/me/sessions/{id}` d'une session d'autrui renvoie 404 et ne la ferme pas. Test : Task 6 `test_cannot_revoke_someone_elses_session`.

---

## File Structure

| Fichier | Responsabilité |
|---|---|
| `backend/app/models/app_settings.py` (créé) | Tables `app_settings`, `ai_usage` |
| `backend/alembic/versions/d4f6a8c0e2b4_app_settings_ai_usage.py` (créé) | Migration (tables, reprise, retrait des colonnes de clé) |
| `backend/app/repositories/app_settings.py` (créé) | `get_app_settings()` |
| `backend/app/services/assistant/usage.py` (créé) | `month_key()`, `month_spent()`, `add_cost()` |
| `backend/app/services/admin/users.py` (créé) | Liste, recherche, tri, modification, suppression, garde-fous |
| `backend/app/services/auth/profile.py` (créé) | Nom, mot de passe, changement de mail |
| `backend/app/api/routes/admin.py` (créé) | `/api/admin/*` |
| `backend/app/schemas/admin.py` (créé) | Schémas admin |
| `backend/app/services/mail/templates/account_deleted.*`, `test.*` (créés) | C6 et mail de test |
| `backend/app/models/user.py` (modifié) | Propriétés `has_password`, `has_google`, `has_premium` |
| `backend/app/models/portfolio.py` (modifié) | Retrait `anthropic_key_enc`, `ai_model` |
| `backend/app/services/secrets.py` (supprimé) | Plus de clé en base |
| `backend/app/core/current_user.py` (modifié) | `require_premium()` |
| `backend/app/api/routes/assistant.py` (modifié) | `/assistant/status`, Premium, limite, clé `.env`, modèle d'`app_settings` |
| `backend/app/services/assistant/streaming.py` (modifié) | `add_cost()` à chaque réponse |
| `backend/app/api/routes/me.py` (modifié) | `PATCH /me`, `/me/password`, `/me/email`, `/me/email/verify`, `/me/sessions` |
| `backend/app/api/routes/auth.py` (modifié) | `GET /auth/admin-check` |
| `backend/app/services/mail/render.py` (modifié) | Kinds `account_deleted`, `test` ; événements C4 |
| `backend/app/services/security_log.py` (modifié) | Nouveaux événements |
| `frontend/src/features/settings/ProfileCard.tsx`, `PasswordCard.tsx`, `EmailCard.tsx`, `DevicesCard.tsx` (créés) | Réglages utilisateur |
| `frontend/src/features/settings/AssistantSettingsCard.tsx` (supprimé) | Plus de clé saisie |
| `frontend/src/features/admin/*` (créés) | Page Admin |
| `frontend/src/features/auth/RequireAdmin.tsx` (créé) | Garde de route |
| `frontend/src/features/assistant/ChatView.tsx`, `api.ts` (modifiés) | Statut de l'assistant |
| `frontend/src/app/Sidebar.tsx`, `Layout.tsx`, `router.tsx` (modifiés) | Entrée Admin |
| `frontend/nginx/default.conf.template` (modifié) | `auth_request` sur `/documentation/` |

---

# Bloc 1 — Backend : Premium, assistant, admin

### Task 1: `app_settings`, `ai_usage`, clé Claude uniquement dans `.env`, Premium

**Files:**
- Create: `backend/app/models/app_settings.py`, `backend/app/repositories/app_settings.py`, `backend/alembic/versions/d4f6a8c0e2b4_app_settings_ai_usage.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/models/user.py`, `backend/app/models/portfolio.py`, `backend/app/schemas/auth.py`, `backend/app/core/current_user.py`, `backend/app/repositories/assistant.py`
- Delete: `backend/app/services/secrets.py`, `backend/tests/test_api_assistant_settings.py`
- Test: `backend/tests/test_models_admin.py`, `backend/tests/test_secrets_catalog.py` (retrait des tests de chiffrement)

**Interfaces:**
- Produces:
  - `AppSettings` (`id=1`, `ai_model: str`, `ai_monthly_cost_limit_usd: float`, `updated_at`), `AiUsage` (`user_id`, `month: str "AAAA-MM"`, `cost_usd: float`)
  - `get_app_settings(db) -> AppSettings` (crée la ligne si absente)
  - `User.has_password`, `User.has_google`, `User.has_premium` (propriétés)
  - `MeOut` gagne `has_password: bool`, `has_google: bool`, `has_premium: bool`
  - `require_premium(user) -> User` (403 `premium_required`)

- [ ] **Step 0: Branche** (déjà faite pendant l'écriture du plan)

```bash
git checkout comptes-securite && git checkout -b comptes-admin
```

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_models_admin.py` :

```python
from sqlalchemy import inspect

from app.models import AppSettings, UserSettings
from app.repositories.app_settings import get_app_settings
from app.schemas.auth import MeOut
from tests.factories import make_user


def test_app_settings_single_row_with_defaults(db):
    first = get_app_settings(db)
    assert (first.id, first.ai_model, first.ai_monthly_cost_limit_usd) == (1, "claude-opus-5", 5.0)
    assert get_app_settings(db) is first
    assert db.query(AppSettings).count() == 1


def test_user_settings_no_longer_hold_a_key():
    columns = {c.key for c in inspect(UserSettings).columns}
    assert "anthropic_key_enc" not in columns and "ai_model" not in columns


def test_me_exposes_sign_in_methods_and_premium(db):
    google_only = make_user(db, "g@example.com", password=None)
    google_only.google_sub = "sub-1"
    admin = make_user(db, "a@example.com", role="admin")
    out = MeOut.model_validate(google_only)
    assert (out.has_password, out.has_google, out.has_premium) == (False, True, False)
    assert MeOut.model_validate(admin).has_premium is True  # un admin est toujours Premium
```

Dans `backend/tests/test_secrets_catalog.py`, supprimer l'import `from app.services.secrets import …` et les trois tests `test_encrypt_roundtrip_and_ciphertext_differs`, `test_decrypt_with_other_secret_returns_none`, `test_encrypt_without_secret_raises`. Supprimer `backend/tests/test_api_assistant_settings.py` (la route disparaît ; remplacée par les tests de la Task 2).

- [ ] **Step 2: Vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_models_admin.py`
Expected: FAIL à l'import (`cannot import name 'AppSettings'`).

- [ ] **Step 3: Modèles** — `backend/app/models/app_settings.py` :

```python
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppSettings(Base):
    """Réglages communs à toute l'application, modifiés dans l'onglet Admin. Une seule ligne (id = 1)."""

    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="app_settings_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ai_model: Mapped[str] = mapped_column(String(64), default="claude-opus-5", server_default="claude-opus-5")
    ai_monthly_cost_limit_usd: Mapped[float] = mapped_column(Float, default=5.0, server_default="5")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AiUsage(Base):
    """Coût de l'assistant cumulé par utilisateur et par mois (heure de Paris).

    Séparé des conversations : supprimer une conversation ne rend pas de budget.
    """

    __tablename__ = "ai_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    month: Mapped[str] = mapped_column(String(7), primary_key=True)  # AAAA-MM
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
```

Dans `backend/app/models/__init__.py`, ajouter `from app.models.app_settings import AiUsage, AppSettings` et les deux noms dans `__all__` (s'il existe, sinon l'import suffit, comme pour les autres modèles).

Dans `backend/app/models/portfolio.py`, supprimer les deux lignes :

```python
    anthropic_key_enc: Mapped[str | None] = mapped_column(Text)  # clé API Claude chiffrée (Fernet)
    ai_model: Mapped[str | None] = mapped_column(String(64))
```

(retirer `Text` et `String` des imports s'ils ne servent plus ailleurs dans le fichier).

Dans `backend/app/models/user.py`, à la fin de la classe `User` :

```python
    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    @property
    def has_google(self) -> bool:
        return self.google_sub is not None

    @property
    def has_premium(self) -> bool:
        """Accès à l'assistant : Premium, ou admin (toujours considéré comme Premium)."""
        return self.is_premium or self.role == "admin"
```

- [ ] **Step 4: Réglages communs** — `backend/app/repositories/app_settings.py` :

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppSettings


def get_app_settings(db: Session) -> AppSettings:
    """La ligne unique des réglages communs ; créée avec les valeurs par défaut si elle manque."""
    row = db.get(AppSettings, 1)
    if row is None:
        db.execute(pg_insert(AppSettings).values(id=1, ai_model=get_settings().assistant_model,
                                                 ai_monthly_cost_limit_usd=5.0)
                   .on_conflict_do_nothing(index_elements=["id"]))
        db.flush()
        row = db.get(AppSettings, 1)
    return row
```

- [ ] **Step 5: `MeOut` et `require_premium`** — dans `backend/app/schemas/auth.py`, classe `MeOut`, après `is_premium: bool` :

```python
    has_password: bool
    has_google: bool
    has_premium: bool  # Premium ou admin : accès à l'assistant
```

Dans `backend/app/core/current_user.py`, après `require_admin` :

```python
def require_premium(user: User = Depends(get_current_user)) -> User:
    if not user.has_premium:
        raise HTTPException(403, detail={"code": "premium_required", "message": "Réservé aux membres Premium."})
    return user
```

- [ ] **Step 6: Plus de clé en base** — supprimer `backend/app/services/secrets.py`. Dans `backend/app/repositories/assistant.py`, supprimer `KeySource`, `resolve_api_key`, l'import `decrypt_secret` et l'import `UserSettings` s'il ne sert plus. Dans `backend/app/api/routes/assistant.py`, supprimer les routes `GET/PUT /assistant/settings`, `_settings_out`, les imports `encrypt_secret`, `MissingSecretError`, `resolve_api_key`, `AssistantSettingsOut`, `AssistantSettingsUpdate`, `ModelOut`, `MODELS`, et remplacer dans `send_message` :

```python
    row = get_user_settings(db, user.id)
    api_key, _ = resolve_api_key(row)
    if not api_key:
        raise HTTPException(status_code=409, detail="Aucune clé API Claude n'est configurée. Ajoutez-la dans les Réglages.")
    config = get_settings()
    model = get_model(row.ai_model)
```

par (version provisoire, complétée à la Task 2) :

```python
    row = get_user_settings(db, user.id)
    config = get_settings()
    if not config.anthropic_api_key:
        raise HTTPException(409, detail={"code": "ai_not_configured",
                                         "message": "L'assistant n'est pas encore configuré (ANTHROPIC_API_KEY)."})
    api_key = config.anthropic_api_key
    model = get_model(get_app_settings(db).ai_model)
```

(import `from app.repositories.app_settings import get_app_settings`). Dans `backend/app/schemas/assistant.py`, supprimer `AssistantSettingsOut` et `AssistantSettingsUpdate` (garder `ModelOut`, resservi par l'admin).

Dans `backend/tests/test_assistant_chat.py`, remplacer la fixture `configured` par :

```python
@pytest.fixture(autouse=True)
def configured(user, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", KEY)
    user.is_premium = True
```

puis :
- `test_haiku_has_no_thinking_nor_fallback` : remplacer `client.put("/api/assistant/settings", json={"model": "claude-haiku-4-5"})` par `get_app_settings(db).ai_model = "claude-haiku-4-5"` (ajouter `db` aux paramètres et l'import `from app.repositories.app_settings import get_app_settings`) ;
- `test_no_key_is_409` : remplacer la ligne `client.put(... "remove_key": True ...)` par `monkeypatch.setattr(get_settings(), "anthropic_api_key", "")` (ajouter `monkeypatch`), et l'assertion par `assert response.status_code == 409 and response.json()["detail"]["code"] == "ai_not_configured"`.

- [ ] **Step 7: Migration** — `backend/alembic/versions/d4f6a8c0e2b4_app_settings_ai_usage.py` :

```python
"""app settings, monthly AI usage, no more Claude key in the database

Revision ID: d4f6a8c0e2b4
Revises: c1e7a9d3f5b2
Create Date: 2026-09-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6a8c0e2b4"
down_revision: Union[str, Sequence[str], None] = "c1e7a9d3f5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ai_model", sa.String(64), nullable=False, server_default="claude-opus-5"),
        sa.Column("ai_monthly_cost_limit_usd", sa.Float(), nullable=False, server_default="5"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="app_settings_single_row"),
    )
    # Le modèle choisi par « Moi » devient le modèle par défaut de tout le monde.
    op.execute("INSERT INTO app_settings (id, ai_model) SELECT 1, COALESCE("
               "(SELECT ai_model FROM user_settings WHERE ai_model IS NOT NULL LIMIT 1), 'claude-opus-5')")
    op.create_table(
        "ai_usage",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("month", sa.String(7), primary_key=True),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.execute(
        "INSERT INTO ai_usage (user_id, month, cost_usd) "
        "SELECT c.user_id, to_char(m.created_at AT TIME ZONE 'Europe/Paris', 'YYYY-MM'), SUM(m.cost_usd) "
        "FROM messages m JOIN conversations c ON c.id = m.conversation_id GROUP BY 1, 2"
    )
    # La clé Claude n'est plus lue qu'à partir de ANTHROPIC_API_KEY (.env).
    op.drop_column("user_settings", "anthropic_key_enc")
    op.drop_column("user_settings", "ai_model")


def downgrade() -> None:
    op.add_column("user_settings", sa.Column("ai_model", sa.String(64), nullable=True))
    op.add_column("user_settings", sa.Column("anthropic_key_enc", sa.Text(), nullable=True))
    op.drop_table("ai_usage")
    op.drop_table("app_settings")
```

Vérifier que les noms de tables `messages` et `conversations` sont ceux de `backend/app/models/assistant.py` (c'est le cas au moment d'écrire ce plan).

- [ ] **Step 8: Vérifier les tests**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_models_admin.py tests/test_secrets_catalog.py tests/test_assistant_chat.py tests/test_api_conversations.py`
Expected: PASS. `test_api_conversations.py` peut échouer ici seulement si une de ses routes utilise déjà `require_premium` : ce n'est pas encore le cas.

- [ ] **Step 9: Migration sur une base jetable**

```bash
docker compose exec -T db createdb -U pea pea_radar_scratch
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T -e DATABASE_URL=postgresql+psycopg://pea:pea@db:5432/pea_radar_scratch api sh -c "alembic upgrade head && alembic downgrade -1 && alembic upgrade head"
docker compose exec -T db dropdb -U pea pea_radar_scratch
```

Expected: les trois commandes Alembic se terminent sans erreur.

- [ ] **Step 10: Suite complète et commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tout passe.

```bash
git add -A backend
git commit -m "feat: app settings and monthly AI usage tables, Claude key only from .env, premium flags on /me"
```

---

### Task 2: Assistant réservé aux Premium, limite de coût mensuelle

**Files:**
- Create: `backend/app/services/assistant/usage.py`
- Modify: `backend/app/api/routes/assistant.py`, `backend/app/services/assistant/streaming.py`, `backend/app/schemas/assistant.py`
- Test: `backend/tests/test_api_assistant_access.py`, `backend/tests/test_api_conversations.py`, `backend/tests/test_assistant_streaming.py`

**Interfaces:**
- Consumes: `get_app_settings`, `AiUsage`, `require_premium`, `User.has_premium` (Task 1)
- Produces:
  - `month_key(now) -> str`, `month_spent(db, user_id, now) -> float`, `add_cost(db, user_id, cost, now) -> None`
  - `GET /api/assistant/status` → `AssistantStatusOut {available: bool, reason: "premium" | "not_configured" | "limit_reached" | null, spent_usd: float, limit_usd: float, model: str}` (`model` = libellé du modèle)
  - Erreurs : 403 `premium_required`, 409 `ai_not_configured`, 429 `ai_limit_reached`

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_assistant_access.py` :

```python
from datetime import UTC, datetime

import pytest

from app.core.config import get_settings
from app.models import AiUsage, Conversation
from app.repositories.app_settings import get_app_settings
from app.services.assistant.usage import add_cost, month_key, month_spent
from tests.fake_llm import text_turn

KEY = "sk-ant-test-1234567890abcdef"


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", KEY)


def this_month() -> str:
    return month_key(datetime.now(UTC))


def test_non_premium_sees_why_and_is_refused(client):
    status = client.get("/api/assistant/status").json()
    assert (status["available"], status["reason"]) == (False, "premium")
    for response in (client.get("/api/assistant/conversations"), client.post("/api/assistant/conversations", json={})):
        assert response.status_code == 403 and response.json()["detail"]["code"] == "premium_required"


def test_admin_is_always_premium(admin_client):
    assert admin_client.get("/api/assistant/status").json()["available"] is True
    assert admin_client.get("/api/assistant/conversations").status_code == 200


def test_premium_without_key_is_not_configured(client, user, monkeypatch):
    user.is_premium = True
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    assert client.get("/api/assistant/status").json()["reason"] == "not_configured"


def test_status_shows_spend_limit_and_model_label(client, db, user):
    user.is_premium = True
    get_app_settings(db).ai_model = "claude-sonnet-5"
    db.add(AiUsage(user_id=user.id, month=this_month(), cost_usd=1.25))
    db.flush()
    status = client.get("/api/assistant/status").json()
    assert status == {"available": True, "reason": None, "spent_usd": 1.25, "limit_usd": 5.0,
                      "model": "Claude Sonnet 5 (plus rapide)"}
    assert KEY not in client.get("/api/assistant/status").text


def test_limit_reached_refuses_new_questions(client, db, user, fake_llm):
    user.is_premium = True
    get_app_settings(db).ai_monthly_cost_limit_usd = 2.0
    db.add(AiUsage(user_id=user.id, month=this_month(), cost_usd=2.0))
    db.add(AiUsage(user_id=user.id, month="2000-01", cost_usd=99.0))  # un ancien mois ne compte pas
    db.flush()
    assert client.get("/api/assistant/status").json()["reason"] == "limit_reached"
    cid = client.post("/api/assistant/conversations", json={}).json()["id"]
    response = client.post(f"/api/assistant/conversations/{cid}/messages", json={"content": "Bonjour"})
    assert response.status_code == 429 and response.json()["detail"]["code"] == "ai_limit_reached"
    assert fake_llm.calls == []


def test_each_reply_adds_to_the_month(client, db, user, fake_llm):
    user.is_premium = True
    fake_llm.turns = [text_turn("Bonjour", input_tokens=1000, output_tokens=2000)]
    cid = client.post("/api/assistant/conversations", json={}).json()["id"]
    client.post(f"/api/assistant/conversations/{cid}/messages", json={"content": "Salut"})
    assert month_spent(db, user.id, datetime.now(UTC)) == pytest.approx(0.001 * 5 + 0.002 * 25, abs=1e-4)


def test_deleting_conversations_does_not_reset_the_spend(client, db, user):
    user.is_premium = True
    conv = Conversation(user_id=user.id, title="x", cost_usd=3.0)
    db.add(conv)
    add_cost(db, user.id, 3.0, datetime.now(UTC))
    db.flush()
    assert client.delete(f"/api/assistant/conversations/{conv.id}").status_code == 204
    assert month_spent(db, user.id, datetime.now(UTC)) == 3.0


def test_month_follows_paris_time():
    assert month_key(datetime(2026, 9, 30, 22, 30, tzinfo=UTC)) == "2026-10"  # 0 h 30 à Paris
```

Dans `backend/tests/test_api_conversations.py` et `backend/tests/test_assistant_streaming.py`, ajouter en tête (après les imports) :

```python
@pytest.fixture(autouse=True)
def premium(user):
    user.is_premium = True
```

(ajouter `import pytest` si absent).

- [ ] **Step 2: Vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_assistant_access.py`
Expected: FAIL (`No module named 'app.services.assistant.usage'`).

- [ ] **Step 3: Compteur mensuel** — `backend/app/services/assistant/usage.py` :

```python
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import AiUsage

PARIS = ZoneInfo("Europe/Paris")


def month_key(now: datetime) -> str:
    """Mois civil à l'heure de Paris, « AAAA-MM » : la limite repart le 1er à minuit."""
    return now.astimezone(PARIS).strftime("%Y-%m")


def month_spent(db: Session, user_id: uuid.UUID, now: datetime) -> float:
    row = db.get(AiUsage, (user_id, month_key(now)))
    return row.cost_usd if row else 0.0


def add_cost(db: Session, user_id: uuid.UUID, cost: float, now: datetime) -> None:
    """Ajoute le coût d'une réponse au mois en cours (dans la transaction de l'appelant)."""
    stmt = pg_insert(AiUsage).values(user_id=user_id, month=month_key(now), cost_usd=cost)
    db.execute(stmt.on_conflict_do_update(index_elements=["user_id", "month"],
                                          set_={"cost_usd": AiUsage.cost_usd + stmt.excluded.cost_usd}))
```

Dans `backend/app/services/assistant/streaming.py`, `save_reply`, juste avant `db.commit()` :

```python
    add_cost(db, conv.user_id, cost, datetime.now(UTC))
```

(imports : `from datetime import UTC, datetime` et `from app.services.assistant.usage import add_cost`).

- [ ] **Step 4: Schéma** — dans `backend/app/schemas/assistant.py` :

```python
class AssistantStatusOut(BaseModel):
    available: bool
    reason: Literal["premium", "not_configured", "limit_reached"] | None
    spent_usd: float
    limit_usd: float
    model: str  # libellé du modèle par défaut
```

- [ ] **Step 5: Routes** — dans `backend/app/api/routes/assistant.py` :

```python
def _status(db: Session, user: User, now: datetime) -> AssistantStatusOut:
    app_settings = get_app_settings(db)
    spent, limit = month_spent(db, user.id, now), app_settings.ai_monthly_cost_limit_usd
    reason = None
    if not user.has_premium:
        reason = "premium"
    elif not get_settings().anthropic_api_key:
        reason = "not_configured"
    elif spent >= limit:
        reason = "limit_reached"
    return AssistantStatusOut(available=reason is None, reason=reason, spent_usd=round(spent, 4), limit_usd=limit,
                              model=get_model(app_settings.ai_model).label)


@router.get("/assistant/status", response_model=AssistantStatusOut)
def assistant_status(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                     now: datetime = Depends(get_now)) -> AssistantStatusOut:
    return _status(db, user, now)
```

Remplacer `Depends(get_current_user)` par `Depends(require_premium)` dans les cinq routes de conversation (`list_conversations`, `create_conversation`, `get_conversation`, `delete_conversation`, `send_message`). Dans `send_message`, ajouter le paramètre `now: datetime = Depends(get_now)` et remplacer le bloc provisoire de la Task 1 par :

```python
    row = get_user_settings(db, user.id)
    status = _status(db, user, now)
    if status.reason == "not_configured":
        raise HTTPException(409, detail={"code": "ai_not_configured",
                                         "message": "L'assistant n'est pas encore configuré (ANTHROPIC_API_KEY)."})
    if status.reason == "limit_reached":
        raise HTTPException(429, detail={"code": "ai_limit_reached", "message": (
            f"Limite mensuelle de l'assistant atteinte ({status.limit_usd:.2f} $) : elle repart le 1er du mois.")})
    config = get_settings()
    api_key = config.anthropic_api_key
    model = get_model(get_app_settings(db).ai_model)
```

Imports : `from datetime import datetime`, `from app.core.current_user import get_current_user, get_now, require_premium`, `from app.services.assistant.usage import month_spent`, `AssistantStatusOut`.

La vérification d'appartenance (`owned_conversation`) reste **avant** le contrôle de limite : la conversation d'un autre renvoie toujours 404.

- [ ] **Step 6: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_assistant_access.py tests/test_api_conversations.py tests/test_assistant_streaming.py tests/test_assistant_chat.py`
Expected: PASS.

- [ ] **Step 7: Suite complète et commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tout passe.

```bash
git add -A backend
git commit -m "feat: assistant for premium members only, with a monthly cost limit per user"
```

---

### Task 3: API Admin — utilisateurs

**Files:**
- Create: `backend/app/services/admin/__init__.py` (vide), `backend/app/services/admin/users.py`, `backend/app/schemas/admin.py`, `backend/app/api/routes/admin.py`, `backend/app/services/mail/templates/account_deleted.html`, `account_deleted.txt`
- Modify: `backend/app/main.py`, `backend/app/services/mail/render.py`, `backend/app/services/security_log.py`
- Test: `backend/tests/test_api_admin_users.py`, `backend/tests/test_mail_render.py`

**Interfaces:**
- Consumes: `require_admin`, `enqueue`, `log_event`, `fail`, `client_ip` (existants)
- Produces:
  - `GET /api/admin/users?q=&sort=&order=asc|desc&page=1` → `AdminUserListOut {items: AdminUserOut[], total, page, page_size}` ; `sort` ∈ `email, first_name, last_name, role, is_premium, verified, created_at, last_login_at` (défaut `created_at`, `desc`)
  - `AdminUserOut {id, email, first_name, last_name, role, is_premium, verified: bool, has_password, has_google, created_at, last_login_at}`
  - `PATCH /api/admin/users/{id}` `AdminUserUpdate {first_name?, last_name?, email?, role?, is_premium?}` → `AdminUserOut` ; erreurs 400 `self_demotion`, 400 `last_admin`, 409 `email_taken`, 404 `not_found`
  - `DELETE /api/admin/users/{id}` `{confirm_email}` → 204 ; erreurs 400 `self_delete`, 400 `confirm_mismatch`
  - Mail `account_deleted` (C6) ; événements C4 `admin_updated`, `email_changed_by_admin`
  - Événements de journal `admin_user_updated`, `admin_user_deleted`

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_admin_users.py` :

```python
import uuid

import pytest
from sqlalchemy import select

from app.models import EmailLog, Favorite, SecurityEvent, User
from tests.factories import make_security, make_user


def admin_of(db) -> User:
    return db.scalar(select(User).where(User.email == "admin@example.com"))


def mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind)).all()


def test_non_admin_gets_403_everywhere(client, db):
    other = make_user(db, "x@example.com")
    for method, path in (("GET", "/api/admin/users"), ("PATCH", f"/api/admin/users/{other.id}"),
                         ("DELETE", f"/api/admin/users/{other.id}")):
        response = client.request(method, path, json={})
        assert response.status_code == 403, path


def test_list_search_ignores_case_and_accents(admin_client, db):
    make_user(db, "helene@example.com", first_name="Hélène", last_name="Dupré")
    make_user(db, "paul@example.com", first_name="Paul", last_name="Martin")
    body = admin_client.get("/api/admin/users", params={"q": "HELENE"}).json()
    assert [u["email"] for u in body["items"]] == ["helene@example.com"] and body["total"] == 1
    assert admin_client.get("/api/admin/users", params={"q": "dupre"}).json()["total"] == 1
    assert admin_client.get("/api/admin/users", params={"q": "PAUL@EX"}).json()["total"] == 1


def test_list_sorts_and_paginates_by_50(admin_client, db):
    for i in range(55):
        make_user(db, f"u{i:02d}@example.com", last_name=f"Nom{i:02d}")
    first = admin_client.get("/api/admin/users", params={"sort": "email", "order": "asc"}).json()
    assert (first["total"], first["page_size"], len(first["items"])) == (56, 50, 50)
    assert first["items"][0]["email"] == "admin@example.com"
    second = admin_client.get("/api/admin/users", params={"sort": "email", "order": "asc", "page": 2}).json()
    assert [u["email"] for u in second["items"]][-1] == "u54@example.com"
    assert admin_client.get("/api/admin/users", params={"sort": "password_hash"}).status_code == 422


def test_list_shows_methods_and_never_secrets(admin_client, db):
    google = make_user(db, "g@example.com", password=None)
    google.google_sub = "sub-123"
    db.flush()
    row = next(u for u in admin_client.get("/api/admin/users").json()["items"] if u["email"] == "g@example.com")
    assert (row["has_password"], row["has_google"], row["verified"]) == (False, True, True)
    text = admin_client.get("/api/admin/users").text
    assert "password_hash" not in text and "sub-123" not in text


def test_toggle_premium_sends_no_mail(admin_client, db):
    user = make_user(db, "p@example.com")
    body = admin_client.patch(f"/api/admin/users/{user.id}", json={"is_premium": True}).json()
    assert body["is_premium"] is True and mails(db, "security_alert") == []


def test_edit_names_alerts_the_user_and_is_logged(admin_client, db):
    user = make_user(db, "p@example.com")
    body = admin_client.patch(f"/api/admin/users/{user.id}", json={"first_name": " Paul ", "last_name": "Neuf"}).json()
    assert (body["first_name"], body["last_name"]) == ("Paul", "Neuf")
    assert [m.recipient for m in mails(db, "security_alert")] == ["p@example.com"]
    event = db.scalars(select(SecurityEvent).where(SecurityEvent.kind == "admin_user_updated")).one()
    assert event.user_id == user.id and event.actor_id == admin_of(db).id
    assert event.details == {"fields": ["first_name", "last_name"]}


def test_edit_email_marks_verified_and_alerts_both_addresses(admin_client, db):
    user = make_user(db, "old@example.com", verified=False)
    body = admin_client.patch(f"/api/admin/users/{user.id}", json={"email": "New@Example.com"}).json()
    assert body["email"] == "new@example.com" and body["verified"] is True
    assert sorted(m.recipient for m in mails(db, "security_alert")) == ["new@example.com", "old@example.com"]


def test_edit_email_to_a_taken_address_is_409(admin_client, db):
    user = make_user(db, "a1@example.com")
    make_user(db, "a2@example.com")
    response = admin_client.patch(f"/api/admin/users/{user.id}", json={"email": "a2@example.com"})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "email_taken"


def test_admin_guards(admin_client, db):
    me = admin_of(db)
    response = admin_client.patch(f"/api/admin/users/{me.id}", json={"role": "user", "first_name": "Changé"})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "self_demotion"
    db.refresh(me)
    assert (me.role, me.first_name) == ("admin", "Admin")  # rien n'est enregistré
    response = admin_client.request("DELETE", f"/api/admin/users/{me.id}", json={"confirm_email": me.email})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "self_delete"


def test_last_admin_cannot_be_demoted(admin_client, db):
    from app.services.admin.users import AdminError, update_user

    me = admin_of(db)
    other = make_user(db, "other-admin@example.com", role="admin")
    assert admin_client.patch(f"/api/admin/users/{other.id}", json={"role": "user"}).json()["role"] == "user"
    # Dernier admin : même par une autre voie que « soi-même », le rôle ne peut plus tomber à zéro.
    with pytest.raises(AdminError) as error:
        update_user(db, actor=other, target=me, changes={"role": "user"}, now=me.created_at)
    assert error.value.code == "last_admin"


def test_delete_requires_the_email_and_removes_everything(admin_client, db):
    user = make_user(db, "bye@example.com")
    security = make_security(db, "MC.PA")
    db.add(Favorite(user_id=user.id, security_id=security.id))
    db.flush()
    wrong = admin_client.request("DELETE", f"/api/admin/users/{user.id}", json={"confirm_email": "autre@example.com"})
    assert wrong.status_code == 400 and wrong.json()["detail"]["code"] == "confirm_mismatch"
    ok = admin_client.request("DELETE", f"/api/admin/users/{user.id}", json={"confirm_email": " BYE@example.com "})
    assert ok.status_code == 204
    db.expire_all()
    assert db.get(User, user.id) is None and db.scalars(select(Favorite)).all() == []
    deleted = mails(db, "account_deleted")
    assert [m.recipient for m in deleted] == ["bye@example.com"] and deleted[0].user_id is None
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.kind == "admin_user_deleted")).one()


def test_unknown_user_is_404(admin_client):
    assert admin_client.patch(f"/api/admin/users/{uuid.uuid4()}", json={"is_premium": True}).status_code == 404
```

Dans `backend/tests/test_mail_render.py`, ajouter :

```python
def test_account_deleted_and_admin_alerts_render():
    deleted = render("account_deleted", {"first_name": "Jean"}, base_url="https://pea.example")
    assert deleted.subject == "Votre compte PEA Radar a été supprimé" and "Jean" in deleted.text
    for event in ("admin_updated", "email_changed_by_admin", "password_changed", "email_changed"):
        mail = render("security_alert", {"first_name": "Jean", "event": event}, base_url="https://pea.example")
        assert mail.text.strip()
```

(avec `from app.services.mail.render import render` si l'import manque).

- [ ] **Step 2: Vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_admin_users.py tests/test_mail_render.py`
Expected: FAIL (404 sur `/api/admin/users`, `KeyError: 'account_deleted'`).

- [ ] **Step 3: Mails et journal** — dans `backend/app/services/mail/render.py`, `SUBJECTS` :

```python
    "account_deleted": "Votre compte PEA Radar a été supprimé",
    "test": "Mail de test PEA Radar",
```

et `SECURITY_EVENTS` :

```python
    "admin_updated": "Un administrateur de PEA Radar vient de modifier votre compte (nom, adresse ou rôle).",
    "email_changed_by_admin": ("Un administrateur de PEA Radar vient de changer l'adresse mail de votre compte. "
                               "Les prochains mails iront à la nouvelle adresse."),
    "password_changed": ("Le mot de passe de votre compte vient d'être changé depuis les réglages. Vos autres "
                         "appareils ont été déconnectés."),
    "email_changed": ("L'adresse mail de votre compte vient d'être changée depuis les réglages. Les prochains mails "
                      "iront à la nouvelle adresse."),
```

`backend/app/services/mail/templates/account_deleted.txt` :

```
Bonjour {{ first_name }},

Votre compte PEA Radar et toutes ses données (ordres, favoris, conversations, réglages) viennent d'être supprimés.

Si vous pensez qu'il s'agit d'une erreur, répondez à ce mail.

{% include "_footer.txt" %}
```

`account_deleted.html` : même contenu dans le gabarit commun, en suivant `welcome.html` (`{% extends "_layout.html" %}` et les mêmes blocs que lui ; reprendre sa structure exacte).

`test.txt` :

```
Bonjour {{ first_name }},

Ce mail de test confirme que l'envoi fonctionne depuis PEA Radar.

{% include "_footer.txt" %}
```

`test.html` : même contenu, même gabarit que `welcome.html`.

Dans `backend/app/services/security_log.py`, ajouter à `EVENT_KINDS` : `"admin_user_updated", "admin_user_deleted", "admin_settings_updated", "password_changed", "email_changed", "session_revoked"`.

- [ ] **Step 4: Schémas** — `backend/app/schemas/admin.py` :

```python
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.services.assistant.catalog import MODELS

SortKey = Literal["email", "first_name", "last_name", "role", "is_premium", "verified", "created_at", "last_login_at"]


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_premium: bool
    verified: bool
    has_password: bool
    has_google: bool
    created_at: datetime
    last_login_at: datetime | None


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    role: Literal["user", "admin"] | None = None
    is_premium: bool | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Champ obligatoire.")
        return value


class DeleteUserIn(BaseModel):
    confirm_email: str = Field(max_length=254)


class ModelChoice(BaseModel):
    id: str
    label: str


class AdminSettingsOut(BaseModel):
    ai_model: str
    ai_monthly_cost_limit_usd: float
    models: list[ModelChoice]


class AdminSettingsIn(BaseModel):
    ai_model: str
    ai_monthly_cost_limit_usd: float = Field(ge=0, le=1000)

    @field_validator("ai_model")
    @classmethod
    def known_model(cls, value: str) -> str:
        if value not in {m.id for m in MODELS}:
            raise ValueError("Modèle inconnu.")
        return value


class ConfigStatusOut(BaseModel):
    claude: bool
    smtp: bool
    google: bool
    turnstile: bool
    app_secret: bool
    admin_email: bool
```

(`AdminSettings*` et `ConfigStatusOut` servent à la Task 4 ; ils sont posés ici pour n'avoir qu'un fichier de schémas.)

- [ ] **Step 5: Service** — `backend/app/services/admin/users.py` :

```python
"""Gestion des comptes par un administrateur : liste, modification, suppression, garde-fous."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.core.security import normalize_email
from app.models import User
from app.services.mail.outbox import enqueue
from app.services.security_log import log_event

PAGE_SIZE = 50
_ACCENTED = "àâäáãéèêëíìîïóòôöõúùûüçñ"
_PLAIN = "aaaaaeeeeiiiiooooouuuucn"
_FOLD = str.maketrans(_ACCENTED, _PLAIN)
SORTS = {
    "email": User.email, "first_name": User.first_name, "last_name": User.last_name, "role": User.role,
    "is_premium": User.is_premium, "verified": User.email_verified_at, "created_at": User.created_at,
    "last_login_at": User.last_login_at,
}


class AdminError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _fold(column) -> ColumnElement:
    """Minuscules sans accents, côté SQL (sans l'extension unaccent)."""
    return func.translate(func.lower(column), _ACCENTED, _PLAIN)


@dataclass(frozen=True)
class UserPage:
    items: list[User]
    total: int


def list_users(db: Session, *, q: str, sort: str, order: str, page: int) -> UserPage:
    stmt = select(User)
    words = q.lower().translate(_FOLD).split()
    for word in words:  # chaque mot doit se trouver dans le mail, le prénom ou le nom
        pattern = f"%{word}%"
        stmt = stmt.where(or_(_fold(User.email).like(pattern), _fold(User.first_name).like(pattern),
                              _fold(User.last_name).like(pattern)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    column = SORTS[sort]
    ordering = column.asc().nulls_last() if order == "asc" else column.desc().nulls_last()
    rows = db.scalars(stmt.order_by(ordering, User.id).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    return UserPage(list(rows), total)


def _admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.role == "admin"))


def update_user(db: Session, *, actor: User, target: User, changes: dict, now: datetime) -> User:
    """Applique les champs fournis. Tous les contrôles passent avant la première écriture."""
    if changes.get("role") == "user" and target.role == "admin":
        if target.id == actor.id:
            raise AdminError(400, "self_demotion", "Vous ne pouvez pas retirer votre propre rôle d'administrateur.")
        if _admin_count(db) <= 1:
            raise AdminError(400, "last_admin", "Il doit rester au moins un administrateur.")
    new_email = normalize_email(changes["email"]) if changes.get("email") else None
    if new_email == target.email:
        new_email = None
    if new_email and db.scalar(select(User.id).where(User.email == new_email)) is not None:
        raise AdminError(409, "email_taken", "Cette adresse est déjà utilisée par un autre compte.")

    changed = [field for field in ("first_name", "last_name", "role", "is_premium")
               if changes.get(field) is not None and changes[field] != getattr(target, field)]
    for field in changed:
        setattr(target, field, changes[field])
    old_email = target.email
    if new_email:
        target.email = new_email
        target.email_verified_at = target.email_verified_at or now  # l'admin en prend la responsabilité
        changed.append("email")
    if not changed:
        return target
    log_event(db, "admin_user_updated", now=now, user_id=target.id, actor_id=actor.id, details={"fields": changed})
    context = {"first_name": target.first_name}
    if new_email:
        for address in (old_email, new_email):
            enqueue(db, "security_alert", to=address, user_id=target.id,
                    context={**context, "event": "email_changed_by_admin"})
    elif set(changed) - {"is_premium"}:
        enqueue(db, "security_alert", to=target.email, user_id=target.id, context={**context, "event": "admin_updated"})
    return target


def delete_user(db: Session, *, actor: User, target: User, confirm_email: str, now: datetime) -> None:
    if target.id == actor.id:
        raise AdminError(400, "self_delete", "Vous ne pouvez pas supprimer votre propre compte ici.")
    if normalize_email(confirm_email) != target.email:
        raise AdminError(400, "confirm_mismatch", "L'adresse retapée ne correspond pas au compte.")
    email, first_name = target.email, target.first_name
    log_event(db, "admin_user_deleted", now=now, user_id=target.id, actor_id=actor.id)
    db.delete(target)  # les tables liées suivent par ON DELETE CASCADE (ou SET NULL pour les journaux)
    db.flush()
    enqueue(db, "account_deleted", to=email, user_id=None, context={"first_name": first_name})
```

Note : la ligne du journal est écrite avant la suppression, sa colonne `user_id` passe à `NULL` par `ON DELETE SET NULL` ; c'est voulu (plus aucune donnée personnelle du compte supprimé ne reste liée).

Vérifier que `normalize_email` de `app/core/security.py` fait bien `strip().lower()` (sinon, `" BYE@example.com "` du test échouera) ; il est utilisé ainsi par `find_user`.

- [ ] **Step 6: Routes** — `backend/app/api/routes/admin.py` :

```python
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.routes.auth import fail
from app.core.current_user import get_now, require_admin
from app.core.db import get_db
from app.models import User
from app.schemas.admin import AdminUserListOut, AdminUserOut, AdminUserUpdate, DeleteUserIn, SortKey
from app.services.admin.users import PAGE_SIZE, AdminError, delete_user, list_users, update_user

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _out(user: User) -> AdminUserOut:
    return AdminUserOut.model_validate({**{k: getattr(user, k) for k in (
        "id", "email", "first_name", "last_name", "role", "is_premium", "has_password", "has_google", "created_at",
        "last_login_at")}, "verified": user.email_verified_at is not None})


def _target(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise fail(404, "not_found", "Compte introuvable.")
    return user


@router.get("/users", response_model=AdminUserListOut)
def admin_list_users(q: str = Query("", max_length=100), sort: SortKey = "created_at",
                     order: str = Query("desc", pattern="^(asc|desc)$"), page: int = Query(1, ge=1),
                     db: Session = Depends(get_db)) -> AdminUserListOut:
    result = list_users(db, q=q, sort=sort, order=order, page=page)
    return AdminUserListOut(items=[_out(u) for u in result.items], total=result.total, page=page, page_size=PAGE_SIZE)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def admin_update_user(user_id: uuid.UUID, payload: AdminUserUpdate, db: Session = Depends(get_db),
                      actor: User = Depends(require_admin), now: datetime = Depends(get_now)) -> AdminUserOut:
    target = _target(db, user_id)
    try:
        update_user(db, actor=actor, target=target, changes=payload.model_dump(exclude_none=True), now=now)
    except AdminError as error:  # levée avant toute écriture : rien à annuler
        raise fail(error.status, error.code, error.message)
    db.commit()
    return _out(target)


@router.delete("/users/{user_id}", status_code=204)
def admin_delete_user(user_id: uuid.UUID, payload: DeleteUserIn, db: Session = Depends(get_db),
                      actor: User = Depends(require_admin), now: datetime = Depends(get_now)) -> Response:
    target = _target(db, user_id)
    try:
        delete_user(db, actor=actor, target=target, confirm_email=payload.confirm_email, now=now)
    except AdminError as error:  # levée avant toute écriture : rien à annuler
        raise fail(error.status, error.code, error.message)
    db.commit()
    return Response(status_code=204)
```

Dans `backend/app/main.py`, importer `admin` avec les autres routes et l'ajouter au tuple (après `me`).

- [ ] **Step 7: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_admin_users.py tests/test_mail_render.py`
Expected: PASS.

- [ ] **Step 8: Suite complète et commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tout passe.

```bash
git add -A backend
git commit -m "feat: admin API to list, search, edit and delete accounts, with guards and alert mails"
```

---

### Task 4: API Admin — assistant, état de la configuration, mail de test, contrôle pour nginx

**Files:**
- Modify: `backend/app/api/routes/admin.py`, `backend/app/api/routes/auth.py`
- Test: `backend/tests/test_api_admin_settings.py`

**Interfaces:**
- Consumes: `get_app_settings` (Task 1), schémas `AdminSettingsIn/Out`, `ModelChoice`, `ConfigStatusOut` (Task 3), `enqueue`, `get_google_client`
- Produces:
  - `GET/PUT /api/admin/settings` → `AdminSettingsOut {ai_model, ai_monthly_cost_limit_usd, models: [{id, label}]}`
  - `GET /api/admin/config-status` → `ConfigStatusOut {claude, smtp, google, turnstile, app_secret, admin_email}` (booléens)
  - `POST /api/admin/test-email` → 202 `{message}` (mail `test` à sa propre adresse)
  - `GET /api/auth/admin-check` → 204 si la session est admin, sinon 401 (sans corps utile)

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_admin_settings.py` :

```python
from sqlalchemy import select

from app.core.config import get_settings
from app.models import EmailLog, SecurityEvent


def test_settings_round_trip_and_are_logged(admin_client, db):
    body = admin_client.get("/api/admin/settings").json()
    assert (body["ai_model"], body["ai_monthly_cost_limit_usd"]) == ("claude-opus-5", 5.0)
    assert {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5 (économique)"} in body["models"]
    saved = admin_client.put("/api/admin/settings", json={"ai_model": "claude-haiku-4-5", "ai_monthly_cost_limit_usd": 12.5})
    assert saved.json()["ai_model"] == "claude-haiku-4-5" and saved.json()["ai_monthly_cost_limit_usd"] == 12.5
    event = db.scalars(select(SecurityEvent).where(SecurityEvent.kind == "admin_settings_updated")).one()
    assert event.details == {"ai_model": "claude-haiku-4-5", "ai_monthly_cost_limit_usd": 12.5}


def test_settings_validation(admin_client):
    for payload in ({"ai_model": "gpt-4", "ai_monthly_cost_limit_usd": 5},
                    {"ai_model": "claude-opus-5", "ai_monthly_cost_limit_usd": -1}):
        assert admin_client.put("/api/admin/settings", json=payload).status_code == 422


def test_config_status_never_shows_values(admin_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-secret-valeur-123")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_password", "mot-de-passe-smtp")
    monkeypatch.setattr(settings, "turnstile_secret_key", "")
    response = admin_client.get("/api/admin/config-status")
    body = response.json()
    assert (body["claude"], body["smtp"], body["turnstile"]) == (True, True, False)
    assert body["google"] is True  # fake_google branché par les tests
    for secret in ("sk-ant-secret-valeur-123", "smtp.example.com", "mot-de-passe-smtp"):
        assert secret not in response.text
    for path in ("/api/admin/settings", "/api/assistant/status"):
        assert "sk-ant-secret-valeur-123" not in admin_client.get(path).text


def test_test_email_goes_to_the_admin_only(admin_client, db):
    assert admin_client.post("/api/admin/test-email").status_code == 202
    assert [m.recipient for m in db.scalars(select(EmailLog).where(EmailLog.kind == "test"))] == ["admin@example.com"]


def test_non_admin_gets_403(client):
    for method, path in (("GET", "/api/admin/settings"), ("GET", "/api/admin/config-status"),
                         ("POST", "/api/admin/test-email")):
        assert client.request(method, path).status_code == 403


def test_admin_check_for_nginx(admin_client, client, anon_client):
    assert admin_client.get("/api/auth/admin-check").status_code == 204
    assert client.get("/api/auth/admin-check").status_code == 401
    assert anon_client.get("/api/auth/admin-check").status_code == 401
```

Attention : `client` et `admin_client` partagent la même base mais sont deux fixtures ; si pytest refuse de les combiner (deux `TestClient` sur la même app ne posent pas de problème ici, chacun construit la sienne), séparer `test_admin_check_for_nginx` en trois tests.

- [ ] **Step 2: Vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_admin_settings.py`
Expected: FAIL (404).

- [ ] **Step 3: Routes admin** — dans `backend/app/api/routes/admin.py`, ajouter :

```python
from app.api.deps import get_google_client
from app.core.config import get_settings
from app.repositories.app_settings import get_app_settings
from app.schemas.admin import AdminSettingsIn, AdminSettingsOut, ConfigStatusOut, ModelChoice
from app.schemas.auth import NoticeOut
from app.services.assistant.catalog import MODELS
from app.services.auth.google import GoogleClient
from app.services.mail.outbox import enqueue
from app.services.security_log import log_event


def _settings_out(db: Session) -> AdminSettingsOut:
    row = get_app_settings(db)
    return AdminSettingsOut(ai_model=row.ai_model, ai_monthly_cost_limit_usd=row.ai_monthly_cost_limit_usd,
                            models=[ModelChoice(id=m.id, label=m.label) for m in MODELS])


@router.get("/settings", response_model=AdminSettingsOut)
def admin_read_settings(db: Session = Depends(get_db)) -> AdminSettingsOut:
    return _settings_out(db)


@router.put("/settings", response_model=AdminSettingsOut)
def admin_update_settings(payload: AdminSettingsIn, db: Session = Depends(get_db),
                          actor: User = Depends(require_admin), now: datetime = Depends(get_now)) -> AdminSettingsOut:
    row = get_app_settings(db)
    row.ai_model, row.ai_monthly_cost_limit_usd = payload.ai_model, payload.ai_monthly_cost_limit_usd
    log_event(db, "admin_settings_updated", now=now, actor_id=actor.id, details=payload.model_dump())
    db.commit()
    return _settings_out(db)


@router.get("/config-status", response_model=ConfigStatusOut)
def admin_config_status(google: GoogleClient | None = Depends(get_google_client)) -> ConfigStatusOut:
    """Ce qui est renseigné dans .env : oui ou non, jamais la valeur."""
    s = get_settings()
    return ConfigStatusOut(claude=bool(s.anthropic_api_key), smtp=bool(s.smtp_host), google=google is not None,
                           turnstile=bool(s.turnstile_secret_key and s.turnstile_site_key),
                           app_secret=bool(s.app_secret) and s.app_secret != "change-me",
                           admin_email=bool(s.admin_email))


@router.post("/test-email", response_model=NoticeOut, status_code=202)
def admin_test_email(db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> NoticeOut:
    enqueue(db, "test", to=actor.email, user_id=actor.id, context={"first_name": actor.first_name})
    db.commit()
    return NoticeOut(message=f"Mail de test mis en file d'attente pour {actor.email}.")
```

- [ ] **Step 4: Contrôle pour nginx** — dans `backend/app/api/routes/auth.py`, à la fin :

```python
@router.get("/admin-check", status_code=204)
def admin_check(user: User | None = Depends(get_optional_user)) -> Response:
    """Pour `auth_request` de nginx (/documentation/) : 204 pour un admin connecté, 401 sinon."""
    if user is None or user.role != "admin":
        return Response(status_code=401)
    return Response(status_code=204)
```

(import `get_optional_user` depuis `app.core.current_user`).

- [ ] **Step 5: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_admin_settings.py`
Expected: PASS.

- [ ] **Step 6: Suite complète et commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tout passe.

```bash
git add -A backend
git commit -m "feat: admin settings for the assistant, configuration status, test mail and admin check for nginx"
```

**Fin du Bloc 1 : s'arrêter pour que l'utilisateur compacte.**

---

# Bloc 2 — Backend : profil et appareils

### Task 5: Profil — nom, mot de passe, changement de mail

**Files:**
- Create: `backend/app/services/auth/profile.py`, `backend/app/schemas/me.py`
- Modify: `backend/app/api/routes/me.py`, `backend/app/services/auth/codes.py`
- Test: `backend/tests/test_api_profile.py`

**Interfaces:**
- Consumes: `issue_code`, `check_code`, `enqueue`, `log_event`, `revoke_user_sessions`, `check_password_rules`, `fail`, `client_ip`, `_mail_allowed` (renommé `mail_allowed`, public), `get_auth_session`
- Produces:
  - `PATCH /api/me` `{first_name, last_name}` → `MeOut`
  - `POST /api/me/password` `{current_password?, new_password}` → `NoticeOut` ; erreurs 400 `wrong_password`, `weak_password`, `pwned_password`
  - `POST /api/me/email` `{new_email, password?}` → 202 `NoticeOut` (toujours la même réponse)
  - `POST /api/me/email/verify` `{code}` → `MeOut` ; erreurs 400 codes de `CODE_ERRORS`, 409 `email_taken`
  - `issue_code(db, user, purpose, now, *, new_email: str | None = None)` ; `pending_new_email(db, user) -> str | None`

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_profile.py` :

```python
from sqlalchemy import select

from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.security import verify_password
from app.models import AuthSession, EmailCode, EmailLog, User
from app.services.auth.codes import issue_code
from app.services.auth.sessions import open_session
from tests.factories import make_user

PASSWORD = "motdepasse-solide"
NEW = "un-nouveau-mot-de-passe-long"
NOW = datetime.now(UTC)


def mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind)).all()


def test_rename(client, user):
    body = client.patch("/api/me", json={"first_name": " Jeanne ", "last_name": "Durand"}).json()
    assert (body["first_name"], body["last_name"]) == ("Jeanne", "Durand")
    assert client.patch("/api/me", json={"first_name": "", "last_name": "x"}).status_code == 422


def test_change_password_needs_the_current_one(client, user):
    wrong = client.post("/api/me/password", json={"current_password": "pas-le-bon-mot-de-passe", "new_password": NEW})
    assert wrong.status_code == 400 and wrong.json()["detail"]["code"] == "wrong_password"
    missing = client.post("/api/me/password", json={"new_password": NEW})
    assert missing.status_code == 400 and missing.json()["detail"]["code"] == "wrong_password"


def test_change_password_signs_out_other_devices_and_alerts(client, db, user):
    current = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))  # session du client de test
    open_session(db, user, persistent=True, ip="198.51.100.1", user_agent="autre", now=NOW, settings=get_settings())
    assert client.post("/api/me/password", json={"current_password": PASSWORD, "new_password": NEW}).status_code == 200
    db.expire_all()
    assert verify_password(db.get(User, user.id).password_hash, NEW)
    remaining = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all()
    assert [s.id for s in remaining] == [current.id]  # celle-ci reste ouverte
    assert [m.recipient for m in mails(db, "security_alert")] == [user.email]


def test_change_password_rules_apply(client, fake_breach):
    short = client.post("/api/me/password", json={"current_password": PASSWORD, "new_password": "court"})
    assert short.json()["detail"]["code"] == "weak_password"
    fake_breach.pwned.add(NEW)
    pwned = client.post("/api/me/password", json={"current_password": PASSWORD, "new_password": NEW})
    assert pwned.json()["detail"]["code"] == "pwned_password"


def test_google_account_can_add_a_password(client, db, user):
    user.password_hash, user.google_sub = None, "sub-1"
    db.flush()
    assert client.post("/api/me/password", json={"new_password": NEW}).status_code == 200
    assert client.get("/api/me").json()["has_password"] is True


def test_email_change_sends_a_code_to_the_new_address(client, db, user):
    response = client.post("/api/me/email", json={"new_email": "Nouveau@Example.com", "password": PASSWORD})
    assert response.status_code == 202
    assert [m.recipient for m in mails(db, "verify_code")] == ["nouveau@example.com"]
    row = db.scalar(select(EmailCode).where(EmailCode.purpose == "change_email"))
    assert row.new_email == "nouveau@example.com"


def test_email_change_needs_the_password(client, db):
    response = client.post("/api/me/email", json={"new_email": "nouveau@example.com", "password": "faux-mot-de-passe"})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "wrong_password"
    assert mails(db, "verify_code") == []


def test_email_change_to_taken_address_sends_nothing(client, db):
    make_user(db, "prise@example.com")
    response = client.post("/api/me/email", json={"new_email": "prise@example.com", "password": PASSWORD})
    assert response.status_code == 202  # même réponse : ne révèle pas le compte
    assert mails(db, "verify_code") == []


def test_email_verify_switches_address_and_alerts_the_old_one(client, db, user, monkeypatch):
    import app.services.auth.codes as codes

    monkeypatch.setattr(codes, "new_code", lambda: "123456")
    client.post("/api/me/email", json={"new_email": "nouveau@example.com", "password": PASSWORD})
    wrong = client.post("/api/me/email/verify", json={"code": "000000"})
    assert wrong.status_code == 400 and wrong.json()["detail"]["code"] == "invalid_code"
    body = client.post("/api/me/email/verify", json={"code": "123456"}).json()
    assert body["email"] == "nouveau@example.com"
    assert [m.recipient for m in mails(db, "security_alert")] == ["moi@example.com"]


def test_email_verify_refuses_an_address_taken_meanwhile(client, db, user):
    code = issue_code(db, user, "change_email", NOW, new_email="course@example.com")
    make_user(db, "course@example.com")
    response = client.post("/api/me/email/verify", json={"code": code})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "email_taken"
    assert db.get(User, user.id).email == "moi@example.com"


def test_profile_routes_need_a_session(anon_client):
    assert anon_client.patch("/api/me", json={"first_name": "a", "last_name": "b"}).status_code == 401
    assert anon_client.post("/api/me/password", json={"new_password": NEW}).status_code == 401
```

Notes pour l'exécutant :
- La session « courante » est celle ouverte par le fixture `client` ; `open_session` en ajoute une seconde, comme un autre appareil.
- **Ne jamais appeler `db.rollback()` dans une route testée** : la session de test travaille dans un point de sauvegarde ouvert au début du test, un rollback effacerait aussi les comptes créés par le test. Les contrôles passent donc avant toute écriture.
- `fake_breach.pwned` : vérifier le nom de l'attribut dans `tests/fake_breach.py` et l'utiliser tel quel.

- [ ] **Step 2: Vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_profile.py`
Expected: FAIL (405 sur `PATCH /api/me`, `issue_code() got an unexpected keyword argument 'new_email'`).

- [ ] **Step 3: Codes de changement de mail** — dans `backend/app/services/auth/codes.py`, remplacer `issue_code` par :

```python
def issue_code(db: Session, user: User, purpose: str, now: datetime, *, new_email: str | None = None) -> str:
    """Nouveau code à 6 chiffres ; les codes précédents du même type ne marchent plus."""
    _cancel_pending(db, user, purpose, now)
    code = new_code()
    db.add(EmailCode(user_id=user.id, purpose=purpose, code_hash=token_hash(code), new_email=new_email,
                     expires_at=now + CODE_TTL, created_at=now))
    db.flush()
    return code


def pending_new_email(db: Session, user: User) -> str | None:
    """Adresse demandée par le dernier code de changement de mail (lu avant de le vérifier)."""
    return db.scalar(select(EmailCode.new_email).where(EmailCode.user_id == user.id,
                                                       EmailCode.purpose == "change_email")
                     .order_by(EmailCode.id.desc()).limit(1))
```

- [ ] **Step 4: Service** — `backend/app/services/auth/profile.py` :

```python
"""Réglages du profil : nom, mot de passe, adresse mail."""
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, normalize_email, verify_password
from app.models import AuthSession, User
from app.services.auth.codes import CodeCheck, check_code, issue_code, pending_new_email
from app.services.mail.outbox import enqueue
from app.services.security_log import log_event


def password_ok(user: User, password: str | None) -> bool:
    """Un compte sans mot de passe (Google seul) n'a rien à confirmer."""
    return not user.has_password or (password is not None and verify_password(user.password_hash, password))


def change_password(db: Session, user: User, new_password: str, *, keep_session: AuthSession, now: datetime,
                    ip: str | None) -> None:
    user.password_hash = hash_password(new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id != keep_session.id))
    log_event(db, "password_changed", now=now, user_id=user.id, ip=ip)
    enqueue(db, "security_alert", to=user.email, user_id=user.id,
            context={"first_name": user.first_name, "event": "password_changed"})


def request_email_change(db: Session, user: User, new_email: str, now: datetime) -> None:
    """Envoie un code à la nouvelle adresse, sauf si elle est déjà prise (sans le dire)."""
    new_email = normalize_email(new_email)
    if new_email == user.email or db.scalar(select(User.id).where(User.email == new_email)) is not None:
        return
    code = issue_code(db, user, "change_email", now, new_email=new_email)
    enqueue(db, "verify_code", to=new_email, user_id=user.id, context={"first_name": user.first_name, "code": code})


class EmailTaken(Exception):
    """La nouvelle adresse a été prise entre la demande et la validation."""


def confirm_email_change(db: Session, user: User, code: str, now: datetime, ip: str | None) -> CodeCheck:
    new_email = pending_new_email(db, user)
    result = check_code(db, user, "change_email", code, now)
    if result != CodeCheck.OK:
        return result
    if new_email is None or db.scalar(select(User.id).where(User.email == new_email)) is not None:
        raise EmailTaken
    old_email = user.email
    user.email = new_email
    log_event(db, "email_changed", now=now, user_id=user.id, ip=ip)
    enqueue(db, "security_alert", to=old_email, user_id=user.id,
            context={"first_name": user.first_name, "event": "email_changed"})
    return result
```

- [ ] **Step 5: Schémas** — `backend/app/schemas/me.py` :

```python
from pydantic import BaseModel, EmailStr, Field, field_validator


class ProfileIn(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Champ obligatoire.")
        return value


class PasswordChangeIn(BaseModel):
    current_password: str | None = Field(default=None, max_length=200)
    new_password: str = Field(max_length=200)


class EmailChangeIn(BaseModel):
    new_email: EmailStr
    password: str | None = Field(default=None, max_length=200)


class CodeIn(BaseModel):
    code: str = Field(pattern=r"^\s*\d{6}\s*$")
```

- [ ] **Step 6: Routes** — dans `backend/app/api/routes/auth.py`, renommer `_mail_allowed` en `mail_allowed` (et ses deux appels). Remplacer `backend/app/api/routes/me.py` par :

```python
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_breach_checker
from app.api.routes.auth import CODE_ERRORS, check_password_rules, client_ip, fail, mail_allowed
from app.core.current_user import get_auth_session, get_current_user, get_now
from app.core.db import get_db
from app.core.security import normalize_email
from app.models import AuthSession, User
from app.schemas.auth import MeOut, NoticeOut
from app.schemas.me import CodeIn, EmailChangeIn, PasswordChangeIn, ProfileIn
from app.services.auth import profile
from app.services.auth.breach import BreachChecker
from app.services.auth.codes import CodeCheck

router = APIRouter(tags=["account"])

WRONG_PASSWORD = ("wrong_password", "Mot de passe actuel incorrect.")


@router.get("/me", response_model=MeOut)
def read_me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut.model_validate(user)


@router.patch("/me", response_model=MeOut)
def update_me(payload: ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> MeOut:
    user.first_name, user.last_name = payload.first_name, payload.last_name
    db.commit()
    return MeOut.model_validate(user)


@router.post("/me/password", response_model=NoticeOut)
def change_password(payload: PasswordChangeIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user), auth: AuthSession = Depends(get_auth_session),
                    now: datetime = Depends(get_now), breach: BreachChecker = Depends(get_breach_checker)) -> NoticeOut:
    if not profile.password_ok(user, payload.current_password):
        raise fail(400, *WRONG_PASSWORD)  # avant Have I Been Pwned : pas de relais gratuit
    check_password_rules(payload.new_password, breach)
    profile.change_password(db, user, payload.new_password, keep_session=auth, now=now, ip=client_ip(request))
    db.commit()
    return NoticeOut(message="Mot de passe enregistré. Vos autres appareils ont été déconnectés.")


@router.post("/me/email", response_model=NoticeOut, status_code=202)
def request_email_change(payload: EmailChangeIn, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user), now: datetime = Depends(get_now)) -> NoticeOut:
    if not profile.password_ok(user, payload.password):
        raise fail(400, *WRONG_PASSWORD)
    new_email = normalize_email(payload.new_email)
    if mail_allowed(db, new_email, client_ip(request) or "inconnue", now):
        profile.request_email_change(db, user, new_email, now)
    db.commit()
    return NoticeOut(message="Si cette adresse peut être utilisée, un code vient d'y être envoyé.")


@router.post("/me/email/verify", response_model=MeOut)
def confirm_email_change(payload: CodeIn, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user), now: datetime = Depends(get_now)) -> MeOut:
    try:
        result = profile.confirm_email_change(db, user, payload.code, now, client_ip(request))
    except profile.EmailTaken:
        db.commit()  # le code est consommé : il faudra en redemander un
        raise fail(409, "email_taken", "Cette adresse vient d'être prise par un autre compte.")
    if result != CodeCheck.OK:
        db.commit()  # enregistre l'essai raté
        raise fail(400, *CODE_ERRORS[result])
    db.commit()
    return MeOut.model_validate(user)
```

Note : `get_current_user` et `get_auth_session` sont deux dépendances qui résolvent la même session ; FastAPI met en cache `get_auth_session` dans une requête, la session n'est lue qu'une fois. Le CSRF est vérifié par `get_auth_session` pour toutes ces routes (méthodes non sûres).

- [ ] **Step 7: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_profile.py tests/test_auth_codes.py`
Expected: PASS.

- [ ] **Step 8: Suite complète et commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tout passe.

```bash
git add -A backend
git commit -m "feat: profile settings - name, password change or first password, email change by code"
```

---

### Task 6: Appareils connectés

**Files:**
- Modify: `backend/app/api/routes/me.py`, `backend/app/schemas/me.py`
- Test: `backend/tests/test_api_sessions.py`

**Interfaces:**
- Consumes: `AuthSession`, `get_auth_session`, `log_event`
- Produces:
  - `GET /api/me/sessions` → `SessionOut[] {id, device, ip, created_at, last_seen_at, current: bool}` (plus récente d'abord, sessions expirées exclues)
  - `DELETE /api/me/sessions/{id}` → 204 (404 si elle n'est pas à soi) ; fermer la session courante revient à se déconnecter
  - `DELETE /api/me/sessions` → 204, ferme toutes les **autres** sessions

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_sessions.py` :

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models import AuthSession
from app.services.auth.sessions import open_session
from tests.factories import make_user


def other_session(db, user, *, agent="Mozilla/5.0 (Windows NT 10.0) Firefox/130.0", days_ago=0):
    now = datetime.now(UTC) - timedelta(days=days_ago)
    return open_session(db, user, persistent=True, ip="198.51.100.20", user_agent=agent, now=now,
                        settings=get_settings()).session


def test_lists_my_sessions_with_the_current_one_flagged(client, db, user):
    other = other_session(db, user)
    make_user(db, "x@example.com")
    rows = client.get("/api/me/sessions").json()
    assert len(rows) == 2
    current = [r for r in rows if r["current"]]
    assert len(current) == 1 and current[0]["id"] != str(other.id)
    assert next(r for r in rows if r["id"] == str(other.id))["ip"] == "198.51.100.0/24"
    assert "token_hash" not in client.get("/api/me/sessions").text and "csrf" not in client.get("/api/me/sessions").text


def test_expired_sessions_are_hidden(client, db, user):
    other = other_session(db, user)
    other.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()
    assert len(client.get("/api/me/sessions").json()) == 1


def test_revoke_one_session(client, db, user):
    other = other_session(db, user)
    assert client.delete(f"/api/me/sessions/{other.id}").status_code == 204
    assert db.get(AuthSession, other.id) is None


def test_cannot_revoke_someone_elses_session(client, db):
    stranger = other_session(db, make_user(db, "x@example.com"))
    assert client.delete(f"/api/me/sessions/{stranger.id}").status_code == 404
    assert db.get(AuthSession, stranger.id) is not None


def test_revoke_all_others_keeps_this_one(client, db, user):
    other_session(db, user)
    other_session(db, user)
    assert client.delete("/api/me/sessions").status_code == 204
    remaining = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all()
    assert len(remaining) == 1
    assert client.get("/api/me").status_code == 200  # toujours connecté ici


def test_revoking_the_current_session_signs_out(client, db, user):
    current = client.get("/api/me/sessions").json()[0]
    assert client.delete(f"/api/me/sessions/{current['id']}").status_code == 204
    assert client.get("/api/me").status_code == 401
```

- [ ] **Step 2: Vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_sessions.py`
Expected: FAIL (404/405).

- [ ] **Step 3: Schéma** — dans `backend/app/schemas/me.py` :

```python
import uuid
from datetime import datetime


class SessionOut(BaseModel):
    id: uuid.UUID
    device: str
    ip: str | None
    created_at: datetime
    last_seen_at: datetime
    current: bool
```

(regrouper les imports en tête du fichier).

- [ ] **Step 4: Routes** — dans `backend/app/api/routes/me.py` :

```python
@router.get("/me/sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db), auth: AuthSession = Depends(get_auth_session),
                  user: User = Depends(get_current_user), now: datetime = Depends(get_now)) -> list[SessionOut]:
    rows = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at > now)
                      .order_by(AuthSession.last_seen_at.desc()))
    return [SessionOut(id=r.id, device=r.device, ip=r.ip, created_at=r.created_at, last_seen_at=r.last_seen_at,
                       current=r.id == auth.id) for r in rows]


@router.delete("/me/sessions/{session_id}", status_code=204)
def revoke_one_session(session_id: uuid.UUID, request: Request, response: Response, db: Session = Depends(get_db),
                       auth: AuthSession = Depends(get_auth_session), user: User = Depends(get_current_user),
                       now: datetime = Depends(get_now)) -> Response:
    row = db.get(AuthSession, session_id)
    if row is None or row.user_id != user.id:
        raise fail(404, "not_found", "Appareil introuvable.")
    revoke_session(db, row.id)
    log_event(db, "session_revoked", now=now, user_id=user.id, ip=client_ip(request))
    db.commit()
    if row.id == auth.id:
        clear_auth_cookies(response, get_settings())
    response.status_code = 204
    return response


@router.delete("/me/sessions", status_code=204)
def revoke_other_sessions(request: Request, db: Session = Depends(get_db), auth: AuthSession = Depends(get_auth_session),
                          user: User = Depends(get_current_user), now: datetime = Depends(get_now)) -> Response:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.id != auth.id))
    log_event(db, "session_revoked", now=now, user_id=user.id, ip=client_ip(request), details={"all_others": True})
    db.commit()
    return Response(status_code=204)
```

Imports à ajouter : `import uuid`, `from fastapi import Response`, `from sqlalchemy import delete, select`, `from app.api.cookies import clear_auth_cookies`, `from app.core.config import get_settings`, `from app.schemas.me import SessionOut`, `from app.services.auth.sessions import revoke_session`, `from app.services.security_log import log_event`.

- [ ] **Step 5: Vérifier**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_sessions.py`
Expected: PASS.

- [ ] **Step 6: Suite complète et commit**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
Expected: tout passe.

```bash
git add -A backend
git commit -m "feat: list and sign out connected devices from the settings"
```

**Fin du Bloc 2 : s'arrêter pour que l'utilisateur compacte.**

---

# Bloc 3 — Frontend

### Task 7: Types, réglages utilisateur réorganisés

**Files:**
- Create: `frontend/src/features/settings/ProfileCard.tsx`, `PasswordCard.tsx`, `EmailCard.tsx`, `DevicesCard.tsx`, `AccountCards.test.tsx`
- Modify: `frontend/src/lib/api/schema.d.ts` (régénéré), `frontend/src/lib/api/client.ts`, `frontend/src/features/settings/SettingsPage.tsx`, `SettingsPage.test.tsx`, `frontend/src/test/utils.tsx`
- Delete: `frontend/src/features/settings/AssistantSettingsCard.tsx`, `AssistantSettingsCard.test.tsx`

**Interfaces:**
- Consumes: routes des Tasks 1 à 6
- Produces:
  - Types `AssistantStatus`, `SessionItem`, `AdminUser`, `AdminUserList`, `AdminSettings`, `ConfigStatus` dans `client.ts`
  - `ME` de test avec `has_password: true, has_google: false, has_premium: false`
  - `EligibilityOverridesCard` exporté depuis `frontend/src/features/admin/EligibilityOverridesCard.tsx` (déplacé, utilisé à la Task 9)

- [ ] **Step 1: Types** — démarrer l'API de dev (elle migre la base réelle : la migration a été vérifiée à la Task 1) puis régénérer :

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --wait api
cd frontend && npm run gen:api
```

Dans `frontend/src/lib/api/client.ts`, supprimer `AssistantSettingsOut` et ajouter :

```ts
export type AssistantStatus = components["schemas"]["AssistantStatusOut"];
export type SessionItem = components["schemas"]["SessionOut"];
export type AdminUser = components["schemas"]["AdminUserOut"];
export type AdminUserList = components["schemas"]["AdminUserListOut"];
export type AdminSettings = components["schemas"]["AdminSettingsOut"];
export type ConfigStatus = components["schemas"]["ConfigStatusOut"];
```

Dans `frontend/src/test/utils.tsx`, compléter `ME` :

```ts
export const ME = { id: "0b6f7c1e-0000-4000-8000-000000000001", email: "moi@example.com", first_name: "Moi",
                    last_name: "Dupont", role: "user", is_premium: false, has_password: true, has_google: false,
                    has_premium: false };
```

(et ajouter les trois champs à l'objet `Me` écrit en dur dans `AuthPage.test.tsx` ligne 86).

- [ ] **Step 2: Tests qui échouent** — `frontend/src/features/settings/AccountCards.test.tsx` :

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { DevicesCard } from "./DevicesCard";
import { EmailCard } from "./EmailCard";
import { PasswordCard } from "./PasswordCard";
import { ProfileCard } from "./ProfileCard";

afterEach(() => vi.unstubAllGlobals());

const bodyOf = (fetchMock: ReturnType<typeof mockFetch>, url: string) =>
  JSON.parse(String(fetchMock.mock.calls.find(([u]) => String(u) === url)?.[1]?.body));

test("modifie le prénom et le nom", async () => {
  const fetchMock = mockFetch((url) => ({ body: url === "/api/me" ? ME : { ...ME, first_name: "Jeanne" } }));
  renderWithProviders(<ProfileCard />);
  const first = await screen.findByLabelText("Prénom");
  await userEvent.clear(first);
  await userEvent.type(first, "Jeanne");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer le profil" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/me")).toEqual({ first_name: "Jeanne", last_name: "Dupont" }));
});

test("change le mot de passe en donnant l'actuel", async () => {
  const fetchMock = mockFetch((url) => ({ body: url === "/api/me" ? ME : { message: "Mot de passe enregistré." } }));
  renderWithProviders(<PasswordCard />);
  await userEvent.type(await screen.findByLabelText("Mot de passe actuel"), "ancien-mot-de-passe");
  await userEvent.type(screen.getByLabelText("Nouveau mot de passe"), "un-nouveau-mot-de-passe");
  await userEvent.click(screen.getByRole("button", { name: "Changer le mot de passe" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/me/password"))
    .toEqual({ current_password: "ancien-mot-de-passe", new_password: "un-nouveau-mot-de-passe" }));
  expect(await screen.findByText("Mot de passe enregistré.")).toBeInTheDocument();
});

test("compte Google sans mot de passe : « Ajouter un mot de passe »", async () => {
  mockFetch(() => ({ body: { ...ME, has_password: false, has_google: true } }));
  renderWithProviders(<PasswordCard />);
  expect(await screen.findByRole("button", { name: "Ajouter un mot de passe" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Mot de passe actuel")).toBeNull();
});

test("change l'adresse mail avec un code", async () => {
  const fetchMock = mockFetch((url) => ({
    body: url === "/api/me" ? ME : url === "/api/me/email" ? { message: "Code envoyé." } : { ...ME, email: "neuf@example.com" },
  }));
  renderWithProviders(<EmailCard />);
  await userEvent.type(await screen.findByLabelText("Nouvelle adresse"), "neuf@example.com");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "motdepasse-solide");
  await userEvent.click(screen.getByRole("button", { name: "Recevoir un code" }));
  await userEvent.type(await screen.findByLabelText("Code reçu"), "123456");
  await userEvent.click(screen.getByRole("button", { name: "Valider la nouvelle adresse" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/me/email/verify")).toEqual({ code: "123456" }));
  expect(await screen.findByText("Adresse modifiée : neuf@example.com")).toBeInTheDocument();
});

test("liste les appareils et en déconnecte un", async () => {
  const sessions = [
    { id: "s1", device: "Chrome sur Windows", ip: "203.0.113.0/24", created_at: "2026-09-01T08:00:00Z", last_seen_at: "2026-09-29T08:00:00Z", current: true },
    { id: "s2", device: "Safari sur iPhone", ip: "198.51.100.0/24", created_at: "2026-09-02T08:00:00Z", last_seen_at: "2026-09-28T08:00:00Z", current: false },
  ];
  const fetchMock = mockFetch((url) => (url === "/api/me/sessions" ? { body: sessions } : { status: 204, body: null }));
  renderWithProviders(<DevicesCard />);
  expect(await screen.findByText("Cet appareil")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Déconnecter Safari sur iPhone" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/me/sessions/s2", expect.objectContaining({ method: "DELETE" })));
  await userEvent.click(screen.getByRole("button", { name: "Déconnecter tous les autres" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/me/sessions", expect.objectContaining({ method: "DELETE" })));
});
```

Dans `SettingsPage.test.tsx` : supprimer le `vi.mock("./AssistantSettingsCard", …)`, supprimer les deux tests d'éligibilité (ils partent à la Task 9 dans `AdminPage.test.tsx`), ajouter en tête `vi.mock("./ProfileCard", () => ({ ProfileCard: () => null }))` et de même pour `PasswordCard`, `EmailCard`, `DevicesCard`, et ce test :

```tsx
test("les réglages ne montrent plus ni clé Claude ni corrections d'éligibilité, même à l'admin", async () => {
  mockFetch((url) => ({ body: url === "/api/me" ? { ...ME, role: "admin" } : SETTINGS }));
  renderWithProviders(<SettingsPage />);
  expect(await screen.findByRole("heading", { level: 1, name: "Réglages" })).toBeInTheDocument();
  expect(screen.queryByText(/clé API/i)).toBeNull();
  expect(screen.queryByText(/Éligibilité PEA/)).toBeNull();
});
```

- [ ] **Step 3: Vérifier l'échec**

Run: `cd frontend && npx vitest --run src/features/settings`
Expected: FAIL (modules `./ProfileCard` … introuvables).

- [ ] **Step 4: Cartes** — `frontend/src/features/settings/ProfileCard.tsx` :

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useMe } from "@/features/auth/useMe";
import { ApiError, apiSend, type Me } from "@/lib/api/client";

export function ProfileCard() {
  const { me } = useMe();
  if (!me) return null;
  return <ProfileForm me={me} />;
}

function ProfileForm({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const [first, setFirst] = useState(me.first_name);
  const [last, setLast] = useState(me.last_name);
  const save = useMutation({
    mutationFn: () => apiSend("PATCH", "/api/me", { first_name: first, last_name: last }) as Promise<Me>,
    onSuccess: (updated) => queryClient.setQueryData(["me"], updated),
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Profil</CardTitle></CardHeader>
      <CardContent>
        <form className="grid max-w-xl gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <label className="text-sm">Prénom
            <Input className="mt-1 bg-white" value={first} onChange={(e) => setFirst(e.target.value)} required maxLength={100} />
          </label>
          <label className="text-sm">Nom
            <Input className="mt-1 bg-white" value={last} onChange={(e) => setLast(e.target.value)} required maxLength={100} />
          </label>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" disabled={save.isPending}>Enregistrer le profil</Button>
            {save.isSuccess && <p role="status" className="text-sm text-muted-foreground">Profil enregistré.</p>}
            {save.error && <p role="alert" className="text-sm text-destructive">{(save.error as ApiError).message}</p>}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
```

`PasswordCard.tsx` :

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PasswordField } from "@/features/auth/PasswordField";
import { useMe } from "@/features/auth/useMe";
import { ApiError, apiSend } from "@/lib/api/client";

export function PasswordCard() {
  const { me } = useMe();
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const save = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/password", {
      ...(me?.has_password ? { current_password: current } : {}), new_password: next,
    }) as Promise<{ message: string }>,
    onSuccess: () => {
      setCurrent("");
      setNext("");
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
  if (!me) return null;
  const label = me.has_password ? "Changer le mot de passe" : "Ajouter un mot de passe";
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Mot de passe</CardTitle>
        {!me.has_password && (
          <p className="text-sm text-muted-foreground">Vous vous connectez avec Google. Un mot de passe vous permettra aussi de vous connecter sans Google.</p>
        )}
      </CardHeader>
      <CardContent>
        <form className="grid max-w-md gap-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          {me.has_password && (
            <PasswordField label="Mot de passe actuel" value={current} onChange={setCurrent} autoComplete="current-password" />
          )}
          <PasswordField label="Nouveau mot de passe" value={next} onChange={setNext} autoComplete="new-password" />
          <p className="text-xs text-muted-foreground">12 caractères minimum. Vos autres appareils seront déconnectés.</p>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={save.isPending}>{label}</Button>
            {save.data && <p role="status" className="text-sm text-muted-foreground">{save.data.message}</p>}
            {save.error && <p role="alert" className="text-sm text-destructive">{(save.error as ApiError).message}</p>}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
```

Avant d'écrire `PasswordCard`, lire `frontend/src/features/auth/PasswordField.tsx` et adapter les props (`label`, `value`, `onChange`, `autoComplete`, éventuellement `name`/`id`) à sa signature réelle ; le libellé doit rester associé au champ (`getByLabelText`).

`EmailCard.tsx` :

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PasswordField } from "@/features/auth/PasswordField";
import { useMe } from "@/features/auth/useMe";
import { ApiError, apiSend, type Me } from "@/lib/api/client";

export function EmailCard() {
  const { me } = useMe();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [changed, setChanged] = useState<string | null>(null);
  const request = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/email", {
      new_email: email, ...(me?.has_password ? { password } : {}),
    }) as Promise<{ message: string }>,
  });
  const verify = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/email/verify", { code }) as Promise<Me>,
    onSuccess: (updated) => {
      queryClient.setQueryData(["me"], updated);
      setChanged(updated.email);
      request.reset();
      setEmail("");
      setPassword("");
      setCode("");
    },
  });
  if (!me) return null;
  const error = (request.error ?? verify.error) as ApiError | null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Adresse mail</CardTitle>
        <p className="text-sm text-muted-foreground">Adresse actuelle : {me.email}</p>
      </CardHeader>
      <CardContent className="max-w-md space-y-3">
        {!request.isSuccess ? (
          <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); request.mutate(); }}>
            <label className="text-sm">Nouvelle adresse
              <Input className="mt-1 bg-white" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            {me.has_password && <PasswordField label="Mot de passe" value={password} onChange={setPassword} autoComplete="current-password" />}
            <div><Button type="submit" disabled={request.isPending}>Recevoir un code</Button></div>
          </form>
        ) : (
          <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); verify.mutate(); }}>
            <p role="status" className="text-sm text-muted-foreground">{request.data?.message}</p>
            <label className="text-sm">Code reçu
              <Input className="mt-1 w-40 bg-white" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                     value={code} onChange={(e) => setCode(e.target.value)} required />
            </label>
            <div className="flex gap-2">
              <Button type="submit" disabled={verify.isPending}>Valider la nouvelle adresse</Button>
              <Button type="button" variant="outline" onClick={() => request.reset()}>Annuler</Button>
            </div>
          </form>
        )}
        {changed && <p role="status" className="text-sm text-muted-foreground">Adresse modifiée : {changed}</p>}
        {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
      </CardContent>
    </Card>
  );
}
```

`DevicesCard.tsx` :

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, apiSend, type SessionItem } from "@/lib/api/client";

const when = (iso: string) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });

export function DevicesCard() {
  const queryClient = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => apiGet<SessionItem[]>("/api/me/sessions") });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["sessions"] });
  const revoke = useMutation({
    mutationFn: (session: SessionItem) => apiSend("DELETE", `/api/me/sessions/${session.id}`),
    onSuccess: (_data, session) => (session.current ? queryClient.clear() : refresh()),
  });
  const revokeOthers = useMutation({ mutationFn: () => apiSend("DELETE", "/api/me/sessions"), onSuccess: refresh });
  const others = (sessions.data ?? []).filter((s) => !s.current).length;
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Appareils connectés</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <ul className="divide-y divide-border">
          {(sessions.data ?? []).map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-4 py-2">
              <div className="min-w-0">
                <p className="flex items-center gap-2 font-medium">{s.device}{s.current && <Badge variant="secondary">Cet appareil</Badge>}</p>
                <p className="text-xs text-muted-foreground">Dernière activité le {when(s.last_seen_at)}{s.ip ? ` · réseau ${s.ip}` : ""}</p>
              </div>
              <Button size="sm" variant="outline" aria-label={`Déconnecter ${s.device}`} disabled={revoke.isPending}
                      onClick={() => revoke.mutate(s)}>Déconnecter</Button>
            </li>
          ))}
        </ul>
        {others > 0 && (
          <Button variant="outline" disabled={revokeOthers.isPending} onClick={() => revokeOthers.mutate()}>Déconnecter tous les autres</Button>
        )}
      </CardContent>
    </Card>
  );
}
```

Vérifier que `Badge` accepte `variant="secondary"` (`badgeVariants` dans `components/ui/badge.tsx`) ; sinon prendre une variante existante.

- [ ] **Step 5: Page Réglages** — créer `frontend/src/features/admin/EligibilityOverridesCard.tsx` en y **déplaçant** `OverrideRow` et `EligibilityOverridesCard` de `SettingsPage.tsx` (même code, `export function EligibilityOverridesCard`). Remplacer `SettingsPage.tsx` par :

```tsx
import { usePageMeta } from "@/seo/usePageMeta";
import { DevicesCard } from "./DevicesCard";
import { EmailCard } from "./EmailCard";
import { FeeSettingsCard } from "./FeeSettingsCard";
import { PasswordCard } from "./PasswordCard";
import { ProfileCard } from "./ProfileCard";

export function SettingsPage() {
  usePageMeta({ title: "Réglages", description: "Votre profil, vos appareils et les frais de votre caisse régionale.", noindex: true });
  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Réglages</h1>
        <p className="mt-1 text-sm text-muted-foreground">Votre profil, vos appareils connectés et les frais de votre caisse régionale.</p>
      </header>
      <ProfileCard />
      <PasswordCard />
      <EmailCard />
      <DevicesCard />
      <FeeSettingsCard />
    </section>
  );
}
```

Supprimer `AssistantSettingsCard.tsx` et `AssistantSettingsCard.test.tsx`.

- [ ] **Step 6: Vérifier**

Run: `cd frontend && npx vitest --run src/features/settings && npx tsc -b`
Expected: PASS ; `tsc` échoue encore seulement dans `features/assistant` (type `AssistantSettingsOut` supprimé), corrigé à la Task 8.

- [ ] **Step 7: Commit**

```bash
git add -A frontend/src
git commit -m "feat: settings split into profile, password, email and devices cards"
```

---

### Task 8: Assistant — Premium, limite, configuration

**Files:**
- Modify: `frontend/src/features/assistant/api.ts`, `ChatView.tsx`, `ChatView.test.tsx`, `AssistantPage.test.tsx`, `AssistantPanel.test.tsx`, `frontend/src/app/router.test.tsx`

**Interfaces:**
- Consumes: `GET /api/assistant/status` (`AssistantStatus`)
- Produces: `useAssistantStatus()` ; `ChatView` affiche une carte selon `reason`

- [ ] **Step 1: Tests qui échouent** — dans `ChatView.test.tsx`, remplacer `CONFIGURED` et le test « sans clé API » par :

```tsx
const AVAILABLE = { available: true, reason: null, spent_usd: 0.5, limit_usd: 5, model: "Claude Opus 5 (recommandé)" };

test("non Premium : carte « Réservé aux membres Premium »", async () => {
  stubFetch((url) => (url === "/api/assistant/status" ? json({ ...AVAILABLE, available: false, reason: "premium" }) : undefined));
  renderChat();
  expect(await screen.findByText("Réservé aux membres Premium")).toBeInTheDocument();
  expect(screen.getByText(/abonnement arrivera bientôt/)).toBeInTheDocument();
  expect(screen.queryByRole("textbox")).toBeNull();
});

test("limite du mois atteinte", async () => {
  stubFetch((url) => (url === "/api/assistant/status" ? json({ ...AVAILABLE, available: false, reason: "limit_reached", spent_usd: 5 }) : undefined));
  renderChat();
  expect(await screen.findByText("Limite du mois atteinte")).toBeInTheDocument();
  expect(screen.getByText(/5,00 \$ sur 5,00 \$/)).toBeInTheDocument();
});

test("clé Claude absente du serveur", async () => {
  stubFetch((url) => (url === "/api/assistant/status" ? json({ ...AVAILABLE, available: false, reason: "not_configured" }) : undefined));
  renderChat();
  expect(await screen.findByText("Assistant pas encore configuré")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Ouvrir les Réglages" })).toBeNull();
});
```

`renderChat`, `stubFetch` et `json` sont les helpers déjà présents dans ce fichier (adapter les noms si besoin). Dans tous les autres tests de ce fichier, et dans `AssistantPage.test.tsx`, `AssistantPanel.test.tsx`, `router.test.tsx`, remplacer `"/api/assistant/settings"` par `"/api/assistant/status"` et le corps `{ configured: true, … }` par `AVAILABLE` (ou l'objet équivalent écrit en ligne).

- [ ] **Step 2: Vérifier l'échec**

Run: `cd frontend && npx vitest --run src/features/assistant`
Expected: FAIL (textes absents).

- [ ] **Step 3: Implémentation** — dans `api.ts`, remplacer `useAssistantSettings` par :

```ts
export const useAssistantStatus = () =>
  useQuery({ queryKey: ["assistant-status"], queryFn: () => apiGet<AssistantStatus>("/api/assistant/status") });
```

(import `type AssistantStatus` au lieu de `AssistantSettingsOut`). Dans `useChat.ts`, à la fin d'une réponse (événement `done`) et sur une erreur 429, invalider `["assistant-status"]` pour rafraîchir le coût du mois : ajouter `queryClient.invalidateQueries({ queryKey: ["assistant-status"] })` là où `["conversations"]` est déjà invalidé.

Dans `ChatView.tsx`, remplacer `const settings = useAssistantSettings();` par `const status = useAssistantStatus();` et le bloc `if (settings.isPending) … if (!settings.data?.configured) { … }` par :

```tsx
  if (status.isPending) return <Skeleton className="h-40 w-full" />;
  if (status.data && !status.data.available) return <Unavailable status={status.data} />;
```

et ajouter en bas du fichier :

```tsx
const usd = (value: number) => value.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const UNAVAILABLE = {
  premium: {
    title: "Réservé aux membres Premium",
    text: "L'assistant IA fait partie de l'offre Premium. L'abonnement arrivera bientôt ; en attendant, l'administrateur peut activer Premium sur votre compte.",
  },
  not_configured: {
    title: "Assistant pas encore configuré",
    text: "La clé Claude n'est pas encore renseignée sur le serveur. L'administrateur doit l'ajouter dans le fichier .env (ANTHROPIC_API_KEY).",
  },
  limit_reached: { title: "Limite du mois atteinte", text: "" },
} as const;

function Unavailable({ status }: { status: AssistantStatus }) {
  const copy = UNAVAILABLE[status.reason ?? "premium"];
  return (
    <div className="rounded-xl border border-dashed border-border bg-white p-6 text-sm">
      <p className="font-medium">{copy.title}</p>
      <p className="mt-1 text-muted-foreground">
        {status.reason === "limit_reached"
          ? `Vous avez utilisé ${usd(status.spent_usd)} $ sur ${usd(status.limit_usd)} $ ce mois-ci. L'assistant sera de nouveau disponible le 1er du mois prochain.`
          : copy.text}
      </p>
    </div>
  );
}
```

Retirer l'import de `Link` s'il ne sert plus. Afficher aussi, sous la zone de saisie quand l'assistant est disponible, une ligne discrète : `Modèle : {status.data.model} · ce mois-ci : {usd(spent)} $ sur {usd(limit)} $` (classe `text-xs text-muted-foreground`), pour que la limite ne soit pas une surprise.

- [ ] **Step 4: Vérifier**

Run: `cd frontend && npx vitest --run && npx tsc -b && npm run lint`
Expected: PASS, aucune erreur de type ni de lint.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src
git commit -m "feat: assistant explains premium, missing key and monthly limit instead of asking for a key"
```

---

### Task 9: Onglet Admin

**Files:**
- Create: `frontend/src/features/auth/RequireAdmin.tsx`, `frontend/src/features/admin/AdminPage.tsx`, `UsersCard.tsx`, `EditUserDialog.tsx`, `DeleteUserDialog.tsx`, `AssistantAdminCard.tsx`, `ConfigStatusCard.tsx`, `AdminPage.test.tsx`
- Modify: `frontend/src/app/Sidebar.tsx`, `Sidebar.test.tsx`, `Layout.tsx`, `router.tsx`, `router.test.tsx`

**Interfaces:**
- Consumes: `/api/admin/*`, `EligibilityOverridesCard` (Task 7), `useMe`
- Produces: route `/admin` (admins seulement, sinon page 404), entrée « Admin » dans la barre latérale pour les admins

- [ ] **Step 1: Tests qui échouent** — `frontend/src/features/admin/AdminPage.test.tsx` :

```tsx
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { AdminPage } from "./AdminPage";

vi.mock("./EligibilityOverridesCard", () => ({ EligibilityOverridesCard: () => null }));
afterEach(() => vi.unstubAllGlobals());

const ADMIN = { ...ME, role: "admin", has_premium: true };
const PAUL = { id: "u2", email: "paul@example.com", first_name: "Paul", last_name: "Martin", role: "user",
  is_premium: false, verified: true, has_password: true, has_google: false, created_at: "2026-09-01T08:00:00Z", last_login_at: null };
const LIST = { items: [PAUL], total: 1, page: 1, page_size: 50 };
const SETTINGS = { ai_model: "claude-opus-5", ai_monthly_cost_limit_usd: 5, models: [
  { id: "claude-opus-5", label: "Claude Opus 5 (recommandé)" }, { id: "claude-haiku-4-5", label: "Claude Haiku 4.5 (économique)" }] };
const STATUS = { claude: true, smtp: true, google: false, turnstile: false, app_secret: true, admin_email: true };

function api(overrides: Record<string, unknown> = {}) {
  return mockFetch((url) => {
    if (url in overrides) return { body: overrides[url] };
    if (url === "/api/me") return { body: ADMIN };
    if (url.startsWith("/api/admin/users?")) return { body: LIST };
    if (url === "/api/admin/settings") return { body: SETTINGS };
    if (url === "/api/admin/config-status") return { body: STATUS };
    return { body: {} };
  });
}

const bodyOf = (fetchMock: ReturnType<typeof mockFetch>, url: string, method: string) =>
  JSON.parse(String(fetchMock.mock.calls.find(([u, init]) => String(u) === url && init?.method === method)?.[1]?.body));

test("liste les inscrits, cherche et trie côté serveur", async () => {
  const fetchMock = api();
  renderWithProviders(<AdminPage />);
  expect(await screen.findByText("paul@example.com")).toBeInTheDocument();
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher un utilisateur" }), "hélène");
  await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes("q=h%C3%A9l%C3%A8ne"))).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: /Mail/ }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => /sort=email&order=asc/.test(String(u)))).toBe(true));
});

test("bascule Premium dans le tableau", async () => {
  const fetchMock = api({ "/api/admin/users/u2": { ...PAUL, is_premium: true } });
  renderWithProviders(<AdminPage />);
  await userEvent.click(await screen.findByRole("switch", { name: "Premium pour Paul Martin" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/admin/users/u2", "PATCH")).toEqual({ is_premium: true }));
});

test("modifie un compte", async () => {
  const fetchMock = api({ "/api/admin/users/u2": PAUL });
  renderWithProviders(<AdminPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Modifier Paul Martin" }));
  const dialog = await screen.findByRole("dialog");
  const last = within(dialog).getByLabelText("Nom");
  await userEvent.clear(last);
  await userEvent.type(last, "Durand");
  await userEvent.selectOptions(within(dialog).getByLabelText("Rôle"), "admin");
  await userEvent.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/admin/users/u2", "PATCH"))
    .toEqual({ first_name: "Paul", last_name: "Durand", email: "paul@example.com", role: "admin", is_premium: false }));
});

test("supprime seulement après avoir retapé le mail", async () => {
  const fetchMock = api({ "/api/admin/users/u2": null });
  renderWithProviders(<AdminPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer Paul Martin" }));
  const dialog = await screen.findByRole("dialog");
  const confirm = within(dialog).getByRole("button", { name: "Supprimer définitivement" });
  expect(confirm).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText("Retapez l'adresse mail pour confirmer"), "paul@example.com");
  await userEvent.click(confirm);
  await waitFor(() => expect(bodyOf(fetchMock, "/api/admin/users/u2", "DELETE")).toEqual({ confirm_email: "paul@example.com" }));
});

test("règle l'assistant et affiche l'état de la configuration sans valeur", async () => {
  const fetchMock = api();
  renderWithProviders(<AdminPage />);
  await userEvent.selectOptions(await screen.findByLabelText("Modèle par défaut"), "claude-haiku-4-5");
  const limit = screen.getByLabelText("Limite mensuelle par utilisateur ($)");
  await userEvent.clear(limit);
  await userEvent.type(limit, "10");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer les réglages de l'assistant" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/admin/settings", "PUT"))
    .toEqual({ ai_model: "claude-haiku-4-5", ai_monthly_cost_limit_usd: 10 }));
  const status = screen.getByRole("list", { name: "État de la configuration" });
  expect(within(status).getByText("Claude").closest("li")).toHaveTextContent("Renseigné");
  expect(within(status).getByText("Google").closest("li")).toHaveTextContent("Manquant");
  await userEvent.click(screen.getByRole("button", { name: "Envoyer un mail de test" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/admin/test-email", expect.objectContaining({ method: "POST" })));
  expect(screen.getByRole("link", { name: "Documentation admin" })).toHaveAttribute("href", "/documentation/");
});
```

Dans `Sidebar.test.tsx`, garder le test des sept entrées (sans `admin`) et ajouter :

```tsx
test("ajoute l'entrée Admin pour un administrateur", () => {
  render(<MemoryRouter><Sidebar admin /></MemoryRouter>);
  const nav = screen.getByRole("navigation", { name: "Navigation principale" });
  expect(Array.from(nav.querySelectorAll("a")).map((a) => a.textContent).at(-1)).toBe("Admin");
});
```

et remplacer le test « … mais pas vers la documentation admin » par le même test (la barre latérale ne lie toujours pas `/documentation/` : le lien est dans la page Admin).

Dans `router.test.tsx`, ajouter (en suivant le style des tests de redirection existants) : un utilisateur `role: "user"` qui ouvre `/admin` voit la page 404 ; un admin voit `h1` « Admin ».

- [ ] **Step 2: Vérifier l'échec**

Run: `cd frontend && npx vitest --run src/features/admin src/app`
Expected: FAIL.

- [ ] **Step 3: Garde de route** — `frontend/src/features/auth/RequireAdmin.tsx` :

```tsx
import { Outlet } from "react-router";
import { NotFoundPage } from "@/app/NotFoundPage";
import { useMe } from "./useMe";

/** Onglet Admin : un non-admin voit une page introuvable (on ne révèle pas son existence). */
export function RequireAdmin() {
  const { me, isPending } = useMe();
  if (isPending) return null;
  return me?.role === "admin" ? <Outlet /> : <NotFoundPage />;
}
```

Dans `router.tsx`, à l'intérieur des enfants de `RequireAuth` :

```tsx
          {
            element: <RequireAdmin />,
            children: [{ path: "admin", lazy: async () => ({ Component: (await import("@/features/admin/AdminPage")).AdminPage }) }],
          },
```

- [ ] **Step 4: Barre latérale** — dans `Sidebar.tsx`, importer `ShieldCheck` de `lucide-react`, ajouter la prop `admin?: boolean`, et construire la liste :

```tsx
export const ADMIN_ITEM = { to: "/admin", label: "Admin", icon: ShieldCheck, end: false };

export function Sidebar({ footer, account, admin = false }: { footer?: ReactNode; account?: ReactNode; admin?: boolean }) {
  const items = admin ? [...NAV_ITEMS, ADMIN_ITEM] : NAV_ITEMS;
```

et itérer sur `items` au lieu de `NAV_ITEMS`. Mettre à jour le commentaire : « La documentation admin (/documentation/) est liée depuis la page Admin, pas d'ici. » Dans `Layout.tsx` : `const { me } = useMe();` puis `<Sidebar … admin={me?.role === "admin"} />`.

- [ ] **Step 5: Page Admin** — `frontend/src/features/admin/AdminPage.tsx` :

```tsx
import { usePageMeta } from "@/seo/usePageMeta";
import { AssistantAdminCard } from "./AssistantAdminCard";
import { ConfigStatusCard } from "./ConfigStatusCard";
import { EligibilityOverridesCard } from "./EligibilityOverridesCard";
import { UsersCard } from "./UsersCard";

export function AdminPage() {
  usePageMeta({ title: "Admin", description: "Utilisateurs, assistant IA et configuration.", noindex: true });
  return (
    <section className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin</h1>
          <p className="mt-1 text-sm text-muted-foreground">Utilisateurs, assistant IA et configuration du serveur.</p>
        </div>
        <a href="/documentation/" className="text-sm font-medium text-primary">Documentation admin</a>
      </header>
      <UsersCard />
      <div className="grid gap-6 lg:grid-cols-2">
        <AssistantAdminCard />
        <ConfigStatusCard />
      </div>
      <EligibilityOverridesCard />
    </section>
  );
}
```

`UsersCard.tsx` :

```tsx
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, apiSend, type AdminUser, type AdminUserList } from "@/lib/api/client";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { DeleteUserDialog } from "./DeleteUserDialog";
import { EditUserDialog } from "./EditUserDialog";

type Sort = "email" | "first_name" | "last_name" | "role" | "is_premium" | "verified" | "created_at" | "last_login_at";
const COLUMNS: { key: Sort; label: string }[] = [
  { key: "first_name", label: "Prénom" }, { key: "last_name", label: "Nom" }, { key: "email", label: "Mail" },
  { key: "role", label: "Rôle" }, { key: "is_premium", label: "Premium" }, { key: "verified", label: "Validé" },
  { key: "created_at", label: "Inscription" }, { key: "last_login_at", label: "Dernière connexion" },
];
const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "—");
const methods = (u: AdminUser) => [u.has_password && "Mot de passe", u.has_google && "Google"].filter(Boolean).join(", ") || "—";

export function UsersCard() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const q = useDebouncedValue(search.trim(), 300);
  const [sort, setSort] = useState<Sort>("created_at");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [deleting, setDeleting] = useState<AdminUser | null>(null);
  const users = useQuery({
    queryKey: ["admin-users", q, sort, order, page],
    queryFn: () => apiGet<AdminUserList>("/api/admin/users", { q, sort, order, page }),
    placeholderData: keepPreviousData,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  const premium = useMutation({
    mutationFn: (u: AdminUser) => apiSend("PATCH", `/api/admin/users/${u.id}`, { is_premium: !u.is_premium }),
    onSettled: refresh,
  });
  const sortBy = (key: Sort) => {
    setOrder(key === sort && order === "asc" ? "desc" : "asc");
    setSort(key);
    setPage(1);
  };
  const data = users.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Utilisateurs{data ? ` (${data.total})` : ""}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input type="search" aria-label="Rechercher un utilisateur" placeholder="Mail, nom ou prénom…" className="w-96 bg-white"
               value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        <Table>
          <TableHeader>
            <TableRow>
              {COLUMNS.map(({ key, label }) => (
                <TableHead key={key} aria-sort={sort === key ? (order === "asc" ? "ascending" : "descending") : undefined}>
                  <button type="button" className="inline-flex items-center gap-1" onClick={() => sortBy(key)}>
                    {label}
                    {sort === key && (order === "asc" ? <ArrowUp className="size-3" aria-hidden /> : <ArrowDown className="size-3" aria-hidden />)}
                  </button>
                </TableHead>
              ))}
              <TableHead>Connexion</TableHead>
              <TableHead><span className="sr-only">Actions</span></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.map((u) => {
              const name = `${u.first_name} ${u.last_name}`;
              return (
                <TableRow key={u.id}>
                  <TableCell>{u.first_name}</TableCell>
                  <TableCell>{u.last_name}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>{u.role === "admin" ? "Admin" : "Utilisateur"}</TableCell>
                  <TableCell>
                    <input type="checkbox" role="switch" aria-label={`Premium pour ${name}`} className="size-4 accent-primary"
                           checked={u.is_premium || u.role === "admin"} disabled={u.role === "admin" || premium.isPending}
                           onChange={() => premium.mutate(u)} />
                  </TableCell>
                  <TableCell>{u.verified ? "Oui" : "Non"}</TableCell>
                  <TableCell>{date(u.created_at)}</TableCell>
                  <TableCell>{date(u.last_login_at)}</TableCell>
                  <TableCell>{methods(u)}</TableCell>
                  <TableCell className="space-x-2 whitespace-nowrap text-right">
                    <Button size="sm" variant="outline" aria-label={`Modifier ${name}`} onClick={() => setEditing(u)}>Modifier</Button>
                    <Button size="sm" variant="outline" aria-label={`Supprimer ${name}`} onClick={() => setDeleting(u)}>Supprimer</Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {data && data.items.length === 0 && <p className="text-sm text-muted-foreground">Aucun utilisateur trouvé.</p>}
        {pages > 1 && (
          <div className="flex items-center gap-3 text-sm">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Précédent</Button>
            <span>Page {page} sur {pages}</span>
            <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Suivant</Button>
          </div>
        )}
      </CardContent>
      <EditUserDialog user={editing} onClose={() => { setEditing(null); refresh(); }} />
      <DeleteUserDialog user={deleting} onClose={() => { setDeleting(null); refresh(); }} />
    </Card>
  );
}
```

Pour un admin, la case Premium est cochée et désactivée (toujours Premium). Vérifier que `apiGet` accepte bien des paramètres `number` (oui : `Record<string, string | number | undefined>`).

`EditUserDialog.tsx` :

```tsx
import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError, apiSend, type AdminUser } from "@/lib/api/client";

export function EditUserDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", role: "user", is_premium: false });
  useEffect(() => {
    if (user) setForm({ first_name: user.first_name, last_name: user.last_name, email: user.email, role: user.role, is_premium: user.is_premium });
  }, [user]);
  const save = useMutation({
    mutationFn: () => apiSend("PATCH", `/api/admin/users/${user!.id}`, form),
    onSuccess: onClose,
  });
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [key]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value });
  return (
    <Dialog open={user !== null} onOpenChange={(open) => { if (!open) { save.reset(); onClose(); } }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Modifier le compte</DialogTitle>
          <DialogDescription>Changer l'adresse la marque comme validée ; l'ancienne et la nouvelle adresse sont prévenues.</DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <label className="text-sm">Prénom<Input className="mt-1" value={form.first_name} onChange={set("first_name")} required /></label>
          <label className="text-sm">Nom<Input className="mt-1" value={form.last_name} onChange={set("last_name")} required /></label>
          <label className="text-sm">Mail<Input className="mt-1" type="email" value={form.email} onChange={set("email")} required /></label>
          <label className="text-sm">Rôle
            <select className="mt-1 h-9 w-full rounded-lg border border-input bg-white px-2 text-sm" value={form.role} onChange={set("role")}>
              <option value="user">Utilisateur</option>
              <option value="admin">Admin</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-primary" checked={form.is_premium} onChange={set("is_premium")} />Premium
          </label>
          {save.error && <p role="alert" className="text-sm text-destructive">{(save.error as ApiError).message}</p>}
          <Button type="submit" disabled={save.isPending}>Enregistrer</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

`DeleteUserDialog.tsx` :

```tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError, apiSend, type AdminUser } from "@/lib/api/client";

export function DeleteUserDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const [typed, setTyped] = useState("");
  const remove = useMutation({
    mutationFn: () => apiSend("DELETE", `/api/admin/users/${user!.id}`, { confirm_email: typed }),
    onSuccess: () => { setTyped(""); onClose(); },
  });
  const matches = user !== null && typed.trim().toLowerCase() === user.email;
  return (
    <Dialog open={user !== null} onOpenChange={(open) => { if (!open) { setTyped(""); remove.reset(); onClose(); } }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Supprimer {user?.first_name} {user?.last_name} ?</DialogTitle>
          <DialogDescription>
            Le compte et toutes ses données (ordres, favoris, conversations, réglages) seront supprimés définitivement.
            Un mail le confirmera à {user?.email}.
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); remove.mutate(); }}>
          <label className="text-sm">Retapez l'adresse mail pour confirmer
            <Input className="mt-1" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
          </label>
          {remove.error && <p role="alert" className="text-sm text-destructive">{(remove.error as ApiError).message}</p>}
          <Button type="submit" variant="destructive" disabled={!matches || remove.isPending}>Supprimer définitivement</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

Vérifier que `buttonVariants` a une variante `destructive` ; sinon utiliser la variante par défaut avec `className="bg-destructive text-white"`.

`AssistantAdminCard.tsx` :

```tsx
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, apiGet, apiSend, type AdminSettings } from "@/lib/api/client";

export function AssistantAdminCard() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["admin-settings"], queryFn: () => apiGet<AdminSettings>("/api/admin/settings") });
  const [model, setModel] = useState("");
  const [limit, setLimit] = useState("");
  useEffect(() => {
    if (settings.data) {
      setModel(settings.data.ai_model);
      setLimit(String(settings.data.ai_monthly_cost_limit_usd).replace(".", ","));
    }
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () => apiSend("PUT", "/api/admin/settings", {
      ai_model: model, ai_monthly_cost_limit_usd: Number(limit.trim().replace(",", ".")),
    }) as Promise<AdminSettings>,
    onSuccess: (data) => {
      queryClient.setQueryData(["admin-settings"], data);
      queryClient.invalidateQueries({ queryKey: ["assistant-status"] });
    },
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Assistant IA</CardTitle>
        <p className="text-sm text-muted-foreground">La clé Claude se règle uniquement dans le fichier .env (ANTHROPIC_API_KEY).</p>
      </CardHeader>
      <CardContent>
        <form className="grid max-w-sm gap-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <label className="text-sm">Modèle par défaut
            <select className="mt-1 h-9 w-full rounded-lg border border-input bg-white px-2 text-sm" value={model} onChange={(e) => setModel(e.target.value)}>
              {settings.data?.models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </label>
          <label className="text-sm">Limite mensuelle par utilisateur ($)
            <Input className="mt-1 w-32 bg-white" inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value)} required />
          </label>
          <p className="text-xs text-muted-foreground">Une fois la limite atteinte, l'assistant refuse les nouvelles questions jusqu'au 1er du mois suivant.</p>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={save.isPending || !settings.data}>Enregistrer les réglages de l'assistant</Button>
            {save.isSuccess && <p role="status" className="text-sm text-muted-foreground">Enregistré.</p>}
            {save.error && <p role="alert" className="text-sm text-destructive">{(save.error as ApiError).message}</p>}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
```

`ConfigStatusCard.tsx` :

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, apiGet, apiSend, type ConfigStatus } from "@/lib/api/client";

const ITEMS: { key: keyof ConfigStatus; label: string; variables: string }[] = [
  { key: "claude", label: "Claude", variables: "ANTHROPIC_API_KEY" },
  { key: "smtp", label: "Envoi des mails", variables: "SMTP_HOST, SMTP_USER, SMTP_PASSWORD" },
  { key: "google", label: "Google", variables: "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET" },
  { key: "turnstile", label: "Turnstile", variables: "TURNSTILE_SITE_KEY, TURNSTILE_SECRET_KEY" },
  { key: "app_secret", label: "Secret de l'application", variables: "APP_SECRET" },
  { key: "admin_email", label: "Adresse de l'admin", variables: "ADMIN_EMAIL" },
];

export function ConfigStatusCard() {
  const status = useQuery({ queryKey: ["config-status"], queryFn: () => apiGet<ConfigStatus>("/api/admin/config-status") });
  const test = useMutation({ mutationFn: () => apiSend("POST", "/api/admin/test-email") as Promise<{ message: string }> });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">État de la configuration</CardTitle>
        <p className="text-sm text-muted-foreground">Ce qui est renseigné dans le fichier .env. Aucune valeur n'est affichée.</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul aria-label="État de la configuration" className="divide-y divide-border text-sm">
          {ITEMS.map(({ key, label, variables }) => {
            const ok = status.data?.[key];
            return (
              <li key={key} className="flex items-center justify-between gap-4 py-2">
                <div>
                  <p className="font-medium">{label}</p>
                  <p className="text-xs text-muted-foreground">{variables}</p>
                </div>
                {status.data && (
                  <span className={ok ? "flex items-center gap-1 text-emerald-700" : "flex items-center gap-1 text-muted-foreground"}>
                    {ok ? <Check className="size-4" aria-hidden /> : <X className="size-4" aria-hidden />}
                    {ok ? "Renseigné" : "Manquant"}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
        <div className="flex items-center gap-3">
          <Button variant="outline" disabled={test.isPending} onClick={() => test.mutate()}>Envoyer un mail de test</Button>
          {test.data && <p role="status" className="text-sm text-muted-foreground">{test.data.message}</p>}
          {test.error && <p role="alert" className="text-sm text-destructive">{(test.error as ApiError).message}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: Vérifier**

Run: `cd frontend && npx vitest --run && npx tsc -b && npm run lint && npm run build`
Expected: PASS, build sans erreur.

- [ ] **Step 7: Commit**

```bash
git add -A frontend/src
git commit -m "feat: admin tab with users, premium switch, assistant settings and configuration status"
```

**Fin du Bloc 3 : s'arrêter pour que l'utilisateur compacte.**

---

# Bloc 4 — nginx, bout en bout, documentation

### Task 10: `/documentation/` réservée aux admins

**Files:**
- Modify: `frontend/nginx/default.conf.template`, `frontend/e2e/headers.spec.ts`
- Create: `frontend/e2e/admin.spec.ts`

**Interfaces:**
- Consumes: `GET /api/auth/admin-check` (Task 4)

- [ ] **Step 1: Test e2e qui échoue** — `frontend/e2e/admin.spec.ts` :

```ts
import { expect, test } from "@playwright/test";

test("la documentation admin renvoie un visiteur vers la connexion", async ({ page }) => {
  await page.goto("/documentation/");
  await expect(page).toHaveURL(/\/connexion\?suite=%2Fdocumentation%2F$/);
});

test("la documentation admin refuse aussi ses fichiers à un visiteur", async ({ request }) => {
  const response = await request.get("/documentation/README.md", { maxRedirects: 0 });
  expect(response.status()).toBe(302);
});

test("le guide et les fichiers Docsify communs restent publics", async ({ request }) => {
  expect((await request.get("/guide/")).status()).toBe(200);
  expect((await request.get("/docsify/theme.css")).status()).toBe(200);
});

test("un visiteur ne voit pas l'onglet Admin", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
});
```

Dans `headers.spec.ts`, retirer `"/documentation/"` de la boucle des violations CSP (Ruling 9).

Vérifier le nom réel du fichier d'accueil de la doc (`frontend/public/documentation/README.md`) et l'adapter dans le test si besoin.

- [ ] **Step 2: Vérifier l'échec**

```bash
docker compose up -d --build --wait web api worker && docker compose restart web
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --wait api worker && docker compose restart web
cd frontend && npx playwright test e2e/admin.spec.ts
```

Expected: FAIL (la documentation répond 200).

- [ ] **Step 3: nginx** — dans `frontend/nginx/default.conf.template`, remplacer le bloc Docsify par :

```nginx
  # Guide utilisateur (/guide/) et fichiers communs (/docsify/) : publics.
  # Documentation admin (/documentation/) : nginx demande à l'API si la session est admin (auth_request).
  # Redirection relative : le port publié (8095) n'est pas celui d'écoute de nginx (80).
  absolute_redirect off;
  location ~ ^/(guide|documentation)$ { return 301 /$1/; }
  location ~ ^/(guide|docsify)/ {
    default_type text/markdown;  # .md absent de mime.types
    charset utf-8;
    charset_types text/markdown text/css application/javascript;
    try_files $uri $uri/ =404;
  }
  location /documentation/ {
    auth_request /_admin_check;
    error_page 401 403 = @connexion_admin;
    add_header Cache-Control "no-store" always;
    include /etc/nginx/security-headers.conf;
    default_type text/markdown;
    charset utf-8;
    charset_types text/markdown text/css application/javascript;
    try_files $uri $uri/ =404;
  }
  location = /_admin_check {
    internal;
    proxy_pass http://api:8000/api/auth/admin-check;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
  }
  location @connexion_admin {
    return 302 /connexion?suite=%2Fdocumentation%2F;
  }
```

(`add_header` dans ce `location` impose de ré-inclure `security-headers.conf`, comme pour `/assets/`.) Côté API, `/api/auth/admin-check` est un `GET` : pas de CSRF. Le cookie `pea_session` est transmis par défaut par `proxy_pass`.

Vérifier que `loginPath` / l'écran de connexion accepte `suite=/documentation/` et, après connexion, fait une **navigation complète** (`window.location.assign`) plutôt qu'une navigation React, puisque `/documentation/` est hors du routeur : lire `frontend/src/features/auth/redirect.ts`. Si `suite` n'accepte que les routes React ou navigue avec `navigate()`, ajouter : « une `suite` qui commence par `/documentation/` ou `/guide/` est ouverte avec `window.location.assign` », avec un test Vitest dans `redirect.test.ts` :

```ts
test("une suite hors de l'application est ouverte par une navigation complète", () => {
  expect(isExternalSuite("/documentation/")).toBe(true);
  expect(isExternalSuite("/portefeuille")).toBe(false);
});
```

(nom de fonction à adapter au code existant ; la fonction doit refuser `//evil.com` comme aujourd'hui).

- [ ] **Step 4: Vérifier**

```bash
docker compose up -d --build --wait web && docker compose restart web
cd frontend && npm run e2e
```

Expected: tous les tests e2e passent (34 existants moins 1 retiré, plus 4). Puis restaurer la pile normale :

```bash
docker compose up -d --wait api worker && docker compose restart web
```

Vérification manuelle : connecté en admin, `http://localhost:8095/documentation/` s'affiche ; déconnecté, redirection vers `/connexion`.

- [ ] **Step 5: Commit**

```bash
git add frontend/nginx/default.conf.template frontend/e2e frontend/src/features/auth
git commit -m "feat: admin documentation only for admins, through nginx auth_request"
```

---

### Task 11: Documentation, vérification finale, PR

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `.env.example`, `frontend/public/guide/*.md` (pages Réglages et Assistant), `frontend/public/documentation/comptes.md`, `api.md`, `base-de-donnees.md`, `installation.md`, `architecture.md`

- [ ] **Step 1: Guide utilisateur** — dans le guide (`frontend/public/guide/`) : la page des réglages décrit Profil, Mot de passe (« Ajouter un mot de passe » pour un compte Google), Adresse mail (code), Appareils connectés, Frais ; la page de l'assistant explique Premium, la limite mensuelle et le libellé « ce mois-ci : X $ sur Y $ ». Retirer toute mention de la clé API à coller dans les Réglages.

- [ ] **Step 2: Documentation admin**
  - `comptes.md` : section « Onglet Admin » (utilisateurs, recherche, tri, Premium, modification, suppression, garde-fous, mails C4/C6), « Assistant : Premium et limite de coût » (`app_settings`, `ai_usage`, mois de Paris, admins inclus, dépassement possible de la dernière réponse), « Profil et appareils », « Documentation protégée » (`auth_request`), nouveaux événements du journal (`admin_user_updated`, `admin_user_deleted`, `admin_settings_updated`, `password_changed`, `email_changed`, `session_revoked`). Remplacer « Étape suivante » par le lot `comptes-rgpd`.
  - `api.md` : routes `/api/assistant/status`, `/api/admin/*`, `/api/me` (PATCH), `/api/me/password`, `/api/me/email`, `/api/me/email/verify`, `/api/me/sessions`, `/api/auth/admin-check` ; retirer `/api/assistant/settings` ; codes `premium_required`, `ai_not_configured`, `ai_limit_reached`, `wrong_password`, `email_taken`, `self_demotion`, `last_admin`, `self_delete`, `confirm_mismatch`.
  - `base-de-donnees.md` : tables `app_settings`, `ai_usage` ; `user_settings` sans clé ni modèle.
  - `installation.md` et `README.md` : **la clé Claude se met dans `ANTHROPIC_API_KEY`** ; une clé saisie autrefois dans les Réglages a été effacée par la migration (Ruling 3). Rendre Premium un compte : onglet Admin.
  - `architecture.md` : nginx `auth_request` pour `/documentation/`.
- [ ] **Step 3: `CLAUDE.md`** — ajouter : routes admin derrière `require_admin()`, assistant derrière `require_premium()`, jamais de secret en base ni dans l'interface, `app_settings` via `get_app_settings()`, coût via `add_cost()` (jamais recalculé depuis les conversations), `/documentation/` protégée par nginx ; mettre à jour les nombres de tests.
- [ ] **Step 4: Vérification finale**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q
cd frontend && npx vitest --run && npx tsc -b && npm run lint && npm run build
```

puis la suite e2e comme à la Task 10 (et restauration de la pile). Expected : tout passe.

- [ ] **Step 5: Commit, revue, push**

```bash
git add -A CLAUDE.md README.md .env.example frontend/public
git commit -m "docs: admin tab, premium assistant with monthly limit, profile and devices, protected admin docs"
```

Revue de branche complète (skill d'exécution), corrections éventuelles, puis :

```bash
git push -u origin comptes-admin
```

PR à ouvrir par l'utilisateur : https://github.com/gbtclement/PEA/compare/comptes-securite...comptes-admin?expand=1, titre « Comptes utilisateurs : admin, Premium, réglages ».

**Fin du Bloc 4.**
