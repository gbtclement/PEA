import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { mockFetch } from "@/test/utils";
import { routes } from "./router";

vi.mock("@/components/charts/EChart", () => ({ EChart: () => null }));
afterEach(() => vi.unstubAllGlobals());

function body(url: string): unknown {
  if (url.includes("/api/status")) return { market_open: false, jobs: [], indices: [] };
  if (url.startsWith("/api/rankings/movers")) return { gainers: [], losers: [] };
  if (url.startsWith("/api/rankings/top") || url.startsWith("/api/market/heatmap") || url.startsWith("/api/screener")) return [];
  return { items: [], total: 0 };
}

test.each([
  ["/", "Accueil"],
  ["/explorer", "Explorer"],
  ["/portefeuille", "Portefeuille"],
  ["/assistant", "Assistant IA"],
])("la route %s affiche le titre %s", async (path, title) => {
  mockFetch((url) => ({ body: body(url) }));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { level: 1, name: title })).toBeInTheDocument();
});
