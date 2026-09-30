import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ME, mockFetch } from "@/test/utils";
import { FinishSignUpPage } from "./FinishSignUpPage";

afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  const router = createMemoryRouter([
    { path: "/finaliser-inscription", element: <FinishSignUpPage /> },
    { path: "/", element: <h1>Accueil</h1> },
    { path: "/portefeuille", element: <h1>Portefeuille</h1> },
    { path: "/inscription", element: <h1>Créer un compte</h1> },
  ], { initialEntries: ["/finaliser-inscription"] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("reprend le nom donné par Google et demande les CGU", async () => {
  const fetchMock = mockFetch((url) => ({ body: url === "/api/auth/google/pending"
    ? { email: "jean@gmail.com", first_name: "Jean", last_name: "Dupont" } : ME }));
  const router = renderPage();
  expect(await screen.findByDisplayValue("Jean")).toBeInTheDocument();
  expect(screen.getByText("jean@gmail.com")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Terminer mon inscription" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Acceptez les CGU");
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Terminer mon inscription" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  const body = JSON.parse(fetchMock.mock.calls.find(([u]) => u === "/api/auth/google/complete")![1]!.body as string);
  expect(body).toEqual({ first_name: "Jean", last_name: "Dupont", accept_terms: true });
});

test("sans connexion Google en cours, retour à l'inscription", async () => {
  mockFetch(() => ({ status: 404, body: { detail: { code: "google_expired", message: "Recommencez la connexion avec Google." } } }));
  const router = renderPage();
  await waitFor(() => expect(router.state.location.pathname).toBe("/inscription"));
});

test("après l'inscription Google, retour à la page demandée au départ", async () => {
  mockFetch((url) => ({ body: url === "/api/auth/google/pending"
    ? { email: "jean@gmail.com", first_name: "Jean", last_name: "Dupont", suite: "/portefeuille" } : ME }));
  const router = renderPage();
  await userEvent.click(await screen.findByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Terminer mon inscription" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/portefeuille"));
});
