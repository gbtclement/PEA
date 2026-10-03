import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { ScreenerCard } from "./ScreenerCard";

const ROW = { id: 7, yahoo_ticker: "MAERSK-B.CO", symbol: "MAERSK B", name: "A.P. Møller - Mærsk B Société anonyme très longue",
  kind: "stock", market: "Nasdaq Copenhagen", country: "DK", sector: "Industrie", envelopes: ["pea"], price: 24240,
  currency: "DKK", change_pct: -1.23, perf_1w: 1, perf_1m: 2, perf_1y: 3, score: 71.4, pe: 12, dividend_yield: 0.02,
  liquid: true, available_ratio: 1, isin: "DK0010244508", is_favorite: false, sparkline: [1, 2] };

test("carte : nom tronqué, place, cours avec devise, variation, score et badge", () => {
  renderWithProviders(<ScreenerCard row={ROW as never} />);
  expect(screen.getByText(/Mærsk B Société anonyme/)).toHaveClass("truncate");
  expect(screen.getByText("MAERSK B · Nasdaq Copenhagen")).toBeInTheDocument();
  expect(screen.getByText(/24\s240,00 DKK/)).toBeInTheDocument();
  expect(screen.getByText(/-1,23/)).toHaveClass("text-down");
  expect(screen.getByText("71")).toBeInTheDocument();
  expect(screen.getByText("Score")).toBeInTheDocument();  // lisible sans survol (pas seulement dans une infobulle)
  expect(screen.getByText("PEA")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Mærsk/ })).toHaveAttribute("href", "/titres/7");
});
