import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { ME, PREMIUM_ME, mockFetch, renderWithProviders } from "@/test/utils";
import { SecurityPage } from "./SecurityPage";

vi.mock("./PriceChartPanel", () => ({ PriceChartPanel: () => <div data-testid="chart" /> }));
afterEach(() => vi.unstubAllGlobals());

const DETAIL = {
  id: 1, yahoo_ticker: "MC.PA", symbol: "MC", name: "LVMH", kind: "stock", market: "Euronext Paris", country: "FR",
  sector: "Consumer Cyclical", industry: "Luxury Goods", isin: "FR0000121014", eligibility: "eligible",
  eligibility_source: "auto", currency: "EUR", available_ratio: 1, price: 612.4, change_pct: 2.07, as_of: "2026-09-25T15:35:00Z", perf_1w: 1, perf_1m: 2,
  perf_1y: 3, score: 72, pe: 18, dividend_yield: 0.0328, liquid: true, is_favorite: false, sparkline: [],
  fundamentals: { pe: 18.07, eps: 33.9, earnings_growth: 0.008, revenue_growth: -0.029, debt_to_equity: 0.53,
                  profit_margin: 0.137, dividend_yield: 0.0328, market_cap: 195_600_000_000, currency: "EUR", updated_at: null },
  score_detail: { total: 72, technical: 80, fundamental: 64, available_ratio: 1, liquid: true, eligible_for_top: true,
                  history_days: 1250, computed_at: "2026-09-25T15:40:00Z",
                  components: [{ key: "trend", label: "Tendance", points: 20, max_points: 20, message: "✅ Tendance haussière", group: "technical" }] },
};

const FORECAST = {
  as_of: "2026-09-25",
  signals: [{ key: "high_52w", label: "Plus haut sur 1 an", bullish: true }],
  horizons: { "1d": { expected_return: 0.001, prob_up: 0.51, reliability: "faible", rank: 40 },
              "1w": { expected_return: 0.003, prob_up: 0.53, reliability: "elevee", rank: 12 }, "1m": null },
};

function renderPage(detailStatus = 200, detail: object = DETAIL, forecast: object = FORECAST, me: { status?: number; body: unknown } = { body: PREMIUM_ME }) {
  const fetchMock = mockFetch((url) => {
    if (url === "/api/me") return me;
    if (url.startsWith("/api/securities/1/forecast")) return { body: forecast };
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

test("affiche la devise de cotation", async () => {
  renderPage(200, { ...DETAIL, market: "Oslo Børs", currency: "NOK", price: 721.83 });
  expect(await screen.findByText(/721,83 NOK/)).toBeInTheDocument();
});

test("le bouton « + J'ai acheté » ouvre le formulaire d'ordre prérempli", async () => {
  renderPage();
  await screen.findByRole("heading", { level: 1, name: "LVMH" });
  await userEvent.click(screen.getByRole("button", { name: "+ J'ai acheté" }));
  const dialog = await screen.findByRole("dialog");
  expect(dialog).toHaveTextContent("Nouvel ordre");
  expect(screen.getByLabelText("Prix unitaire (€)")).toHaveValue("612,4");
});

const jsonLd = () => [...document.head.querySelectorAll('script[type="application/ld+json"]')].map((s) => JSON.parse(s.textContent!));

test("métadonnées : titre, Corporation avec ticker et fil d'Ariane", async () => {
  renderPage();
  await screen.findByRole("heading", { level: 1, name: "LVMH" });
  await waitFor(() => expect(document.title).toBe("LVMH (MC) — cours, score et analyse | Cotalyx"));
  expect(document.head.querySelector('meta[name="description"]')?.getAttribute("content")).toMatch(/LVMH/);
  const types = jsonLd().map((d) => d["@type"]);
  expect(types).toEqual(["Corporation", "BreadcrumbList"]);
  expect(jsonLd()[0]).toMatchObject({ tickerSymbol: "MC", identifier: "FR0000121014" });
  expect(document.head.querySelector('meta[name="robots"]')).toBeNull();
});

test("métadonnées : un ETF est un InvestmentFund", async () => {
  renderPage(200, { ...DETAIL, kind: "etf", name: "Amundi MSCI World", symbol: "CW8", score_detail: null });
  await screen.findByRole("heading", { level: 1, name: "Amundi MSCI World" });
  await waitFor(() => expect(jsonLd()[0]?.["@type"]).toBe("InvestmentFund"));
});

test("métadonnées : titre introuvable non indexé, sans données structurées", async () => {
  renderPage(404, { detail: "Titre introuvable" });
  await screen.findByText("Titre introuvable.");
  await waitFor(() => expect(document.head.querySelector('meta[name="robots"]')?.getAttribute("content")).toBe("noindex, nofollow"));
  expect(jsonLd()).toEqual([]);
});

test("carte des prévisions court terme : signaux actifs et horizons", async () => {
  renderPage();
  const card = (await screen.findByRole("heading", { level: 2, name: "Prévisions court terme" })).closest("[data-slot=card]") as HTMLElement;
  expect(await within(card).findByText(/Plus haut sur 1 an/)).toBeInTheDocument();
  expect(within(card).getByText("+0,30 %")).toBeInTheDocument();
  expect(within(card).getByText("53 % de hausse")).toBeInTheDocument();
  expect(within(card).getByText(/12e du jour/)).toBeInTheDocument();
  expect(within(card).getByRole("link", { name: /Voir toutes les prévisions/ })).toHaveAttribute("href", "/previsions");
});

test("carte des prévisions : aucun signal aujourd'hui", async () => {
  renderPage(200, DETAIL, { as_of: "2026-09-25", signals: [], horizons: { "1d": null, "1w": null, "1m": null } });
  expect(await screen.findByText("Aucun signal actif aujourd'hui.")).toBeInTheDocument();
});

test("carte des prévisions : avertissement", async () => {
  renderPage();
  expect(await screen.findByText(/Estimation statistique, pas une certitude ni un conseil/)).toBeInTheDocument();
});

test("carte des prévisions : un visiteur est invité à se connecter", async () => {
  const fetchMock = renderPage(200, DETAIL, FORECAST, { status: 401, body: { detail: { code: "not_authenticated", message: "…" } } });
  const link = await screen.findByRole("link", { name: "Connectez-vous" });
  expect(link).toHaveAttribute("href", "/connexion?suite=%2Ftitres%2F1");
  expect(screen.getByText(/réservées aux membres connectés/)).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/forecast"))).toBe(false);
});

test("favori : un visiteur est envoyé vers la connexion", async () => {
  const fetchMock = renderPage(200, DETAIL, FORECAST, { status: 401, body: { detail: { code: "not_authenticated", message: "…" } } });
  await screen.findByRole("link", { name: "Connectez-vous" });
  await userEvent.click(screen.getByRole("button", { name: "Ajouter aux favoris" }));
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/favorites"))).toBe(false);
});

test("« + J'ai acheté » : un visiteur passe par la connexion au lieu du formulaire", async () => {
  renderPage(200, DETAIL, FORECAST, { status: 401, body: { detail: { code: "not_authenticated", message: "…" } } });
  await screen.findByRole("link", { name: "Connectez-vous" });
  await userEvent.click(screen.getByRole("button", { name: "+ J'ai acheté" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("ForecastCard ne demande pas la prévision sans Premium", async () => {
  const fetchMock = renderPage(200, DETAIL, FORECAST, { body: ME });
  expect(await screen.findByText("Réservé aux membres Premium")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/forecast"))).toBe(false);
});
