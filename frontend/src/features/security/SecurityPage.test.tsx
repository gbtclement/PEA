import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { SecurityPage } from "./SecurityPage";

vi.mock("./PriceChartPanel", () => ({ PriceChartPanel: () => <div data-testid="chart" /> }));
afterEach(() => vi.unstubAllGlobals());

const DETAIL = {
  id: 1, yahoo_ticker: "MC.PA", symbol: "MC", name: "LVMH", kind: "stock", market: "Euronext Paris", country: "FR",
  sector: "Consumer Cyclical", industry: "Luxury Goods", isin: "FR0000121014", eligibility: "eligible",
  eligibility_source: "auto", price: 612.4, change_pct: 2.07, as_of: "2026-09-25T15:35:00Z", perf_1w: 1, perf_1m: 2,
  perf_1y: 3, score: 72, pe: 18, dividend_yield: 0.0328, liquid: true, is_favorite: false, sparkline: [],
  fundamentals: { pe: 18.07, eps: 33.9, earnings_growth: 0.008, revenue_growth: -0.029, debt_to_equity: 0.53,
                  profit_margin: 0.137, dividend_yield: 0.0328, market_cap: 195_600_000_000, currency: "EUR", updated_at: null },
  score_detail: { total: 72, technical: 80, fundamental: 64, available_ratio: 1, liquid: true, eligible_for_top: true,
                  history_days: 1250, computed_at: "2026-09-25T15:40:00Z",
                  components: [{ key: "trend", label: "Tendance", points: 20, max_points: 20, message: "✅ Tendance haussière", group: "technical" }] },
};

function renderPage(detailStatus = 200, detail: object = DETAIL) {
  const fetchMock = mockFetch((url) => {
    if (url.startsWith("/api/securities/1/news")) return { body: [{ title: "LVMH accélère", url: "https://ex.com/a", publisher: "Reuters", published_at: null }] };
    if (url.startsWith("/api/securities/1/simulate")) return { body: { start_date: "2026-08-25", start_price: 368, current_price: 400, shares: 2, invested: 736, buy_fee: 1.32, sell_fee: 1.44, current_value: 800, gain: 61.24, gain_pct: 8.3, message: null } };
    if (url.startsWith("/api/fees/estimate")) return { body: { amount: 500, fee: 2.4, rate: 0.0048 } };
    return { status: detailStatus, body: detail };
  });
  renderWithProviders(<Routes><Route path="/titres/:id" element={<SecurityPage />} /></Routes>, { route: "/titres/1" });
  return fetchMock;
}

test("en-tête, score détaillé, fondamentaux et actualités", async () => {
  renderPage();
  expect(await screen.findByRole("heading", { level: 1, name: "LVMH" })).toBeInTheDocument();
  expect(screen.getByText("Éligible PEA")).toBeInTheDocument();
  expect(screen.getByText("✅ Tendance haussière")).toBeInTheDocument();
  expect(screen.getByText(/195,6\sMd\s€/u)).toBeInTheDocument();
  expect(screen.getByText(/Luxury Goods/)).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: /LVMH accélère/ })).toHaveAttribute("href", "https://ex.com/a");
  expect(screen.getByTestId("chart")).toBeInTheDocument();
});

test("simulateur et aide sur les frais", async () => {
  const fetchMock = renderPage();
  await screen.findByRole("heading", { level: 1, name: "LVMH" });
  expect(await screen.findByText(/≈ 2,40 € de frais \(0,48 %\)/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Simuler" }));
  expect(await screen.findByText(/\+61,24 €/)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("amount=500"), expect.anything());
});

test("test_security_page_without_score : titre sans score ni fondamentaux", async () => {
  renderPage(200, { ...DETAIL, score: null, fundamentals: null, score_detail: null, price: null, change_pct: null });
  expect(await screen.findByText(/Score pas encore calculé/)).toBeInTheDocument();
  expect(screen.getByText(/Données fondamentales indisponibles/)).toBeInTheDocument();
});

test("titre introuvable", async () => {
  renderPage(404, { detail: "Titre introuvable" });
  expect(await screen.findByText("Titre introuvable.")).toBeInTheDocument();
});
