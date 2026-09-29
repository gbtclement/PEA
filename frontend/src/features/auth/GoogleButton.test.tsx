import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { mockFetch } from "@/test/utils";
import { AuthPage } from "./AuthPage";

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string, google: boolean) {
  mockFetch((url) => ({ body: url === "/api/auth/config" ? { google, turnstile_site_key: null } : {} }));
  const router = createMemoryRouter([
    { path: "/connexion", element: <AuthPage mode="connexion" /> },
    { path: "/inscription", element: <AuthPage mode="inscription" /> },
  ], { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
}

test("le bouton Google garde la page où revenir", async () => {
  renderAt("/connexion?suite=%2Fportefeuille", true);
  const link = await screen.findByRole("link", { name: "Continuer avec Google" });
  expect(link).toHaveAttribute("href", "/api/auth/google/start?suite=%2Fportefeuille&remember=0");
  expect(screen.getByText("ou")).toBeInTheDocument();
});

test("sans Google configuré, pas de bouton", async () => {
  renderAt("/inscription", false);
  await screen.findByRole("heading", { level: 1, name: "Créer un compte" });
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(screen.queryByRole("link", { name: "Continuer avec Google" })).toBeNull();
});

test.each([
  ["google", "La connexion avec Google n'a pas abouti. Réessayez."],
  ["google_email", "Votre adresse Google n'est pas validée par Google : utilisez une autre méthode."],
])("erreur %s au retour de Google", async (code, message) => {
  renderAt(`/connexion?erreur=${code}`, true);
  expect(await screen.findByRole("alert")).toHaveTextContent(message);
});
