# Comptes : sécurité (Google, Turnstile, limites, HIBP, en-têtes, journal) — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter à PEA Radar la connexion avec Google, le captcha Cloudflare Turnstile, les limites de tentatives et le blocage temporaire, le refus des mots de passe ayant fuité (Have I Been Pwned), les en-têtes de sécurité nginx et le journal de sécurité.

**Architecture:** Tout reste dans le backend FastAPI existant. Trois fournisseurs externes (Google OIDC, Turnstile, HIBP) sont cachés derrière de petites interfaces injectées par dépendance FastAPI (`app/api/deps.py`) et remplacées par des faux en test. Les compteurs anti-abus et le journal vivent dans PostgreSQL (tables `rate_limit_hits` et `security_events`), purgés chaque nuit par le worker. Le flux Google est fait côté serveur (PKCE, `state`, `nonce`) avec un cookie signé de courte durée ; un nouveau compte Google n'est créé qu'après l'écran « Finaliser l'inscription » (CGU acceptées).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, httpx, `authlib` (vérification du jeton d'identité Google), React 19, react-router 7, TanStack Query, Vitest, Playwright, nginx 1.27.

**Spec:** `docs/superpowers/specs/2026-09-28-comptes-utilisateurs-design.md` (sections 2.1 Origin, 2.2 HIBP, 2.4, 2.5, 2.6, 2.7, 3.2, 3.3, 7, 8, 9, 11 étape 2).

**Branche :** `comptes-securite`, créée depuis `comptes-socle` (PR empilée : si `comptes-socle` n'est pas encore fusionnée, la PR vise `comptes-socle`).

## Global Constraints

- Interface, messages d'erreur, commentaires et docstrings en **français** ; identifiants en anglais ; commits en anglais, *conventional commits*, terminés par `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Nouvelles erreurs d'API : `{"detail": {"code", "message"}}` (helper `fail()` de `app/api/routes/auth.py`).
- **Aucun test** n'appelle Google, Cloudflare, Have I Been Pwned ni un vrai SMTP.
- Ne jamais stocker un jeton, un code, un mot de passe ni une IP complète : empreintes (`token_hash`) et IP tronquée (`truncate_ip`) seulement.
- Pas de fuite d'information : même réponse, même code HTTP, que le compte existe ou non (y compris pour les blocages).
- Limites (spec 2.4, verbatim) : connexion 10 échecs par compte en 15 min → blocage de 15 min ; 30 échecs par IP en 15 min → 429 ; captcha à la connexion après 3 échecs pour ce compte ou cette IP ; inscription 5 par IP et par heure, Turnstile toujours demandé ; envoi de code / mot de passe oublié 5 par compte et par heure, 20 par IP et par heure, Turnstile demandé pour le mot de passe oublié.
- `TURNSTILE_SECRET_KEY` vide ⇒ vérification désactivée. `GOOGLE_CLIENT_ID` ou `GOOGLE_CLIENT_SECRET` vide ⇒ bouton Google masqué et routes Google en 404.
- HIBP : k-anonymat (5 premiers caractères du SHA-1), délai 2 s, service muet ⇒ vérification ignorée.
- Journal : aucun mot de passe, code ou jeton ; conservation 12 mois.
- Ports : web 8095, API de dev 8000, Vite 5180, Mailpit 8025. Jamais 8080, 8081, 5173.
- Commandes backend **toujours dans Docker** : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q …` depuis la racine du dépôt. Frontend : `cd frontend && npx vitest --run …`.
- L'API de dev partage le volume `pgdata` et migre au démarrage : la base réelle est déjà migrée (étape 1), la nouvelle migration de cette étape est réversible et sans danger, mais on la vérifie d'abord sur une base jetable.

## Review Focus

1. **Rattachement Google d'un compte jamais validé** : si quelqu'un s'est inscrit avec l'adresse de la victime sans valider le code, puis que la victime se connecte avec Google, le mot de passe de l'inconnu doit être effacé — sinon il garde l'accès. Test : Task 6 `test_linking_an_unverified_account_drops_its_password`.
2. **Blocage identique pour une adresse inconnue** : 10 échecs sur `personne@example.com` doivent donner exactement la même réponse 429 que sur un compte réel, sinon le blocage révèle quels comptes existent. Test : Task 2 `test_lock_looks_the_same_for_unknown_addresses`.
3. **Cookie OAuth absent, falsifié ou rejoué** : un callback sans cookie, avec un `state` différent ou avec un cookie déjà consommé ne doit ouvrir aucune session. Test : Task 6 `test_callback_refuses_missing_or_mismatched_state`.
4. **Redirection ouverte par `suite` côté Google** : `/api/auth/google/start?suite=//evil.com` doit ramener sur `/`. Test : Task 6 `test_google_suite_is_kept_only_for_internal_paths`.
5. **CSP qui casse une vraie page** (Docsify, graphiques, iframe Turnstile) : aucune violation CSP dans la console sur l'app, le guide, la doc admin et l'écran de connexion. Test : Task 10 `e2e/headers.spec.ts`.

---

## File Structure

| Fichier | Responsabilité |
|---|---|
| `backend/app/models/security.py` (créé) | Tables `security_events`, `rate_limit_hits` |
| `backend/alembic/versions/b8d4f0a2c3e5_security_events_rate_limits.py` (créé) | Migration |
| `backend/app/services/security_log.py` (créé) | `log_event()`, purge 12 mois |
| `backend/app/services/ratelimit.py` (créé) | `record()`, `count()`, `over()`, `clear()`, purge |
| `backend/app/services/auth/captcha.py` (créé) | Interface captcha, Turnstile, captcha désactivé |
| `backend/app/services/auth/breach.py` (créé) | Interface HIBP, client réel, `suffix_found()` |
| `backend/app/services/auth/google.py` (créé) | Interface Google, client OIDC réel, PKCE |
| `backend/app/api/origin.py` (créé) | Dépendance `check_origin` |
| `backend/app/api/routes/google.py` (créé) | `/api/auth/google/start|callback|pending|complete` |
| `backend/app/jobs/cleanup.py` (créé) | Purge nocturne du journal et des compteurs |
| `backend/app/core/security.py` (modifié) | `sign()` / `unsign()` (cookie signé), `pkce_challenge()` |
| `backend/app/core/config.py` (modifié) | Variables Google, Turnstile, HIBP, origines de dev |
| `backend/app/api/deps.py` (modifié) | `get_captcha`, `get_breach_checker`, `get_google_client` |
| `backend/app/api/routes/auth.py` (modifié) | Limites, captcha, HIBP, journal, Origin, `/auth/config` |
| `backend/app/services/auth/accounts.py` (modifié) | `register` renvoie le compte, `promote_if_admin`, `google_sign_in`, `create_google_account` |
| `backend/app/services/mail/render.py` (modifié) | Événement `google_linked` |
| `frontend/src/features/auth/useAuthConfig.ts` (créé) | Config publique (Google, clé Turnstile) |
| `frontend/src/features/auth/GoogleButton.tsx` (créé) | Bouton « Continuer avec Google » + séparateur « ou » |
| `frontend/src/features/auth/Turnstile.tsx` (créé) | Widget Turnstile |
| `frontend/src/features/auth/FinishSignUpPage.tsx` (créé) | `/finaliser-inscription` |
| `frontend/nginx.conf` → `frontend/nginx/default.conf.template` + `frontend/nginx/security-headers.conf` | En-têtes de sécurité, HSTS par variable |
| `frontend/public/guide/config.js`, `frontend/public/documentation/config.js` (créés) | Config Docsify sortie du HTML (CSP sans `unsafe-inline` pour les scripts) |

---

# Bloc 1 — Journal, limites et captcha (backend)

### Task 1: Tables, configuration, journal et compteurs

**Files:**
- Create: `backend/app/models/security.py`, `backend/alembic/versions/b8d4f0a2c3e5_security_events_rate_limits.py`, `backend/app/services/security_log.py`, `backend/app/services/ratelimit.py`, `backend/app/jobs/cleanup.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/core/config.py`, `backend/app/jobs/scheduler.py`, `.env.example`
- Test: `backend/tests/test_security_log.py`, `backend/tests/test_ratelimit.py`

**Interfaces:**
- Produces:
  - `log_event(db, kind: str, *, now: datetime, user_id: uuid.UUID | None = None, ip: str | None = None, details: dict | None = None, actor_id: uuid.UUID | None = None) -> None` ; `EVENT_KINDS` ; `purge_events(db, now) -> int`
  - `record(db, bucket: str, value: str, now) -> None`, `count(db, bucket, value, now) -> int`, `over(db, bucket, value, now) -> bool`, `clear(db, bucket, value) -> None`, `purge_hits(db, now) -> int` ; `LIMITS: dict[str, tuple[int, timedelta]]` avec les clés `login_account`, `login_ip`, `signup_ip`, `mail_account`, `mail_ip` ; `CAPTCHA_AFTER = 3`
  - Settings : `google_client_id`, `google_client_secret`, `turnstile_site_key`, `turnstile_secret_key`, `hibp_enabled: bool = True`, `dev_origins: str = "http://localhost:5180"`

- [ ] **Step 0: Branche**

```bash
git checkout comptes-socle && git pull --ff-only && git checkout -b comptes-securite
```

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_security_log.py` :

```python
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import SecurityEvent
from app.services.security_log import log_event, purge_events
from tests.factories import make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_event_keeps_only_the_network_of_the_ip(db):
    user = make_user(db, "jean@example.com")
    log_event(db, "login_failed", now=NOW, user_id=user.id, ip="203.0.113.77", details={"method": "password"})
    event = db.scalars(select(SecurityEvent)).one()
    assert (event.kind, event.user_id, event.ip, event.details) == ("login_failed", user.id, "203.0.113.0/24",
                                                                    {"method": "password"})


def test_unknown_kind_is_refused(db):
    with pytest.raises(ValueError):
        log_event(db, "n_importe_quoi", now=NOW)


def test_events_are_kept_twelve_months(db):
    log_event(db, "logout", now=NOW - timedelta(days=366))
    log_event(db, "logout", now=NOW - timedelta(days=300))
    assert purge_events(db, NOW) == 1
    assert len(db.scalars(select(SecurityEvent)).all()) == 1
```

`backend/tests/test_ratelimit.py` :

```python
from datetime import UTC, datetime, timedelta

from app.services import ratelimit

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_count_is_a_sliding_window(db):
    for minutes in (20, 10, 1):
        ratelimit.record(db, "login_account", "Jean@Example.com", NOW - timedelta(minutes=minutes))
    assert ratelimit.count(db, "login_account", "jean@example.com", NOW) == 2  # 15 min, casse ignorée


def test_over_uses_the_limit_of_the_bucket(db):
    for _ in range(9):
        ratelimit.record(db, "login_account", "jean@example.com", NOW)
    assert not ratelimit.over(db, "login_account", "jean@example.com", NOW)
    ratelimit.record(db, "login_account", "jean@example.com", NOW)
    assert ratelimit.over(db, "login_account", "jean@example.com", NOW)


def test_buckets_and_values_are_separate_and_clear_works(db):
    ratelimit.record(db, "login_account", "a@example.com", NOW)
    ratelimit.record(db, "login_ip", "a@example.com", NOW)
    ratelimit.clear(db, "login_account", "a@example.com")
    assert ratelimit.count(db, "login_account", "a@example.com", NOW) == 0
    assert ratelimit.count(db, "login_ip", "a@example.com", NOW) == 1


def test_values_are_stored_as_hashes_and_purged_after_a_day(db):
    from sqlalchemy import select

    from app.models import RateLimitHit

    ratelimit.record(db, "login_ip", "203.0.113.5", NOW - timedelta(days=2))
    ratelimit.record(db, "login_ip", "203.0.113.5", NOW)
    assert all("203.0.113.5" not in hit.key_hash for hit in db.scalars(select(RateLimitHit)))
    assert ratelimit.purge_hits(db, NOW) == 1
```

- [ ] **Step 2: Lancer** — `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_security_log.py tests/test_ratelimit.py`
Expected: FAIL (`ImportError: cannot import name 'SecurityEvent'`).

- [ ] **Step 3: Modèles** — `backend/app/models/security.py` :

```python
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SecurityEvent(Base):
    """Journal de sécurité : jamais de mot de passe, de code ni de jeton ; IP tronquée ; 12 mois."""
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(40))
    ip: Mapped[str | None] = mapped_column(String(50))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class RateLimitHit(Base):
    """Une tentative comptée pour une limite (compte ou IP, jamais en clair). Purgée au bout d'un jour."""
    __tablename__ = "rate_limit_hits"
    __table_args__ = (Index("ix_rate_limit_hits_lookup", "bucket", "key_hash", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bucket: Mapped[str] = mapped_column(String(30))
    key_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

Ajouter `from app.models.security import RateLimitHit, SecurityEvent` et les deux noms dans `__all__` de `backend/app/models/__init__.py` (même style que les imports existants).

- [ ] **Step 4: Services** — `backend/app/services/security_log.py` :

```python
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import truncate_ip
from app.models import SecurityEvent

EVENT_KINDS = frozenset({
    "signup", "email_verified", "login_ok", "login_failed", "locked", "logout", "password_reset",
    "google_linked", "google_signup", "not_me",
})
RETENTION = timedelta(days=365)


def log_event(db: Session, kind: str, *, now: datetime, user_id: uuid.UUID | None = None, ip: str | None = None,
              details: dict | None = None, actor_id: uuid.UUID | None = None) -> None:
    """Ajoute une ligne au journal, dans la transaction en cours (pas de commit)."""
    if kind not in EVENT_KINDS:
        raise ValueError(f"Événement de sécurité inconnu : {kind}")
    db.add(SecurityEvent(kind=kind, user_id=user_id, actor_id=actor_id, ip=truncate_ip(ip), details=details or {},
                         created_at=now))


def purge_events(db: Session, now: datetime) -> int:
    return db.execute(delete(SecurityEvent).where(SecurityEvent.created_at < now - RETENTION)).rowcount
```

`backend/app/services/ratelimit.py` :

```python
"""Limites anti-abus comptées en base sur une fenêtre glissante (spec 2.4). Les valeurs ne sont stockées qu'en empreinte."""
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import token_hash
from app.models import RateLimitHit

FIFTEEN_MINUTES = timedelta(minutes=15)
ONE_HOUR = timedelta(hours=1)
LIMITS: dict[str, tuple[int, timedelta]] = {
    "login_account": (10, FIFTEEN_MINUTES),  # échecs de connexion par adresse → blocage
    "login_ip": (30, FIFTEEN_MINUTES),       # échecs de connexion par IP → 429
    "signup_ip": (5, ONE_HOUR),              # inscriptions par IP
    "mail_account": (5, ONE_HOUR),           # codes et liens envoyés par adresse
    "mail_ip": (20, ONE_HOUR),               # demandes de code ou de lien par IP
}
CAPTCHA_AFTER = 3  # échecs de connexion (compte ou IP) avant de demander le captcha
KEEP = timedelta(days=1)


def _key(bucket: str, value: str) -> str:
    return token_hash(f"{bucket}:{value.strip().lower()}")


def record(db: Session, bucket: str, value: str, now: datetime) -> None:
    db.add(RateLimitHit(bucket=bucket, key_hash=_key(bucket, value), created_at=now))
    db.flush()


def count(db: Session, bucket: str, value: str, now: datetime) -> int:
    window = LIMITS[bucket][1]
    return db.scalar(select(func.count()).select_from(RateLimitHit).where(
        RateLimitHit.bucket == bucket, RateLimitHit.key_hash == _key(bucket, value),
        RateLimitHit.created_at > now - window)) or 0


def over(db: Session, bucket: str, value: str, now: datetime) -> bool:
    return count(db, bucket, value, now) >= LIMITS[bucket][0]


def clear(db: Session, bucket: str, value: str) -> None:
    db.execute(delete(RateLimitHit).where(RateLimitHit.bucket == bucket, RateLimitHit.key_hash == _key(bucket, value)))


def purge_hits(db: Session, now: datetime) -> int:
    return db.execute(delete(RateLimitHit).where(RateLimitHit.created_at < now - KEEP)).rowcount
```

- [ ] **Step 5: Lancer les tests** — même commande qu'au Step 2. Expected: 7 passed.

- [ ] **Step 6: Migration** — `backend/alembic/versions/b8d4f0a2c3e5_security_events_rate_limits.py` :

```python
"""security events and rate limit hits

Revision ID: b8d4f0a2c3e5
Revises: a7c3e9f1b2d4
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d4f0a2c3e5"
down_revision: Union[str, Sequence[str], None] = "a7c3e9f1b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("ip", sa.String(50), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_security_events_user_id", "security_events", ["user_id"])
    op.create_index("ix_security_events_created_at", "security_events", ["created_at"])
    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("bucket", sa.String(30), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_limit_hits_lookup", "rate_limit_hits", ["bucket", "key_hash", "created_at"])


def downgrade() -> None:
    op.drop_table("rate_limit_hits")
    op.drop_table("security_events")
```

Vérifier sur une base jetable (jamais `pea_radar` directement) :

```bash
docker compose exec -T db psql -U pea -d postgres -c "DROP DATABASE IF EXISTS pea_check" -c "CREATE DATABASE pea_check"
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T --no-deps -e DATABASE_URL=postgresql+psycopg://pea:pea@db:5432/pea_check api sh -c "alembic upgrade head && alembic check && alembic downgrade -1 && alembic upgrade head"
docker compose exec -T db psql -U pea -d postgres -c "DROP DATABASE pea_check"
```
Expected: `No new upgrade operations detected.` et aucune erreur au downgrade/upgrade.

- [ ] **Step 7: Configuration** — dans `backend/app/core/config.py`, après `mail_from` :

```python
    # Connexion Google (OpenID Connect) ; vide = bouton masqué
    google_client_id: str = ""
    google_client_secret: str = ""
    # Cloudflare Turnstile ; clé secrète vide = captcha désactivé (local, tests)
    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""
    # Refus des mots de passe connus dans les fuites (Have I Been Pwned, k-anonymat)
    hibp_enabled: bool = True
    # Origines acceptées en plus de PUBLIC_BASE_URL (serveur Vite de développement), séparées par des virgules
    dev_origins: str = "http://localhost:5180"
```

Dans `.env.example`, après le bloc SMTP :

```bash
# Connexion Google : identifiants OAuth (console Google Cloud). Vide = bouton « Continuer avec Google » masqué.
# URI de redirection à déclarer chez Google : <PUBLIC_BASE_URL>/api/auth/google/callback
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
# Cloudflare Turnstile (anti-robot). Clé secrète vide = vérification désactivée (local).
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=
# En-tête HSTS : true seulement derrière HTTPS
HSTS_ENABLED=false
```

- [ ] **Step 8: Purge nocturne** — `backend/app/jobs/cleanup.py` :

```python
from app.jobs.context import JobContext
from app.services.ratelimit import purge_hits
from app.services.security_log import purge_events


def purge_security_data(ctx: JobContext) -> int:
    """Chaque nuit : journal de plus de 12 mois et compteurs de plus d'un jour."""
    now = ctx.now()
    with ctx.session_factory() as db:
        removed = purge_events(db, now) + purge_hits(db, now)
        db.commit()
    return removed
```

Vérifier le nom de la méthode d'horloge de `JobContext` (`backend/app/jobs/context.py`) et l'utiliser telle quelle. Dans `build_scheduler` (`backend/app/jobs/scheduler.py`), après le job `evening` :

```python
    scheduler.add_job(cleanup_job, CronTrigger(hour=3, minute=30, timezone=tz), args=[ctx], id="cleanup", **daily)
```

et, à côté de `mail_job` :

```python
def cleanup_job(ctx: JobContext) -> None:
    run_job(ctx, "cleanup", purge_security_data)
```

(import `from app.jobs.cleanup import purge_security_data` en tête). Ajouter à `backend/tests/test_security_log.py` :

```python
def test_cleanup_job_purges_both_tables(db, make_ctx):
    from app.jobs.cleanup import purge_security_data
    from app.services import ratelimit

    log_event(db, "logout", now=NOW - timedelta(days=400))
    ratelimit.record(db, "login_ip", "203.0.113.5", NOW - timedelta(days=3))
    assert purge_security_data(make_ctx(now=NOW)) == 2
```

- [ ] **Step 9: Suite complète** — `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` → tout passe (475 + 8).

- [ ] **Step 10: Commit**

```bash
git add backend .env.example
git commit -m "feat: security journal and database rate limit counters, purged nightly"
```

### Task 2: Connexion — blocage, 429 par IP, captcha après 3 échecs, journal

**Files:**
- Create: `backend/app/services/auth/captcha.py`, `backend/tests/fake_captcha.py`, `backend/tests/test_api_login_limits.py`
- Modify: `backend/app/api/deps.py`, `backend/app/api/routes/auth.py`, `backend/app/schemas/auth.py`, `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `ratelimit.*`, `log_event` (Task 1).
- Produces:
  - `CaptchaVerifier` (Protocol) avec `verify(token: str | None, ip: str | None) -> bool` ; `TurnstileVerifier(secret)`, `DisabledCaptcha` ; dépendance `get_captcha()` dans `app/api/deps.py`.
  - `LoginIn.captcha: str | None = None`.
  - Codes d'erreur : `captcha_required` (400), `account_locked` (429), `too_many_requests` (429).
  - `tests/fake_captcha.FakeCaptcha` (attribut `required: bool`, jeton accepté `"jeton-valide"`), fixture `fake_captcha`.
  - `_build_app(db, fake_market, fake_llm, fake_captcha, fake_breach, fake_google)` : les trois fixtures `fake_*` supplémentaires existent dès cette tâche (`fake_breach` et `fake_google` valent `None` jusqu'aux Tasks 4 et 5 ; l'override n'est posé que si la valeur n'est pas `None`).

- [ ] **Step 1: Faux captcha et fixtures** — `backend/tests/fake_captcha.py` :

```python
class FakeCaptcha:
    """Remplace Turnstile. Par défaut, pas de captcha (comme en local) ; `required = True` pour le tester."""

    def __init__(self) -> None:
        self.required = False
        self.calls: list[tuple[str | None, str | None]] = []

    def verify(self, token: str | None, ip: str | None) -> bool:
        self.calls.append((token, ip))
        return not self.required or token == "jeton-valide"
```

Dans `backend/tests/conftest.py` : ajouter les fixtures

```python
@pytest.fixture
def fake_captcha():
    from tests.fake_captcha import FakeCaptcha

    return FakeCaptcha()


@pytest.fixture
def fake_breach():
    return None  # remplacé à la Task 4


@pytest.fixture
def fake_google():
    return None  # remplacé à la Task 5
```

changer `_build_app(db, fake_market, fake_llm)` en `_build_app(db, fake_market, fake_llm, fake_captcha, fake_breach, fake_google)` avec, avant `return app` :

```python
    from app.api.deps import get_captcha

    app.dependency_overrides[get_captcha] = lambda: fake_captcha
```

et passer les trois nouvelles fixtures dans `anon_client`, `client` et `admin_client` (signatures et appels). Chercher les autres appels : `grep -rn "_build_app" backend/tests` et les mettre à jour de la même façon.

- [ ] **Step 2: Tests qui échouent** — `backend/tests/test_api_login_limits.py` :

```python
from sqlalchemy import select

from app.models import SecurityEvent
from tests.factories import make_user


def _login(client, email="jean@example.com", password="mauvais-mot-de-passe", **extra):
    return client.post("/api/auth/login", json={"email": email, "password": password, **extra})


def test_ten_failures_lock_the_account_even_with_the_right_password(anon_client, db):
    user = make_user(db, "jean@example.com")
    for _ in range(10):
        assert _login(anon_client, captcha="jeton-valide").status_code == 401
    locked = _login(anon_client, password="motdepasse-solide", captcha="jeton-valide")
    assert locked.status_code == 429 and locked.json()["detail"]["code"] == "account_locked"
    assert user.locked_until is not None
    kinds = [e.kind for e in db.scalars(select(SecurityEvent).order_by(SecurityEvent.id))]
    assert kinds.count("login_failed") == 10 and kinds.count("locked") == 1


def test_lock_looks_the_same_for_unknown_addresses(anon_client, db):
    make_user(db, "jean@example.com")
    for email in ("jean@example.com", "personne@example.com"):
        for _ in range(10):
            _login(anon_client, email=email, captcha="jeton-valide")
    real = _login(anon_client, email="jean@example.com", captcha="jeton-valide")
    unknown = _login(anon_client, email="personne@example.com", captcha="jeton-valide")
    assert (real.status_code, real.json()) == (unknown.status_code, unknown.json())


def test_success_clears_the_failures_of_the_account(anon_client, db):
    make_user(db, "jean@example.com")
    for _ in range(2):
        _login(anon_client)
    assert _login(anon_client, password="motdepasse-solide").status_code == 200
    events = [e.kind for e in db.scalars(select(SecurityEvent))]
    assert "login_ok" in events
    # les 2 échecs sont oubliés : 2 nouveaux échecs ne demandent pas encore le captcha
    anon_client.cookies.clear()
    for _ in range(2):
        assert _login(anon_client).status_code == 401


def test_captcha_is_required_after_three_failures(anon_client, db, fake_captcha):
    fake_captcha.required = True
    make_user(db, "jean@example.com")
    for _ in range(3):
        assert _login(anon_client).status_code == 401
    refused = _login(anon_client, password="motdepasse-solide")
    assert refused.status_code == 400 and refused.json()["detail"]["code"] == "captcha_required"
    assert _login(anon_client, password="motdepasse-solide", captcha="jeton-valide").status_code == 200


def test_thirty_failures_from_one_ip_give_429(anon_client, db):
    for i in range(30):
        _login(anon_client, email=f"inconnu{i}@example.com", captcha="jeton-valide")
    blocked = _login(anon_client, email="autre@example.com", captcha="jeton-valide")
    assert blocked.status_code == 429 and blocked.json()["detail"]["code"] == "too_many_requests"
```

- [ ] **Step 3: Lancer** — `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_login_limits.py`
Expected: FAIL (`ImportError: cannot import name 'get_captcha'`).

- [ ] **Step 4: Captcha** — `backend/app/services/auth/captcha.py` :

```python
import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class CaptchaVerifier(Protocol):
    def verify(self, token: str | None, ip: str | None) -> bool: ...


class DisabledCaptcha:
    """TURNSTILE_SECRET_KEY vide (local, tests) : tout passe."""

    def verify(self, token: str | None, ip: str | None) -> bool:
        return True


class TurnstileVerifier:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    def verify(self, token: str | None, ip: str | None) -> bool:
        if not token:
            return False
        try:
            response = httpx.post(SITEVERIFY_URL, data={"secret": self.secret, "response": token,
                                                        **({"remoteip": ip} if ip else {})}, timeout=5.0)
            return bool(response.json().get("success"))
        except (httpx.HTTPError, ValueError):
            # Cloudflare injoignable : on laisse passer plutôt que bloquer tout le monde (les limites restent actives).
            logger.warning("Turnstile injoignable : vérification ignorée")
            return True
```

Dans `backend/app/api/deps.py` :

```python
def get_captcha():
    """Turnstile si la clé secrète est configurée, sinon captcha désactivé ; remplacé en test."""
    from app.services.auth.captcha import DisabledCaptcha, TurnstileVerifier

    secret = get_settings().turnstile_secret_key
    return TurnstileVerifier(secret) if secret else DisabledCaptcha()
```

Dans `backend/app/schemas/auth.py`, `LoginIn` gagne `captcha: str | None = Field(default=None, max_length=4096)`.

- [ ] **Step 5: Route de connexion** — dans `backend/app/api/routes/auth.py`, imports :

```python
from app.api.deps import get_captcha
from app.core.security import normalize_email, password_problem
from app.services import ratelimit
from app.services.auth.captcha import CaptchaVerifier
from app.services.security_log import log_event

LOCKED = ("account_locked", "Trop d'essais pour ce compte : réessayez dans 15 minutes.")
TOO_MANY = ("too_many_requests", "Trop de tentatives depuis votre connexion : réessayez plus tard.")
CAPTCHA = ("captcha_required", "Confirmez que vous n'êtes pas un robot, puis réessayez.")
```

et remplacer `login` par :

```python
@router.post("/login", response_model=MeOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db),
          now: datetime = Depends(get_now), captcha: CaptchaVerifier = Depends(get_captcha)) -> MeOut:
    ip, email = client_ip(request) or "inconnue", normalize_email(payload.email)
    if ratelimit.over(db, "login_ip", ip, now):
        raise fail(429, *TOO_MANY)
    if ratelimit.over(db, "login_account", email, now):  # même réponse que le compte existe ou non
        raise fail(429, *LOCKED)
    failures = max(ratelimit.count(db, "login_account", email, now), ratelimit.count(db, "login_ip", ip, now))
    if failures >= ratelimit.CAPTCHA_AFTER and not captcha.verify(payload.captcha, ip):
        raise fail(400, *CAPTCHA)
    user = accounts.authenticate(db, email, payload.password)
    if user is None:
        known = accounts.find_user(db, email)
        ratelimit.record(db, "login_account", email, now)
        ratelimit.record(db, "login_ip", ip, now)
        log_event(db, "login_failed", now=now, user_id=known.id if known else None, ip=ip)
        if ratelimit.over(db, "login_account", email, now):
            log_event(db, "locked", now=now, user_id=known.id if known else None, ip=ip)
            if known is not None:
                known.locked_until = now + ratelimit.FIFTEEN_MINUTES
        db.commit()
        raise fail(401, "invalid_credentials", "Adresse mail ou mot de passe incorrect.")
    if user.email_verified_at is None:
        accounts.resend_code(db, user.email, now)
        db.commit()
        raise fail(403, "email_not_verified", "Validez d'abord votre adresse : un code vient de vous être envoyé.")
    ratelimit.clear(db, "login_account", email)
    user.failed_logins, user.locked_until = 0, None
    log_event(db, "login_ok", now=now, user_id=user.id, ip=ip, details={"method": "password"})
    previous = resolve_session(db, request.cookies.get(SESSION_COOKIE), now=now, settings=get_settings())
    if previous is not None:
        revoke_session(db, previous.id)  # jamais deux sessions pour le même cookie
    start_session(db, user, request, response, persistent=payload.remember, now=now, alert_new_device=True)
    return MeOut.model_validate(user)
```

- [ ] **Step 6: Lancer** — commande du Step 3. Expected: 5 passed. Puis suite complète : tout passe (les tests existants de connexion font moins de 3 échecs).

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat: sign-in lock after 10 failures, 429 per IP, captcha after 3 failures, security journal"
```

### Task 3: Inscription, codes et mot de passe oublié — limites, Turnstile, Origin, journal

**Files:**
- Create: `backend/app/api/origin.py`, `backend/tests/test_api_signup_limits.py`
- Modify: `backend/app/api/routes/auth.py`, `backend/app/schemas/auth.py`, `backend/app/services/auth/accounts.py`

**Interfaces:**
- Consumes: Task 1, Task 2 (`get_captcha`, `CAPTCHA`, `TOO_MANY`).
- Produces:
  - `check_origin` : dépendance FastAPI sans valeur de retour, 403 `bad_origin` si l'en-tête `Origin` est présent et n'est ni l'origine de `PUBLIC_BASE_URL` ni une de `DEV_ORIGINS`. Posée sur **toutes** les routes `POST /api/auth/*` (dont `google/complete` à la Task 6).
  - `RegisterIn.captcha`, `EmailIn.captcha` (optionnels).
  - `accounts.register(...) -> User | None` (le compte créé ou remplacé, `None` si l'adresse appartient déjà à un compte validé).
  - Événements journalisés : `signup`, `email_verified`, `logout`, `password_reset`, `not_me`.

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_signup_limits.py` :

```python
from sqlalchemy import select

from app.models import EmailLog, SecurityEvent

FORM = {"first_name": "Jean", "last_name": "Dupont", "email": "jean@example.com",
        "password": "motdepasse-solide", "accept_terms": True}


def _kinds(db):
    return [e.kind for e in db.scalars(select(SecurityEvent).order_by(SecurityEvent.id))]


def test_signup_needs_the_captcha_when_enabled(anon_client, fake_captcha):
    fake_captcha.required = True
    refused = anon_client.post("/api/auth/register", json=FORM)
    assert refused.status_code == 400 and refused.json()["detail"]["code"] == "captcha_required"
    assert anon_client.post("/api/auth/register", json={**FORM, "captcha": "jeton-valide"}).status_code == 202


def test_five_signups_per_ip_and_hour(anon_client, db):
    for i in range(5):
        assert anon_client.post("/api/auth/register", json={**FORM, "email": f"p{i}@example.com"}).status_code == 202
    sixth = anon_client.post("/api/auth/register", json={**FORM, "email": "p6@example.com"})
    assert sixth.status_code == 429 and sixth.json()["detail"]["code"] == "too_many_requests"
    assert _kinds(db).count("signup") == 5


def test_codes_per_address_are_capped_silently(anon_client, db):
    anon_client.post("/api/auth/register", json=FORM)
    from datetime import UTC, datetime

    from app.services import ratelimit

    for _ in range(5):
        ratelimit.record(db, "mail_account", "jean@example.com", datetime.now(UTC))
    before = len(db.scalars(select(EmailLog)).all())
    again = anon_client.post("/api/auth/forgot-password", json={"email": "jean@example.com"})
    assert again.status_code == 202  # même réponse, mais plus aucun mail
    assert len(db.scalars(select(EmailLog)).all()) == before


def test_twenty_mail_requests_per_ip_give_429(anon_client):
    for i in range(20):
        anon_client.post("/api/auth/resend-code", json={"email": f"x{i}@example.com"})
    blocked = anon_client.post("/api/auth/forgot-password", json={"email": "y@example.com"})
    assert blocked.status_code == 429


def test_forgot_password_needs_the_captcha_when_enabled(anon_client, fake_captcha):
    fake_captcha.required = True
    refused = anon_client.post("/api/auth/forgot-password", json={"email": "jean@example.com"})
    assert refused.json()["detail"]["code"] == "captcha_required"
    ok = anon_client.post("/api/auth/forgot-password", json={"email": "jean@example.com", "captcha": "jeton-valide"})
    assert ok.status_code == 202


def test_foreign_origin_is_refused_but_own_and_missing_pass(anon_client):
    evil = anon_client.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 12},
                            headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403 and evil.json()["detail"]["code"] == "bad_origin"
    own = anon_client.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 12},
                           headers={"Origin": "http://localhost:8095"})
    assert own.status_code == 401
    dev = anon_client.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 12},
                           headers={"Origin": "http://localhost:5180"})
    assert dev.status_code == 401


def test_verification_logout_and_reset_are_journaled(anon_client, db):
    import re

    anon_client.post("/api/auth/register", json=FORM)
    mail = db.scalars(select(EmailLog).where(EmailLog.kind == "verify_code")).one()
    code = re.search(r"\b(\d{6})\b", mail.subject).group(1)
    verified = anon_client.post("/api/auth/verify-email", json={"email": "jean@example.com", "code": code})
    anon_client.headers["X-CSRF-Token"] = verified.cookies.get("pea_csrf") or anon_client.cookies.get("pea_csrf")
    anon_client.post("/api/auth/logout")
    assert _kinds(db)[-3:] == ["signup", "email_verified", "logout"]
```

- [ ] **Step 2: Lancer** — `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_signup_limits.py`
Expected: FAIL (captcha non demandé, pas de 429, pas de `bad_origin`).

- [ ] **Step 3: Origin** — `backend/app/api/origin.py` :

```python
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from app.core.config import get_settings


def _origin(url: str) -> str:
    parts = urlsplit(url.strip())
    return f"{parts.scheme}://{parts.netloc}".lower()


def check_origin(request: Request) -> None:
    """Routes publiques de connexion et d'inscription : refuse un en-tête Origin étranger (spec 2.1).

    Un navigateur envoie toujours Origin sur un POST ; son absence (outil en ligne de commande, tests) est acceptée.
    """
    origin = request.headers.get("Origin")
    if origin is None:
        return
    settings = get_settings()
    allowed = {_origin(settings.public_base_url)} | {_origin(o) for o in settings.dev_origins.split(",") if o.strip()}
    if origin.lower().rstrip("/") not in allowed:
        raise HTTPException(403, detail={"code": "bad_origin", "message": "Requête refusée : rechargez la page."})
```

Dans `backend/app/api/routes/auth.py` : `router = APIRouter(prefix="/auth", tags=["auth"])` reste, et **chaque** décorateur `@router.post(...)` reçoit `dependencies=[Depends(check_origin)]` (register, verify-email, resend-code, login, logout, forgot-password, reset-password, not-me).

- [ ] **Step 4: Schémas et service** — `RegisterIn` et `EmailIn` gagnent `captcha: str | None = Field(default=None, max_length=4096)`. Dans `accounts.register`, remplacer `return` (branche compte déjà validé) par `return None` et terminer par `return user` ; annoter `-> User | None`.

- [ ] **Step 5: Routes** — dans `backend/app/api/routes/auth.py` :

```python
def _mail_allowed(db: Session, email: str, ip: str, now: datetime) -> bool:
    """Compte une demande de code ou de lien. 429 si l'IP abuse ; False (sans rien dire) si l'adresse a assez reçu."""
    if ratelimit.over(db, "mail_ip", ip, now):
        raise fail(429, *TOO_MANY)
    ratelimit.record(db, "mail_ip", ip, now)
    if ratelimit.over(db, "mail_account", email, now):
        return False
    ratelimit.record(db, "mail_account", email, now)
    return True


@router.post("/register", response_model=NoticeOut, status_code=202, dependencies=[Depends(check_origin)])
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db), now: datetime = Depends(get_now),
             captcha: CaptchaVerifier = Depends(get_captcha)) -> NoticeOut:
    ip = client_ip(request) or "inconnue"
    if not captcha.verify(payload.captcha, ip):
        raise fail(400, *CAPTCHA)
    check_password_rules(payload.password)
    if ratelimit.over(db, "signup_ip", ip, now):
        raise fail(429, *TOO_MANY)
    ratelimit.record(db, "signup_ip", ip, now)
    user = accounts.register(db, first_name=payload.first_name, last_name=payload.last_name, email=payload.email,
                             password=payload.password, now=now)
    if user is not None:
        log_event(db, "signup", now=now, user_id=user.id, ip=ip)
    db.commit()
    return CODE_SENT


@router.post("/resend-code", response_model=NoticeOut, status_code=202, dependencies=[Depends(check_origin)])
def resend_code(payload: EmailIn, request: Request, db: Session = Depends(get_db),
                now: datetime = Depends(get_now)) -> NoticeOut:
    email = normalize_email(payload.email)
    if _mail_allowed(db, email, client_ip(request) or "inconnue", now):
        accounts.resend_code(db, email, now)
    db.commit()
    return CODE_SENT


@router.post("/forgot-password", response_model=NoticeOut, status_code=202, dependencies=[Depends(check_origin)])
def forgot_password(payload: EmailIn, request: Request, db: Session = Depends(get_db), now: datetime = Depends(get_now),
                    captcha: CaptchaVerifier = Depends(get_captcha)) -> NoticeOut:
    ip, email = client_ip(request) or "inconnue", normalize_email(payload.email)
    if not captcha.verify(payload.captcha, ip):
        raise fail(400, *CAPTCHA)
    if _mail_allowed(db, email, ip, now):
        accounts.request_password_reset(db, email, now)
    db.commit()
    return RESET_SENT
```

Journal dans les routes existantes (ajouter `request: Request` à la signature quand il manque) :
- `verify_email` : après le succès, `log_event(db, "email_verified", now=now, user_id=user.id, ip=client_ip(request))` avant `start_session` (qui committe).
- `logout` : `log_event(db, "logout", now=get_now(), user_id=auth.user_id, ip=client_ip(request))` dans la branche `auth is not None`, avant le commit.
- `reset_password` : garder le retour de `accounts.reset_password` dans `user`, puis `log_event(db, "password_reset", now=now, user_id=user.id, ip=client_ip(request))`.
- `not_me` : idem avec `"not_me"`.

- [ ] **Step 6: Lancer** — commande du Step 2 : 7 passed ; puis suite complète : tout passe. Si un test existant envoie plus de 5 inscriptions dans le même test, c'est la limite qui joue : le signaler dans le ledger et découper le test, ne pas relever la limite.

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat: sign-up and mail limits, Turnstile on sign-up and forgotten password, Origin check, journal"
```

### Task 4: Mots de passe ayant fuité (Have I Been Pwned)

**Files:**
- Create: `backend/app/services/auth/breach.py`, `backend/tests/fake_breach.py`, `backend/tests/test_breach.py`
- Modify: `backend/app/api/deps.py`, `backend/app/api/routes/auth.py`, `backend/tests/conftest.py`

**Interfaces:**
- Produces: `BreachChecker` (Protocol) `is_pwned(password: str) -> bool` ; `HibpChecker`, `NoBreachCheck` ; `suffix_found(body: str, suffix: str) -> bool` ; dépendance `get_breach_checker()` ; code d'erreur `pwned_password` (400) sur `register` et `reset-password`.

- [ ] **Step 1: Faux et fixture** — `backend/tests/fake_breach.py` :

```python
class FakeBreach:
    """Remplace Have I Been Pwned : seuls les mots de passe de `pwned` sont « connus des fuites »."""

    def __init__(self) -> None:
        self.pwned: set[str] = set()

    def is_pwned(self, password: str) -> bool:
        return password in self.pwned
```

Dans `conftest.py`, la fixture `fake_breach` devient :

```python
@pytest.fixture
def fake_breach():
    from tests.fake_breach import FakeBreach

    return FakeBreach()
```

et `_build_app` ajoute `app.dependency_overrides[get_breach_checker] = lambda: fake_breach` (import depuis `app.api.deps`).

- [ ] **Step 2: Tests qui échouent** — `backend/tests/test_breach.py` :

```python
import hashlib

import httpx

from app.services.auth.breach import HibpChecker, suffix_found

FORM = {"first_name": "Jean", "last_name": "Dupont", "email": "jean@example.com",
        "password": "motdepasse123", "accept_terms": True}


def test_suffix_found_reads_the_range_answer():
    body = "0018A45C4D1DEF81644B54AB7F969B88D65:3\r\n00D4F6E8FA6EECAD2A3AA415EEC418D38EC:0\r\n"
    assert suffix_found(body, "0018a45c4d1def81644b54ab7f969b88d65")
    assert not suffix_found(body, "00D4F6E8FA6EECAD2A3AA415EEC418D38EC")  # 0 = remplissage (Add-Padding)
    assert not suffix_found(body, "FFFF")


def test_only_the_first_five_characters_leave_the_server(monkeypatch):
    sha1 = hashlib.sha1(b"motdepasse123").hexdigest().upper()
    seen = []

    def fake_get(url, headers, timeout):
        seen.append((url, headers, timeout))
        return httpx.Response(200, text=f"{sha1[5:]}:42\r\n")

    monkeypatch.setattr(httpx, "get", fake_get)
    assert HibpChecker().is_pwned("motdepasse123")
    assert seen[0][0].endswith(f"/range/{sha1[:5]}") and seen[0][2] == 2.0 and seen[0][1]["Add-Padding"] == "true"


def test_a_silent_service_is_ignored(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectTimeout("trop long")

    monkeypatch.setattr(httpx, "get", boom)
    assert not HibpChecker().is_pwned("motdepasse123")


def test_signup_and_reset_refuse_a_pwned_password(anon_client, fake_breach):
    fake_breach.pwned.add("motdepasse123")
    refused = anon_client.post("/api/auth/register", json=FORM)
    assert refused.status_code == 400 and refused.json()["detail"]["code"] == "pwned_password"
    reset = anon_client.post("/api/auth/reset-password", json={"token": "x" * 43, "password": "motdepasse123"})
    assert reset.json()["detail"]["code"] == "pwned_password"
```

- [ ] **Step 3: Lancer** — `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_breach.py`
Expected: FAIL (`ModuleNotFoundError: app.services.auth.breach`).

- [ ] **Step 4: Implémentation** — `backend/app/services/auth/breach.py` :

```python
"""Have I Been Pwned, en k-anonymat : seuls les 5 premiers caractères du SHA-1 quittent le serveur."""
import hashlib
import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)
RANGE_URL = "https://api.pwnedpasswords.com/range/"


class BreachChecker(Protocol):
    def is_pwned(self, password: str) -> bool: ...


class NoBreachCheck:
    def is_pwned(self, password: str) -> bool:
        return False


def suffix_found(body: str, suffix: str) -> bool:
    """Vrai si le suffixe figure dans la réponse avec au moins une fuite (les lignes à 0 sont du remplissage)."""
    wanted = suffix.upper()
    for line in body.splitlines():
        candidate, _, count = line.strip().partition(":")
        if candidate.upper() == wanted and count.strip().isdigit() and int(count) > 0:
            return True
    return False


class HibpChecker:
    def is_pwned(self, password: str) -> bool:
        digest = hashlib.sha1(password.encode()).hexdigest().upper()
        try:
            response = httpx.get(RANGE_URL + digest[:5], headers={"Add-Padding": "true"}, timeout=2.0)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("Have I Been Pwned ne répond pas : vérification ignorée")
            return False
        return suffix_found(response.text, digest[5:])
```

`backend/app/api/deps.py` :

```python
def get_breach_checker():
    """Have I Been Pwned (désactivable par HIBP_ENABLED=false) ; remplacé en test."""
    from app.services.auth.breach import HibpChecker, NoBreachCheck

    return HibpChecker() if get_settings().hibp_enabled else NoBreachCheck()
```

Dans `auth.py`, remplacer `check_password_rules` par :

```python
PWNED = ("pwned_password", "Ce mot de passe apparaît dans des fuites de données connues : choisissez-en un autre.")


def check_password_rules(password: str, breach: BreachChecker) -> None:
    problem = password_problem(password)
    if problem:
        raise fail(400, "weak_password", problem)
    if breach.is_pwned(password):
        raise fail(400, *PWNED)
```

et ajouter `breach: BreachChecker = Depends(get_breach_checker)` à `register` et `reset_password`, qui appellent `check_password_rules(payload.password, breach)`.

- [ ] **Step 5: Lancer** — commande du Step 3 : 4 passed ; suite complète : tout passe.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: refuse passwords found in known breaches (Have I Been Pwned, k-anonymity)"
```

> **Fin du Bloc 1 — stop.** Statut : journal, limites, captcha et HIBP en place côté API ; suite verte. Suite : Bloc 2 (Google).

---

# Bloc 2 — Connexion Google (backend)

### Task 5: Client Google OIDC, PKCE et cookie signé

**Files:**
- Create: `backend/app/services/auth/google.py`, `backend/tests/fake_google.py`, `backend/tests/test_google_client.py`
- Modify: `backend/pyproject.toml` (`"authlib>=1.3"`), `backend/app/core/security.py`, `backend/app/api/deps.py`, `backend/tests/conftest.py`

**Interfaces:**
- Produces:
  - `GoogleIdentity(sub: str, email: str, email_verified: bool, first_name: str, last_name: str)` (dataclass figée) ; `GoogleError(Exception)`.
  - `GoogleClient` (Protocol) : `authorize_url(*, state: str, nonce: str, code_challenge: str, redirect_uri: str) -> str` ; `identify(*, code: str, code_verifier: str, nonce: str, redirect_uri: str) -> GoogleIdentity` (lève `GoogleError`).
  - `GoogleOIDC(client_id, client_secret)` (réel) ; dépendance `get_google_client() -> GoogleClient | None` (`None` si Google n'est pas configuré ou si `APP_SECRET` est vide).
  - `core.security` : `sign(data: dict, secret: str, now: datetime) -> str`, `unsign(value: str | None, secret: str, now: datetime, max_age: timedelta) -> dict | None`, `pkce_challenge(verifier: str) -> str`.
  - `tests/fake_google.FakeGoogle` : `identity: GoogleIdentity`, `authorize_url()` renvoie `https://accounts.google.test/auth?state=…`, `identify()` vérifie que le `code` vaut `"bon-code"` et renvoie `identity` avec le `nonce` reçu enregistré dans `last_nonce`.

- [ ] **Step 1: Dépendance** — ajouter `"authlib>=1.3",` aux dépendances de `backend/pyproject.toml`, puis reconstruire l'image de dev : `docker compose -f docker-compose.yml -f docker-compose.dev.yml build api`.

- [ ] **Step 2: Tests qui échouent** — `backend/tests/test_google_client.py` :

```python
import base64
import hashlib
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from authlib.jose import JsonWebKey, jwt

from app.core.security import pkce_challenge, sign, unsign
from app.services.auth.google import GoogleError, GoogleOIDC

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_signed_value_round_trip_and_tampering():
    value = sign({"state": "abc"}, "secret", NOW)
    assert unsign(value, "secret", NOW + timedelta(minutes=5), timedelta(minutes=10)) == {"state": "abc"}
    assert unsign(value, "autre", NOW, timedelta(minutes=10)) is None
    assert unsign(value + "x", "secret", NOW, timedelta(minutes=10)) is None
    assert unsign(value, "secret", NOW + timedelta(minutes=11), timedelta(minutes=10)) is None
    assert unsign(None, "secret", NOW, timedelta(minutes=10)) is None


def test_pkce_challenge_is_s256():
    expected = base64.urlsafe_b64encode(hashlib.sha256(b"verifier").digest()).rstrip(b"=").decode()
    assert pkce_challenge("verifier") == expected


def test_authorize_url_asks_for_pkce_and_openid():
    url = GoogleOIDC("id-client", "secret").authorize_url(state="s", nonce="n", code_challenge="c",
                                                          redirect_uri="http://localhost:8095/api/auth/google/callback")
    for part in ("client_id=id-client", "response_type=code", "scope=openid+email+profile", "state=s", "nonce=n",
                 "code_challenge=c", "code_challenge_method=S256"):
        assert part in url


@pytest.fixture
def signing_key():
    return JsonWebKey.generate_key("RSA", 2048, is_private=True, options={"kid": "k1"})


def _id_token(key, **claims):
    base = {"iss": "https://accounts.google.com", "aud": "id-client", "sub": "123", "email": "jean@gmail.com",
            "email_verified": True, "given_name": "Jean", "family_name": "Dupont", "nonce": "n",
            "iat": int(time.time()), "exp": int(time.time()) + 600}
    return jwt.encode({"alg": "RS256", "kid": "k1"}, {**base, **claims}, key).decode()


def _mock_google(monkeypatch, key, token):
    monkeypatch.setattr(httpx, "post", lambda url, data, timeout: httpx.Response(200, json={"id_token": token}))
    monkeypatch.setattr(httpx, "get", lambda url, timeout: httpx.Response(200, json={"keys": [key.as_dict()]}))


def test_identify_checks_signature_audience_and_nonce(monkeypatch, signing_key):
    _mock_google(monkeypatch, signing_key, _id_token(signing_key))
    identity = GoogleOIDC("id-client", "secret").identify(code="c", code_verifier="v", nonce="n", redirect_uri="r")
    assert (identity.sub, identity.email, identity.email_verified, identity.first_name) == ("123", "jean@gmail.com",
                                                                                            True, "Jean")


@pytest.mark.parametrize("claims", [{"aud": "autre-client"}, {"nonce": "rejoue"}, {"iss": "https://evil.example"},
                                    {"exp": int(time.time()) - 3600}])
def test_identify_refuses_a_foreign_or_replayed_token(monkeypatch, signing_key, claims):
    _mock_google(monkeypatch, signing_key, _id_token(signing_key, **claims))
    with pytest.raises(GoogleError):
        GoogleOIDC("id-client", "secret").identify(code="c", code_verifier="v", nonce="n", redirect_uri="r")
```

- [ ] **Step 3: Lancer** — `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_google_client.py`
Expected: FAIL (`ImportError: cannot import name 'pkce_challenge'`).

- [ ] **Step 4: Primitives** — ajouter à `backend/app/core/security.py` (imports `base64`, `json`, `from datetime import datetime, timedelta`) :

```python
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(data: dict, secret: str, now: datetime) -> str:
    """Valeur de cookie signée (HMAC-SHA256), horodatée. Lisible par le navigateur : n'y mettre rien de secret."""
    payload = _b64(json.dumps({"d": data, "t": int(now.timestamp())}, separators=(",", ":")).encode())
    mac = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{mac}"


def unsign(value: str | None, secret: str, now: datetime, max_age: timedelta) -> dict | None:
    """Le contenu si la signature est bonne et la valeur assez récente, sinon None."""
    if not value or "." not in value:
        return None
    payload, _, mac = value.rpartition(".")
    expected = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(mac, expected):
        return None
    try:
        content = json.loads(_unb64(payload))
    except ValueError:
        return None
    if now.timestamp() - content["t"] > max_age.total_seconds():
        return None
    return content["d"]


def pkce_challenge(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode()).digest())
```

- [ ] **Step 5: Client Google** — `backend/app/services/auth/google.py` :

```python
"""Connexion Google (OpenID Connect, code + PKCE), faite côté serveur : le navigateur ne voit jamais les jetons Google."""
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ["https://accounts.google.com", "accounts.google.com"]


class GoogleError(Exception):
    """Échange ou jeton d'identité refusé."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    first_name: str
    last_name: str


class GoogleClient(Protocol):
    def authorize_url(self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str) -> str: ...

    def identify(self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str) -> GoogleIdentity: ...


class GoogleOIDC:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id, self.client_secret = client_id, client_secret

    def authorize_url(self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str) -> str:
        return AUTHORIZE_URL + "?" + urlencode({
            "client_id": self.client_id, "response_type": "code", "scope": "openid email profile",
            "redirect_uri": redirect_uri, "state": state, "nonce": nonce, "code_challenge": code_challenge,
            "code_challenge_method": "S256", "prompt": "select_account",
        })

    def identify(self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str) -> GoogleIdentity:
        try:
            token = httpx.post(TOKEN_URL, data={
                "code": code, "client_id": self.client_id, "client_secret": self.client_secret,
                "redirect_uri": redirect_uri, "grant_type": "authorization_code", "code_verifier": code_verifier,
            }, timeout=10.0)
            token.raise_for_status()
            keys = JsonWebKey.import_key_set(httpx.get(JWKS_URL, timeout=10.0).json())
            claims = jwt.decode(token.json()["id_token"], keys, claims_options={
                "iss": {"essential": True, "values": ISSUERS},
                "aud": {"essential": True, "value": self.client_id},
                "nonce": {"essential": True, "value": nonce},
                "sub": {"essential": True},
            })
            claims.validate(leeway=60)
        except (httpx.HTTPError, KeyError, ValueError, JoseError) as error:
            raise GoogleError(str(error)) from error
        return GoogleIdentity(sub=str(claims["sub"]), email=str(claims.get("email", "")).lower(),
                              email_verified=bool(claims.get("email_verified")),
                              first_name=str(claims.get("given_name", ""))[:100],
                              last_name=str(claims.get("family_name", ""))[:100])
```

`backend/app/api/deps.py` :

```python
def get_google_client():
    """Client Google, ou None si GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET ou APP_SECRET manque ; remplacé en test."""
    from app.services.auth.google import GoogleOIDC

    settings = get_settings()
    if not (settings.google_client_id and settings.google_client_secret and settings.app_secret):
        return None
    return GoogleOIDC(settings.google_client_id, settings.google_client_secret)
```

`backend/tests/fake_google.py` :

```python
from urllib.parse import urlencode

from app.services.auth.google import GoogleError, GoogleIdentity


class FakeGoogle:
    """Remplace Google : `identity` est le compte « choisi » par l'utilisateur ; seul le code « bon-code » passe."""

    def __init__(self) -> None:
        self.identity = GoogleIdentity(sub="google-123", email="jean@gmail.com", email_verified=True,
                                       first_name="Jean", last_name="Dupont")
        self.last_nonce: str | None = None
        self.last_verifier: str | None = None

    def authorize_url(self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str) -> str:
        return "https://accounts.google.test/auth?" + urlencode({"state": state, "nonce": nonce,
                                                                  "code_challenge": code_challenge})

    def identify(self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str) -> GoogleIdentity:
        if code != "bon-code":
            raise GoogleError("code refusé")
        self.last_nonce, self.last_verifier = nonce, code_verifier
        return self.identity
```

Dans `conftest.py`, la fixture `fake_google` renvoie `FakeGoogle()` et `_build_app` ajoute `app.dependency_overrides[get_google_client] = lambda: fake_google`.

- [ ] **Step 6: Lancer** — commande du Step 3 : 8 passed ; suite complète verte.

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat: Google OpenID Connect client with PKCE, signed short-lived cookies"
```

### Task 6: Routes Google, rattachement, finalisation, configuration publique

**Files:**
- Create: `backend/app/api/routes/google.py`, `backend/tests/test_api_google.py`
- Modify: `backend/app/main.py`, `backend/app/api/routes/auth.py` (`/auth/config`, `start_session` exportée), `backend/app/services/auth/accounts.py`, `backend/app/schemas/auth.py`, `backend/app/services/mail/render.py`

**Interfaces:**
- Consumes: Task 5 (`GoogleClient`, `sign`/`unsign`, `pkce_challenge`), Task 3 (`check_origin`), Task 1 (`log_event`), `start_session`, `safe_next` (nouvelle, ci-dessous).
- Produces:
  - `GET /api/auth/config` → `{"google": bool, "turnstile_site_key": str | null}` (schéma `AuthConfigOut`).
  - `GET /api/auth/google/start?suite=&remember=` → 302 vers Google + cookie `pea_oauth` (10 min, `Path=/api/auth/google`).
  - `GET /api/auth/google/callback` → 302 vers `suite` (connexion), `/finaliser-inscription` (nouveau compte), `/connexion?erreur=google` ou `/connexion?erreur=google_email`.
  - `GET /api/auth/google/pending` → `{"email", "first_name", "last_name"}` ou 404.
  - `POST /api/auth/google/complete` `{first_name, last_name, accept_terms}` → `MeOut` + session ; 400 `google_expired` sans cookie valide.
  - `accounts.promote_if_admin(user) -> None`, `accounts.google_sign_in(db, identity, now, *, ip=None) -> User | None` (None = compte à créer ; journalise `google_linked` au rattachement), `accounts.oauth_state_used(db, state, now) -> bool`, `accounts.create_google_account(db, identity, *, first_name, last_name, now) -> User`.
  - `safe_next(value: str | None) -> str` dans `app/api/routes/google.py` (mêmes règles que `frontend/src/features/auth/redirect.ts`).

- [ ] **Step 1: Tests qui échouent** — `backend/tests/test_api_google.py` :

```python
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from app.models import EmailLog, SecurityEvent, User
from app.services.auth.sessions import SESSION_COOKIE
from tests.factories import make_user


@pytest.fixture(autouse=True)
def app_secret(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "app_secret", "secret-de-test")


def _start(client, suite="/portefeuille"):
    response = client.get("/api/auth/google/start", params={"suite": suite, "remember": "1"}, follow_redirects=False)
    assert response.status_code == 302
    return parse_qs(urlsplit(response.headers["location"]).query)["state"][0]


def _callback(client, state, code="bon-code"):
    return client.get("/api/auth/google/callback", params={"state": state, "code": code}, follow_redirects=False)


def test_config_tells_the_frontend_what_is_enabled(anon_client):
    assert anon_client.get("/api/auth/config").json() == {"google": True, "turnstile_site_key": None}


def test_known_google_account_signs_in_and_goes_back(anon_client, db):
    user = make_user(db, "jean@gmail.com")
    user.google_sub = "google-123"
    db.flush()
    back = _callback(anon_client, _start(anon_client))
    assert back.status_code == 302 and back.headers["location"] == "/portefeuille"
    assert anon_client.cookies.get(SESSION_COOKIE)
    assert "login_ok" in [e.kind for e in db.scalars(select(SecurityEvent))]


def test_existing_address_is_linked_with_an_alert(anon_client, db):
    user = make_user(db, "jean@gmail.com")
    _callback(anon_client, _start(anon_client))
    assert user.google_sub == "google-123"
    alert = db.scalars(select(EmailLog).where(EmailLog.kind == "security_alert")).one()
    assert "Google" in alert.text


def test_linking_an_unverified_account_drops_its_password(anon_client, db):
    squatter = make_user(db, "jean@gmail.com", password="mot-de-passe-du-squatteur", verified=False)
    _callback(anon_client, _start(anon_client))
    assert squatter.email_verified_at is not None and squatter.password_hash is None


def test_new_google_account_is_created_only_after_finishing(anon_client, db, fake_google):
    back = _callback(anon_client, _start(anon_client))
    assert back.headers["location"] == "/finaliser-inscription"
    assert db.scalars(select(User)).all() == []
    assert anon_client.get("/api/auth/google/pending").json() == {"email": "jean@gmail.com", "first_name": "Jean",
                                                                   "last_name": "Dupont"}
    refused = anon_client.post("/api/auth/google/complete", json={"first_name": "Jean", "last_name": "Dupont",
                                                                  "accept_terms": False})
    assert refused.status_code == 422
    done = anon_client.post("/api/auth/google/complete", json={"first_name": "Jeannot", "last_name": "Dupont",
                                                               "accept_terms": True})
    assert done.status_code == 200 and done.json()["first_name"] == "Jeannot"
    user = db.scalars(select(User)).one()
    assert (user.google_sub, user.password_hash, user.terms_version is not None) == ("google-123", None, True)
    assert anon_client.get("/api/auth/google/pending").status_code == 404  # cookie consommé


def test_unverified_google_address_is_refused(anon_client, db, fake_google):
    from dataclasses import replace

    fake_google.identity = replace(fake_google.identity, email_verified=False)
    back = _callback(anon_client, _start(anon_client))
    assert back.headers["location"] == "/connexion?erreur=google_email"
    assert db.scalars(select(User)).all() == []


def test_callback_refuses_missing_or_mismatched_state(anon_client, db):
    make_user(db, "jean@gmail.com").google_sub = "google-123"
    db.flush()
    state = _start(anon_client)
    assert _callback(anon_client, "autre-state").headers["location"] == "/connexion?erreur=google"
    anon_client.cookies.clear()
    assert _callback(anon_client, state).headers["location"] == "/connexion?erreur=google"  # plus de cookie
    assert _callback(anon_client, _start(anon_client), code="mauvais-code").headers["location"] == "/connexion?erreur=google"
    assert anon_client.cookies.get(SESSION_COOKIE) is None


def test_state_cookie_cannot_be_replayed(anon_client, db):
    make_user(db, "jean@gmail.com").google_sub = "google-123"
    db.flush()
    state = _start(anon_client)
    oauth_cookie = anon_client.cookies.get("pea_oauth", path="/api/auth/google")
    assert _callback(anon_client, state).headers["location"] == "/portefeuille"
    anon_client.cookies.clear()
    anon_client.cookies.set("pea_oauth", oauth_cookie, path="/api/auth/google")
    assert _callback(anon_client, state).headers["location"] == "/connexion?erreur=google"


@pytest.mark.parametrize("suite", ["//evil.com", "https://evil.com", "/\\evil.com", ""])
def test_google_suite_is_kept_only_for_internal_paths(anon_client, db, suite):
    make_user(db, "jean@gmail.com").google_sub = "google-123"
    db.flush()
    assert _callback(anon_client, _start(anon_client, suite=suite)).headers["location"] == "/"


def test_google_is_404_when_not_configured(anon_client):
    from app.api.deps import get_google_client

    anon_client.app.dependency_overrides[get_google_client] = lambda: None
    assert anon_client.get("/api/auth/google/start").status_code == 404
    assert anon_client.get("/api/auth/config").json()["google"] is False
```

- [ ] **Step 2: Lancer** — `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_google.py`
Expected: FAIL (404 sur `/api/auth/config`).

- [ ] **Step 3: Service** — dans `backend/app/services/auth/accounts.py` :

```python
def promote_if_admin(user: User) -> None:
    """Le compte ADMIN_EMAIL devient admin dès que son adresse est prouvée (code ou Google)."""
    if user.email == normalize_email(get_settings().admin_email or "-"):
        user.role, user.is_premium = "admin", True


def google_sign_in(db: Session, identity: GoogleIdentity, now: datetime, *, ip: str | None = None) -> User | None:
    """Compte à connecter pour cette identité Google (vérifiée), ou None s'il faut en créer un (après les CGU)."""
    user = db.scalar(select(User).where(User.google_sub == identity.sub))
    if user is not None:
        return user
    user = find_user(db, identity.email)
    if user is None:
        return None
    if user.email_verified_at is None:
        # Inscription jamais validée : rien ne prouve que son mot de passe vient du propriétaire de l'adresse.
        user.password_hash = None
        user.email_verified_at = now
        promote_if_admin(user)
    user.google_sub = identity.sub
    log_event(db, "google_linked", now=now, user_id=user.id, ip=ip)
    enqueue(db, "security_alert", to=user.email, user_id=user.id,
            context={"first_name": user.first_name, "event": "google_linked"})
    return user


def create_google_account(db: Session, identity: GoogleIdentity, *, first_name: str, last_name: str,
                          now: datetime) -> User:
    user = User(email=normalize_email(identity.email), first_name=first_name, last_name=last_name,
                google_sub=identity.sub, email_verified_at=now, terms_accepted_at=now, terms_version=TERMS_VERSION)
    db.add(user)
    promote_if_admin(user)
    db.flush()
    enqueue(db, "welcome", to=user.email, user_id=user.id, context={"first_name": user.first_name})
    return user
```

(imports `from app.services.auth.google import GoogleIdentity`, `from app.services import ratelimit` et `from app.services.security_log import log_event`), et `verify_email` appelle `promote_if_admin(user)` à la place de ses deux lignes équivalentes. Dans `backend/app/services/mail/render.py`, `SECURITY_EVENTS` gagne :

```python
    "google_linked": ("Un compte Google vient d'être associé à votre compte PEA Radar : vous pouvez maintenant vous "
                      "connecter avec Google. Si ce n'était pas vous, choisissez un nouveau mot de passe."),
```

- [ ] **Step 4: Schémas** — dans `backend/app/schemas/auth.py` :

```python
class AuthConfigOut(BaseModel):
    google: bool
    turnstile_site_key: str | None


class GooglePendingOut(BaseModel):
    email: str
    first_name: str
    last_name: str


class GoogleCompleteIn(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    accept_terms: bool

    _names = field_validator("first_name", "last_name")(RegisterIn.not_blank.__func__)
    _terms = field_validator("accept_terms")(RegisterIn.terms_accepted.__func__)
```

Si Pydantic refuse la réutilisation des validateurs ainsi, recopier les deux méthodes `not_blank` et `terms_accepted` telles quelles (ledger).

- [ ] **Step 5: Routes** — `/auth/config` dans `backend/app/api/routes/auth.py` :

```python
@router.get("/config", response_model=AuthConfigOut)
def auth_config(google: GoogleClient | None = Depends(get_google_client)) -> AuthConfigOut:
    return AuthConfigOut(google=google is not None, turnstile_site_key=get_settings().turnstile_site_key or None)
```

`backend/app/api/routes/google.py` :

```python
"""Connexion Google : /start redirige vers Google, /callback revient avec le code (spec 2.5)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_google_client
from app.api.origin import check_origin
from app.api.routes.auth import client_ip, fail, start_session
from app.core.config import get_settings
from app.core.current_user import get_now
from app.core.db import get_db
from app.core.security import new_token, pkce_challenge, sign, unsign
from app.schemas.auth import GoogleCompleteIn, GooglePendingOut, MeOut
from app.services.auth import accounts
from app.services.auth.google import GoogleClient, GoogleError, GoogleIdentity
from app.services.security_log import log_event

router = APIRouter(prefix="/auth/google", tags=["auth"])
OAUTH_COOKIE, PENDING_COOKIE, COOKIE_PATH = "pea_oauth", "pea_google_pending", "/api/auth/google"
OAUTH_MAX_AGE, PENDING_MAX_AGE = timedelta(minutes=10), timedelta(minutes=30)


def safe_next(value: str | None) -> str:
    """Chemin interne seulement (même règle que le frontend) : sinon l'accueil."""
    if not value or not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return "/"
    return value


def _redirect_uri() -> str:
    return get_settings().public_base_url.rstrip("/") + "/api/auth/google/callback"


def _set_cookie(response: Response, name: str, value: str, max_age: timedelta) -> None:
    response.set_cookie(name, value, max_age=int(max_age.total_seconds()), path=COOKIE_PATH, httponly=True,
                        secure=get_settings().cookie_secure, samesite="lax")


def _require(google: GoogleClient | None) -> GoogleClient:
    if google is None:
        raise HTTPException(404, detail={"code": "google_disabled", "message": "Connexion Google non configurée."})
    return google


@router.get("/start")
def start(suite: str | None = None, remember: bool = True, now: datetime = Depends(get_now),
          google: GoogleClient | None = Depends(get_google_client)) -> RedirectResponse:
    client = _require(google)
    state, nonce, verifier = new_token(), new_token(), new_token()
    response = RedirectResponse(client.authorize_url(state=state, nonce=nonce, code_challenge=pkce_challenge(verifier),
                                                     redirect_uri=_redirect_uri()), status_code=302)
    _set_cookie(response, OAUTH_COOKIE, sign({"state": state, "nonce": nonce, "verifier": verifier,
                                              "suite": safe_next(suite), "remember": remember},
                                             get_settings().app_secret, now), OAUTH_MAX_AGE)
    return response


def _error(kind: str = "google") -> RedirectResponse:
    response = RedirectResponse(f"/connexion?erreur={kind}", status_code=302)
    response.delete_cookie(OAUTH_COOKIE, path=COOKIE_PATH)
    return response


@router.get("/callback")
def callback(request: Request, state: str | None = None, code: str | None = None, db: Session = Depends(get_db),
             now: datetime = Depends(get_now), google: GoogleClient | None = Depends(get_google_client)) -> Response:
    client = _require(google)
    flow = unsign(request.cookies.get(OAUTH_COOKIE), get_settings().app_secret, now, OAUTH_MAX_AGE)
    if flow is None or not state or not code or state != flow["state"] or accounts.oauth_state_used(db, state, now):
        return _error()
    try:
        identity = client.identify(code=code, code_verifier=flow["verifier"], nonce=flow["nonce"],
                                   redirect_uri=_redirect_uri())
    except GoogleError:
        return _error()
    if not identity.email_verified or not identity.email:
        return _error("google_email")
    user = accounts.google_sign_in(db, identity, now, ip=client_ip(request))
    if user is None:
        response = RedirectResponse("/finaliser-inscription", status_code=302)
        _set_cookie(response, PENDING_COOKIE, sign({"sub": identity.sub, "email": identity.email,
                                                    "first_name": identity.first_name, "last_name": identity.last_name},
                                                   get_settings().app_secret, now), PENDING_MAX_AGE)
        db.commit()
    else:
        log_event(db, "login_ok", now=now, user_id=user.id, ip=client_ip(request), details={"method": "google"})
        response = RedirectResponse(flow["suite"], status_code=302)
        start_session(db, user, request, response, persistent=bool(flow["remember"]), now=now, alert_new_device=True)
    response.delete_cookie(OAUTH_COOKIE, path=COOKIE_PATH)
    return response
```

Rejeu du cookie : `accounts.oauth_state_used(db, state, now) -> bool` enregistre l'empreinte du `state` dans `rate_limit_hits` (bucket `oauth_state`, ajouté à `LIMITS` avec `(1, timedelta(minutes=10))`) et renvoie vrai s'il y était déjà :

```python
def oauth_state_used(db: Session, state: str, now: datetime) -> bool:
    """Un « state » Google ne sert qu'une fois (cookie rejoué = refus)."""
    if ratelimit.over(db, "oauth_state", state, now):
        return True
    ratelimit.record(db, "oauth_state", state, now)
    db.commit()
    return False
```

Suite de `google.py` :

```python
@router.get("/pending", response_model=GooglePendingOut)
def pending(request: Request, now: datetime = Depends(get_now)) -> GooglePendingOut:
    data = unsign(request.cookies.get(PENDING_COOKIE), get_settings().app_secret, now, PENDING_MAX_AGE)
    if data is None:
        raise HTTPException(404, detail={"code": "google_expired", "message": "Recommencez la connexion avec Google."})
    return GooglePendingOut(email=data["email"], first_name=data["first_name"], last_name=data["last_name"])


@router.post("/complete", response_model=MeOut, dependencies=[Depends(check_origin)])
def complete(payload: GoogleCompleteIn, request: Request, response: Response, db: Session = Depends(get_db),
             now: datetime = Depends(get_now)) -> MeOut:
    data = unsign(request.cookies.get(PENDING_COOKIE), get_settings().app_secret, now, PENDING_MAX_AGE)
    if data is None:
        raise fail(400, "google_expired", "Recommencez la connexion avec Google.")
    identity = GoogleIdentity(sub=data["sub"], email=data["email"], email_verified=True,
                              first_name=data["first_name"], last_name=data["last_name"])
    ip = client_ip(request)
    user = accounts.google_sign_in(db, identity, now, ip=ip)  # compte apparu entre-temps : simple connexion
    if user is None:
        user = accounts.create_google_account(db, identity, first_name=payload.first_name,
                                              last_name=payload.last_name, now=now)
        log_event(db, "google_signup", now=now, user_id=user.id, ip=ip)
    response.delete_cookie(PENDING_COOKIE, path=COOKIE_PATH)
    start_session(db, user, request, response, persistent=True, now=now, alert_new_device=False)
    return MeOut.model_validate(user)
```

Dans `backend/app/main.py`, ajouter `google` à l'import et à la liste des routeurs, **avant** `auth` n'est pas nécessaire (préfixes distincts).

- [ ] **Step 6: Lancer** — commande du Step 2 : tout passe ; suite complète verte.

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat: sign in with Google (link by verified address, finish sign-up after accepting terms)"
```

> **Fin du Bloc 2 — stop.** Statut : Google fonctionne côté API (testé avec un faux fournisseur). Suite : Bloc 3 (écrans). Pour l'essai réel, l'utilisateur doit déclarer `http://localhost:8095/api/auth/google/callback` comme URI de redirection autorisée dans la console Google.

---

# Bloc 3 — Écrans (frontend)

Régénérer d'abord les types : l'API de dev peut démarrer (la base réelle est déjà migrée à l'étape 1 ; la migration `b8d4f0a2c3e5` est réversible et ajoute seulement deux tables), mais la méthode hors ligne reste la plus sûre :

```bash
SP=<dossier temporaire>
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T --no-deps api python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > $SP/openapi.json
cd frontend && npx --yes openapi-typescript@7 $SP/openapi.json -o src/lib/api/schema.d.ts
```

### Task 7: Configuration publique et bouton « Continuer avec Google »

**Files:**
- Create: `frontend/src/features/auth/useAuthConfig.ts`, `frontend/src/features/auth/GoogleButton.tsx`, `frontend/src/features/auth/GoogleButton.test.tsx`
- Modify: `frontend/src/features/auth/SignInForm.tsx`, `frontend/src/features/auth/SignUpForm.tsx`, `frontend/src/lib/api/schema.d.ts` (régénéré), `frontend/src/lib/api/client.ts` (`export type AuthConfig = components["schemas"]["AuthConfigOut"]`)

**Interfaces:**
- Produces: `useAuthConfig(): AuthConfig | undefined` (clé `["auth-config"]`, `staleTime: Infinity`) ; `<GoogleButton suite={string} remember={boolean} />` (rendu vide si Google désactivé) — lien `/api/auth/google/start?suite=…&remember=1|0`, suivi du séparateur « ou » ; messages `?erreur=google` et `?erreur=google_email` affichés par `SignInForm`.

- [ ] **Step 1: Tests qui échouent** — `frontend/src/features/auth/GoogleButton.test.tsx` :

```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { mockFetch } from "@/test/utils";
import { AuthPage } from "./AuthPage";

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string, google: boolean) {
  mockFetch((url) => ({ body: url === "/api/auth/config" ? { google, turnstile_site_key: null } : {} }));
  const router = createMemoryRouter([
    { path: "/connexion", element: <AuthPage mode="connexion" /> },
    { path: "/inscription", element: <AuthPage mode="inscription" /> },
  ], { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
}

test("le bouton Google garde la page où revenir", async () => {
  renderAt("/connexion?suite=%2Fportefeuille", true);
  const link = await screen.findByRole("link", { name: "Continuer avec Google" });
  expect(link).toHaveAttribute("href", "/api/auth/google/start?suite=%2Fportefeuille&remember=0");
  expect(screen.getByText("ou")).toBeInTheDocument();
});

test("sans Google configuré, pas de bouton", async () => {
  renderAt("/inscription", false);
  await screen.findByRole("heading", { level: 1, name: "Créer un compte" });
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(screen.queryByRole("link", { name: "Continuer avec Google" })).toBeNull();
});

test.each([
  ["google", "La connexion avec Google n'a pas abouti. Réessayez."],
  ["google_email", "Votre adresse Google n'est pas validée par Google : utilisez une autre méthode."],
])("erreur %s au retour de Google", async (code, message) => {
  renderAt(`/connexion?erreur=${code}`, true);
  expect(await screen.findByRole("alert")).toHaveTextContent(message);
});
```

- [ ] **Step 2: Lancer** — `cd frontend && npx vitest --run src/features/auth/GoogleButton.test.tsx` → FAIL (lien introuvable).

- [ ] **Step 3: Implémentation** — `useAuthConfig.ts` :

```ts
import { useQuery } from "@tanstack/react-query";
import { apiGet, type AuthConfig } from "@/lib/api/client";

/** Ce que le serveur active : bouton Google, clé publique Turnstile. Ne change pas pendant la visite. */
export function useAuthConfig(): AuthConfig | undefined {
  return useQuery({ queryKey: ["auth-config"], queryFn: () => apiGet<AuthConfig>("/api/auth/config"), staleTime: Infinity }).data;
}
```

`GoogleButton.tsx` :

```tsx
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { safeNext } from "./redirect";
import { useAuthConfig } from "./useAuthConfig";

/** « Continuer avec Google » puis le séparateur « ou » ; rien si Google n'est pas configuré. */
export function GoogleButton({ suite, remember }: { suite: string | null; remember: boolean }) {
  const config = useAuthConfig();
  if (!config?.google) return null;
  const query = new URLSearchParams({ suite: safeNext(suite), remember: remember ? "1" : "0" });
  return (
    <>
      <a href={`/api/auth/google/start?${query}`} className={cn(buttonVariants({ variant: "outline" }), "w-full gap-2 bg-white")}>
        <GoogleLogo />
        Continuer avec Google
      </a>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />ou<span className="h-px flex-1 bg-border" />
      </div>
    </>
  );
}

function GoogleLogo() {
  return (
    <svg viewBox="0 0 48 48" className="size-4" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.5 5.8c4.4-4 6.8-10 6.8-17.2z" />
      <path fill="#FBBC05" d="M10.6 28.6A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.8-4.6l-7.9-6.1A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.7l8-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.2 0-11.5-4.1-13.4-9.9l-8 6.1C6.6 42.6 14.6 48 24 48z" />
    </svg>
  );
}
```

Dans `SignInForm.tsx` : juste après le bloc titre, `<GoogleButton suite={params.get("suite")} remember={remember} />` ; et avant le bouton d'envoi, l'erreur de retour :

```tsx
const GOOGLE_ERRORS: Record<string, string> = {
  google: "La connexion avec Google n'a pas abouti. Réessayez.",
  google_email: "Votre adresse Google n'est pas validée par Google : utilisez une autre méthode.",
};
// …
const googleError = GOOGLE_ERRORS[params.get("erreur") ?? ""];
// …
{googleError && !login.error && <p role="alert" className="text-sm text-red-600">{googleError}</p>}
```

Dans `SignUpForm.tsx` : après le bloc titre, `<GoogleButton suite={params.get("suite")} remember />` (ajouter `useSearchParams` s'il manque).

- [ ] **Step 4: Lancer** — commande du Step 2 : 4 passed ; `npx vitest --run` complet vert ; `npx tsc -b` propre. Les tests existants d'`AuthPage` qui renvoient `{}` pour toute URL restent verts (`google` indéfini ⇒ pas de bouton).

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: Continue with Google button and Google error messages on the sign-in screen"
```

### Task 8: Widget Turnstile (inscription, mot de passe oublié, connexion après 3 échecs)

**Files:**
- Create: `frontend/src/features/auth/Turnstile.tsx`, `frontend/src/features/auth/Turnstile.test.tsx`
- Modify: `SignUpForm.tsx`, `ForgotPasswordPage.tsx`, `SignInForm.tsx`

**Interfaces:**
- Consumes: `useAuthConfig().turnstile_site_key` (Task 7) ; codes d'erreur `captcha_required`, `too_many_requests`, `account_locked`, `pwned_password` (Bloc 1).
- Produces: `<Turnstile siteKey={string} onToken={(token: string | null) => void} />` — charge une seule fois `https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit`, appelle `window.turnstile.render(div, {sitekey, callback, "expired-callback", "error-callback"})`, et `window.turnstile.remove(id)` au démontage. Les formulaires envoient `captcha: token` ; ils remontent le widget (prop `key`) après chaque réponse d'erreur, un jeton ne servant qu'une fois.

- [ ] **Step 1: Tests qui échouent** — `Turnstile.test.tsx` (le script Cloudflare n'est jamais chargé : `window.turnstile` est posé à la main, et le composant ne rajoute pas de `<script>` s'il existe déjà) :

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { mockFetch } from "@/test/utils";
import { AuthPage } from "./AuthPage";
import { ForgotPasswordPage } from "./ForgotPasswordPage";

type Options = { callback: (token: string) => void };

beforeEach(() => {
  (window as unknown as { turnstile: unknown }).turnstile = {
    render: (_el: HTMLElement, options: Options) => { options.callback("jeton-du-widget"); return "w1"; },
    remove: vi.fn(),
  };
});
afterEach(() => vi.unstubAllGlobals());

function renderPage(element: React.ReactElement, path: string) {
  const router = createMemoryRouter([{ path: path.split("?")[0], element }], { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
}

test("le mot de passe oublié envoie le jeton du widget", async () => {
  const fetchMock = mockFetch((url) => ({ body: url === "/api/auth/config"
    ? { google: false, turnstile_site_key: "cle-publique" } : { message: "Si un compte utilise cette adresse, un lien vient d'y être envoyé." } }));
  renderPage(<ForgotPasswordPage />, "/mot-de-passe-oublie");
  await userEvent.type(await screen.findByLabelText("Adresse mail"), "jean@example.com");
  await waitFor(() => expect(screen.getByRole("button", { name: /Recevoir/ })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: /Recevoir/ }));
  const body = JSON.parse(fetchMock.mock.calls.find(([u]) => u === "/api/auth/forgot-password")![1].body);
  expect(body).toEqual({ email: "jean@example.com", captcha: "jeton-du-widget" });
});

test("la connexion ne montre le widget qu'après la demande du serveur", async () => {
  let attempts = 0;
  mockFetch((url) => {
    if (url === "/api/auth/config") return { body: { google: false, turnstile_site_key: "cle-publique" } };
    attempts++;
    return { status: 400, body: { detail: { code: "captcha_required", message: "Confirmez que vous n'êtes pas un robot, puis réessayez." } } };
  });
  renderPage(<AuthPage mode="connexion" />, "/connexion");
  expect(document.querySelector("[data-turnstile]")).toBeNull();
  await userEvent.type(await screen.findByLabelText("Adresse mail"), "jean@example.com");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "motdepasse-solide");
  await userEvent.click(screen.getByRole("button", { name: "Me connecter" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Confirmez que vous n'êtes pas un robot");
  expect(document.querySelector("[data-turnstile]")).not.toBeNull();
  expect(attempts).toBe(1);
});
```

Adapter le libellé du bouton de `ForgotPasswordPage` à l'existant (lire le fichier ; le test doit viser son vrai nom accessible).

- [ ] **Step 2: Lancer** — `cd frontend && npx vitest --run src/features/auth/Turnstile.test.tsx` → FAIL.

- [ ] **Step 3: Implémentation** — `Turnstile.tsx` :

```tsx
import { useEffect, useRef } from "react";

type TurnstileApi = {
  render: (element: HTMLElement, options: Record<string, unknown>) => string;
  remove: (id: string) => void;
};
declare global {
  interface Window { turnstile?: TurnstileApi }
}

const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let loading: Promise<void> | null = null;

function loadTurnstile(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => { loading = null; reject(new Error("Turnstile indisponible")); };
    document.head.appendChild(script);
  });
  return loading;
}

/** Case anti-robot Cloudflare. `onToken(null)` quand le jeton expire ou en cas d'erreur. */
export function Turnstile({ siteKey, onToken }: { siteKey: string; onToken: (token: string | null) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const callback = useRef(onToken);
  callback.current = onToken;

  useEffect(() => {
    let id: string | null = null;
    let cancelled = false;
    loadTurnstile().then(() => {
      if (cancelled || !box.current || !window.turnstile) return;
      id = window.turnstile.render(box.current, {
        sitekey: siteKey, language: "fr",
        callback: (token: string) => callback.current(token),
        "expired-callback": () => callback.current(null),
        "error-callback": () => callback.current(null),
      });
    }).catch(() => callback.current(null));
    return () => {
      cancelled = true;
      if (id && window.turnstile) window.turnstile.remove(id);
    };
  }, [siteKey]);

  return <div ref={box} data-turnstile className="min-h-[65px]" />;
}
```

Intégration (même schéma dans les trois formulaires) :

```tsx
const siteKey = useAuthConfig()?.turnstile_site_key ?? null;
const [captcha, setCaptcha] = useState<string | null>(null);
const [captchaRound, setCaptchaRound] = useState(0); // nouvelle case après chaque refus : un jeton ne sert qu'une fois
// dans le mutationFn : { ...champs, captcha }
// dans onError : setCaptcha(null); setCaptchaRound((n) => n + 1);
{siteKey && <Turnstile key={captchaRound} siteKey={siteKey} onToken={setCaptcha} />}
```

- `SignUpForm` et `ForgotPasswordPage` : widget toujours affiché quand `siteKey` existe ; si `siteKey && !captcha` à l'envoi, alerte locale « Cochez la case anti-robot. » sans appel réseau.
- `SignInForm` : état `needCaptcha` (faux au départ) mis à vrai quand `error.code === "captcha_required"` ; widget affiché seulement si `siteKey && needCaptcha`.
- Messages : les erreurs `too_many_requests`, `account_locked`, `pwned_password` s'affichent telles que le serveur les écrit (déjà le cas via `ApiError.message`).

- [ ] **Step 4: Lancer** — commande du Step 2 puis suite complète : vert ; `npx tsc -b` propre ; `npm run lint` sans nouvel avertissement.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: Cloudflare Turnstile on sign-up, forgotten password and sign-in after failures"
```

### Task 9: Écran « Finaliser l'inscription » (Google)

**Files:**
- Create: `frontend/src/features/auth/FinishSignUpPage.tsx`, `frontend/src/features/auth/FinishSignUpPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Consumes: `GET /api/auth/google/pending`, `POST /api/auth/google/complete` (Task 6) ; `AuthCard` ; `["me"]` en cache.
- Produces: route `/finaliser-inscription` (hors mise en page, `noindex`).

- [ ] **Step 1: Tests qui échouent** — `FinishSignUpPage.test.tsx` :

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ME, mockFetch } from "@/test/utils";
import { FinishSignUpPage } from "./FinishSignUpPage";

afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  const router = createMemoryRouter([
    { path: "/finaliser-inscription", element: <FinishSignUpPage /> },
    { path: "/", element: <h1>Accueil</h1> },
    { path: "/inscription", element: <h1>Créer un compte</h1> },
  ], { initialEntries: ["/finaliser-inscription"] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("reprend le nom donné par Google et demande les CGU", async () => {
  const fetchMock = mockFetch((url) => ({ body: url === "/api/auth/google/pending"
    ? { email: "jean@gmail.com", first_name: "Jean", last_name: "Dupont" } : ME }));
  const router = renderPage();
  expect(await screen.findByDisplayValue("Jean")).toBeInTheDocument();
  expect(screen.getByText("jean@gmail.com")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Terminer mon inscription" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Acceptez les CGU");
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Terminer mon inscription" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  const body = JSON.parse(fetchMock.mock.calls.find(([u]) => u === "/api/auth/google/complete")![1].body);
  expect(body).toEqual({ first_name: "Jean", last_name: "Dupont", accept_terms: true });
});

test("sans connexion Google en cours, retour à l'inscription", async () => {
  mockFetch(() => ({ status: 404, body: { detail: { code: "google_expired", message: "Recommencez la connexion avec Google." } } }));
  const router = renderPage();
  await waitFor(() => expect(router.state.location.pathname).toBe("/inscription"));
});
```

- [ ] **Step 2: Lancer** — `npx vitest --run src/features/auth/FinishSignUpPage.test.tsx` → FAIL (module absent).

- [ ] **Step 3: Implémentation** — `FinishSignUpPage.tsx` :

```tsx
import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiSend, type Me } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";

type Pending = { email: string; first_name: string; last_name: string };

export function FinishSignUpPage() {
  usePageMeta({ title: "Finaliser l'inscription", description: "Derniers détails avant d'utiliser PEA Radar.", noindex: true });
  const pending = useQuery({ queryKey: ["google-pending"], queryFn: () => apiGet<Pending>("/api/auth/google/pending"), retry: false });
  if (pending.isError) return <Navigate to="/inscription" replace />;
  return (
    <AuthCard title="Finaliser l'inscription">
      {pending.data && <FinishForm pending={pending.data} />}
    </AuthCard>
  );
}

function FinishForm({ pending }: { pending: Pending }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [firstName, setFirstName] = useState(pending.first_name);
  const [lastName, setLastName] = useState(pending.last_name);
  const [terms, setTerms] = useState(false);
  const [local, setLocal] = useState<string | null>(null);
  const complete = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/google/complete",
      { first_name: firstName, last_name: lastName, accept_terms: terms }) as Promise<Me>,
    onSuccess: (me) => {
      queryClient.setQueryData(["me"], me);
      navigate("/", { replace: true });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!terms) return setLocal("Acceptez les CGU et la politique de confidentialité pour continuer.");
    setLocal(null);
    complete.mutate();
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">Compte Google : <strong>{pending.email}</strong></p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="finish-first-name" className="text-sm font-medium">Prénom</label>
          <Input id="finish-first-name" value={firstName} onChange={(e) => setFirstName(e.target.value)} required maxLength={100} className="bg-white" />
        </div>
        <div className="space-y-1">
          <label htmlFor="finish-last-name" className="text-sm font-medium">Nom</label>
          <Input id="finish-last-name" value={lastName} onChange={(e) => setLastName(e.target.value)} required maxLength={100} className="bg-white" />
        </div>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-1" />
        <span>J'accepte les <Link to="/cgu" className="text-primary underline">CGU</Link> et la{" "}
          <Link to="/confidentialite" className="text-primary underline">politique de confidentialité</Link>.</span>
      </label>
      {(local || complete.error) && <p role="alert" className="text-sm text-red-600">{local ?? complete.error?.message}</p>}
      <Button type="submit" disabled={complete.isPending}>{complete.isPending ? "Création…" : "Terminer mon inscription"}</Button>
    </form>
  );
}
```

Dans `router.tsx`, à côté des autres écrans de compte :

```tsx
  { path: "/finaliser-inscription", lazy: async () => ({ Component: (await import("@/features/auth/FinishSignUpPage")).FinishSignUpPage }) },
```

Le libellé de l'alerte du test (« Acceptez les CGU ») est un début de la phrase ci-dessus : garder les deux cohérents.

- [ ] **Step 4: Lancer** — suite frontend complète verte, `npx tsc -b`, `npm run lint`, `npm run build`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: finish sign-up screen for new Google accounts"
```

> **Fin du Bloc 3 — stop.** Statut : écrans prêts. Suite : Bloc 4 (en-têtes nginx, e2e, docs, vérification finale, PR).

---

# Bloc 4 — En-têtes nginx, vérification de bout en bout, documentation

### Task 10: En-têtes de sécurité nginx, HSTS par variable, Docsify sans script en ligne

**Files:**
- Create: `frontend/nginx/default.conf.template` (contenu de l'actuel `frontend/nginx.conf`, modifié), `frontend/nginx/security-headers.conf`, `frontend/public/guide/config.js`, `frontend/public/documentation/config.js`, `frontend/e2e/headers.spec.ts`
- Delete: `frontend/nginx.conf`
- Modify: `frontend/Dockerfile`, `docker-compose.yml` (service `web`), `frontend/public/guide/index.html`, `frontend/public/documentation/index.html`

**Interfaces:**
- Produces: en-têtes sur toutes les réponses de `web` ; `HSTS_ENABLED=true` ⇒ `Strict-Transport-Security: max-age=31536000; includeSubDomains`.

- [ ] **Step 1: Test e2e qui échoue** — `frontend/e2e/headers.spec.ts` :

```ts
import { expect, test } from "@playwright/test";

test("en-têtes de sécurité sur l'application", async ({ request }) => {
  const headers = (await request.get("/")).headers();
  expect(headers["content-security-policy"]).toContain("default-src 'self'");
  expect(headers["content-security-policy"]).toContain("https://challenges.cloudflare.com");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["permissions-policy"]).toContain("camera=()");
  expect(headers["strict-transport-security"]).toBeUndefined(); // HTTP en local
  const asset = (await request.get("/")).text();
  const script = (await asset).match(/\/assets\/[^"]+\.js/)?.[0];
  expect((await request.get(script!)).headers()["x-content-type-options"]).toBe("nosniff"); // aussi sous /assets/
});

for (const path of ["/", "/explorer", "/connexion", "/inscription", "/guide/", "/documentation/"]) {
  test(`aucune violation CSP sur ${path}`, async ({ page }) => {
    const violations: string[] = [];
    page.on("console", (message) => { if (/Content Security Policy/i.test(message.text())) violations.push(message.text()); });
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(violations).toEqual([]);
  });
}
```

Reconstruire et lancer : `docker compose up -d --build web && cd frontend && npx playwright test e2e/headers.spec.ts` → FAIL (en-têtes absents).

- [ ] **Step 2: En-têtes** — `frontend/nginx/security-headers.conf` :

```nginx
# Inclus dans server et dans chaque location qui ajoute ses propres en-têtes (sinon nginx ne les hérite pas).
add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=(), usb=()" always;
add_header X-Frame-Options "DENY" always;
add_header Strict-Transport-Security $hsts always;
```

`frontend/nginx/default.conf.template` = l'actuel `nginx.conf`, avec en tête :

```nginx
# HSTS seulement derrière HTTPS (HSTS_ENABLED=true dans .env) ; une valeur vide n'envoie pas l'en-tête.
map "${HSTS_ENABLED}" $hsts {
  "true"  "max-age=31536000; includeSubDomains";
  default "";
}
```

`include /etc/nginx/security-headers.conf;` ajouté juste après `root …;` dans `server`, **et** dans `location /assets/` après son `add_header Cache-Control …`.

`frontend/Dockerfile`, étape nginx :

```dockerfile
FROM nginx:1.27-alpine
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
```

`docker-compose.yml`, service `web` :

```yaml
    environment:
      HSTS_ENABLED: ${HSTS_ENABLED:-false}
      NGINX_ENVSUBST_FILTER: "^HSTS_"  # ne remplacer que nos variables, jamais $host & co
```

Supprimer `frontend/nginx.conf` (`git rm`).

- [ ] **Step 3: Docsify sans script en ligne** — déplacer le contenu du `<script>` en ligne de `public/guide/index.html` (lignes 15 à la balise fermante) dans `public/guide/config.js`, tel quel, et remplacer le bloc par `<script src="config.js"></script>` **au même endroit** (avant `back-to-app.js`). Même chose pour `public/documentation/index.html` → `public/documentation/config.js`.

- [ ] **Step 4: Lancer** — `docker compose up -d --build web && cd frontend && npx playwright test e2e/headers.spec.ts` → 7 passed.
  - Si Docsify déclenche une violation (`unsafe-eval` ou style), ne pas affaiblir la CSP de l'application : ajouter pour `location ~ ^/(guide|documentation|docsify)/` un `add_header Content-Security-Policy` propre (plus les autres en-têtes, qui ne s'héritent plus) avec la seule directive supplémentaire nécessaire, et consigner la décision dans le ledger.
  - Si Turnstile n'est pas configuré en local, l'iframe n'est jamais chargée : le test vérifie seulement que la CSP l'autorise.

- [ ] **Step 5: Suite e2e complète** — `cd frontend && npm run e2e` → tout passe (27 + 7).

- [ ] **Step 6: Commit**

```bash
git add frontend docker-compose.yml
git rm --cached frontend/nginx.conf 2>/dev/null; git add -A frontend/nginx.conf
git commit -m "feat: nginx security headers (CSP, frame, nosniff, referrer, permissions, optional HSTS)"
```

### Task 11: Documentation, vérification finale, PR

**Files:**
- Modify: `frontend/public/guide/app/compte.md`, `frontend/public/guide/faq.md`, `frontend/public/documentation/comptes.md`, `api.md`, `base-de-donnees.md`, `installation.md`, `architecture.md`, `developpement.md`, `seo.md`, `CLAUDE.md`, `README.md`

- [ ] **Step 1: Guide** (`app/compte.md`, sans nom de fichier ni commande) : bouton « Continuer avec Google » (premier passage : écran « Finaliser l'inscription » avec les CGU ; compte existant avec la même adresse : il est associé et un mail prévient) ; case anti-robot (inscription, mot de passe oublié, connexion après plusieurs erreurs) ; blocage 15 minutes après 10 mots de passe faux ; refus d'un mot de passe « apparu dans des fuites » et comment en choisir un bon (phrase de plusieurs mots, unique). FAQ : « Je suis bloqué après plusieurs essais » et « Pourquoi mon mot de passe est refusé ? ».

- [ ] **Step 2: Documentation admin** :
  - `comptes.md` : tableau des limites (spec 2.4, avec les buckets de `ratelimit.LIMITS`) ; journal (`security_events`, liste des `kind`, 12 mois, requête SQL d'exemple) ; flux Google (schéma start → Google → callback → session ou `/finaliser-inscription`, cookies `pea_oauth` et `pea_google_pending`, rattachement et effacement du mot de passe d'un compte jamais validé) ; Turnstile (désactivé si clé secrète vide ; comportement si Cloudflare ne répond pas) ; HIBP (k-anonymat, 2 s, `HIBP_ENABLED`) ; contrôle `Origin` ; section « Étape suivante » mise à jour (comptes-admin).
  - `installation.md` : créer le client OAuth Google (type « Application Web », URI de redirection `http://localhost:8095/api/auth/google/callback` en local, `https://<domaine>/api/auth/google/callback` en ligne, origine JavaScript inutile) ; créer un widget Turnstile (domaines `localhost` et le domaine public) ; `HSTS_ENABLED` ; tableau `.env` complété.
  - `api.md` : `/auth/config`, `/auth/google/*`, nouveaux codes d'erreur (`captcha_required`, `account_locked`, `too_many_requests`, `pwned_password`, `bad_origin`, `google_expired`).
  - `base-de-donnees.md` : `security_events`, `rate_limit_hits`.
  - `architecture.md` : configuration (nouvelles variables), en-têtes nginx, fournisseurs externes (Google, Cloudflare, HIBP).
  - `developpement.md` : fixtures `fake_captcha`, `fake_breach`, `fake_google` ; « aucun test n'appelle Google, Cloudflare ni HIBP ».
  - `seo.md` : « À prévoir avant une mise en ligne » : `HSTS_ENABLED=true`, domaines du widget Turnstile, URI de redirection Google du domaine.

- [ ] **Step 3: CLAUDE.md et README** : fournisseurs externes et leurs faux ; limites ; « ne jamais affaiblir la CSP de l'app pour une page de doc » ; `HSTS_ENABLED` ; nouvelles variables `.env` ; nombre de tests.

- [ ] **Step 4: Vérification finale** (coller les lignes de résumé dans le statut) :
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
  - `cd frontend && npx vitest --run && npx tsc -b && npm run lint && npm run build`
  - `docker compose up -d --build && docker compose exec -T api alembic check` → aucune différence
  - `cd frontend && npm run e2e` → tout passe (dont `documentation.spec.ts` et `headers.spec.ts`)
  - Essai réel de Google si l'utilisateur a déclaré l'URI de redirection : `/connexion` → « Continuer avec Google » → compte de l'utilisateur rattaché (mail « Un compte Google a été associé » reçu via Brevo) → retour connecté.
  - Reprendre la Review Focus point par point.

- [ ] **Step 5: Commit, push, PR**

```bash
git add -A && git commit -m "docs: Google sign-in, Turnstile, limits, breach check and security headers"
git push -u origin comptes-securite
```

Lien : `https://github.com/gbtclement/PEA/compare/comptes-socle...comptes-securite?expand=1` si `comptes-socle` n'est pas fusionnée, sinon `master...comptes-securite`. Titre : « Comptes utilisateurs : sécurité (Google, Turnstile, limites, en-têtes) ». Corps terminé par `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

> **Fin du Bloc 4 — stop.** Statut : branche prête pour la PR. Suite : étape 3 (`comptes-admin`), avec son propre plan.
