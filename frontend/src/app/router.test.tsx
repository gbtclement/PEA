import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { mockFetch } from "@/test/utils";
import { routes } from "./router";

afterEach(() => vi.unstubAllGlobals());

test.each([
  ["/", "Accueil"],
  ["/explorer", "Explorer"],
  ["/portefeuille", "Portefeuille"],
  ["/assistant", "Assistant IA"],
])("la route %s affiche le titre %s", async (path, title) => {
  mockFetch((url) => ({
    body: url.includes("/api/status") ? { market_open: false, jobs: [], indices: [] } : { items: [], total: 0 },
  }));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { level: 1, name: title })).toBeInTheDocument();
});
