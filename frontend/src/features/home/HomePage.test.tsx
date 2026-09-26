import { screen } from "@testing-library/react";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { HomePage } from "./HomePage";

vi.mock("@/components/charts/EChart", () => ({ EChart: () => <div data-testid="echart" /> }));
afterEach(() => vi.unstubAllGlobals());

const row = (id: number, symbol: string, name: string, change: number) => ({
  id, yahoo_ticker: `${symbol}.PA`, symbol, name, kind: "stock", market: "Euronext Paris", country: "FR", sector: "Luxe",
  eligibility: "eligible", price: 100, change_pct: change, perf_1w: 1, perf_1m: 2, perf_1y: 3, score: 80, pe: 15,
  dividend_yield: 0.02, liquid: true, is_favorite: false, sparkline: [1, 2, 3],
});

function api(top: unknown[]) {
  return mockFetch((url) => {
    if (url.startsWith("/api/rankings/top")) return { body: top };
    if (url.startsWith("/api/rankings/movers")) return { body: { gainers: [row(3, "AIR", "Airbus", 4.2)], losers: [row(4, "KER", "Kering", -3.1)] } };
    if (url.startsWith("/api/market/heatmap")) return { body: [] };
    if (url.startsWith("/api/orders/counter")) return { body: { year: 2026, count: 3, min_orders: 12, remaining: 9, expected_by_now: 8.8, behind: true, penalty_fee: 96 } };
    if (url.startsWith("/api/status")) return { body: { market_open: true, jobs: [], indices: [{ id: 9, yahoo_ticker: "^FCHI", name: "CAC 40", price: 7500, change_pct: 0.8, as_of: null }] } };
    return { body: { period: "1D", intraday: true, bars: [], sma50: [], sma200: [], rsi: [], macd: [] } };
  });
}

test("affiche le top 10 avec raisons, les indices et les mouvements", async () => {
  api([{ ...row(1, "MC", "LVMH", 2.1), technical: 80, fundamental: 70, reasons: ["✅ Tendance haussière", "✅ Dividende de 2 %", "⚠️ RSI"] }]);
  renderWithProviders(<HomePage />);
  expect(screen.getByRole("heading", { level: 1, name: "Accueil" })).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: /LVMH/ })).toHaveAttribute("href", "/titres/1");
  expect(screen.getByText("✅ Tendance haussière")).toBeInTheDocument();
  expect(await screen.findByText("CAC 40")).toBeInTheDocument();
  expect(await screen.findByText("Airbus")).toBeInTheDocument();
  expect(screen.getByText("Kering")).toBeInTheDocument();
  expect(await screen.findByText("3/12 ordres en 2026")).toBeInTheDocument();
});

test("test_home_empty_state : message d'attente sans classement", async () => {
  api([]);
  renderWithProviders(<HomePage />);
  expect(await screen.findByText(/Le classement sera disponible/)).toBeInTheDocument();
});
