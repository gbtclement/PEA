import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { mockFetch } from "@/test/utils";
import { AuthPage } from "./AuthPage";
import { passwordStrength } from "./PasswordField";

afterEach(() => vi.unstubAllGlobals());

function renderAuth(path: string) {
  const router = createMemoryRouter([
    { path: "/inscription", element: <AuthPage mode="inscription" /> },
    { path: "/connexion", element: <AuthPage mode="connexion" /> },
    { path: "/verifier-email", element: <h1>Vérifier</h1> },
    { path: "/portefeuille", element: <h1>Portefeuille</h1> },
  ], { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("le panneau bascule entre inscription et connexion", async () => {
  mockFetch(() => ({ body: {} }));
  const router = renderAuth("/inscription?suite=%2Fportefeuille");
  expect(screen.getByRole("heading", { level: 1, name: "Créer un compte" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
  expect(await screen.findByRole("heading", { level: 1, name: "Se connecter" })).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/connexion");
  expect(router.state.location.search).toBe("?suite=%2Fportefeuille");
});

test("inscription : envoie le formulaire puis demande le code", async () => {
  const fetchMock = mockFetch(() => ({ status: 202, body: { message: "ok" } }));
  const router = renderAuth("/inscription");
  await userEvent.type(screen.getByLabelText("Prénom"), "Jean");
  await userEvent.type(screen.getByLabelText("Nom"), "Dupont");
  await userEvent.type(screen.getByLabelText("Adresse mail"), "jean@example.com");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "motdepasse-solide");
  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Créer mon compte" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/verifier-email"));
  expect(router.state.location.search).toBe("?adresse=jean%40example.com");
  expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toMatchObject({ email: "jean@example.com", accept_terms: true });
});

test("inscription : mot de passe trop court refusé sans appel", async () => {
  const fetchMock = mockFetch(() => ({ body: {} }));
  renderAuth("/inscription");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "court");
  await userEvent.click(screen.getByRole("button", { name: "Créer mon compte" }));
  expect(fetchMock).not.toHaveBeenCalled();
});

test("connexion : erreur affichée, puis retour à la page demandée", async () => {
  let attempt = 0;
  mockFetch(() => (attempt++ === 0
    ? { status: 401, body: { detail: { code: "invalid_credentials", message: "Adresse mail ou mot de passe incorrect." } } }
    : { body: { email: "jean@example.com" } }));
  const router = renderAuth("/connexion?suite=%2Fportefeuille");
  await userEvent.type(screen.getByLabelText("Adresse mail"), "jean@example.com");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "mauvais-mot-de-passe");
  await userEvent.click(screen.getByRole("button", { name: "Me connecter" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Adresse mail ou mot de passe incorrect.");
  await userEvent.click(screen.getByRole("button", { name: "Me connecter" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/portefeuille"));
});

test("jauge de solidité", () => {
  expect(passwordStrength("")).toBe(0);
  expect(passwordStrength("court")).toBe(0);
  expect(passwordStrength("douzelettres")).toBe(1);
  expect(passwordStrength("Douze-lettres-7")).toBe(2);
  expect(passwordStrength("une phrase de passe très longue")).toBe(3);
});
