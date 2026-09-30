import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router";
import { mockFetch } from "@/test/utils";
import { AuthPage } from "./AuthPage";
import { ForgotPasswordPage } from "./ForgotPasswordPage";

type Options = { callback: (token: string) => void };

beforeEach(() => {
  (window as unknown as { turnstile: unknown }).turnstile = {
    render: (_el: HTMLElement, options: Options) => { options.callback("jeton-du-widget"); return "w1"; },
    remove: vi.fn(),
  };
});
afterEach(() => vi.unstubAllGlobals());

function renderPage(element: React.ReactElement, path: string) {
  const router = createMemoryRouter([{ path: path.split("?")[0], element }], { initialEntries: [path] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
}

test("le mot de passe oublié envoie le jeton du widget", async () => {
  const fetchMock = mockFetch((url) => ({ body: url === "/api/auth/config"
    ? { google: false, turnstile_site_key: "cle-publique" } : { message: "Si un compte utilise cette adresse, un lien vient d'y être envoyé." } }));
  renderPage(<ForgotPasswordPage />, "/mot-de-passe-oublie");
  await userEvent.type(await screen.findByLabelText("Adresse mail"), "jean@example.com");
  await waitFor(() => expect(screen.getByRole("button", { name: "Envoyer le lien" })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: "Envoyer le lien" }));
  const body = JSON.parse(fetchMock.mock.calls.find(([u]) => u === "/api/auth/forgot-password")![1]!.body as string);
  expect(body).toEqual({ email: "jean@example.com", captcha: "jeton-du-widget" });
});

test("la connexion ne montre le widget qu'après la demande du serveur", async () => {
  let attempts = 0;
  mockFetch((url) => {
    if (url === "/api/auth/config") return { body: { google: false, turnstile_site_key: "cle-publique" } };
    attempts++;
    return { status: 400, body: { detail: { code: "captcha_required", message: "Confirmez que vous n'êtes pas un robot, puis réessayez." } } };
  });
  renderPage(<AuthPage mode="connexion" />, "/connexion");
  expect(document.querySelector("[data-turnstile]")).toBeNull();
  await userEvent.type(await screen.findByLabelText("Adresse mail"), "jean@example.com");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "motdepasse-solide");
  await userEvent.click(screen.getByRole("button", { name: "Me connecter" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Confirmez que vous n'êtes pas un robot");
  expect(document.querySelector("[data-turnstile]")).not.toBeNull();
  expect(attempts).toBe(1);
});
