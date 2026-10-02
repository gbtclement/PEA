import { screen } from "@testing-library/react";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { MarketStatus } from "./MarketStatus";

afterEach(() => vi.unstubAllGlobals());

const job = (name: string, success: string | null, error: string | null = null) => ({
  job: name, last_success_at: success, last_error_at: error, last_error: error ? "KO" : null, last_count: 1,
});

const markets = (europe: boolean, us: boolean) => [
  { code: "europe", label: "Europe", open: europe }, { code: "us", label: "New York", open: us },
];

test("état de chaque place avec heure de mise à jour", async () => {
  mockFetch(() => ({ body: { market_open: true, markets: markets(true, false), jobs: [job("quotes_t1", "2026-09-28T08:02:00Z")], indices: [] } }));
  renderWithProviders(<MarketStatus />);
  expect(await screen.findByText("Europe : ouverte")).toBeInTheDocument();
  expect(screen.getByText("New York : fermée")).toBeInTheDocument();
  expect(screen.getByText(/Cours mis à jour/)).toBeInTheDocument();
});

test("le soir, seule New York est ouverte", async () => {
  mockFetch(() => ({ body: { market_open: false, markets: markets(false, true), jobs: [], indices: [] } }));
  renderWithProviders(<MarketStatus />);
  expect(await screen.findByText("Europe : fermée")).toBeInTheDocument();
  expect(screen.getByText("New York : ouverte")).toBeInTheDocument();
});

test("bandeau si la dernière récupération a échoué", async () => {
  mockFetch(() => ({ body: { market_open: true, markets: markets(true, false), jobs: [job("quotes_t1", "2026-09-28T08:00:00Z", "2026-09-28T08:10:00Z")], indices: [] } }));
  renderWithProviders(<MarketStatus />);
  expect(await screen.findByText(/Source de données indisponible/)).toBeInTheDocument();
});

test("API injoignable", async () => {
  mockFetch(() => ({ status: 502, body: {} }));
  renderWithProviders(<MarketStatus />);
  expect(await screen.findByText("API injoignable")).toBeInTheDocument();
});
