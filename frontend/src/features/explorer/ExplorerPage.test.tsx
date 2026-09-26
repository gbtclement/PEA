import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { ExplorerPage } from "./ExplorerPage";

const ITEMS = [
  { id: 1, yahoo_ticker: "MC.PA", symbol: "MC", name: "LVMH", kind: "stock", market: "Euronext Paris", country: "FR",
    sector: null, eligibility: "eligible", price: 612.4, change_pct: 2.07, as_of: "2026-09-25T15:35:00Z" },
  { id: 2, yahoo_ticker: "GFC.PA", symbol: "GFC", name: "Gecina", kind: "stock", market: "Euronext Paris", country: "FR",
    sector: null, eligibility: "a_verifier", price: 90.1, change_pct: -1.2, as_of: "2026-09-25T15:35:00Z" },
];

afterEach(() => vi.unstubAllGlobals());

test("affiche les titres avec éligibilité et variation colorée", async () => {
  mockFetch(() => ({ body: { items: ITEMS, total: 2 } }));
  renderWithProviders(<ExplorerPage />);
  expect(await screen.findByText("LVMH")).toBeInTheDocument();
  expect(screen.getByText("Éligible PEA")).toBeInTheDocument();
  expect(screen.getByText("À vérifier")).toBeInTheDocument();
  expect(screen.getByText(/\+2,07/)).toHaveClass("text-up");
  expect(screen.getByText(/-1,20/)).toHaveClass("text-down");
});

test("la recherche interroge l'API avec le paramètre q", async () => {
  const fetchMock = mockFetch(() => ({ body: { items: ITEMS, total: 2 } }));
  renderWithProviders(<ExplorerPage />);
  await screen.findByText("LVMH");
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher" }), "lvmh");
  await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(expect.stringContaining("q=lvmh"), expect.anything()));
});

test("message si aucun résultat", async () => {
  mockFetch(() => ({ body: { items: [], total: 0 } }));
  renderWithProviders(<ExplorerPage />);
  expect(await screen.findByText(/Aucun titre ne correspond/)).toBeInTheDocument();
});

test("message d'erreur si l'API échoue", async () => {
  mockFetch(() => ({ status: 500, body: { detail: "boom" } }));
  renderWithProviders(<ExplorerPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger les titres");
});

test("pagination", async () => {
  const fetchMock = mockFetch(() => ({ body: { items: ITEMS, total: 120 } }));
  renderWithProviders(<ExplorerPage />);
  expect(await screen.findByText("1–50 sur 120")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Suivant" }));
  await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(expect.stringContaining("offset=50"), expect.anything()));
});
