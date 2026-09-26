# Lot 4 — Assistant IA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un assistant Claude intégré (page dédiée + panneau latéral ✨) qui répond en streaming en s'appuyant sur les données réelles de l'application via des outils, avec la clé API chiffrée en base et le coût estimé par message.

**Architecture:** Le backend appelle Claude avec le SDK Python officiel (`anthropic`, client synchrone, `client.beta.messages.stream`) dans une boucle d'outils manuelle, exécute les outils sur sa propre base, et renvoie un flux SSE (`text/event-stream`) au navigateur. L'appel à Claude est derrière une dépendance FastAPI (`get_llm_factory`) remplacée par un faux client scripté en test : aucun appel réseau en test. Le frontend lit le flux SSE avec `fetch` + `ReadableStream` (EventSource ne fait pas de POST), affiche le Markdown avec `react-markdown`, et partage un seul composant `ChatView` entre la page Assistant et le panneau latéral.

**Tech Stack:** FastAPI 0.141, SQLAlchemy 2, Alembic, `anthropic` (SDK Python), `cryptography` (Fernet) · React 19, TanStack Query, shadcn (Sheet), `react-markdown` + `remark-gfm`, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-26-pea-radar-design.md` (§ 3.4 tables `user_settings`, `conversations`/`messages` ; § 5.7 Assistant IA ; § 5.8 Réglages ; § 6 Assistant IA — fonctionnement ; § 7 erreurs IA ; § 9 tests).

## Global Constraints

- Modèle par défaut : `claude-opus-5` (modifiable dans les Réglages), réflexion adaptative (`thinking: {"type": "adaptive"}`), réponses en streaming.
- Repli côté serveur en cas de refus : `fallbacks: "default"` avec l'en-tête bêta `server-side-fallback-2026-07-01` (uniquement pour `claude-opus-5`).
- La clé API est stockée **chiffrée** en base (Fernet, clé dérivée de `APP_SECRET`) ou lue depuis `ANTHROPIC_API_KEY` ; elle n'est **jamais** renvoyée au navigateur (ni en clair, ni chiffrée, ni partiellement).
- Endpoint de chat : `POST /api/assistant/conversations/{id}/messages` → SSE.
- Outils : `search_securities(query)`, `get_security_overview(ticker)`, `get_price_history(ticker, period)`, `get_top10()`, `get_portfolio()`, `simulate_past_investment(ticker, amount, date)`, + recherche web serveur Anthropic (`web_search_20260209`).
- Consigne système : français, pédagogique, cite l'horodatage des données, distingue faits et opinions, jamais de prévision présentée comme certaine, rappel « pas un conseil en investissement réglementé ».
- Tokens entrée/sortie et coût estimé enregistrés par message ; coût cumulé par conversation affiché.
- Messages clairs pour : clé absente, clé invalide, quota atteint, service indisponible ; une réponse interrompue reste affichée avec la mention « réponse interrompue ».
- Tout `user_id` passe par `get_current_user` ; toutes les tables métier portent `user_id`.
- Interface en français, thème clair, bureau ≥ 1280 px.
- Tests : outils de l'assistant testés sans appeler Claude ; aucun appel réseau en test.
- Commandes : backend `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` ; frontend `cd frontend && npm test` / `npm run build`.

## Review Focus

1. **Clé API qui fuit** : aucune réponse JSON (réglages, conversations, erreurs SSE, logs d'exception) ne doit contenir la clé ni sa forme chiffrée — test dans Task 1 (`test_settings_never_return_key`) et Task 4 (`test_error_message_does_not_leak_key`).
2. **Coupure en plein flux** (erreur API au milieu, déconnexion du navigateur) : le texte déjà reçu est enregistré avec `interrupted=True` et l'erreur lisible — test Task 4 (`test_api_error_mid_stream_keeps_partial_text`).
3. **Historique invalide envoyé à Claude** : un message assistant vide (erreur avant tout texte) suivi d'un nouveau message utilisateur ne doit pas produire deux messages `user` consécutifs ni un contenu vide — test Task 4 (`test_history_skips_empty_and_merges_consecutive_user_messages`).
4. **Entrées d'outils fantaisistes du modèle** (ticker inconnu, date future, montant négatif, période invalide) : résultat `is_error` explicite, jamais d'exception 500 — tests Task 3.
5. **Accès croisé** : une conversation d'un autre utilisateur renvoie 404 en lecture, suppression et envoi — test Task 2 (`test_other_user_conversation_is_404`).

---

## File Structure

**Backend**
- Modify `backend/pyproject.toml` — dépendances `anthropic`, `cryptography`.
- Modify `backend/app/core/config.py` — `app_secret`, `anthropic_api_key`, `assistant_model`, `assistant_max_tokens`, `assistant_max_rounds`.
- Create `backend/app/services/secrets.py` — chiffrement/déchiffrement Fernet.
- Create `backend/app/services/assistant/__init__.py`, `catalog.py` (modèles + tarifs + coût), `prompt.py` (consigne système), `tools.py` (définitions + exécution), `chat.py` (boucle Claude + erreurs).
- Modify `backend/app/models/portfolio.py` — colonnes `anthropic_key_enc`, `ai_model` sur `UserSettings`.
- Create `backend/app/models/assistant.py` — `Conversation`, `ChatMessage`.
- Create 2 migrations Alembic (autogénérées).
- Create `backend/app/repositories/assistant.py` — clé effective, historique, conversions.
- Create `backend/app/schemas/assistant.py`.
- Create `backend/app/api/routes/assistant.py` — réglages IA, conversations, SSE.
- Modify `backend/app/api/deps.py` — `get_llm_factory`.
- Modify `backend/app/api/routes/security_detail.py` — extraire `simulate_since`.
- Modify `backend/app/main.py` — enregistrer le routeur.
- Tests : `test_secrets_catalog.py`, `test_api_assistant_settings.py`, `test_api_conversations.py`, `test_assistant_tools.py`, `test_assistant_chat.py`, `tests/fake_llm.py`.

**Frontend**
- `src/lib/api/client.ts` — types + `streamSSE`.
- `src/components/ui/sheet.tsx` (shadcn).
- `src/features/settings/AssistantSettingsCard.tsx` (+ test).
- `src/features/assistant/` : `api.ts`, `useChat.ts`, `Markdown.tsx`, `ChatMessages.tsx`, `Composer.tsx`, `suggestions.ts`, `ChatView.tsx`, `AssistantPage.tsx`, `AssistantPanel.tsx` (provider + contexte), `AskAiButton.tsx`, tests.
- Modify `src/app/router.tsx`, `src/app/Layout.tsx`, `src/features/home/TopList.tsx`, `src/features/security/SecurityPage.tsx`, `src/features/settings/SettingsPage.tsx`.

**Infra/doc** : `frontend/nginx.conf` (délai de lecture 600 s), `.env.example`, `README.md`, `e2e/smoke.spec.ts`.

---

### Task 1: Clé API chiffrée, catalogue des modèles, réglages IA

**Files:**
- Modify: `backend/pyproject.toml`, `backend/app/core/config.py`, `backend/app/models/portfolio.py`, `.env.example`, `.env` (local, ignoré par git)
- Create: `backend/app/services/secrets.py`, `backend/app/services/assistant/__init__.py`, `backend/app/services/assistant/catalog.py`, `backend/app/repositories/assistant.py`, `backend/app/schemas/assistant.py`, `backend/app/api/routes/assistant.py`, migration `*_assistant_settings.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_secrets_catalog.py`, `backend/tests/test_api_assistant_settings.py`

**Interfaces:**
- Produces:
  - `encrypt_secret(plain: str, secret: str) -> str`, `decrypt_secret(token: str, secret: str) -> str | None`, `class MissingSecretError(Exception)`
  - `AssistantModel` (dataclass: `id, label, input_per_mtok, output_per_mtok, adaptive_thinking: bool, fallback: str | None, web_search_type: str`), `MODELS: tuple[AssistantModel, ...]`, `get_model(model_id: str | None) -> AssistantModel` (inconnu/None → modèle par défaut de la config), `Usage` (dataclass mutable: `input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, web_searches`, méthode `add(sdk_usage)`), `estimate_cost(model: AssistantModel, usage: Usage) -> float` (USD)
  - `resolve_api_key(settings_row: UserSettings) -> tuple[str | None, Literal["settings", "env"] | None]`
  - Routes `GET /api/assistant/settings` → `AssistantSettingsOut{configured: bool, source: "settings"|"env"|None, model: str, models: list[ModelOut{id,label}]}`, `PUT /api/assistant/settings` body `AssistantSettingsUpdate{api_key: str|None=None, remove_key: bool=False, model: str}`

- [ ] **Step 1: Dépendances et configuration**

`backend/pyproject.toml` : ajouter à `dependencies` :
```toml
  "anthropic>=0.116",
  "cryptography>=43",
```
`backend/app/core/config.py`, ajouter dans `Settings` :
```python
    app_secret: str = ""
    anthropic_api_key: str = ""
    assistant_model: str = "claude-opus-5"
    assistant_max_tokens: int = 16000
    assistant_max_rounds: int = 8
```
`.env.example` : ajouter
```
# Chiffre la clé API Claude en base : une longue chaîne aléatoire, à ne pas changer ensuite
APP_SECRET=change-me
# Optionnel : clé API Claude (sinon, saisie dans les Réglages)
ANTHROPIC_API_KEY=
```
`.env` local : ajouter `APP_SECRET=<48 caractères aléatoires>` (générés avec `openssl rand -hex 24`).
Reconstruire l'image : `docker compose -f docker-compose.yml -f docker-compose.dev.yml build api`.

- [ ] **Step 2: Tests du chiffrement et du catalogue (échouent)**

`backend/tests/test_secrets_catalog.py` :
```python
from types import SimpleNamespace

import pytest

from app.services.assistant.catalog import MODELS, Usage, estimate_cost, get_model
from app.services.secrets import MissingSecretError, decrypt_secret, encrypt_secret


def test_encrypt_roundtrip_and_ciphertext_differs():
    token = encrypt_secret("sk-ant-abc", "secret-1")
    assert token != "sk-ant-abc" and "sk-ant" not in token
    assert decrypt_secret(token, "secret-1") == "sk-ant-abc"


def test_decrypt_with_other_secret_returns_none():
    assert decrypt_secret(encrypt_secret("sk-ant-abc", "secret-1"), "secret-2") is None


def test_encrypt_without_secret_raises():
    with pytest.raises(MissingSecretError):
        encrypt_secret("sk-ant-abc", "")


def test_get_model_defaults_to_opus_5():
    assert get_model(None).id == "claude-opus-5"
    assert get_model("inconnu").id == "claude-opus-5"
    assert get_model("claude-sonnet-5").id == "claude-sonnet-5"
    assert get_model("claude-opus-5").fallback == "default"
    assert not get_model("claude-haiku-4-5").adaptive_thinking
    assert {m.id for m in MODELS} >= {"claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"}


def test_usage_add_and_cost():
    usage = Usage()
    usage.add(SimpleNamespace(input_tokens=1000, output_tokens=2000, cache_read_input_tokens=None,
                              cache_creation_input_tokens=0, server_tool_use=SimpleNamespace(web_search_requests=2)))
    usage.add(SimpleNamespace(input_tokens=1000, output_tokens=0))
    assert (usage.input_tokens, usage.output_tokens, usage.web_searches) == (2000, 2000, 2)
    # Opus 5 : 5 $/Mtok en entrée, 25 $/Mtok en sortie, 0,01 $ par recherche
    assert estimate_cost(get_model("claude-opus-5"), usage) == pytest.approx(0.002 * 5 + 0.002 * 25 + 0.02)
```
Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_secrets_catalog.py`
Expected: FAIL (`ModuleNotFoundError: app.services.assistant`).

- [ ] **Step 3: Implémenter `secrets.py` et `catalog.py`**

`backend/app/services/secrets.py` :
```python
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class MissingSecretError(Exception):
    """APP_SECRET absent : impossible de chiffrer une clé en base."""


def _fernet(secret: str) -> Fernet:
    if not secret:
        raise MissingSecretError
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt_secret(plain: str, secret: str) -> str:
    return _fernet(secret).encrypt(plain.encode()).decode()


def decrypt_secret(token: str, secret: str) -> str | None:
    try:
        return _fernet(secret).decrypt(token.encode()).decode()
    except (InvalidToken, MissingSecretError):
        return None
```
`backend/app/services/assistant/__init__.py` : vide.
`backend/app/services/assistant/catalog.py` :
```python
from dataclasses import dataclass

from app.core.config import get_settings

FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH_COST = 0.01  # 10 $ les 1 000 recherches


@dataclass(frozen=True)
class AssistantModel:
    id: str
    label: str
    input_per_mtok: float
    output_per_mtok: float
    adaptive_thinking: bool = True
    fallback: str | None = None
    web_search_type: str = "web_search_20260209"


MODELS: tuple[AssistantModel, ...] = (
    AssistantModel("claude-opus-5", "Claude Opus 5 (recommandé)", 5.0, 25.0, fallback="default"),
    AssistantModel("claude-sonnet-5", "Claude Sonnet 5 (plus rapide)", 3.0, 15.0),
    AssistantModel("claude-haiku-4-5", "Claude Haiku 4.5 (économique)", 1.0, 5.0, adaptive_thinking=False,
                   web_search_type="web_search_20250305"),
    AssistantModel("claude-fable-5-1", "Claude Fable 5.1 (le plus puissant, plus cher)", 10.0, 50.0),
)
_BY_ID = {m.id: m for m in MODELS}


def get_model(model_id: str | None) -> AssistantModel:
    return _BY_ID.get(model_id or "") or _BY_ID.get(get_settings().assistant_model) or MODELS[0]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    web_searches: int = 0

    def add(self, usage: object) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        server = getattr(usage, "server_tool_use", None)
        self.web_searches += (getattr(server, "web_search_requests", 0) or 0) if server else 0


def estimate_cost(model: AssistantModel, usage: Usage) -> float:
    """Coût estimé en dollars (tarifs publics ; lecture du cache 0,1 x, écriture 1,25 x l'entrée)."""
    per_input = model.input_per_mtok / 1_000_000
    return round(
        usage.input_tokens * per_input
        + usage.cache_read_tokens * per_input * 0.1
        + usage.cache_write_tokens * per_input * 1.25
        + usage.output_tokens * model.output_per_mtok / 1_000_000
        + usage.web_searches * WEB_SEARCH_COST,
        6,
    )
```
Run the Step 2 command. Expected: PASS (5 tests).

- [ ] **Step 4: Tests des réglages IA (échouent)**

`backend/tests/test_api_assistant_settings.py` :
```python
import pytest

from app.core.config import get_settings
from app.models import UserSettings


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_secret", "test-secret")
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")


def test_settings_default_not_configured(client):
    body = client.get("/api/assistant/settings").json()
    assert body["configured"] is False and body["source"] is None and body["model"] == "claude-opus-5"
    assert {"id": "claude-opus-5", "label": "Claude Opus 5 (recommandé)"} in body["models"]


def test_save_key_is_encrypted_and_never_returned(client, db):
    response = client.put("/api/assistant/settings", json={"api_key": "sk-ant-test-1234567890abcdef", "model": "claude-sonnet-5"})
    assert response.status_code == 200
    body = response.json()
    assert body == {**body, "configured": True, "source": "settings", "model": "claude-sonnet-5"}
    stored = db.query(UserSettings).one()
    assert stored.anthropic_key_enc and "sk-ant" not in stored.anthropic_key_enc


def test_settings_never_return_key(client):
    client.put("/api/assistant/settings", json={"api_key": "sk-ant-test-1234567890abcdef", "model": "claude-opus-5"})
    for response in (client.get("/api/assistant/settings"), client.get("/api/settings")):
        assert "sk-ant" not in response.text and "anthropic_key" not in response.text


def test_model_change_keeps_key_and_remove_key(client):
    client.put("/api/assistant/settings", json={"api_key": "sk-ant-test-1234567890abcdef", "model": "claude-opus-5"})
    assert client.put("/api/assistant/settings", json={"model": "claude-haiku-4-5"}).json()["configured"] is True
    body = client.put("/api/assistant/settings", json={"remove_key": True, "model": "claude-haiku-4-5"}).json()
    assert body["configured"] is False and body["model"] == "claude-haiku-4-5"


def test_env_key_is_used_when_none_saved(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-env-1234567890")
    assert client.get("/api/assistant/settings").json()["source"] == "env"


@pytest.mark.parametrize("payload", [
    {"api_key": "court", "model": "claude-opus-5"},
    {"api_key": "sk-ant avec espaces 1234567890", "model": "claude-opus-5"},
    {"model": "gpt-4"},
])
def test_invalid_payload_is_422(client, payload):
    assert client.put("/api/assistant/settings", json=payload).status_code == 422


def test_missing_app_secret_is_explained(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_secret", "")
    response = client.put("/api/assistant/settings", json={"api_key": "sk-ant-test-1234567890abcdef", "model": "claude-opus-5"})
    assert response.status_code == 503 and "APP_SECRET" in response.json()["detail"]
```
Run: `docker compose ... run --rm -T api pytest -q tests/test_api_assistant_settings.py`
Expected: FAIL (404 sur `/api/assistant/settings`).

- [ ] **Step 5: Modèle, migration, dépôt, schémas, routes**

`backend/app/models/portfolio.py`, dans `UserSettings` (importer `Text`) :
```python
    anthropic_key_enc: Mapped[str | None] = mapped_column(Text)  # clé API Claude chiffrée (Fernet)
    ai_model: Mapped[str | None] = mapped_column(String(64))
```
Migration : `docker compose ... run --rm -T api alembic revision --autogenerate -m "assistant settings"` puis vérifier qu'elle ne contient que les deux `add_column`.

`backend/app/repositories/assistant.py` :
```python
from typing import Literal

from app.core.config import get_settings
from app.models import UserSettings
from app.services.secrets import decrypt_secret

KeySource = Literal["settings", "env"]


def resolve_api_key(settings_row: UserSettings) -> tuple[str | None, KeySource | None]:
    """Clé saisie dans les Réglages en priorité, sinon ANTHROPIC_API_KEY."""
    config = get_settings()
    if settings_row.anthropic_key_enc:
        key = decrypt_secret(settings_row.anthropic_key_enc, config.app_secret)
        if key:
            return key, "settings"
    if config.anthropic_api_key:
        return config.anthropic_api_key, "env"
    return None, None
```
`backend/app/schemas/assistant.py` :
```python
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.assistant.catalog import MODELS


class ModelOut(BaseModel):
    id: str
    label: str


class AssistantSettingsOut(BaseModel):
    configured: bool
    source: Literal["settings", "env"] | None
    model: str
    models: list[ModelOut]


class AssistantSettingsUpdate(BaseModel):
    api_key: str | None = Field(default=None, min_length=20, max_length=300, pattern=r"^\S+$")
    remove_key: bool = False
    model: str

    @field_validator("model")
    @classmethod
    def known_model(cls, value: str) -> str:
        if value not in {m.id for m in MODELS}:
            raise ValueError("Modèle inconnu.")
        return value
```
`backend/app/api/routes/assistant.py` :
```python
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import User, UserSettings
from app.repositories.assistant import resolve_api_key
from app.repositories.user_settings import get_user_settings
from app.schemas.assistant import AssistantSettingsOut, AssistantSettingsUpdate, ModelOut
from app.services.assistant.catalog import MODELS, get_model
from app.services.secrets import MissingSecretError, encrypt_secret

router = APIRouter(tags=["assistant"])
logger = logging.getLogger(__name__)


def _settings_out(row: UserSettings) -> AssistantSettingsOut:
    _, source = resolve_api_key(row)
    return AssistantSettingsOut(configured=source is not None, source=source, model=get_model(row.ai_model).id,
                                models=[ModelOut(id=m.id, label=m.label) for m in MODELS])


@router.get("/assistant/settings", response_model=AssistantSettingsOut)
def read_assistant_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AssistantSettingsOut:
    return _settings_out(get_user_settings(db, user.id))


@router.put("/assistant/settings", response_model=AssistantSettingsOut)
def update_assistant_settings(
    payload: AssistantSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> AssistantSettingsOut:
    row = get_user_settings(db, user.id)
    row.ai_model = payload.model
    if payload.remove_key:
        row.anthropic_key_enc = None
    elif payload.api_key:
        try:
            row.anthropic_key_enc = encrypt_secret(payload.api_key, get_settings().app_secret)
        except MissingSecretError:
            db.rollback()
            raise HTTPException(status_code=503, detail="Ajoutez APP_SECRET dans le fichier .env pour enregistrer une clé.")
    db.commit()
    return _settings_out(row)
```
`backend/app/main.py` : importer `assistant` et l'ajouter au tuple des routeurs.

Run the Step 4 command. Expected: PASS (9 tests). Then full backend suite: `docker compose ... run --rm -T api pytest -q` → all pass.

- [ ] **Step 6: Commit**
```bash
git add -A backend .env.example && git commit -m "feat: encrypted Claude API key and assistant model settings"
```

---

### Task 2: Conversations et messages (tables + API CRUD)

**Files:**
- Create: `backend/app/models/assistant.py`, migration `*_conversations_and_messages.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/repositories/assistant.py`, `backend/app/schemas/assistant.py`, `backend/app/api/routes/assistant.py`
- Test: `backend/tests/test_api_conversations.py`

**Interfaces:**
- Consumes: `get_user_settings`, `get_current_user`.
- Produces:
  - `Conversation(id, user_id, title, security_id|None, input_tokens, output_tokens, cost_usd, created_at, updated_at)`; `ChatMessage(id, conversation_id, role "user"|"assistant", content, tools: list[str], input_tokens, output_tokens, cost_usd, model|None, interrupted: bool, error|None, created_at)` — table `messages`.
  - `DEFAULT_TITLE = "Nouvelle conversation"`; `owned_conversation(db, user_id, conversation_id) -> Conversation` (404 sinon); `conversation_out(db, conv) -> ConversationOut`; `message_out(msg) -> MessageOut`; `claude_history(messages: list[ChatMessage]) -> list[dict]`.
  - Routes : `GET /api/assistant/conversations` → `list[ConversationOut]` (plus récente d'abord) ; `POST /api/assistant/conversations` body `ConversationIn{security_id: int|None}` → 201 `ConversationOut` ; `GET /api/assistant/conversations/{id}` → `ConversationDetail` (`ConversationOut` + `messages: list[MessageOut]`) ; `DELETE /api/assistant/conversations/{id}` → 204.
  - `ConversationOut{id, title, security_id, security_name, security_symbol, input_tokens, output_tokens, cost_usd, created_at, updated_at}`, `MessageOut{id, role, content, tools, interrupted, error, cost_usd, created_at}`.

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_api_conversations.py` :
```python
from app.models import ChatMessage, Conversation, User
from app.repositories.assistant import claude_history
from tests.factories import make_security


def test_create_list_get_delete_conversation(client, db):
    s = make_security(db, "MC.PA", name="LVMH")
    created = client.post("/api/assistant/conversations", json={"security_id": s.id})
    assert created.status_code == 201
    conv = created.json()
    assert (conv["title"], conv["security_name"], conv["security_symbol"], conv["cost_usd"]) == ("À propos de LVMH", "LVMH", "MC", 0)
    plain = client.post("/api/assistant/conversations", json={}).json()
    assert plain["title"] == "Nouvelle conversation" and plain["security_id"] is None
    assert [c["id"] for c in client.get("/api/assistant/conversations").json()] == [plain["id"], conv["id"]]
    detail = client.get(f"/api/assistant/conversations/{conv['id']}").json()
    assert detail["messages"] == []
    assert client.delete(f"/api/assistant/conversations/{conv['id']}").status_code == 204
    assert client.get(f"/api/assistant/conversations/{conv['id']}").status_code == 404


def test_unknown_security_is_404(client):
    assert client.post("/api/assistant/conversations", json={"security_id": 999999}).status_code == 404


def test_other_user_conversation_is_404(client, db):
    client.get("/api/assistant/conversations")  # crée l'utilisateur par défaut
    other = User(name="Autre")
    db.add(other)
    db.flush()
    conv = Conversation(user_id=other.id, title="Secret")
    db.add(conv)
    db.flush()
    assert client.get(f"/api/assistant/conversations/{conv.id}").status_code == 404
    assert client.delete(f"/api/assistant/conversations/{conv.id}").status_code == 404
    assert client.post(f"/api/assistant/conversations/{conv.id}/messages", json={"content": "Bonjour"}).status_code == 404
    assert all(c["id"] != conv.id for c in client.get("/api/assistant/conversations").json())


def test_history_skips_empty_and_merges_consecutive_user_messages():
    messages = [
        ChatMessage(role="user", content="Bonjour"),
        ChatMessage(role="assistant", content="", interrupted=True, error="Service indisponible"),
        ChatMessage(role="user", content="Tu es là ?"),
        ChatMessage(role="assistant", content="Oui."),
    ]
    assert claude_history(messages) == [
        {"role": "user", "content": "Bonjour\n\nTu es là ?"},
        {"role": "assistant", "content": "Oui."},
    ]
```
Run: `docker compose ... run --rm -T api pytest -q tests/test_api_conversations.py`
Expected: FAIL (`ImportError: ChatMessage`).

- [ ] **Step 2: Modèles + migration**

`backend/app/models/assistant.py` :
```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    security_id: Mapped[int | None] = mapped_column(ForeignKey("securities.id", ondelete="SET NULL"))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChatMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text, default="")
    tools: Mapped[list] = mapped_column(JSONB, default=list)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    model: Mapped[str | None] = mapped_column(String(64))
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```
`backend/app/models/__init__.py` : importer et exporter `ChatMessage`, `Conversation`.
Migration : `alembic revision --autogenerate -m "conversations and messages"` ; vérifier les 2 tables + index.

- [ ] **Step 3: Dépôt, schémas, routes**

Ajouter à `backend/app/repositories/assistant.py` (imports : `HTTPException`, `select`, `Session`, `ChatMessage`, `Conversation`, `Security`, schémas) :
```python
DEFAULT_TITLE = "Nouvelle conversation"


def owned_conversation(db: Session, user_id: int, conversation_id: int) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    return conv


def conversation_messages(db: Session, conversation_id: int) -> list[ChatMessage]:
    return list(db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
                           .order_by(ChatMessage.created_at, ChatMessage.id)))


def conversation_out(db: Session, conv: Conversation) -> ConversationOut:
    security = db.get(Security, conv.security_id) if conv.security_id else None
    return ConversationOut(
        id=conv.id, title=conv.title, security_id=conv.security_id,
        security_name=security.name if security else None, security_symbol=security.symbol if security else None,
        input_tokens=conv.input_tokens, output_tokens=conv.output_tokens, cost_usd=round(conv.cost_usd, 4),
        created_at=conv.created_at, updated_at=conv.updated_at,
    )


def message_out(msg: ChatMessage) -> MessageOut:
    return MessageOut(id=msg.id, role=msg.role, content=msg.content, tools=list(msg.tools or []),
                      interrupted=msg.interrupted, error=msg.error, cost_usd=round(msg.cost_usd, 4),
                      created_at=msg.created_at)


def claude_history(messages: list[ChatMessage]) -> list[dict]:
    """Historique texte seul : les messages vides sont ignorés et deux messages du même rôle fusionnés."""
    history: list[dict] = []
    for msg in messages:
        if not msg.content.strip():
            continue
        if history and history[-1]["role"] == msg.role:
            history[-1]["content"] += "\n\n" + msg.content
        else:
            history.append({"role": msg.role, "content": msg.content})
    return history
```
Ajouter à `backend/app/schemas/assistant.py` (import `datetime`) :
```python
class ConversationIn(BaseModel):
    security_id: int | None = None


class ConversationOut(BaseModel):
    id: int
    title: str
    security_id: int | None
    security_name: str | None
    security_symbol: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    tools: list[str]
    interrupted: bool
    error: str | None
    cost_usd: float
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]
```
Ajouter à `backend/app/api/routes/assistant.py` :
```python
@router.get("/assistant/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ConversationOut]:
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id)
                      .order_by(Conversation.updated_at.desc(), Conversation.id.desc()))
    return [conversation_out(db, c) for c in rows]


@router.post("/assistant/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(payload: ConversationIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ConversationOut:
    title = DEFAULT_TITLE
    if payload.security_id is not None:
        security = db.get(Security, payload.security_id)
        if security is None:
            raise HTTPException(status_code=404, detail="Titre introuvable")
        title = f"À propos de {security.name}"[:120]
    conv = Conversation(user_id=user.id, title=title, security_id=payload.security_id)
    db.add(conv)
    db.commit()
    return conversation_out(db, conv)


@router.get("/assistant/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ConversationDetail:
    conv = owned_conversation(db, user.id, conversation_id)
    return ConversationDetail(**conversation_out(db, conv).model_dump(),
                              messages=[message_out(m) for m in conversation_messages(db, conv.id)])


@router.delete("/assistant/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    db.delete(owned_conversation(db, user.id, conversation_id))
    db.commit()
```
Ajouter une route provisoire d'envoi qui fait seulement la vérification d'appartenance (remplacée en Task 4) :
```python
@router.post("/assistant/conversations/{conversation_id}/messages")
def send_message(conversation_id: int, payload: MessageIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned_conversation(db, user.id, conversation_id)
    raise HTTPException(status_code=501, detail="Bientôt disponible")
```
avec dans les schémas :
```python
class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message vide.")
        return value.strip()
```
Run: `docker compose ... run --rm -T api pytest -q tests/test_api_conversations.py` → PASS (4 tests) ; suite complète → PASS.

- [ ] **Step 4: Commit**
```bash
git add -A backend && git commit -m "feat: assistant conversations and messages API"
```

---

### Task 3: Outils de l'assistant (exécutés sur les données de l'application)

**Files:**
- Create: `backend/app/services/assistant/tools.py`
- Modify: `backend/app/api/routes/security_detail.py` (extraire `simulate_since`)
- Test: `backend/tests/test_assistant_tools.py`

**Interfaces:**
- Consumes: `get_security`, `get_top`, `get_portfolio` (fonctions de routes appelées directement avec `db=`, `user=`), `search_securities`, `all_daily_prices`, `rsi`, `sma`, `macd`, `performance`.
- Produces:
  - `simulate_since(db, user_id, security_id, amount, first_day: date) -> SimulationOut` (la route `simulate` l'appelle avec `prices[-1].date - timedelta(days=window)`).
  - `TOOL_SPECS: list[dict]` (6 outils client, JSON Schema), `TOOL_LABELS: dict[str, str]` (libellés FR, incluant `web_search`), `class ToolError(Exception)`, `run_tool(db, user: User, name: str, tool_input: dict) -> dict | list`, `tool_label(name) -> str`.

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_assistant_tools.py` :
```python
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.current_user import ensure_default_user
from app.models import DailyPrice, SecurityQuote
from app.services.assistant.tools import TOOL_LABELS, TOOL_SPECS, ToolError, run_tool
from tests.factories import make_security


@pytest.fixture
def user(db):
    return ensure_default_user(db)


def closes(db, security, n=260, start=100.0):
    today = date.today()
    for i in range(n):
        db.add(DailyPrice(security_id=security.id, date=today - timedelta(days=n - i), close=start + i))
    db.flush()


def test_specs_are_valid_and_labelled():
    names = {t["name"] for t in TOOL_SPECS}
    assert names == {"search_securities", "get_security_overview", "get_price_history", "get_top10", "get_portfolio",
                     "simulate_past_investment"}
    for spec in TOOL_SPECS:
        assert spec["input_schema"]["type"] == "object" and spec["description"]
        assert spec["name"] in TOOL_LABELS
    assert "web_search" in TOOL_LABELS


def test_search_securities(db, user):
    make_security(db, "MC.PA", name="LVMH")
    result = run_tool(db, user, "search_securities", {"query": "lvmh"})
    assert result[0]["ticker"] == "MC.PA" and result[0]["name"] == "LVMH"
    assert run_tool(db, user, "search_securities", {"query": "zzz"}) == []


def test_security_overview_by_symbol_or_yahoo_ticker(db, user):
    s = make_security(db, "MC.PA", name="LVMH")
    db.add(SecurityQuote(security_id=s.id, price=600, previous_close=590, change_pct=1.7, volume=1,
                         as_of=datetime(2026, 3, 10, 16, tzinfo=UTC)))
    db.flush()
    for ticker in ("MC.PA", "mc", "MC"):
        overview = run_tool(db, user, "get_security_overview", {"ticker": ticker})
        assert overview["name"] == "LVMH" and overview["price"] == 600 and overview["as_of"].startswith("2026-03-10")
        assert "sparkline" not in overview


def test_unknown_ticker_is_tool_error(db, user):
    with pytest.raises(ToolError, match="introuvable"):
        run_tool(db, user, "get_security_overview", {"ticker": "NOPE"})


def test_price_history_sampled_with_indicators(db, user):
    s = make_security(db, "MC.PA")
    closes(db, s)
    result = run_tool(db, user, "get_price_history", {"ticker": "MC.PA", "period": "1Y"})
    assert len(result["closes"]) <= 60 and result["closes"][-1]["close"] == 359.0
    assert result["indicators"]["sma50"] is not None and result["indicators"]["rsi14"] == pytest.approx(100.0)
    assert result["performance_pct"] > 0
    with pytest.raises(ToolError):
        run_tool(db, user, "get_price_history", {"ticker": "MC.PA", "period": "10Y"})


def test_top10_and_portfolio_empty(db, user):
    assert run_tool(db, user, "get_top10", {}) == []
    portfolio = run_tool(db, user, "get_portfolio", {})
    assert portfolio["positions"] == [] and portfolio["counter"]["min_orders"] == 12


def test_simulate_past_investment(db, user):
    s = make_security(db, "MC.PA")
    closes(db, s)
    start = (date.today() - timedelta(days=100)).isoformat()
    result = run_tool(db, user, "simulate_past_investment", {"ticker": "MC.PA", "amount": 1000, "date": start})
    assert result["shares"] > 0 and result["gain"] > 0 and result["start_date"] >= start


@pytest.mark.parametrize("tool_input", [
    {"ticker": "MC.PA", "amount": -5, "date": "2026-01-02"},
    {"ticker": "MC.PA", "amount": 100, "date": "2999-01-01"},
    {"ticker": "MC.PA", "amount": 100, "date": "pas une date"},
    {"ticker": "MC.PA"},
])
def test_simulate_invalid_input_is_tool_error(db, user, tool_input):
    make_security(db, "MC.PA")
    with pytest.raises(ToolError):
        run_tool(db, user, "simulate_past_investment", tool_input)


def test_unknown_tool_is_tool_error(db, user):
    with pytest.raises(ToolError):
        run_tool(db, user, "rm_rf", {})
```
Run: `docker compose ... run --rm -T api pytest -q tests/test_assistant_tools.py`
Expected: FAIL (`ModuleNotFoundError: app.services.assistant.tools`).

- [ ] **Step 2: Extraire `simulate_since`**

Dans `security_detail.py`, remplacer le corps de `simulate` par :
```python
def simulate_since(db: Session, user_id: int, security_id: int, amount: float, first_day: date) -> SimulationOut:
    row = _row_or_404(db, user_id, security_id)
    security, quote = row[0], row[1]
    rate = to_eur(1.0, currency_for_market(security.market)) or 1.0  # le PEA se paie en euros
    prices = all_daily_prices(db, security_id)
    empty = dict(shares=0, invested=0.0, buy_fee=0.0, sell_fee=0.0, current_value=0.0, gain=0.0, gain_pct=None)
    if not prices:
        return SimulationOut(start_date=None, start_price=None, current_price=None,
                             message="Pas assez d'historique pour simuler cet achat.", **empty)
    start = next((p for p in prices if p.date >= first_day), prices[-1])
    # ... reste identique (start_price, current_price, shares, frais, gain) avec user_fee_grid(db, user_id)


@router.get("/securities/{security_id}/simulate", response_model=SimulationOut)
def simulate(security_id: int, amount: float = Query(..., gt=0, le=1_000_000),
             period: Literal["1W", "1M", "6M", "1Y"] = "1M",
             db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SimulationOut:
    prices = all_daily_prices(db, security_id)
    last = prices[-1].date if prices else date.today()
    return simulate_since(db, user.id, security_id, amount, last - timedelta(days=SIMULATION_WINDOW[period]))
```
Ruling attendu : le repli `prices[0]` de l'ancienne version (fenêtre plus longue que l'historique) devient « première clôture ≥ date demandée, sinon la plus récente ». Pour garder le comportement de la route (historique trop court → premier jour disponible), `simulate_since` utilise `next((p for p in prices if p.date >= first_day), prices[-1])` et la route garantit `first_day ≤ last`, donc le premier prix ≥ `first_day` existe toujours et vaut `prices[0]` si la fenêtre dépasse l'historique. Les tests existants de `simulate` doivent rester verts.

- [ ] **Step 3: Implémenter `tools.py`**

```python
import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.orders import paris_today
from app.api.routes.portfolio import get_portfolio
from app.api.routes.rankings import get_top
from app.api.routes.security_detail import get_security, simulate_since
from app.models import Security, User
from app.repositories.market_data import all_daily_prices
from app.repositories.securities import search_securities
from app.services.indicators import macd, performance, rsi, sma

logger = logging.getLogger(__name__)
HISTORY_DAYS = {"1M": 31, "6M": 183, "1Y": 365, "5Y": 365 * 5}
MAX_POINTS = 60


class ToolError(Exception):
    """Erreur renvoyée à Claude comme résultat d'outil (is_error)."""


TOOL_LABELS = {
    "search_securities": "Recherche de titres",
    "get_security_overview": "Fiche du titre",
    "get_price_history": "Historique des cours",
    "get_top10": "Top 10",
    "get_portfolio": "Votre portefeuille",
    "simulate_past_investment": "Simulation d'achat passé",
    "web_search": "Recherche web",
}

_TICKER = {"type": "string", "description": "Ticker Yahoo (ex. MC.PA) ou symbole (ex. MC)."}
TOOL_SPECS: list[dict] = [
    {"name": "search_securities",
     "description": "Cherche des actions ou ETF par nom, ticker ou ISIN. Renvoie ticker, cours, variation du jour, score et éligibilité PEA.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Texte recherché"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 10}}, "required": ["query"]}},
    {"name": "get_security_overview",
     "description": "Fiche complète d'un titre : cours et horodatage, score détaillé (composants et explications), fondamentaux, éligibilité PEA.",
     "input_schema": {"type": "object", "properties": {"ticker": _TICKER}, "required": ["ticker"]}},
    {"name": "get_price_history",
     "description": "Clôtures journalières d'un titre sur une période (échantillonnées, 60 points maximum) avec RSI 14, moyennes mobiles 50/200, MACD et performance.",
     "input_schema": {"type": "object", "properties": {
         "ticker": _TICKER, "period": {"type": "string", "enum": list(HISTORY_DAYS)}}, "required": ["ticker", "period"]}},
    {"name": "get_top10",
     "description": "Top 10 actuel de l'application (actions éligibles PEA les mieux notées) avec les 3 principales raisons de chaque score.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_portfolio",
     "description": "Portefeuille PEA de l'utilisateur : positions, PRU, plus/moins-values, répartition par secteur, compteur d'ordres de l'année.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "simulate_past_investment",
     "description": "Simule un achat passé : combien vaudrait aujourd'hui un montant investi à une date donnée, frais de courtage inclus (grille de l'utilisateur).",
     "input_schema": {"type": "object", "properties": {
         "ticker": _TICKER, "amount": {"type": "number", "description": "Montant en euros"},
         "date": {"type": "string", "description": "Date d'achat AAAA-MM-JJ"}}, "required": ["ticker", "amount", "date"]}},
]


def tool_label(name: str) -> str:
    return TOOL_LABELS.get(name, name)


def _resolve(db: Session, ticker: object) -> Security:
    if not isinstance(ticker, str) or not ticker.strip():
        raise ToolError("Paramètre ticker manquant.")
    value = ticker.strip().upper()
    base = select(Security).where(Security.active.is_(True), Security.kind != "index")
    found = db.scalars(base.where(func.upper(Security.yahoo_ticker) == value)).first()
    if found is None:
        # symbole seul : priorité aux titres éligibles, puis à Paris
        candidates = list(db.scalars(base.where(func.upper(Security.symbol) == value)))
        candidates.sort(key=lambda s: (s.eligibility != "eligible", not s.yahoo_ticker.endswith(".PA")))
        found = candidates[0] if candidates else None
    if found is None:
        raise ToolError(f"Titre introuvable : {ticker}. Utilisez search_securities pour trouver le bon ticker.")
    return found


def _search(db: Session, user: User, args: dict) -> list[dict]:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolError("Paramètre query manquant.")
    limit = args.get("limit") if isinstance(args.get("limit"), int) else 8
    rows, _ = search_securities(db, q=query, kind=None, eligibility=None, limit=max(1, min(limit, 10)), offset=0)
    return [{"ticker": s.yahoo_ticker, "symbol": s.symbol, "name": s.name, "kind": s.kind, "market": s.market,
             "eligibility": s.eligibility, "price": q.price if q else None, "change_pct": q.change_pct if q else None}
            for s, q in rows]


def _overview(db: Session, user: User, args: dict) -> dict:
    security = _resolve(db, args.get("ticker"))
    return get_security(security.id, db=db, user=user).model_dump(mode="json", exclude={"sparkline"})


def _last(values: list) -> float | None:
    value = values[-1] if values else None
    return round(value, 2) if value is not None else None


def _history(db: Session, user: User, args: dict) -> dict:
    period = args.get("period")
    if period not in HISTORY_DAYS:
        raise ToolError("Période invalide : utilisez 1M, 6M, 1Y ou 5Y.")
    security = _resolve(db, args.get("ticker"))
    prices = all_daily_prices(db, security.id)
    if not prices:
        raise ToolError(f"Pas d'historique pour {security.name}.")
    values = [p.close for p in prices]
    since = prices[-1].date - timedelta(days=HISTORY_DAYS[period])
    window = [p for p in prices if p.date >= since]
    step = max(1, -(-len(window) // MAX_POINTS))
    sampled = window[::-1][::step][::-1]  # garde toujours la dernière clôture
    m = macd(values)
    return {
        "ticker": security.yahoo_ticker, "name": security.name, "period": period, "currency_note": "cours en devise de cotation",
        "first_date": window[0].date.isoformat(), "last_date": window[-1].date.isoformat(),
        "closes": [{"date": p.date.isoformat(), "close": round(p.close, 4)} for p in sampled],
        "min": round(min(p.close for p in window), 4), "max": round(max(p.close for p in window), 4),
        "performance_pct": performance([p.close for p in window], len(window) - 1),
        "indicators": {"rsi14": _last(rsi(values)), "sma50": _last(sma(values, 50)), "sma200": _last(sma(values, 200)),
                       "macd": _last(m.macd), "macd_signal": _last(m.signal)},
    }


def _top(db: Session, user: User, args: dict) -> list[dict]:
    return [{"rank": i + 1, **item.model_dump(mode="json", include={
        "yahoo_ticker", "symbol", "name", "sector", "price", "change_pct", "score", "technical", "fundamental",
        "reasons", "perf_1m", "perf_1y", "pe", "dividend_yield"})}
            for i, item in enumerate(get_top(10, db=db, user=user))]


def _portfolio(db: Session, user: User, args: dict) -> dict:
    return get_portfolio(db=db, user=user).model_dump(mode="json")


def _simulate(db: Session, user: User, args: dict) -> dict:
    amount = args.get("amount")
    if not isinstance(amount, (int, float)) or not 0 < amount <= 1_000_000:
        raise ToolError("Montant invalide : entre 0 et 1 000 000 €.")
    try:
        start = date.fromisoformat(str(args.get("date")))
    except ValueError:
        raise ToolError("Date invalide : format AAAA-MM-JJ attendu.") from None
    if start >= paris_today():
        raise ToolError("La date doit être dans le passé.")
    security = _resolve(db, args.get("ticker"))
    return simulate_since(db, user.id, security.id, float(amount), start).model_dump(mode="json")


_HANDLERS = {"search_securities": _search, "get_security_overview": _overview, "get_price_history": _history,
             "get_top10": _top, "get_portfolio": _portfolio, "simulate_past_investment": _simulate}


def run_tool(db: Session, user: User, name: str, tool_input: dict) -> dict | list:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ToolError(f"Outil inconnu : {name}")
    if not isinstance(tool_input, dict):
        raise ToolError("Paramètres invalides.")
    return handler(db, user, tool_input)
```
Run: `docker compose ... run --rm -T api pytest -q tests/test_assistant_tools.py` → PASS ; suite complète → PASS (y compris les tests `simulate` existants).

- [ ] **Step 4: Commit**
```bash
git add -A backend && git commit -m "feat: assistant tools over app data (search, overview, history, top 10, portfolio, simulation)"
```

---

### Task 4: Boucle Claude + flux SSE + erreurs lisibles

**Files:**
- Create: `backend/app/services/assistant/prompt.py`, `backend/app/services/assistant/chat.py`, `backend/tests/fake_llm.py`
- Modify: `backend/app/api/deps.py`, `backend/app/api/routes/assistant.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_assistant_chat.py`

**Interfaces:**
- Consumes: `TOOL_SPECS`, `run_tool`, `ToolError`, `tool_label`, `get_model`, `Usage`, `estimate_cost`, `FALLBACK_BETA`, `claude_history`, `resolve_api_key`, `owned_conversation`, `message_out`, `conversation_out`, `DEFAULT_TITLE`.
- Produces:
  - `system_prompt(today: date, min_orders: int, security: Security | None) -> str`
  - `class ChatRun(llm, *, model: AssistantModel, system: str, history: list[dict], execute_tool: Callable[[str, dict, str], dict], max_tokens: int, max_rounds: int)` avec `events() -> Iterator[dict]` (événements `{"type": "text", "text"}` et `{"type": "tool", "name", "label"}`), attributs après itération : `text: str` (propriété), `tools: list[str]`, `usage: Usage`, `completed: bool`, `interrupted: bool`, `error: str | None`.
  - `friendly_error(exc: Exception) -> str`
  - `get_llm_factory() -> Callable[[str], LLM]` (dépendance ; vrai client = `anthropic.Anthropic(api_key=key, max_retries=2).beta.messages`)
  - SSE : `data: <json>\n\n` ; événements `start` (`user_message`), `text`, `tool`, `error` (`message`), `done` (`message`: MessageOut, `conversation`: ConversationOut).
  - Erreurs HTTP avant flux : 404 conversation inconnue ; 409 `"Aucune clé API Claude n'est configurée. Ajoutez-la dans les Réglages."`.

- [ ] **Step 1: Faux client LLM de test**

`backend/tests/fake_llm.py` :
```python
from types import SimpleNamespace


def text_turn(*chunks: str, stop_reason: str = "end_turn", input_tokens: int = 100, output_tokens: int = 50):
    return {"events": [SimpleNamespace(type="text", text=c) for c in chunks],
            "content": [SimpleNamespace(type="text", text="".join(chunks))], "stop_reason": stop_reason,
            "usage": SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)}


def tool_turn(name: str, tool_input: dict, tool_id: str = "toolu_1", server: bool = False):
    block_type = "server_tool_use" if server else "tool_use"
    block = SimpleNamespace(type=block_type, name=name, input=tool_input, id=tool_id)
    return {"events": [SimpleNamespace(type="content_block_start", content_block=block)], "content": [block],
            "stop_reason": "pause_turn" if server else "tool_use",
            "usage": SimpleNamespace(input_tokens=100, output_tokens=20)}


def error_turn(exc: Exception, *chunks: str):
    return {"events": [SimpleNamespace(type="text", text=c) for c in chunks], "raise": exc}


class _Stream:
    def __init__(self, turn):
        self.turn = turn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        yield from self.turn["events"]
        if "raise" in self.turn:
            raise self.turn["raise"]

    def get_final_message(self):
        return SimpleNamespace(content=self.turn["content"], stop_reason=self.turn["stop_reason"], usage=self.turn["usage"])


class FakeLLM:
    """Remplace client.beta.messages : rejoue des tours scriptés et garde les paramètres reçus."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.calls: list[dict] = []
        self.api_keys: list[str] = []

    def stream(self, **params):
        self.calls.append({**params, "messages": list(params["messages"])})
        return _Stream(self.turns.pop(0))
```
`backend/tests/conftest.py` : ajouter une fixture `fake_llm` (liste de tours à définir par test) et brancher `get_llm_factory` dans `client` :
```python
@pytest.fixture
def fake_llm():
    from tests.fake_llm import FakeLLM

    return FakeLLM()
```
et dans `client`, après les autres overrides :
```python
    from app.api.deps import get_llm_factory

    def factory():
        def make(api_key: str):
            fake_llm.api_keys.append(api_key)
            return fake_llm
        return make

    app.dependency_overrides[get_llm_factory] = factory
```
(ajouter `fake_llm` aux paramètres de la fixture `client`).

- [ ] **Step 2: Tests (échouent)**

`backend/tests/test_assistant_chat.py` :
```python
import json

import anthropic
import httpx
import pytest

from app.core.config import get_settings
from app.models import ChatMessage, Conversation
from app.services.assistant.chat import friendly_error
from tests.factories import make_security
from tests.fake_llm import error_turn, text_turn, tool_turn

KEY = "sk-ant-test-1234567890abcdef"


@pytest.fixture(autouse=True)
def configured(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_secret", "test-secret")
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    client.put("/api/assistant/settings", json={"api_key": KEY, "model": "claude-opus-5"})


def events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.split("\n") if line.startswith("data: ")]


def new_conversation(client, **body) -> int:
    return client.post("/api/assistant/conversations", json=body).json()["id"]


def send(client, cid, content="Bonjour"):
    return client.post(f"/api/assistant/conversations/{cid}/messages", json={"content": content})


def test_streams_text_and_persists_both_messages(client, db, fake_llm):
    fake_llm.turns = [text_turn("Bon", "jour !", input_tokens=1000, output_tokens=2000)]
    cid = new_conversation(client)
    response = send(client, cid, "Salut, qui es-tu ?")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    evts = events(response)
    assert [e["type"] for e in evts] == ["start", "text", "text", "done"]
    assert evts[0]["user_message"]["content"] == "Salut, qui es-tu ?"
    done = evts[-1]
    assert done["message"]["content"] == "Bonjour !" and done["message"]["interrupted"] is False
    assert done["message"]["cost_usd"] == pytest.approx(0.001 * 5 + 0.002 * 25, abs=1e-4)
    assert done["conversation"]["title"] == "Salut, qui es-tu ?" and done["conversation"]["output_tokens"] == 2000
    assert fake_llm.api_keys == [KEY]
    call = fake_llm.calls[0]
    assert call["model"] == "claude-opus-5" and call["thinking"] == {"type": "adaptive"}
    assert call["betas"] == ["server-side-fallback-2026-07-01"] and call["extra_body"] == {"fallbacks": "default"}
    assert {"type": "web_search_20260209", "name": "web_search", "max_uses": 3} in call["tools"]
    assert "français" in call["system"] and call["messages"] == [{"role": "user", "content": "Salut, qui es-tu ?"}]
    detail = client.get(f"/api/assistant/conversations/{cid}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


def test_tool_loop_runs_tools_and_sends_results(client, db, fake_llm):
    make_security(db, "MC.PA", name="LVMH")
    fake_llm.turns = [tool_turn("get_security_overview", {"ticker": "MC.PA"}), text_turn("LVMH va bien.")]
    evts = events(send(client, new_conversation(client), "Et LVMH ?"))
    assert {"type": "tool", "name": "get_security_overview", "label": "Fiche du titre"} in evts
    second = fake_llm.calls[1]["messages"]
    result = second[-1]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "toolu_1" and "LVMH" in result["content"]
    assert "is_error" not in result
    assert evts[-1]["message"]["tools"] == ["get_security_overview"]


def test_tool_error_is_sent_back_as_is_error(client, fake_llm):
    fake_llm.turns = [tool_turn("get_security_overview", {"ticker": "NOPE"}), text_turn("Introuvable.")]
    send(client, new_conversation(client))
    result = fake_llm.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and "introuvable" in result["content"]


def test_pause_turn_is_resumed(client, fake_llm):
    fake_llm.turns = [tool_turn("web_search", {"query": "LVMH"}, server=True), text_turn("Selon la presse…")]
    evts = events(send(client, new_conversation(client)))
    assert {"type": "tool", "name": "web_search", "label": "Recherche web"} in evts
    assert fake_llm.calls[1]["messages"][-1]["role"] == "assistant"
    assert evts[-1]["message"]["content"] == "Selon la presse…"


def _status_error(cls, status):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(message=f"Error code: {status} {KEY}", response=httpx.Response(status, request=request), body=None)


def test_api_error_mid_stream_keeps_partial_text(client, db, fake_llm):
    fake_llm.turns = [error_turn(_status_error(anthropic.InternalServerError, 529), "Début de réponse")]
    cid = new_conversation(client)
    evts = events(send(client, cid))
    assert [e["type"] for e in evts] == ["start", "text", "error", "done"]
    assert "indisponible" in evts[2]["message"]
    saved = evts[-1]["message"]
    assert saved["content"] == "Début de réponse" and saved["interrupted"] is True and "indisponible" in saved["error"]


def test_error_message_does_not_leak_key(client, fake_llm):
    fake_llm.turns = [error_turn(_status_error(anthropic.AuthenticationError, 401))]
    response = send(client, new_conversation(client))
    assert KEY not in response.text and "Clé API invalide" in response.text


@pytest.mark.parametrize("cls,status,expected", [
    (anthropic.AuthenticationError, 401, "Clé API invalide"),
    (anthropic.PermissionDeniedError, 403, "accès"),
    (anthropic.NotFoundError, 404, "Modèle"),
    (anthropic.RateLimitError, 429, "Limite"),
    (anthropic.APIStatusError, 402, "Crédit"),
    (anthropic.InternalServerError, 500, "indisponible"),
])
def test_friendly_errors(cls, status, expected):
    assert expected in friendly_error(_status_error(cls, status))


def test_friendly_error_connection():
    exc = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    assert "indisponible" in friendly_error(exc)


def test_refusal_is_explained(client, fake_llm):
    fake_llm.turns = [text_turn(stop_reason="refusal")]
    evts = events(send(client, new_conversation(client)))
    assert evts[-2]["type"] == "error" and "refusé" in evts[-2]["message"]


def test_history_and_security_context_sent(client, db, fake_llm):
    s = make_security(db, "MC.PA", name="LVMH")
    cid = new_conversation(client, security_id=s.id)
    fake_llm.turns = [text_turn("Premier."), text_turn("Second.")]
    send(client, cid, "Q1")
    send(client, cid, "Q2")
    call = fake_llm.calls[1]
    assert call["messages"] == [{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "Premier."},
                                {"role": "user", "content": "Q2"}]
    assert "LVMH" in call["system"] and "MC.PA" in call["system"]
    assert client.get(f"/api/assistant/conversations/{cid}").json()["title"] == "À propos de LVMH"


def test_haiku_has_no_thinking_nor_fallback(client, fake_llm):
    client.put("/api/assistant/settings", json={"model": "claude-haiku-4-5"})
    fake_llm.turns = [text_turn("ok")]
    send(client, new_conversation(client))
    call = fake_llm.calls[0]
    assert "thinking" not in call and "betas" not in call and "extra_body" not in call
    assert {"type": "web_search_20250305", "name": "web_search", "max_uses": 3} in call["tools"]


def test_no_key_is_409(client, db, fake_llm):
    client.put("/api/assistant/settings", json={"remove_key": True, "model": "claude-opus-5"})
    response = send(client, new_conversation(client))
    assert response.status_code == 409 and "Réglages" in response.json()["detail"]
    assert db.query(ChatMessage).count() == 0


def test_round_limit_stops_with_error(client, fake_llm, monkeypatch):
    monkeypatch.setattr(get_settings(), "assistant_max_rounds", 2)
    fake_llm.turns = [tool_turn("get_top10", {}, "t1"), tool_turn("get_top10", {}, "t2")]
    evts = events(send(client, new_conversation(client)))
    assert evts[-2]["type"] == "error" and "étapes" in evts[-2]["message"]


def test_blank_message_is_422(client):
    assert send(client, new_conversation(client), "   ").status_code == 422
```
Run: `docker compose ... run --rm -T api pytest -q tests/test_assistant_chat.py`
Expected: FAIL (`ImportError: get_llm_factory` / `app.services.assistant.chat`).

- [ ] **Step 3: Consigne système**

`backend/app/services/assistant/prompt.py` :
```python
from datetime import date

from app.models import Security

BASE = """Tu es l'assistant de PEA Radar, une application personnelle qui aide un investisseur débutant à choisir des actions pour son PEA (Crédit Agricole, formule Invest Store Intégral) et à suivre son portefeuille.

Date du jour : {today} (heure de Paris).

Règles :
- Réponds en français, de façon pédagogique et concise ; explique simplement chaque terme technique (PER, RSI, PRU…).
- Pour tout chiffre (cours, score, portefeuille, performance), appuie-toi sur les outils et cite l'horodatage des données (champs as_of, computed_at, date).
- Distingue clairement les faits (données) de ton opinion.
- Ne présente jamais une prévision comme certaine.
- Quand tu donnes un avis sur un achat ou une vente, rappelle qu'il ne s'agit pas d'un conseil en investissement réglementé.
- Utilise la recherche web pour l'actualité récente et cite tes sources.
- Contexte PEA : seuls les titres éligibles peuvent être achetés ; les frais de courtage suivent la grille de l'utilisateur ; il doit passer au moins {min_orders} ordres par an, sinon il paie des frais.
- Mise en forme : Markdown simple (titres courts, listes, tableaux si utile).
- Quand tu utilises un outil, tu peux dire une courte phrase avant. Si aucun outil ne permet de répondre, dis-le au lieu de deviner. N'inclus pas de balises XML internes ou système dans ta réponse."""


def system_prompt(today: date, min_orders: int, security: Security | None) -> str:
    text = BASE.format(today=today.strftime("%d/%m/%Y"), min_orders=min_orders)
    if security is not None:
        text += (f"\n\nContexte : l'utilisateur consulte la fiche de {security.name} "
                 f"(ticker {security.yahoo_ticker}). Ses questions portent a priori sur ce titre.")
    return text
```

- [ ] **Step 4: Boucle `ChatRun` et erreurs**

`backend/app/services/assistant/chat.py` :
```python
import logging
from collections.abc import Callable, Iterator
from typing import Any, Protocol

import anthropic

from app.services.assistant.catalog import FALLBACK_BETA, AssistantModel, Usage
from app.services.assistant.tools import TOOL_SPECS, tool_label

logger = logging.getLogger(__name__)
REFUSAL = "Claude a refusé de répondre à cette demande. Reformulez votre question."
TRUNCATED = "La réponse a été coupée car elle était trop longue."
TOO_MANY_STEPS = "L'assistant a atteint la limite d'étapes pour cette question. Posez une question plus précise."
UNAVAILABLE = "Le service Claude est momentanément indisponible. Réessayez dans un instant."


class LLM(Protocol):
    def stream(self, **params: Any) -> Any: ...


def friendly_error(exc: Exception) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "Clé API invalide ou révoquée. Vérifiez-la dans les Réglages."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "Cette clé API n'a pas accès au modèle choisi. Changez de modèle dans les Réglages."
    if isinstance(exc, anthropic.NotFoundError):
        return "Modèle introuvable. Choisissez un autre modèle dans les Réglages."
    if isinstance(exc, anthropic.RateLimitError):
        return "Limite d'utilisation de l'API atteinte. Patientez quelques minutes puis réessayez."
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.InternalServerError)):
        return UNAVAILABLE
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 402:
            return "Crédit insuffisant sur votre compte Anthropic. Rechargez-le sur console.anthropic.com."
        if exc.status_code == 529 or exc.status_code >= 500:
            return UNAVAILABLE
        return f"L'API Claude a refusé la requête (erreur {exc.status_code})."
    return "Erreur inattendue de l'assistant."


class ChatRun:
    def __init__(self, llm: LLM, *, model: AssistantModel, system: str, history: list[dict],
                 execute_tool: Callable[[str, dict, str], dict], max_tokens: int, max_rounds: int) -> None:
        self.llm, self.model, self.system, self.history = llm, model, system, history
        self.execute_tool, self.max_tokens, self.max_rounds = execute_tool, max_tokens, max_rounds
        self.parts: list[str] = []
        self.tools: list[str] = []
        self.usage = Usage()
        self.completed = False
        self.interrupted = False
        self.error: str | None = None

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def _params(self, messages: list) -> dict:
        tools = [*TOOL_SPECS, {"type": self.model.web_search_type, "name": "web_search", "max_uses": 3}]
        params: dict = dict(model=self.model.id, max_tokens=self.max_tokens, system=self.system,
                            messages=messages, tools=tools)
        if self.model.adaptive_thinking:
            params["thinking"] = {"type": "adaptive"}
        if self.model.fallback:
            params["betas"] = [FALLBACK_BETA]
            params["extra_body"] = {"fallbacks": self.model.fallback}
        return params

    def events(self) -> Iterator[dict]:
        messages: list = list(self.history)
        try:
            for _ in range(self.max_rounds):
                new_round = True
                with self.llm.stream(**self._params(messages)) as stream:
                    for event in stream:
                        if event.type == "text" and event.text:
                            if new_round and self.parts and not self.text.endswith("\n"):
                                self.parts.append("\n\n")  # sépare le texte de deux tours
                            new_round = False
                            self.parts.append(event.text)
                            yield {"type": "text", "text": event.text}
                        elif event.type == "content_block_start" and event.content_block.type in ("tool_use", "server_tool_use"):
                            name = event.content_block.name
                            self.tools.append(name)
                            yield {"type": "tool", "name": name, "label": tool_label(name)}
                    final = stream.get_final_message()
                self.usage.add(final.usage)
                if final.stop_reason == "refusal":
                    self.error = REFUSAL
                    return
                if final.stop_reason == "pause_turn":
                    messages.append({"role": "assistant", "content": final.content})
                    continue
                tool_uses = [b for b in final.content if b.type == "tool_use"]
                if final.stop_reason == "max_tokens":
                    self.error = TRUNCATED
                    return
                if not tool_uses:
                    self.completed = True
                    return
                messages.append({"role": "assistant", "content": final.content})
                messages.append({"role": "user", "content": [self.execute_tool(b.name, b.input, b.id) for b in tool_uses]})
            self.error = TOO_MANY_STEPS
        except Exception as exc:  # erreurs API ou réseau : message lisible, sans détails techniques
            logger.warning("Assistant error: %s", type(exc).__name__)
            self.error = friendly_error(exc)
```
Note : le log ne contient que le nom de la classe d'exception (le message d'une erreur API peut reprendre des en-têtes).

- [ ] **Step 5: Dépendance LLM et route SSE**

`backend/app/api/deps.py` :
```python
def get_llm_factory():
    """Fabrique le client Claude pour une clé donnée ; remplacée par un faux client en test."""
    import anthropic

    def make(api_key: str):
        return anthropic.Anthropic(api_key=api_key, max_retries=2).beta.messages

    return make
```
Remplacer la route provisoire `send_message` dans `routes/assistant.py` :
```python
def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _tool_executor(db: Session, user: User) -> Callable[[str, dict, str], dict]:
    def execute(name: str, tool_input: dict, tool_use_id: str) -> dict:
        try:
            content = json.dumps(run_tool(db, user, name, tool_input), ensure_ascii=False, default=str)
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
        except ToolError as exc:
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": str(exc), "is_error": True}
        except Exception:
            logger.exception("Tool %s failed", name)
            db.rollback()
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": "Erreur interne de l'outil.", "is_error": True}
    return execute


@router.post("/assistant/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: int, payload: MessageIn, db: Session = Depends(get_db), user: User = Depends(get_current_user),
    llm_factory: Callable = Depends(get_llm_factory),
) -> StreamingResponse:
    conv = owned_conversation(db, user.id, conversation_id)
    row = get_user_settings(db, user.id)
    api_key, _ = resolve_api_key(row)
    if not api_key:
        raise HTTPException(status_code=409, detail="Aucune clé API Claude n'est configurée. Ajoutez-la dans les Réglages.")
    config = get_settings()
    model = get_model(row.ai_model)
    security = db.get(Security, conv.security_id) if conv.security_id else None
    history = claude_history([*conversation_messages(db, conv.id), ChatMessage(role="user", content=payload.content)])
    user_msg = ChatMessage(conversation_id=conv.id, role="user", content=payload.content, tools=[])
    db.add(user_msg)
    if conv.title == DEFAULT_TITLE:
        conv.title = payload.content[:60] + ("…" if len(payload.content) > 60 else "")
    db.commit()
    run = ChatRun(llm_factory(api_key), model=model, system=system_prompt(paris_today(), row.min_orders_per_year, security),
                  history=history, execute_tool=_tool_executor(db, user),
                  max_tokens=config.assistant_max_tokens, max_rounds=config.assistant_max_rounds)

    def save() -> ChatMessage:
        cost = estimate_cost(model, run.usage)
        msg = ChatMessage(conversation_id=conv.id, role="assistant", content=run.text, tools=list(dict.fromkeys(run.tools)),
                          input_tokens=run.usage.input_tokens, output_tokens=run.usage.output_tokens, cost_usd=cost,
                          model=model.id, interrupted=not run.completed, error=run.error)
        db.add(msg)
        conv.input_tokens += run.usage.input_tokens
        conv.output_tokens += run.usage.output_tokens
        conv.cost_usd += cost
        conv.updated_at = func.now()
        db.commit()
        return msg

    def stream() -> Iterator[str]:
        saved = False
        try:
            yield _sse({"type": "start", "user_message": message_out(user_msg).model_dump(mode="json")})
            for event in run.events():
                yield _sse(event)
            if run.error:
                yield _sse({"type": "error", "message": run.error})
            msg = save()
            saved = True
            yield _sse({"type": "done", "message": message_out(msg).model_dump(mode="json"),
                        "conversation": conversation_out(db, conv).model_dump(mode="json")})
        finally:
            if not saved:  # navigateur déconnecté en plein flux : on garde ce qui a été reçu
                run.error = run.error or "Réponse interrompue."
                save()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```
Imports nécessaires : `json`, `Callable`, `Iterator`, `func` (sqlalchemy), `StreamingResponse`, `get_llm_factory`, `paris_today`, `ChatRun`, `system_prompt`, `estimate_cost`, `run_tool`, `ToolError`, `claude_history`, `conversation_messages`, `ChatMessage`, `Security`.

Run: `docker compose ... run --rm -T api pytest -q tests/test_assistant_chat.py` → PASS ; suite complète → PASS.

- [ ] **Step 6: Commit**
```bash
git add -A backend && git commit -m "feat: Claude chat loop with tools, SSE streaming, cost tracking and readable errors"
```

---

### Task 5: Frontend — client SSE, types, réglages IA

**Files:**
- Modify: `frontend/src/lib/api/client.ts`, `frontend/src/lib/api/schema.d.ts` (régénéré), `frontend/src/features/settings/SettingsPage.tsx`, `frontend/src/features/settings/SettingsPage.test.tsx`
- Create: `frontend/src/features/settings/AssistantSettingsCard.tsx`, `frontend/src/features/settings/AssistantSettingsCard.test.tsx`, `frontend/src/lib/api/stream.test.ts`
- Modify: `frontend/src/test/utils.tsx` (helper `sseResponse`)

**Interfaces:**
- Produces:
  - Types `AssistantSettingsOut`, `ConversationOut`, `ConversationDetail`, `MessageOut`.
  - `type ChatEvent = {type:"start"; user_message: MessageOut} | {type:"text"; text: string} | {type:"tool"; name: string; label: string} | {type:"error"; message: string} | {type:"done"; message: MessageOut; conversation: ConversationOut}`
  - `streamSSE(path: string, body: unknown, onEvent: (e: ChatEvent) => void, signal?: AbortSignal): Promise<void>` (lève `ApiError` avec le `detail` du serveur si le statut n'est pas 2xx).
  - Test helper `sseResponse(events: unknown[], { split?: boolean }): Response`.
  - `AssistantSettingsCard` : champ mot de passe `Clé API Claude`, statut « Configurée » / « Non configurée » / « Définie dans le fichier .env », select `Modèle IA`, boutons « Enregistrer » et « Supprimer la clé » ; query key `["assistant-settings"]`.

- [ ] **Step 1: Régénérer les types** — lancer l'API de dev (`docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d api`) puis `cd frontend && npm run gen:api`. Ajouter à `client.ts` :
```ts
export type AssistantSettingsOut = components["schemas"]["AssistantSettingsOut"];
export type ConversationOut = components["schemas"]["ConversationOut"];
export type ConversationDetail = components["schemas"]["ConversationDetail"];
export type MessageOut = components["schemas"]["MessageOut"];
```

- [ ] **Step 2: Tests `streamSSE` (échouent)**

`frontend/src/test/utils.tsx` :
```ts
export function sseResponse(events: unknown[], { split = false } = {}) {
  const text = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  const encoder = new TextEncoder();
  const chunks = split ? [text.slice(0, 7), text.slice(7, text.length - 3), text.slice(text.length - 3)] : [text];
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}
```
`frontend/src/lib/api/stream.test.ts` :
```ts
import { sseResponse } from "@/test/utils";
import { ApiError, streamSSE, type ChatEvent } from "./client";

afterEach(() => vi.unstubAllGlobals());

test("lit les événements même coupés au milieu d'un paquet", async () => {
  const fetchMock = vi.fn(async () => sseResponse([{ type: "text", text: "Bon" }, { type: "text", text: "jour" }], { split: true }));
  vi.stubGlobal("fetch", fetchMock);
  const seen: ChatEvent[] = [];
  await streamSSE("/api/x", { content: "a" }, (e) => seen.push(e));
  expect(seen).toEqual([{ type: "text", text: "Bon" }, { type: "text", text: "jour" }]);
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", body: JSON.stringify({ content: "a" }) });
});

test("renvoie le message du serveur en cas de refus", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Aucune clé API Claude n'est configurée." }), { status: 409 })));
  await expect(streamSSE("/api/x", {}, () => {})).rejects.toEqual(new ApiError(409, "Aucune clé API Claude n'est configurée."));
});
```
Run: `cd frontend && npx vitest run src/lib/api/stream.test.ts` → FAIL (`streamSSE` n'existe pas).

- [ ] **Step 3: Implémenter `streamSSE`** dans `client.ts` :
```ts
export type ChatEvent =
  | { type: "start"; user_message: MessageOut }
  | { type: "text"; text: string }
  | { type: "tool"; name: string; label: string }
  | { type: "error"; message: string }
  | { type: "done"; message: MessageOut; conversation: ConversationOut };

export async function streamSSE(path: string, body: unknown, onEvent: (event: ChatEvent) => void, signal?: AbortSignal): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw await errorFrom(response, path);
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index;
    while ((index = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const data = block.split("\n").filter((line) => line.startsWith("data: ")).map((line) => line.slice(6)).join("\n");
      if (data) onEvent(JSON.parse(data) as ChatEvent);
    }
  }
}
```
Run the Step 2 command → PASS (2 tests).

- [ ] **Step 4: Tests de la carte réglages IA (échouent)**

`frontend/src/features/settings/AssistantSettingsCard.test.tsx` :
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { AssistantSettingsCard } from "./AssistantSettingsCard";

afterEach(() => vi.unstubAllGlobals());
const MODELS = [{ id: "claude-opus-5", label: "Claude Opus 5 (recommandé)" }, { id: "claude-sonnet-5", label: "Claude Sonnet 5 (plus rapide)" }];
const settings = (configured: boolean, source: string | null = configured ? "settings" : null) =>
  ({ configured, source, model: "claude-opus-5", models: MODELS });

test("enregistre la clé et le modèle sans jamais réafficher la clé", async () => {
  const fetchMock = mockFetch((url) => ({ body: url === "/api/assistant/settings" ? settings(false) : {} }));
  renderWithProviders(<AssistantSettingsCard />);
  expect(await screen.findByText("Non configurée")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Clé API Claude"), "sk-ant-test-1234567890abcdef");
  await userEvent.selectOptions(screen.getByLabelText("Modèle IA"), "claude-sonnet-5");
  fetchMock.mockImplementation(async () => new Response(JSON.stringify({ ...settings(true), model: "claude-sonnet-5" }), { status: 200 }));
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(screen.getByText("Configurée")).toBeInTheDocument());
  const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")!;
  expect(JSON.parse(put[1]!.body as string)).toEqual({ api_key: "sk-ant-test-1234567890abcdef", model: "claude-sonnet-5" });
  expect(screen.getByLabelText("Clé API Claude")).toHaveValue("");
});

test("clé définie dans le fichier .env", async () => {
  mockFetch(() => ({ body: settings(true, "env") }));
  renderWithProviders(<AssistantSettingsCard />);
  expect(await screen.findByText("Définie dans le fichier .env")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Supprimer la clé" })).not.toBeInTheDocument();
});

test("supprimer la clé", async () => {
  const fetchMock = mockFetch(() => ({ body: settings(true) }));
  renderWithProviders(<AssistantSettingsCard />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer la clé" }));
  const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")!;
  expect(JSON.parse(put[1]!.body as string)).toEqual({ remove_key: true, model: "claude-opus-5" });
});
```
Run: `npx vitest run src/features/settings/AssistantSettingsCard.test.tsx` → FAIL (module introuvable).

- [ ] **Step 5: Implémenter `AssistantSettingsCard`**

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, apiSend, type AssistantSettingsOut } from "@/lib/api/client";

const STATUS = { settings: "Configurée", env: "Définie dans le fichier .env" } as const;

export function AssistantSettingsCard() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["assistant-settings"], queryFn: () => apiGet<AssistantSettingsOut>("/api/assistant/settings") });
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (body: object) => apiSend("PUT", "/api/assistant/settings", body) as Promise<AssistantSettingsOut>,
    onSuccess: (next) => {
      queryClient.setQueryData(["assistant-settings"], next);
      setApiKey("");
      setError(null);
      toast.success("Réglages de l'assistant enregistrés");
    },
    onError: (err) => setError(err.message),
  });
  if (!data) return null;
  const selected = model ?? data.model;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Assistant IA (Claude)</CardTitle>
        <p className="text-sm text-muted-foreground">
          Créez une clé sur console.anthropic.com (rubrique API Keys). Elle est chiffrée sur votre ordinateur et n'est jamais
          renvoyée au navigateur. Chaque question est facturée par Anthropic selon le modèle choisi.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2 text-sm">
          Statut : <Badge variant={data.configured ? "default" : "secondary"}>{data.source ? STATUS[data.source] : "Non configurée"}</Badge>
        </div>
        <form className="flex flex-wrap items-end gap-3"
              onSubmit={(e) => { e.preventDefault(); save.mutate({ ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}), model: selected }); }}>
          <label className="space-y-1 text-xs font-medium text-muted-foreground">
            Clé API Claude
            <Input type="password" autoComplete="off" className="w-96 bg-white" placeholder={data.configured ? "•••••••• (laisser vide pour la garder)" : "sk-ant-…"}
                   value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          </label>
          <label className="space-y-1 text-xs font-medium text-muted-foreground">
            Modèle IA
            <select value={selected} onChange={(e) => setModel(e.target.value)} className="block h-8 rounded-lg border border-input bg-white px-2 text-sm text-foreground">
              {data.models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </label>
          <Button type="submit" disabled={save.isPending}>Enregistrer</Button>
          {data.source === "settings" && (
            <Button type="button" variant="outline" disabled={save.isPending} onClick={() => save.mutate({ remove_key: true, model: selected })}>
              Supprimer la clé
            </Button>
          )}
        </form>
        {error && <p role="alert" className="text-sm text-down">{error}</p>}
      </CardContent>
    </Card>
  );
}
```
Les `<label>` englobant l'`<Input>` donnent le nom accessible « Clé API Claude » / « Modèle IA ».
`SettingsPage.tsx` : afficher `<AssistantSettingsCard />` avant `<FeeSettingsCard />` ; remplacer la phrase d'en-tête par « Assistant IA, frais de votre caisse régionale et corrections d'éligibilité. » ; `SettingsPage.test.tsx` : ajouter un mock `/api/assistant/settings` dans le handler existant.

Run: `npx vitest run src/features/settings` → PASS ; `npm test` → PASS.

- [ ] **Step 6: Commit**
```bash
git add -A frontend && git commit -m "feat: SSE client and assistant settings card (API key, model)"
```

---

### Task 6: Frontend — chat (hook de streaming, messages Markdown, page Assistant)

**Files:**
- Modify: `frontend/package.json` (`react-markdown`, `remark-gfm`), `frontend/src/app/router.tsx`, `frontend/src/app/router.test.tsx`
- Create: `frontend/src/features/assistant/api.ts`, `useChat.ts`, `Markdown.tsx`, `ChatMessages.tsx`, `Composer.tsx`, `suggestions.ts`, `ChatView.tsx`, `AssistantPage.tsx`, `ChatView.test.tsx`, `AssistantPage.test.tsx`

**Interfaces:**
- Consumes: `streamSSE`, `ChatEvent`, types de Task 5.
- Produces:
  - `api.ts` : `useAssistantSettings()`, `useConversations()` (`["conversations"]`), `useConversation(id: number | null)` (`["conversation", id]`, désactivé si null), `useDeleteConversation()`, `createConversation(securityId?: number): Promise<ConversationOut>`.
  - `useChat({ conversationId, securityId, onConversationCreated })` → `{ pending: PendingTurn | null, send(content: string): Promise<void>, stop(): void, streaming: boolean }`, `PendingTurn = { user: string; text: string; tools: string[]; error: string | null; interrupted: boolean }`.
  - `ChatView({ conversationId, securityId?, securityName?, onConversationCreated, compact? })`.
  - `SECURITY_SUGGESTIONS: string[]` (4 questions de la spec), `GENERAL_SUGGESTIONS: string[]`.
  - Route `/assistant` → `AssistantPage` (conversation sélectionnée dans `?c=<id>`).

- [ ] **Step 1: Dépendances** : `cd frontend && npm install react-markdown remark-gfm`.

- [ ] **Step 2: Tests (échouent)**

`frontend/src/features/assistant/ChatView.test.tsx` :
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, sseResponse } from "@/test/utils";
import { ChatView } from "./ChatView";

afterEach(() => vi.unstubAllGlobals());
const CONFIGURED = { configured: true, source: "settings", model: "claude-opus-5", models: [] };
const conv = (messages: unknown[] = []) => ({ id: 5, title: "Nouvelle conversation", security_id: null, security_name: null, security_symbol: null,
  input_tokens: 0, output_tokens: 0, cost_usd: 0.0123, created_at: "2026-09-26T10:00:00Z", updated_at: "2026-09-26T10:00:00Z", messages });
const msg = (id: number, role: string, content: string, extra = {}) =>
  ({ id, role, content, tools: [], interrupted: false, error: null, cost_usd: 0, created_at: "2026-09-26T10:00:00Z", ...extra });

function stubFetch(handler: (url: string, init?: RequestInit) => Response | undefined) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => handler(String(input), init) ?? new Response("{}", { status: 404 }));
  vi.stubGlobal("fetch", fn);
  return fn;
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

test("crée la conversation, affiche la réponse en streaming puis la version enregistrée", async () => {
  let saved = false;
  const onCreated = vi.fn();
  stubFetch((url, init) => {
    if (url === "/api/assistant/settings") return json(CONFIGURED);
    if (url === "/api/assistant/conversations" && init?.method === "POST") return json(conv(), 201);
    if (url === "/api/assistant/conversations/5/messages") {
      saved = true;
      return sseResponse([
        { type: "start", user_message: msg(1, "user", "Analyse LVMH") },
        { type: "tool", name: "get_security_overview", label: "Fiche du titre" },
        { type: "text", text: "**LVMH** est " }, { type: "text", text: "solide." },
        { type: "done", message: msg(2, "assistant", "**LVMH** est solide."), conversation: conv() },
      ]);
    }
    if (url === "/api/assistant/conversations/5") return json(conv(saved ? [msg(1, "user", "Analyse LVMH"), msg(2, "assistant", "**LVMH** est solide.", { tools: ["get_security_overview"] })] : []));
    return undefined;
  });
  renderWithProviders(<ChatView conversationId={null} onConversationCreated={onCreated} />);
  await userEvent.type(await screen.findByLabelText("Votre question"), "Analyse LVMH{Enter}");
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(5));
  expect(await screen.findByText("LVMH", { selector: "strong" })).toBeInTheDocument();
  expect(screen.getByText(/Fiche du titre/)).toBeInTheDocument();
  expect(screen.getByLabelText("Votre question")).toHaveValue("");
});

test("affiche l'erreur et la mention « réponse interrompue »", async () => {
  stubFetch((url) => {
    if (url === "/api/assistant/settings") return json(CONFIGURED);
    if (url === "/api/assistant/conversations/5") return json(conv([msg(1, "user", "Q"), msg(2, "assistant", "Début", { interrupted: true, error: "Le service Claude est momentanément indisponible." })]));
    return undefined;
  });
  renderWithProviders(<ChatView conversationId={5} onConversationCreated={() => {}} />);
  expect(await screen.findByText("réponse interrompue")).toBeInTheDocument();
  expect(screen.getByText(/momentanément indisponible/)).toBeInTheDocument();
});

test("sans clé API : explication et lien vers les Réglages", async () => {
  stubFetch((url) => (url === "/api/assistant/settings" ? json({ ...CONFIGURED, configured: false, source: null }) : undefined));
  renderWithProviders(<ChatView conversationId={null} onConversationCreated={() => {}} />);
  expect(await screen.findByRole("link", { name: "Ouvrir les Réglages" })).toHaveAttribute("href", "/reglages");
  expect(screen.queryByLabelText("Votre question")).not.toBeInTheDocument();
});

test("questions prêtes pour un titre", async () => {
  stubFetch((url) => (url === "/api/assistant/settings" ? json(CONFIGURED) : undefined));
  renderWithProviders(<ChatView conversationId={null} securityId={1} securityName="LVMH" onConversationCreated={() => {}} />);
  expect(await screen.findByRole("button", { name: "Pourquoi est-elle dans le top 10 ?" })).toBeInTheDocument();
});
```
`frontend/src/features/assistant/AssistantPage.test.tsx` :
```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { AssistantPage } from "./AssistantPage";

afterEach(() => vi.unstubAllGlobals());
const item = (id: number, title: string, cost: number) => ({ id, title, security_id: null, security_name: null, security_symbol: null,
  input_tokens: 0, output_tokens: 0, cost_usd: cost, created_at: "2026-09-26T10:00:00Z", updated_at: "2026-09-26T10:00:00Z" });

test("liste les conversations avec leur coût et ouvre celle choisie", async () => {
  mockFetch((url) => {
    if (url === "/api/assistant/settings") return { body: { configured: true, source: "settings", model: "claude-opus-5", models: [] } };
    if (url === "/api/assistant/conversations") return { body: [item(2, "Mon portefeuille", 0.0421), item(1, "À propos de LVMH", 0.003)] };
    if (url === "/api/assistant/conversations/2") return { body: { ...item(2, "Mon portefeuille", 0.0421), messages: [{ id: 9, role: "user", content: "Analyse mon portefeuille", tools: [], interrupted: false, error: null, cost_usd: 0, created_at: "2026-09-26T10:00:00Z" }] } };
    return { body: {} };
  });
  renderWithProviders(<AssistantPage />);
  expect(await screen.findByRole("heading", { level: 1, name: "Assistant IA" })).toBeInTheDocument();
  expect(await screen.findByText("≈ 0,04 $")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Mon portefeuille/ }));
  expect(await screen.findByText("Analyse mon portefeuille")).toBeInTheDocument();
});
```
Run: `npx vitest run src/features/assistant` → FAIL (modules introuvables).

- [ ] **Step 3: `api.ts`, `suggestions.ts`, `Markdown.tsx`**

`api.ts` :
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend, type AssistantSettingsOut, type ConversationDetail, type ConversationOut } from "@/lib/api/client";

export const useAssistantSettings = () =>
  useQuery({ queryKey: ["assistant-settings"], queryFn: () => apiGet<AssistantSettingsOut>("/api/assistant/settings") });

export const useConversations = () =>
  useQuery({ queryKey: ["conversations"], queryFn: () => apiGet<ConversationOut[]>("/api/assistant/conversations") });

export const useConversation = (id: number | null) =>
  useQuery({ queryKey: ["conversation", id], queryFn: () => apiGet<ConversationDetail>(`/api/assistant/conversations/${id}`), enabled: id !== null });

export const createConversation = (securityId?: number) =>
  apiSend("POST", "/api/assistant/conversations", { security_id: securityId ?? null }) as Promise<ConversationOut>;

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiSend("DELETE", `/api/assistant/conversations/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["conversations"] }),
  });
}
```
`suggestions.ts` :
```ts
export const SECURITY_SUGGESTIONS = [
  "Analyse cette action",
  "Pourquoi est-elle dans le top 10 ?",
  "Aurais-je dû l'acheter il y a une semaine ?",
  "Quels sont les risques ?",
];

export const GENERAL_SUGGESTIONS = [
  "Analyse mon portefeuille",
  "Explique-moi le top 10 du moment",
  "Combien d'ordres me reste-t-il à passer cette année ?",
  "C'est quoi le PER, simplement ?",
];
```
`Markdown.tsx` :
```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function Markdown({ text }: { text: string }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:font-semibold [&_ol]:list-decimal [&_ol]:pl-5 [&_ul]:list-disc [&_ul]:pl-5 [&_table]:w-full [&_table]:text-xs [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-2 [&_th]:py-1 [&_code]:rounded [&_code]:bg-muted [&_code]:px-1">
      <ReactMarkdown remarkPlugins={[remarkGfm]}
                     components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline">{children}</a> }}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 4: `useChat.ts`**
```ts
import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamSSE } from "@/lib/api/client";
import { createConversation } from "./api";

export type PendingTurn = { user: string; text: string; tools: string[]; error: string | null; interrupted: boolean };

type Options = { conversationId: number | null; securityId?: number; onConversationCreated: (id: number) => void };

export function useChat({ conversationId, securityId, onConversationCreated }: Options) {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [streaming, setStreaming] = useState(false);
  const controller = useRef<AbortController | null>(null);

  async function send(content: string) {
    const turn: PendingTurn = { user: content, text: "", tools: [], error: null, interrupted: false };
    setPending(turn);
    setStreaming(true);
    const abort = new AbortController();
    controller.current = abort;
    let id = conversationId;
    try {
      if (id === null) {
        id = (await createConversation(securityId)).id;
        onConversationCreated(id);
      } else {
        await queryClient.invalidateQueries({ queryKey: ["conversation", id] });  // efface une réponse interrompue affichée localement
      }
      await streamSSE(`/api/assistant/conversations/${id}/messages`, { content }, (event) => {
        if (event.type === "text") setPending((p) => p && { ...p, text: p.text + event.text });
        else if (event.type === "tool") setPending((p) => p && { ...p, tools: [...p.tools, event.label] });
        else if (event.type === "error") setPending((p) => p && { ...p, error: event.message, interrupted: true });
      }, abort.signal);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["conversation", id] }),
        queryClient.invalidateQueries({ queryKey: ["conversations"] }),
      ]);
      setPending(null);
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === "AbortError";
      setPending((p) => p && { ...p, interrupted: true, error: aborted ? null : (err as Error).message });
    } finally {
      setStreaming(false);
      controller.current = null;
    }
  }

  return { pending, streaming, send, stop: () => controller.current?.abort() };
}
```

- [ ] **Step 5: `ChatMessages.tsx`, `Composer.tsx`, `ChatView.tsx`**

`ChatMessages.tsx` :
```tsx
import type { MessageOut } from "@/lib/api/client";
import { Markdown } from "./Markdown";
import type { PendingTurn } from "./useChat";
import { TOOL_NAMES } from "./toolNames";

function UserBubble({ text }: { text: string }) {
  return <div className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-primary-foreground">{text}</div>;
}

function AssistantBubble({ text, tools, interrupted, error, loading }: { text: string; tools: string[]; interrupted: boolean; error: string | null; loading?: boolean }) {
  return (
    <div className="max-w-[92%] space-y-2">
      {tools.length > 0 && <p className="text-xs text-muted-foreground">🔎 A consulté : {[...new Set(tools)].join(", ")}</p>}
      {text ? <Markdown text={text} /> : loading && <p className="animate-pulse text-sm text-muted-foreground">Réflexion en cours…</p>}
      {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-down">{error}</p>}
      {interrupted && <p className="text-xs italic text-muted-foreground">réponse interrompue</p>}
    </div>
  );
}

export function ChatMessages({ messages, pending, streaming }: { messages: MessageOut[]; pending: PendingTurn | null; streaming: boolean }) {
  return (
    <div className="space-y-4">
      {messages.map((m) => m.role === "user"
        ? <UserBubble key={m.id} text={m.content} />
        : <AssistantBubble key={m.id} text={m.content} tools={m.tools.map((t) => TOOL_NAMES[t] ?? t)} interrupted={m.interrupted} error={m.error} />)}
      {pending && (
        <>
          <UserBubble text={pending.user} />
          <AssistantBubble text={pending.text} tools={pending.tools} interrupted={pending.interrupted} error={pending.error} loading={streaming} />
        </>
      )}
    </div>
  );
}
```
Créer `toolNames.ts` (mêmes libellés que `TOOL_LABELS` côté serveur, pour les messages enregistrés) :
```ts
export const TOOL_NAMES: Record<string, string> = {
  search_securities: "Recherche de titres", get_security_overview: "Fiche du titre", get_price_history: "Historique des cours",
  get_top10: "Top 10", get_portfolio: "Votre portefeuille", simulate_past_investment: "Simulation d'achat passé", web_search: "Recherche web",
};
```
`Composer.tsx` :
```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";

export function Composer({ onSend, onStop, streaming }: { onSend: (text: string) => void; onStop: () => void; streaming: boolean }) {
  const [text, setText] = useState("");
  function submit() {
    const value = text.trim();
    if (!value || streaming) return;
    setText("");
    onSend(value);
  }
  return (
    <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <textarea aria-label="Votre question" rows={2} maxLength={4000} value={text} placeholder="Posez votre question… (Entrée pour envoyer, Maj+Entrée pour aller à la ligne)"
                className="min-h-[44px] flex-1 resize-none rounded-lg border border-input bg-white px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} />
      {streaming
        ? <Button type="button" variant="outline" onClick={onStop}>Arrêter</Button>
        : <Button type="submit" disabled={!text.trim()}>Envoyer</Button>}
    </form>
  );
}
```
`ChatView.tsx` :
```tsx
import { useEffect, useRef } from "react";
import { Link } from "react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useAssistantSettings, useConversation } from "./api";
import { ChatMessages } from "./ChatMessages";
import { Composer } from "./Composer";
import { GENERAL_SUGGESTIONS, SECURITY_SUGGESTIONS } from "./suggestions";
import { useChat } from "./useChat";

type Props = { conversationId: number | null; securityId?: number; securityName?: string; onConversationCreated: (id: number) => void; compact?: boolean };

export function ChatView({ conversationId, securityId, securityName, onConversationCreated, compact }: Props) {
  const settings = useAssistantSettings();
  const conversation = useConversation(conversationId);
  const chat = useChat({ conversationId, securityId, onConversationCreated });
  const bottom = useRef<HTMLDivElement>(null);
  const messages = conversation.data?.messages ?? [];
  useEffect(() => { bottom.current?.scrollIntoView?.({ block: "end" }); }, [messages.length, chat.pending?.text]);

  if (settings.isPending) return <Skeleton className="h-40 w-full" />;
  if (!settings.data?.configured) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-white p-6 text-sm">
        <p className="font-medium">L'assistant a besoin de votre clé API Claude.</p>
        <p className="mt-1 text-muted-foreground">Créez-la sur console.anthropic.com puis collez-la dans les Réglages. Elle reste chiffrée sur votre ordinateur.</p>
        <Link to="/reglages" className="mt-3 inline-block font-medium text-primary">Ouvrir les Réglages</Link>
      </div>
    );
  }
  const empty = messages.length === 0 && !chat.pending;
  const suggestions = securityId ? SECURITY_SUGGESTIONS : GENERAL_SUGGESTIONS;
  return (
    <div className={cn("flex min-h-0 flex-1 flex-col gap-4", compact ? "h-full" : "h-[calc(100vh-11rem)]")}>
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {empty ? (
          <div className="space-y-3 py-6">
            <p className="text-sm text-muted-foreground">{securityName ? `Posez une question sur ${securityName} :` : "Posez une question sur les marchés, un titre ou votre portefeuille :"}</p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button key={s} type="button" onClick={() => chat.send(s)}
                        className="rounded-full border border-border bg-white px-3 py-1.5 text-sm hover:border-primary hover:text-primary">{s}</button>
              ))}
            </div>
          </div>
        ) : (
          <ChatMessages messages={messages} pending={chat.pending} streaming={chat.streaming} />
        )}
        <div ref={bottom} />
      </div>
      <Composer onSend={chat.send} onStop={chat.stop} streaming={chat.streaming} />
      <p className="text-center text-xs text-muted-foreground">Outil d'aide à la décision : ceci n'est pas un conseil en investissement.</p>
    </div>
  );
}
```

- [ ] **Step 6: `AssistantPage.tsx` + route**
```tsx
import { useState } from "react";
import { useSearchParams } from "react-router";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useConversations, useDeleteConversation } from "./api";
import { ChatView } from "./ChatView";

export const formatCost = (usd: number) => `≈ ${usd.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} $`;

export function AssistantPage() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("c") ? Number(params.get("c")) : null;
  const conversations = useConversations();
  const remove = useDeleteConversation();
  const [viewKey, setViewKey] = useState(0);
  const show = (id: number | null) => setParams(id === null ? {} : { c: String(id) });
  const select = (id: number | null) => { setViewKey((k) => k + 1); show(id); };
  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Assistant IA</h1>
        <p className="mt-1 text-sm text-muted-foreground">Claude répond en s'appuyant sur les données de l'application (cours, scores, votre portefeuille) et sur l'actualité.</p>
      </header>
      <div className="grid grid-cols-[280px_1fr] gap-6">
        <Card className="h-[calc(100vh-11rem)] gap-0 overflow-y-auto p-3">
          <Button className="mb-3 w-full" onClick={() => select(null)}>+ Nouvelle conversation</Button>
          <ul className="space-y-1">
            {conversations.data?.map((c) => (
              <li key={c.id} className={cn("group flex items-center rounded-lg", c.id === selected ? "bg-accent" : "hover:bg-muted")}>
                <button type="button" onClick={() => select(c.id)} className="min-w-0 flex-1 px-3 py-2 text-left">
                  <p className="truncate text-sm font-medium">{c.title}</p>
                  <p className="text-xs text-muted-foreground">{new Date(c.updated_at).toLocaleDateString("fr-FR")} · {formatCost(c.cost_usd)}</p>
                </button>
                <button type="button" aria-label={`Supprimer la conversation ${c.title}`}
                        className="mr-2 hidden rounded p-1 text-muted-foreground hover:text-down group-hover:block"
                        onClick={() => { if (window.confirm("Supprimer cette conversation ?")) remove.mutate(c.id, { onSuccess: () => c.id === selected && select(null) }); }}>
                  <Trash2 className="size-4" />
                </button>
              </li>
            ))}
            {conversations.data?.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">Aucune conversation pour l'instant.</li>}
          </ul>
        </Card>
        <Card className="p-5">
          <ChatView key={viewKey} conversationId={selected} onConversationCreated={show} />
        </Card>
      </div>
    </section>
  );
}
```
Note : `viewKey` ne change que sur « Nouvelle conversation » ou le choix d’une autre conversation ; la création d’une conversation pendant l’envoi (`onConversationCreated`) met seulement à jour `?c=`, sans recréer le `ChatView`, pour ne pas couper le flux en cours.

`router.tsx` : `{ path: "assistant", lazy: async () => ({ Component: (await import("@/features/assistant/AssistantPage")).AssistantPage }) }` ; supprimer l'import `ComingSoon` s'il n'est plus utilisé. `router.test.tsx` : dans `body()`, renvoyer `[]` pour `/api/assistant/conversations` et `{configured:false, source:null, model:"claude-opus-5", models:[]}` pour `/api/assistant/settings`.

Run: `npx vitest run src/features/assistant src/app` → PASS ; `npm test` → PASS ; `npm run build` → OK.

- [ ] **Step 7: Commit**
```bash
git add -A frontend && git commit -m "feat: assistant page with streaming chat, Markdown answers and conversation history"
```

---

### Task 7: Frontend — panneau latéral ✨ (fiche titre et top 10)

**Files:**
- Create: `frontend/src/components/ui/sheet.tsx` (shadcn), `frontend/src/features/assistant/AssistantPanel.tsx`, `frontend/src/features/assistant/AskAiButton.tsx`, `frontend/src/features/assistant/AssistantPanel.test.tsx`
- Modify: `frontend/src/app/Layout.tsx`, `frontend/src/features/home/TopList.tsx`, `frontend/src/features/security/SecurityPage.tsx`, tests existants qui rendent ces composants sans provider (le hook doit fonctionner hors provider : bouton inactif → no-op).

**Interfaces:**
- Consumes: `ChatView`.
- Produces:
  - `AssistantPanelProvider({ children })`, `useAssistantPanel(): { open(security: { id: number; name: string }): void }`.
  - `AskAiButton({ security: { id, name }, label?: boolean })` — icône ✨, `aria-label="Demander à l'IA à propos de {name}"`, texte « Demander à l'IA » si `label`.

- [ ] **Step 1: Composant Sheet** : `cd frontend && npx shadcn@latest add sheet` (vérifier la localisation du bouton de fermeture « Fermer » comme pour le dialog).

- [ ] **Step 2: Test (échoue)**

`frontend/src/features/assistant/AssistantPanel.test.tsx` :
```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { AskAiButton } from "./AskAiButton";
import { AssistantPanelProvider } from "./AssistantPanel";

afterEach(() => vi.unstubAllGlobals());

test("le bouton ✨ ouvre le panneau avec le titre en contexte et les questions prêtes", async () => {
  mockFetch((url) => ({ body: url === "/api/assistant/settings" ? { configured: true, source: "settings", model: "claude-opus-5", models: [] } : {} }));
  renderWithProviders(<AssistantPanelProvider><AskAiButton security={{ id: 1, name: "LVMH" }} label /></AssistantPanelProvider>);
  await userEvent.click(screen.getByRole("button", { name: "Demander à l'IA à propos de LVMH" }));
  expect(await screen.findByRole("dialog", { name: "Assistant IA — LVMH" })).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Analyse cette action" })).toBeInTheDocument();
});

test("hors provider, le bouton ne plante pas", async () => {
  renderWithProviders(<AskAiButton security={{ id: 1, name: "LVMH" }} />);
  await userEvent.click(screen.getByRole("button", { name: "Demander à l'IA à propos de LVMH" }));
});
```
Run: `npx vitest run src/features/assistant/AssistantPanel.test.tsx` → FAIL.

- [ ] **Step 3: Implémenter**

`AssistantPanel.tsx` :
```tsx
import { createContext, lazy, Suspense, useContext, useState, type ReactNode } from "react";
import { Link } from "react-router";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

const ChatView = lazy(async () => ({ default: (await import("./ChatView")).ChatView }));

type PanelSecurity = { id: number; name: string };
const PanelContext = createContext<{ open: (security: PanelSecurity) => void }>({ open: () => {} });

export const useAssistantPanel = () => useContext(PanelContext);

export function AssistantPanelProvider({ children }: { children: ReactNode }) {
  const [security, setSecurity] = useState<PanelSecurity | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isOpen, setOpen] = useState(false);
  function open(next: PanelSecurity) {
    if (next.id !== security?.id) setConversationId(null);  // nouveau titre : nouvelle conversation
    setSecurity(next);
    setOpen(true);
  }
  return (
    <PanelContext.Provider value={{ open }}>
      {children}
      <Sheet open={isOpen} onOpenChange={setOpen}>
        <SheetContent side="right" className="flex w-[520px] flex-col gap-3 sm:max-w-[520px]">
          <SheetHeader>
            <SheetTitle>Assistant IA — {security?.name}</SheetTitle>
            <SheetDescription>
              Claude a accès aux données de ce titre et à votre portefeuille.{" "}
              {conversationId !== null && <Link to={`/assistant?c=${conversationId}`} onClick={() => setOpen(false)} className="text-primary">Ouvrir dans la page Assistant</Link>}
            </SheetDescription>
          </SheetHeader>
          <div className="flex min-h-0 flex-1 flex-col px-4 pb-4">
            {security && (
              <Suspense fallback={null}>
                <ChatView compact conversationId={conversationId} securityId={security.id} securityName={security.name} onConversationCreated={setConversationId} />
              </Suspense>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </PanelContext.Provider>
  );
}
```
`AskAiButton.tsx` :
```tsx
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAssistantPanel } from "./AssistantPanel";

export function AskAiButton({ security, label = false }: { security: { id: number; name: string }; label?: boolean }) {
  const { open } = useAssistantPanel();
  return (
    <Button type="button" variant={label ? "outline" : "ghost"} size={label ? "sm" : "icon"} aria-label={`Demander à l'IA à propos de ${security.name}`}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); open(security); }}>
      <Sparkles className="size-4 text-primary" />
      {label && <span>Demander à l'IA</span>}
    </Button>
  );
}
```
`Layout.tsx` : envelopper le contenu dans `<AssistantPanelProvider>`.
`TopList.tsx` : `<AskAiButton security={{ id: item.id, name: item.name }} />` avant `FavoriteButton`.
`SecurityPage.tsx` : `{data.kind !== "index" && <AskAiButton security={{ id: data.id, name: data.name }} label />}` à côté de « + J'ai acheté ».

Ruling possible : un `ChatView` lazy dans le Layout ajoute `react-markdown` à un chunk séparé chargé seulement à l'ouverture du panneau (bundle principal inchangé).

Run: `npx vitest run` → PASS ; `npm run build` → OK.

- [ ] **Step 4: Commit**
```bash
git add -A frontend && git commit -m "feat: ✨ assistant side panel from top 10 and security page"
```

---

### Task 8: Intégration — nginx, e2e, README, vérification réelle

**Files:**
- Modify: `frontend/nginx.conf`, `frontend/e2e/smoke.spec.ts`, `README.md`

- [ ] **Step 1: nginx** — dans `location /api/`, ajouter `proxy_read_timeout 600s;` (la réflexion de Claude peut rester silencieuse plus de 60 s) et `proxy_http_version 1.1;`.

- [ ] **Step 2: e2e** — ajouter à `smoke.spec.ts` :
```ts
test("assistant : page et réglages", async ({ page }) => {
  await page.goto("/assistant");
  await expect(page.getByRole("heading", { level: 1, name: "Assistant IA" })).toBeVisible();
  await page.goto("/reglages");
  await expect(page.getByText("Assistant IA (Claude)")).toBeVisible();
});
```

- [ ] **Step 3: README** — section « Fonctionnalités » : lot 4 (assistant, clé chiffrée, modèles, coût) ; section installation : `APP_SECRET` obligatoire pour enregistrer une clé, `ANTHROPIC_API_KEY` optionnelle.

- [ ] **Step 4: Vérification réelle** — `docker compose up -d --build` ; `curl` : `GET /api/assistant/settings` (non configurée), `POST /api/assistant/conversations`, `POST .../messages` → 409 lisible ; enregistrer une fausse clé `sk-ant-fausse-cle-0000000000` via l'UI, envoyer un message → événement SSE `error` « Clé API invalide… » affiché dans le chat et message enregistré avec « réponse interrompue » ; vérifier que la clé n'apparaît dans aucune réponse ni dans `docker compose logs api` ; supprimer la clé et la conversation de test. `npm run e2e` → PASS.

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "chore: nginx streaming timeout, assistant smoke test and README for lot 4"
```
