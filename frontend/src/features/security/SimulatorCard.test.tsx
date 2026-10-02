import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { SimulatorCard } from "./SimulatorCard";

afterEach(() => vi.unstubAllGlobals());

const NOTE = "Historique disponible depuis le 03/01/2000 : la simulation part de cette date.";
const SIMULATION = { start_date: "2000-01-03", start_price: 10, current_price: 40, shares: 50, invested: 500, buy_fee: 2.4,
                     sell_fee: 3.6, current_value: 2000, gain: 1494, gain_pct: 297.9, message: null, note: NOTE };

function setup() {
  return mockFetch((url) => url.startsWith("/api/fees") ? { body: { amount: 500, fee: 2.4, rate: 0.0048 } } : { body: SIMULATION });
}

const simulateUrls = (fetchMock: ReturnType<typeof mockFetch>) =>
  fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/simulate"));

test("autre durée : nombre et unité, puis note sur l'historique", async () => {
  const fetchMock = setup();
  renderWithProviders(<SimulatorCard securityId={1} />);
  await userEvent.selectOptions(screen.getByLabelText("Période"), "other");
  await userEvent.clear(screen.getByLabelText("Durée"));
  await userEvent.type(screen.getByLabelText("Durée"), "10");
  await userEvent.selectOptions(screen.getByLabelText("Unité"), "years");
  await userEvent.click(screen.getByRole("button", { name: "Simuler" }));
  expect(await screen.findByText(NOTE)).toBeInTheDocument();
  const [url] = simulateUrls(fetchMock);
  expect(url).toContain("duration=10");
  expect(url).toContain("unit=years");
  expect(url).not.toContain("period=");
});

test("durée invalide : aucune simulation", async () => {
  const fetchMock = setup();
  renderWithProviders(<SimulatorCard securityId={1} />);
  await userEvent.selectOptions(screen.getByLabelText("Période"), "other");
  await userEvent.clear(screen.getByLabelText("Durée"));
  await userEvent.type(screen.getByLabelText("Durée"), "0");
  await userEvent.click(screen.getByRole("button", { name: "Simuler" }));
  expect(simulateUrls(fetchMock)).toEqual([]);
});
