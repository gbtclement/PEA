import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { PortfolioPage } from "./PortfolioPage";

vi.mock("@/components/charts/EChart", () => ({ EChart: () => <div data-testid="echart" /> }));
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

const COUNTER = { year: 2026, count: 5, min_orders: 12, remaining: 7, expected_by_now: 8.8, behind: true, penalty_fee: 96 };
const EMPTY = { total_value: 0, invested: 0, gain: 0, gain_pct: null, day_change: 0, day_change_pct: null, realized_gain: 0,
  positions: [], sectors: [], counter: { ...COUNTER, count: 0, remaining: 12 } };
const FULL = {
  total_value: 600, invested: 500, gain: 100, gain_pct: 20, day_change: 50, day_change_pct: 9.09, realized_gain: 50,
  positions: [{ security_id: 1, symbol: "MC", name: "LVMH", sector: "Luxe", kind: "stock", quantity: 10, avg_cost: 50, price: 60,
    change_pct: 9.09, value: 600, gain: 100, gain_pct: 20, weight: 1 }],
  sectors: [{ sector: "Luxe", value: 600, weight: 1 }], counter: COUNTER,
};
const ORDERS = [{ id: 3, security_id: 1, symbol: "MC", name: "LVMH", trade_date: "2026-03-02", side: "buy", quantity: 10,
  unit_price: 50, fee: 2.4, amount: 500, note: null }];

function api(portfolio: typeof FULL | typeof EMPTY, orders: unknown[], onDelete?: () => { status: number; body: unknown }) {
  return mockFetch((url) => {
    if (url === "/api/portfolio") return { body: portfolio };
    if (url === "/api/portfolio/history") return { body: [] };
    if (url === "/api/orders/counter") return { body: portfolio.counter };
    if (url === "/api/orders/3") return onDelete ? onDelete() : { status: 204, body: null };
    if (url === "/api/orders") return { body: orders };
    return { body: { amount: 0, fee: 0, rate: 0 } };
  });
}

test("affiche un état vide sans ordre", async () => {
  api(EMPTY, []);
  renderWithProviders(<PortfolioPage />);
  expect(screen.getByRole("heading", { level: 1, name: "Portefeuille" })).toBeInTheDocument();
  expect(await screen.findByText("Aucun ordre pour l'instant")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Ajouter mon premier ordre" }));
  expect(await screen.findByRole("dialog")).toHaveTextContent("Nouvel ordre");
});

test("affiche chiffres clés, compteur en retard, positions et historique", async () => {
  api(FULL, ORDERS);
  renderWithProviders(<PortfolioPage />);
  expect(await screen.findByText("Valeur totale")).toBeInTheDocument();
  expect(screen.getAllByText("600,00 €").length).toBeGreaterThan(0);
  expect(await screen.findByText("5/12 ordres en 2026")).toBeInTheDocument();
  expect(screen.getByText(/En retard sur le rythme/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "LVMH" })).toHaveAttribute("href", "/titres/1");
  expect(await screen.findByText("Achat")).toBeInTheDocument();
});

test("supprimer un ordre refusé affiche le message du serveur", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const fetchMock = api(FULL, ORDERS, () => ({ status: 422, body: { detail: "Vente impossible : vous ne détenez que 0 titre(s) LVMH." } }));
  renderWithProviders(<PortfolioPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer l'ordre du 02/03/2026" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/orders/3", expect.objectContaining({ method: "DELETE" })));
  expect(await screen.findByText(/vous ne détenez que 0/)).toBeInTheDocument();
});
