# Cotalyx bloc E — Mobile — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every page except Admin usable on a 360 px phone: drawer navigation, one-column layouts, list rows as cards, full-screen dialogs, a bottom action bar on security pages.

**Architecture:** Mostly CSS (Tailwind breakpoints `md` = 768 px, `lg` = 1024 px) on existing components. Two shared pieces: a `useIsMobile()` hook (matchMedia `< 768px`) used where markup must differ (virtualized lists render cards instead of grid rows), and a `MobileHeader` with a left `Sheet` drawer that replaces the sidebar under 1024 px. Desktop (≥ 1024 px) stays pixel-identical.

**Tech Stack:** React 19, react-router 7, Tailwind 4, shadcn/base-ui (`Sheet`, `Dialog`), TanStack Table/Virtual, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-03-mobile-seo-mise-en-ligne-design.md` (section « Bloc E — Mobile »).

## Global Constraints

- Branch `mobile` (already created from `master`, holds the spec commit); PR against `master` at the end. Stop after the block.
- Interface text, comments and docs in French; commits in English (conventional commits), ending with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Never open or print `.env`. Do not modify files under `.superpowers/` or `docs/superpowers/` except this plan and its ledger.
- Breakpoints: phone < 768 px, tablet 768–1023 px, desktop ≥ 1024 px (unchanged). No horizontal page scroll at 360 px. One column under 768 px, 16 px side margins.
- Under 1024 px: no sidebar; top bar (logo, ☰ menu, account) and a left drawer with the same links, place status, guide link, sign-in or account menu; the drawer closes on link choice, Escape, outside tap.
- Lists (Explorer, ETF, Prévisions) under 768 px: one card per row (name, symbol · place, price with currency, day change, score, envelope badges, favourite); tap opens the security; sort and filters in a full-screen « Filtres » panel; region toggle stays visible; list stays virtualized.
- Security page under 768 px: full-width chart, horizontally scrolling period buttons, indicator toggles in a menu, stacked cards, actions (favourite, alert, order, assistant) in a fixed bottom bar.
- Dialogs full-screen on phones. Assistant full-screen with the composer pinned at the bottom.
- Touch: targets ≥ 44 × 44 px on phones; nothing reachable only on hover; form fields ≥ 16 px font on phones (no iOS zoom).
- Admin tab and admin documentation: out of scope.
- Tests:
  - frontend (in `frontend/`): `npx tsc -b`, `npx vitest run`, `npx oxlint` (add `< /dev/null`);
  - e2e: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build api worker web` (and `docker compose up -d mailpit`), then `npm run e2e` in `frontend/`; restore with `docker compose up -d --build api worker web`.

## Review Focus

1. Rotating a phone or resizing across 768 px must not lose state (filters in the URL, open drawer closes cleanly, the list re-renders as table or cards without a blank screen). Test: `useIsMobile` reacts to `change` events (Task 2).
2. The drawer must not stay open after navigating (back button included) and must not trap focus after closing. Test: « le tiroir se ferme quand on change de page » (Task 1).
3. iOS keyboard: the assistant composer and full-screen dialogs must keep the focused field visible (layout uses `dvh`, not `vh`). Test: e2e at 390 × 664 (Task 7).
4. Long names (e.g. « Société Générale Société anonyme »), long prices (« 24 240,00 DKK ») and envelope badges must wrap or truncate inside a 328 px card, never overflow. Test: card with a long name and DKK price in the e2e clip check (Task 7) and in `ScreenerCard` unit test (Task 3).
5. Desktop must not change: the existing `layout.spec.ts` (1100–1440 px) and `table.spec.ts` stay green.

---

### Task 1: Layout and mobile navigation

**Files:**
- Create: `frontend/src/app/MobileHeader.tsx`, `frontend/src/app/MobileHeader.test.tsx`
- Modify: `frontend/src/app/Layout.tsx`, `frontend/src/app/Sidebar.tsx`, `frontend/src/index.css`

**Interfaces:**
- Produces: `MobileHeader({ footer, account, admin }: { footer?: ReactNode; account?: ReactNode; admin?: boolean })` — top bar + drawer, rendered only below `lg` via CSS (`lg:hidden`); `SidebarNav({ items, onNavigate })` exported from `Sidebar.tsx` (the list of `NavLink`s plus the guide link, shared by sidebar and drawer).

- [ ] **Step 1: Failing tests** — `frontend/src/app/MobileHeader.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { renderWithProviders } from "@/test/utils";
import { MobileHeader } from "./MobileHeader";

function renderHeader(route = "/") {
  return renderWithProviders(
    <Routes>
      <Route path="*" element={<><MobileHeader footer={<p>Europe : ouverte</p>} account={<p>Compte</p>} /><p>page</p></>} />
    </Routes>,
    { route },
  );
}

test("le menu s'ouvre en tiroir avec les liens, l'état des places et le guide", async () => {
  renderHeader();
  expect(screen.queryByRole("navigation", { name: "Navigation principale" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
  const nav = await screen.findByRole("navigation", { name: "Navigation principale" });
  expect(nav).toHaveTextContent("Explorer");
  expect(screen.getByText("Europe : ouverte")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Guide" })).toHaveAttribute("href", "/guide/");
});

test("le tiroir se ferme quand on change de page", async () => {
  renderHeader();
  await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
  await userEvent.click(await screen.findByRole("link", { name: "Explorer" }));
  expect(screen.queryByRole("navigation", { name: "Navigation principale" })).not.toBeInTheDocument();
});

test("Échap ferme le tiroir", async () => {
  renderHeader();
  await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
  await screen.findByRole("navigation", { name: "Navigation principale" });
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("navigation", { name: "Navigation principale" })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run** `npx vitest run src/app/MobileHeader.test.tsx < /dev/null`. Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`Sidebar.tsx`: extract the `<nav>` list and the guide link into an exported `SidebarNav`:

```tsx
export function SidebarNav({ admin = false, onNavigate }: { admin?: boolean; onNavigate?: () => void }) {
  const items = admin ? [...NAV_ITEMS, ADMIN_ITEM] : NAV_ITEMS;
  return (
    <>
      <nav aria-label="Navigation principale" className="flex-1 space-y-1 px-3">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} onClick={onNavigate}
                   className={({ isActive }) => cn(
                     "flex min-h-11 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors lg:min-h-0",
                     isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
            <Icon className="size-4" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>
      {/* Le guide est servi par nginx hors de l'application : lien classique, pas NavLink. */}
      <div className="px-3 pb-3">
        <a href="/guide/" className="flex min-h-11 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground lg:min-h-0">
          <BookOpen className="size-4" aria-hidden />
          Guide
        </a>
      </div>
    </>
  );
}
```

`Sidebar` keeps its markup but uses `<SidebarNav admin={admin} />` between the logo and the account block (keep the existing order: logo, nav, account, guide, footer — move the account block before the guide as today by rendering `{account && …}` between `nav` and guide: split `SidebarNav` usage accordingly, or pass `account` as a prop to `SidebarNav`; keep the DOM order identical to today so `Sidebar.test.tsx` stays green). Add `hidden lg:flex` to the `<aside>` class.

`MobileHeader.tsx`:

```tsx
import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router";
import { Menu, Radar } from "lucide-react";
import { Link } from "react-router";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { SITE_NAME } from "@/seo/schema";
import { SidebarNav } from "./Sidebar";

/** Sous 1024 px : barre du haut et menu en tiroir (la barre latérale est masquée). */
export function MobileHeader({ footer, account, admin = false }: { footer?: ReactNode; account?: ReactNode; admin?: boolean }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);  // bouton retour compris
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-2 border-b border-border bg-white px-2 lg:hidden">
      <button type="button" aria-label="Ouvrir le menu" onClick={() => setOpen(true)}
              className="flex size-11 items-center justify-center rounded-lg hover:bg-muted">
        <Menu className="size-5" aria-hidden />
      </button>
      <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
        <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Radar className="size-4" aria-hidden />
        </span>
        {SITE_NAME}
      </Link>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-72 gap-0 p-0 pt-4" aria-describedby={undefined}>
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <SidebarNav admin={admin} onNavigate={() => setOpen(false)} />
          {account && <div className="border-t border-border px-4 py-3">{account}</div>}
          {footer && <div className="border-t border-border px-6 py-4">{footer}</div>}
        </SheetContent>
      </Sheet>
    </header>
  );
}
```

(Check `components/ui/sheet.tsx` exports `SheetTitle`; add it following the file's pattern if missing.)

`Layout.tsx`: remove `min-w-[1024px]`; render `<MobileHeader footer={<MarketStatus />} account={<AccountMenu />} admin={me?.role === "admin"} />` before the sidebar; `main` → `className="px-4 py-4 md:px-8 md:py-6 lg:ml-60"`; footer → `className="px-4 pb-6 md:px-8 lg:ml-60"`.

`index.css`: add

```css
/* Téléphones : champs en 16 px, sinon iOS zoome la page à la saisie. */
@media (max-width: 767px) {
  input, select, textarea { font-size: 16px; }
}
```

- [ ] **Step 4: Run** the new test file, then `npx vitest run < /dev/null` (Sidebar and router tests must stay green), `npx tsc -b < /dev/null`. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: mobile top bar and drawer navigation, layout without minimum width`

---

### Task 2: `useIsMobile` and full-screen dialogs

**Files:**
- Create: `frontend/src/lib/useIsMobile.ts`, `frontend/src/lib/useIsMobile.test.tsx`
- Modify: `frontend/src/test/setup.ts` (matchMedia stub), `frontend/src/components/ui/dialog.tsx`

**Interfaces:**
- Produces: `useIsMobile(): boolean` (true under 768 px, follows `change` events); test helper `setViewportWidth(px: number)` exported from `frontend/src/test/utils.tsx`.

- [ ] **Step 1: Failing tests** — `useIsMobile.test.tsx`:

```tsx
import { act, renderHook } from "@testing-library/react";
import { setViewportWidth } from "@/test/utils";
import { useIsMobile } from "./useIsMobile";

afterEach(() => setViewportWidth(1200));

test("vrai sous 768 px, et suit la rotation de l'écran", () => {
  setViewportWidth(390);
  const { result } = renderHook(() => useIsMobile());
  expect(result.current).toBe(true);
  act(() => setViewportWidth(1024));
  expect(result.current).toBe(false);
});
```

- [ ] **Step 2: Run** it. Expected: FAIL (no module / no `setViewportWidth`).

- [ ] **Step 3: Implement**

`test/setup.ts` — jsdom has no `matchMedia`; add a stub driven by a mutable width:

```ts
let viewportWidth = 1200;
const listeners = new Set<() => void>();
export function __setViewportWidth(px: number) {
  viewportWidth = px;
  listeners.forEach((notify) => notify());
}
Object.defineProperty(window, "matchMedia", {
  configurable: true,
  value: (query: string) => {
    const max = Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Infinity);
    const mql = {
      get matches() { return viewportWidth <= max; },
      media: query,
      addEventListener: (_: string, cb: () => void) => listeners.add(cb),
      removeEventListener: (_: string, cb: () => void) => listeners.delete(cb),
      addListener: (cb: () => void) => listeners.add(cb),
      removeListener: (cb: () => void) => listeners.delete(cb),
      onchange: null, dispatchEvent: () => true,
    };
    return mql;
  },
});
```

`test/utils.tsx`: `export { __setViewportWidth as setViewportWidth } from "./setup";` (if importing from the setup file is awkward, move the stub to `test/viewport.ts`, import it from `setup.ts`, and re-export from `utils.tsx`).

`lib/useIsMobile.ts`:

```ts
import { useSyncExternalStore } from "react";

const QUERY = "(max-width: 767px)";

/** Téléphone (moins de 768 px) : listes en cartes, fenêtres plein écran. Suit la rotation de l'écran. */
export function useIsMobile(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const mql = window.matchMedia(QUERY);
      mql.addEventListener("change", notify);
      return () => mql.removeEventListener("change", notify);
    },
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}
```

`dialog.tsx` `DialogContent` popup classes: prepend phone full-screen classes
`max-md:inset-0 max-md:top-0 max-md:left-0 max-md:h-dvh max-md:max-w-none max-md:translate-x-0 max-md:translate-y-0 max-md:overflow-y-auto max-md:rounded-none` (keep existing classes for ≥ 768 px). Close button: `size-11` on phones (`max-md:size-11`).

- [ ] **Step 4: Run** the test, the whole vitest suite (dialogs used in many tests) and `npx tsc -b`. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: useIsMobile hook and full-screen dialogs on phones`

---

### Task 3: Explorer, ETF and Prévisions as cards on phones

**Files:**
- Create: `frontend/src/features/screener/ScreenerCard.tsx`, `frontend/src/features/screener/ScreenerCard.test.tsx`, `frontend/src/features/screener/FiltersSheet.tsx`
- Modify: `frontend/src/components/DataTable.tsx`, `frontend/src/features/screener/ScreenerPage.tsx`, `frontend/src/features/screener/ScreenerFilters.tsx`, `frontend/src/features/forecasts/PredictionsView.tsx`
- Test: `frontend/src/features/screener/ScreenerPage.test.tsx`

**Interfaces:**
- Consumes: `useIsMobile()`, `setViewportWidth()` (Task 2).
- Produces: `DataTable` prop `renderCard?: (row: T) => ReactNode` — when set and `useIsMobile()` is true, the table renders a virtualized list of cards (estimated height 112 px) instead of grid rows; `ScreenerCard({ row })`; `FiltersSheet({ children, active })` — button « Filtres (n) » opening a full-screen sheet with `children`.

- [ ] **Step 1: Failing tests**

`ScreenerCard.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { ScreenerCard } from "./ScreenerCard";

const ROW = { id: 7, yahoo_ticker: "MAERSK-B.CO", symbol: "MAERSK B", name: "A.P. Møller - Mærsk B Société anonyme très longue",
  kind: "stock", market: "Nasdaq Copenhagen", country: "DK", sector: "Industrie", envelopes: ["pea"], price: 24240,
  currency: "DKK", change_pct: -1.23, perf_1w: 1, perf_1m: 2, perf_1y: 3, score: 71.4, pe: 12, dividend_yield: 0.02,
  liquid: true, available_ratio: 1, isin: "DK0010244508", is_favorite: false, sparkline: [1, 2] };

test("carte : nom, place, cours avec devise, variation, score et badge", () => {
  renderWithProviders(<ScreenerCard row={ROW as never} />);
  expect(screen.getByText(/Mærsk B Société anonyme/)).toHaveClass("truncate");
  expect(screen.getByText("MAERSK B · Nasdaq Copenhagen")).toBeInTheDocument();
  expect(screen.getByText("24 240,00 DKK")).toBeInTheDocument();
  expect(screen.getByText(/-1,23/)).toHaveClass("text-down");
  expect(screen.getByText("71")).toBeInTheDocument();
  expect(screen.getByText("PEA")).toBeInTheDocument();
});
```

Append to `ScreenerPage.test.tsx`:

```tsx
test("sur téléphone, une carte par titre et les filtres dans un panneau", async () => {
  setViewportWidth(390);
  try {
    renderPage();
    await screen.findByText("LVMH");
    expect(screen.queryByRole("columnheader")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Airbus|Danone|LVMH/ })).toHaveLength(3);
    await userEvent.click(screen.getByRole("button", { name: /Filtres/ }));
    expect(await screen.findByRole("combobox", { name: "Secteur" })).toBeVisible();
  } finally {
    setViewportWidth(1200);
  }
});
```

(Import `setViewportWidth` from `@/test/utils`. Check the formatted DKK price string against `formatPrice` + `currencyUnit` output: `formatPrice(24240)` uses a narrow no-break space as thousands separator in `fr-FR`; write the expectation with the exact character the existing format tests use, or match with a regex `/24\s?240,00 DKK/`.)

- [ ] **Step 2: Run** both files. Expected: FAIL.

- [ ] **Step 3: Implement**

`ScreenerCard.tsx`:

```tsx
import { Link } from "react-router";
import { FavoriteButton } from "@/components/FavoriteButton";
import { EnvelopeBadges } from "@/features/security/EnvelopeBadges";  // reuse the existing badge component (check its path)
import type { ScreenerRow } from "@/lib/api/client";
import { currencyUnit, formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Ligne de l'Explorer sur téléphone : tout tient dans 328 px, le nom long est tronqué. */
export function ScreenerCard({ row }: { row: ScreenerRow }) {
  const change = row.change_pct ?? 0;
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-card p-3">
      <Link to={`/titres/${row.id}`} className="min-w-0 flex-1">
        <p className="truncate font-medium">{row.name}</p>
        <p className="truncate text-xs text-muted-foreground">{row.symbol} · {row.market}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm tabular-nums">
          <span className="font-medium whitespace-nowrap">
            {row.price == null ? "—" : `${formatPrice(row.price)} ${currencyUnit(row.currency)}`}
          </span>
          <span className={cn("whitespace-nowrap", change > 0 && "text-up", change < 0 && "text-down")}>{formatPct(row.change_pct)}</span>
          <EnvelopeBadges codes={row.envelopes} />
        </div>
      </Link>
      <div className="flex flex-col items-end gap-1">
        {row.score != null && <span className="rounded-md bg-muted px-2 py-0.5 text-sm font-semibold tabular-nums">{Math.round(row.score)}</span>}
        <FavoriteButton securityId={row.id} isFavorite={row.is_favorite} />
      </div>
    </div>
  );
}
```

(Find the real badge component with `grep -rn "export function EnvelopeBadges" src`; the Link's accessible name contains the security name so the page test's `getAllByRole("link", { name: … })` works. `FavoriteButton` must keep a 44 px hit area on phones: add `max-md:size-11` to its button if smaller.)

`DataTable.tsx`: add `renderCard?: (row: T) => ReactNode`; `const mobile = useIsMobile() && renderCard !== undefined;` — when `mobile`, render instead of the header and grid rows:

```tsx
<div ref={scrollRef} className={cn(heightClass, "overflow-auto")}>
  <div ref={bodyRef} style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
    {virtualizer.getVirtualItems().map((item) => (
      <div key={item.key} data-index={item.index} ref={virtualizer.measureElement}
           className="absolute inset-x-0 px-1 pb-2" style={{ transform: `translateY(${item.start - virtualizer.options.scrollMargin}px)` }}>
        {renderCard(tableRows[item.index].original)}
      </div>
    ))}
  </div>
</div>
```

with `estimateSize: () => (mobile ? 112 : ROW_HEIGHT)` (sorting still applies: cards follow `tableRows`). Hooks stay unconditional (same `useVirtualizer` call). Phone height: pass `heightClass` from the page; default for cards `h-[calc(100dvh-220px)] min-h-[360px]`.

`FiltersSheet.tsx`:

```tsx
import { useState, type ReactNode } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";

/** Téléphone : filtres et tri dans un panneau plein écran (ils restent dans l'URL). */
export function FiltersSheet({ children, active }: { children: ReactNode; active: number }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="outline" className="min-h-11" onClick={() => setOpen(true)}>
        <SlidersHorizontal className="size-4" aria-hidden /> Filtres{active ? ` (${active})` : ""}
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="bottom" className="h-dvh overflow-y-auto p-4" aria-describedby={undefined}>
          <SheetTitle>Filtres</SheetTitle>
          <div className="flex flex-col gap-3 [&_select]:min-h-11 [&_input]:min-h-11">{children}</div>
          <Button className="mt-4 min-h-11" onClick={() => setOpen(false)}>Voir les résultats</Button>
        </SheetContent>
      </Sheet>
    </>
  );
}
```

`ScreenerFilters.tsx`: split into `FilterFields` (all selects/inputs/checkboxes, plus a « Trier par » select listing `SORT_KEYS` labels and an order select — on phones there are no column headers to click) and the wrapper: on phones (`useIsMobile()`), render the search input full width, then `<FiltersSheet active={countActive(filters)}>` with `FilterFields`, then the count; on larger screens render today's single row unchanged. Search input class: `w-full md:w-60`.

`ScreenerPage.tsx`: pass `renderCard={(row) => <ScreenerCard row={row} />}` to `DataTable`; region toggle and header stay above. The sort select calls the existing `onSortingChange`.

`PredictionsView.tsx`: same `renderCard` with a `PredictionCard` defined in the same file (name, symbol · place, horizon, expected return colored, reliability, probability up), and its two filter selects wrap (`flex-wrap`, `min-h-11` on phones).

- [ ] **Step 4: Run** the screener, forecasts and DataTable-related tests, then the whole vitest suite and `tsc`. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: list rows as cards and filters panel on phones`

---

### Task 4: Security page on phones

**Files:**
- Create: `frontend/src/features/security/MobileActionBar.tsx`, `frontend/src/features/security/MobileActionBar.test.tsx`
- Modify: `frontend/src/features/security/SecurityPage.tsx`, `frontend/src/features/security/PriceChartPanel.tsx`, `frontend/src/features/security/PriceChart.tsx` (height), `frontend/src/features/security/ForecastCard.tsx`, `frontend/src/features/security/FundamentalsCard.tsx`
- Test: `frontend/src/features/security/SecurityPage.test.tsx`, `PriceChartPanel.test.tsx`

**Interfaces:**
- Consumes: `useIsMobile()` (Task 2).
- Produces: `MobileActionBar({ children })` — fixed bottom bar, `md:hidden`, with `pb-[env(safe-area-inset-bottom)]`; the page adds bottom padding (`pb-20 md:pb-0`) so content is not hidden.

- [ ] **Step 1: Failing tests**

`MobileActionBar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MobileActionBar } from "./MobileActionBar";

test("barre d'actions fixée en bas, masquée sur ordinateur", () => {
  render(<MobileActionBar><button type="button">Alerte</button></MobileActionBar>);
  const bar = screen.getByRole("toolbar", { name: "Actions sur ce titre" });
  expect(bar).toHaveClass("fixed", "bottom-0", "md:hidden");
  expect(screen.getByRole("button", { name: "Alerte" })).toBeInTheDocument();
});
```

Append to `PriceChartPanel.test.tsx`:

```tsx
test("sur téléphone, les indicateurs sont dans un menu et les périodes défilent", async () => {
  setViewportWidth(390);
  try {
    mockFetch(() => ({ body: BOUNDED }));
    renderWithProviders(<PriceChartPanel securityId={5} />);
    await waitFor(() => expect(chart.addSeries).toHaveBeenCalled());
    expect(screen.getByRole("group", { name: "Période" })).toHaveClass("overflow-x-auto");
    expect(screen.queryByRole("checkbox", { name: "RSI" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Indicateurs" }));
    expect(await screen.findByRole("checkbox", { name: "RSI" })).toBeInTheDocument();
  } finally {
    setViewportWidth(1200);
  }
});
```

- [ ] **Step 2: Run** both. Expected: FAIL.

- [ ] **Step 3: Implement**

`MobileActionBar.tsx`:

```tsx
import type { ReactNode } from "react";

/** Téléphone : actions de la fiche toujours à portée du pouce. */
export function MobileActionBar({ children }: { children: ReactNode }) {
  return (
    <div role="toolbar" aria-label="Actions sur ce titre"
         className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around gap-1 border-t border-border bg-white px-2 pt-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] md:hidden [&_button]:min-h-11">
      {children}
    </div>
  );
}
```

`SecurityPage.tsx`:
- header: price block `text-left md:text-right`, `w-full md:w-auto`; the action buttons (`+ J'ai acheté`, `AskAiButton`, `PriceAlertButton`) wrapped in `<div className="hidden flex-wrap items-center gap-2 md:flex">` and rendered a second time inside `<MobileActionBar>` (favourite, alert, « J'ai acheté », assistant) when `data.kind !== "index"`; the `FavoriteButton` next to the title stays.
- section: `className="space-y-6 pb-20 md:pb-0"`.
- Use stable accessible names so desktop tests that query buttons by name keep working: render the desktop group only when `!isMobile` and the bar only when `isMobile` (use `useIsMobile()`), so each button exists once in the DOM.

`PriceChartPanel.tsx`:
- wrap the period buttons in `<div role="group" aria-label="Période" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1 md:flex-wrap md:overflow-visible">` with `shrink-0` buttons;
- on phones (`useIsMobile()`), replace the four checkboxes by a button « Indicateurs » that toggles a small panel (`role="group" aria-label="Indicateurs"`) containing the same checkboxes; desktop unchanged;
- custom date form: inputs `w-full sm:w-40`.

`PriceChart.tsx`: chart height `isMobile ? 300 : 420` (and the skeleton in `PriceChartPanel` `h-[300px] md:h-[420px]`); keep `width` from the container.

`ForecastCard.tsx` `grid-cols-3` → `grid-cols-1 sm:grid-cols-3`; `FundamentalsCard.tsx` `grid-cols-2` → `grid-cols-1 sm:grid-cols-2`.

- [ ] **Step 4: Run** the security tests, whole vitest suite and `tsc`. Expected: PASS (desktop `SecurityPage.test.tsx` unchanged because the viewport stub defaults to 1200 px).

- [ ] **Step 5: Commit** — `feat: security page on phones — bottom action bar, scrolling periods, indicators menu`

---

### Task 5: Home, portfolio, forecasts, settings, Premium, account and legal pages

**Files:**
- Modify: `frontend/src/features/home/HomePage.tsx:20-22`, `frontend/src/features/home/IndicesBar.tsx:31,34`, `frontend/src/features/portfolio/PortfolioPage.tsx:36,52,127`, `frontend/src/features/portfolio/PositionsTable.tsx`, `frontend/src/features/portfolio/OrdersHistory.tsx`, `frontend/src/features/portfolio/OrderDialog.tsx:104,124`, `frontend/src/features/forecasts/TrackRecordView.tsx:37,79,97`, `frontend/src/features/forecasts/SignalStatsView.tsx`, `frontend/src/features/auth/SignUpForm.tsx:63`, `frontend/src/features/premium/PremiumPage.tsx`, settings cards with fixed rows, `frontend/src/features/legal/*`
- Test: `frontend/src/features/portfolio/PortfolioPage.test.tsx`

**Interfaces:**
- Consumes: `setViewportWidth()` (Task 2) in tests only; positions and orders use CSS-only switching (both markups rendered, `md:hidden` / `hidden md:table`), so no hook is needed.

- [ ] **Step 1: Failing test** — append to `PortfolioPage.test.tsx` (reuse its existing fetch mock for a portfolio with one position):

```tsx
test("positions aussi en cartes pour téléphone, avec le PRU expliqué sans survol", async () => {
  // (même mise en place que le test de la page avec une position)
  …render as in the existing positions test…
  const cards = await screen.findByRole("list", { name: "Positions" });
  expect(cards).toHaveClass("md:hidden");
  expect(within(cards).getByText(/PRU \(frais inclus\)/)).toBeInTheDocument();
});
```

Write it concretely from the existing positions test in the file (copy its arrange part; the `…` above stands for those exact lines, not for missing code).

- [ ] **Step 2: Run** it. Expected: FAIL.

- [ ] **Step 3: Implement** (class changes; desktop unchanged)

- `HomePage.tsx:22` `grid-cols-2 xl:grid-cols-1` → `grid-cols-1 md:grid-cols-2 xl:grid-cols-1`.
- `IndicesBar.tsx` `grid grid-cols-3 gap-4` (both lines) → `grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4`.
- `PortfolioPage.tsx:36` `grid-cols-4` → `grid-cols-2 lg:grid-cols-4`; `:52` `grid-cols-2` → `grid-cols-1 md:grid-cols-2`; `:127` `grid-cols-[1fr_2fr]` → `grid-cols-1 md:grid-cols-[1fr_2fr]`; page header actions wrap (`flex-wrap`).
- `PositionsTable.tsx`: keep the table with `hidden md:table`; add before it

```tsx
<ul aria-label="Positions" className="space-y-2 md:hidden">
  {positions.map((p) => (
    <li key={p.security_id} className="rounded-xl border border-border p-3 text-sm">
      <Link to={`/titres/${p.security_id}`} className="font-medium">{p.name}</Link>
      <span className="ml-2 text-xs text-muted-foreground">{p.symbol}</span>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 tabular-nums">
        <dt className="text-muted-foreground">Quantité</dt><dd className="text-right">{p.quantity}</dd>
        <dt className="text-muted-foreground">PRU (frais inclus)</dt><dd className="text-right">{formatPrice(p.avg_cost)} €</dd>
        <dt className="text-muted-foreground">Cours</dt><dd className="text-right">{p.price == null ? "—" : `${formatPrice(p.price)} €`}</dd>
        <dt className="text-muted-foreground">Valeur</dt><dd className="text-right">{formatPrice(p.value)} €</dd>
        <dt className="text-muted-foreground">+/- value</dt>
        <dd className={cn("text-right", p.gain > 0 && "text-up", p.gain < 0 && "text-down")}>
          {p.gain > 0 ? "+" : ""}{formatPrice(p.gain)} € ({formatPct(p.gain_pct)})
        </dd>
        <dt className="text-muted-foreground">Poids</dt><dd className="text-right">{formatRatioPct(p.weight)}</dd>
      </dl>
    </li>
  ))}
</ul>
```

(field names: copy them from the table cells of the same file — `p.gain_pct`, `p.weight` may be named differently.)
- `OrdersHistory.tsx`: same pattern (`hidden md:table` + `<ul aria-label="Ordres" className="md:hidden">` with date, sens, titre, quantité × prix, frais, montant, and the edit/delete buttons with `min-h-11`).
- `OrderDialog.tsx:104` `grid-cols-2` → `grid-cols-1 sm:grid-cols-2`; `:124` `grid-cols-3` → `grid-cols-1 sm:grid-cols-3`.
- `TrackRecordView.tsx:37` `grid-cols-2` stays (short label/value pairs); `:79,:97` already `grid-cols-1 xl:grid-cols-3` (ok). `SignalStatsView.tsx`: wrap its table in `overflow-x-auto` with `min-w-[560px]` on the table (dense statistics table, acceptable to scroll inside its card).
- `SignUpForm.tsx:63` `grid-cols-2` → `grid-cols-1 sm:grid-cols-2`.
- `PremiumPage.tsx`, settings cards, legal pages: replace any fixed multi-column grid or fixed width found by `grep -n "grid-cols-[2-9]\|w-\[[0-9]" ` in those folders with a `grid-cols-1 sm:grid-cols-…` / `w-full sm:w-…` variant; long legal text gets `break-words`.
- `AssistantPage.tsx:57` delete button: `opacity-100 md:opacity-0 md:group-hover:opacity-100` (visible on touch screens).

- [ ] **Step 4: Run** the portfolio test, the whole vitest suite and `tsc`. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: home, portfolio, forecasts and account pages on phones`

---

### Task 6: Assistant on phones

**Files:**
- Modify: `frontend/src/features/assistant/AssistantPage.tsx`, `frontend/src/features/assistant/ChatView.tsx:45`, `frontend/src/features/assistant/Composer.tsx`, `frontend/src/features/assistant/AssistantPanel.tsx:26`
- Test: `frontend/src/features/assistant/AssistantPage.test.tsx`

**Interfaces:**
- Consumes: `useIsMobile()`, `setViewportWidth()` (Task 2); `Sheet` (shadcn).

- [ ] **Step 1: Failing test** — append to `AssistantPage.test.tsx` (reuse its mocks for a list with one conversation):

```tsx
test("sur téléphone, la conversation prend l'écran et la liste s'ouvre à la demande", async () => {
  setViewportWidth(390);
  try {
    …same arrange as the existing list test…
    expect(screen.queryByRole("button", { name: "+ Nouvelle conversation" })).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Conversations" }));
    expect(await screen.findByRole("button", { name: "+ Nouvelle conversation" })).toBeVisible();
  } finally {
    setViewportWidth(1200);
  }
});
```

(Write the arrange part concretely from the existing test in the file.)

- [ ] **Step 2: Run** it. Expected: FAIL.

- [ ] **Step 3: Implement**

- `AssistantPage.tsx`: extract the conversation list (button + `<ul>`) into a local `ConversationList` component; desktop keeps `grid grid-cols-[280px_1fr]`; phones (`useIsMobile()`) render a header row with a button « Conversations » opening a left `Sheet` containing `ConversationList` (closing it on selection), and the chat card full width without card padding (`p-0 md:p-5`, `border-0 md:border`).
- `ChatView.tsx:45` height `h-[calc(100vh-13rem)]` → `h-[calc(100dvh-11rem)] md:h-[calc(100vh-13rem)]` (`dvh` follows the iOS keyboard).
- `Composer.tsx`: container `sticky bottom-0 bg-background pb-[env(safe-area-inset-bottom)]`; send button `min-h-11 min-w-11`.
- `AssistantPanel.tsx:26` sheet `w-[520px] sm:max-w-[520px]` → `w-full sm:w-[520px] sm:max-w-[520px]`.

- [ ] **Step 4: Run** the assistant tests, whole vitest suite and `tsc`. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: assistant on phones — full-screen chat, conversations drawer`

---

### Task 7: Mobile e2e checks, docs

**Files:**
- Create: `frontend/e2e/mobile.spec.ts`
- Modify: `frontend/e2e/layout.spec.ts` (replace the 390 px account-screens test by the new spec), `CLAUDE.md` (« Mise en page »), guide page `frontend/public/guide/premiers-pas.md` (one sentence: the app works on phones, menu ☰), admin doc `frontend/public/documentation/architecture.md` (layout breakpoints line, if it describes the layout)

- [ ] **Step 1: Write the e2e spec**

```ts
import { expect, test, type Page } from "@playwright/test";

// Téléphones : 390 px (iPhone récent) et 360 px (Android courant). Hauteur réduite = clavier ouvert.
const PHONES = [{ width: 390, height: 844 }, { width: 360, height: 780 }];

async function problems(page: Page) {
  return page.evaluate(() => {
    const found: string[] = [];
    if (document.documentElement.scrollWidth > window.innerWidth) {
      found.push(`page plus large que l'écran (${document.documentElement.scrollWidth} > ${window.innerWidth})`);
    }
    document.querySelectorAll<HTMLElement>("[data-slot=card], li, [role=toolbar]").forEach((el) => {
      const box = el.getBoundingClientRect();
      if (box.width > 0 && box.right > window.innerWidth + 1) found.push(`« ${el.textContent?.slice(0, 30)} » coupé à droite`);
    });
    document.querySelectorAll<HTMLElement>("a, button").forEach((el) => {
      const box = el.getBoundingClientRect();
      if (box.width > 0 && box.height > 0 && box.height < 32 && el.closest("main, header, [role=toolbar]")) {
        found.push(`zone tactile trop petite : « ${(el.getAttribute("aria-label") ?? el.textContent ?? "").slice(0, 30)} » (${Math.round(box.height)} px)`);
      }
    });
    return found;
  });
}

for (const phone of PHONES) {
  test(`toutes les pages hors Admin à ${phone.width} px`, async ({ page }) => {
    await page.setViewportSize(phone);
    await page.goto("/explorer");
    await page.locator("main a[href^='/titres/']").first().click();
    await expect(page.getByText("Score mixte")).toBeVisible();
    const security = new URL(page.url()).pathname;
    for (const path of ["/", "/explorer", "/explorer?region=us", "/etf", "/previsions", "/previsions?vue=statistiques",
                        "/previsions?vue=bulletin", "/portefeuille", "/assistant", "/reglages", "/premium", "/cgu",
                        "/mentions-legales", "/connexion", "/inscription", security]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(await page.getByRole("heading", { level: 1 }).count(), `${path} : un seul h1`).toBe(1);
      expect(await problems(page), `${path} à ${phone.width} px`).toEqual([]);
    }
  });
}

test("menu mobile : ouvrir, naviguer, refermé", async ({ page }) => {
  await page.setViewportSize(PHONES[0]);
  await page.goto("/");
  await page.getByRole("button", { name: "Ouvrir le menu" }).click();
  await page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "ETF" }).click();
  await expect(page).toHaveURL(/\/etf$/);
  await expect(page.getByRole("navigation", { name: "Navigation principale" })).toBeHidden();
});

test("clavier ouvert : la saisie de l'assistant reste visible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 664 });
  await page.goto("/assistant");
  const box = page.getByRole("textbox").last();
  await box.focus();
  await expect(box).toBeInViewport();
});
```

(The e2e user is signed in through the existing global setup, as in the other specs; check `playwright.config.ts` `storageState`.)

- [ ] **Step 2: Run** the e2e stack and `npm run e2e`. Fix any reported page in its owning file (layout class, card truncation, touch target), re-run until green. Each fix: commit with a `fix:` message naming the page. Expected end: all specs pass, including `layout.spec.ts` (1100–1440 px) and `table.spec.ts`.

- [ ] **Step 3: Docs**
- `CLAUDE.md` « Mise en page » bullet: « thème clair ; utilisable dès 360 px (téléphone : barre du haut et menu en tiroir sous 1024 px, une colonne sous 768 px, listes en cartes, fenêtres plein écran), deux colonnes à partir de `xl` (1280 px). L'onglet Admin reste pensé pour ordinateur. `useIsMobile()` (`lib/useIsMobile.ts`) quand le balisage doit changer ; sinon classes Tailwind `md:`/`lg:`. Vérifier qu'aucune carte n'est coupée (`layout.spec.ts`, `mobile.spec.ts`). »
- Guide `premiers-pas.md`: « Cotalyx fonctionne aussi sur téléphone : le menu s'ouvre avec le bouton ☰ en haut à gauche. »

- [ ] **Step 4: Full checks** — `npx tsc -b`, `npx vitest run`, `npx oxlint`, e2e. Restore the normal stack. Expected: PASS.

- [ ] **Step 5: Commit** — `test: mobile e2e checks; docs: mobile layout`
