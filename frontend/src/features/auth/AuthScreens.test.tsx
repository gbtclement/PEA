import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { LegalPage } from "@/features/legal/LegalPage";
import { ME, mockFetch } from "@/test/utils";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { NotMePage } from "./NotMePage";
import { ResetPasswordPage } from "./ResetPasswordPage";
import { VerifyEmailPage } from "./VerifyEmailPage";

afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  const router = createMemoryRouter([
    { path: "/", element: <h1>Accueil</h1> },
    { path: "/inscription", element: <h1>Inscription</h1> },
    { path: "/verifier-email", element: <VerifyEmailPage /> },
    { path: "/mot-de-passe-oublie", element: <ForgotPasswordPage /> },
    { path: "/reinitialiser", element: <ResetPasswordPage /> },
    { path: "/ce-n-etait-pas-moi", element: <NotMePage /> },
    { path: "/cgu", element: <LegalPage kind="cgu" /> },
  ], { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

test("code : validation puis accueil", async () => {
  const fetchMock = mockFetch(() => ({ body: ME }));
  const router = renderAt("/verifier-email?adresse=jean%40example.com");
  expect(screen.getByText("jean@example.com")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Code à 6 chiffres"), "123456");
  await userEvent.click(screen.getByRole("button", { name: "Valider" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toEqual({ email: "jean@example.com", code: "123456" });
});

test("code : renvoi bloqué pendant 60 secondes", () => {
  mockFetch(() => ({ body: {} }));
  renderAt("/verifier-email?adresse=jean%40example.com");
  expect(screen.getByRole("button", { name: /Renvoyer le code/ })).toBeDisabled();
});

test("code : sans adresse, retour à l'inscription", async () => {
  mockFetch(() => ({ body: {} }));
  const router = renderAt("/verifier-email");
  await waitFor(() => expect(router.state.location.pathname).toBe("/inscription"));
});

test("mot de passe oublié : même message dans tous les cas", async () => {
  mockFetch(() => ({ status: 202, body: { message: "Si un compte utilise cette adresse, un lien vient d'y être envoyé." } }));
  renderAt("/mot-de-passe-oublie");
  await userEvent.type(screen.getByLabelText("Adresse mail"), "jean@example.com");
  await userEvent.click(screen.getByRole("button", { name: "Envoyer le lien" }));
  expect(await screen.findByRole("status")).toHaveTextContent("un lien vient d'y être envoyé");
});

test("réinitialisation : confirmation différente refusée, lien périmé expliqué", async () => {
  const fetchMock = mockFetch(() => ({ status: 400, body: { detail: { code: "invalid_token", message: "Ce lien n'est plus valable : refaites une demande." } } }));
  renderAt("/reinitialiser?jeton=abc");
  await userEvent.type(screen.getByLabelText("Nouveau mot de passe"), "nouveau-mot-de-passe");
  await userEvent.type(screen.getByLabelText("Confirmer le mot de passe"), "autre-mot-de-passe!");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Les deux mots de passe sont différents.");
  expect(fetchMock).not.toHaveBeenCalled();
  await userEvent.clear(screen.getByLabelText("Confirmer le mot de passe"));
  await userEvent.type(screen.getByLabelText("Confirmer le mot de passe"), "nouveau-mot-de-passe");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  expect(await screen.findByRole("link", { name: "Refaire une demande" })).toBeInTheDocument();
});

test("ce n'était pas moi : rien ne se passe sans clic", async () => {
  const fetchMock = mockFetch(() => ({ body: { message: "Tous vos appareils ont été déconnectés." } }));
  renderAt("/ce-n-etait-pas-moi?jeton=abc");
  expect(fetchMock).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Sécuriser mon compte" }));
  expect(await screen.findByRole("status")).toHaveTextContent("déconnectés");
});

test("CGU provisoires avec l'avertissement", () => {
  renderAt("/cgu");
  expect(screen.getByRole("heading", { level: 1, name: "Conditions générales d'utilisation" })).toBeInTheDocument();
  expect(screen.getByText(/Version provisoire/)).toBeInTheDocument();
  expect(screen.getByText(/pas un conseil en investissement/)).toBeInTheDocument();
});
