import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { SettingsPage } from "./SettingsPage";

vi.mock("./ProfileCard", () => ({ ProfileCard: () => null }));
vi.mock("./PasswordCard", () => ({ PasswordCard: () => null }));
vi.mock("./EmailCard", () => ({ EmailCard: () => null }));
vi.mock("./DevicesCard", () => ({ DevicesCard: () => null }));
vi.mock("./NotificationsCard", () => ({ NotificationsCard: () => null }));
afterEach(() => vi.unstubAllGlobals());

const SETTINGS = { min_orders_per_year: 12, penalty_fee: 96, fee_grid: [{ up_to: null, rate: 0.0012 }] };

test("modifie les obligations et la grille de frais", async () => {
  const fetchMock = mockFetch((url) => {
    if (url === "/api/settings") return { body: { min_orders_per_year: 12, penalty_fee: 96, fee_grid: [{ up_to: 500, rate: 0.0048 }, { up_to: 1000, rate: 0.0018 }, { up_to: null, rate: 0.0012 }] } };
    return { body: { items: [], total: 0 } };
  });
  renderWithProviders(<SettingsPage />);
  const minOrders = await screen.findByLabelText("Ordres minimum par an");
  await userEvent.clear(minOrders);
  await userEvent.type(minOrders, "10");
  const rate = screen.getByLabelText("Taux de la tranche 1 (%)");
  expect(rate).toHaveValue("0,48");
  await userEvent.clear(rate);
  await userEvent.type(rate, "0,5");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer les frais" }));
  await waitFor(() => {
    const put = fetchMock.mock.calls.find(([url, init]) => url === "/api/settings" && init?.method === "PUT");
    expect(put).toBeDefined();
    expect(JSON.parse(put![1]!.body as string)).toEqual({ min_orders_per_year: 10, penalty_fee: 96,
      fee_grid: [{ up_to: 500, rate: 0.005 }, { up_to: 1000, rate: 0.0018 }, { up_to: null, rate: 0.0012 }] });
  });
});

test("les réglages ne montrent plus ni clé Claude ni corrections d'éligibilité, même à l'admin", async () => {
  mockFetch((url) => ({ body: url === "/api/me" ? { ...ME, role: "admin" } : SETTINGS }));
  renderWithProviders(<SettingsPage />);
  expect(await screen.findByRole("heading", { level: 1, name: "Réglages" })).toBeInTheDocument();
  expect(screen.queryByText(/clé API/i)).toBeNull();
  expect(screen.queryByText(/Éligibilité PEA/)).toBeNull();
});
