import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, PREMIUM_ME, mockFetch, renderWithProviders } from "@/test/utils";
import { AccountMenu } from "./AccountMenu";

afterEach(() => vi.unstubAllGlobals());

test("compte connecté : nom, adresse et déconnexion", async () => {
  const fetchMock = mockFetch((url) => (url === "/api/me" ? { body: ME } : { status: 204, body: null }));
  renderWithProviders(<AccountMenu />);
  expect(await screen.findByText("Moi Dupont")).toBeInTheDocument();
  expect(screen.getByText("moi@example.com")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Se déconnecter" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", expect.objectContaining({ method: "POST" })));
});

test("visiteur : liens de connexion et d'inscription", async () => {
  mockFetch(() => ({ status: 401, body: { detail: { code: "not_authenticated", message: "…" } } }));
  renderWithProviders(<AccountMenu />);
  expect(await screen.findByRole("link", { name: "Se connecter" })).toHaveAttribute("href", "/connexion");
  expect(screen.getByRole("link", { name: "Créer un compte" })).toHaveAttribute("href", "/inscription");
});

test("membre gratuit : lien « Passer Premium » ; membre Premium : badge", async () => {
  mockFetch(() => ({ body: ME }));
  const { unmount } = renderWithProviders(<AccountMenu />);
  expect(await screen.findByRole("link", { name: "Passer Premium" })).toHaveAttribute("href", "/premium");
  unmount();
  vi.unstubAllGlobals();
  mockFetch(() => ({ body: PREMIUM_ME }));
  renderWithProviders(<AccountMenu />);
  expect(await screen.findByText("Premium")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Passer Premium" })).not.toBeInTheDocument();
});
