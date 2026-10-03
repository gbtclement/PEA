import { screen, waitFor } from "@testing-library/react";
import { ME, PREMIUM_ME, mockFetch, renderWithProviders } from "@/test/utils";
import { PremiumThanksPage } from "./PremiumThanksPage";

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

test("synchronise la session puis souhaite la bienvenue", async () => {
  let premium = false;
  const fetchMock = mockFetch((url) => {
    if (url === "/api/billing/sync") { premium = true; return { body: { source: "subscription" } }; }
    return { body: premium ? PREMIUM_ME : ME };
  });
  renderWithProviders(<PremiumThanksPage />, { route: "/premium/merci?session_id=cs_1" });
  expect(await screen.findByRole("heading", { name: "Bienvenue dans Premium" }, { timeout: 5000 })).toBeInTheDocument();
  const sync = fetchMock.mock.calls.find(([url]) => url === "/api/billing/sync");
  expect(JSON.parse(String(sync![1]!.body))).toEqual({ session_id: "cs_1" });
  expect(screen.getByRole("link", { name: "Ouvrir l'assistant IA" })).toHaveAttribute("href", "/assistant");
});

test("message rassurant si l'activation tarde", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockFetch(() => ({ body: ME }));
  renderWithProviders(<PremiumThanksPage />, { route: "/premium/merci" });
  expect(await screen.findByText("Paiement reçu, activation en cours…")).toBeInTheDocument();
  vi.advanceTimersByTime(31_000);
  await waitFor(() => expect(screen.getByText(/peut prendre quelques minutes/)).toBeInTheDocument());
});

test("si la vérification échoue, la page arrête d'interroger et explique", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetchMock = mockFetch((url) => (url === "/api/billing/sync"
    ? { status: 503, body: { detail: { code: "billing_unavailable", message: "Paiement indisponible" } } }
    : { body: ME }));
  renderWithProviders(<PremiumThanksPage />, { route: "/premium/merci?session_id=cs_1" });
  expect(await screen.findByText(/n'avons pas pu vérifier votre paiement/)).toBeInTheDocument();
  const meCalls = () => fetchMock.mock.calls.filter(([url]) => url === "/api/me").length;
  const before = meCalls();
  vi.advanceTimersByTime(20_000);
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(meCalls()).toBe(before);  // plus d'appel toutes les 2 s
  expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
});
