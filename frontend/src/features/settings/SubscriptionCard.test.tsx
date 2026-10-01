import { screen } from "@testing-library/react";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { SubscriptionCard } from "./SubscriptionCard";

afterEach(() => vi.unstubAllGlobals());

const base = { source: "subscription", status: "active", interval: "year", current_period_end: "2026-11-01T00:00:00Z",
               cancel_at_period_end: false, has_customer: true };

function show(body: object) {
  mockFetch(() => ({ body }));
  renderWithProviders(<SubscriptionCard />);
}

test("abonné : formule, renouvellement et gestion", async () => {
  show(base);
  expect(await screen.findByText(/Premium annuel/)).toBeInTheDocument();
  expect(screen.getByText(/Renouvellement le 01\/11\/2026/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Gérer mon abonnement" })).toBeInTheDocument();
});

test("résilié : date de fin", async () => {
  show({ ...base, cancel_at_period_end: true });
  expect(await screen.findByText(/Premium s'arrête le 01\/11\/2026/)).toBeInTheDocument();
});

test("paiement échoué : alerte carte", async () => {
  show({ ...base, status: "past_due" });
  expect(await screen.findByRole("alert")).toHaveTextContent("Mettez à jour votre carte");
});

test("Premium offert", async () => {
  show({ ...base, source: "offered", status: null, interval: null, current_period_end: null, has_customer: false });
  expect(await screen.findByText("Premium vous est offert.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Gérer mon abonnement" })).not.toBeInTheDocument();
});

test("gratuit, avec un ancien abonnement : lien Premium et factures", async () => {
  show({ ...base, source: "none", status: "canceled" });
  expect(await screen.findByText("Vous n'êtes pas abonné.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Découvrir Premium" })).toHaveAttribute("href", "/premium");
  expect(screen.getByRole("button", { name: "Gérer mon abonnement" })).toBeInTheDocument();
});
