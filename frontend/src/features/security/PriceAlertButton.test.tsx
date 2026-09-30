import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { PriceAlertButton } from "./PriceAlertButton";

afterEach(() => vi.unstubAllGlobals());

const SECURITY = { id: 7, name: "Equinor", price: 301.5, currency: "NOK" };

test("crée une alerte au-dessus d'un prix, dans la devise du titre", async () => {
  const fetchMock = mockFetch((url) => (url === "/api/me" ? { body: ME } : { status: 201, body: { id: "a1" } }));
  renderWithProviders(<PriceAlertButton security={SECURITY} />);
  await userEvent.click(await screen.findByRole("button", { name: "Créer une alerte" }));
  const dialog = await screen.findByRole("dialog");
  const price = within(dialog).getByLabelText("Prix (NOK)");
  expect(price).toHaveValue("301,50");
  await userEvent.clear(price);
  await userEvent.type(price, "320");
  await userEvent.click(within(dialog).getByRole("button", { name: "Créer l'alerte" }));
  await waitFor(() => {
    const call = fetchMock.mock.calls.find(([u, init]) => String(u) === "/api/me/price-alerts" && init?.method === "POST");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ security_id: 7, direction: "above", price: 320 });
  });
});

test("seuil déjà franchi : le message de l'API s'affiche", async () => {
  mockFetch((url) => (url === "/api/me" ? { body: ME }
    : { status: 400, body: { detail: { code: "already_reached", message: "Le cours est déjà au-dessus de ce prix." } } }));
  renderWithProviders(<PriceAlertButton security={SECURITY} />);
  await userEvent.click(await screen.findByRole("button", { name: "Créer une alerte" }));
  await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Créer l'alerte" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("déjà au-dessus");
});

test("un visiteur est envoyé vers la connexion", async () => {
  mockFetch(() => ({ status: 401, body: { detail: { code: "not_authenticated", message: "" } } }));
  renderWithProviders(<PriceAlertButton security={SECURITY} />, { route: "/titres/7" });
  await userEvent.click(await screen.findByRole("button", { name: "Créer une alerte" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});
