import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { PriceChartPanel } from "./PriceChartPanel";

const { chart } = vi.hoisted(() => {
  const series = () => ({ setData: vi.fn(), priceScale: () => ({ applyOptions: vi.fn() }) });
  return {
    chart: {
      addSeries: vi.fn(() => series()),
      panes: vi.fn(() => [{ setHeight: vi.fn() }, { setHeight: vi.fn() }, { setHeight: vi.fn() }]),
      timeScale: () => ({ fitContent: vi.fn() }),
      remove: vi.fn(),
    },
  };
});
vi.mock("lightweight-charts", () => ({
  createChart: vi.fn(() => chart),
  CandlestickSeries: "Candlestick", HistogramSeries: "Histogram", LineSeries: "Line",
}));
afterEach(() => { vi.unstubAllGlobals(); chart.addSeries.mockClear(); });

const DAILY = {
  period: "6M", intraday: false,
  bars: [{ time: "2026-09-24", open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }, { time: "2026-09-25", open: 1.5, high: 2, low: 1, close: 1.8, volume: 12 }],
  sma50: [{ time: "2026-09-25", value: 1.2 }], sma200: [], rsi: [{ time: "2026-09-25", value: 55 }],
  macd: [{ time: "2026-09-25", macd: 0.1, signal: 0.05, histogram: 0.05 }],
};

test("charge 6 mois par défaut puis change de période", async () => {
  const fetchMock = mockFetch(() => ({ body: DAILY }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("period=6M"), expect.anything()));
  await waitFor(() => expect(chart.addSeries).toHaveBeenCalledWith("Candlestick", expect.anything()));
  await userEvent.click(screen.getByRole("button", { name: "1A" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("period=1Y"), expect.anything()));
});

test("RSI ajouté dans un panneau séparé quand on coche la case", async () => {
  mockFetch(() => ({ body: DAILY }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  await waitFor(() => expect(chart.addSeries).toHaveBeenCalled());
  chart.addSeries.mockClear();
  await userEvent.click(screen.getByRole("checkbox", { name: "RSI" }));
  await waitFor(() => expect(chart.addSeries).toHaveBeenCalledWith("Line", expect.anything(), 1));
});

test("message quand il n'y a pas de données", async () => {
  mockFetch(() => ({ body: { ...DAILY, period: "1D", intraday: true, bars: [], sma50: [], rsi: [], macd: [] } }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  await userEvent.click(screen.getByRole("button", { name: "1J" }));
  expect(await screen.findByText(/Pas de données pour cette période/)).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "RSI" })).toBeDisabled();
});
