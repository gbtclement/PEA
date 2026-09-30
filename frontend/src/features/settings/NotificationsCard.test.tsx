import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { NotificationsCard } from "./NotificationsCard";

afterEach(() => vi.unstubAllGlobals());

const PREFS = { price_move: true, price_alert: true, daily_recap: false, weekly_recap: false, order_reminder: true,
  score_change: false, move_threshold_pct: 5 };
const FIRED = { id: "a1", security_id: 7, symbol: "EQNR", name: "Equinor", currency: "NOK", direction: "above", price: 300,
  current_price: 301.5, active: false, triggered_at: "2026-10-01T08:00:00Z", created_at: "2026-09-30T08:00:00Z" };

function api(alerts: unknown[] = []) {
  return mockFetch((url, init) => {
    if (url === "/api/me/notifications") return { body: init?.method === "PUT" ? JSON.parse(String(init.body)) : PREFS };
    if (url === "/api/me/price-alerts") return { body: alerts };
    return { status: 204, body: null };
  });
}

const sent = (fetchMock: ReturnType<typeof mockFetch>, method: string, url: string) =>
  fetchMock.mock.calls.filter(([u, init]) => String(u) === url && init?.method === method);

test("un interrupteur par mail, enregistré aussitôt", async () => {
  const fetchMock = api();
  renderWithProviders(<NotificationsCard />);
  const recap = await screen.findByRole("switch", { name: /Récap du soir/ });
  expect(recap).not.toBeChecked();
  expect(screen.getByRole("switch", { name: /Forte variation/ })).toBeChecked();
  await userEvent.click(recap);
  await waitFor(() => expect(sent(fetchMock, "PUT", "/api/me/notifications")).toHaveLength(1));
  expect(JSON.parse(String(sent(fetchMock, "PUT", "/api/me/notifications")[0][1]!.body))).toEqual({ ...PREFS, daily_recap: true });
});

test("seuil de forte variation enregistré en quittant le champ", async () => {
  const fetchMock = api();
  renderWithProviders(<NotificationsCard />);
  const field = await screen.findByLabelText("Seuil de forte variation (%)");
  await userEvent.clear(field);
  await userEvent.type(field, "3,5");
  await userEvent.tab();
  await waitFor(() => expect(JSON.parse(String(sent(fetchMock, "PUT", "/api/me/notifications")[0][1]!.body)).move_threshold_pct).toBe(3.5));
});

test("alertes de prix : réarmer ou supprimer", async () => {
  const fetchMock = api([FIRED]);
  renderWithProviders(<NotificationsCard />);
  expect(await screen.findByText(/Au-dessus de 300,00 NOK/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Réarmer l'alerte sur Equinor" }));
  const price = screen.getByLabelText("Nouveau prix (NOK)");
  expect(price).toHaveValue("300,00");  // le cours est déjà au-dessus : on choisit un autre seuil
  await userEvent.clear(price);
  await userEvent.type(price, "320");
  await userEvent.click(screen.getByRole("button", { name: "Confirmer le réarmement" }));
  await waitFor(() => expect(sent(fetchMock, "PATCH", "/api/me/price-alerts/a1")).toHaveLength(1));
  expect(JSON.parse(String(sent(fetchMock, "PATCH", "/api/me/price-alerts/a1")[0][1]!.body)))
    .toEqual({ active: true, direction: "above", price: 320 });
  await userEvent.click(screen.getByRole("button", { name: "Supprimer l'alerte sur Equinor" }));
  await waitFor(() => expect(sent(fetchMock, "DELETE", "/api/me/price-alerts/a1")).toHaveLength(1));
});

test("sans alerte : explique comment en créer une", async () => {
  api();
  renderWithProviders(<NotificationsCard />);
  expect(await screen.findByText(/Créez-en une depuis la fiche d'un titre/)).toBeInTheDocument();
});
