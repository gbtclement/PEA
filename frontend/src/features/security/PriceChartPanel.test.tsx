import { fireEvent, screen, waitFor } from "@testing-library/react";
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

test("les heures intraday sont affichées à l'heure de Paris", async () => {
  const { createChart } = await import("lightweight-charts");
  mockFetch(() => ({ body: DAILY }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  await waitFor(() => expect(createChart).toHaveBeenCalled());
  const options = vi.mocked(createChart).mock.calls.at(-1)![1] as { localization: { timeFormatter: (t: number | string) => string } };
  expect(options.localization.timeFormatter(Date.UTC(2026, 8, 25, 7, 0) / 1000)).toContain("09:00");
});

const BOUNDED = { ...DAILY, interval: "day", first_date: "2000-01-03", last_date: "2026-09-25" };
const urls = (fetchMock: ReturnType<typeof mockFetch>) => fetchMock.mock.calls.map(([url]) => String(url));

test("périodes 10A et Max", async () => {
  const fetchMock = mockFetch(() => ({ body: BOUNDED }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  await waitFor(() => expect(chart.addSeries).toHaveBeenCalled());
  await userEvent.click(screen.getByRole("button", { name: "10A" }));
  await userEvent.click(screen.getByRole("button", { name: "Max" }));
  await waitFor(() => expect(urls(fetchMock).some((u) => u.includes("period=MAX"))).toBe(true));
  expect(urls(fetchMock).some((u) => u.includes("period=10Y"))).toBe(true);
});

test("période personnalisée bornée à l'historique", async () => {
  const fetchMock = mockFetch(() => ({ body: BOUNDED }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  await waitFor(() => expect(chart.addSeries).toHaveBeenCalled());
  await userEvent.click(screen.getByRole("button", { name: "Personnalisé" }));
  const start = screen.getByLabelText("Début");
  const end = screen.getByLabelText("Fin");
  expect(start).toHaveAttribute("min", "2000-01-03");
  expect(end).toHaveAttribute("max", "2026-09-25");
  fireEvent.change(start, { target: { value: "2020-01-01" } });
  fireEvent.change(end, { target: { value: "2019-01-01" } });
  expect(screen.getByText("La date de fin doit suivre la date de début.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Appliquer" })).toBeDisabled();
  fireEvent.change(end, { target: { value: "2021-06-30" } });
  await userEvent.click(screen.getByRole("button", { name: "Appliquer" }));
  await waitFor(() => expect(urls(fetchMock).some(
    (u) => u.includes("period=custom") && u.includes("start=2020-01-01") && u.includes("end=2021-06-30"))).toBe(true));
});

test("indique le regroupement des barres", async () => {
  mockFetch(() => ({ body: { ...BOUNDED, interval: "month" } }));
  renderWithProviders(<PriceChartPanel securityId={5} />);
  expect(await screen.findByText("Une barre par mois sur cette période.")).toBeInTheDocument();
});
