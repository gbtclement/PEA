# Comptes utilisateurs, étape 1 (`comptes-socle`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Stop after each block.** The user asked to stop at the end of every block (Bloc 1 to Bloc 5) so they can `/compact`. At the end of a block: all tests of the block pass, everything is committed, give a short status in French (done / next block / this file's path) and wait for the user's go.

**Goal:** Replace the single default user with real accounts: e-mail + password sign-up validated by a 6-digit code, sign-in with server-side sessions, forgot password, new-device alert, an e-mail outbox sent by the worker (Mailpit locally), the sliding sign-in/sign-up screen, public showcase pages vs. private app pages, and the takeover of the existing "Moi" data by the `ADMIN_EMAIL` account.

**Architecture:**
- **Data**: `users.id` becomes a UUID (one-way Alembic migration that converts every `user_id`). New tables `sessions`, `known_devices`, `email_codes`, `email_log`.
- **Auth**: an opaque random token in an `HttpOnly` cookie `pea_session`, only its SHA-256 stored in `sessions`; CSRF double-submit (`pea_csrf` cookie echoed in `X-CSRF-Token`). A session only ever exists for a **verified** user, so `get_current_user()` means "signed-in and verified". `get_optional_user()` serves the public pages.
- **Mail**: the API only writes rows in `email_log` (outbox, same transaction as the action); the worker sends them over SMTP every 5 s with retries. Jinja2 templates, HTML + text.
- **Frontend**: `useMe()` (GET `/api/me`, `null` when anonymous), a `RequireAuth` route wrapper for private pages, full-screen auth pages outside `Layout`.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, argon2-cffi, Jinja2, email-validator, smtplib, APScheduler, React 19, react-router 7, TanStack Query, Tailwind 4, Vitest, Playwright, Mailpit.

**Spec:** `docs/superpowers/specs/2026-09-28-comptes-utilisateurs-design.md` (sections 1, 2.1–2.3, 3, 5, 7, 8, 9, 11 step 1). Read it first.

## Global Constraints

- **Language**: UI text, visible errors, comments and docstrings in **French**; identifiers in English; commits in English, conventional commits, ending with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Commands** (host has no Python/Node guaranteed, everything in Docker, from the repo root):
  - backend dev stack: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db api worker mailpit`
  - backend tests: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` (add a path/`-k` to target)
  - after changing `pyproject.toml`: `docker compose -f docker-compose.yml -f docker-compose.dev.yml build api worker`
  - frontend: `cd frontend && npm test -- --run <path>`, `npm run lint`, `npm run build` (Node on the host; if missing, `docker run --rm -v "$PWD/frontend:/app" -w /app node:22-alpine sh -c "npm ci && npm test"`)
  - full app: `docker compose up -d --build` then http://localhost:8095; Mailpit UI http://localhost:8025
- **Secrets** only in `.env` (never in DB, never logged, never sent to the browser). Tokens, codes and session ids are stored **hashed** (SHA-256 hex), compared with `hmac.compare_digest`.
- **Passwords**: Argon2id (`argon2-cffi` defaults), 12 to 128 characters, no composition rule.
- **Codes**: 6 digits, 15 min, 5 attempts, resend after 60 s, a new code cancels the previous one. Reset link: 256-bit token, 30 min, single use. "Ce n'était pas moi" link: 7 days.
- **Sessions**: 30 days sliding with "Rester connecté" (and right after sign-up), otherwise browser-session cookie and 12 h sliding server-side; `last_seen_at` refreshed at most once a minute.
- **Cookies**: `pea_session` (HttpOnly), `pea_csrf` (readable by JS), `pea_device` (HttpOnly, 1 year); all `SameSite=Lax`, `Path=/`, `Secure` unless `COOKIE_SECURE=false`.
- **No user enumeration**: sign-up, resend and forgot-password answer the same thing whether the address exists or not.
- **Error bodies** of the new endpoints: `{"detail": {"code": "<snake_case>", "message": "<French sentence>"}}`.
- **Public vs private** (spec 3.1): public = home, explorer, ETF, security pages, their APIs, status, fees estimate, simulation, legal pages, auth pages. Private = portfolio, favorites, orders, settings, assistant, **forecasts (page, API and the forecast card)**. The eligibility override (global data) becomes **admin-only**.
- **Layout**: app pages desktop from 1024 px; auth screens also usable below 768 px. One `h1` per page. Private and auth pages `noindex` except `/connexion` and `/inscription`.
- **Ports**: web 8095, API dev 8000, Vite 5180, Mailpit UI 8025. Never 8080, 8081, 5173.
- **Tests never call** a real SMTP server, Yahoo or Anthropic.

## Review Focus

1. **Enumeration through side channels**: sign-up with an already verified address must return exactly the same status/body as a fresh one and must not set a cookie; `forgot-password` and `resend-code` likewise. Tests in Tasks 8 and 9 compare full responses.
2. **Cross-user access with a valid session**: user A must get 404/empty on B's orders, conversations and favorites; UUIDs of other users never leak in responses. Test in Task 7.
3. **Code brute force and replay**: the 6th wrong code fails even if correct; a used code, reset token or not-me token cannot be reused; an older code stops working when a new one is issued. Tests in Tasks 8 and 9.
4. **Open redirect through `?suite=`**: `//evil.com`, `https://evil.com`, `/\evil.com` must all fall back to `/`. Test in Task 11.
5. **Restart safety of the admin takeover**: running `bootstrap-admin` twice sends only one reset mail and never duplicates or loses "Moi"'s data; the migration keeps orders/favorites/conversations/settings attached. Tests in Tasks 3 and 10.

---

# Bloc 1 — Données et migration

### Task 1: Dependencies, settings and security primitives

**Files:**
- Modify: `backend/pyproject.toml`, `backend/app/core/config.py`
- Create: `backend/app/core/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Produces (in `app.core.security`): `hash_password(password: str) -> str`, `verify_password(password_hash: str | None, password: str) -> bool`, `needs_rehash(password_hash: str) -> bool`, `password_problem(password: str) -> str | None`, `new_token() -> str`, `token_hash(token: str) -> str`, `new_code() -> str`, `same(a: str, b: str) -> bool`, `truncate_ip(ip: str | None) -> str | None`, `device_label(user_agent: str | None) -> str`, `normalize_email(email: str) -> str`.
- Produces settings: `admin_email`, `cookie_secure`, `session_days`, `session_short_hours`, `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_tls`, `mail_from`.

- [ ] **Step 1: Add dependencies**

In `backend/pyproject.toml` `dependencies`, add:
```toml
  "argon2-cffi>=23.1",
  "jinja2>=3.1",
  "email-validator>=2.2",
```
and in `[tool.setuptools.package-data]` add `"app.services.mail" = ["templates/*"]`.
Rebuild: `docker compose -f docker-compose.yml -f docker-compose.dev.yml build api worker`.

- [ ] **Step 2: Write the failing tests** — `backend/tests/test_security.py`

```python
from app.core.security import (
    device_label, hash_password, needs_rehash, new_code, new_token, normalize_email, password_problem, same,
    token_hash, truncate_ip, verify_password,
)


def test_password_hash_roundtrip():
    stored = hash_password("correct horse battery")
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, "correct horse battery")
    assert not verify_password(stored, "wrong horse battery")
    assert not needs_rehash(stored)


def test_verify_password_without_hash_is_false():
    # compte sans mot de passe (Google, ou admin repris) : jamais de connexion par mot de passe
    assert not verify_password(None, "n'importe quoi")


def test_password_rules():
    assert password_problem("court") == "Le mot de passe doit contenir au moins 12 caractères."
    assert password_problem("x" * 129) == "Le mot de passe ne doit pas dépasser 128 caractères."
    assert password_problem("douze-lettres") is None


def test_tokens_and_codes():
    assert len(new_token()) >= 43 and new_token() != new_token()
    assert len(token_hash("abc")) == 64 and token_hash("abc") == token_hash("abc")
    codes = {new_code() for _ in range(50)}
    assert all(len(c) == 6 and c.isdigit() for c in codes) and len(codes) > 1
    assert same("abc", "abc") and not same("abc", "abd")


def test_truncate_ip():
    assert truncate_ip("203.0.113.57") == "203.0.113.0/24"
    assert truncate_ip("2001:db8:1234:5678::1") == "2001:db8:1234::/48"
    assert truncate_ip("pas une ip") is None
    assert truncate_ip(None) is None


def test_device_label():
    chrome_windows = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
    safari_iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
    firefox_android = "Mozilla/5.0 (Android 15; Mobile; rv:140.0) Gecko/140.0 Firefox/140.0"
    assert device_label(chrome_windows) == "Chrome sur Windows"
    assert device_label(safari_iphone) == "Safari sur iOS"
    assert device_label(firefox_android) == "Firefox sur Android"
    assert device_label(None) == "Navigateur inconnu sur système inconnu"


def test_normalize_email():
    assert normalize_email("  Jean.Dupont@Example.COM ") == "jean.dupont@example.com"
```

- [ ] **Step 3: Run and see it fail**: `... run --rm -T api pytest -q tests/test_security.py` → `ModuleNotFoundError: app.core.security`.

- [ ] **Step 4: Implement** — `backend/app/core/security.py`

```python
"""Primitives de sécurité : mots de passe, jetons, codes. Fonctions pures, sans base ni réseau."""
import hashlib
import hmac
import ipaddress
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

_hasher = PasswordHasher()  # Argon2id, paramètres recommandés par la bibliothèque
# Vérifier contre un faux hachage quand le compte n'existe pas : même durée de réponse dans les deux cas.
_DUMMY_HASH = _hasher.hash("pas-un-vrai-mot-de-passe")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        ok = _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return ok and password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_problem(password: str) -> str | None:
    """Message à afficher si le mot de passe est refusé, sinon None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Le mot de passe ne doit pas dépasser {PASSWORD_MAX_LENGTH} caractères."
    return None


def new_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def truncate_ip(ip: str | None) -> str | None:
    """IP réduite à son réseau (/24 ou /48) : assez pour repérer une anomalie, pas pour identifier quelqu'un."""
    if not ip:
        return None
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return None
    prefix = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


# L'ordre compte : Edge et Opera contiennent « Chrome/ », Chrome contient « Safari/ » ;
# Android contient « Linux », iOS contient « Mac OS X ».
_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
_SYSTEMS = (("Windows", "Windows"), ("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iPadOS"),
            ("Mac OS X", "macOS"), ("Linux", "Linux"))


def device_label(user_agent: str | None) -> str:
    ua = user_agent or ""
    browser = next((name for key, name in _BROWSERS if key in ua), "Navigateur inconnu")
    system = next((name for key, name in _SYSTEMS if key in ua), "système inconnu")
    return f"{browser} sur {system}"


def normalize_email(email: str) -> str:
    return email.strip().lower()
```

- [ ] **Step 5: Add settings** — in `Settings` of `backend/app/core/config.py`, after `seo_indexing`:

```python
    # Comptes : ADMIN_EMAIL désigne le compte administrateur (reprend les données de « Moi »)
    admin_email: str = ""
    cookie_secure: bool = True  # false seulement en local sans HTTPS
    session_days: int = 30
    session_short_hours: int = 12

    # Envoi des mails (SMTP) ; SMTP_HOST vide = les mails restent en file d'attente
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: str = "starttls"  # starttls | ssl | none
    mail_from: str = "PEA Radar <no-reply@localhost>"
```

- [ ] **Step 6: Run and see it pass**: `pytest -q tests/test_security.py` → all PASS.

- [ ] **Step 7: Commit**: `git add backend/pyproject.toml backend/app/core/config.py backend/app/core/security.py backend/tests/test_security.py && git commit -m "feat: password hashing, tokens and account settings"`

### Task 2: Models (UUID users, sessions, codes, outbox)

**Files:**
- Modify: `backend/app/models/user.py`, `favorite.py`, `portfolio.py`, `assistant.py`, `__init__.py`, `backend/app/core/current_user.py` (temporary default user), `backend/app/repositories/*.py` (type hints `int` → `uuid.UUID` for `user_id`), `backend/app/services/assistant/streaming.py` (type hint)
- Create: `backend/app/models/auth.py`, `backend/app/models/email.py`
- Modify tests: `backend/tests/factories.py`, `backend/tests/test_models.py`, `backend/tests/test_api_conversations.py`
- Test: `backend/tests/test_models_auth.py`

**Interfaces:**
- Produces: `User` (fields of spec 1.1, `id: uuid.UUID`), `LEGACY_EMAIL = "moi@pea-radar.invalid"` in `app.models.user`; `AuthSession` (table `sessions`), `KnownDevice`, `EmailCode`, `EmailLog`, all exported from `app.models`.
- Produces test factory: `make_user(db, email="moi@example.com", *, first_name="Jean", last_name="Dupont", password="motdepasse-solide", verified=True, role="user", is_premium=False) -> User`.

- [ ] **Step 1: Write the failing test** — `backend/tests/test_models_auth.py`

```python
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import AuthSession, EmailCode, EmailLog, Favorite, KnownDevice, User
from tests.factories import make_security, make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_user_has_uuid_and_defaults(db):
    user = make_user(db, "jean@example.com")
    assert isinstance(user.id, uuid.UUID)
    assert user.role == "user" and user.is_premium is False and user.failed_logins == 0
    assert user.email_verified_at is not None


def test_deleting_user_cascades(db):
    user = make_user(db, "jean@example.com")
    security = make_security(db, "MC.PA")
    db.add_all([
        Favorite(user_id=user.id, security_id=security.id),
        AuthSession(user_id=user.id, token_hash="a" * 64, csrf_token="c", device="Chrome sur Windows",
                    persistent=True, last_seen_at=NOW, expires_at=NOW + timedelta(days=30)),
        KnownDevice(user_id=user.id, token_hash="b" * 64),
        EmailCode(user_id=user.id, purpose="verify_email", code_hash="d" * 64, expires_at=NOW),
    ])
    log = EmailLog(user_id=user.id, kind="welcome", recipient=user.email, subject="s", html="h", text="t")
    db.add(log)
    db.flush()
    db.delete(user)
    db.flush()
    for model in (Favorite, AuthSession, KnownDevice, EmailCode):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    db.refresh(log)
    assert log.user_id is None  # l'historique d'envoi survit, sans lien vers le compte
```

- [ ] **Step 2: Run and see it fail**: `pytest -q tests/test_models_auth.py` → ImportError on `AuthSession`.

- [ ] **Step 3: Rewrite `backend/app/models/user.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Adresse provisoire de l'ancien utilisateur unique « Moi », reprise par ADMIN_EMAIL au démarrage.
LEGACY_EMAIL = "moi@pea-radar.invalid"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # toujours en minuscules
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(10), default="user", server_default="user")  # user | admin
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_version: Mapped[str | None] = mapped_column(String(20))
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inactivity_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 4: Create `backend/app/models/auth.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuthSession(Base):
    """Un appareil connecté. Le jeton du cookie n'est jamais stocké, seulement son empreinte."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    device: Mapped[str] = mapped_column(String(100))
    ip: Mapped[str | None] = mapped_column(String(50))
    persistent: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class KnownDevice(Base):
    """Navigateur déjà vu pour ce compte (cookie pea_device) : sert à l'alerte « nouvel appareil »."""

    __tablename__ = "known_devices"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailCode(Base):
    """Code à 6 chiffres ou jeton de lien envoyé par mail (empreinte uniquement)."""

    __tablename__ = "email_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # verify_email | reset_password | not_me | change_email
    code_hash: Mapped[str] = mapped_column(String(64), index=True)
    new_email: Mapped[str | None] = mapped_column(String(254))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Create `backend/app/models/email.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmailLog(Base):
    """File d'envoi et historique des mails : l'API écrit, le worker envoie."""

    __tablename__ = "email_log"
    __table_args__ = (Index("ix_email_log_pending", "status", "next_attempt_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    recipient: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    html: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")  # pending | sent | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(300))
    dedupe_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 6: Convert the child foreign keys.** In `favorite.py`, `portfolio.py` (`Order.user_id`, `UserSettings.user_id`) and `assistant.py` (`Conversation.user_id`), change each to `Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), ...)` keeping the existing extra arguments (`primary_key=True`, `index=True`), and add `import uuid` + `Uuid` to the sqlalchemy import. Export the new models in `app/models/__init__.py` (`AuthSession`, `EmailCode`, `EmailLog`, `KnownDevice`, added to `__all__` in alphabetical order). In the repositories and `services/assistant/streaming.py`, change `user_id: int` hints to `user_id: uuid.UUID`.

- [ ] **Step 7: Keep the default user working until Task 7.** In `backend/app/core/current_user.py`, `ensure_default_user` now creates `User(email=LEGACY_EMAIL, first_name="Moi", last_name="", role="admin", is_premium=True, email_verified_at=datetime.now(UTC))`; keep its lookup `order_by(User.created_at)`. (Removed in Task 7.)

- [ ] **Step 8: Add the factory** — append to `backend/tests/factories.py`:

```python
from app.core.security import hash_password
from app.models import User

_HASHES: dict[str, str] = {}  # Argon2 est volontairement lent : un hachage par mot de passe pour toute la session


def make_user(
    db: Session, email: str = "moi@example.com", *, first_name: str = "Jean", last_name: str = "Dupont",
    password: str | None = "motdepasse-solide", verified: bool = True, role: str = "user", is_premium: bool = False,
) -> User:
    if password is not None and password not in _HASHES:
        _HASHES[password] = hash_password(password)
    user = User(
        email=email, first_name=first_name, last_name=last_name,
        password_hash=_HASHES[password] if password is not None else None,
        email_verified_at=datetime(2026, 9, 1, tzinfo=UTC) if verified else None, role=role, is_premium=is_premium,
    )
    db.add(user)
    db.flush()
    return user
```

Fix the two existing tests: in `tests/test_models.py` assert `first.first_name == "Moi"` instead of `first.name`; in `tests/test_api_conversations.py` replace `User(name="Autre")` + add/flush by `other = make_user(db, "autre@example.com")` (import `make_user`).

- [ ] **Step 9: Run the whole backend suite**: `pytest -q` → all PASS (≈ 320 tests).

- [ ] **Step 10: Commit**: `git commit -am "feat: UUID users with sessions, e-mail codes and e-mail outbox models"` (add the new files first with `git add backend/app/models backend/tests`).

### Task 3: One-way migration with the "Moi" takeover

**Files:**
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/a7c3e9f1b2d4_user_accounts.py`
- Test: `backend/tests/test_migration_accounts.py`

**Interfaces:**
- Consumes: models of Task 2 (the migration must produce exactly that schema).
- Produces: Alembic head `a7c3e9f1b2d4`; `config.attributes["database_url"]` override in `env.py` (used by the test).

- [ ] **Step 1: Let tests point Alembic at another database.** In `backend/alembic/env.py` replace the `set_main_option` line with:

```python
# Un test peut viser une base jetable via config.attributes["database_url"].
config.set_main_option("sqlalchemy.url", config.attributes.get("database_url") or get_settings().database_url)
```

- [ ] **Step 2: Write the failing test** — `backend/tests/test_migration_accounts.py`

```python
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

PREVIOUS = "75e519660560"
NAME = "pea_radar_migration_test"


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


def test_moi_keeps_data_and_becomes_legacy_admin(migration_url):
    cfg = _config(migration_url)
    command.upgrade(cfg, PREVIOUS)
    engine = create_engine(migration_url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, name) VALUES (1, 'Moi')"))
        conn.execute(text("INSERT INTO user_settings (user_id, min_orders_per_year, penalty_fee, fee_grid) "
                          "VALUES (1, 10, 50.0, '[]'::jsonb)"))
        conn.execute(text("INSERT INTO conversations (user_id, title, input_tokens, output_tokens, cost_usd) "
                          "VALUES (1, 'Ma question', 0, 0, 0)"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        user = conn.execute(text("SELECT id, email, first_name, role, is_premium, email_verified_at FROM users")).one()
        assert user.email == "moi@pea-radar.invalid" and user.first_name == "Moi"
        assert user.role == "admin" and user.is_premium and user.email_verified_at is not None
        assert conn.execute(text("SELECT user_id FROM user_settings")).scalar_one() == user.id
        assert conn.execute(text("SELECT user_id FROM conversations")).scalar_one() == user.id
    columns = {c["name"]: c for c in inspect(engine).get_columns("users")}
    assert str(columns["id"]["type"]) == "UUID" and "name" not in columns
    assert {"sessions", "known_devices", "email_codes", "email_log"} <= set(inspect(engine).get_table_names())
    engine.dispose()
```

- [ ] **Step 3: Run and see it fail**: `pytest -q tests/test_migration_accounts.py` → fails (no `email` column).

- [ ] **Step 4: Write the migration** — `backend/alembic/versions/a7c3e9f1b2d4_user_accounts.py`

```python
"""user accounts: UUID users, sessions, e-mail codes, e-mail outbox

Revision ID: a7c3e9f1b2d4
Revises: 75e519660560
Create Date: 2026-09-28

Migration à sens unique : les identifiants entiers des utilisateurs deviennent des UUID.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7c3e9f1b2d4"
down_revision: Union[str, Sequence[str], None] = "75e519660560"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHILDREN = ("orders", "favorites", "conversations", "user_settings")
LEGACY_EMAIL = "moi@pea-radar.invalid"


def upgrade() -> None:
    # 1. Un UUID pour chaque utilisateur, recopié dans les tables qui pointent vers lui.
    op.execute("ALTER TABLE users ADD COLUMN uuid uuid NOT NULL DEFAULT gen_random_uuid()")
    for table in CHILDREN:
        op.execute(f"ALTER TABLE {table} ADD COLUMN user_uuid uuid")
        op.execute(f"UPDATE {table} t SET user_uuid = u.uuid FROM users u WHERE u.id = t.user_id")
        # Supprimer la colonne emporte sa clé étrangère, ses index et la clé primaire qui l'utilise.
        op.execute(f"ALTER TABLE {table} DROP COLUMN user_id")
        op.execute(f"ALTER TABLE {table} RENAME COLUMN user_uuid TO user_id")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL")

    # 2. Identité : prénom, nom, adresse. Le premier utilisateur est « Moi », repris par ADMIN_EMAIL.
    op.add_column("users", sa.Column("email", sa.String(254), nullable=True))
    op.add_column("users", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(100), nullable=True))
    op.execute(
        "UPDATE users SET first_name = name, last_name = '', email = CASE "
        f"WHEN id = (SELECT min(id) FROM users) THEN '{LEGACY_EMAIL}' "
        "ELSE 'utilisateur-' || id || '@pea-radar.invalid' END"
    )
    op.execute("ALTER TABLE users DROP COLUMN id")
    op.execute("ALTER TABLE users DROP COLUMN name")
    op.execute("ALTER TABLE users RENAME COLUMN uuid TO id")
    op.execute("ALTER TABLE users ALTER COLUMN id DROP DEFAULT")
    op.create_primary_key("users_pkey", "users", ["id"])
    for column in ("email", "first_name", "last_name"):
        op.alter_column("users", column, nullable=False)
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.create_unique_constraint("users_google_sub_key", "users", ["google_sub"])
    op.add_column("users", sa.Column("role", sa.String(10), nullable=False, server_default="user"))
    op.add_column("users", sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.false()))
    for column in ("email_verified_at", "terms_accepted_at", "locked_until", "inactivity_warned_at",
                   "last_login_at", "last_seen_at"):
        op.add_column("users", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("terms_version", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"))
    op.execute(f"UPDATE users SET role = 'admin', is_premium = true, email_verified_at = now() WHERE email = '{LEGACY_EMAIL}'")

    # 3. Clés des tables enfants, recréées sur les UUID.
    for table in CHILDREN:
        op.create_foreign_key(f"{table}_user_id_fkey", table, "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_primary_key("favorites_pkey", "favorites", ["user_id", "security_id"])
    op.create_primary_key("user_settings_pkey", "user_settings", ["user_id"])
    op.create_index("ix_orders_user_date", "orders", ["user_id", "trade_date"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # 4. Nouvelles tables.
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("device", sa.String(100), nullable=False),
        sa.Column("ip", sa.String(50), nullable=True),
        sa.Column("persistent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_table(
        "known_devices",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "email_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("new_email", sa.String(254), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_codes_user_id", "email_codes", ["user_id"])
    op.create_index("ix_email_codes_code_hash", "email_codes", ["code_hash"])
    op.create_table(
        "email_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column("dedupe_key", sa.String(120), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_log_user_id", "email_log", ["user_id"])
    op.create_index("ix_email_log_pending", "email_log", ["status", "next_attempt_at"])


def downgrade() -> None:
    raise NotImplementedError("Migration à sens unique : restaurer une sauvegarde de la base pour revenir en arrière.")
```

- [ ] **Step 5: Run and see it pass**: `pytest -q tests/test_migration_accounts.py` → PASS.

- [ ] **Step 6: Check the model and the migration agree.** With the dev stack up (`... up -d db api`), run `docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -T api alembic check`. Expected: `No new upgrade operations detected.` If it lists differences (a name or a nullable), fix the **migration** to match the models, drop and recreate the migration test DB by re-running Step 5, then re-run `alembic check`. **Back up first**: `docker compose exec -T db pg_dump -U pea pea_radar > backup-avant-comptes.sql` (the file is ignored by git: add `*.sql` under a `backups/` folder or delete it after checking; never commit it).

- [ ] **Step 7: Run the whole suite**: `pytest -q` → PASS.

- [ ] **Step 8: Commit**: `git add backend/alembic && git add backend/tests/test_migration_accounts.py && git commit -m "feat: one-way migration to UUID users with account tables"`

> **Fin du Bloc 1 — stop.** Status for the user: data model and migration done; next is Bloc 2 (mails).

---

# Bloc 2 — Mails

### Task 4: Mail templates (pure rendering)

**Files:**
- Create: `backend/app/services/mail/__init__.py` (empty), `backend/app/services/mail/render.py`, `backend/app/services/mail/templates/_layout.html`, `_footer.txt`, and for each kind `verify_code`, `welcome`, `reset_password`, `security_alert`, `new_device`: `<kind>.html` + `<kind>.txt`
- Test: `backend/tests/test_mail_render.py`

**Interfaces:**
- Produces: `RenderedEmail(subject: str, html: str, text: str)` (frozen dataclass); `render(kind: str, context: dict, *, base_url: str) -> RenderedEmail`; `KINDS: frozenset[str]`; `SECURITY_EVENTS: dict[str, str]` with keys `password_reset`, `signup_attempt`.
- Context per kind (all include `first_name`):
  - `verify_code`: `code`
  - `welcome`: —
  - `reset_password`: `token`, `valid_minutes`
  - `security_alert`: `event` (key of `SECURITY_EVENTS`)
  - `new_device`: `device`, `when` (aware `datetime`), `token`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_mail_render.py`

```python
from datetime import UTC, datetime

import pytest

from app.services.mail.render import KINDS, render

BASE = "https://pea-radar.example"
CONTEXTS = {
    "verify_code": {"first_name": "Jean", "code": "042917"},
    "welcome": {"first_name": "Jean"},
    "reset_password": {"first_name": "Jean", "token": "abc_123", "valid_minutes": 30},
    "security_alert": {"first_name": "Jean", "event": "password_reset"},
    "new_device": {"first_name": "Jean", "device": "Chrome sur Windows", "when": datetime(2026, 9, 28, 12, 5, tzinfo=UTC), "token": "tok"},
}


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_every_kind_renders_html_and_text(kind):
    mail = render(kind, CONTEXTS[kind], base_url=BASE)
    assert mail.subject and "Jean" in mail.text and "Jean" in mail.html
    assert "<" not in mail.text.replace("<https", "")  # texte brut, sans balise
    assert "pas un conseil" not in mail.text  # l'avertissement est réservé aux notifications (étape 5)


def test_code_is_in_subject_and_body():
    mail = render("verify_code", CONTEXTS["verify_code"], base_url=BASE)
    assert "042917" in mail.subject and "042917" in mail.html and "15 minutes" in mail.text


def test_links_use_public_base_url():
    assert f"{BASE}/reinitialiser?jeton=abc_123" in render("reset_password", CONTEXTS["reset_password"], base_url=BASE).text
    new_device = render("new_device", CONTEXTS["new_device"], base_url=BASE)
    assert f"{BASE}/ce-n-etait-pas-moi?jeton=tok" in new_device.html
    assert "28/09/2026 à 14:05" in new_device.text  # heure de Paris


def test_html_escapes_user_input():
    mail = render("welcome", {"first_name": "<script>alert(1)</script>"}, base_url=BASE)
    assert "<script>" not in mail.html and "&lt;script&gt;" in mail.html


def test_unknown_security_event_fails():
    with pytest.raises(KeyError):
        render("security_alert", {"first_name": "Jean", "event": "inconnu"}, base_url=BASE)
```

- [ ] **Step 2: Run and see it fail** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `render.py`**

```python
"""Rendu des mails (HTML + texte brut) à partir des modèles Jinja2. Fonctions pures."""
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

PARIS = ZoneInfo("Europe/Paris")

SUBJECTS = {
    "verify_code": "Votre code PEA Radar : {code}",
    "welcome": "Bienvenue sur PEA Radar",
    "reset_password": "Choisir un nouveau mot de passe PEA Radar",
    "security_alert": "Alerte de sécurité sur votre compte PEA Radar",
    "new_device": "Nouvelle connexion à votre compte PEA Radar",
}
KINDS = frozenset(SUBJECTS)

# Phrases des alertes de sécurité (C4) ; les étapes suivantes en ajoutent.
SECURITY_EVENTS = {
    "password_reset": "Le mot de passe de votre compte vient d'être réinitialisé.",
    "signup_attempt": ("Quelqu'un vient d'essayer de créer un compte PEA Radar avec votre adresse. Vous avez déjà un "
                       "compte : si c'était vous, connectez-vous ou choisissez un nouveau mot de passe."),
}


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


def _paris(value: datetime) -> str:
    return value.astimezone(PARIS).strftime("%d/%m/%Y à %H:%M")


_env = Environment(
    loader=PackageLoader("app.services.mail", "templates"),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["paris"] = _paris


def render(kind: str, context: dict, *, base_url: str) -> RenderedEmail:
    values = {**context, "base_url": base_url.rstrip("/")}
    if kind == "security_alert":
        values["event_text"] = SECURITY_EVENTS[context["event"]]
    return RenderedEmail(
        subject=SUBJECTS[kind].format(**values),
        html=_env.get_template(f"{kind}.html").render(values),
        text=_env.get_template(f"{kind}.txt").render(values),
    )
```

- [ ] **Step 4: Write the templates.** Shared layout, inline styles (mail clients ignore `<style>`), indigo `#4f46e5` (≈ the app's `primary`):

`templates/_layout.html`:
```html
<!doctype html>
<html lang="fr">
<body style="margin:0;padding:24px;background:#f5f6fa;font-family:Inter,Segoe UI,Arial,sans-serif;color:#1f2937">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden">
    <tr><td style="background:#4f46e5;padding:20px 28px;color:#ffffff;font-size:18px;font-weight:600">PEA Radar</td></tr>
    <tr><td style="padding:28px;font-size:15px;line-height:1.6">
      <p style="margin-top:0">Bonjour {{ first_name }},</p>
      {% block body %}{% endblock %}
    </td></tr>
    <tr><td style="padding:16px 28px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280">
      Vous recevez ce mail car un compte PEA Radar utilise cette adresse. <a href="{{ base_url }}" style="color:#4f46e5">{{ base_url }}</a>
    </td></tr>
  </table>
</body>
</html>
```
A reusable button inside bodies: `<a href="…" style="display:inline-block;background:#4f46e5;color:#ffffff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600">…</a>`.

`templates/_footer.txt`:
```
--
PEA Radar — {{ base_url }}
Vous recevez ce mail car un compte PEA Radar utilise cette adresse.
```

`verify_code.html`:
```html
{% extends "_layout.html" %}
{% block body %}
<p>Voici votre code pour valider votre adresse :</p>
<p style="font-size:32px;font-weight:700;letter-spacing:8px;color:#4f46e5">{{ code }}</p>
<p>Il est valable 15 minutes. Si vous n'avez pas demandé de compte PEA Radar, ignorez ce mail.</p>
{% endblock %}
```
`verify_code.txt`:
```
Bonjour {{ first_name }},

Voici votre code pour valider votre adresse : {{ code }}

Il est valable 15 minutes. Si vous n'avez pas demandé de compte PEA Radar, ignorez ce mail.

{% include "_footer.txt" %}
```
`welcome.html` / `.txt`: "Votre compte est prêt." + three first steps (explorer the top 10, add favourites with the star, record orders in Portefeuille) + button/link `{{ base_url }}/guide/` "Lire le guide".
`reset_password.html` / `.txt`: "Pour choisir un nouveau mot de passe, ouvrez ce lien (valable {{ valid_minutes }} minutes, une seule fois) :" + button/link `{{ base_url }}/reinitialiser?jeton={{ token }}` + "Si vous n'êtes pas à l'origine de cette demande, ignorez ce mail : votre mot de passe actuel reste valable."
`security_alert.html` / `.txt`: `{{ event_text }}` + "Si ce n'était pas vous, choisissez tout de suite un nouveau mot de passe :" + link `{{ base_url }}/mot-de-passe-oublie`.
`new_device.html` / `.txt`: "Une connexion à votre compte a eu lieu depuis un nouvel appareil : {{ device }}, le {{ when | paris }} (heure de Paris)." + "Si c'était vous, il n'y a rien à faire." + button/link "Ce n'était pas moi" → `{{ base_url }}/ce-n-etait-pas-moi?jeton={{ token }}` + "Ce bouton déconnecte tous vos appareils et vous demande un nouveau mot de passe."
Every `.txt` starts with `Bonjour {{ first_name }},` and ends with `{% include "_footer.txt" %}`; links are written bare (no angle brackets).

- [ ] **Step 5: Run and see it pass**: `pytest -q tests/test_mail_render.py`.

- [ ] **Step 6: Commit**: `git add backend/app/services/mail backend/tests/test_mail_render.py && git commit -m "feat: account e-mail templates (code, welcome, reset, security alert, new device)"`

### Task 5: Outbox, SMTP sender, worker job and Mailpit

**Files:**
- Create: `backend/app/services/mail/outbox.py`, `backend/app/services/mail/smtp.py`, `backend/app/jobs/mail.py`, `backend/tests/fake_mailer.py`
- Modify: `backend/app/jobs/context.py`, `backend/app/jobs/worker.py`, `backend/app/jobs/scheduler.py`, `backend/tests/conftest.py` (`make_ctx` gets `mailer=None`), `docker-compose.yml`, `.env.example`
- Test: `backend/tests/test_mail_outbox.py`, `backend/tests/test_scheduler.py` (one new test)

**Interfaces:**
- Consumes: `render`, `EmailLog`, `JobContext`.
- Produces:
  - `enqueue(db: Session, kind: str, *, to: str, context: dict, user_id: uuid.UUID | None = None, dedupe_key: str | None = None) -> int | None` — returns the new `email_log.id`, or `None` if `dedupe_key` already exists; **does not commit**.
  - `Mailer` protocol: `send(*, to: str, subject: str, html: str, text: str, headers: dict[str, str]) -> None`; `SmtpMailer`; `mailer_from_settings(settings) -> Mailer | None`.
  - `send_pending_emails(ctx: JobContext) -> int` (number sent); `RETRY_DELAYS`.
  - `JobContext.mailer: Mailer | None = None`.
  - `tests.fake_mailer.FakeMailer` with `.sent: list[dict]` and `.fail_next: int`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_mail_outbox.py`

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.jobs.mail import send_pending_emails
from app.models import EmailLog
from app.services.mail.outbox import enqueue
from tests.factories import make_user
from tests.fake_mailer import FakeMailer

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _enqueue(db, **kw):
    return enqueue(db, "welcome", to="jean@example.com", context={"first_name": "Jean"}, **kw)


def test_enqueue_renders_and_waits(db):
    user = make_user(db, "jean@example.com")
    log_id = _enqueue(db, user_id=user.id)
    row = db.get(EmailLog, log_id)
    assert row.status == "pending" and row.subject == "Bienvenue sur PEA Radar" and "Jean" in row.text


def test_dedupe_key_prevents_duplicates(db):
    assert _enqueue(db, dedupe_key="welcome:1") is not None
    assert _enqueue(db, dedupe_key="welcome:1") is None
    assert len(db.scalars(select(EmailLog)).all()) == 1


def test_worker_sends_pending(db, make_ctx):
    _enqueue(db)
    mailer = FakeMailer()
    db.execute(EmailLog.__table__.update().values(next_attempt_at=NOW - timedelta(seconds=1)))
    assert send_pending_emails(make_ctx(mailer=mailer, now=NOW)) == 1
    assert mailer.sent[0]["to"] == "jean@example.com"
    row = db.scalars(select(EmailLog)).one()
    assert row.status == "sent" and row.sent_at == NOW and row.attempts == 1
    assert send_pending_emails(make_ctx(mailer=mailer, now=NOW)) == 0  # jamais envoyé deux fois


def test_worker_retries_then_gives_up(db, make_ctx):
    _enqueue(db)
    db.execute(EmailLog.__table__.update().values(next_attempt_at=NOW))
    mailer = FakeMailer()
    mailer.fail_next = 10
    now = NOW
    for expected_delay in (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30)):
        send_pending_emails(make_ctx(mailer=mailer, now=now))
        row = db.scalars(select(EmailLog)).one()
        assert row.status == "pending" and row.next_attempt_at == now + expected_delay and "SMTP" in row.error
        assert send_pending_emails(make_ctx(mailer=mailer, now=now)) == 0  # pas avant le délai
        now = row.next_attempt_at
    send_pending_emails(make_ctx(mailer=mailer, now=now))
    assert db.scalars(select(EmailLog)).one().status == "failed"
```

Note: `db.execute(...update())` is used because `next_attempt_at` defaults to the DB clock; tests pin it.

Append to `backend/tests/test_scheduler.py`:
```python
def test_scheduler_sends_emails_only_with_a_mailer(make_ctx):
    from tests.fake_mailer import FakeMailer

    scheduler = build_scheduler(make_ctx(mailer=FakeMailer()), BackgroundScheduler(timezone="Europe/Paris"))
    job = scheduler.get_job("emails")
    assert job is not None and job.trigger.interval.total_seconds() == 5
```
(The existing `test_build_scheduler_registers_jobs` keeps its exact set: without a mailer there is no `emails` job.)

- [ ] **Step 2: Run and see them fail.**

- [ ] **Step 3: Implement**

`backend/tests/fake_mailer.py`:
```python
class FakeMailer:
    """Remplace le serveur SMTP : garde les mails envoyés, peut simuler des pannes."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.fail_next = 0

    def send(self, **mail) -> None:
        if self.fail_next:
            self.fail_next -= 1
            raise OSError("SMTP indisponible")
        self.sent.append(mail)
```

`backend/app/services/mail/outbox.py`:
```python
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmailLog
from app.services.mail.render import render


def enqueue(
    db: Session, kind: str, *, to: str, context: dict, user_id: uuid.UUID | None = None, dedupe_key: str | None = None,
) -> int | None:
    """Met un mail en file d'attente dans la même transaction que l'action qui le déclenche (pas de commit ici).

    Le worker l'enverra dans les secondes qui suivent. Renvoie None si `dedupe_key` a déjà été utilisée.
    """
    mail = render(kind, context, base_url=get_settings().public_base_url)
    stmt = (
        pg_insert(EmailLog)
        .values(user_id=user_id, kind=kind, recipient=to, subject=mail.subject, html=mail.html, text=mail.text,
                headers={}, dedupe_key=dedupe_key)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(EmailLog.id)
    )
    return db.execute(stmt).scalar_one_or_none()
```

`backend/app/services/mail/smtp.py`:
```python
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Protocol

from app.core.config import Settings


class Mailer(Protocol):
    def send(self, *, to: str, subject: str, html: str, text: str, headers: dict[str, str]) -> None: ...


class SmtpMailer:
    def __init__(self, host: str, port: int, user: str, password: str, tls: str, sender: str) -> None:
        self.host, self.port, self.user, self.password, self.tls, self.sender = host, port, user, password, tls, sender

    def send(self, *, to: str, subject: str, html: str, text: str, headers: dict[str, str]) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain=self.sender.rsplit("@", 1)[-1].rstrip(">"))
        for name, value in headers.items():
            message[name] = value
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        smtp_class = smtplib.SMTP_SSL if self.tls == "ssl" else smtplib.SMTP
        with smtp_class(self.host, self.port, timeout=20) as smtp:
            if self.tls == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(message)


def mailer_from_settings(settings: Settings) -> Mailer | None:
    if not settings.smtp_host:
        return None
    return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.smtp_password,
                      settings.smtp_tls, settings.mail_from)
```

`backend/app/jobs/context.py`: add `from app.services.mail.smtp import Mailer` and the last field `mailer: Mailer | None = None` (after `now`).

`backend/app/jobs/mail.py`:
```python
import logging
from datetime import timedelta

from sqlalchemy import select

from app.jobs.context import JobContext
from app.models import EmailLog

logger = logging.getLogger(__name__)
RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30))
BATCH_SIZE = 50


def send_pending_emails(ctx: JobContext) -> int:
    """Envoie les mails en attente dont l'heure est venue ; en cas d'échec, réessaie à 1, 5 puis 30 min."""
    if ctx.mailer is None:
        return 0
    now = ctx.now()
    sent = 0
    with ctx.session_factory() as session:
        rows = session.scalars(
            select(EmailLog)
            .where(EmailLog.status == "pending", EmailLog.next_attempt_at <= now)
            .order_by(EmailLog.id).limit(BATCH_SIZE).with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.attempts += 1
            try:
                ctx.mailer.send(to=row.recipient, subject=row.subject, html=row.html, text=row.text, headers=row.headers or {})
            except Exception as exc:  # serveur absent, refus, délai dépassé…
                row.error = str(exc)[:300]
                if row.attempts > len(RETRY_DELAYS):
                    row.status = "failed"
                    logger.error("Mail %s abandonné après %d essais : %s", row.id, row.attempts, row.error)
                else:
                    row.next_attempt_at = now + RETRY_DELAYS[row.attempts - 1]
                    logger.warning("Échec d'envoi du mail %s (essai %d) : %s", row.id, row.attempts, row.error)
            else:
                row.status, row.sent_at, row.error = "sent", now, None
                sent += 1
        session.commit()
    return sent
```

`backend/app/jobs/scheduler.py`: import `send_pending_emails`; add
```python
def mail_job(ctx: JobContext) -> None:
    # Toutes les 5 s : pas de trace dans data_status (run_job) pour ne pas noyer le suivi des données.
    try:
        send_pending_emails(ctx)
    except Exception:
        logging.getLogger(__name__).exception("Échec de la file d'envoi des mails")
```
and at the end of `build_scheduler`, before `return`:
```python
    if ctx.mailer is not None:
        scheduler.add_job(mail_job, IntervalTrigger(seconds=5, timezone=tz), args=[ctx], id="emails", **common)
    else:
        logging.getLogger(__name__).warning("SMTP_HOST vide : les mails restent en file d'attente.")
```
(add `import logging` at the top).

`backend/app/jobs/worker.py`: `mailer=mailer_from_settings(settings)` in `build_context` (import from `app.services.mail.smtp`).

`backend/tests/conftest.py` `make_ctx`: add parameter `mailer=None` and pass `mailer=mailer` to `JobContext`.

- [ ] **Step 4: Run and see them pass**: `pytest -q tests/test_mail_outbox.py tests/test_scheduler.py`.

- [ ] **Step 5: Mailpit.** In `docker-compose.yml` add (the user runs the app locally with this file, so Mailpit lives here, not only in the dev override; update spec §5.2 accordingly in the same commit):

```yaml
  # Attrape tous les mails en local : http://localhost:8025. À la mise en ligne, SMTP_* vise Brevo.
  mailpit:
    image: axllent/mailpit:latest
    ports:
      - "8025:8025"
    restart: unless-stopped
```
In `.env.example` add (with French comments):
```
# Compte administrateur : reprend les données existantes, reçoit un lien pour choisir son mot de passe
ADMIN_EMAIL=
# false seulement en local sans HTTPS
COOKIE_SECURE=false

# Envoi des mails. En local : Mailpit (http://localhost:8025). En ligne : les identifiants SMTP de Brevo.
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_TLS=none
MAIL_FROM=PEA Radar <no-reply@pea-radar.local>
```
Tell the user (in the block status) to copy these lines into their own `.env`, with their address in `ADMIN_EMAIL`.

- [ ] **Step 6: Manual check**: `docker compose up -d mailpit worker` then in the api container `python -c "from app.core.db import get_session_factory; from app.services.mail.outbox import enqueue; s=get_session_factory()(); enqueue(s,'welcome',to='test@example.com',context={'first_name':'Test'}); s.commit()"`; within ~5 s the mail shows at http://localhost:8025. Delete it in Mailpit.

- [ ] **Step 7: Full suite + commit**: `pytest -q` → PASS; `git add -A backend docker-compose.yml .env.example docs/superpowers/specs && git commit -m "feat: e-mail outbox sent by the worker over SMTP, Mailpit locally"`

> **Fin du Bloc 2 — stop.** Status: templates, outbox and Mailpit ready; next is Bloc 3 (authentication API). Remind the user to add the new `.env` lines.

---

# Bloc 3 — Authentification (API)

### Task 6: Sessions, cookies, CSRF and the current-user dependencies

**Files:**
- Create: `backend/app/services/auth/__init__.py` (empty), `backend/app/services/auth/sessions.py`, `backend/app/api/cookies.py`, `backend/app/schemas/auth.py`, `backend/app/api/routes/me.py`, `backend/tests/auth_helpers.py`
- Modify: `backend/app/core/current_user.py`, `backend/app/main.py`
- Test: `backend/tests/test_auth_sessions.py`

**Interfaces:**
- Produces in `app.services.auth.sessions`: constants `SESSION_COOKIE = "pea_session"`, `CSRF_COOKIE = "pea_csrf"`, `DEVICE_COOKIE = "pea_device"`, `TOUCH_EVERY = timedelta(minutes=1)`; `NewSession(token: str, csrf_token: str, session: AuthSession)`; `open_session(db, user, *, persistent: bool, ip: str | None, user_agent: str | None, now: datetime, settings: Settings) -> NewSession`; `resolve_session(db, token: str | None, *, now, settings) -> AuthSession | None`; `revoke_session(db, session_id: uuid.UUID) -> None`; `revoke_user_sessions(db, user_id: uuid.UUID) -> None`.
- Produces in `app.api.cookies`: `set_auth_cookies(response, new: NewSession, settings)`, `clear_auth_cookies(response, settings)`, `set_device_cookie(response, token: str, settings)`.
- Produces in `app.core.current_user`: `get_now() -> datetime` (dependency, overridable), `get_auth_session(...) -> AuthSession | None` (enforces CSRF on unsafe methods), `get_optional_user(...) -> User | None`, `get_current_user(...) -> User` (401), `require_admin(...) -> User` (403). `ensure_default_user` is **removed in Task 7**, keep it for now.
- Produces `app.schemas.auth.MeOut(id: uuid.UUID, email: str, first_name: str, last_name: str, role: str, is_premium: bool)` (`from_attributes=True`), `MessageOut(message: str)`.
- Route: `GET /api/me` → `MeOut` or 401.
- Test helper `tests.auth_helpers.sign_in(client, db, user, *, persistent=True) -> NewSession` (sets the cookie and the `X-CSRF-Token` header on the client).

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_auth_sessions.py`

```python
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.current_user import get_now
from app.models import AuthSession
from app.services.auth.sessions import SESSION_COOKIE, open_session, resolve_session, revoke_user_sessions
from app.core.security import token_hash
from tests.auth_helpers import sign_in
from tests.factories import make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
SETTINGS = Settings(session_days=30, session_short_hours=12)


def test_open_session_stores_only_a_hash(db):
    user = make_user(db)
    new = open_session(db, user, persistent=True, ip="203.0.113.9", user_agent=None, now=NOW, settings=SETTINGS)
    assert new.session.token_hash == token_hash(new.token) and new.token not in new.session.token_hash
    assert new.session.ip == "203.0.113.0/24" and new.session.expires_at == NOW + timedelta(days=30)
    assert user.last_login_at == NOW


def test_short_session_and_sliding_expiry(db):
    user = make_user(db)
    new = open_session(db, user, persistent=False, ip=None, user_agent=None, now=NOW, settings=SETTINGS)
    assert new.session.expires_at == NOW + timedelta(hours=12)
    later = NOW + timedelta(hours=11)
    assert resolve_session(db, new.token, now=later, settings=SETTINGS) is not None
    assert new.session.expires_at == later + timedelta(hours=12)  # prolongée à chaque activité
    assert resolve_session(db, new.token, now=later + timedelta(hours=13), settings=SETTINGS) is None


def test_resolve_rejects_unknown_and_revoked(db):
    user = make_user(db)
    new = open_session(db, user, persistent=True, ip=None, user_agent=None, now=NOW, settings=SETTINGS)
    assert resolve_session(db, "inconnu", now=NOW, settings=SETTINGS) is None
    assert resolve_session(db, None, now=NOW, settings=SETTINGS) is None
    revoke_user_sessions(db, user.id)
    assert resolve_session(db, new.token, now=NOW, settings=SETTINGS) is None


def test_me_requires_a_session(anon_client):
    response = anon_client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "not_authenticated"


def test_me_returns_the_signed_in_user(anon_client, db):
    user = make_user(db, "jean@example.com", first_name="Jean")
    sign_in(anon_client, db, user)
    body = anon_client.get("/api/me").json()
    assert body == {"id": str(user.id), "email": "jean@example.com", "first_name": "Jean", "last_name": "Dupont",
                    "role": "user", "is_premium": False}
    assert "password_hash" not in body


def test_expired_session_is_401(anon_client, db):
    user = make_user(db)
    sign_in(anon_client, db, user, persistent=False)
    anon_client.app.dependency_overrides[get_now] = lambda: datetime.now(UTC) + timedelta(days=2)
    assert anon_client.get("/api/me").status_code == 401
```

`anon_client` is created in Task 7's conftest change; to have it now, do Step 2 of Task 7's conftest refactor **here** (the fixture code is below in Step 4).

- [ ] **Step 2: Run and see them fail.**

- [ ] **Step 3: Implement `services/auth/sessions.py`**

```python
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import device_label, new_token, token_hash, truncate_ip
from app.models import AuthSession, User

SESSION_COOKIE = "pea_session"
CSRF_COOKIE = "pea_csrf"
DEVICE_COOKIE = "pea_device"
TOUCH_EVERY = timedelta(minutes=1)


@dataclass(frozen=True)
class NewSession:
    token: str
    csrf_token: str
    session: AuthSession


def lifetime(persistent: bool, settings: Settings) -> timedelta:
    return timedelta(days=settings.session_days) if persistent else timedelta(hours=settings.session_short_hours)


def open_session(db: Session, user: User, *, persistent: bool, ip: str | None, user_agent: str | None,
                 now: datetime, settings: Settings) -> NewSession:
    """Nouvelle session pour un compte validé. Seule l'empreinte du jeton est enregistrée."""
    token, csrf = new_token(), new_token()
    row = AuthSession(
        user_id=user.id, token_hash=token_hash(token), csrf_token=csrf, device=device_label(user_agent),
        ip=truncate_ip(ip), persistent=persistent, last_seen_at=now, expires_at=now + lifetime(persistent, settings),
    )
    db.add(row)
    user.last_login_at = now
    db.flush()
    return NewSession(token, csrf, row)


def resolve_session(db: Session, token: str | None, *, now: datetime, settings: Settings) -> AuthSession | None:
    if not token:
        return None
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    if row is None or row.expires_at <= now:
        return None
    if now - row.last_seen_at >= TOUCH_EVERY:  # au plus une écriture par minute
        row.last_seen_at = now
        row.expires_at = now + lifetime(row.persistent, settings)
        db.commit()
    return row


def revoke_session(db: Session, session_id: uuid.UUID) -> None:
    db.execute(delete(AuthSession).where(AuthSession.id == session_id))


def revoke_user_sessions(db: Session, user_id: uuid.UUID) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
```

`backend/app/api/cookies.py`:
```python
from datetime import timedelta

from fastapi import Response

from app.core.config import Settings
from app.services.auth.sessions import CSRF_COOKIE, DEVICE_COOKIE, SESSION_COOKIE, NewSession

DEVICE_MAX_AGE = int(timedelta(days=365).total_seconds())


def set_auth_cookies(response: Response, new: NewSession, settings: Settings) -> None:
    # Sans « rester connecté », cookies de session du navigateur (effacés à sa fermeture).
    max_age = int(timedelta(days=settings.session_days).total_seconds()) if new.session.persistent else None
    common = dict(max_age=max_age, secure=settings.cookie_secure, samesite="lax", path="/")
    response.set_cookie(SESSION_COOKIE, new.token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, new.csrf_token, httponly=False, **common)  # lu par le JavaScript


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name, httponly in ((SESSION_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, httponly=httponly, samesite="lax")


def set_device_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(DEVICE_COOKIE, token, max_age=DEVICE_MAX_AGE, httponly=True, secure=settings.cookie_secure,
                        samesite="lax", path="/")
```

`backend/app/core/current_user.py` — add (keep `ensure_default_user` and the old `get_current_user` body until Task 7? **No**: replace `get_current_user` now; `ensure_default_user` stays only because old tests import it until Task 7):

```python
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import same
from app.models import AuthSession, User
from app.services.auth.sessions import SESSION_COOKIE, resolve_session

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_now() -> datetime:
    """Heure courante ; remplacée dans les tests."""
    return datetime.now(UTC)


def get_auth_session(request: Request, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> AuthSession | None:
    row = resolve_session(db, request.cookies.get(SESSION_COOKIE), now=now, settings=get_settings())
    if row is not None and request.method in UNSAFE_METHODS and not same(request.headers.get("X-CSRF-Token", ""), row.csrf_token):
        raise HTTPException(403, detail={"code": "csrf", "message": "Jeton de sécurité manquant ou périmé : rechargez la page."})
    return row


def get_optional_user(auth: AuthSession | None = Depends(get_auth_session), db: Session = Depends(get_db)) -> User | None:
    """Pages publiques : l'utilisateur s'il est connecté, sinon None."""
    return db.get(User, auth.user_id) if auth is not None else None


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    """Pages privées. Une session n'existe que pour un compte validé : l'utilisateur renvoyé l'est toujours."""
    if user is None:
        raise HTTPException(401, detail={"code": "not_authenticated", "message": "Connectez-vous pour accéder à cette page."})
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, detail={"code": "forbidden", "message": "Réservé aux administrateurs."})
    return user
```

`backend/app/schemas/auth.py` (MeOut + MessageOut for now; Task 8 adds the inputs):
```python
import uuid

from pydantic import BaseModel, ConfigDict


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_premium: bool


class MessageOut(BaseModel):
    message: str
```

`backend/app/api/routes/me.py`:
```python
from fastapi import APIRouter, Depends

from app.core.current_user import get_current_user
from app.models import User
from app.schemas.auth import MeOut

router = APIRouter(tags=["account"])


@router.get("/me", response_model=MeOut)
def read_me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut.model_validate(user)
```
Register `me` in `app/main.py` (import and add to the tuple).

`backend/tests/auth_helpers.py`:
```python
from datetime import UTC, datetime

from app.core.config import get_settings
from app.services.auth.sessions import SESSION_COOKIE, NewSession, open_session


def sign_in(client, db, user, *, persistent: bool = True) -> NewSession:
    """Ouvre une session directement en base et la donne au client de test (cookie + en-tête CSRF)."""
    new = open_session(db, user, persistent=persistent, ip="203.0.113.5", user_agent="pytest",
                       now=datetime.now(UTC), settings=get_settings())
    client.cookies.set(SESSION_COOKIE, new.token)
    client.headers["X-CSRF-Token"] = new.csrf_token
    return new
```

- [ ] **Step 4: conftest — `user`, `client` (signed in) and `anon_client`.** Replace the `client` fixture of `backend/tests/conftest.py` with:

```python
def _build_app(db, fake_market, fake_llm):
    from contextlib import nullcontext

    from app.api.deps import INTRADAY_CACHE, NEWS_CACHE, get_llm_factory, get_market_provider, get_session_maker

    INTRADAY_CACHE.clear()
    NEWS_CACHE.clear()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_market_provider] = lambda: fake_market

    def llm_factory():
        def make(api_key: str):
            fake_llm.api_keys.append(api_key)
            return fake_llm
        return make

    app.dependency_overrides[get_llm_factory] = llm_factory
    app.dependency_overrides[get_session_maker] = lambda: (lambda: nullcontext(db))
    return app


@pytest.fixture
def user(db):
    from tests.factories import make_user

    return make_user(db, "moi@example.com", first_name="Moi")


@pytest.fixture
def anon_client(db, fake_market, fake_llm):
    # https : les cookies « Secure » posés par l'API sont renvoyés comme par un vrai navigateur.
    with TestClient(_build_app(db, fake_market, fake_llm), base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def client(db, fake_market, fake_llm, user):
    """Client connecté avec le compte `user` (validé, rôle utilisateur)."""
    from tests.auth_helpers import sign_in

    with TestClient(_build_app(db, fake_market, fake_llm), base_url="https://testserver") as test_client:
        sign_in(test_client, db, user)
        yield test_client
```

- [ ] **Step 5: Run**: `pytest -q tests/test_auth_sessions.py` → PASS. Then the full suite: tests that relied on `ensure_default_user` creating **the** request user now fail (the request user is `user`, not "Moi"). They are fixed in Task 7 Step 1; if you want a green commit here, do Task 7 Step 1 now and commit both together.

- [ ] **Step 6: Commit**: `git add -A backend && git commit -m "feat: cookie sessions with CSRF protection and /api/me"`

### Task 7: Public and private routes, per-user isolation

**Files:**
- Modify: `backend/app/core/current_user.py` (delete `ensure_default_user`, `DEFAULT_USER_NAME`), `backend/app/api/routes/{screener,rankings,securities,security_detail,fees,forecasts}.py`, `backend/app/repositories/screener.py`, `backend/app/repositories/user_settings.py`
- Modify tests: every file importing `ensure_default_user` (`test_api_favorites_eligibility.py`, `test_api_screener.py`, `test_api_settings.py`, `test_assistant_streaming.py`, `test_assistant_tools.py`, `test_lot2_review_fixes.py`, `test_models.py`, `test_models_lot2.py`, `test_scoring_job.py`), `test_api_conversations.py`
- Test: `backend/tests/test_api_access.py`

**Interfaces:**
- Consumes: `get_optional_user`, `get_current_user`, `require_admin`, `sign_in`, fixtures `user`, `client`, `anon_client`.
- Produces: `screener_rows(session, user_id: uuid.UUID | None, ...)` (favourite flag `False` when `None`); `user_fee_grid(session, user_id: uuid.UUID | None)` (default grid when `None`); `simulate_since(db, user_id: uuid.UUID | None, ...)`.

- [ ] **Step 1: Migrate the existing tests.** Replace every `user = ensure_default_user(db)` by the `user` fixture (add `user` to the test's parameters and delete the import). In `test_models.py` delete `test_ensure_default_user_is_idempotent`. In `test_api_conversations.py::test_other_user_conversation_is_404` delete the first line (`client.get(...)  # crée l'utilisateur par défaut`). In `test_assistant_tools.py`, the helper returning `ensure_default_user(db)` becomes `make_user(db)`. Run `grep -rn ensure_default_user backend` → nothing left except `current_user.py`, then delete the function and `DEFAULT_USER_NAME` there.

- [ ] **Step 2: Write the failing access tests** — `backend/tests/test_api_access.py`

```python
from datetime import date

import pytest

from app.models import Order
from tests.auth_helpers import sign_in
from tests.factories import make_security, make_user

PRIVATE = [
    ("GET", "/api/orders"), ("GET", "/api/orders/counter"), ("POST", "/api/orders"),
    ("GET", "/api/portfolio"), ("GET", "/api/portfolio/history"),
    ("PUT", "/api/favorites/1"), ("DELETE", "/api/favorites/1"),
    ("GET", "/api/settings"), ("PUT", "/api/settings"),
    ("GET", "/api/assistant/settings"), ("GET", "/api/assistant/conversations"),
    ("GET", "/api/forecasts"), ("GET", "/api/forecasts/signals"), ("GET", "/api/forecasts/track-record"),
    ("GET", "/api/securities/1/forecast"),
    ("PATCH", "/api/securities/1/eligibility"),
]
PUBLIC = ["/api/screener?kind=stock", "/api/rankings/top", "/api/rankings/movers", "/api/market/heatmap",
          "/api/securities", "/api/status", "/api/fees/estimate?amount=1000", "/api/health"]


@pytest.mark.parametrize(("method", "path"), PRIVATE)
def test_private_routes_need_a_session(anon_client, method, path):
    response = anon_client.request(method, path, json={})
    assert response.status_code == 401, path


@pytest.mark.parametrize("path", PUBLIC)
def test_public_routes_work_without_account(anon_client, path):
    assert anon_client.get(path).status_code == 200, path


def test_anonymous_security_page_has_no_favourite(anon_client, db):
    security = make_security(db, "MC.PA")
    body = anon_client.get(f"/api/securities/{security.id}").json()
    assert body["is_favorite"] is False
    assert anon_client.get(f"/api/securities/{security.id}/simulate?amount=1000&period=1M").status_code == 200


def test_unsafe_request_without_csrf_header_is_refused(client):
    del client.headers["X-CSRF-Token"]
    response = client.put("/api/favorites/1")
    assert response.status_code == 403 and response.json()["detail"]["code"] == "csrf"


def test_eligibility_override_is_admin_only(client, anon_client, db):
    security = make_security(db, "MC.PA")
    assert client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "non_eligible"}).status_code == 403
    sign_in(anon_client, db, make_user(db, "admin@example.com", role="admin"))
    assert anon_client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "non_eligible"}).status_code == 200


def test_users_never_see_each_other_orders_or_favourites(client, anon_client, db, user):
    security = make_security(db, "MC.PA")
    other = make_user(db, "autre@example.com")
    db.add(Order(user_id=other.id, security_id=security.id, trade_date=date(2026, 9, 1), side="buy",
                 quantity=1, unit_price=10.0, fee=1.0))
    db.flush()
    sign_in(anon_client, db, other)
    assert anon_client.put(f"/api/favorites/{security.id}").status_code == 204
    assert client.get("/api/orders").json() == []
    assert client.get(f"/api/securities/{security.id}").json()["is_favorite"] is False
    order_id = anon_client.get("/api/orders").json()[0]["id"]
    assert client.delete(f"/api/orders/{order_id}").status_code == 404
    assert str(other.id) not in client.get("/api/orders").text
```

- [ ] **Step 3: Run and see them fail** (public routes return 401, forecasts return 200 anonymously, eligibility accepts a normal user).

- [ ] **Step 4: Implement.**
  - `repositories/screener.py`: `user_id: uuid.UUID | None`; build the flag as
    ```python
    if user_id is None:
        is_favorite = literal(False).label("is_favorite")  # visiteur sans compte
    else:
        is_favorite = (select(Favorite.security_id)
                       .where(Favorite.user_id == user_id, Favorite.security_id == Security.id)
                       .exists().label("is_favorite"))
    ```
    (`from sqlalchemy import Row, literal, select`).
  - `repositories/user_settings.py`: 
    ```python
    def user_fee_grid(session: Session, user_id: uuid.UUID | None) -> tuple[FeeTier, ...]:
        if user_id is None:  # visiteur : grille par défaut (Invest Store Intégral)
            return grid_from_json(DEFAULT_GRID_JSON)
        return grid_from_json(get_user_settings(session, user_id).fee_grid)
    ```
  - `screener.py`, `rankings.py`, `security_detail.py`, `fees.py`: `user: User | None = Depends(get_optional_user)` and pass `user.id if user else None` (in `security_detail.py` type `_row_or_404` and `simulate_since` with `uuid.UUID | None`). In `securities.py` `GET /securities` drops its unused `_user` parameter.
  - `securities.py` `PATCH /securities/{id}/eligibility`: `_admin: User = Depends(require_admin)`.
  - `forecasts.py`: add `_user: User = Depends(get_current_user)` to the four routes (private: AMF caution, spec 3.1).
  - `services/assistant/tools.py` keeps calling these functions with the signed-in `user`: no change needed.

- [ ] **Step 5: Run**: `pytest -q` → all PASS.

- [ ] **Step 6: Commit**: `git commit -am "feat: public showcase routes, private personal routes, admin-only eligibility override"` (with `git add` of the new test).

### Task 8: Sign-up and e-mail validation

**Files:**
- Create: `backend/app/services/auth/codes.py`, `backend/app/services/auth/accounts.py`, `backend/app/api/routes/auth.py`
- Modify: `backend/app/schemas/auth.py`, `backend/app/main.py` (register `auth`)
- Test: `backend/tests/test_auth_codes.py`, `backend/tests/test_api_signup.py`

**Interfaces:**
- Produces in `codes.py`: `CODE_TTL`, `RESET_TTL`, `NOT_ME_TTL`, `RESEND_AFTER`, `MAX_ATTEMPTS = 5`; `class CodeCheck(StrEnum): OK, INVALID, EXPIRED, TOO_MANY`; `issue_code(db, user, purpose, now) -> str`; `last_code_at(db, user, purpose) -> datetime | None`; `check_code(db, user, purpose, code, now) -> CodeCheck`; `issue_link_token(db, user, purpose, now, ttl) -> str`; `consume_link_token(db, token, purpose, now) -> User | None`.
- Produces in `accounts.py`: `TERMS_VERSION = "2026-09-28"`; `find_user(db, email) -> User | None`; `register(db, *, first_name, last_name, email, password, now) -> None`; `send_verification_code(db, user, now) -> None`; `verify_email(db, email, code, now) -> tuple[User | None, CodeCheck]`; `resend_code(db, email, now) -> None`.
- Schemas: `RegisterIn(first_name, last_name, email: EmailStr, password, accept_terms: bool)`, `VerifyEmailIn(email: EmailStr, code: str)`, `EmailIn(email: EmailStr)`.
- Routes: `POST /api/auth/register` → 202 `MessageOut`; `POST /api/auth/verify-email` → 200 `MeOut` + cookies; `POST /api/auth/resend-code` → 202 `MessageOut`.
- Shared helper in `routes/auth.py`: `start_session(db, user, request, response, *, persistent, now, alert_new_device: bool) -> None` (used again in Task 9).

- [ ] **Step 1: Write the failing unit tests** — `backend/tests/test_auth_codes.py`

```python
from datetime import UTC, datetime, timedelta

from app.services.auth.codes import CodeCheck, check_code, consume_link_token, issue_code, issue_link_token
from tests.factories import make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_code_ok_once(db):
    user = make_user(db, verified=False)
    code = issue_code(db, user, "verify_email", NOW)
    assert check_code(db, user, "verify_email", code, NOW) == CodeCheck.OK
    assert check_code(db, user, "verify_email", code, NOW) == CodeCheck.INVALID  # déjà utilisé


def test_code_expires_after_15_minutes(db):
    user = make_user(db, verified=False)
    code = issue_code(db, user, "verify_email", NOW)
    assert check_code(db, user, "verify_email", code, NOW + timedelta(minutes=15)) == CodeCheck.EXPIRED


def test_sixth_attempt_fails_even_with_right_code(db):
    user = make_user(db, verified=False)
    code = issue_code(db, user, "verify_email", NOW)
    wrong = "000000" if code != "000000" else "111111"
    results = [check_code(db, user, "verify_email", wrong, NOW) for _ in range(5)]
    assert results == [CodeCheck.INVALID] * 4 + [CodeCheck.TOO_MANY]
    assert check_code(db, user, "verify_email", code, NOW) == CodeCheck.TOO_MANY


def test_new_code_cancels_previous(db):
    user = make_user(db, verified=False)
    first = issue_code(db, user, "verify_email", NOW)
    second = issue_code(db, user, "verify_email", NOW)
    if first != second:
        assert check_code(db, user, "verify_email", first, NOW) == CodeCheck.INVALID
    assert check_code(db, user, "verify_email", second, NOW) == CodeCheck.OK


def test_link_token_single_use_and_purpose_bound(db):
    user = make_user(db)
    token = issue_link_token(db, user, "reset_password", NOW, timedelta(minutes=30))
    assert consume_link_token(db, token, "not_me", NOW) is None
    assert consume_link_token(db, token, "reset_password", NOW + timedelta(minutes=31)) is None
    assert consume_link_token(db, token, "reset_password", NOW) == user
    assert consume_link_token(db, token, "reset_password", NOW) is None
```
Note: `test_link_token...` consumes with an expired time first, which must **not** burn the token.

- [ ] **Step 2: Write the failing API tests** — `backend/tests/test_api_signup.py`

```python
import re

from sqlalchemy import select

from app.models import EmailLog, User
from app.services.auth.sessions import SESSION_COOKIE
from tests.factories import make_user

FORM = {"first_name": "Jean", "last_name": "Dupont", "email": "Jean@Example.com",
        "password": "motdepasse-solide", "accept_terms": True}


def _last_code(db, email="jean@example.com") -> str:
    mail = db.scalars(select(EmailLog).where(EmailLog.recipient == email, EmailLog.kind == "verify_code")
                      .order_by(EmailLog.id.desc())).first()
    return re.search(r"\b(\d{6})\b", mail.subject).group(1)


def test_signup_then_verify_opens_a_session(anon_client, db):
    response = anon_client.post("/api/auth/register", json=FORM)
    assert response.status_code == 202 and SESSION_COOKIE not in response.cookies
    user = db.scalar(select(User).where(User.email == "jean@example.com"))
    assert user.email_verified_at is None and user.terms_version == "2026-09-28"
    verified = anon_client.post("/api/auth/verify-email", json={"email": "jean@example.com", "code": _last_code(db)})
    assert verified.status_code == 200 and verified.json()["email"] == "jean@example.com"
    assert SESSION_COOKIE in verified.cookies and "pea_csrf" in verified.cookies
    assert anon_client.get("/api/me").status_code == 200
    kinds = [m.kind for m in db.scalars(select(EmailLog).order_by(EmailLog.id))]
    assert kinds == ["verify_code", "welcome"]


def test_existing_account_gets_same_answer_and_an_alert(anon_client, db):
    make_user(db, "jean@example.com")
    fresh = anon_client.post("/api/auth/register", json={**FORM, "email": "nouveau@example.com"})
    taken = anon_client.post("/api/auth/register", json=FORM)
    assert (taken.status_code, taken.json(), dict(taken.cookies)) == (fresh.status_code, fresh.json(), dict(fresh.cookies))
    alert = db.scalars(select(EmailLog).where(EmailLog.recipient == "jean@example.com")).one()
    assert alert.kind == "security_alert"


def test_wrong_code_and_errors(anon_client, db):
    anon_client.post("/api/auth/register", json=FORM)
    code = _last_code(db)
    wrong = "000000" if code != "000000" else "111111"
    response = anon_client.post("/api/auth/verify-email", json={"email": "jean@example.com", "code": wrong})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "invalid_code"
    unknown = anon_client.post("/api/auth/verify-email", json={"email": "personne@example.com", "code": code})
    assert unknown.status_code == 400 and unknown.json()["detail"]["code"] == "invalid_code"


def test_signup_rules(anon_client):
    assert anon_client.post("/api/auth/register", json={**FORM, "accept_terms": False}).status_code == 422
    weak = anon_client.post("/api/auth/register", json={**FORM, "password": "court"})
    assert weak.status_code == 400 and weak.json()["detail"]["code"] == "weak_password"
    assert anon_client.post("/api/auth/register", json={**FORM, "email": "pas-une-adresse"}).status_code == 422
    assert anon_client.post("/api/auth/register", json={**FORM, "first_name": "   "}).status_code == 422


def test_signing_up_again_before_validation_replaces_the_pending_account(anon_client, db):
    anon_client.post("/api/auth/register", json=FORM)
    anon_client.post("/api/auth/register", json={**FORM, "first_name": "Jeanne"})
    users = db.scalars(select(User).where(User.email == "jean@example.com")).all()
    assert len(users) == 1 and users[0].first_name == "Jeanne"


def test_resend_code_waits_60_seconds_and_hides_unknown_addresses(anon_client, db):
    anon_client.post("/api/auth/register", json=FORM)
    first = anon_client.post("/api/auth/resend-code", json={"email": "jean@example.com"})
    unknown = anon_client.post("/api/auth/resend-code", json={"email": "personne@example.com"})
    assert first.status_code == unknown.status_code == 202 and first.json() == unknown.json()
    # moins de 60 s après l'inscription : pas de deuxième code
    assert len(db.scalars(select(EmailLog).where(EmailLog.kind == "verify_code")).all()) == 1


def test_admin_email_becomes_admin_on_validation(anon_client, db, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "admin_email", "jean@example.com")
    anon_client.post("/api/auth/register", json=FORM)
    anon_client.post("/api/auth/verify-email", json={"email": "jean@example.com", "code": _last_code(db)})
    assert anon_client.get("/api/me").json()["role"] == "admin"
```

- [ ] **Step 3: Run and see them fail.**

- [ ] **Step 4: Implement `services/auth/codes.py`**

```python
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import new_code, new_token, same, token_hash
from app.models import EmailCode, User

CODE_TTL = timedelta(minutes=15)
RESET_TTL = timedelta(minutes=30)
NOT_ME_TTL = timedelta(days=7)
RESEND_AFTER = timedelta(seconds=60)
MAX_ATTEMPTS = 5


class CodeCheck(StrEnum):
    OK = "ok"
    INVALID = "invalid"
    EXPIRED = "expired"
    TOO_MANY = "too_many"


def _cancel_pending(db: Session, user: User, purpose: str, now: datetime) -> None:
    db.execute(update(EmailCode).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose,
                                       EmailCode.used_at.is_(None)).values(used_at=now))


def issue_code(db: Session, user: User, purpose: str, now: datetime) -> str:
    """Nouveau code à 6 chiffres ; les codes précédents du même type ne marchent plus."""
    _cancel_pending(db, user, purpose, now)
    code = new_code()
    db.add(EmailCode(user_id=user.id, purpose=purpose, code_hash=token_hash(code), expires_at=now + CODE_TTL,
                     created_at=now))
    db.flush()
    return code


def last_code_at(db: Session, user: User, purpose: str) -> datetime | None:
    return db.scalar(select(EmailCode.created_at).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose)
                     .order_by(EmailCode.id.desc()).limit(1))


def check_code(db: Session, user: User, purpose: str, code: str, now: datetime) -> CodeCheck:
    row = db.scalar(select(EmailCode).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose,
                                            EmailCode.used_at.is_(None)).order_by(EmailCode.id.desc()).limit(1))
    if row is None:
        return CodeCheck.INVALID
    if row.expires_at <= now:
        return CodeCheck.EXPIRED
    if row.attempts >= MAX_ATTEMPTS:
        return CodeCheck.TOO_MANY
    if not same(row.code_hash, token_hash(code.strip())):
        row.attempts += 1
        return CodeCheck.TOO_MANY if row.attempts >= MAX_ATTEMPTS else CodeCheck.INVALID
    row.used_at = now
    return CodeCheck.OK


def issue_link_token(db: Session, user: User, purpose: str, now: datetime, ttl: timedelta) -> str:
    """Jeton long (256 bits) pour un lien envoyé par mail ; les liens précédents du même type ne marchent plus."""
    _cancel_pending(db, user, purpose, now)
    token = new_token()
    db.add(EmailCode(user_id=user.id, purpose=purpose, code_hash=token_hash(token), expires_at=now + ttl, created_at=now))
    db.flush()
    return token


def consume_link_token(db: Session, token: str, purpose: str, now: datetime) -> User | None:
    row = db.scalar(select(EmailCode).where(EmailCode.code_hash == token_hash(token), EmailCode.purpose == purpose,
                                            EmailCode.used_at.is_(None), EmailCode.expires_at > now))
    if row is None:
        return None
    row.used_at = now
    return db.get(User, row.user_id)
```
(`created_at=now` is passed explicitly so the 60-second resend rule uses the same clock as the request.)

- [ ] **Step 5: Implement `services/auth/accounts.py`**

```python
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, needs_rehash, normalize_email, verify_password
from app.models import User
from app.services.auth.codes import RESEND_AFTER, CodeCheck, check_code, issue_code, last_code_at
from app.services.mail.outbox import enqueue

TERMS_VERSION = "2026-09-28"  # à changer quand les CGU changent (étape 4)


def find_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def send_verification_code(db: Session, user: User, now: datetime) -> None:
    code = issue_code(db, user, "verify_email", now)
    enqueue(db, "verify_code", to=user.email, user_id=user.id, context={"first_name": user.first_name, "code": code})


def register(db: Session, *, first_name: str, last_name: str, email: str, password: str, now: datetime) -> None:
    """Crée (ou remplace, s'il n'a jamais été validé) un compte et envoie le code.

    Si l'adresse appartient déjà à un compte validé, rien ne change : son propriétaire reçoit une alerte,
    et la réponse de l'API reste identique pour ne pas révéler que le compte existe.
    """
    user = find_user(db, email)
    if user is not None and user.email_verified_at is not None:
        enqueue(db, "security_alert", to=user.email, user_id=user.id,
                context={"first_name": user.first_name, "event": "signup_attempt"},
                dedupe_key=f"signup_attempt:{user.id}:{now:%Y-%m-%d}")  # au plus une alerte par jour
        return
    if user is None:
        user = User(email=normalize_email(email), first_name=first_name, last_name=last_name)
        db.add(user)
    user.first_name, user.last_name = first_name, last_name
    user.password_hash = hash_password(password)
    user.terms_accepted_at, user.terms_version = now, TERMS_VERSION
    db.flush()
    send_verification_code(db, user, now)


def verify_email(db: Session, email: str, code: str, now: datetime) -> tuple[User | None, CodeCheck]:
    user = find_user(db, email)
    if user is None or user.email_verified_at is not None:
        return None, CodeCheck.INVALID
    result = check_code(db, user, "verify_email", code, now)
    if result != CodeCheck.OK:
        return None, result
    user.email_verified_at = now
    if user.email == normalize_email(get_settings().admin_email or "-"):
        user.role, user.is_premium = "admin", True
    enqueue(db, "welcome", to=user.email, user_id=user.id, context={"first_name": user.first_name})
    return user, result


def resend_code(db: Session, email: str, now: datetime) -> None:
    user = find_user(db, email)
    if user is None or user.email_verified_at is not None:
        return
    last = last_code_at(db, user, "verify_email")
    if last is not None and now - last < RESEND_AFTER:
        return
    send_verification_code(db, user, now)


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Le compte si le mot de passe est bon (validé ou non), sinon None. Même durée dans tous les cas."""
    user = find_user(db, email)
    if not verify_password(user.password_hash if user else None, password):
        return None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user
```

- [ ] **Step 6: Schemas** — append to `schemas/auth.py`:

```python
from pydantic import EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: EmailStr
    password: str = Field(max_length=200)  # la règle 12–128 est vérifiée ensuite, avec un message clair
    accept_terms: bool

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Champ obligatoire.")
        return value

    @field_validator("accept_terms")
    @classmethod
    def terms_accepted(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Les CGU et la politique de confidentialité doivent être acceptées.")
        return value


class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\s*\d{6}\s*$")


class EmailIn(BaseModel):
    email: EmailStr
```

- [ ] **Step 7: Routes** — `backend/app/api/routes/auth.py`:

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.cookies import set_auth_cookies, set_device_cookie
from app.core.config import get_settings
from app.core.current_user import get_now
from app.core.db import get_db
from app.core.security import password_problem
from app.models import User
from app.schemas.auth import EmailIn, MeOut, MessageOut, RegisterIn, VerifyEmailIn
from app.services.auth import accounts
from app.services.auth.codes import CodeCheck
from app.services.auth.devices import remember_device
from app.services.auth.sessions import DEVICE_COOKIE, open_session

router = APIRouter(prefix="/auth", tags=["auth"])

CODE_SENT = MessageOut(message="Si cette adresse peut recevoir un code, il vient d'y être envoyé.")
CODE_ERRORS = {
    CodeCheck.INVALID: ("invalid_code", "Code incorrect."),
    CodeCheck.EXPIRED: ("code_expired", "Ce code a expiré : demandez-en un nouveau."),
    CodeCheck.TOO_MANY: ("too_many_attempts", "Trop d'essais : demandez un nouveau code."),
}


def fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message})


def check_password_rules(password: str) -> None:
    problem = password_problem(password)
    if problem:
        raise fail(400, "weak_password", problem)


def client_ip(request: Request) -> str | None:
    # nginx ajoute l'IP du visiteur en dernier dans X-Forwarded-For ; c'est le seul proxy de confiance.
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else None


def start_session(db: Session, user: User, request: Request, response: Response, *, persistent: bool,
                  now: datetime, alert_new_device: bool) -> None:
    """Ouvre la session, reconnaît l'appareil et pose les cookies. Le commit est fait ici."""
    settings = get_settings()
    new = open_session(db, user, persistent=persistent, ip=client_ip(request),
                       user_agent=request.headers.get("User-Agent"), now=now, settings=settings)
    device_token, is_new_device = remember_device(db, user, request.cookies.get(DEVICE_COOKIE), now)
    if alert_new_device and is_new_device:
        accounts.alert_new_device(db, user, new.session.device, now)
    db.commit()
    set_auth_cookies(response, new, settings)
    set_device_cookie(response, device_token, settings)


@router.post("/register", response_model=MessageOut, status_code=202)
def register(payload: RegisterIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> MessageOut:
    check_password_rules(payload.password)
    accounts.register(db, first_name=payload.first_name, last_name=payload.last_name, email=payload.email,
                      password=payload.password, now=now)
    db.commit()
    return CODE_SENT


@router.post("/verify-email", response_model=MeOut)
def verify_email(payload: VerifyEmailIn, request: Request, response: Response, db: Session = Depends(get_db),
                 now: datetime = Depends(get_now)) -> MeOut:
    user, result = accounts.verify_email(db, payload.email, payload.code, now)
    if user is None:
        db.commit()  # enregistre l'essai raté
        raise fail(400, *CODE_ERRORS[result])
    start_session(db, user, request, response, persistent=True, now=now, alert_new_device=False)
    return MeOut.model_validate(user)


@router.post("/resend-code", response_model=MessageOut, status_code=202)
def resend_code(payload: EmailIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> MessageOut:
    accounts.resend_code(db, payload.email, now)
    db.commit()
    return CODE_SENT
```

`remember_device` and `alert_new_device` are implemented in Task 9 Step 3; to keep this task green, create `backend/app/services/auth/devices.py` now with the Task 9 implementation of `remember_device`, and add to `accounts.py`:
```python
def alert_new_device(db: Session, user: User, device: str, now: datetime) -> None:
    from app.services.auth.codes import NOT_ME_TTL, issue_link_token

    token = issue_link_token(db, user, "not_me", now, NOT_ME_TTL)
    enqueue(db, "new_device", to=user.email, user_id=user.id,
            context={"first_name": user.first_name, "device": device, "when": now, "token": token})
```
(move the import to the top of the module; it is shown inline only to make the dependency visible).

Register `auth` in `app/main.py`.

- [ ] **Step 8: Run**: `pytest -q tests/test_auth_codes.py tests/test_api_signup.py` → PASS; then `pytest -q`.

- [ ] **Step 9: Commit**: `git add -A backend && git commit -m "feat: sign-up with e-mail code validation"`

### Task 9: Sign-in, sign-out, forgotten password, new device and "Ce n'était pas moi"

**Files:**
- Create/complete: `backend/app/services/auth/devices.py`
- Modify: `backend/app/services/auth/accounts.py`, `backend/app/api/routes/auth.py`, `backend/app/schemas/auth.py`
- Test: `backend/tests/test_api_signin.py`

**Interfaces:**
- Produces: `remember_device(db, user, device_token: str | None, now) -> tuple[str, bool]` (token to set in the cookie, `True` if this browser is new **and** the account already had another device); `accounts.request_password_reset(db, email, now) -> None`; `accounts.reset_password(db, token, password, now) -> User | None`; `accounts.not_me(db, token, now) -> User | None`.
- Schemas: `LoginIn(email: EmailStr, password: str (max 200), remember: bool = False)`, `ResetPasswordIn(token: str (max 100), password: str (max 200))`, `TokenIn(token: str (max 100))`.
- Routes: `POST /api/auth/login` → `MeOut` + cookies, 401 `invalid_credentials`, 403 `email_not_verified`; `POST /api/auth/logout` → 204; `POST /api/auth/forgot-password` → 202 `MessageOut`; `POST /api/auth/reset-password` → 200 `MessageOut` or 400 `invalid_token`/`weak_password`; `POST /api/auth/not-me` → 200 `MessageOut` or 400 `invalid_token`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_api_signin.py`

```python
import re

from sqlalchemy import func, select

from app.models import AuthSession, EmailLog
from app.services.auth.sessions import DEVICE_COOKIE, SESSION_COOKIE
from tests.factories import make_user

PASSWORD = "motdepasse-solide"


def _login(client, email="jean@example.com", password=PASSWORD, remember=False):
    return client.post("/api/auth/login", json={"email": email, "password": password, "remember": remember})


def _mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind).order_by(EmailLog.id)).all()


def _token(mail: EmailLog) -> str:
    return re.search(r"jeton=([\w-]+)", mail.text).group(1)


def test_login_sets_cookies_and_me_works(anon_client, db):
    make_user(db, "jean@example.com")
    response = _login(anon_client, "  JEAN@example.com ", remember=True)
    assert response.status_code == 200 and response.json()["email"] == "jean@example.com"
    assert {SESSION_COOKIE, "pea_csrf", DEVICE_COOKIE} <= set(response.cookies)
    assert anon_client.get("/api/me").status_code == 200


def test_bad_credentials_look_the_same(anon_client, db):
    make_user(db, "jean@example.com")
    wrong_password = _login(anon_client, password="mauvais-mot-de-passe")
    unknown = _login(anon_client, email="personne@example.com")
    assert wrong_password.status_code == unknown.status_code == 401
    assert wrong_password.json() == unknown.json()
    assert wrong_password.json()["detail"]["code"] == "invalid_credentials"


def test_unverified_account_is_sent_to_validation(anon_client, db):
    make_user(db, "jean@example.com", verified=False)
    response = _login(anon_client)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "email_not_verified"
    assert SESSION_COOKIE not in response.cookies
    assert len(_mails(db, "verify_code")) == 1


def test_logout_revokes_the_session(anon_client, db):
    make_user(db, "jean@example.com")
    _login(anon_client)
    anon_client.headers["X-CSRF-Token"] = anon_client.cookies["pea_csrf"]
    assert anon_client.post("/api/auth/logout").status_code == 204
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0
    assert anon_client.get("/api/me").status_code == 401


def test_new_device_alert_only_from_the_second_browser(anon_client, db):
    make_user(db, "jean@example.com")
    _login(anon_client)                  # premier appareil du compte : pas d'alerte
    _login(anon_client)                  # même navigateur (cookie pea_device) : pas d'alerte
    assert _mails(db, "new_device") == []
    anon_client.cookies.clear()
    _login(anon_client)                  # autre navigateur
    assert len(_mails(db, "new_device")) == 1


def test_not_me_closes_everything_and_forces_a_new_password(anon_client, db):
    user = make_user(db, "jean@example.com")
    _login(anon_client)
    anon_client.cookies.clear()
    _login(anon_client)
    token = _token(_mails(db, "new_device")[0])
    anon_client.cookies.clear()
    anon_client.headers.pop("X-CSRF-Token", None)
    assert anon_client.post("/api/auth/not-me", json={"token": token}).status_code == 200
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0
    db.refresh(user)
    assert user.password_hash is None and len(_mails(db, "reset_password")) == 1
    assert _login(anon_client).status_code == 401
    assert anon_client.post("/api/auth/not-me", json={"token": token}).status_code == 400  # usage unique


def test_forgot_and_reset_password(anon_client, db):
    make_user(db, "jean@example.com")
    _login(anon_client)
    same_answer = anon_client.post("/api/auth/forgot-password", json={"email": "personne@example.com"})
    response = anon_client.post("/api/auth/forgot-password", json={"email": "jean@example.com"})
    assert response.status_code == same_answer.status_code == 202 and response.json() == same_answer.json()
    token = _token(_mails(db, "reset_password")[0])
    weak = anon_client.post("/api/auth/reset-password", json={"token": token, "password": "court"})
    assert weak.status_code == 400 and weak.json()["detail"]["code"] == "weak_password"
    ok = anon_client.post("/api/auth/reset-password", json={"token": token, "password": "nouveau-mot-de-passe"})
    assert ok.status_code == 200
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 0  # tous les appareils déconnectés
    assert [m.kind for m in _mails(db, "security_alert")] == ["security_alert"]
    assert _login(anon_client, password="nouveau-mot-de-passe").status_code == 200
    again = anon_client.post("/api/auth/reset-password", json={"token": token, "password": "encore-un-autre-mdp"})
    assert again.status_code == 400 and again.json()["detail"]["code"] == "invalid_token"


def test_login_replaces_a_previous_session(anon_client, db):
    make_user(db, "jean@example.com")
    _login(anon_client)
    anon_client.headers["X-CSRF-Token"] = anon_client.cookies["pea_csrf"]
    _login(anon_client)
    assert db.scalar(select(func.count()).select_from(AuthSession)) == 1
```

- [ ] **Step 2: Run and see them fail.**

- [ ] **Step 3: Implement** `services/auth/devices.py`:

```python
from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.security import new_token, token_hash
from app.models import KnownDevice, User


def remember_device(db: Session, user: User, device_token: str | None, now: datetime) -> tuple[str, bool]:
    """Enregistre ce navigateur pour le compte. Renvoie (jeton du cookie pea_device, faut-il alerter ?).

    Pas d'alerte pour le tout premier appareil d'un compte (l'inscription elle-même).
    """
    token = device_token or new_token()
    digest = token_hash(token)
    if db.get(KnownDevice, (user.id, digest)) is not None:
        return token, False
    had_devices = db.scalar(select(exists().where(KnownDevice.user_id == user.id)))
    db.add(KnownDevice(user_id=user.id, token_hash=digest, first_seen_at=now))
    db.flush()
    return token, bool(had_devices)
```

Add to `accounts.py`:
```python
def request_password_reset(db: Session, email: str, now: datetime) -> None:
    user = find_user(db, email)
    if user is None or user.email_verified_at is None:
        return
    token = issue_link_token(db, user, "reset_password", now, RESET_TTL)
    enqueue(db, "reset_password", to=user.email, user_id=user.id,
            context={"first_name": user.first_name, "token": token, "valid_minutes": int(RESET_TTL.total_seconds() // 60)})


def reset_password(db: Session, token: str, password: str, now: datetime) -> User | None:
    user = consume_link_token(db, token, "reset_password", now)
    if user is None:
        return None
    user.password_hash = hash_password(password)
    user.failed_logins, user.locked_until = 0, None
    revoke_user_sessions(db, user.id)
    enqueue(db, "security_alert", to=user.email, user_id=user.id,
            context={"first_name": user.first_name, "event": "password_reset"})
    return user


def not_me(db: Session, token: str, now: datetime) -> User | None:
    """« Ce n'était pas moi » : tout le monde est déconnecté et l'ancien mot de passe ne marche plus."""
    user = consume_link_token(db, token, "not_me", now)
    if user is None:
        return None
    user.password_hash = None
    revoke_user_sessions(db, user.id)
    request_password_reset(db, user.email, now)
    return user
```
(imports: `RESET_TTL`, `issue_link_token`, `consume_link_token` from codes; `revoke_user_sessions` from sessions.)

Schemas in `schemas/auth.py`:
```python
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)
    remember: bool = False


class ResetPasswordIn(BaseModel):
    token: str = Field(max_length=100)
    password: str = Field(max_length=200)


class TokenIn(BaseModel):
    token: str = Field(max_length=100)
```

Routes, appended to `routes/auth.py` (imports: `get_auth_session`, `clear_auth_cookies`, `revoke_session`, `LoginIn`, `ResetPasswordIn`, `TokenIn`, `AuthSession`, `SESSION_COOKIE`, `resolve_session`):
```python
INVALID_TOKEN = ("invalid_token", "Ce lien n'est plus valable : refaites une demande.")
RESET_SENT = MessageOut(message="Si un compte utilise cette adresse, un lien vient d'y être envoyé.")


@router.post("/login", response_model=MeOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db),
          now: datetime = Depends(get_now)) -> MeOut:
    user = accounts.authenticate(db, payload.email, payload.password)
    if user is None:
        raise fail(401, "invalid_credentials", "Adresse mail ou mot de passe incorrect.")
    if user.email_verified_at is None:
        accounts.resend_code(db, user.email, now)
        db.commit()
        raise fail(403, "email_not_verified", "Validez d'abord votre adresse : un code vient de vous être envoyé.")
    previous = resolve_session(db, request.cookies.get(SESSION_COOKIE), now=now, settings=get_settings())
    if previous is not None:
        revoke_session(db, previous.id)  # jamais deux sessions pour le même cookie
    start_session(db, user, request, response, persistent=payload.remember, now=now, alert_new_device=True)
    return MeOut.model_validate(user)


@router.post("/logout", status_code=204)
def logout(response: Response, auth: AuthSession | None = Depends(get_auth_session), db: Session = Depends(get_db)) -> Response:
    if auth is not None:
        revoke_session(db, auth.id)
        db.commit()
    clear_auth_cookies(response, get_settings())
    response.status_code = 204
    return response


@router.post("/forgot-password", response_model=MessageOut, status_code=202)
def forgot_password(payload: EmailIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> MessageOut:
    accounts.request_password_reset(db, payload.email, now)
    db.commit()
    return RESET_SENT


@router.post("/reset-password", response_model=MessageOut)
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> MessageOut:
    check_password_rules(payload.password)
    if accounts.reset_password(db, payload.token, payload.password, now) is None:
        raise fail(400, *INVALID_TOKEN)
    db.commit()
    return MessageOut(message="Mot de passe modifié : vous pouvez vous connecter.")


@router.post("/not-me", response_model=MessageOut)
def not_me(payload: TokenIn, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> MessageOut:
    if accounts.not_me(db, payload.token, now) is None:
        raise fail(400, *INVALID_TOKEN)
    db.commit()
    return MessageOut(message="Tous vos appareils ont été déconnectés. Un lien pour choisir un nouveau mot de passe "
                              "vient de vous être envoyé.")
```
Note for `logout`: the dependency `get_auth_session` enforces CSRF, so a forged cross-site logout is refused.

- [ ] **Step 4: Run**: `pytest -q tests/test_api_signin.py` → PASS; `pytest -q` → PASS.

- [ ] **Step 5: Commit**: `git add -A backend && git commit -m "feat: sign-in, sign-out, password reset and new-device alert"`

### Task 10: Admin takeover at start-up and the `app.cli` commands

**Files:**
- Create: `backend/app/services/auth/bootstrap.py`, `backend/app/cli.py`
- Modify: `backend/docker/entrypoint-api.sh`, `docker-compose.dev.yml` (api command)
- Test: `backend/tests/test_bootstrap.py`

**Interfaces:**
- Produces: `bootstrap_admin(db, admin_email: str, now) -> str` (French status line, commits nothing); `ensure_user(db, *, email, password, first_name, last_name, admin: bool, now) -> User`; CLI `python -m app.cli bootstrap-admin` and `python -m app.cli ensure-user --email E --password P [--first-name F] [--last-name L] [--admin]`.
- `BOOTSTRAP_RESET_TTL = timedelta(hours=24)`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_bootstrap.py`

```python
from datetime import UTC, datetime

from sqlalchemy import select

from app.models import EmailLog, Favorite, User
from app.models.user import LEGACY_EMAIL
from app.services.auth.bootstrap import bootstrap_admin, ensure_user
from tests.factories import make_security, make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _legacy(db):
    return make_user(db, LEGACY_EMAIL, first_name="Moi", last_name="", password=None, role="admin", is_premium=True)


def test_admin_takes_over_moi_and_keeps_data(db):
    moi = _legacy(db)
    security = make_security(db, "MC.PA")
    db.add(Favorite(user_id=moi.id, security_id=security.id))
    db.flush()
    bootstrap_admin(db, " Clement@Example.com ", NOW)
    db.flush()
    assert moi.email == "clement@example.com" and moi.role == "admin"
    assert db.scalars(select(Favorite)).one().user_id == moi.id
    mails = db.scalars(select(EmailLog)).all()
    assert [m.kind for m in mails] == ["reset_password"] and mails[0].recipient == "clement@example.com"


def test_running_twice_sends_one_mail(db):
    _legacy(db)
    bootstrap_admin(db, "clement@example.com", NOW)
    bootstrap_admin(db, "clement@example.com", NOW)
    assert len(db.scalars(select(EmailLog)).all()) == 1


def test_existing_account_is_promoted(db):
    user = make_user(db, "clement@example.com")
    bootstrap_admin(db, "clement@example.com", NOW)
    assert user.role == "admin" and user.is_premium
    assert db.scalars(select(EmailLog)).all() == []  # il a déjà un mot de passe


def test_without_admin_email_nothing_changes(db):
    moi = _legacy(db)
    assert "ADMIN_EMAIL" in bootstrap_admin(db, "", NOW)
    assert moi.email == LEGACY_EMAIL


def test_ensure_user_creates_then_updates(db):
    user = ensure_user(db, email="e2e@pea-radar.test", password="motdepasse-e2e-123", first_name="Test",
                       last_name="E2E", admin=False, now=NOW)
    again = ensure_user(db, email="e2e@pea-radar.test", password="autre-mot-de-passe", first_name="Test",
                        last_name="E2E", admin=True, now=NOW)
    assert again.id == user.id and again.role == "admin" and again.email_verified_at == NOW
    assert len(db.scalars(select(User)).all()) == 1
```

- [ ] **Step 2: Run and see them fail.**

- [ ] **Step 3: Implement `services/auth/bootstrap.py`**

```python
from datetime import datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, normalize_email
from app.models import EmailCode, User
from app.models.user import LEGACY_EMAIL
from app.services.auth.accounts import TERMS_VERSION, find_user
from app.services.auth.codes import issue_link_token
from app.services.mail.outbox import enqueue

BOOTSTRAP_RESET_TTL = timedelta(hours=24)


def bootstrap_admin(db: Session, admin_email: str, now: datetime) -> str:
    """Au démarrage de l'API : ADMIN_EMAIL devient admin ; s'il n'existe pas, il reprend le compte « Moi ».

    Sans mot de passe (compte repris), un lien valable 24 h est envoyé, une seule fois.
    """
    if not admin_email.strip():
        return "ADMIN_EMAIL vide : aucun compte administrateur configuré."
    email = normalize_email(admin_email)
    user = find_user(db, email)
    if user is None:
        user = db.scalar(select(User).where(User.email == LEGACY_EMAIL))
        if user is None:
            return f"Aucun compte {email} : il deviendra admin dès qu'il aura validé son inscription."
        user.email = email
    user.role, user.is_premium = "admin", True
    user.email_verified_at = user.email_verified_at or now
    pending = db.scalar(select(exists().where(EmailCode.user_id == user.id, EmailCode.purpose == "reset_password",
                                              EmailCode.used_at.is_(None), EmailCode.expires_at > now)))
    if user.password_hash is None and user.google_sub is None and not pending:
        token = issue_link_token(db, user, "reset_password", now, BOOTSTRAP_RESET_TTL)
        enqueue(db, "reset_password", to=user.email, user_id=user.id,
                context={"first_name": user.first_name, "token": token, "valid_minutes": 24 * 60})
        return f"{email} est admin : un lien pour choisir son mot de passe vient d'être envoyé."
    return f"{email} est admin."


def ensure_user(db: Session, *, email: str, password: str, first_name: str, last_name: str, admin: bool,
                now: datetime) -> User:
    """Crée ou met à jour un compte déjà validé (tests de bout en bout, dépannage). Jamais exposé par l'API."""
    user = find_user(db, email)
    if user is None:
        user = User(email=normalize_email(email), first_name=first_name, last_name=last_name)
        db.add(user)
    user.first_name, user.last_name = first_name, last_name
    user.password_hash = hash_password(password)
    user.email_verified_at = user.email_verified_at or now
    user.terms_accepted_at, user.terms_version = now, TERMS_VERSION
    user.role = "admin" if admin else user.role or "user"
    db.flush()
    return user
```
Note: the `valid_minutes` 1440 renders "valable 1440 minutes" — acceptable but ugly: in `reset_password.*` templates, write `{% if valid_minutes >= 120 %}{{ valid_minutes // 60 }} heures{% else %}{{ valid_minutes }} minutes{% endif %}` and add a render test case (`valid_minutes: 1440` → "24 heures").

- [ ] **Step 4: Implement `app/cli.py`**

```python
"""Commandes d'exploitation : python -m app.cli <commande> (dans le conteneur api)."""
import argparse
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.services.auth.bootstrap import bootstrap_admin, ensure_user


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap-admin", help="Donne le rôle admin à ADMIN_EMAIL (lancé au démarrage de l'API)")
    user = commands.add_parser("ensure-user", help="Crée ou met à jour un compte validé (tests, dépannage)")
    user.add_argument("--email", required=True)
    user.add_argument("--password", required=True)
    user.add_argument("--first-name", default="Test")
    user.add_argument("--last-name", default="PEA Radar")
    user.add_argument("--admin", action="store_true")
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    with get_session_factory()() as db:
        if args.command == "bootstrap-admin":
            print(bootstrap_admin(db, get_settings().admin_email, now))
        else:
            account = ensure_user(db, email=args.email, password=args.password, first_name=args.first_name,
                                  last_name=args.last_name, admin=args.admin, now=now)
            print(f"Compte {account.email} prêt ({account.role}).")
        db.commit()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Start-up.** `backend/docker/entrypoint-api.sh`:
```sh
#!/bin/sh
set -e
alembic upgrade head
python -m app.cli bootstrap-admin
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```
`docker-compose.dev.yml` api command: `["sh", "-c", "alembic upgrade head && python -m app.cli bootstrap-admin && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]`.

- [ ] **Step 6: Run**: `pytest -q` → PASS. Then real check: back up (`docker compose exec -T db pg_dump -U pea pea_radar > ../pea-backup-2026-09-28.sql`, **outside** the repo), set `ADMIN_EMAIL` in `.env`, `docker compose up -d --build api worker mailpit`, `docker compose logs api | grep admin` shows "… est admin : un lien … envoyé", Mailpit shows the reset mail. Open the link only once the frontend exists (Bloc 4); the API can already be tested with `curl -X POST localhost:8000/api/auth/reset-password …` in the dev stack.

- [ ] **Step 7: Commit**: `git add -A backend docker-compose.dev.yml && git commit -m "feat: ADMIN_EMAIL takes over the existing data at start-up, app.cli commands"`

> **Fin du Bloc 3 — stop.** Status: the whole account API works (tests + Mailpit); next is Bloc 4 (screens).

---

# Bloc 4 — Écrans

Run `npm run gen:api` once at the start of this block (dev API up on :8000) so `schema.d.ts` knows `MeOut`, `RegisterIn`, etc.

### Task 11: API client (CSRF, error codes), `useMe`, `RequireAuth`, safe redirects

**Files:**
- Modify: `frontend/src/lib/api/client.ts`, `frontend/src/lib/api/schema.d.ts` (generated), `frontend/src/test/utils.tsx`
- Create: `frontend/src/features/auth/useMe.ts`, `frontend/src/features/auth/RequireAuth.tsx`, `frontend/src/features/auth/redirect.ts`
- Test: `frontend/src/lib/api/client.test.ts` (extend), `frontend/src/features/auth/redirect.test.ts`, `frontend/src/features/auth/RequireAuth.test.tsx`

**Interfaces:**
- Produces: `ApiError.code: string | null`; `csrfToken(): string | null`; `apiSend` and `streamSSE` send `X-CSRF-Token` when the cookie exists; `type Me = components["schemas"]["MeOut"]`.
- `useMe(): { me: Me | null | undefined; isPending: boolean }` — query key `["me"]`, `null` on 401, `staleTime: 60_000`.
- `safeNext(value: string | null): string` — internal path or `/`.
- `loginPath(location: { pathname: string; search: string }): string` → `/connexion?suite=<encoded>`.
- `<RequireAuth />` — renders `<Outlet />` when signed in, `<Navigate to={loginPath(location)} replace />` when `null`, nothing while pending.
- Test util: `ME` fixture object and `mockFetch` handlers answer `/api/me` (see Step 4).

- [ ] **Step 1: Failing tests.**

`redirect.test.ts`:
```ts
import { loginPath, safeNext } from "./redirect";

test.each([
  [null, "/"], ["", "/"], ["/portefeuille", "/portefeuille"], ["/titres/12?vue=1", "/titres/12?vue=1"],
  ["//evil.com", "/"], ["https://evil.com", "/"], ["/\\evil.com", "/"], ["javascript:alert(1)", "/"],
])("safeNext(%s) = %s", (value, expected) => {
  expect(safeNext(value)).toBe(expected);
});

test("loginPath garde la page demandée", () => {
  expect(loginPath({ pathname: "/portefeuille", search: "?onglet=ordres" })).toBe("/connexion?suite=%2Fportefeuille%3Fonglet%3Dordres");
});
```
Extend `client.test.ts`:
```ts
test("apiSend envoie le jeton CSRF lu dans le cookie", async () => {
  document.cookie = "pea_csrf=jeton-123; path=/";
  const fetchMock = mockFetch(() => ({ body: { ok: true } }));
  await apiSend("POST", "/api/test", {});
  expect(new Headers(fetchMock.mock.calls[0][1]!.headers).get("X-CSRF-Token")).toBe("jeton-123");
  document.cookie = "pea_csrf=; max-age=0; path=/";
});

test("les erreurs de l'API gardent leur code et leur message", async () => {
  mockFetch(() => ({ status: 401, body: { detail: { code: "invalid_credentials", message: "Adresse mail ou mot de passe incorrect." } } }));
  await expect(apiSend("POST", "/api/auth/login", {})).rejects.toMatchObject({
    status: 401, code: "invalid_credentials", message: "Adresse mail ou mot de passe incorrect.",
  });
});
```
`RequireAuth.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ME, mockFetch } from "@/test/utils";
import { RequireAuth } from "./RequireAuth";

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  const router = createMemoryRouter([
    { element: <RequireAuth />, children: [{ path: "/portefeuille", element: <h1>Portefeuille</h1> }] },
    { path: "/connexion", element: <h1>Connexion</h1> },
  ], { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("un visiteur est envoyé vers la connexion avec la page demandée", async () => {
  mockFetch(() => ({ status: 401, body: { detail: { code: "not_authenticated", message: "…" } } }));
  const router = renderAt("/portefeuille");
  expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
  expect(router.state.location.search).toBe("?suite=%2Fportefeuille");
});

test("un compte connecté voit la page", async () => {
  mockFetch(() => ({ body: ME }));
  renderAt("/portefeuille");
  expect(await screen.findByRole("heading", { name: "Portefeuille" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run** `npm test -- --run src/features/auth src/lib/api` → fail.

- [ ] **Step 3: Implement.**

In `client.ts`:
```ts
export type Me = components["schemas"]["MeOut"];

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** Jeton anti-CSRF posé par l'API à la connexion (cookie lisible), renvoyé dans un en-tête à chaque modification. */
export function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)pea_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function writeHeaders(accept: string, json: boolean): Record<string, string> {
  const token = csrfToken();
  return { Accept: accept, ...(json ? { "Content-Type": "application/json" } : {}), ...(token ? { "X-CSRF-Token": token } : {}) };
}
```
`errorFrom` now reads `detail` as a string **or** `{ code, message }`:
```ts
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") message = body.detail;
    else if (body.detail && typeof body.detail === "object" && "message" in body.detail) {
      const detail = body.detail as { code?: string; message: string };
      return new ApiError(response.status, detail.message, detail.code ?? null);
    }
```
`apiGet`: on non-OK, `throw await errorFrom(response, path)` (instead of the generic message) so `useMe` can see 401. `apiSend` uses `headers: writeHeaders("application/json", body !== undefined)`, `streamSSE` uses `writeHeaders("text/event-stream", true)`. Same-origin `fetch` sends cookies by default: no `credentials` option needed.

`redirect.ts`:
```ts
/** Chemin interne sûr pour revenir après la connexion ; tout le reste renvoie à l'accueil (pas de redirection ouverte). */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return "/";
  return value;
}

export function loginPath({ pathname, search }: { pathname: string; search: string }): string {
  return `/connexion?suite=${encodeURIComponent(pathname + search)}`;
}
```
`useMe.ts`:
```ts
import { useQuery } from "@tanstack/react-query";
import { ApiError, apiGet, type Me } from "@/lib/api/client";

/** Le compte connecté, `null` pour un visiteur, `undefined` pendant le premier chargement. */
export function useMe() {
  const { data, isPending } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await apiGet<Me>("/api/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });
  return { me: data, isPending };
}
```
`RequireAuth.tsx`:
```tsx
import { Navigate, Outlet, useLocation } from "react-router";
import { loginPath } from "./redirect";
import { useMe } from "./useMe";

/** Pages privées : visiteur renvoyé vers la connexion, puis ramené ici. */
export function RequireAuth() {
  const { me, isPending } = useMe();
  const location = useLocation();
  if (isPending) return null;
  if (!me) return <Navigate to={loginPath(location)} replace />;
  return <Outlet />;
}
```

- [ ] **Step 4: Test utils.** In `src/test/utils.tsx` export:
```ts
export const ME = { id: "0b6f7c1e-0000-4000-8000-000000000001", email: "moi@example.com", first_name: "Moi",
                    last_name: "Dupont", role: "user", is_premium: false };
```
Existing page tests that mock fetch with a catch-all body now also get that body for `/api/me`; where a test's handler returns `{ items: [], total: 0 }` by default, add `if (url === "/api/me") return ME;` (at least `router.test.tsx`'s `body()`; run the suite to find the others).

- [ ] **Step 5: Run** `npm test -- --run` → PASS; `npm run lint` → clean.

- [ ] **Step 6: Commit**: `git add frontend/src && git commit -m "feat: CSRF-aware API client, useMe and RequireAuth"`

### Task 12: The sliding sign-in / sign-up screen

**Files:**
- Create: `frontend/src/features/auth/AuthPage.tsx`, `SignUpForm.tsx`, `SignInForm.tsx`, `PasswordField.tsx`, `AuthFooter.tsx`, `AuthPage.test.tsx`
- Modify: `frontend/src/index.css` (auth panel animation, reduced motion)

**Interfaces:**
- Consumes: `apiSend`, `ApiError`, `safeNext`, `usePageMeta`, `Button`, `Input`.
- Produces: `<AuthPage mode="inscription" | "connexion" />`; `<PasswordField id label value onChange autoComplete showStrength? />`; `passwordStrength(value: string): 0 | 1 | 2 | 3` (exported from `PasswordField.tsx`); `<AuthFooter />` (legal links, used by every auth screen).
- Behaviour contract:
  - `/inscription` shows the sign-up form (h1 "Créer un compte"), `/connexion` the sign-in form (h1 "Se connecter"); the panel button navigates between the two URLs (`navigate(..., { replace: false })` so Back works) and keeps `?suite=`.
  - Sign-up success → `navigate("/verifier-email?adresse=<email>")`.
  - Sign-in success → invalidate `["me"]` then `navigate(safeNext(suite))`; `email_not_verified` → `/verifier-email?adresse=…`; other errors shown in a `role="alert"` paragraph.
  - Only the active form is in the accessibility tree (`inert` + `aria-hidden` on the other).

- [ ] **Step 1: Failing tests** — `AuthPage.test.tsx`

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { mockFetch } from "@/test/utils";
import { AuthPage } from "./AuthPage";
import { passwordStrength } from "./PasswordField";

afterEach(() => vi.unstubAllGlobals());

function renderAuth(path: string) {
  const router = createMemoryRouter([
    { path: "/inscription", element: <AuthPage mode="inscription" /> },
    { path: "/connexion", element: <AuthPage mode="connexion" /> },
    { path: "/verifier-email", element: <h1>Vérifier</h1> },
    { path: "/portefeuille", element: <h1>Portefeuille</h1> },
  ], { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("le panneau bascule entre inscription et connexion", async () => {
  mockFetch(() => ({ body: {} }));
  const router = renderAuth("/inscription?suite=%2Fportefeuille");
  expect(screen.getByRole("heading", { level: 1, name: "Créer un compte" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
  expect(await screen.findByRole("heading", { level: 1, name: "Se connecter" })).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/connexion");
  expect(router.state.location.search).toBe("?suite=%2Fportefeuille");
});

test("inscription : envoie le formulaire puis demande le code", async () => {
  const fetchMock = mockFetch(() => ({ status: 202, body: { message: "ok" } }));
  const router = renderAuth("/inscription");
  await userEvent.type(screen.getByLabelText("Prénom"), "Jean");
  await userEvent.type(screen.getByLabelText("Nom"), "Dupont");
  await userEvent.type(screen.getByLabelText("Adresse mail"), "jean@example.com");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "motdepasse-solide");
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Créer mon compte" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/verifier-email"));
  expect(router.state.location.search).toBe("?adresse=jean%40example.com");
  expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toMatchObject({ email: "jean@example.com", accept_terms: true });
});

test("inscription : mot de passe trop court refusé sans appel", async () => {
  const fetchMock = mockFetch(() => ({ body: {} }));
  renderAuth("/inscription");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "court");
  await userEvent.click(screen.getByRole("button", { name: "Créer mon compte" }));
  expect(fetchMock).not.toHaveBeenCalled();
});

test("connexion : erreur affichée, puis retour à la page demandée", async () => {
  let attempt = 0;
  mockFetch(() => (attempt++ === 0
    ? { status: 401, body: { detail: { code: "invalid_credentials", message: "Adresse mail ou mot de passe incorrect." } } }
    : { body: { email: "jean@example.com" } }));
  const router = renderAuth("/connexion?suite=%2Fportefeuille");
  await userEvent.type(screen.getByLabelText("Adresse mail"), "jean@example.com");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "mauvais-mot-de-passe");
  await userEvent.click(screen.getByRole("button", { name: "Me connecter" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Adresse mail ou mot de passe incorrect.");
  await userEvent.click(screen.getByRole("button", { name: "Me connecter" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/portefeuille"));
});

test("jauge de solidité", () => {
  expect(passwordStrength("")).toBe(0);
  expect(passwordStrength("court")).toBe(0);
  expect(passwordStrength("douzelettres")).toBe(1);
  expect(passwordStrength("Douze-lettres-7")).toBe(2);
  expect(passwordStrength("une phrase de passe très longue")).toBe(3);
});
```

- [ ] **Step 2: Run** → fail.

- [ ] **Step 3: Implement.** Key code (Tailwind; reuse `Button`, `Input`):

`PasswordField.tsx`:
```tsx
import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** Indication seulement : la règle qui fait foi (12 caractères) est vérifiée par l'API. */
export function passwordStrength(value: string): 0 | 1 | 2 | 3 {
  if (value.length < 12) return 0;
  const kinds = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((re) => re.test(value)).length;
  if (value.length >= 20) return 3;
  return kinds >= 3 ? 2 : 1;
}

const LABELS = ["Trop court (12 caractères minimum)", "Correct", "Solide", "Très solide"];
const COLORS = ["bg-red-500", "bg-amber-500", "bg-emerald-500", "bg-emerald-600"];

export function PasswordField({ id, label, value, onChange, autoComplete, showStrength = false }: {
  id: string; label: string; value: string; onChange: (value: string) => void;
  autoComplete: "new-password" | "current-password"; showStrength?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  const strength = passwordStrength(value);
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      <div className="relative">
        <Input id={id} type={visible ? "text" : "password"} value={value} autoComplete={autoComplete} required
               minLength={showStrength ? 12 : undefined} maxLength={128} className="bg-white pr-10"
               onChange={(e) => onChange(e.target.value)} />
        <button type="button" onClick={() => setVisible(!visible)} aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground hover:text-foreground">
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      {showStrength && value && (
        <div aria-live="polite" className="space-y-1">
          <div className="flex gap-1" aria-hidden>
            {[0, 1, 2].map((i) => <span key={i} className={cn("h-1 flex-1 rounded-full bg-muted", i < Math.max(strength, 1) && COLORS[strength])} />)}
          </div>
          <p className="text-xs text-muted-foreground">{LABELS[strength]}</p>
        </div>
      )}
    </div>
  );
}
```

`SignUpForm.tsx` (fields Prénom, Nom, Adresse mail, `PasswordField` with strength, checkbox with links to `/cgu` and `/confidentialite` opening in a new tab, submit "Créer mon compte"): local state; on submit `event.preventDefault()`, return early if `passwordStrength(password) === 0` (set an error "Le mot de passe doit contenir au moins 12 caractères.") or checkbox unchecked (native `required` on the checkbox handles it); `useMutation` → `apiSend("POST", "/api/auth/register", { first_name, last_name, email, password, accept_terms: true })`; success → `navigate(\`/verifier-email?adresse=${encodeURIComponent(email.trim().toLowerCase())}\`)`; error → `role="alert"` with `error.message`. Button disabled while pending, label "Création…".

`SignInForm.tsx` (Adresse mail, `PasswordField` current-password, checkbox "Rester connecté", link "Mot de passe oublié ?" to `/mot-de-passe-oublie`, submit "Me connecter"): mutation `apiSend("POST", "/api/auth/login", { email, password, remember })`; success → `await queryClient.invalidateQueries({ queryKey: ["me"] })`, `navigate(safeNext(searchParams.get("suite")), { replace: true })`; `ApiError` with `code === "email_not_verified"` → `navigate(\`/verifier-email?adresse=${…}\`)`; otherwise show `error.message` in `role="alert"`.

`AuthPage.tsx`:
```tsx
import { Radar } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthFooter } from "./AuthFooter";
import { SignInForm } from "./SignInForm";
import { SignUpForm } from "./SignUpForm";

type Mode = "inscription" | "connexion";

const PANEL = {
  inscription: { title: "Déjà un compte ?", text: "Retrouvez votre portefeuille, vos favoris et vos alertes.", action: "Se connecter" },
  connexion: { title: "Pas encore de compte ?", text: "Créez votre compte gratuit pour suivre votre PEA en quelques minutes.", action: "S'inscrire" },
};

export function AuthPage({ mode }: { mode: Mode }) {
  const signUp = mode === "inscription";
  usePageMeta({
    title: signUp ? "Créer un compte" : "Se connecter",
    description: "Créez votre compte PEA Radar ou connectez-vous pour suivre votre portefeuille PEA.",
  });
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const other = signUp ? "/connexion" : "/inscription";
  const panel = PANEL[mode];

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-background via-background to-primary/10 text-foreground">
      <nav aria-label="Navigation principale" className="px-4 py-4 sm:px-8">
        <Link to="/" className="inline-flex items-center gap-2 text-sm font-semibold">
          <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Radar className="size-4" aria-hidden /></span>
          PEA Radar
        </Link>
      </nav>
      <main className="flex flex-1 items-center justify-center px-4 py-6">
        <div className="relative w-full max-w-[960px] overflow-hidden rounded-2xl bg-white shadow-xl md:h-[600px]">
          {/* Panneau indigo : bandeau en haut sur mobile, moitié qui glisse sur grand écran */}
          <aside className={cn("auth-panel relative z-20 flex flex-col justify-center gap-4 bg-primary p-8 text-primary-foreground",
                               "md:absolute md:inset-y-0 md:w-1/2", signUp ? "md:translate-x-full" : "md:translate-x-0")}>
            <p className="text-2xl font-semibold">{panel.title}</p>
            <p className="text-sm text-primary-foreground/80">{panel.text}</p>
            <MiniChart />
            <Button variant="outline" className="w-fit border-white/60 bg-transparent text-white hover:bg-white/10 hover:text-white"
                    onClick={() => navigate({ pathname: other, search: params.toString() ? `?${params}` : "" })}>
              {panel.action}
            </Button>
          </aside>
          <div className="grid md:h-full md:grid-cols-2">
            <section aria-hidden={!signUp} inert={!signUp} className={cn("auth-form p-8 md:col-start-1", !signUp && "hidden md:block md:opacity-0")}>
              {signUp && <SignUpForm />}
            </section>
            <section aria-hidden={signUp} inert={signUp} className={cn("auth-form p-8 md:col-start-2", signUp && "hidden md:block md:opacity-0")}>
              {!signUp && <SignInForm />}
            </section>
          </div>
        </div>
      </main>
      <AuthFooter />
    </div>
  );
}

/** Courbe de cours stylisée, décorative. */
function MiniChart() {
  return (
    <svg viewBox="0 0 200 60" className="h-16 w-full max-w-xs text-white/70" aria-hidden>
      <polyline fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                points="0,50 25,44 45,47 70,32 95,36 120,22 145,26 170,12 200,8" />
    </svg>
  );
}
```
Each form renders its own `<h1>` ("Créer un compte" / "Se connecter"); only one form is mounted at a time, so there is exactly one `h1`.

In `index.css` add:
```css
/* Écran de connexion : le panneau indigo glisse d'une moitié à l'autre, le formulaire apparaît en fondu */
.auth-panel { transition: transform 600ms cubic-bezier(0.65, 0, 0.35, 1); }
.auth-form { transition: opacity 400ms ease 200ms; }
@media (prefers-reduced-motion: reduce) {
  .auth-panel, .auth-form { transition: none; }
}
```
Focus: in both forms, `autoFocus` on the first field (after navigation the new form mounts, so focus lands on it).

`AuthFooter.tsx`: `<footer>` with links "Mentions légales" (`/mentions-legales`), "CGU" (`/cgu`), "Confidentialité" (`/confidentialite`), "Guide" (`<a href="/guide/">`) and the "pas un conseil en investissement" sentence, `text-xs text-muted-foreground`, centred.

- [ ] **Step 4: Run** `npm test -- --run src/features/auth` → PASS; `npm run lint`.

- [ ] **Step 5: Commit**: `git add frontend/src && git commit -m "feat: sliding sign-in and sign-up screen"`

### Task 13: Code, forgotten-password, reset, "Ce n'était pas moi" and provisional legal pages

**Files:**
- Create: `frontend/src/features/auth/AuthCard.tsx`, `VerifyEmailPage.tsx`, `ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`, `NotMePage.tsx`, `AuthScreens.test.tsx`; `frontend/src/features/legal/LegalPage.tsx`
- Test: `frontend/src/features/auth/AuthScreens.test.tsx`

**Interfaces:**
- Produces: `<AuthCard title: string; children />` (same frame as the auth screen: logo nav, centred white card max 480 px, `AuthFooter`; renders the `h1`); pages listed above; `<LegalPage kind: "cgu" | "confidentialite" | "mentions-legales" />`.
- Behaviour:
  - `/verifier-email?adresse=…`: shows the address, one input `inputMode="numeric"`, `autoComplete="one-time-code"`, `maxLength={6}`, label "Code à 6 chiffres"; submit "Valider" → `POST /api/auth/verify-email` → invalidate `["me"]` → `navigate("/")`; "Renvoyer le code" disabled for 60 s (countdown text "Renvoyer le code (42 s)") → `POST /api/auth/resend-code`, toast "Si l'adresse est correcte, un nouveau code arrive." ; link "Modifier l'adresse" → `/inscription`. Without `adresse` param → `<Navigate to="/inscription" replace />`.
  - `/mot-de-passe-oublie`: email field → `POST /api/auth/forgot-password` → shows the API `message` in a `role="status"` paragraph and hides the form.
  - `/reinitialiser?jeton=…`: `PasswordField` (with strength) + confirmation field; mismatch → error "Les deux mots de passe sont différents." without call → `POST /api/auth/reset-password` → success message + link "Se connecter" (`/connexion`); `invalid_token` → message + link "Refaire une demande" (`/mot-de-passe-oublie`).
  - `/ce-n-etait-pas-moi?jeton=…`: a confirmation button "Sécuriser mon compte" (the action is not triggered by merely opening the link — mail scanners open links) → `POST /api/auth/not-me` → message.
  - `LegalPage`: provisional content in `Layout` (public): h1 "Conditions générales d'utilisation" / "Politique de confidentialité" / "Mentions légales", a paragraph "Version provisoire : le texte complet sera publié avant l'ouverture du site." and, for CGU, the investment-advice warning.

- [ ] **Step 1: Failing tests** — `AuthScreens.test.tsx` (same `createMemoryRouter` helper as Task 12):

```tsx
test("code : validation puis accueil", async () => {
  const fetchMock = mockFetch(() => ({ body: ME }));
  const router = renderAt("/verifier-email?adresse=jean%40example.com");
  expect(screen.getByText("jean@example.com")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Code à 6 chiffres"), "123456");
  await userEvent.click(screen.getByRole("button", { name: "Valider" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toEqual({ email: "jean@example.com", code: "123456" });
});

test("code : renvoi bloqué pendant 60 secondes", () => {
  mockFetch(() => ({ body: {} }));
  renderAt("/verifier-email?adresse=jean%40example.com");
  expect(screen.getByRole("button", { name: /Renvoyer le code/ })).toBeDisabled();
});

test("code : sans adresse, retour à l'inscription", async () => {
  mockFetch(() => ({ body: {} }));
  const router = renderAt("/verifier-email");
  await waitFor(() => expect(router.state.location.pathname).toBe("/inscription"));
});

test("mot de passe oublié : même message dans tous les cas", async () => {
  mockFetch(() => ({ status: 202, body: { message: "Si un compte utilise cette adresse, un lien vient d'y être envoyé." } }));
  renderAt("/mot-de-passe-oublie");
  await userEvent.type(screen.getByLabelText("Adresse mail"), "jean@example.com");
  await userEvent.click(screen.getByRole("button", { name: "Envoyer le lien" }));
  expect(await screen.findByRole("status")).toHaveTextContent("un lien vient d'y être envoyé");
});

test("réinitialisation : confirmation différente refusée, lien périmé expliqué", async () => {
  const fetchMock = mockFetch(() => ({ status: 400, body: { detail: { code: "invalid_token", message: "Ce lien n'est plus valable : refaites une demande." } } }));
  renderAt("/reinitialiser?jeton=abc");
  await userEvent.type(screen.getByLabelText("Nouveau mot de passe"), "nouveau-mot-de-passe");
  await userEvent.type(screen.getByLabelText("Confirmer le mot de passe"), "autre-mot-de-passe!");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Les deux mots de passe sont différents.");
  expect(fetchMock).not.toHaveBeenCalled();
  await userEvent.clear(screen.getByLabelText("Confirmer le mot de passe"));
  await userEvent.type(screen.getByLabelText("Confirmer le mot de passe"), "nouveau-mot-de-passe");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  expect(await screen.findByRole("link", { name: "Refaire une demande" })).toBeInTheDocument();
});

test("ce n'était pas moi : rien ne se passe sans clic", async () => {
  const fetchMock = mockFetch(() => ({ body: { message: "Tous vos appareils ont été déconnectés." } }));
  renderAt("/ce-n-etait-pas-moi?jeton=abc");
  expect(fetchMock).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Sécuriser mon compte" }));
  expect(await screen.findByRole("status")).toHaveTextContent("déconnectés");
});
```

- [ ] **Step 2: Run** → fail. **Step 3: Implement** the pages following the behaviour list above (each calls `usePageMeta({ title, description, noindex: true })`; each form shows API errors in `role="alert"`; the 60-second countdown uses `useEffect` + `setInterval(1000)`, started at mount and restarted after a resend). **Step 4: Run** → PASS, lint clean.

- [ ] **Step 5: Commit**: `git add frontend/src && git commit -m "feat: e-mail code, password reset and not-me screens, provisional legal pages"`

### Task 14: Wire everything into the app (routes, sidebar, banners, private cards)

**Files:**
- Modify: `frontend/src/app/router.tsx`, `Layout.tsx`, `Sidebar.tsx`, `router.test.tsx`, `Sidebar.test.tsx`; `frontend/src/components/FavoriteButton.tsx`; `frontend/src/features/security/ForecastCard.tsx`; `frontend/src/features/settings/SettingsPage.tsx`
- Create: `frontend/src/app/AccountMenu.tsx`, `frontend/src/app/SignUpBanner.tsx`

**Interfaces:**
- Consumes: `useMe`, `RequireAuth`, `loginPath`, auth pages, `LegalPage`.
- Produces routes:
  - top level, outside `Layout`: `/inscription`, `/connexion`, `/verifier-email`, `/mot-de-passe-oublie`, `/reinitialiser`, `/ce-n-etait-pas-moi` (lazy);
  - inside `Layout`, public: index, `explorer`, `etf`, `titres/:id`, `cgu`, `confidentialite`, `mentions-legales`, `*`;
  - inside `Layout` → `RequireAuth`: `previsions`, `portefeuille`, `assistant`, `reglages`.

- [ ] **Step 1: Failing tests.** In `router.test.tsx`:
  - `body()` returns `ME` for `/api/me` in the existing tests (signed-in user);
  - add:
```tsx
test("un visiteur qui ouvre le portefeuille arrive sur la connexion", async () => {
  mockFetch((url) => (url === "/api/me" ? { status: 401, body: { detail: { code: "not_authenticated", message: "…" } } } : { body: body(url) }));
  render(/* same providers */ <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/portefeuille"] })} />);
  expect(await screen.findByRole("heading", { level: 1, name: "Se connecter" }, { timeout: 5000 })).toBeInTheDocument();
});

test("un visiteur voit l'explorateur et le bandeau d'inscription", async () => {
  mockFetch((url) => (url === "/api/me" ? { status: 401, body: { detail: { code: "not_authenticated", message: "…" } } } : { body: body(url) }));
  renderRoute("/explorer");
  expect(await screen.findByRole("heading", { level: 1, name: "Explorer" }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Créer un compte gratuit" })).toHaveAttribute("href", "/inscription");
});

test.each([["/connexion", "Se connecter"], ["/inscription", "Créer un compte"]])("%s est indexable", async (path, title) => {
  mockFetch((url) => ({ body: body(url) }));
  renderRoute(path);
  await screen.findByRole("heading", { level: 1, name: title }, { timeout: 5000 });
  expect(robots()).toBeNull();
});
```
  - in `Sidebar.test.tsx`: signed in → the menu shows "Moi Dupont" and a "Se déconnecter" button; clicking it posts `/api/auth/logout`; anonymous → links "Se connecter" and "Créer un compte".
  - a test in `SettingsPage.test.tsx`: the "Éligibilité PEA — corrections manuelles" card is absent for `role: "user"` and present for `role: "admin"`.
  - a test for `ForecastCard`: when `/api/securities/1/forecast` answers 401, the card shows a link "Connectez-vous" to `/connexion?suite=…` and no error.

- [ ] **Step 2: Run** → fail.

- [ ] **Step 3: Implement.**
  - `router.tsx`: restructure as listed; private children inside `{ element: <RequireAuth />, children: [...] }`.
  - `AccountMenu.tsx` (bottom of the sidebar, above the Guide link): signed in → initials badge, full name, e-mail (truncated), button "Se déconnecter" → `apiSend("POST", "/api/auth/logout")`, then `queryClient.clear()` and `navigate("/")`. Anonymous → two links "Se connecter" (`/connexion`) and "Créer un compte" (`/inscription`, primary style). While `useMe` is pending → nothing.
  - `SignUpBanner.tsx`: for visitors only, a slim card at the top of `main` in `Layout`: "Créez un compte gratuit pour suivre votre portefeuille, vos favoris et vos alertes." + link "Créer un compte gratuit" (`/inscription`) + link "Se connecter". Not shown on the legal pages.
  - `Layout.tsx`: render `<SignUpBanner />` above `<Outlet />`.
  - `FavoriteButton.tsx`: `const { me } = useMe();` if `me === null`, clicking navigates to `loginPath(location)` instead of mutating; `aria-label` stays.
  - `ForecastCard.tsx`: `useQuery` gets `enabled: !!me`; when `me === null`, the card content is "Les prévisions sont réservées aux membres connectés." + `<Link to={loginPath(location)}>Connectez-vous</Link>`.
  - `SettingsPage.tsx`: render the eligibility card only when `me?.role === "admin"`; update the page description ("Assistant IA et frais de votre caisse régionale.") — the assistant card stays until step 3.
  - `useToggleFavorite` and every other mutation are unchanged (CSRF handled in `apiSend`).

- [ ] **Step 4: Run** `npm test -- --run` → PASS; `npm run lint`; `npm run build` → OK.

- [ ] **Step 5: Manual check** (full stack `docker compose up -d --build`): anonymous home and explorer work with the banner; `/portefeuille` redirects to `/connexion?suite=%2Fportefeuille`; sign up → code from Mailpit → home signed in; sign out; sign in again → back to the requested page; the admin reset link from Bloc 3 works and "Moi"'s portfolio is there.

- [ ] **Step 6: Commit**: `git add frontend/src && git commit -m "feat: private pages behind sign-in, account menu and sign-up banner"`

> **Fin du Bloc 4 — stop.** Status: the screens work end to end; next is Bloc 5 (e2e tests and docs).

---

# Bloc 5 — Bout en bout, documentation, vérification

### Task 15: Playwright with accounts

**Files:**
- Create: `frontend/e2e/global-setup.ts`, `frontend/e2e/auth.spec.ts`
- Modify: `frontend/playwright.config.ts`, `frontend/e2e/smoke.spec.ts`, `frontend/e2e/seo.spec.ts`, `frontend/e2e/layout.spec.ts`, `.gitignore` (`frontend/e2e/.auth/`)

**Interfaces:**
- Produces: `E2E_EMAIL = "e2e@pea-radar.test"`, `E2E_PASSWORD = "motdepasse-e2e-123"`; storage state `e2e/.auth/user.json` used by default; `auth.spec.ts` runs without it.

- [ ] **Step 1: Global setup** — `global-setup.ts`:

```ts
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { request, type FullConfig } from "@playwright/test";

export const E2E_EMAIL = "e2e@pea-radar.test";
export const E2E_PASSWORD = "motdepasse-e2e-123";
export const STATE = "e2e/.auth/user.json";

/** Compte de test validé (créé dans le conteneur api), connecté une fois pour toutes les pages privées. */
export default async function globalSetup(config: FullConfig) {
  execSync(`docker compose exec -T api python -m app.cli ensure-user --email ${E2E_EMAIL} --password ${E2E_PASSWORD} --first-name Test --last-name E2E --admin`,
           { cwd: "..", stdio: "inherit" });
  mkdirSync("e2e/.auth", { recursive: true });
  const context = await request.newContext({ baseURL: config.projects[0].use.baseURL });
  const response = await context.post("/api/auth/login", { data: { email: E2E_EMAIL, password: E2E_PASSWORD, remember: true } });
  if (!response.ok()) throw new Error(`Connexion du compte e2e impossible : ${response.status()}`);
  await context.storageState({ path: STATE });
  await context.dispose();
}
```
`playwright.config.ts`: `globalSetup: "./e2e/global-setup.ts"`, `use.storageState: "e2e/.auth/user.json"`.
Note: with `COOKIE_SECURE=false` locally the cookies work on `http://localhost:8095`; the e2e run requires the local `.env` value (document it in `developpement.md`).

- [ ] **Step 2: `auth.spec.ts`**

```ts
import { expect, test } from "@playwright/test";

test.use({ storageState: { cookies: [], origins: [] } });

async function lastCode(request: import("@playwright/test").APIRequestContext, to: string): Promise<string> {
  for (let i = 0; i < 20; i++) {
    const list = await (await request.get(`http://localhost:8025/api/v1/search?query=to:${encodeURIComponent(to)}`)).json();
    const subject: string | undefined = list.messages?.[0]?.Subject;
    const code = subject?.match(/\b(\d{6})\b/)?.[1];
    if (code) return code;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("Aucun code reçu dans Mailpit");
}

test("inscription, code reçu par mail, déconnexion puis connexion", async ({ page, request }) => {
  const email = `e2e-${Date.now()}@pea-radar.test`;
  await page.goto("/inscription");
  await page.getByLabel("Prénom").fill("Élodie");
  await page.getByLabel("Nom").fill("Test");
  await page.getByLabel("Adresse mail").fill(email);
  await page.getByLabel("Mot de passe", { exact: true }).fill("motdepasse-solide-e2e");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Créer mon compte" }).click();
  await expect(page).toHaveURL(/verifier-email/);
  await page.getByLabel("Code à 6 chiffres").fill(await lastCode(request, email));
  await page.getByRole("button", { name: "Valider" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Accueil" })).toBeVisible();
  await page.getByRole("button", { name: "Se déconnecter" }).click();
  await page.goto("/portefeuille");
  await expect(page).toHaveURL(/\/connexion\?suite=%2Fportefeuille/);
  await page.getByLabel("Adresse mail").fill(email);
  await page.getByLabel("Mot de passe", { exact: true }).fill("motdepasse-solide-e2e");
  await page.getByRole("button", { name: "Me connecter" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Portefeuille" })).toBeVisible();
});

test("le panneau glisse et l'URL suit", async ({ page }) => {
  await page.goto("/inscription");
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/connexion$/);
  await expect(page.getByRole("heading", { level: 1, name: "Se connecter" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { level: 1, name: "Créer un compte" })).toBeVisible();
});

test("un visiteur voit la vitrine", async ({ page }) => {
  await page.goto("/explorer");
  await expect(page.getByRole("heading", { level: 1, name: "Explorer" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Créer un compte gratuit" })).toBeVisible();
});
```
Accounts created by this test (`e2e-<timestamp>@pea-radar.test`) accumulate locally; the cleanup of unverified/old accounts comes with step 4. Acceptable.

- [ ] **Step 3: Update existing specs.**
  - `smoke.spec.ts`: the assistant test no longer expects the settings card to be global — keep it (the card still exists at step 1).
  - `seo.spec.ts`: add `/connexion` and `/inscription` to the indexable list; add `/verifier-email?adresse=a%40b.fr`, `/mot-de-passe-oublie` to `NOINDEX`. Auth pages have `main`, `nav` and `footer` exactly once (built in Task 12/13).
  - `layout.spec.ts`: add `/connexion` and `/inscription` to the paths (and a 390 px run on these two only, checking no horizontal scroll).

- [ ] **Step 4: Run** the full stack (`docker compose up -d --build`) then `cd frontend && npm run e2e` → all PASS.

- [ ] **Step 5: Commit**: `git add frontend/e2e frontend/playwright.config.ts .gitignore && git commit -m "test: end-to-end sign-up with Mailpit and signed-in storage state"`

### Task 16: Documentation, CLAUDE.md and final verification

**Files:**
- Create: `frontend/public/guide/app/compte.md`, `frontend/public/documentation/comptes.md`
- Modify: `frontend/public/guide/_sidebar.md`, `frontend/public/guide/premiers-pas.md`, `frontend/public/guide/app/reglages.md`, `frontend/public/documentation/_sidebar.md`, `api.md`, `base-de-donnees.md`, `installation.md`, `developpement.md`, `architecture.md`, `CLAUDE.md`, `README.md`

- [ ] **Step 1: Guide** (`app/compte.md`, in the sidebar under "Utiliser l'application", first item): create an account, the code (where to find it, spam folder, 15 min, resend after 60 s), sign in and "Rester connecté", forgotten password, the "nouvel appareil" mail and what "Ce n'était pas moi" does, what is visible without an account. No file names, no commands (guide rules). Update `premiers-pas.md` (step 1 = create your account) and `reglages.md` (eligibility corrections are now an admin tool).

- [ ] **Step 2: Admin documentation** (`comptes.md`, under "Fonctionnement"): sessions and cookies, CSRF, codes and tokens (TTL, attempts), outbox and retries, Mailpit, `ADMIN_EMAIL` takeover and `python -m app.cli` commands, public/private route table, what step 2 will add. Update `api.md` (the `/api/auth/*` and `/api/me` routes, error body format), `base-de-donnees.md` (new tables, UUID), `installation.md` (new `.env` variables, backup before the migration, Mailpit on 8025), `developpement.md` (fixtures `user`/`client`/`anon_client`, `sign_in`, `FakeMailer`, e2e account and `COOKIE_SECURE=false`), `architecture.md` (mailpit container, outbox arrow). Check with `npm run e2e -- documentation.spec.ts`.

- [ ] **Step 3: CLAUDE.md**:
  - Architecture diagram: add `mailpit` and "worker → SMTP".
  - Replace the "Multi-utilisateur prêt" convention by: routes get the user via `get_current_user()` (private, 401) / `get_optional_user()` (public) / `require_admin()`; new API errors use `{"detail": {"code", "message"}}`; never store a token in clear; `enqueue()` never commits and the API never sends mail itself.
  - Ports: add Mailpit 8025.
  - Commands: `python -m app.cli bootstrap-admin|ensure-user`.
  - Pitfalls: the UUID migration is one-way (back up first); `COOKIE_SECURE=false` only locally; tests use `anon_client`/`client` with `https://testserver`.
  - README: `.env` (ADMIN_EMAIL, SMTP), Mailpit URL, first start (mail to choose the admin password).

- [ ] **Step 4: Final verification** (all must pass, paste the summary lines in the status):
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`
  - `cd frontend && npm test -- --run && npm run lint && npm run build`
  - `docker compose up -d --build && cd frontend && npm run e2e`
  - `docker compose exec -T api alembic check` → no difference.
  - Check the review focus list at the top of this plan item by item.

- [ ] **Step 5: Commit and push**: `git add -A && git commit -m "docs: user accounts in the guide, admin documentation and CLAUDE.md"`, then `git push -u origin comptes-socle` and give the user the pre-filled PR link: `https://github.com/gbtclement/PEA/compare/master...comptes-socle?expand=1` with a suggested title "Comptes utilisateurs : socle (inscription, connexion, mails)" and a body ending with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

> **Fin du Bloc 5 — stop.** Status: branch ready for the PR; next is step 2 (`comptes-securite`: Google, Turnstile, rate limits), which gets its own plan.
