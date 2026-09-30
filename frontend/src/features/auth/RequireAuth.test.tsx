import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ME, mockFetch } from "@/test/utils";
import { RequireAuth } from "./RequireAuth";

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  const router = createMemoryRouter([
    { element: <RequireAuth />, children: [{ path: "/portefeuille", element: <h1>Portefeuille</h1> }] },
    { path: "/connexion", element: <h1>Connexion</h1> },
  ], { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("un visiteur est envoyé vers la connexion avec la page demandée", async () => {
  mockFetch(() => ({ status: 401, body: { detail: { code: "not_authenticated", message: "…" } } }));
  const router = renderAt("/portefeuille");
  expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
  expect(router.state.location.search).toBe("?suite=%2Fportefeuille");
});

test("un compte connecté voit la page", async () => {
  mockFetch(() => ({ body: ME }));
  renderAt("/portefeuille");
  expect(await screen.findByRole("heading", { name: "Portefeuille" })).toBeInTheDocument();
});
