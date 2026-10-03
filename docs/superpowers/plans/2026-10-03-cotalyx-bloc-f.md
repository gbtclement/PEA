# Cotalyx bloc F — SEO et performances — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Public pages arrive ready for search engines (title, description, canonical, Open Graph, JSON-LD, readable summary and the page's data embedded in the HTML), the Explorer/ETF lists are paginated server-side, the first JavaScript is light, public API answers are cacheable, the sitemap scales to ~18 000 securities, and Lighthouse mobile scores ≥ 95.

**Architecture:** nginx sends public page URLs (`/`, `/explorer`, `/etf`, `/titres/:id`, `/premium`, legal pages) to a new API route `GET /api/seo/page?path=…`, which fills the built `index.html` (fetched once from the web container at `SPA_TEMPLATE_URL`, cached) with head tags, a semantic HTML summary inside `#root` and a `<script id="cotalyx-data" type="application/json">` holding React Query entries; `main.tsx` seeds the query cache from it before rendering. If the API fails, nginx falls back to the static `index.html`. The screener endpoint gains filters/sort/pagination in SQL; the frontend uses `useInfiniteQuery`. A small FastAPI helper sets `Cache-Control`/`ETag` on public GET answers (private when a session cookie is present).

**Tech Stack:** FastAPI, SQLAlchemy 2, PostgreSQL, nginx 1.27; React 19, TanStack Query (infinite queries), Vite 8 (rolldown), Vitest, Playwright, Lighthouse.

**Spec:** `docs/superpowers/specs/2026-10-03-mobile-seo-mise-en-ligne-design.md` (section « Bloc F — SEO et performances »).

## Global Constraints

- Branch `seo-performances`, created from `mobile` (block E, not merged yet). PR at the end; the user is away and pre-approved plan and execution: no questions, stop after the block.
- French UI/comments/docs; English conventional commits ending with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Never open `.env`. Don't touch `.superpowers/` or `docs/superpowers/` except this plan and its ledger. Never modify existing Alembic migrations.
- Public pages enriched: `/`, `/explorer`, `/etf`, `/titres/:id`, `/premium`, `/cgu`, `/cgv`, `/mentions-legales`, `/confidentialite`. Private pages keep the static `index.html`.
- Server-generated title/description must equal what the page sets in the browser (same texts; e2e checks the served HTML against `document.title` after load).
- Unknown security → real HTTP 404 with a `noindex` page.
- API failure → nginx serves static `index.html` (app works as today).
- Screener: `limit` 50 default (max 200), `offset`, `{items, total}`; first page ≤ 60 KB gzip; filters stay in the URL.
- Cache: `/assets/*` 1 year immutable; HTML `no-cache`; public API GET 30–60 s + `ETag`; any request carrying the session cookie → `private, no-store`.
- Sitemap index, files ≤ 10 000 URLs, `lastmod` from last quote/score, only securities with a quote, guide pages included.
- Lighthouse mobile ≥ 95 in Performance, SEO, Accessibility, Best Practices on `/`, `/explorer`, one security page (report attached to the PR).
- Tests: backend `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q`; frontend `npx tsc -b`, `npx vitest run`, `npx oxlint` (add `< /dev/null`); API types `npm run gen:api` (dev API rebuilt first); e2e as in block E (e2e stack, `mailpit` up, restore normal stack afterwards).

## Review Focus

1. A signed-in member must never receive another member's data from a cache, and the embedded data must be computed for the requester (favourites, envelopes) or not embedded. Test: `test_page_html_is_never_publicly_cached` and `test_public_api_private_with_session` (Tasks 1, 4).
2. Text injected in HTML (security names with `<`, `&`, quotes; `</script>` inside JSON) must be escaped. Test: `test_page_escapes_names_and_json` (Task 1).
3. Pagination with filters and sort must be stable (no duplicate or missing row between pages: tie-break on id). Test: `test_screener_pages_are_disjoint` (Task 2).
4. Changing a filter must restart at page 1 and not mix pages of two filter sets. Test: Vitest « changer un filtre repart de la première page » (Task 2).
5. API down or template unreachable → the site still loads. Test: `test_page_falls_back_when_template_missing` + nginx fallback e2e (Tasks 1, 6).

---

### Task 1: HTML enrichi (`/api/seo/page`) and embedded data

**Files:**
- Create: `backend/app/services/seo/page.py` (pure rendering: head tags, summaries, JSON script), `backend/app/services/seo/__init__.py`, `backend/tests/test_seo_page.py`
- Modify: `backend/app/api/routes/seo.py` (route `GET /seo/page`), `backend/app/core/config.py` (`spa_template_url: str = "http://web/_spa/index.html"`), `frontend/nginx/default.conf.template`, `frontend/src/main.tsx`, `frontend/src/lib/queryClient.ts` (`seedFromPage(client)`), `frontend/src/lib/queryClient.test.ts`, `docker-compose.dev.yml` only if the dev API needs `SPA_TEMPLATE_URL` (dev uses Vite: leave unset → route returns 503 and is unused)

**Interfaces:**
- Produces: `render_page(template: str, page: PageContent) -> str`; `PageContent(title, description, canonical, noindex, json_ld: list[dict], summary_html: str, data: list[tuple[list, object]], status: int)`; builders `home_page(db, user)`, `screener_page(db, user, kind)`, `security_page(db, user, security_id)`, `static_page(path)`; route `GET /api/seo/page?path=` → `text/html`, `Cache-Control: no-cache, private`.
- Frontend: `seedFromPage(client: QueryClient, doc = document)` reads `#cotalyx-data` (array of `[queryKey, data]`) and calls `client.setQueryData` for each.
- Query keys embedded must match the frontend exactly: `["me"]` (member or `null`), `["top", account]` (`account` = user id or `"visiteur"`), `["screener", kind, region, filtersKey]` (first page, see Task 2), `["security", String(id)]`.

- [ ] **Step 1: Failing tests** — `backend/tests/test_seo_page.py` covering:
  - `test_security_page_has_head_summary_and_data`: GET `/api/seo/page?path=/titres/{id}` (template injected via dependency override) → 200, `<title>LVMH (MC) — cours, score et analyse | Cotalyx</title>`, `meta name="description"` equal to the frontend formula, canonical `https://…/titres/{id}`, `og:title`, JSON-LD `Corporation` + `BreadcrumbList`, the summary contains the name, the price with currency and the score reasons, and `#cotalyx-data` contains `["security","{id}"]`.
  - `test_unknown_security_is_404_noindex`.
  - `test_home_and_lists`: `/` contains the top 10 names and `["top","visiteur"]`; `/explorer` contains links to the first securities.
  - `test_page_escapes_names_and_json`: a security named `A <b>&"x"</b></script>` → no raw `<b>`, no `</script>` inside the JSON script (`<\/` escaping).
  - `test_page_html_is_never_publicly_cached`: response `Cache-Control` contains `private` and `no-cache`.
  - `test_page_falls_back_when_template_missing`: template loader raises → 503 (nginx then serves the static file).
  - `test_signed_in_member_gets_his_own_data`: with a session, `["me", …]` holds the member and `["top", "<user id>"]` is used.
  Frontend `queryClient.test.ts`: `seedFromPage` fills the cache from a script element and ignores a malformed one.

- [ ] **Step 2: Run** them. Expected: FAIL (route missing).

- [ ] **Step 3: Implement**
  - `services/seo/page.py`: `escape` from `html`; JSON via `json.dumps(..., ensure_ascii=False).replace("</", "<\\/")`; head block inserted before `</head>` (remove the template's default `<title>`/description first); summary inserted into `<div id="root"></div>` → `<div id="root">…</div>`; data script inserted before the module script. Titles/descriptions copied from the frontend: home `Cotalyx` + `DEFAULT_DESCRIPTION`; Explorer/ETF from `router.tsx`; security from `securityMeta` in `SecurityPage.tsx` (same score/envelope wording); Premium and legal pages from their `usePageMeta` calls. Keep these strings in one Python module with a comment pointing to the frontend source.
  - Data: build with the same Pydantic schemas and repository calls as the JSON routes (`SecurityDetail`, `TopItem`, `MeOut`…), serialized with `model_dump(mode="json")`.
  - Template loader: `httpx.get(settings.spa_template_url, timeout=2)`, cached 60 s in memory; overridable dependency for tests.
  - nginx: `location = /_spa/index.html { alias /usr/share/nginx/html/index.html; }`; for `~ ^/(|explorer|etf|premium|cgu|cgv|mentions-legales|confidentialite|titres/[0-9]+)$`: `proxy_pass http://api:8000/api/seo/page?path=$uri;` with `proxy_intercept_errors on; error_page 500 502 503 504 = /index.html;` (404 passes through), forwarding cookies and `X-Forwarded-For`.
  - `main.tsx`: `seedFromPage(queryClient)` before `createRoot`.

- [ ] **Step 4: Run** backend file + suite, frontend vitest + tsc. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: public pages served with head tags, readable summary and embedded data`

---

### Task 2: Explorer and ETF paginated server-side

**Files:**
- Modify: `backend/app/repositories/screener.py` (new `screener_page(...)` + `screener_facets(...)`), `backend/app/api/routes/screener.py`, `backend/app/schemas/screener.py` (`ScreenerPage {items, total}`, `ScreenerFacets {sectors, countries, markets}`), `frontend/src/features/screener/useScreener.ts` (`useInfiniteQuery`), `ScreenerPage.tsx`, `ScreenerFilters.tsx` (facets from the API), `filters.ts` (`filtersKey(f)`, params builder; `filterRows` removed), `components/DataTable.tsx` (`onEndReached`, `manualSorting`)
- Test: `backend/tests/test_api_screener.py`, `frontend/src/features/screener/ScreenerPage.test.tsx`, `filters.test.ts`

**Interfaces:**
- `GET /api/screener?kind&region&q&sector&country&market&envelope&min_score&min_price&max_price&liquid&fav&sort&order&limit&offset` → `{items: ScreenerRow[], total: int}`; sort keys = `SORT_KEYS` of the frontend; nulls last; tie-break `Security.id`; name sort = numeric prefix then `lower(name)` (natural order kept); search accent-insensitive via `translate(lower(...))` on name, symbol, ISIN.
- `GET /api/screener/facets?kind&region` → distinct sectors, countries, places of priced securities.
- `DataTable` props `manualSorting?: boolean`, `onEndReached?: () => void` (called when the last rendered virtual item is within 10 of the end).
- Query key `["screener", kind, region, filtersKey(filters, sort)]` (Task 1 embeds the first page under this key for the default filters).

- [ ] **Step 1: Failing tests** — backend: filters (each one), sort asc/desc with nulls last, `test_screener_pages_are_disjoint` (3 pages of 2 cover 6 ids exactly), `fav` requires a session (ignored for visitors), facets. Frontend: first page rendered from `{items,total}` with count = `total`; scrolling to the end requests `offset=50`; « changer un filtre repart de la première page » (query with `offset=0` and new params, old pages dropped); sort header click sends `sort`/`order`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** as specified (SQL in the repository; route maps params; `useInfiniteQuery` with `getNextPageParam: (last, pages) => loaded < total ? loaded : undefined`; `DataTable` gets `manualSorting` and calls `onEndReached`; `ScreenerFilters` takes `facets` instead of `rows`). Rankings/security_detail keep using `screener_rows`.
- [ ] **Step 4: Run** suites, `npm run gen:api`, tsc. Expected: PASS.
- [ ] **Step 5: Commit** — `feat: server-side filters, sort and pagination for the Explorer and ETF lists`

---

### Task 3: Lighter JavaScript, images, fonts

**Files:**
- Modify: `frontend/vite.config.ts` (vendor chunks), `frontend/src/features/home/MarketHeatmap.tsx` (load `EChart` when visible), `frontend/src/features/portfolio/PortfolioPage.tsx` (lazy `EChart`), `frontend/index.html` (preload font, `og:image`, `apple-touch-icon`), `frontend/public/` (`og-image.png` 1200×630, `apple-touch-icon.png` 180×180, generated from `favicon.svg`), `frontend/src/index.css` (font-display)
- Test: `frontend/src/features/home/HomePage.test.tsx` (heatmap placeholder until visible), bundle budget script `frontend/scripts/check-bundle.mjs` run in the task

**Interfaces:** `useInView(ref)` hook (`lib/useInView.ts`, IntersectionObserver, true once seen; jsdom stub returns true).

- [ ] **Step 1: Failing test** — HomePage test: with IntersectionObserver never firing, the heatmap shows a placeholder and `EChart` is not rendered; once visible, it renders. Bundle script: fails if the JS needed by `/` (entry + its static imports, from `dist/.vite/manifest.json`) exceeds 120 KB gzip.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** — `React.lazy` + `Suspense` for `EChart` in heatmap and portfolio, rendered only when in view; `build.rolldownOptions.output.advancedChunks` (or `manualChunks`) groups `react`/`react-dom`/`react-router`, `@tanstack/*`, `@base-ui/*` + `lucide-react`; `build.manifest = true`; font `@fontsource-variable/inter` preloaded with `font-display: swap`; OG image and touch icon added and referenced (also in the server head of Task 1).
- [ ] **Step 4: Run** build + budget script + vitest + tsc. Expected: PASS, budget met.
- [ ] **Step 5: Commit** — `perf: load charts on demand, split vendor chunks, font and social images`

---

### Task 4: Cache headers

**Files:**
- Create: `backend/app/api/cache.py` (`public_cache(max_age)` dependency + ETag middleware for marked routes)
- Modify: public GET routes (`rankings` top/movers/heatmap, `screener` + facets, `security_detail` detail/history/fundamentals/news, `status`, `billing/plans`, `seo` robots/sitemap/llms), `frontend/nginx/default.conf.template` (`index.html` no-cache, gzip types/level)
- Test: `backend/tests/test_api_cache.py`

**Interfaces:** `public_cache(seconds)` — sets `Cache-Control: public, max-age=seconds` and `Vary: Cookie` when no session cookie, else `private, no-store`; middleware adds a weak `ETag` (sha256 of the body) on responses that carry `public` and answers `304` to a matching `If-None-Match`.

- [ ] **Step 1: Failing tests** — `test_public_answer_is_cacheable_with_etag`, `test_if_none_match_gives_304`, `test_public_api_private_with_session` (signed-in client → `private, no-store`), `test_personal_routes_never_public` (portfolio, me).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement**; nginx: `location = /index.html { add_header Cache-Control "no-cache"; … }` (keep security headers include), `gzip_types` + `application/xml text/markdown text/plain`, `gzip_comp_level 6`, `gzip_vary on`.
- [ ] **Step 4: Run** suite. Expected: PASS.
- [ ] **Step 5: Commit** — `perf: cacheable public API answers with ETag, no-cache HTML`

---

### Task 5: Sitemap index

**Files:** `backend/app/api/routes/seo.py`, `frontend/nginx/default.conf.template` (`location ~ ^/sitemap-[a-z0-9-]+\.xml$`), `frontend/vite.config.ts` (dev proxy for sitemaps), `backend/tests/test_api_seo.py`

**Interfaces:** `/sitemap.xml` → `<sitemapindex>` listing `/sitemap-pages.xml`, `/sitemap-actions-1.xml`…, `/sitemap-etf-1.xml`…, `/sitemap-guide.xml`; each ≤ 10 000 URLs with `lastmod` (date of `quotes.as_of` or `scores.computed_at`, latest).

- [ ] **Step 1: Failing tests** — index lists the files; a file holds ≤ 10 000 URLs (patch the constant to 2 in the test); unpriced securities absent; `lastmod` present; guide pages listed (read `frontend/public/guide/_sidebar.md` at build? — no: list the guide paths in a Python constant kept next to `PUBLIC_PATHS`, with a test that each file exists in `frontend/public/guide` when the folder is available).
- [ ] **Step 2: Run.** FAIL. **Step 3: Implement. Step 4: Run.** PASS.
- [ ] **Step 5: Commit** — `feat: sitemap index with lastmod, priced securities only, guide pages`

---

### Task 6: Lighthouse, e2e, docs

**Files:**
- Create: `frontend/scripts/lighthouse.mjs` (runs `npx --yes lighthouse@12` with Playwright's Chromium in mobile mode on the three pages, prints the four scores, exits 1 under 95), `frontend/e2e/seo-html.spec.ts`
- Modify: `frontend/e2e/seo.spec.ts` if it relied on client-only meta, docs (`documentation/architecture.md` rendering + cache, `documentation/api.md` screener params/facets/page route, `documentation/donnees.md` sitemap), `CLAUDE.md` (SEO section), `README.md` if it lists API behaviour

- [ ] **Step 1: e2e** — `seo-html.spec.ts`: fetch `/titres/<id>` with `request` (no JS) → contains `<title>`, description, canonical, JSON-LD and the security name in `#root`; after a real page load, `document.title` equals the served title; `/titres/99999999` → 404; Explorer scroll loads more rows.
- [ ] **Step 2: Run** the e2e stack + full e2e; fix what fails (each fix committed).
- [ ] **Step 3: Lighthouse** — run the script on the e2e stack (SEO indexing is off there: run with `SEO_INDEXING=true` for the SEO category, via the e2e compose env if needed); iterate on findings (contrast, labels, image sizes, render-blocking) until ≥ 95; keep the printed scores for the PR.
- [ ] **Step 4: Docs** — as listed; full checks; restore the normal stack.
- [ ] **Step 5: Commit** — `test: served-HTML and Lighthouse checks; docs: rendering, cache, sitemap`
