import { screen } from "@testing-library/react";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { MarketStatus } from "./MarketStatus";

afterEach(() => vi.unstubAllGlobals());

const job = (name: string, success: string | null, error: string | null = null) => ({
  job: name, last_success_at: success, last_error_at: error, last_error: error ? "KO" : null, last_count: 1,
});

test("bourse ouverte avec heure de mise à jour", async () => {
  mockFetch(() => ({ body: { market_open: true, jobs: [job("quotes_t1", "2026-09-28T08:02:00Z")], indices: [] } }));
  renderWithProviders(<MarketStatus />);
  expect(await screen.findByText("Bourse ouverte")).toBeInTheDocument();
  expect(screen.getByText(/Cours mis à jour/)).toBeInTheDocument();
});

test("bourse fermée", async () => {
  mockFetch(() => ({ body: { market_open: false, jobs: [], indices: [] } }));
  renderWithProviders(<MarketStatus />);
  expect(await screen.findByText("Bourse fermée")).toBeInTheDocument();
});

test("bandeau si la dernière récupération a échoué", async () => {
  mockFetch(() => ({ body: { market_open: true, jobs: [job("quotes_t1", "2026-09-28T08:00:00Z", "2026-09-28T08:10:00Z")], indices: [] } }));
  renderWithProviders(<MarketStatus />);
  expect(await screen.findByText(/Source de données indisponible/)).toBeInTheDocument();
});

test("API injoignable", async () => {
  mockFetch(() => ({ status: 502, body: {} }));
  renderWithProviders(<MarketStatus />);
  expect(await screen.findByText("API injoignable")).toBeInTheDocument();
});
