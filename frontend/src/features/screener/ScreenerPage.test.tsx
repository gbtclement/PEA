import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { mockFetch, renderWithProviders, setViewportWidth } from "@/test/utils";
import { ScreenerPage } from "./ScreenerPage";

afterEach(() => vi.unstubAllGlobals());

const row = (id: number, symbol: string, name: string, score: number | null, change: number) => ({
  id, yahoo_ticker: `${symbol}.PA`, symbol, name, kind: "stock", market: "Euronext Paris", country: "FR", sector: "Luxe",
  envelopes: ["pea"], price: 100 + id, currency: "EUR", change_pct: change, perf_1w: 1, perf_1m: 2, perf_1y: 3, score, pe: 15,
  dividend_yield: 0.02, liquid: true, available_ratio: 1, isin: null, is_favorite: false, sparkline: [1, 2],
});
const ROWS = [row(1, "MC", "LVMH", 80, 2.07), row(2, "AIR", "Airbus", 60, -1.2), row(3, "BN", "Danone", null, 0.5)];

const FACETS = { sectors: ["Luxe"], countries: ["FR"], markets: ["Euronext Paris"] };

/** Faux serveur : filtre, trie et découpe en pages comme /api/screener. */
function api(rows: ReturnType<typeof row>[] = ROWS) {
  return mockFetch((url) => {
    if (url.startsWith("/api/screener/facets")) return { body: FACETS };
    if (url.startsWith("/api/favorites")) return { status: 204, body: null };
    if (!url.startsWith("/api/screener")) return { body: {} };
    const p = new URL(url, "http://test").searchParams;
    const q = (p.get("q") ?? "").toLowerCase();
    const minScore = p.get("min_score");
    const sort = (p.get("sort") ?? "name") as keyof ReturnType<typeof row>;
    const sign = p.get("order") === "desc" ? -1 : 1;
    const items = rows
      .filter((r) => !q || r.name.toLowerCase().includes(q))
      .filter((r) => minScore === null || (r.score !== null && r.score >= Number(minScore)))
      .sort((a, b) => {
        const va = a[sort], vb = b[sort];
        if (va === null) return 1;
        if (vb === null) return -1;
        return (typeof va === "string" ? va.localeCompare(String(vb)) : Number(va) - Number(vb)) * sign;
      });
    const offset = Number(p.get("offset") ?? 0), limit = Number(p.get("limit") ?? 50);
    return { body: { items: items.slice(offset, offset + limit), total: items.length } };
  });
}

function renderPage(route = "/explorer", rows: ReturnType<typeof row>[] = ROWS) {
  const fetchMock = api(rows);
  renderWithProviders(
    <Routes>
      <Route path="/explorer" element={<ScreenerPage kind="stock" title="Explorer" description="d" />} />
      <Route path="/titres/:id" element={<p>Fiche ouverte</p>} />
    </Routes>,
    { route },
  );
  return fetchMock;
}

const names = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[1].textContent);

test("liste triée par nom par défaut avec variations colorées", async () => {
  renderPage();
  await screen.findByText("LVMH");
  expect(names()[0]).toContain("Airbus");
  expect(screen.getByText(/\+2,07/)).toHaveClass("text-up");
  expect(screen.getByText("3 titres")).toBeInTheDocument();
});

test("tri par score décroissant en cliquant sur l'en-tête", async () => {
  renderPage();
  await screen.findByText("LVMH");
  await userEvent.click(screen.getByRole("button", { name: /Score/ }));
  await waitFor(() => expect(names()[0]).toContain("LVMH"));
});

test("filtres lus depuis l'URL", async () => {
  renderPage("/explorer?minScore=70");
  await screen.findByText("LVMH");
  expect(screen.queryByText("Airbus")).not.toBeInTheDocument();
  expect(screen.getByText("1 titre")).toBeInTheDocument();
});

test("recherche texte", async () => {
  renderPage();
  await screen.findByText("LVMH");
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher" }), "dan");
  await waitFor(() => expect(names()).toEqual([expect.stringContaining("Danone")]));
});

test("clic sur une ligne ouvre la fiche", async () => {
  renderPage();
  await userEvent.click(await screen.findByText("LVMH"));
  expect(await screen.findByText("Fiche ouverte")).toBeInTheDocument();
});

test("message si rien ne correspond", async () => {
  renderPage("/explorer?q=zzzz");
  expect(await screen.findByText(/Aucun titre ne correspond/)).toBeInTheDocument();
});

test("le favori change immédiatement sans recharger toute la liste", async () => {
  const fetchMock = api();
  renderWithProviders(
    <Routes><Route path="/explorer" element={<ScreenerPage kind="stock" title="Explorer" description="d" />} /></Routes>,
    { route: "/explorer" },
  );
  await screen.findByText("LVMH");
  const lvmhRow = screen.getAllByRole("row").find((r) => r.textContent?.includes("LVMH"))!;
  await userEvent.click(within(lvmhRow).getByRole("button", { name: "Ajouter aux favoris" }));
  expect(await within(lvmhRow).findByRole("button", { name: "Retirer des favoris" })).toBeInTheDocument();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/favorites/1", expect.objectContaining({ method: "PUT" })));
  expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith("/api/screener?"))).toHaveLength(1);
});

test("le filtre Enveloppe propose Toutes, PEA et PEA-PME, sans « à vérifier »", async () => {
  renderPage();
  const select = await screen.findByRole("combobox", { name: "Enveloppe" });
  expect([...select.querySelectorAll("option")].map((o) => o.textContent)).toEqual(["Enveloppe : toutes", "PEA", "PEA-PME"]);
});

test("région Europe par défaut, puis États-Unis", async () => {
  const fetch = api();
  renderWithProviders(
    <Routes><Route path="/explorer" element={<ScreenerPage kind="stock" title="Explorer" description="d" />} /></Routes>,
    { route: "/explorer" },
  );
  await screen.findByText("LVMH");
  expect(fetch.mock.calls.some(([u]) => String(u).startsWith("/api/screener?") && String(u).includes("region=europe"))).toBe(true);
  expect(screen.getByRole("button", { name: "Europe" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(screen.getByRole("button", { name: "États-Unis" }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => String(url).includes("region=us"))).toBe(true));
  expect(screen.getByRole("button", { name: "États-Unis" })).toHaveAttribute("aria-pressed", "true");
});

test("le cours affiche sa devise", async () => {
  api([ROWS[0], { ...row(4, "AAPL", "Apple", 70, 1), yahoo_ticker: "AAPL", price: 250, currency: "USD" }]);
  renderWithProviders(
    <Routes><Route path="/explorer" element={<ScreenerPage kind="stock" title="Explorer" description="d" />} /></Routes>,
    { route: "/explorer" },
  );
  expect(await screen.findByText("101,00 €")).toBeInTheDocument();
  expect(screen.getByText("250,00 USD")).toBeInTheDocument();
});

test("sur téléphone, une carte par titre et les filtres dans un panneau", async () => {
  setViewportWidth(390);
  try {
    renderPage();
    await screen.findByText("LVMH");
    expect(screen.queryByRole("columnheader")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Airbus|Danone|LVMH/ })).toHaveLength(3);
    await userEvent.click(screen.getByRole("button", { name: /Filtres/ }));
    expect(await screen.findByRole("combobox", { name: "Secteur" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Trier par" })).toBeInTheDocument();
  } finally {
    setViewportWidth(1200);
  }
});

const many = Array.from({ length: 60 }, (_, i) => row(100 + i, `T${i}`, `Titre ${String(i).padStart(2, "0")}`, 50, 0));

test("en descendant, la page suivante est chargée", async () => {
  const fetchMock = renderPage("/explorer", many);
  await screen.findByText("Titre 00");
  expect(screen.getByText("60 titres")).toBeInTheDocument();
  const scroller = screen.getByRole("table");
  scroller.scrollTop = 50 * 56;
  scroller.dispatchEvent(new Event("scroll"));
  await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes("offset=50"))).toBe(true));
});

test("changer un filtre repart de la première page", async () => {
  const fetchMock = renderPage("/explorer", many);
  await screen.findByText("Titre 00");
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher" }), "titre 5");
  await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => /q=titre(\+|%20)5/.test(String(u)) && String(u).includes("offset=0"))).toBe(true));
  await screen.findByText("Titre 59");
  expect(screen.queryByText("Titre 00")).not.toBeInTheDocument();
});
