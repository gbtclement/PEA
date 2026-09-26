import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { ScreenerPage } from "./ScreenerPage";

afterEach(() => vi.unstubAllGlobals());

const row = (id: number, symbol: string, name: string, score: number | null, change: number) => ({
  id, yahoo_ticker: `${symbol}.PA`, symbol, name, kind: "stock", market: "Euronext Paris", country: "FR", sector: "Luxe",
  eligibility: "eligible", price: 100 + id, change_pct: change, perf_1w: 1, perf_1m: 2, perf_1y: 3, score, pe: 15,
  dividend_yield: 0.02, liquid: true, available_ratio: 1, isin: null, is_favorite: false, sparkline: [1, 2],
});
const ROWS = [row(1, "MC", "LVMH", 80, 2.07), row(2, "AIR", "Airbus", 60, -1.2), row(3, "BN", "Danone", null, 0.5)];

function renderPage(route = "/explorer") {
  mockFetch(() => ({ body: ROWS }));
  return renderWithProviders(
    <Routes>
      <Route path="/explorer" element={<ScreenerPage kind="stock" title="Explorer" description="d" />} />
      <Route path="/titres/:id" element={<p>Fiche ouverte</p>} />
    </Routes>,
    { route },
  );
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
  const fetchMock = mockFetch((url) => (url.startsWith("/api/favorites") ? { status: 204, body: null } : { body: ROWS }));
  renderWithProviders(
    <Routes><Route path="/explorer" element={<ScreenerPage kind="stock" title="Explorer" description="d" />} /></Routes>,
    { route: "/explorer" },
  );
  await screen.findByText("LVMH");
  const lvmhRow = screen.getAllByRole("row").find((r) => r.textContent?.includes("LVMH"))!;
  await userEvent.click(within(lvmhRow).getByRole("button", { name: "Ajouter aux favoris" }));
  expect(await within(lvmhRow).findByRole("button", { name: "Retirer des favoris" })).toBeInTheDocument();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/favorites/1", expect.objectContaining({ method: "PUT" })));
  expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith("/api/screener"))).toHaveLength(1);
});
