# Comptes : RGPD, pages légales, CGU versionnées, et correctifs de sécurité — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre PEA Radar publiable : CGU versionnées avec écran d'acceptation, pages légales complètes (brouillons), export des données (C7), suppression du compte par son titulaire (C6), durées de conservation avec mail d'inactivité (C8), registre des traitements, plus les correctifs de sécurité reportés des étapes 2 et 3.

**Architecture:** Backend FastAPI existant. Nouveau paquet `app/services/privacy/` : `erasure.py` (suppression d'un compte, partagée par l'utilisateur, l'admin et la purge d'inactivité), `export.py` (construction du JSON), `retention.py` (purges nocturnes et inactivité). Une seule nouvelle table, `data_exports`, dont le contenu JSON est stocké en base (pas de fichier partagé entre `api` et `worker`). La vérification des CGU passe dans `get_current_user()` : toutes les routes personnelles la reçoivent sans rien changer ; les routes de compte (`/api/me…`) utilisent `get_account_user()`, sans cette vérification, pour que l'écran `/accepter-cgu` fonctionne. Côté React : pages légales réécrites, écran `/accepter-cgu`, carte « Mes données » dans les Réglages.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, APScheduler, Jinja2, React 19, react-router 7, TanStack Query, Vitest, Playwright, Docsify.

**Spec:** `docs/superpowers/specs/2026-09-28-comptes-utilisateurs-design.md` (sections 1.1 `terms_*` et `inactivity_warned_at`, 1.2 `data_exports`, 2.1 `require_verified_user`, 3.5, 4.1 « Exporter mes données » et « Supprimer mon compte », 5.1 C6 à C8, 6.1 à 6.6, 8, 10, 11 étape 4).

**Branche :** `comptes-rgpd`, créée depuis `master` (étapes 1 à 3 fusionnées, PR #1 à #5).

## Global Constraints

- Interface, messages d'erreur, commentaires et docstrings en **français** ; identifiants en anglais ; commits en anglais, *conventional commits*, terminés par `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Erreurs d'API : `{"detail": {"code", "message"}}` (helper `fail()` de `app/api/routes/auth.py`).
- CGU : « La version courante est une constante (`TERMS_VERSION`). Si `terms_version` de l'utilisateur est différente, […] 403 `terms_outdated` et le frontend affiche `/accepter-cgu`. »
- Export : « un JSON (profil, réglages, préférences, ordres, favoris, alertes, conversations et messages), puis mail C7 avec un lien valable 7 jours qui exige d'être connecté. Un export à la fois, au plus un par jour. »
- Effacement : « suppression immédiate du compte et de ses données (cascade). `security_events` et `email_log` gardent la ligne avec `user_id` à vide et le mail remplacé par une empreinte. »
- Suppression par l'utilisateur : « mot de passe demandé, ou reconnexion Google de moins de 5 minutes pour un compte sans mot de passe ».
- Conservation (tâche de nuit) : comptes jamais validés 7 jours ; sessions, codes et exports expirés supprimés ; `email_log` 90 jours ; `security_events` 12 mois ; 3 ans sans connexion → C8, puis suppression 30 jours après si toujours aucune connexion ; **les admins sont exclus**.
- Pages légales : brouillons complets, éléments inconnus marqués `[À COMPLÉTER]`, relecture par un professionnel conseillée ; publiques et indexables ; `/cgv` n'existe pas.
- Cookies : uniquement strictement nécessaires + Turnstile → **pas de bandeau de consentement**.
- Sous-traitants déclarés : hébergeur, Brevo, Google, Cloudflare, **Anthropic** (États-Unis, rappel sur la page de l'assistant).
- Aucun test n'appelle Google, Cloudflare, Have I Been Pwned, Anthropic ni un vrai SMTP.
- Ports : web 8095, API de dev 8000, Vite 5180, Mailpit 8025. Jamais 8080, 8081, 5173.
- Commandes backend **toujours dans Docker**, depuis la racine : `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q …`. Frontend : `cd frontend && npx vitest --run …`.
- La base réelle (`pgdata`) est partagée avec l'API de dev qui migre au démarrage : la migration est d'abord vérifiée sur une base jetable (Task 3, Step 4).

## Rulings (décisions prises là où la spec se tait)

1. **`require_verified_user()` = `get_current_user()`** : la vérification des CGU est ajoutée à `get_current_user()` (refus par défaut : `require_admin`, `require_premium` et toutes les routes personnelles l'héritent). Les routes de compte (`/api/me`, profil, mot de passe, adresse, appareils, acceptation, export, suppression) utilisent une nouvelle dépendance `get_account_user()` sans vérification des CGU. `MeOut` gagne `terms_outdated`.
2. **Nouvelle version des CGU** : `TERMS_VERSION = "2026-10-01"` (texte définitif de cette étape). Tous les comptes existants, admin compris, acceptent une fois à la prochaine visite. `ensure-user` (e2e) et la fabrique de test posent la version courante.
3. **Redirection vers `/accepter-cgu`** depuis `Layout` (toutes les pages de l'application, publiques comprises) et non depuis `RequireAuth` seul : sinon une page publique appellerait des routes personnelles (compteur d'ordres, favoris) qui répondent 403.
4. **Contenu de l'export en base** (`data_exports.content`, texte JSON) au lieu d'un fichier : `api` et `worker` n'ont pas de volume commun, et le JSON d'un particulier pèse quelques centaines de Ko. Le contenu est effacé avec la ligne à l'expiration.
5. **Préférences de notification et alertes de prix** n'existent qu'à l'étape 5 : l'export les ajoutera alors. Il contient en plus `ai_usage` (coût de l'assistant) et les appareils connectés, qui sont des données personnelles.
6. **Route de suivi de l'export** : `GET /api/me/export` (dernier export, ou `null`) en plus de `POST /api/me/export` et `GET /api/me/export/{id}`, pour que la carte des Réglages affiche l'état.
7. **« Reconnexion Google de moins de 5 minutes »** = la session courante a été ouverte il y a moins de 5 minutes. Un compte sans mot de passe ne peut se connecter qu'avec Google : c'est donc bien une reconnexion Google. Sinon 403 `reauth_required`, et la carte propose « Se reconnecter avec Google » (retour sur `/reglages`).
8. **Confirmation de la suppression par l'utilisateur** : il retape aussi son adresse (même garde-fou que l'admin) ; le dernier admin ne peut pas se supprimer (`last_admin`).
9. **Mail C6 après suppression** : sa ligne d'`email_log` garde l'adresse le temps de l'envoi, puis `forget_secrets()` la remplace par une empreinte. Les mails encore en attente du compte supprimé sont retirés de la file.
10. **Inactivité** : « connexion » = la plus récente de `created_at`, `last_login_at` et `last_seen_at`. `last_seen_at` de l'utilisateur est mis à jour en même temps que celui de la session (au plus une fois par minute), pour qu'un « rester connecté » actif ne soit jamais pris pour de l'inactivité. La suppression pour inactivité envoie aussi C6.
11. **Heure de la purge** : la tâche `cleanup` existante (3 h 30) fait tout ; la spec dit 3 h, l'écart ne change rien pour l'utilisateur.
12. **Correctifs reportés** (revue finale de l'étape 3, et restes de l'étape 2) regroupés au Bloc 2. `locked_until` reste écrit mais non lu : le blocage réel passe par `ratelimit` (compteur `login_account`) ; rien à corriger.

## Review Focus

1. **Un compte aux CGU périmées ne doit rien pouvoir faire d'autre qu'accepter** : ordres, favoris, assistant, admin répondent 403 `terms_outdated` ; `/api/me`, l'acceptation, la déconnexion, l'export et la suppression restent possibles. Test : Task 1 `test_outdated_terms_block_personal_routes_but_not_account_routes`.
2. **L'export d'un autre** : `GET /api/me/export/{id}` d'un export d'autrui, expiré ou pas encore prêt → 404, jamais son contenu. Test : Task 3 `test_export_download_is_owner_only_and_expires`.
3. **Ce qui reste après une suppression** : plus aucune ligne liée au compte (ordres, favoris, conversations, sessions, exports, usage IA), et l'adresse n'apparaît plus en clair ni dans `email_log` (sauf C6 jusqu'à son envoi) ni dans `security_events`. Test : Task 2 `test_self_delete_erases_everything_and_anonymizes_logs`.
4. **Admins et comptes actifs épargnés par la purge d'inactivité** : un admin inactif depuis 4 ans, ou un compte averti qui s'est reconnecté après le C8, ne sont jamais supprimés. Test : Task 4 `test_inactivity_never_deletes_admins_or_accounts_back_in_use`.
5. **Rafale sur le mot de passe actuel** : 10 essais faux en 15 min sur `/me/password`, `/me/email` ou `DELETE /me` → 429, même avec le bon mot de passe ensuite. Test : Task 5 `test_current_password_guesses_are_limited`.

---

## File Structure

| Fichier | Responsabilité |
|---|---|
| `backend/app/core/current_user.py` (modifié) | `get_account_user()` ; `get_current_user()` vérifie les CGU |
| `backend/app/services/auth/accounts.py` (modifié) | `TERMS_VERSION = "2026-10-01"`, `accept_terms()` |
| `backend/app/services/privacy/__init__.py` (créé) | paquet |
| `backend/app/services/privacy/erasure.py` (créé) | `erase_account()`, `email_fingerprint()` |
| `backend/app/services/privacy/export.py` (créé) | `build_export()`, `request_export()`, règles « un à la fois, un par jour » |
| `backend/app/services/privacy/retention.py` (créé) | purges nocturnes et inactivité |
| `backend/app/models/privacy.py` (créé) | table `data_exports` |
| `backend/alembic/versions/e6b8d0f2a4c6_data_exports.py` (créé) | migration |
| `backend/app/api/routes/me.py` (modifié) | `accept-terms`, `export`, `DELETE /me`, limite des essais de mot de passe |
| `backend/app/jobs/privacy.py` (créé) | `build_pending_exports()` (toutes les 15 s) |
| `backend/app/jobs/cleanup.py`, `scheduler.py` (modifiés) | purge nocturne étendue, tâche `exports` |
| `backend/app/services/mail/templates/data_export_ready.*`, `inactivity_warning.*` (créés) | C7, C8 |
| `backend/app/services/admin/users.py` (modifié) | suppression via `erase_account()`, recherche échappée, verrou du dernier admin |
| `frontend/src/features/legal/` (réécrit) | pages légales complètes |
| `frontend/src/features/auth/AcceptTermsPage.tsx` (créé) | `/accepter-cgu` |
| `frontend/src/features/settings/DataCard.tsx` (créé) | export et suppression du compte |
| `frontend/public/documentation/registre.md` (créé) | registre des traitements |

---

# Bloc 1 — Backend RGPD (Tasks 1 à 4)

### Task 1: CGU versionnées et acceptation

**Files:**
- Modify: `backend/app/core/current_user.py`, `backend/app/services/auth/accounts.py`, `backend/app/schemas/auth.py`, `backend/app/api/routes/me.py`, `backend/app/services/security_log.py`, `backend/tests/factories.py`
- Test: `backend/tests/test_api_terms.py` (créé)

**Interfaces:**
- Produces: `get_account_user(user = Depends(get_optional_user)) -> User` (401 si absent, pas de vérification des CGU) ; `get_current_user` lève 403 `terms_outdated` ; `accounts.TERMS_VERSION = "2026-10-01"` ; `accounts.accept_terms(user, now) -> None` ; `MeOut.terms_outdated: bool` ; `POST /api/me/accept-terms` `{accept_terms: true}` → `MeOut` ; événement `terms_accepted`.

- [ ] **Step 1: Fabrique de test à jour** — dans `tests/factories.py`, `make_user` prend `terms_version: str | None = TERMS_VERSION` et le pose avec `terms_accepted_at=datetime(2026, 9, 1, tzinfo=UTC)` :

```python
from app.services.auth.accounts import TERMS_VERSION
...
def make_user(
    db: Session, email: str = "moi@example.com", *, first_name: str = "Jean", last_name: str = "Dupont",
    password: str | None = "motdepasse-solide", verified: bool = True, role: str = "user", is_premium: bool = False,
    terms_version: str | None = TERMS_VERSION,
) -> User:
    ...
    user = User(
        email=email, first_name=first_name, last_name=last_name,
        password_hash=_HASHES[password] if password is not None else None,
        email_verified_at=datetime(2026, 9, 1, tzinfo=UTC) if verified else None, role=role, is_premium=is_premium,
        terms_version=terms_version, terms_accepted_at=datetime(2026, 9, 1, tzinfo=UTC) if terms_version else None,
    )
```

- [ ] **Step 2: Tests qui échouent** — `tests/test_api_terms.py` :

```python
import pytest
from sqlalchemy import select

from app.models import SecurityEvent
from app.services.auth.accounts import TERMS_VERSION


@pytest.fixture
def outdated(db, user):
    user.terms_version = "2026-09-28"
    db.flush()
    return user


def test_me_says_when_terms_are_outdated(client, outdated):
    assert client.get("/api/me").json()["terms_outdated"] is True


def test_outdated_terms_block_personal_routes_but_not_account_routes(client, outdated):
    for method, path in [("GET", "/api/orders"), ("GET", "/api/favorites"), ("GET", "/api/settings"),
                         ("GET", "/api/assistant/status"), ("GET", "/api/portfolio")]:
        response = client.request(method, path)
        assert response.status_code == 403 and response.json()["detail"]["code"] == "terms_outdated", path
    for path in ["/api/me", "/api/me/sessions"]:
        assert client.get(path).status_code == 200, path


def test_accepting_updates_the_version_and_unblocks(client, db, outdated):
    refused = client.post("/api/me/accept-terms", json={"accept_terms": False})
    assert refused.status_code == 422
    body = client.post("/api/me/accept-terms", json={"accept_terms": True}).json()
    assert body["terms_outdated"] is False
    assert outdated.terms_version == TERMS_VERSION
    assert client.get("/api/orders").status_code == 200
    assert db.scalars(select(SecurityEvent.kind)).all() == ["terms_accepted"]


def test_admin_with_outdated_terms_is_blocked_too(admin_client, db):
    from app.models import User

    admin = db.scalars(select(User).where(User.role == "admin")).one()
    admin.terms_version = None
    db.flush()
    assert admin_client.get("/api/admin/users").json()["detail"]["code"] == "terms_outdated"
```

(Vérifier le chemin réel des routes d'ordres, favoris et portefeuille dans `app/api/routes/*.py` et l'adapter si besoin ; `GET /api/orders` doit répondre 200 pour un compte à jour.)

- [ ] **Step 3: Vérifier l'échec**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_terms.py`
Expected: FAIL (`terms_outdated` absent de `/api/me`, 200 au lieu de 403, 404 sur `/api/me/accept-terms`).

- [ ] **Step 4: Implémentation**

`app/services/auth/accounts.py` :

```python
TERMS_VERSION = "2026-10-01"  # date du texte des CGU en vigueur : la changer oblige chacun à les accepter à nouveau


def accept_terms(user: User, now: datetime) -> None:
    user.terms_accepted_at, user.terms_version = now, TERMS_VERSION
```

`app/core/current_user.py` :

```python
from app.services.auth.accounts import TERMS_VERSION

def get_account_user(user: User | None = Depends(get_optional_user)) -> User:
    """Routes du compte lui-même (profil, appareils, CGU, export, suppression) : sans vérifier les CGU."""
    if user is None:
        raise HTTPException(401, detail={"code": "not_authenticated", "message": "Connectez-vous pour accéder à cette page."})
    return user


def get_current_user(user: User = Depends(get_account_user)) -> User:
    """Pages privées : compte validé (toute session l'est) et CGU en vigueur acceptées (sinon 403 terms_outdated)."""
    if user.terms_version != TERMS_VERSION:
        raise HTTPException(403, detail={"code": "terms_outdated",
                                         "message": "Nos conditions d'utilisation ont changé : acceptez-les pour continuer."})
    return user
```

(Si l'import de `accounts` crée un cycle, déplacer `TERMS_VERSION` dans `app/core/terms.py` et l'importer depuis les deux.)

`MeOut` gagne `terms_outdated`, calculé par une propriété du modèle. Dans `app/models/user.py` :

```python
    @property
    def terms_outdated(self) -> bool:
        from app.services.auth.accounts import TERMS_VERSION
        return self.terms_version != TERMS_VERSION
```

et, dans `app/schemas/auth.py`, `terms_outdated: bool` ajouté à `MeOut` (lu par `from_attributes`).

`app/schemas/me.py` :

```python
class AcceptTermsIn(BaseModel):
    accept_terms: bool

    @field_validator("accept_terms")
    @classmethod
    def must_accept(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Acceptez les CGU et la politique de confidentialité pour continuer.")
        return value
```

`app/api/routes/me.py` : **toutes** les routes du fichier passent de `get_current_user` à `get_account_user`, puis :

```python
@router.post("/me/accept-terms", response_model=MeOut)
def accept_terms(payload: AcceptTermsIn, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_account_user), now: datetime = Depends(get_now)) -> MeOut:
    accounts.accept_terms(user, now)
    log_event(db, "terms_accepted", now=now, user_id=user.id, ip=client_ip(request), details={"version": user.terms_version})
    db.commit()
    return MeOut.model_validate(user)
```

`app/services/security_log.py` : ajouter `"terms_accepted", "account_deleted", "data_export"` à `EVENT_KINDS`.

- [ ] **Step 5: Vérifier** — `pytest -q tests/test_api_terms.py` puis toute la suite `pytest -q`. Expected: tout passe (les autres tests utilisent `make_user`, à jour). Si un test crée un `User(...)` à la main sans `terms_version` et appelle une route personnelle, lui ajouter `terms_version=TERMS_VERSION`.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: versioned terms, personal routes refuse outdated acceptance, accept-terms route"
```

---

### Task 2: Suppression du compte par son titulaire (C6) et anonymisation

**Files:**
- Create: `backend/app/services/privacy/__init__.py`, `backend/app/services/privacy/erasure.py`
- Modify: `backend/app/services/admin/users.py` (`delete_user` utilise `erase_account`), `backend/app/services/mail/outbox.py` (`forget_secrets`), `backend/app/api/routes/me.py`, `backend/app/schemas/me.py`
- Test: `backend/tests/test_api_account_deletion.py` (créé)

**Interfaces:**
- Consumes: `get_account_user`, `get_auth_session` (Task 1).
- Produces: `erasure.email_fingerprint(email: str) -> str` (`"supprimé:" + 16 premiers caractères de token_hash(email)`) ; `erasure.erase_account(db, user, *, now, actor: User | None = None, reason: str = "self") -> None` (journalise, anonymise `email_log`, retire les mails en attente, supprime, met C6 en file ; pas de commit) ; `DELETE /api/me` `{confirm_email, password?}` → 204 et cookies effacés ; codes `confirm_mismatch`, `wrong_password`, `reauth_required`, `last_admin`.

- [ ] **Step 1: Tests qui échouent** — `tests/test_api_account_deletion.py` :

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models import AiUsage, AuthSession, EmailLog, Favorite, Order, SecurityEvent, User
from app.services.auth.sessions import SESSION_COOKIE
from app.services.mail.outbox import enqueue, forget_secrets
from app.services.privacy.erasure import email_fingerprint
from tests.factories import make_security, make_user

PASSWORD = "motdepasse-solide"


def test_self_delete_needs_the_email_and_the_password(client, db, user):
    wrong_email = client.request("DELETE", "/api/me", json={"confirm_email": "autre@example.com", "password": PASSWORD})
    assert wrong_email.status_code == 400 and wrong_email.json()["detail"]["code"] == "confirm_mismatch"
    wrong_password = client.request("DELETE", "/api/me", json={"confirm_email": user.email, "password": "faux"})
    assert wrong_password.status_code == 400 and wrong_password.json()["detail"]["code"] == "wrong_password"
    assert db.get(User, user.id) is not None


def test_self_delete_erases_everything_and_anonymizes_logs(client, db, user):
    security = make_security(db)
    db.add_all([Favorite(user_id=user.id, security_id=security.id),
                AiUsage(user_id=user.id, month="2026-09", cost_usd=1.0)])
    enqueue(db, "welcome", to=user.email, user_id=user.id, context={"first_name": "Moi"})
    db.flush()
    user_id, email = user.id, user.email
    response = client.request("DELETE", "/api/me", json={"confirm_email": " MOI@example.com ", "password": PASSWORD})
    assert response.status_code == 204
    assert client.cookies.get(SESSION_COOKIE) is None
    db.expire_all()
    assert db.get(User, user_id) is None
    for model in (Favorite, AiUsage, AuthSession, Order):
        assert db.scalars(select(model).where(model.user_id == user_id)).all() == [], model
    logs = db.scalars(select(EmailLog)).all()
    assert [(m.kind, m.recipient) for m in logs] == [("account_deleted", email)]  # « welcome » en attente retiré
    event = db.scalars(select(SecurityEvent).where(SecurityEvent.kind == "account_deleted")).one()
    assert event.user_id is None and email not in str(event.details)
    forget_secrets(logs[0])  # une fois C6 envoyé, l'adresse disparaît aussi de sa ligne
    assert logs[0].recipient == email_fingerprint(email)


def test_sent_mails_keep_their_line_with_a_fingerprint(client, db, user):
    row_id = enqueue(db, "welcome", to=user.email, user_id=user.id, context={"first_name": "Moi"})
    db.get(EmailLog, row_id).status = "sent"
    db.flush()
    client.request("DELETE", "/api/me", json={"confirm_email": user.email, "password": PASSWORD})
    db.expire_all()
    row = db.get(EmailLog, row_id)
    assert row.user_id is None and row.recipient == email_fingerprint("moi@example.com")


def test_google_account_without_password_must_have_signed_in_recently(client, db, user):
    user.password_hash, user.google_sub = None, "google-1"
    db.flush()
    session = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).one()
    session.created_at = datetime.now(UTC) - timedelta(minutes=10)
    db.flush()
    stale = client.request("DELETE", "/api/me", json={"confirm_email": user.email})
    assert stale.status_code == 403 and stale.json()["detail"]["code"] == "reauth_required"
    session.created_at = datetime.now(UTC) - timedelta(minutes=2)
    db.flush()
    assert client.request("DELETE", "/api/me", json={"confirm_email": user.email}).status_code == 204


def test_last_admin_cannot_delete_itself(admin_client, db):
    admin = db.scalars(select(User).where(User.role == "admin")).one()
    response = admin_client.request("DELETE", "/api/me", json={"confirm_email": admin.email, "password": PASSWORD})
    assert response.status_code == 400 and response.json()["detail"]["code"] == "last_admin"


def test_admin_deletion_uses_the_same_erasure(admin_client, db):
    target = make_user(db, "p@example.com")
    enqueue(db, "welcome", to=target.email, user_id=target.id, context={"first_name": "P"})
    db.flush()
    admin_client.request("DELETE", f"/api/admin/users/{target.id}", json={"confirm_email": "p@example.com"})
    kinds = [m.kind for m in db.scalars(select(EmailLog))]
    assert kinds == ["account_deleted"]
```

(`make_security` existe dans `tests/factories.py` ; si sa signature diffère, l'adapter.)

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_api_account_deletion.py`. Expected: FAIL (`DELETE /api/me` 405, `app.services.privacy` introuvable).

- [ ] **Step 3: `erasure.py`**

```python
"""Suppression d'un compte (par son titulaire, par un admin ou pour inactivité), spec 6.4."""
from datetime import datetime

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.core.security import token_hash
from app.models import EmailLog, User
from app.services.mail.outbox import enqueue
from app.services.security_log import log_event


def email_fingerprint(email: str) -> str:
    """Remplace une adresse dans les journaux : permet de reconnaître une même adresse sans la révéler."""
    return f"supprimé:{token_hash(email.strip().lower())[:16]}"


def erase_account(db: Session, user: User, *, now: datetime, actor: User | None = None, reason: str = "self") -> None:
    """Supprime le compte et toutes ses données (ON DELETE CASCADE). Pas de commit ici.

    Le journal de sécurité et l'historique des mails gardent leurs lignes, sans lien ni adresse en clair.
    """
    email, first_name = user.email, user.first_name
    if actor is not None:
        log_event(db, "admin_user_deleted", now=now, user_id=user.id, actor_id=actor.id)
    else:
        log_event(db, "account_deleted", now=now, user_id=user.id, details={"reason": reason})
    db.execute(delete(EmailLog).where(EmailLog.user_id == user.id, EmailLog.status == "pending"))
    db.execute(update(EmailLog).where(EmailLog.user_id == user.id).values(recipient=email_fingerprint(email)))
    db.flush()
    db.delete(user)
    db.flush()
    enqueue(db, "account_deleted", to=email, user_id=None, context={"first_name": first_name})
```

`app/services/mail/outbox.py` : `forget_secrets` remplace aussi l'adresse de C6 une fois envoyé :

```python
def forget_secrets(row: EmailLog) -> None:
    if row.kind in SECRET_KINDS:
        row.subject = SUBJECTS[row.kind].split(" : {")[0]
        row.html = row.text = ERASED
    if row.kind == "account_deleted":  # le compte n'existe plus : son adresse ne reste pas en clair (spec 6.4)
        from app.services.privacy.erasure import email_fingerprint
        row.recipient = email_fingerprint(row.recipient)
```

`app/services/admin/users.py`, `delete_user` : après les deux contrôles existants, remplacer le corps par `erase_account(db, target, now=now, actor=actor)`.

- [ ] **Step 4: Route** — `app/schemas/me.py` :

```python
class DeleteAccountIn(BaseModel):
    confirm_email: str = Field(max_length=254)
    password: str | None = Field(default=None, max_length=200)
```

`app/api/routes/me.py` :

```python
REAUTH_WINDOW = timedelta(minutes=5)


@router.delete("/me", status_code=204)
def delete_account(payload: DeleteAccountIn, request: Request, response: Response, db: Session = Depends(get_db),
                   user: User = Depends(get_account_user), auth: AuthSession = Depends(get_auth_session),
                   now: datetime = Depends(get_now)) -> Response:
    if normalize_email(payload.confirm_email) != user.email:
        raise fail(400, "confirm_mismatch", "L'adresse retapée ne correspond pas à votre compte.")
    if user.has_password:
        if not profile.password_ok(user, payload.password):
            raise fail(400, *WRONG_PASSWORD)
    elif now - auth.created_at > REAUTH_WINDOW:
        raise fail(403, "reauth_required", "Reconnectez-vous avec Google, puis confirmez dans les 5 minutes.")
    if user.role == "admin" and db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) <= 1:
        raise fail(400, "last_admin", "Vous êtes le seul administrateur : nommez-en un autre avant de supprimer votre compte.")
    erase_account(db, user, now=now)
    db.commit()
    clear_auth_cookies(response, get_settings())
    response.status_code = 204
    return response
```

(Task 5 remplacera la vérification du mot de passe par `_check_current_password()`, limitée en essais.)

- [ ] **Step 5: Vérifier** — `pytest -q tests/test_api_account_deletion.py tests/test_api_admin_users.py`, puis `pytest -q`. Expected: tout passe (`test_delete_requires_the_email_and_removes_everything` de l'admin reste vert).

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: users can delete their account; erasure shared with admin deletion anonymizes logs"
```

---

### Task 3: Export des données (C7)

**Files:**
- Create: `backend/app/models/privacy.py`, `backend/alembic/versions/e6b8d0f2a4c6_data_exports.py`, `backend/app/services/privacy/export.py`, `backend/app/jobs/privacy.py`, `backend/app/services/mail/templates/data_export_ready.html`, `.txt`
- Modify: `backend/app/models/__init__.py`, `backend/app/services/mail/render.py` (`SUBJECTS`), `backend/app/api/routes/me.py`, `backend/app/schemas/me.py`, `backend/app/jobs/scheduler.py`
- Test: `backend/tests/test_privacy_export.py` (créé)

**Interfaces:**
- Consumes: `get_account_user` (Task 1).
- Produces: modèle `DataExport(id: UUID, user_id, status: "pending"|"ready", content: str | None, created_at, ready_at, expires_at)` ; `export.EXPORT_TTL = timedelta(days=7)` ; `export.request_export(db, user, now) -> DataExport` (lève `ExportRefused(code, message)`) ; `export.build_export(db, user, now) -> dict` ; `jobs.privacy.build_pending_exports(ctx) -> int` ; routes `POST /api/me/export` (202 `ExportOut`), `GET /api/me/export` (`ExportOut | null`), `GET /api/me/export/{id}` (fichier JSON) ; mail `data_export_ready`.

- [ ] **Step 1: Tests qui échouent** — `tests/test_privacy_export.py` :

```python
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.jobs.privacy import build_pending_exports
from app.models import Conversation, ChatMessage, DataExport, EmailLog, Order
from tests.factories import make_security, make_user
from tests.auth_helpers import sign_in


def _ready(client, make_ctx):
    created = client.post("/api/me/export")
    assert created.status_code == 202 and created.json()["status"] == "pending"
    assert build_pending_exports(make_ctx()) == 1
    return created.json()["id"]


def test_export_contains_the_personal_data_and_mails_a_link(client, db, user, make_ctx):
    security = make_security(db)
    db.add(Order(user_id=user.id, security_id=security.id, side="buy", quantity=2, unit_price=10.0, fees=1.0,
                 trade_date=datetime(2026, 9, 1).date()))
    conv = Conversation(user_id=user.id, title="Q")
    db.add(conv)
    db.flush()
    db.add(ChatMessage(conversation_id=conv.id, role="user", content="Bonjour"))
    db.flush()
    export_id = _ready(client, make_ctx)
    download = client.get(f"/api/me/export/{export_id}")
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    data = json.loads(download.content)
    assert data["profil"]["email"] == "moi@example.com" and "password_hash" not in data["profil"]
    assert data["ordres"][0]["quantity"] == 2 and data["ordres"][0]["titre"]["symbol"] == security.symbol
    assert data["conversations"][0]["messages"][0]["content"] == "Bonjour"
    for key in ("reglages", "favoris", "usage_assistant", "appareils"):
        assert key in data
    mail = db.scalars(select(EmailLog).where(EmailLog.kind == "data_export_ready")).one()
    assert "/reglages" in mail.text


def test_one_export_at_a_time_and_one_per_day(client, db, make_ctx):
    client.post("/api/me/export")
    again = client.post("/api/me/export")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "export_pending"
    build_pending_exports(make_ctx())
    tomorrow_not_yet = client.post("/api/me/export")
    assert tomorrow_not_yet.status_code == 429 and tomorrow_not_yet.json()["detail"]["code"] == "export_limit"
    latest = client.get("/api/me/export").json()
    assert latest["status"] == "ready" and latest["expires_at"] is not None


def test_export_download_is_owner_only_and_expires(client, anon_client, db, user, make_ctx):
    export_id = _ready(client, make_ctx)
    other = make_user(db, "autre@example.com")
    sign_in(anon_client, db, other)
    assert anon_client.get(f"/api/me/export/{export_id}").status_code == 404
    row = db.get(DataExport, export_id)
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()
    assert client.get(f"/api/me/export/{export_id}").status_code == 404


def test_pending_export_cannot_be_downloaded(client):
    export_id = client.post("/api/me/export").json()["id"]
    assert client.get(f"/api/me/export/{export_id}").status_code == 404


def test_latest_export_is_null_at_first(client):
    assert client.get("/api/me/export").json() is None
```

(Vérifier les noms des champs d'`Order` dans `app/models/portfolio.py` et les adapter dans le test ; `make_ctx()` utilise la même session `db`.)

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_privacy_export.py`. Expected: FAIL (`DataExport` introuvable).

- [ ] **Step 3: Modèle et migration**

`app/models/privacy.py` :

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DataExport(Base):
    """Export des données d'un compte (spec 6.4) : préparé par le worker, téléchargeable 7 jours, connecté."""

    __tablename__ = "data_exports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")  # pending | ready
    content: Mapped[str | None] = mapped_column(Text)  # JSON ; en base plutôt qu'en fichier (Ruling 4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
```

Ajouter `DataExport` à `app/models/__init__.py` (import et `__all__`).

`alembic/versions/e6b8d0f2a4c6_data_exports.py` : `revision = "e6b8d0f2a4c6"`, `down_revision = "d4f6a8c0e2b4"` ; `upgrade()` crée la table (mêmes colonnes, index `ix_data_exports_user_id` et `ix_data_exports_expires_at`) ; `downgrade()` la supprime.

- [ ] **Step 4: Migration sur base jetable**

```bash
docker compose exec -T db psql -U pea -d postgres -c "DROP DATABASE IF EXISTS pea_migr" -c "CREATE DATABASE pea_migr"
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T -e DATABASE_URL=postgresql+psycopg://pea:pea@db:5432/pea_migr api sh -c "alembic upgrade head && alembic downgrade -1 && alembic upgrade head"
docker compose exec -T db psql -U pea -d postgres -c "DROP DATABASE pea_migr"
```

Expected: les trois commandes Alembic réussissent.

- [ ] **Step 5: Service** — `app/services/privacy/export.py` :

```python
"""Export des données personnelles (spec 6.4 : accès et portabilité)."""
from datetime import date, datetime, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models import AiUsage, AuthSession, ChatMessage, Conversation, DataExport, Favorite, Order, Security, User, UserSettings

EXPORT_TTL = timedelta(days=7)
ONE_PER = timedelta(days=1)
HIDDEN = {"password_hash", "token_hash", "csrf_token", "user_id"}  # jamais exportés (secrets, ou redondants)


class ExportRefused(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value) if isinstance(value, uuid.UUID) else float(value)
    return value


def _row(obj) -> dict:
    return {c.key: _plain(getattr(obj, c.key)) for c in inspect(obj).mapper.column_attrs if c.key not in HIDDEN}


def build_export(db: Session, user: User, now: datetime) -> dict:
    securities = {s.id: {"symbol": s.symbol, "name": s.name, "isin": s.isin} for s in db.scalars(
        select(Security).where(Security.id.in_(
            select(Order.security_id).where(Order.user_id == user.id).union(
                select(Favorite.security_id).where(Favorite.user_id == user.id)))))}
    settings = db.get(UserSettings, user.id)
    conversations = db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.id)).all()
    return {
        "genere_le": now.isoformat(),
        "profil": _row(user),
        "reglages": _row(settings) if settings else None,
        "ordres": [{**_row(o), "titre": securities.get(o.security_id)} for o in
                   db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.id))],
        "favoris": [{**_row(f), "titre": securities.get(f.security_id)} for f in
                    db.scalars(select(Favorite).where(Favorite.user_id == user.id))],
        "conversations": [{**_row(c), "messages": [_row(m) for m in db.scalars(
            select(ChatMessage).where(ChatMessage.conversation_id == c.id).order_by(ChatMessage.id))]} for c in conversations],
        "usage_assistant": [_row(u) for u in db.scalars(select(AiUsage).where(AiUsage.user_id == user.id))],
        "appareils": [_row(s) for s in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id))],
    }


def latest_export(db: Session, user: User) -> DataExport | None:
    return db.scalar(select(DataExport).where(DataExport.user_id == user.id).order_by(DataExport.created_at.desc()).limit(1))


def request_export(db: Session, user: User, now: datetime) -> DataExport:
    """Un export à la fois, au plus un par jour (spec 6.4)."""
    last = latest_export(db, user)
    if last is not None and last.status == "pending":
        raise ExportRefused(409, "export_pending", "Votre export est déjà en préparation : vous recevrez un mail.")
    if last is not None and last.created_at > now - ONE_PER:
        raise ExportRefused(429, "export_limit", "Un export par jour au plus : réessayez demain.")
    row = DataExport(user_id=user.id, created_at=now)
    db.add(row)
    db.flush()
    return row
```

(Vérifier que `Security` a bien `symbol`, `name`, `isin` ; sinon garder les colonnes existantes.)

`app/jobs/privacy.py` :

```python
import json

from sqlalchemy import select

from app.jobs.context import JobContext
from app.models import DataExport, User
from app.services.mail.outbox import enqueue
from app.services.privacy.export import EXPORT_TTL, build_export


def build_pending_exports(ctx: JobContext) -> int:
    """Toutes les 15 s : prépare les exports demandés, puis prévient par mail (C7)."""
    now, done = ctx.now(), 0
    with ctx.session_factory() as db:
        for row in db.scalars(select(DataExport).where(DataExport.status == "pending").with_for_update(skip_locked=True)).all():
            user = db.get(User, row.user_id)
            row.content = json.dumps(build_export(db, user, now), ensure_ascii=False, indent=2)
            row.status, row.ready_at, row.expires_at = "ready", now, now + EXPORT_TTL
            enqueue(db, "data_export_ready", to=user.email, user_id=user.id,
                    context={"first_name": user.first_name, "expires_at": row.expires_at})
            done += 1
        db.commit()
    return done
```

`app/jobs/scheduler.py` : fonction `exports_job(ctx)` calquée sur `mail_job` (try/except + log), ajoutée avec `IntervalTrigger(seconds=15, timezone=tz)`, `id="exports"`, `**common`, **hors** du `if ctx.mailer`.

Mail : `SUBJECTS["data_export_ready"] = "Vos données PEA Radar sont prêtes"`. `data_export_ready.html` :

```html
{% extends "_layout.html" %}
{% block body %}
<p>L'export de vos données PEA Radar est prêt.</p>
<p><a href="{{ base_url }}/reglages#mes-donnees">Le télécharger depuis vos réglages</a> (connexion requise). Il reste disponible jusqu'au {{ expires_at | paris }}.</p>
<p>Si vous n'avez pas demandé cet export, changez votre mot de passe.</p>
{% endblock %}
```

`data_export_ready.txt` : même texte (salutation `Bonjour {{ first_name }},`, lien en clair `{{ base_url }}/reglages#mes-donnees`, puis `{% include "_footer.txt" %}`), sur le modèle de `account_deleted.txt`.

- [ ] **Step 6: Routes** — `app/schemas/me.py` :

```python
class ExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
    created_at: datetime
    expires_at: datetime | None
```

`app/api/routes/me.py` :

```python
@router.post("/me/export", response_model=ExportOut, status_code=202)
def request_data_export(request: Request, db: Session = Depends(get_db), user: User = Depends(get_account_user),
                        now: datetime = Depends(get_now)) -> ExportOut:
    try:
        row = export.request_export(db, user, now)
    except export.ExportRefused as refused:
        raise fail(refused.status, refused.code, refused.message)
    log_event(db, "data_export", now=now, user_id=user.id, ip=client_ip(request))
    db.commit()
    return ExportOut.model_validate(row)


@router.get("/me/export", response_model=ExportOut | None)
def latest_data_export(db: Session = Depends(get_db), user: User = Depends(get_account_user)) -> ExportOut | None:
    row = export.latest_export(db, user)
    return ExportOut.model_validate(row) if row else None


@router.get("/me/export/{export_id}")
def download_data_export(export_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_account_user),
                         now: datetime = Depends(get_now)) -> Response:
    row = db.get(DataExport, export_id)
    if row is None or row.user_id != user.id or row.status != "ready" or row.expires_at <= now:
        raise fail(404, "not_found", "Export introuvable ou expiré : demandez-en un nouveau.")
    name = f"pea-radar-mes-donnees-{row.ready_at:%Y-%m-%d}.json"
    return Response(row.content, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})
```

- [ ] **Step 7: Vérifier** — `pytest -q tests/test_privacy_export.py tests/test_mail_render.py` (le test de rendu parcourt `KINDS` : ajouter un contexte pour `data_export_ready` s'il en exige un), puis `pytest -q`. Expected: tout passe.

- [ ] **Step 8: Commit**

```bash
git add backend
git commit -m "feat: personal data export prepared by the worker, downloadable for 7 days (C7)"
```

---

### Task 4: Durées de conservation et inactivité (C8)

**Files:**
- Create: `backend/app/services/privacy/retention.py`, `backend/app/services/mail/templates/inactivity_warning.html`, `.txt`
- Modify: `backend/app/jobs/cleanup.py`, `backend/app/services/auth/sessions.py` (`resolve_session` touche aussi `users.last_seen_at`), `backend/app/services/mail/render.py`
- Test: `backend/tests/test_privacy_retention.py` (créé)

**Interfaces:**
- Consumes: `erase_account()` (Task 2), `DataExport` (Task 3).
- Produces: `retention.run_retention(db, now) -> dict[str, int]` (clés `unverified`, `sessions`, `codes`, `exports`, `email_log`, `warned`, `inactive_deleted`) ; constantes `UNVERIFIED_TTL = 7 jours`, `EMAIL_LOG_TTL = 90 jours`, `INACTIVITY = 3 × 365 jours`, `INACTIVITY_GRACE = 30 jours` ; mail `inactivity_warning`.

- [ ] **Step 1: Tests qui échouent** — `tests/test_privacy_retention.py` :

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models import AuthSession, DataExport, EmailCode, EmailLog, User
from app.services.auth.sessions import open_session, resolve_session
from app.services.privacy.retention import run_retention
from tests.factories import make_user

NOW = datetime(2029, 12, 1, 3, 30, tzinfo=UTC)


def _age(user, days):
    user.created_at = NOW - timedelta(days=days)
    user.last_login_at = user.last_seen_at = None


def test_unverified_accounts_go_after_7_days(db):
    old = make_user(db, "vieux@example.com", verified=False)
    new = make_user(db, "neuf@example.com", verified=False)
    _age(old, 8), _age(new, 2)
    db.flush()
    assert run_retention(db, NOW)["unverified"] == 1
    assert db.get(User, new.id) is not None and db.get(User, old.id) is None


def test_expired_sessions_codes_exports_and_old_mails_go(db):
    user = make_user(db)
    session = open_session(db, user, persistent=False, ip=None, user_agent="x", now=NOW - timedelta(days=2),
                           settings=get_settings()).session
    db.add_all([EmailCode(user_id=user.id, purpose="verify_email", code_hash="h", expires_at=NOW - timedelta(hours=1)),
                DataExport(user_id=user.id, status="ready", content="{}", expires_at=NOW - timedelta(hours=1)),
                EmailLog(kind="welcome", recipient="a@b.c", subject="s", html="h", text="t", status="sent",
                         created_at=NOW - timedelta(days=91)),
                EmailLog(kind="welcome", recipient="a@b.c", subject="s", html="h", text="t", status="sent",
                         created_at=NOW - timedelta(days=10))])
    db.flush()
    counts = run_retention(db, NOW)
    assert (counts["sessions"], counts["codes"], counts["exports"], counts["email_log"]) == (1, 1, 1, 1)
    assert db.get(AuthSession, session.id) is None


def test_three_years_without_login_warns_then_deletes_30_days_later(db):
    user = make_user(db, "dormeur@example.com")
    _age(user, 3 * 365 + 1)
    db.flush()
    assert run_retention(db, NOW)["warned"] == 1
    assert user.inactivity_warned_at == NOW
    warning = db.scalars(select(EmailLog).where(EmailLog.kind == "inactivity_warning")).one()
    assert "31/12/2029" in warning.text  # date de suppression annoncée (NOW + 30 jours)
    assert run_retention(db, NOW + timedelta(days=29))["inactive_deleted"] == 0
    assert run_retention(db, NOW + timedelta(days=31))["inactive_deleted"] == 1
    assert db.scalars(select(User).where(User.email == "dormeur@example.com")).first() is None
    assert db.scalars(select(EmailLog).where(EmailLog.kind == "account_deleted")).one()


def test_inactivity_never_deletes_admins_or_accounts_back_in_use(db):
    admin = make_user(db, "admin@example.com", role="admin")
    back = make_user(db, "revenu@example.com")
    _age(admin, 4 * 365), _age(back, 4 * 365)
    db.flush()
    counts = run_retention(db, NOW)
    assert counts["warned"] == 1 and admin.inactivity_warned_at is None
    back.last_login_at = NOW + timedelta(days=5)  # reconnecté après le C8
    db.flush()
    assert run_retention(db, NOW + timedelta(days=40))["inactive_deleted"] == 0
    assert db.get(User, back.id) is not None and back.inactivity_warned_at is None


def test_using_a_remembered_session_counts_as_activity(db):
    user = make_user(db)
    new = open_session(db, user, persistent=True, ip=None, user_agent="x", now=NOW - timedelta(days=1), settings=get_settings())
    resolve_session(db, new.token, now=NOW, settings=get_settings())
    assert user.last_seen_at == NOW
```

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_privacy_retention.py`. Expected: FAIL (`app.services.privacy.retention` introuvable).

- [ ] **Step 3: Implémentation** — `app/services/privacy/retention.py` :

```python
"""Durées de conservation (spec 6.5), appliquées chaque nuit par la tâche « cleanup »."""
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AuthSession, DataExport, EmailCode, EmailLog, User
from app.services.mail.outbox import enqueue
from app.services.privacy.erasure import erase_account

UNVERIFIED_TTL = timedelta(days=7)
EMAIL_LOG_TTL = timedelta(days=90)
INACTIVITY = timedelta(days=3 * 365)
INACTIVITY_GRACE = timedelta(days=30)


def _activity():
    """Dernier signe de vie : création, connexion, ou usage d'une session « rester connecté »."""
    return func.greatest(User.created_at, func.coalesce(User.last_login_at, User.created_at),
                         func.coalesce(User.last_seen_at, User.created_at))


def run_retention(db: Session, now: datetime) -> dict[str, int]:
    counts = {
        "unverified": db.execute(delete(User).where(User.email_verified_at.is_(None), User.role != "admin",
                                                    User.created_at < now - UNVERIFIED_TTL)).rowcount,
        "sessions": db.execute(delete(AuthSession).where(AuthSession.expires_at < now)).rowcount,
        "codes": db.execute(delete(EmailCode).where(EmailCode.expires_at < now)).rowcount,
        "exports": db.execute(delete(DataExport).where(DataExport.expires_at < now)).rowcount,
        "email_log": db.execute(delete(EmailLog).where(EmailLog.created_at < now - EMAIL_LOG_TTL,
                                                       EmailLog.status != "pending")).rowcount,
    }
    counts |= _inactivity(db, now)
    return counts


def _inactivity(db: Session, now: datetime) -> dict[str, int]:
    active = _activity()
    members = select(User).where(User.role != "admin", User.email_verified_at.is_not(None))
    # Revenu après l'avertissement : on oublie l'avertissement.
    for user in db.scalars(members.where(User.inactivity_warned_at.is_not(None), active > User.inactivity_warned_at)):
        user.inactivity_warned_at = None
    warned = 0
    for user in db.scalars(members.where(User.inactivity_warned_at.is_(None), active < now - INACTIVITY)):
        user.inactivity_warned_at = now
        enqueue(db, "inactivity_warning", to=user.email, user_id=user.id,
                context={"first_name": user.first_name, "delete_on": now + INACTIVITY_GRACE})
        warned += 1
    deleted = 0
    for user in db.scalars(members.where(User.inactivity_warned_at < now - INACTIVITY_GRACE,
                                         active <= User.inactivity_warned_at)).all():
        erase_account(db, user, now=now, reason="inactivity")
        deleted += 1
    db.flush()
    return {"warned": warned, "inactive_deleted": deleted}
```

`app/jobs/cleanup.py` :

```python
def purge_security_data(ctx: JobContext) -> int:
    """Chaque nuit : durées de conservation (spec 6.5), journal de plus de 12 mois, compteurs de plus d'un jour."""
    now = ctx.now()
    with ctx.session_factory() as db:
        removed = sum(run_retention(db, now).values()) + purge_events(db, now) + purge_hits(db, now)
        db.commit()
    return removed
```

`app/services/auth/sessions.py`, dans `resolve_session`, au moment où `row.last_seen_at` est touché :

```python
        db.execute(update(User).where(User.id == row.user_id).values(last_seen_at=now))  # inactivité (spec 6.5)
```

Mail : `SUBJECTS["inactivity_warning"] = "Votre compte PEA Radar sera supprimé dans 30 jours"`. `inactivity_warning.html` :

```html
{% extends "_layout.html" %}
{% block body %}
<p>Vous ne vous êtes pas connecté à PEA Radar depuis 3 ans. Sans nouvelle connexion, votre compte et ses données seront supprimés le {{ delete_on | paris }}.</p>
<p><a href="{{ base_url }}/connexion">Me connecter pour garder mon compte</a></p>
<p>Si vous ne souhaitez plus utiliser PEA Radar, vous n'avez rien à faire.</p>
{% endblock %}
```

`.txt` sur le même modèle. Le test attend « 31/12/2029 » : le filtre `paris` rend `%d/%m/%Y à %H:%M`.

- [ ] **Step 4: Vérifier** — `pytest -q tests/test_privacy_retention.py`, puis `pytest -q`. Expected: tout passe.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: nightly retention (unverified, expired, 90-day mail log) and 3-year inactivity warning then deletion (C8)"
```

**Fin du Bloc 1 : s'arrêter pour que l'utilisateur compacte.**

---

# Bloc 2 — Correctifs de sécurité reportés (Tasks 5 et 6)

### Task 5: Mot de passe actuel, changement d'adresse, admin

**Files:**
- Modify: `backend/app/services/ratelimit.py`, `backend/app/api/routes/me.py`, `backend/app/services/auth/profile.py`, `backend/app/services/auth/codes.py`, `backend/app/services/admin/users.py`, `backend/app/api/routes/admin.py`
- Test: `backend/tests/test_api_profile.py`, `backend/tests/test_api_admin_users.py`

**Interfaces:**
- Produces: `ratelimit.LIMITS["password_check"] = (10, FIFTEEN_MINUTES)` (clé : identifiant du compte) ; `me._check_current_password(db, user, password, now) -> None` (429 `too_many_requests` ou 400 `wrong_password`) ; `codes.cancel_codes(db, user_id, purposes, now) -> None` ; `profile.email_in_use(db, email) -> bool`.

- [ ] **Step 1: Tests qui échouent** — ajouter à `tests/test_api_profile.py` :

```python
def test_current_password_guesses_are_limited(client, db, user):
    for _ in range(10):
        client.post("/api/me/password", json={"current_password": "faux", "new_password": NEW})
    for call in (lambda p: client.post("/api/me/password", json={"current_password": p, "new_password": NEW}),
                 lambda p: client.post("/api/me/email", json={"new_email": "n@example.com", "password": p}),
                 lambda p: client.request("DELETE", "/api/me", json={"confirm_email": user.email, "password": p})):
        response = call(PASSWORD)  # même le bon mot de passe est refusé pendant 15 min
        assert response.status_code == 429 and response.json()["detail"]["code"] == "too_many_requests"


def test_email_change_code_is_not_resent_within_60_seconds(client, db, user):
    client.post("/api/me/email", json={"new_email": "nouveau@example.com", "password": PASSWORD})
    client.post("/api/me/email", json={"new_email": "nouveau@example.com", "password": PASSWORD})
    assert len(mails(db, "verify_code")) == 1


def test_email_change_cancels_pending_reset_links(client, db, user):
    reset = issue_code(db, user, "reset_password", NOW)
    code = issue_code(db, user, "change_email", NOW, new_email="nouveau@example.com")
    client.post("/api/me/email/verify", json={"code": code})
    assert client.post("/api/auth/reset-password", json={"token": reset, "password": NEW}).status_code == 400


def test_email_taken_at_commit_time_is_a_409_not_a_500(client, db, user, monkeypatch):
    from app.services.auth import profile

    code = issue_code(db, user, "change_email", NOW, new_email="course@example.com")
    make_user(db, "course@example.com")
    monkeypatch.setattr(profile, "email_in_use", lambda db, email: False)  # la vérification passe, la base refuse
    response = client.post("/api/me/email/verify", json={"code": code})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "email_taken"
```

(Vérifier le nom de la route de réinitialisation et de son corps dans `app/api/routes/auth.py` : `/auth/reset-password` `{token, password}` ; `issue_code(db, user, "reset_password", now)` renvoie le jeton du lien.)

Ajouter à `tests/test_api_admin_users.py` :

```python
def test_search_treats_percent_and_underscore_literally(admin_client, db):
    make_user(db, "paul@example.com")
    assert admin_client.get("/api/admin/users", params={"q": "%"}).json()["total"] == 0
    assert admin_client.get("/api/admin/users", params={"q": "_"}).json()["total"] == 0


def test_admin_email_change_cancels_reset_links(admin_client, db):
    from app.services.auth.codes import issue_code

    user = make_user(db, "p@example.com")
    token = issue_code(db, user, "reset_password", datetime.now(UTC))
    admin_client.patch(f"/api/admin/users/{user.id}", json={"email": "q@example.com"})
    assert admin_client.post("/api/auth/reset-password", json={"token": token, "password": "un-mot-de-passe-long"}).status_code == 400
```

- [ ] **Step 2: Vérifier l'échec** — `pytest -q tests/test_api_profile.py tests/test_api_admin_users.py`. Expected: les 6 nouveaux tests échouent.

- [ ] **Step 3: Implémentation**

`ratelimit.LIMITS` : `"password_check": (10, FIFTEEN_MINUTES),  # mots de passe actuels faux par compte (réglages, suppression)`.

`app/api/routes/me.py` :

```python
def _check_current_password(db: Session, user: User, password: str | None, now: datetime) -> None:
    """Mot de passe actuel, limité à 10 essais faux par 15 min : une session volée ne permet pas de le deviner."""
    key = str(user.id)
    if ratelimit.over(db, "password_check", key, now):
        raise fail(429, *TOO_MANY)
    if not profile.password_ok(user, password):
        ratelimit.record(db, "password_check", key, now)
        db.commit()
        raise fail(400, *WRONG_PASSWORD)
```

Remplacer les trois `if not profile.password_ok(...)` de `/me/password`, `/me/email` et `DELETE /me` par cet appel (`TOO_MANY` et `ratelimit` importés de `auth.py` / `app.services`). Pour `DELETE /me`, l'appel reste dans la branche `if user.has_password`.

`app/services/auth/codes.py` :

```python
def cancel_codes(db: Session, user_id: uuid.UUID, purposes: tuple[str, ...], now: datetime) -> None:
    """Rend inutilisables les codes et liens encore valables (ex. lien de réinitialisation envoyé à l'ancienne adresse)."""
    db.execute(update(EmailCode).where(EmailCode.user_id == user_id, EmailCode.purpose.in_(purposes),
                                       EmailCode.used_at.is_(None)).values(used_at=now))
```

`app/services/auth/profile.py` :

```python
RESEND_DELAY = timedelta(seconds=60)
LINKS_TO_OLD_ADDRESS = ("reset_password", "not_me")


def email_in_use(db: Session, email: str) -> bool:
    return db.scalar(select(User.id).where(User.email == email)) is not None
```

- `request_email_change` : utilise `email_in_use`, et ne fait rien si un code `change_email` non utilisé a été créé il y a moins de `RESEND_DELAY` (`EmailCode.created_at > now - RESEND_DELAY`).
- `confirm_email_change` : utilise `email_in_use`, puis appelle `cancel_codes(db, user.id, LINKS_TO_OLD_ADDRESS, now)` après le changement d'adresse.

Route `/me/email/verify` et `PATCH /api/admin/users/{id}` : entourer le `db.commit()` final de

```python
    try:
        db.commit()
    except IntegrityError:  # adresse prise entre la vérification et l'écriture
        db.rollback()
        raise fail(409, "email_taken", "Cette adresse vient d'être prise par un autre compte.")
```

`app/services/admin/users.py` :
- `_admin_count` : `len(db.scalars(select(User.id).where(User.role == "admin").with_for_update()).all())` — verrouille les lignes admin : deux admins qui se retirent le rôle en même temps ne peuvent pas tous deux passer.
- `update_user`, quand l'adresse change : `cancel_codes(db, target.id, LINKS_TO_OLD_ADDRESS, now)`.
- `list_users` : échapper la recherche avant le `like` :

```python
def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
```

et passer `escape="\\"` à chaque `.like(...)`.

- [ ] **Step 4: Vérifier** — `pytest -q tests/test_api_profile.py tests/test_api_admin_users.py`, puis `pytest -q`. Expected: tout passe.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "fix: limit current-password guesses, 60 s between email-change codes, cancel old reset links, 409 on email race, literal admin search"
```

---

### Task 6: Restes de l'étape 2 (Google et Turnstile)

**Files:**
- Modify: `backend/app/api/routes/google.py`, `backend/app/schemas/auth.py` (`GooglePendingOut`), `backend/app/api/deps.py` (`get_captcha`), `frontend/src/features/auth/FinishSignUpPage.tsx`
- Test: `backend/tests/test_api_google.py`, `backend/tests/test_captcha_config.py` (créé), `frontend/src/features/auth/FinishSignUpPage.test.tsx`

**Interfaces:**
- Produces: `GooglePendingOut.suite: str` ; `get_captcha()` renvoie `DisabledCaptcha` si l'une des deux clés Turnstile manque.

- [ ] **Step 1: Tests qui échouent**

`tests/test_api_google.py` : dans `test_new_google_account_is_created_only_after_finishing`, l'égalité de `pending` devient

```python
    assert anon_client.get("/api/auth/google/pending").json() == {"email": "jean@gmail.com", "first_name": "Jean",
                                                                   "last_name": "Dupont", "suite": "/portefeuille"}
```

et ajouter :

```python
def test_google_sign_in_replaces_the_previous_session(anon_client, db):
    from tests.auth_helpers import sign_in

    user = make_user(db, "jean@gmail.com")
    user.google_sub = "google-123"
    old = sign_in(anon_client, db, user)
    _callback(anon_client, _start(anon_client))
    assert db.get(type(old.session), old.session.id) is None
```

`tests/test_captcha_config.py` :

```python
from app.api.deps import get_captcha
from app.core.config import get_settings
from app.services.auth.captcha import DisabledCaptcha, TurnstileVerifier


def test_turnstile_needs_both_keys(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")
    monkeypatch.setattr(settings, "turnstile_site_key", "")
    assert isinstance(get_captcha(), DisabledCaptcha)  # sans widget, exiger un jeton bloquerait la connexion
    monkeypatch.setattr(settings, "turnstile_site_key", "site")
    assert isinstance(get_captcha(), TurnstileVerifier)
```

`frontend/src/features/auth/FinishSignUpPage.test.tsx` (créé, sur le modèle des autres tests de `features/auth`) :

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { FinishSignUpPage } from "./FinishSignUpPage";

afterEach(() => vi.unstubAllGlobals());

test("après l'inscription Google, retour à la page demandée au départ", async () => {
  mockFetch((url) => (url === "/api/auth/google/pending"
    ? { body: { email: "jean@gmail.com", first_name: "Jean", last_name: "Dupont", suite: "/portefeuille" } }
    : url === "/api/auth/google/complete" ? { body: ME } : { body: {} }));
  const { router } = renderWithProviders(<FinishSignUpPage />, { route: "/finaliser-inscription" });
  await userEvent.click(await screen.findByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: /Créer mon compte|Terminer/ }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/portefeuille"));
});
```

(Si `renderWithProviders` ne renvoie pas le routeur, vérifier la navigation par un élément de la route cible, comme dans `AuthPage.test.tsx`.)

- [ ] **Step 2: Vérifier l'échec** — backend `pytest -q tests/test_api_google.py tests/test_captcha_config.py`, frontend `npx vitest --run src/features/auth/FinishSignUpPage.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Implémentation**
- `google.py`, callback : le cookie « en attente » signé contient aussi `"suite": flow["suite"]` ; dans la branche « compte connu », avant `start_session`, révoquer la session précédente comme `login()` :

```python
        previous = resolve_session(db, request.cookies.get(SESSION_COOKIE), now=now, settings=get_settings())
        if previous is not None:
            revoke_session(db, previous.id)  # jamais deux sessions pour le même cookie
```

- `pending()` renvoie `suite=data.get("suite", "/")` ; `GooglePendingOut` gagne `suite: str = "/"`.
- `deps.get_captcha` : `TurnstileVerifier(secret) if secret and settings.turnstile_site_key else DisabledCaptcha()`, docstring « les deux clés, sinon désactivé : un captcha exigé sans widget bloquerait la connexion ».
- `FinishSignUpPage.tsx` : type `Pending` gagne `suite: string` ; `onSuccess` : `const suite = safeNext(pending.suite); if (isExternalSuite(suite)) window.location.assign(suite); else navigate(suite, { replace: true });`.
- `npm run gen:api` (API de dev lancée) pour régénérer `schema.d.ts`.

- [ ] **Step 4: Vérifier** — `pytest -q` et `cd frontend && npx vitest --run && npx tsc -b`. Expected: tout passe.

- [ ] **Step 5: Commit**

```bash
git add backend frontend
git commit -m "fix: Google sign-in replaces the previous session and keeps the requested page; Turnstile needs both keys"
```

**Fin du Bloc 2 : s'arrêter pour que l'utilisateur compacte.**

---

# Bloc 3 — Frontend (Tasks 7 à 9)

### Task 7: Pages légales complètes

**Files:**
- Modify: `frontend/src/features/legal/LegalPage.tsx`
- Create: `frontend/src/features/legal/content.tsx`, `frontend/src/features/legal/LegalPage.test.tsx`
- Modify: `frontend/src/features/assistant/ChatView.tsx` (rappel Anthropic)

**Interfaces:**
- Produces: `LEGAL_UPDATED = "1er octobre 2026"` ; `LegalPage({ kind })` inchangé pour le routeur.

- [ ] **Step 1: Test qui échoue** — `LegalPage.test.tsx` :

```tsx
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { LegalPage } from "./LegalPage";

test.each([
  ["cgu", "Conditions générales d'utilisation", [/18 ans/, /pas un conseil en investissement/i, /Assistant IA/]],
  ["confidentialite", "Politique de confidentialité", [/Anthropic/, /Brevo/, /Cloudflare/, /3 ans/, /Exporter mes données/]],
  ["mentions-legales", "Mentions légales", [/Éditeur/, /Hébergeur/]],
] as const)("%s : texte complet, sections attendues", (kind, title, patterns) => {
  renderWithProviders(<LegalPage kind={kind} />);
  expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
  expect(screen.queryByText(/Version provisoire/)).toBeNull();
  for (const pattern of patterns) expect(screen.getAllByText(pattern).length).toBeGreaterThan(0);
  expect(screen.getByText(/Dernière mise à jour : 1er octobre 2026/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Vérifier l'échec** — `npx vitest --run src/features/legal`. Expected: FAIL (« Version provisoire » présent).

- [ ] **Step 3: Contenu** — `content.tsx` exporte `CGU`, `PRIVACY`, `NOTICE` : des composants qui rendent des `<section>` avec `<h2>` et paragraphes/listes, en français simple. Texte à écrire intégralement, avec au minimum :

**CGU** (`h2`) : 1. Objet (PEA Radar, outil gratuit d'aide à la décision et d'apprentissage pour le PEA) · 2. Accès (réservé aux **18 ans et plus** ; pages publiques sans compte) · 3. Compte et sécurité (exactitude des informations, mot de passe personnel, « Ce n'était pas moi ») · 4. **Pas un conseil en investissement** (données différées, éligibilité PEA déduite, scores et prévisions sans garantie ; vérifier auprès de sa banque ; aucune recommandation personnalisée au sens de l'AMF) · 5. Assistant IA (réservé Premium, réponses générées par Claude d'Anthropic, pouvant être fausses, limite mensuelle) · 6. Premium (activé par l'administrateur ; l'abonnement payant fera l'objet de CGV) · 7. Suspension et suppression (par l'utilisateur à tout moment dans les Réglages ; par l'éditeur en cas d'abus ; inactivité 3 ans) · 8. Responsabilité (limitée, pas de garantie de disponibilité) · 9. Modification des CGU (nouvelle acceptation demandée) · 10. Droit applicable (droit français ; tribunaux de `[À COMPLÉTER : ville]`) · Contact `[À COMPLÉTER : adresse de contact]`.

**Confidentialité** : Responsable du traitement `[À COMPLÉTER : nom ou société, adresse]` · Données collectées (compte : prénom, nom, mail, mot de passe haché ; données saisies : ordres, favoris, réglages, conversations avec l'assistant ; techniques : appareils connectés, IP tronquée, journal de sécurité, historique des mails) · Finalités et bases légales (tableau : fournir le service → contrat ; sécurité et prévention des abus → intérêt légitime ; mails de compte → contrat) · Durées (tableau reprenant la spec 6.5 : compte jusqu'à suppression ou **3 ans** d'inactivité avec prévenance de 30 jours ; comptes non validés 7 jours ; export 7 jours ; historique des mails 90 jours ; journal de sécurité 12 mois) · Sous-traitants (hébergeur `[À COMPLÉTER]`, **Brevo** mails, **Google** connexion Google pour ceux qui l'utilisent, **Cloudflare** Turnstile, **Anthropic** assistant IA, aux **États-Unis**) · Transferts hors UE (Anthropic, Google, Cloudflare : clauses contractuelles types / cadre UE–États-Unis `[À VÉRIFIER]`) · Vos droits (accès et portabilité : bouton **Exporter mes données** ; rectification : Réglages ; effacement : **Supprimer mon compte** ; opposition ; réclamation auprès de la CNIL) · Cookies (uniquement `pea_session`, `pea_csrf`, `pea_device` et Turnstile, strictement nécessaires : pas de bandeau ; pas de publicité ni de mesure d'audience).

**Mentions légales** : Éditeur `[À COMPLÉTER : nom, statut, SIRET éventuel, adresse, contact]` · Directeur de la publication `[À COMPLÉTER]` · Hébergeur `[À COMPLÉTER : nom, adresse, téléphone]` · Propriété intellectuelle · Données de marché (sources : Yahoo Finance et Euronext, cours différés, sans garantie).

Chaque page commence par « Dernière mise à jour : 1er octobre 2026 » et un encadré (`role="note"`) : « Brouillon : les passages entre crochets restent à compléter, et une relecture par un professionnel est conseillée avant l'ouverture publique. » (supprimé par l'utilisateur quand les textes sont validés).

`LegalPage.tsx` : garde `PAGES` et `usePageMeta` (publiques, indexables), retire « Version provisoire », rend `<CGU />`, `<PRIVACY />` ou `<NOTICE />` dans `<article className="max-w-3xl space-y-6">` avec des styles lisibles (`prose`-like : `h2` `text-lg font-semibold`, listes `list-disc pl-5`).

`ChatView.tsx` : sous la ligne « Modèle : … », ajouter « Vos questions sont envoyées à Anthropic (États-Unis) pour y répondre. » avec un lien « En savoir plus » vers `/confidentialite`.

- [ ] **Step 4: Vérifier** — `npx vitest --run src/features/legal src/features/assistant`. Expected: tout passe.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/legal frontend/src/features/assistant
git commit -m "feat: full draft terms, privacy policy and legal notice"
```

---

### Task 8: Écran `/accepter-cgu`

**Files:**
- Create: `frontend/src/features/auth/AcceptTermsPage.tsx`, `frontend/src/features/auth/AcceptTermsPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`, `frontend/src/app/Layout.tsx`, `frontend/src/test/utils.tsx` (`ME.terms_outdated = false`), `frontend/src/lib/api/schema.d.ts` (`npm run gen:api`)

**Interfaces:**
- Consumes: `MeOut.terms_outdated`, `POST /api/me/accept-terms` (Task 1).
- Produces: route `/accepter-cgu?suite=…` ; `Layout` redirige tout compte aux CGU périmées.

- [ ] **Step 1: Tests qui échouent** — `AcceptTermsPage.test.tsx` :

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ME, mockFetch } from "@/test/utils";
import { routes } from "@/app/router";

vi.mock("@/components/charts/EChart", () => ({ EChart: () => null }));
afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("un compte aux CGU périmées est envoyé vers /accepter-cgu, puis ramené", async () => {
  let accepted = false;
  const fetchMock = mockFetch((url, init) => {
    if (url === "/api/me/accept-terms") { accepted = true; return { body: { ...ME, terms_outdated: false } }; }
    if (url === "/api/me") return { body: { ...ME, terms_outdated: !accepted } };
    return { body: url.startsWith("/api/orders") ? [] : {} };
  });
  const router = renderAt("/portefeuille");
  expect(await screen.findByRole("heading", { level: 1, name: "Nos conditions ont changé" }, { timeout: 5000 })).toBeInTheDocument();
  expect(router.state.location.search).toBe("?suite=%2Fportefeuille");
  const accept = screen.getByRole("button", { name: "Accepter et continuer" });
  expect(accept).toBeDisabled();
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(accept);
  await waitFor(() => expect(router.state.location.pathname).toBe("/portefeuille"));
  expect(fetchMock).toHaveBeenCalledWith("/api/me/accept-terms", expect.objectContaining({ method: "POST" }));
});

test("liens vers les CGU et la politique de confidentialité", async () => {
  mockFetch((url) => ({ body: url === "/api/me" ? { ...ME, terms_outdated: true } : {} }));
  renderAt("/accepter-cgu");
  expect(await screen.findByRole("link", { name: "CGU" })).toHaveAttribute("href", "/cgu");
  expect(screen.getByRole("link", { name: "politique de confidentialité" })).toHaveAttribute("href", "/confidentialite");
});
```

- [ ] **Step 2: Vérifier l'échec** — `npx vitest --run src/features/auth/AcceptTermsPage.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Implémentation**
- `npm run gen:api` ; `ME` de `test/utils.tsx` gagne `terms_outdated: false`, comme le `Me` écrit en dur dans `AuthPage.test.tsx`.
- `AcceptTermsPage.tsx` : `AuthCard title="Nos conditions ont changé"`, `usePageMeta({ title: "Accepter les CGU", noindex: true, … })`, texte « Pour continuer à utiliser PEA Radar, lisez et acceptez la nouvelle version », case « J'accepte les <Link to="/cgu">CGU</Link> et la <Link to="/confidentialite">politique de confidentialité</Link> », bouton « Accepter et continuer » désactivé tant que la case n'est pas cochée ; `useMutation` POST `/api/me/accept-terms` `{ accept_terms: true }` → `queryClient.setQueryData(["me"], me)` puis `navigate(safeNext(params.get("suite")), { replace: true })` (ou `window.location.assign` si `isExternalSuite`). Lien secondaire « Se déconnecter » (POST `/api/auth/logout`, puis `queryClient.clear()` et `/`). Sans compte (`me === null`) : `<Navigate to="/connexion" replace />`.
- `router.tsx` : `{ path: "/accepter-cgu", lazy: async () => ({ Component: (await import("@/features/auth/AcceptTermsPage")).AcceptTermsPage }) }` à côté des autres écrans de compte.
- `Layout.tsx` : juste après `useMe()`, `if (me?.terms_outdated) return <Navigate to={`/accepter-cgu?suite=${encodeURIComponent(location.pathname + location.search)}`} replace />;` (Ruling 3).

- [ ] **Step 4: Vérifier** — `npx vitest --run && npx tsc -b && npm run lint`. Expected: tout passe.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: accept-terms screen, every page redirects an account with outdated terms"
```

---

### Task 9: Carte « Mes données » (export et suppression) et rafraîchissement de l'admin

**Files:**
- Create: `frontend/src/features/settings/DataCard.tsx`, `frontend/src/features/settings/DataCard.test.tsx`
- Modify: `frontend/src/features/settings/SettingsPage.tsx`, `frontend/src/lib/api/client.ts` (`DataExport` type), `frontend/src/features/admin/EditUserDialog.tsx`, `frontend/src/features/admin/AdminPage.test.tsx`

**Interfaces:**
- Consumes: `POST/GET /api/me/export`, `GET /api/me/export/{id}`, `DELETE /api/me` (Tasks 2 et 3).
- Produces: `DataCard` (ancre `id="mes-donnees"`), `export type DataExport = components["schemas"]["ExportOut"]`.

- [ ] **Step 1: Tests qui échouent** — `DataCard.test.tsx` :

```tsx
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { DataCard } from "./DataCard";

afterEach(() => vi.unstubAllGlobals());

const READY = { id: "e1", status: "ready", created_at: "2026-10-01T08:00:00Z", expires_at: "2026-10-08T08:00:00Z" };

test("demande un export, puis indique qu'il est en préparation", async () => {
  let latest: unknown = null;
  mockFetch((url, init) => {
    if (url === "/api/me") return { body: ME };
    if (url === "/api/me/export" && init?.method === "POST") { latest = { ...READY, status: "pending" }; return { status: 202, body: latest }; }
    if (url === "/api/me/export") return { body: latest };
    return { body: {} };
  });
  renderWithProviders(<DataCard />);
  await userEvent.click(await screen.findByRole("button", { name: "Exporter mes données" }));
  expect(await screen.findByText(/en préparation/)).toBeInTheDocument();
});

test("export prêt : lien de téléchargement", async () => {
  mockFetch((url) => ({ body: url === "/api/me/export" ? READY : ME }));
  renderWithProviders(<DataCard />);
  expect(await screen.findByRole("link", { name: /Télécharger/ })).toHaveAttribute("href", "/api/me/export/e1");
});

test("supprimer le compte : adresse retapée et mot de passe", async () => {
  const fetchMock = mockFetch((url) => ({ status: url === "/api/me" ? 200 : 204, body: url === "/api/me" ? ME : null }));
  renderWithProviders(<DataCard />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer mon compte" }));
  const dialog = await screen.findByRole("dialog");
  const confirm = within(dialog).getByRole("button", { name: "Supprimer définitivement" });
  expect(confirm).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText("Retapez votre adresse mail"), ME.email);
  await userEvent.type(within(dialog).getByLabelText("Mot de passe"), "motdepasse-solide");
  await userEvent.click(confirm);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/me", expect.objectContaining({ method: "DELETE" })));
});

test("compte Google sans mot de passe : propose de se reconnecter", async () => {
  mockFetch((url) => ({ body: url === "/api/me" ? { ...ME, has_password: false, has_google: true } : null }));
  renderWithProviders(<DataCard />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer mon compte" }));
  expect(await screen.findByRole("link", { name: "Se reconnecter avec Google" }))
    .toHaveAttribute("href", expect.stringContaining("/api/auth/google/start?suite=%2Freglages"));
});
```

`AdminPage.test.tsx`, test « modifie un compte » : après l'enregistrement, vérifier que `/api/me` est relu (`fetchMock.mock.calls.filter(([u]) => u === "/api/me").length` augmente), pour que la barre latérale suive un admin qui se modifie lui-même.

- [ ] **Step 2: Vérifier l'échec** — `npx vitest --run src/features/settings/DataCard.test.tsx src/features/admin`. Expected: FAIL.

- [ ] **Step 3: Implémentation** — `DataCard.tsx` : `Card` avec `id="mes-donnees"`, titre « Mes données ».
- Export : `useQuery(["data-export"], GET /api/me/export)`. Aucun export ou export expiré → bouton « Exporter mes données » (POST, puis `invalidateQueries(["data-export"])`) et texte « Un fichier JSON avec votre profil, vos réglages, vos ordres, vos favoris et vos conversations. Vous recevrez un mail quand il sera prêt. » ; `pending` → « Export en préparation : vous recevrez un mail. » avec `refetchInterval: 10_000` ; `ready` → lien `<a href={`/api/me/export/${id}`} download>Télécharger mes données</a>` et « disponible jusqu'au … ». Erreur 429 → message de l'API.
- Suppression : bouton `variant="destructive"` « Supprimer mon compte » qui ouvre un `Dialog` : texte « Votre compte, vos ordres, vos favoris, vos conversations et vos réglages seront supprimés immédiatement et définitivement. », champ « Retapez votre adresse mail », et soit `PasswordField` (`id="delete-password"`, libellé « Mot de passe ») si `me.has_password`, soit, pour un compte Google, le lien « Se reconnecter avec Google » vers `/api/auth/google/start?suite=%2Freglages&remember=1` et la note « puis revenez ici dans les 5 minutes ». Bouton « Supprimer définitivement » activé quand l'adresse retapée (sans casse ni espaces) est celle du compte. Succès → `queryClient.clear()` puis `window.location.assign("/")`. Erreur `reauth_required` → message de l'API.
- `SettingsPage.tsx` : `<DataCard />` après `<DevicesCard />`.
- `EditUserDialog.tsx` : `onSuccess` invalide aussi `["me"]`.

- [ ] **Step 4: Vérifier** — `npx vitest --run && npx tsc -b && npm run lint && npm run build`. Expected: tout passe.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: settings card to export personal data and delete the account"
```

**Fin du Bloc 3 : s'arrêter pour que l'utilisateur compacte.**

---

# Bloc 4 — Documentation, e2e, PR (Task 10)

### Task 10: Registre, documentation, bout en bout, vérification finale

**Files:**
- Create: `frontend/public/documentation/registre.md`, `frontend/e2e/privacy.spec.ts`
- Modify: `frontend/public/documentation/_sidebar.md`, `comptes.md`, `api.md`, `base-de-donnees.md`, `frontend/public/guide/app/compte.md`, `frontend/public/guide/app/reglages.md`, `frontend/public/guide/faq.md`, `CLAUDE.md`, `frontend/e2e/seo.spec.ts`

- [ ] **Step 1: E2E qui échoue** — `frontend/e2e/privacy.spec.ts` :

```ts
import { expect, test } from "@playwright/test";

test("pages légales publiques, complètes et indexables", async ({ page }) => {
  for (const [path, title] of [["/cgu", "Conditions générales d'utilisation"], ["/confidentialite", "Politique de confidentialité"],
                               ["/mentions-legales", "Mentions légales"]]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(page.locator('meta[name="robots"]')).not.toHaveAttribute("content", /noindex/);
  }
});

test("export des données depuis les réglages", async ({ page }) => {
  await page.goto("/reglages#mes-donnees");
  const card = page.locator("#mes-donnees");
  const button = card.getByRole("button", { name: "Exporter mes données" });
  if (await button.isVisible()) await button.click();
  await expect(card.getByRole("link", { name: /Télécharger/ })).toBeVisible({ timeout: 30_000 });  // worker : 15 s max
});
```

Dans `seo.spec.ts`, ajouter `/accepter-cgu` aux pages `noindex`.

Run: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait api worker web && docker compose restart web && cd frontend && npx playwright test e2e/privacy.spec.ts`
Expected: PASS une fois les Blocs 1 à 3 en place (sinon FAIL sur le texte des pages). Si l'export du jour existe déjà (relance), le test trouve directement le lien.

- [ ] **Step 2: Documentation admin**
- `registre.md` (spec 6.6) : un tableau par traitement (Comptes et authentification ; Données saisies : ordres, favoris, réglages ; Assistant IA ; Mails ; Sécurité et prévention des abus) avec finalité, base légale, catégories de données, destinataires et sous-traitants, transferts hors UE, durée de conservation, mesures de sécurité. Ajouter « Registre des traitements » au `_sidebar.md`.
- `comptes.md` : sections « CGU versionnées » (`TERMS_VERSION`, 403 `terms_outdated`, `get_account_user()`, écran `/accepter-cgu`), « Export des données » (`data_exports`, worker toutes les 15 s, C7, 7 jours, un à la fois, un par jour), « Suppression du compte » (`erase_account()`, empreinte dans les journaux, reconnexion Google de 5 min), « Durées de conservation » (tableau spec 6.5, tâche `cleanup` de 3 h 30, inactivité C8). Remplacer « Étape suivante » par le lot `notifications`. Journal : `terms_accepted`, `account_deleted` (`details.reason` : `self` ou `inactivity`), `data_export`.
- `api.md` : `POST /me/accept-terms`, `POST/GET /me/export`, `GET /me/export/{id}`, `DELETE /me` ; codes `terms_outdated`, `export_pending`, `export_limit`, `reauth_required`, et `too_many_requests` sur les essais de mot de passe actuel.
- `base-de-donnees.md` : table `data_exports` (données personnelles : oui).
- **Guide** : `app/compte.md` (exporter ses données, supprimer son compte, CGU mises à jour), `app/reglages.md` (carte « Mes données »), `faq.md` (« Comment récupérer ou supprimer mes données ? »).
- `CLAUDE.md` : `get_current_user()` vérifie les CGU, `get_account_user()` pour les routes du compte ; `erase_account()` seul chemin de suppression ; durées de conservation dans `services/privacy/retention.py` ; changer `TERMS_VERSION` quand les CGU changent ; nombre de tests mis à jour ; ligne d'état « suivante : `notifications` ».

- [ ] **Step 3: Vérification finale**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q
cd frontend && npx vitest --run && npx tsc -b && npm run lint && npm run build
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait api worker web && docker compose restart web
docker compose exec -T db psql -U pea -d pea_radar -qc "DELETE FROM rate_limit_hits;"
cd frontend && npm run e2e
docker compose up -d --wait api worker && docker compose restart web
```

Expected: tout passe. Le compte e2e (`ensure-user`) a la version courante des CGU.

- [ ] **Step 4: Commit, revue, PR**

```bash
git add -A CLAUDE.md frontend/public frontend/e2e
git commit -m "docs: processing register, privacy and retention docs, guide pages for export and deletion"
```

Revue de branche complète (skill d'exécution), corrections éventuelles, puis :

```bash
git push -u origin comptes-rgpd
gh pr create --base master --head comptes-rgpd --title "Comptes utilisateurs : RGPD et pages légales" --body "…"
```

**Fin du Bloc 4.**
