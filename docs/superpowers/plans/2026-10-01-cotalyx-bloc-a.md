# Cotalyx — Bloc A (curseur, renommage, textes neutres) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tout élément cliquable affiche le curseur « main », l'application s'appelle Cotalyx partout et ses textes ne la présentent plus comme un outil réservé au PEA.

**Architecture:** Une règle CSS globale dans `@layer base`. Le nom vient d'une seule constante par côté (`APP_NAME` dans `backend/app/core/brand.py`, `SITE_NAME` déjà présent dans `frontend/src/seo/schema.ts`), utilisée partout au lieu du texte en dur ; les gabarits de mails la reçoivent comme variable. Les cookies passent du préfixe `pea_` à `cotalyx_`. Les mentions de l'éligibilité (badges, filtres, admin) ne bougent pas : c'est le bloc B.

**Tech Stack:** FastAPI, Jinja2 (mails), React 19 + Tailwind 4, Vitest, Playwright, Docsify.

**Spec:** `docs/superpowers/specs/2026-10-01-cotalyx-design.md` (section « Bloc A »).

## Global Constraints

- Nom : **Cotalyx** (C majuscule, le reste en minuscules), « Cotalyx Premium » pour l'abonnement.
- Préfixe des cookies : `cotalyx_` (`cotalyx_session`, `cotalyx_csrf`, `cotalyx_device`, `cotalyx_oauth`, `cotalyx_google_pending`).
- Paquet Python : `cotalyx`.
- **Ne pas modifier** : nom du dépôt, base et utilisateur PostgreSQL (`pea_radar`, `pea`), `LEGACY_EMAIL = "moi@pea-radar.invalid"` (identifiant stocké en base), migrations Alembic existantes, `.env` (ne jamais l'ouvrir ni l'afficher), fichiers sous `.superpowers/` et `docs/superpowers/` (historique).
- Ne pas toucher aux libellés d'éligibilité (« Éligible PEA », « Éligibles PEA uniquement », filtre de l'Explorer, carte admin) : bloc B.
- Le guide `frontend/public/guide/bourse/pea.md` reste : il explique l'enveloppe PEA.
- Avertissement « outil d'aide à la décision, pas un conseil en investissement » conservé partout où il existe.
- Interface et commentaires en français, commits en anglais (conventional commits), message terminé par `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Versions légales : `TERMS_VERSION = CGV_VERSION = "2026-10-06"`, `LEGAL_UPDATED = "6 octobre 2026"`.

## Review Focus

1. Un visiteur déjà connecté avant le déploiement (ancien cookie `pea_session`) doit simplement être vu comme déconnecté, sans erreur 500 ni boucle de redirection — test dans la tâche 3.
2. Le client HTTP doit lire le nouveau cookie CSRF : sinon toute requête POST échoue en 403 après connexion — test dans la tâche 3.
3. Un sujet de mail à code (« Votre code Cotalyx : {code} ») doit toujours perdre son code dans `email_log` (`outbox.py` coupe sur `" : {"`) — test existant `test_mail_outbox.py`, à adapter dans la tâche 2.
4. Un bouton désactivé ne doit pas afficher la main — test e2e dans la tâche 1.
5. Aucune page publique ne doit encore afficher « PEA Radar » (titre, description, `og:site_name`, `llms.txt`) — tests dans les tâches 2 et 4.

---

### Task 1: Curseur « main » sur tout ce qui est cliquable

**Files:**
- Modify: `frontend/src/index.css` (bloc `@layer base`, lignes 122-132)
- Test: `frontend/e2e/smoke.spec.ts`

**Interfaces:** aucune.

- [ ] **Step 1: Écrire le test e2e qui échoue**

Ajouter à la fin de `frontend/e2e/smoke.spec.ts` :

```ts
test("les éléments cliquables affichent la main", async ({ page }) => {
  const cursor = (selector: string) => page.locator(selector).first().evaluate((el) => getComputedStyle(el).cursor);

  await page.goto("/reglages");
  await expect(page.getByRole("button", { name: /Enregistrer/ }).first()).toBeVisible();
  expect(await page.getByRole("button", { name: /Enregistrer/ }).first().evaluate((el) => getComputedStyle(el).cursor)).toBe("pointer");

  await page.goto("/explorer");
  await expect(page.getByRole("heading", { level: 1, name: "Explorer" })).toBeVisible();
  expect(await cursor("select")).toBe("pointer");
  expect(await cursor("a[href]")).toBe("pointer");
  expect(await cursor("[role=tab], button")).toBe("pointer");

  // Un bouton désactivé ne propose pas le clic.
  await page.evaluate(() => {
    const b = document.createElement("button");
    b.id = "cursor-probe";
    b.disabled = true;
    b.textContent = "x";
    document.body.append(b);
  });
  expect(await cursor("#cursor-probe")).toBe("not-allowed");
});
```

- [ ] **Step 2: Vérifier qu'il échoue**

```bash
docker compose up -d --build web
cd frontend && npx playwright test e2e/smoke.spec.ts -g "main"
```
Attendu : FAIL, `Expected: "pointer"  Received: "default"` (Tailwind 4 remet les boutons en `cursor: default`).

- [ ] **Step 3: Ajouter la règle CSS**

Dans `frontend/src/index.css`, à l'intérieur du `@layer base` existant, après la règle `html { … }` :

```css
  /* Tout ce qui se clique montre la main ; ce qui est désactivé montre l'interdiction. */
  button,
  a[href],
  select,
  summary,
  label[for],
  input:is([type="checkbox"], [type="radio"], [type="range"], [type="file"], [type="submit"], [type="button"], [type="reset"]),
  [role="button"],
  [role="tab"],
  [role="link"],
  [role="menuitem"],
  [role="menuitemcheckbox"],
  [role="menuitemradio"],
  [role="option"],
  [role="switch"],
  [role="checkbox"],
  [role="radio"] {
    cursor: pointer;
  }
  :is(button, select, input, [role="button"], [role="tab"], [role="menuitem"], [role="option"], [role="switch"]):is(:disabled, [aria-disabled="true"]) {
    cursor: not-allowed;
  }
```

Les composants shadcn qui posent `disabled:pointer-events-none` gardent ce comportement (aucun survol), c'est voulu.

- [ ] **Step 4: Vérifier qu'il passe**

```bash
docker compose up -d --build web
cd frontend && npx playwright test e2e/smoke.spec.ts
```
Attendu : PASS (tous les tests du fichier).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css frontend/e2e/smoke.spec.ts
git commit -m "feat(ui): pointer cursor on every clickable element"
```

---

### Task 2: Nom Cotalyx côté backend (mails, API, SEO, assistant)

**Files:**
- Create: `backend/app/core/brand.py`
- Modify: `backend/app/main.py:7`, `backend/app/core/config.py:50`, `backend/app/cli.py:18`, `backend/app/api/routes/me.py:190`, `backend/app/providers/euronext.py:104`, `backend/app/api/routes/seo.py:59-85`, `backend/app/services/assistant/prompt.py`, `backend/app/services/assistant/tools.py:51`, `backend/app/services/mail/render.py:11-46`, `backend/app/services/mail/outbox.py:38` (commentaire), `backend/app/services/mail/templates/*.html|*.txt` (toutes les occurrences de « PEA Radar », plus `premium_started.*` ligne « votre PEA »), `backend/app/api/routes/security_detail.py:147` (commentaire), `backend/app/repositories/market_data.py:12` (docstring), `backend/pyproject.toml:2`, `.env.example:28,45`
- Test: `backend/tests/test_mail_render.py`, `backend/tests/test_mail_outbox.py`, `backend/tests/test_api_seo.py`, `backend/tests/test_bootstrap.py`, nouveau `backend/tests/test_brand.py`

**Interfaces:**
- Produces: `app.core.brand.APP_NAME: str = "Cotalyx"`. Les gabarits Jinja reçoivent `app_name` dans leur contexte de rendu.

- [ ] **Step 1: Écrire les tests qui échouent**

`backend/tests/test_brand.py` :

```python
from pathlib import Path

from app.core.brand import APP_NAME

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def test_app_name():
    assert APP_NAME == "Cotalyx"


def test_old_name_is_gone_from_code_and_mails():
    hits = [str(p) for p in APP_DIR.rglob("*") if p.is_file() and p.suffix in {".py", ".html", ".txt"}
            and "PEA Radar" in p.read_text(encoding="utf-8")]
    assert hits == []
```

Dans `backend/tests/test_api_seo.py`, ajouter :

```python
def test_llms_txt_is_not_pea_centric(client):
    body = client.get("/llms.txt").text
    assert body.startswith("# Cotalyx")
    assert "PEA Radar" not in body
    assert "éligibles au PEA" not in body
```

Dans `backend/tests/test_mail_render.py`, ajouter (`render(kind, context, *, base_url)` renvoie un `RenderedEmail` avec `subject`, `html`, `text`) :

```python
def test_subjects_and_footer_use_new_name():
    mail = render("verify_code", {"code": "123456"}, base_url="https://x")
    assert mail.subject == "Votre code Cotalyx : 123456"
    assert "Cotalyx" in mail.html and "Cotalyx" in mail.text
    assert "PEA Radar" not in mail.html + mail.text
```

(Ajouter au contexte les autres clés que le gabarit `verify_code` exige, en copiant celles du test `verify_code` existant du fichier.)

Remplacer dans les tests existants (`test_mail_render.py`, `test_mail_outbox.py`, `test_bootstrap.py`, `test_api_seo.py`) toute attente contenant « PEA Radar » par « Cotalyx » (garder `moi@pea-radar.invalid` tel quel).

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_brand.py tests/test_api_seo.py tests/test_mail_render.py tests/test_mail_outbox.py tests/test_bootstrap.py
```
Attendu : FAIL (`ModuleNotFoundError: app.core.brand`, puis attentes « Cotalyx »).

- [ ] **Step 3: Implémenter**

`backend/app/core/brand.py` :

```python
"""Nom public de l'application, affiché dans l'API, les mails et les textes pour les robots."""

APP_NAME = "Cotalyx"
```

Remplacements :

| Fichier | Avant | Après |
|---|---|---|
| `main.py:7` | `FastAPI(title="PEA Radar API")` | `FastAPI(title=f"{APP_NAME} API")` (+ `from app.core.brand import APP_NAME`) |
| `core/config.py:50` | `"PEA Radar <no-reply@localhost>"` | `"Cotalyx <no-reply@localhost>"` |
| `cli.py:18` | `default="PEA Radar"` | `default=APP_NAME` |
| `me.py:190` | `f"pea-radar-mes-donnees-…"` | `f"cotalyx-mes-donnees-…"` |
| `euronext.py:104` | `"Mozilla/5.0 (PEA Radar)"` | `f"Mozilla/5.0 ({APP_NAME})"` |
| `render.py` | chaque « PEA Radar » dans `SUBJECTS` et les textes | `{APP_NAME}` via f-string, ou « Cotalyx » ; « PEA Radar Premium » → « Cotalyx Premium » |
| `outbox.py:38` | commentaire « Votre code PEA Radar » | « Votre code Cotalyx » |
| gabarits `templates/*` | « PEA Radar » | `{{ app_name }}` |
| `premium_started.html/.txt` | « sur vos titres et votre PEA » | « sur vos titres et votre portefeuille » |
| `security_detail.py:147` | `# le PEA se paie en euros` | `# le simulateur compte en euros` |
| `market_data.py:12` | « tout ce qui n'est pas exclu du PEA » | « titres non exclus (règle revue au bloc B) » |
| `tools.py:51` | « Portefeuille PEA de l'utilisateur » | « Portefeuille de l'utilisateur » |
| `pyproject.toml:2` | `name = "pea-radar"` | `name = "cotalyx"` |
| `.env.example:28` | `MAIL_FROM=PEA Radar <no-reply@pea-radar.local>` | `MAIL_FROM=Cotalyx <no-reply@cotalyx.local>` |
| `.env.example:45` | « PEA Radar Premium » | « Cotalyx Premium » |

Dans `render.py:98`, injecter le nom avec `base_url` : `values = {**context, "base_url": base_url.rstrip("/"), "app_name": APP_NAME}`, pour que `{{ app_name }}` fonctionne dans `_layout.html`, `_footer.txt` et les gabarits (et `{app_name}` dans `SUBJECTS` si on préfère le formatage).

`prompt.py`, remplacer `BASE` (première ligne et règle « Contexte PEA ») :

```python
BASE = """Tu es l'assistant de Cotalyx, une application qui aide des investisseurs particuliers, souvent débutants, à comprendre les actions et les ETF, à choisir des titres et à suivre leur portefeuille.

Date du jour : {today} (heure de Paris).

Règles :
- Réponds en français, de façon pédagogique et concise ; explique simplement chaque terme technique (PER, RSI, PRU…).
- Pour tout chiffre (cours, score, portefeuille, performance), appuie-toi sur les outils et cite l'horodatage des données (champs as_of, computed_at, date).
- Distingue clairement les faits (données) de ton opinion.
- Ne présente jamais une prévision comme certaine.
- Quand tu donnes un avis sur un achat ou une vente, rappelle qu'il ne s'agit pas d'un conseil en investissement réglementé.
- Utilise la recherche web pour l'actualité récente et cite tes sources.
- Enveloppes : ne suppose pas que l'utilisateur investit via un PEA ; si l'enveloppe compte pour la réponse (PEA, compte-titres…), demande-la ou présente les cas. Les frais de courtage suivent la grille de l'utilisateur ; son courtier lui facture des frais s'il passe moins de {min_orders} ordres par an.
- Mise en forme : Markdown simple (titres courts, listes, tableaux si utile).
- Quand tu utilises un outil, tu peux dire une courte phrase avant. Si aucun outil ne permet de répondre, dis-le au lieu de deviner. N'inclus pas de balises XML internes ou système dans ta réponse."""
```

`seo.py`, corps de `llms()` :

```python
    body = f"""# {APP_NAME}

> Radar des actions et ETF : top 10 du moment selon un score mixte technique et fondamental, explorateur, fiches détaillées avec graphiques et simulateur « et si j'avais investi ». Outil d'aide à la décision et d'apprentissage, pas un conseil en investissement.

Suivi actuel : {stocks} action{"s" if stocks > 1 else ""} et {etfs} ETF (Euronext, Xetra, Madrid…). Cours issus de Yahoo Finance, en différé.

## Pages

- [Accueil]({_url(settings, "/")}) : top 10 du moment avec l'explication de chaque score, indices, hausses et baisses du jour, carte du marché.
- [Explorer]({_url(settings, "/explorer")}) : toutes les actions avec score, performances (1 jour à 1 an), PER, rendement et enveloppes compatibles (PEA…), triables et filtrables.
- [ETF]({_url(settings, "/etf")}) : ETF classés par score technique.
- Fiches titres ({_url(settings, "/titres/")}<id>) : cours, graphique en chandeliers avec moyennes mobiles, RSI et MACD, détail du score, données fondamentales, actualités, simulateur d'achat passé frais inclus.

## Méthode du score

- Score sur 100 : moitié technique (tendance, force relative face au CAC 40, RSI, MACD), moitié fondamentale (valorisation, croissance, bilan, dividende). Les ETF sont notés sur la partie technique seule.
- Le top 10 exclut les titres peu échangés ou à l'historique trop court.
- La compatibilité avec le PEA est déduite du pays du siège (code ISIN) : à confirmer auprès de son courtier.

## Plan du site

- [sitemap.xml]({_url(settings, "/sitemap.xml")})
"""
```

(Le filtre `_public_securities()` sur l'éligibilité reste tel quel jusqu'au bloc B.)

- [ ] **Step 4: Vérifier que tout passe**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q
```
Attendu : PASS sur toute la suite (~750 tests).

- [ ] **Step 5: Commit**

```bash
git add backend .env.example
git commit -m "feat: rename the app to Cotalyx in API, mails, SEO and assistant"
```

---

### Task 3: Cookies `cotalyx_*`

**Files:**
- Modify: `backend/app/services/auth/sessions.py:12-14`, `backend/app/api/routes/google.py:22`, docstrings `backend/app/models/auth.py:28` et `backend/app/services/auth/devices.py:11`, `frontend/src/lib/api/client.ts:30`, `frontend/src/lib/api/client.test.ts:26,30`
- Test: `backend/tests/test_api_signin.py`, `test_api_signup.py`, `test_api_signup_limits.py`, `test_api_google.py`, `frontend/src/lib/api/client.test.ts`

**Interfaces:**
- Produces: `SESSION_COOKIE = "cotalyx_session"`, `CSRF_COOKIE = "cotalyx_csrf"`, `DEVICE_COOKIE = "cotalyx_device"`, `OAUTH_COOKIE = "cotalyx_oauth"`, `PENDING_COOKIE = "cotalyx_google_pending"`.

- [ ] **Step 1: Adapter les tests (ils échouent)**

Dans les tests backend listés, remplacer les chaînes `"pea_csrf"`, `"pea_oauth"`, `"pea_google_pending"` par les constantes importées (`from app.services.auth.sessions import CSRF_COOKIE` ; `from app.api.routes.google import OAUTH_COOKIE, PENDING_COOKIE`) — plus aucun nom de cookie en dur dans les tests. Ajouter dans `backend/tests/test_api_signin.py` :

```python
def test_cookie_names_use_new_prefix(anon_client):
    from app.services.auth.sessions import CSRF_COOKIE, DEVICE_COOKIE, SESSION_COOKIE
    assert (SESSION_COOKIE, CSRF_COOKIE, DEVICE_COOKIE) == ("cotalyx_session", "cotalyx_csrf", "cotalyx_device")


def test_old_session_cookie_is_simply_ignored(anon_client):
    anon_client.cookies.set("pea_session", "ancien-jeton")
    response = anon_client.get("/api/me")
    assert response.status_code == 401  # visiteur, comme sans cookie : pas de 500
```

Dans `frontend/src/lib/api/client.test.ts`, lignes 26 et 30 : `pea_csrf` → `cotalyx_csrf`.

- [ ] **Step 2: Vérifier l'échec**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_api_signin.py tests/test_api_google.py
cd frontend && npx vitest run src/lib/api/client.test.ts
```
Attendu : FAIL sur les noms de cookies.

- [ ] **Step 3: Implémenter**

- `sessions.py:12-14` : `"cotalyx_session"`, `"cotalyx_csrf"`, `"cotalyx_device"`.
- `google.py:22` : `"cotalyx_oauth", "cotalyx_google_pending"`.
- docstrings `models/auth.py:28`, `devices.py:11` : `pea_device` → `cotalyx_device`.
- `client.ts:30` : `/(?:^|;\s*)cotalyx_csrf=([^;]+)/`.

- [ ] **Step 4: Vérifier**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q
cd frontend && npm test -- --run
```
Attendu : PASS.

- [ ] **Step 5: Commit**

```bash
git add backend frontend/src/lib/api
git commit -m "feat(auth): rename cookies to the cotalyx_ prefix"
```

---

### Task 4: Nom et textes neutres côté frontend, versions légales

**Files:**
- Modify: `frontend/src/seo/schema.ts:3`, `frontend/index.html:7-10`, `frontend/src/seo/usePageMeta.ts:6` (commentaire), `frontend/src/app/Layout.tsx:32-33`, `NotFoundPage.tsx:10`, `Sidebar.tsx:26`, `features/auth/AcceptTermsPage.tsx:60`, `AuthCard.tsx:12`, `AuthFooter.tsx:14`, `AuthPage.tsx:15,33,117,149`, `FinishSignUpPage.tsx:14`, `UnsubscribePage.tsx:13`, `features/legal/LegalPage.tsx:7-10`, `features/legal/content.tsx` (toutes les occurrences, plus `LEGAL_UPDATED`), `features/portfolio/PortfolioPage.tsx:94`, `features/portfolio/OrderDialog.tsx:101`, `features/settings/FeeSettingsCard.tsx:46`, `features/premium/PremiumPage.tsx:22,26,36,76-77`, `features/security/SecurityPage.tsx:33`, `frontend/src/app/router.tsx:28` (description « éligibilité au PEA » → neutre), `backend/app/core/terms.py`
- Test: `frontend/src/app/router.test.tsx`, `frontend/src/seo/usePageMeta.test.tsx`, `frontend/src/features/security/SecurityPage.test.tsx`, `frontend/e2e/seo.spec.ts`, `frontend/e2e/premium.spec.ts`

**Interfaces:**
- Consumes: `SITE_NAME` (`frontend/src/seo/schema.ts`), désormais `"Cotalyx"`.

- [ ] **Step 1: Adapter les tests (ils échouent)**

- `router.test.tsx` : `| PEA Radar` → `| Cotalyx`, `"PEA Radar"` → `"Cotalyx"` ; ligne 76 : `toMatch(/PEA/)` → `toMatch(/actions et ETF/)`.
- `usePageMeta.test.tsx` : idem pour les titres ; ligne 32 : `"Radar PEA."` → `"Radar des marchés."`.
- `SecurityPage.test.tsx:92` : `| PEA Radar` → `| Cotalyx`.
- `e2e/seo.spec.ts`, `e2e/premium.spec.ts` : « PEA Radar » → « Cotalyx ».
- Ajouter dans `router.test.tsx` :

```tsx
test("l'accueil ne se présente plus comme un outil PEA", async () => {
  renderRoute("/");  // même helper que les tests voisins du fichier
  await waitFor(() => expect(document.title).toBe("Cotalyx"));
  const description = document.head.querySelector('meta[name="description"]')?.getAttribute("content") ?? "";
  expect(description).not.toMatch(/PEA/);
});
```

- [ ] **Step 2: Vérifier l'échec**

```bash
cd frontend && npx vitest run src/app/router.test.tsx src/seo/usePageMeta.test.tsx src/features/security/SecurityPage.test.tsx
```
Attendu : FAIL (`"PEA Radar"` reçu).

- [ ] **Step 3: Implémenter**

- `schema.ts:3` : `export const SITE_NAME = "Cotalyx";`. Partout dans `frontend/src`, remplacer le texte « PEA Radar » par `{SITE_NAME}` (JSX) ou `` `…${SITE_NAME}…` `` (chaînes), en important `SITE_NAME` depuis `@/seo/schema` ; « PEA Radar Premium » → `` `${SITE_NAME} Premium` ``. `SecurityPage.tsx:33` : `` `score ${SITE_NAME} ${Math.round(data.score)}/100, ` ``.
- `index.html` : `<title>Cotalyx</title>`, `og:site_name` « Cotalyx », description : « Radar des actions et ETF : top 10 du moment, score technique et fondamental expliqué, graphiques et simulateur. Outil d'aide à la décision, pas un conseil en investissement. »
- Textes neutres :

| Fichier | Avant | Après |
|---|---|---|
| `AuthPage.tsx:15` | « pour suivre votre PEA en quelques minutes » | « pour suivre vos investissements en quelques minutes » |
| `AuthPage.tsx:33` | « …pour suivre votre portefeuille PEA. » | « …pour suivre votre portefeuille. » |
| `AuthPage.tsx:117` | `Mon PEA` | `Mon portefeuille` |
| `AuthPage.tsx:149` | `✓ Éligible PEA` | `✓ Score 82/100` (décor : met en avant le score plutôt qu'une enveloppe) |
| `Layout.tsx:33` | « éligibilité PEA déduite du pays du siège, à confirmer auprès de votre banque » | « compatibilité PEA déduite du pays du siège, à confirmer auprès de votre courtier » |
| `PortfolioPage.tsx:94` | « sur l'application Crédit Agricole » | « chez votre courtier » |
| `OrderDialog.tsx:101` | « sur l'application Crédit Agricole » | « chez votre courtier » |
| `FeeSettingsCard.tsx:46` | « Valeurs par défaut : formule Invest Store Intégral (caisse de Paris). » | « Valeurs par défaut : un exemple de grille de banque en ligne (Crédit Agricole, Invest Store Intégral). Remplacez-les par celles de votre courtier. » |
| `router.tsx:28` | « …et leur éligibilité au PEA. » | « …et les enveloppes compatibles. » |
| `router.tsx:29` | « Les ETF éligibles au PEA, classés… » | « Les ETF, classés… » |
| `content.tsx` CGU §1 | « …pour le Plan d'Épargne en Actions (PEA). » | « …pour investir en actions et en ETF. » |
| `content.tsx` CGU §4 | « L'éligibilité au PEA est déduite automatiquement » | « La compatibilité d'un titre avec une enveloppe (PEA…) est déduite automatiquement » |
| `content.tsx` cookies | `pea_session`, `pea_csrf`, `pea_device` | `cotalyx_session`, `cotalyx_csrf`, `cotalyx_device` |

- `content.tsx` : `LEGAL_UPDATED = "6 octobre 2026"`. `backend/app/core/terms.py` : `TERMS_VERSION = "2026-10-06"`, `CGV_VERSION = "2026-10-06"`.

- [ ] **Step 4: Vérifier**

```bash
cd frontend && npm test -- --run && npx tsc -b
grep -rn "PEA Radar" src index.html
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q
```
Attendu : tests PASS, `tsc` sans erreur, `grep` sans résultat.

- [ ] **Step 5: Commit**

```bash
git add frontend/src frontend/index.html frontend/e2e backend/app/core/terms.py
git commit -m "feat: Cotalyx name and broker-neutral wording in the web app, bump legal versions"
```

---

### Task 5: Guide, documentation admin, README, CLAUDE.md

**Files:**
- Modify: tous les fichiers de `frontend/public/guide/` et `frontend/public/documentation/` qui contiennent « PEA Radar » (liste : `grep -rl "PEA Radar" frontend/public`), leurs `index.html` et `config.js` (titre Docsify), `README.md`, `CLAUDE.md`
- Test: `frontend/e2e/documentation.spec.ts` (attentes de titre)

**Interfaces:** aucune.

- [ ] **Step 1: Adapter le test e2e**

Dans `frontend/e2e/documentation.spec.ts`, remplacer « PEA Radar » par « Cotalyx » dans les attentes.

- [ ] **Step 2: Mettre à jour les contenus**

- « PEA Radar » → « Cotalyx » partout dans `frontend/public/guide` et `frontend/public/documentation` (`name` Docsify dans les deux `config.js`, `<title>` des deux `index.html`).
- Guide : là où le texte suppose que le lecteur a un PEA (`premiers-pas.md`, `app/portefeuille.md`, `app/reglages.md`, `faq.md`), le reformuler pour un investisseur avec n'importe quelle enveloppe ; `bourse/pea.md` reste la page qui explique le PEA ; ajouter dans `faq.md` une question « Pourquoi PEA Radar s'appelle maintenant Cotalyx ? » avec une réponse de deux phrases (l'app couvre désormais toutes les enveloppes).
- Documentation admin `installation.md` : signaler que les cookies ont été renommés (déconnexion de tous au déploiement), que `MAIL_FROM` dans `.env` doit être changé à la main en « Cotalyx <…> », et que la base garde le nom `pea_radar`.
- `README.md` et `CLAUDE.md` : titre « Cotalyx », première phrase de CLAUDE.md réécrite (« Application web grand public pour investisseurs particuliers… ») ; garder la mention des noms techniques inchangés (dépôt, base).

- [ ] **Step 3: Vérifier**

```bash
grep -rln "PEA Radar" frontend/public README.md CLAUDE.md
docker compose up -d --build
cd frontend && npx playwright test
```
Attendu : `grep` sans résultat ; toute la suite e2e PASS (dont `documentation.spec.ts`, `layout.spec.ts`, `headers.spec.ts`, et le test du curseur).

- [ ] **Step 4: Commit**

```bash
git add frontend/public frontend/e2e README.md CLAUDE.md
git commit -m "docs: Cotalyx name and envelope-neutral guide and admin docs"
```

---

### Task 6: Vérification finale et PR

- [ ] **Step 1: Contrôle global**

```bash
grep -rIn "PEA Radar\|pea-radar" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude-dir=.superpowers --exclude-dir=superpowers . | grep -v "pea-radar.invalid\|\.env:"
```
Attendu : aucun résultat (hors `LEGACY_EMAIL` et migrations Alembic existantes, qui sont autorisés).

- [ ] **Step 2: Vérification visuelle**

`docker compose up -d --build`, puis ouvrir http://localhost:8095 :
- barre latérale, onglet du navigateur, écran de connexion : « Cotalyx » ;
- survol des boutons « Enregistrer » des Réglages, des réglages Admin, d'un select de l'Explorer : main ;
- se connecter (l'ancienne session est perdue, c'est attendu), accepter les nouvelles CGU.

- [ ] **Step 3: Pousser et ouvrir la PR**

```bash
git push -u origin cotalyx
gh pr create --base master --title "Cotalyx: rename, neutral wording, pointer cursor (bloc A)" --body "$(cat <<'EOF'
Bloc A du spec docs/superpowers/specs/2026-10-01-cotalyx-design.md.

- Curseur « main » sur tout élément cliquable (règle globale), « interdit » sur ce qui est désactivé.
- Nom Cotalyx partout (API, mails, SEO, assistant, interface, guide, documentation).
- Textes neutres : plus de « votre PEA », plus de « Crédit Agricole » comme banque supposée.
- Cookies renommés en cotalyx_* : tout le monde est déconnecté une fois au déploiement.
- TERMS_VERSION / CGV_VERSION = 2026-10-06 : chaque compte réaccepte les CGU.

À faire à la main : MAIL_FROM dans .env.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Arrêt**

Donner à l'utilisateur un court état (fait, PR, prochain bloc B dont le plan sera écrit au départ) et s'arrêter pour qu'il puisse faire `/compact`.
