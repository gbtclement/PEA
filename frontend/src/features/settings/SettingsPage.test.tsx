import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { SettingsPage } from "./SettingsPage";

vi.mock("./AssistantSettingsCard", () => ({ AssistantSettingsCard: () => null }));
afterEach(() => vi.unstubAllGlobals());

const ADMIN = { ...ME, role: "admin" };
const SETTINGS = { min_orders_per_year: 12, penalty_fee: 96, fee_grid: [{ up_to: null, rate: 0.0012 }] };
const GECINA = { id: 4, yahoo_ticker: "GFC.PA", symbol: "GFC", name: "Gecina", kind: "stock", market: "Euronext Paris",
  country: "FR", sector: "Real Estate", eligibility: "a_verifier", eligibility_source: "auto", eligibility_override: null,
  price: 90, change_pct: 0, as_of: null };

test("recherche un titre et corrige son éligibilité", async () => {
  const fetchMock = mockFetch((url) => {
    if (url === "/api/me") return { body: ADMIN };
    if (url === "/api/settings") return { body: SETTINGS };
    if (url.includes("overridden=true")) return { body: { items: [], total: 0 } };
    if (url.includes("/eligibility")) return { body: { ...GECINA, eligibility: "eligible", eligibility_source: "override", eligibility_override: "eligible" } };
    return { body: { items: [GECINA], total: 1 } };
  });
  renderWithProviders(<SettingsPage />);
  expect(screen.getByRole("heading", { level: 1, name: "Réglages" })).toBeInTheDocument();
  await userEvent.type(await screen.findByRole("searchbox", { name: "Rechercher un titre" }), "gec");
  const select = await screen.findByRole("combobox", { name: "Éligibilité de Gecina" });
  await userEvent.selectOptions(select, "eligible");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/securities/4/eligibility",
    expect.objectContaining({ method: "PATCH", body: JSON.stringify({ override: "eligible" }) })));
});

test("liste les corrections existantes", async () => {
  mockFetch((url) => url === "/api/me" ? { body: ADMIN } : url === "/api/settings" ? { body: SETTINGS } : url.includes("overridden=true")
    ? { body: { items: [{ ...GECINA, eligibility: "eligible", eligibility_source: "override", eligibility_override: "eligible" }], total: 1 } }
    : { body: { items: [], total: 0 } });
  renderWithProviders(<SettingsPage />);
  expect(await screen.findByText("Gecina")).toBeInTheDocument();
});

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

test.each([["user", false], ["admin", true]])("carte des corrections d'éligibilité pour le rôle %s : %s", async (role, visible) => {
  mockFetch((url) => url === "/api/me" ? { body: { ...ME, role } } : url === "/api/settings" ? { body: SETTINGS } : { body: { items: [], total: 0 } });
  renderWithProviders(<SettingsPage />);
  await screen.findByRole("heading", { level: 2, name: "Frais et obligations de la caisse régionale" });
  await waitFor(() => expect(screen.queryByRole("heading", { level: 2, name: "Éligibilité PEA — corrections manuelles" }) !== null).toBe(visible));
});
