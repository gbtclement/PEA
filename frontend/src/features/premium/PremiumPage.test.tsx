import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, PREMIUM_ME, mockFetch, renderWithProviders } from "@/test/utils";
import { PremiumPage } from "./PremiumPage";
import { redirectTo } from "./redirect";

vi.mock("./redirect", () => ({ redirectTo: vi.fn() }));
afterEach(() => { vi.unstubAllGlobals(); vi.mocked(redirectTo).mockReset(); });

const PLANS = { configured: true, yearly_saving_pct: 18,
                plans: [{ interval: "month", amount: 499, currency: "eur" }, { interval: "year", amount: 4900, currency: "eur" }] };

function renderPage(me: { status?: number; body: unknown }, plans: object = PLANS, checkout: { status?: number; body: unknown } = { body: { url: "https://checkout.stripe.test/cs_1" } }) {
  const fetchMock = mockFetch((url) => {
    if (url === "/api/me") return me;
    if (url === "/api/billing/plans") return { body: plans };
    if (url === "/api/billing/checkout") return checkout;
    return { body: { url: "https://billing.stripe.test/cus_1" } };
  });
  renderWithProviders(<PremiumPage />, { route: "/premium" });
  return fetchMock;
}

test("affiche les prix et l'économie de la formule annuelle", async () => {
  renderPage({ body: ME });
  expect(await screen.findByText("4,99 €")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Annuel/ }));
  expect(screen.getByText("49,00 €")).toBeInTheDocument();
  expect(screen.getByText(/18 %/)).toBeInTheDocument();
});

test("les deux cases sont obligatoires, puis Stripe s'ouvre", async () => {
  const fetchMock = renderPage({ body: ME });
  const subscribe = await screen.findByRole("button", { name: "S'abonner" });
  expect(subscribe).toBeDisabled();
  await userEvent.click(screen.getByRole("checkbox", { name: /CGV/ }));
  expect(subscribe).toBeDisabled();
  await userEvent.click(screen.getByRole("checkbox", { name: /droit de rétractation/ }));
  await userEvent.click(subscribe);
  await waitFor(() => expect(redirectTo).toHaveBeenCalledWith("https://checkout.stripe.test/cs_1"));
  const call = fetchMock.mock.calls.find(([url]) => url === "/api/billing/checkout");
  expect(JSON.parse(String(call![1]!.body))).toEqual({ interval: "month", accept_cgv: true, waive_withdrawal: true });
});

test("erreur de paiement affichée", async () => {
  renderPage({ body: ME }, PLANS, { status: 503, body: { detail: { code: "billing_unavailable", message: "Paiement indisponible, réessayez dans quelques minutes." } } });
  await userEvent.click(await screen.findByRole("checkbox", { name: /CGV/ }));
  await userEvent.click(screen.getByRole("checkbox", { name: /droit de rétractation/ }));
  await userEvent.click(screen.getByRole("button", { name: "S'abonner" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Paiement indisponible");
  expect(redirectTo).not.toHaveBeenCalled();
});

test("visiteur : créer un compte ou se connecter", async () => {
  renderPage({ status: 401, body: { detail: { code: "not_authenticated", message: "…" } } });
  expect(await screen.findByRole("link", { name: "Créer un compte" })).toHaveAttribute("href", "/inscription");
  expect(screen.getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", "/connexion?suite=%2Fpremium");
  expect(screen.queryByRole("button", { name: "S'abonner" })).not.toBeInTheDocument();
});

test("abonné : gérer son abonnement ; Premium offert : rien à acheter", async () => {
  renderPage({ body: PREMIUM_ME });
  expect(await screen.findByText("Vous êtes Premium.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Gérer mon abonnement" })).toBeInTheDocument();
});

test("Premium offert : pas de bouton d'achat", async () => {
  renderPage({ body: { ...ME, has_premium: true, premium_source: "offered" } });
  expect(await screen.findByText("Premium vous est offert.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "S'abonner" })).not.toBeInTheDocument();
});

test("Stripe pas configuré : l'abonnement arrive bientôt", async () => {
  renderPage({ body: ME }, { configured: false, plans: [], yearly_saving_pct: null });
  expect(await screen.findByText("L'abonnement arrive bientôt.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "S'abonner" })).not.toBeInTheDocument();
});
