import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ME, mockFetch } from "@/test/utils";
import { routes } from "./router";

vi.mock("@/components/charts/EChart", () => ({ EChart: () => null }));
afterEach(() => vi.unstubAllGlobals());

function body(url: string): unknown {
  if (url === "/api/me") return ME;
  if (url.includes("/api/status")) return { market_open: false, jobs: [], indices: [] };
  if (url.startsWith("/api/rankings/movers")) return { gainers: [], losers: [] };
  if (url === "/api/assistant/settings") return { configured: false, source: null, model: "claude-opus-5", models: [] };
  if (url === "/api/assistant/conversations" || url === "/api/me/sessions") return [];
  if (url === "/api/forecasts") return { as_of: null, round_trip_cost: null, rows: [] };
  if (url === "/api/settings") return { min_orders_per_year: 12, penalty_fee: 96, fee_grid: [{ up_to: null, rate: 0.0012 }] };
  if (url.startsWith("/api/rankings/top") || url.startsWith("/api/market/heatmap") || url.startsWith("/api/screener")) return [];
  return { items: [], total: 0 };
}

test.each([
  ["/", "Accueil"],
  ["/explorer", "Explorer"],
  ["/previsions", "Prévisions court terme"],
  ["/portefeuille", "Portefeuille"],
  ["/assistant", "Assistant IA"],
])("la route %s affiche le titre %s", async (path, title) => {
  mockFetch((url) => ({ body: body(url) }));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { level: 1, name: title }, { timeout: 5000 })).toBeInTheDocument();
});

function renderRoute(path: string) {
  mockFetch((url) => ({ body: body(url) }));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
}

const robots = () => document.head.querySelector('meta[name="robots"]')?.getAttribute("content") ?? null;
const jsonLdTypes = () =>
  [...document.head.querySelectorAll('script[type="application/ld+json"]')].map((s) => JSON.parse(s.textContent!)["@type"]);

test.each([
  ["/portefeuille", "Portefeuille"],
  ["/assistant", "Assistant IA"],
  ["/reglages", "Réglages"],
])("la page personnelle %s n'est jamais indexée", async (path, title) => {
  renderRoute(path);
  await screen.findByRole("heading", { level: 1, name: title }, { timeout: 5000 });
  await waitFor(() => expect(robots()).toBe("noindex, nofollow"));
  expect(document.title).toBe(`${title} | PEA Radar`);
});

test("accueil : indexable, titre du site et WebApplication", async () => {
  renderRoute("/");
  await screen.findByRole("heading", { level: 1, name: "Accueil" }, { timeout: 5000 });
  await waitFor(() => expect(jsonLdTypes()).toEqual(["WebApplication"]));
  expect(robots()).toBeNull();
  expect(document.title).toBe("PEA Radar");
});

test.each([["/explorer", "Explorer"], ["/etf", "ETF"]])("%s : fil d'Ariane schema.org", async (path, title) => {
  renderRoute(path);
  await screen.findByRole("heading", { level: 1, name: title }, { timeout: 5000 });
  await waitFor(() => expect(jsonLdTypes()).toEqual(["BreadcrumbList"]));
  expect(document.title).toBe(`${title} | PEA Radar`);
  expect(document.head.querySelector('meta[name="description"]')?.getAttribute("content")).toMatch(/PEA/);
});

test("pied de page avec l'avertissement et titres de cartes en h2", async () => {
  renderRoute("/reglages");
  await screen.findByRole("heading", { level: 1, name: "Réglages" }, { timeout: 5000 });
  expect(screen.getByRole("contentinfo")).toHaveTextContent(/pas un conseil en investissement/);
  expect(screen.getByRole("heading", { level: 2, name: "Frais et obligations de la caisse régionale" })).toBeInTheDocument();
});

test("adresse inconnue : page introuvable dans la mise en page, jamais indexée", async () => {
  renderRoute("/page-qui-n-existe-pas");
  expect(await screen.findByRole("heading", { level: 1, name: "Page introuvable" }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Navigation principale" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Retour à l'accueil" })).toHaveAttribute("href", "/");
  await waitFor(() => expect(robots()).toBe("noindex, nofollow"));
  expect(document.title).toBe("Page introuvable | PEA Radar");
});

const ANONYMOUS = { status: 401, body: { detail: { code: "not_authenticated", message: "…" } } };

test("un visiteur qui ouvre le portefeuille arrive sur la connexion", async () => {
  mockFetch((url) => (url === "/api/me" ? ANONYMOUS : { body: body(url) }));
  const router = createMemoryRouter(routes, { initialEntries: ["/portefeuille"] });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { level: 1, name: "Se connecter" }, { timeout: 5000 })).toBeInTheDocument();
  expect(router.state.location.search).toBe("?suite=%2Fportefeuille");
});

test("un visiteur voit l'explorateur et le bandeau d'inscription", async () => {
  mockFetch((url) => (url === "/api/me" ? ANONYMOUS : { body: body(url) }));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/explorer"] })} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { level: 1, name: "Explorer" }, { timeout: 5000 })).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: "Créer un compte gratuit" })).toHaveAttribute("href", "/inscription");
});

test.each([["/connexion", "Se connecter"], ["/inscription", "Créer un compte"]])("%s est indexable", async (path, title) => {
  renderRoute(path);
  await screen.findByRole("heading", { level: 1, name: title }, { timeout: 5000 });
  expect(robots()).toBeNull();
});

test("les pages légales sont publiques", async () => {
  mockFetch((url) => (url === "/api/me" ? ANONYMOUS : { body: body(url) }));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/confidentialite"] })} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { level: 1, name: "Politique de confidentialité" }, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Créer un compte gratuit" })).toBeNull();
});
