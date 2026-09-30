import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { UnsubscribePage } from "./UnsubscribePage";

afterEach(() => vi.unstubAllGlobals());

test("désinscription d'un seul mail", async () => {
  const fetchMock = mockFetch((url, init) => (init?.method === "POST"
    ? { body: { message: "Vous ne recevrez plus « Récap du soir »." } }
    : { body: url.startsWith("/api/unsubscribe") ? { kind: "daily_recap", label: "Récap du soir" } : null }));
  renderWithProviders(<UnsubscribePage />, { route: "/desinscription?jeton=t0k.en&type=daily_recap" });
  await userEvent.click(await screen.findByRole("button", { name: "Ne plus recevoir « Récap du soir »" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Vous ne recevrez plus « Récap du soir »");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/unsubscribe?jeton=t0k.en&type=daily_recap",
    expect.objectContaining({ method: "POST" })));
});

test("tout arrêter d'un coup", async () => {
  const fetchMock = mockFetch((_url, init) => (init?.method === "POST"
    ? { body: { message: "Vous ne recevrez plus aucune notification." } } : { body: { kind: "daily_recap", label: "Récap du soir" } }));
  renderWithProviders(<UnsubscribePage />, { route: "/desinscription?jeton=t0k.en&type=daily_recap" });
  await userEvent.click(await screen.findByRole("button", { name: "Ne plus recevoir aucune notification" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/unsubscribe?jeton=t0k.en",
    expect.objectContaining({ method: "POST" })));
});

test("lien invalide", async () => {
  mockFetch(() => ({ status: 404, body: { detail: { code: "bad_link", message: "Ce lien n'est pas valable." } } }));
  renderWithProviders(<UnsubscribePage />, { route: "/desinscription?jeton=faux" });
  expect(await screen.findByRole("alert")).toHaveTextContent("n'est pas valable");
});
