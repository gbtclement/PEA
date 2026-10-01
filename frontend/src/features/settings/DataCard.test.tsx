import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { DataCard } from "./DataCard";

afterEach(() => vi.unstubAllGlobals());

const READY = { id: "e1", status: "ready", created_at: "2026-10-01T08:00:00Z", expires_at: "2026-10-08T08:00:00Z" };

test("demande un export, puis indique qu'il est en préparation", async () => {
  let latest: unknown = null;
  mockFetch((url, init) => {
    if (url === "/api/me") return { body: ME };
    if (url === "/api/me/export" && init?.method === "POST") { latest = { ...READY, status: "pending" }; return { status: 202, body: latest }; }
    if (url === "/api/me/export") return { body: latest };
    return { body: {} };
  });
  renderWithProviders(<DataCard />);
  await userEvent.click(await screen.findByRole("button", { name: "Exporter mes données" }));
  expect(await screen.findByText(/en préparation/)).toBeInTheDocument();
});

test("export prêt : lien de téléchargement", async () => {
  mockFetch((url) => ({ body: url === "/api/me/export" ? READY : ME }));
  renderWithProviders(<DataCard />);
  expect(await screen.findByRole("link", { name: /Télécharger/ })).toHaveAttribute("href", "/api/me/export/e1");
});

test("supprimer le compte : adresse retapée et mot de passe", async () => {
  const fetchMock = mockFetch((url) => ({ status: url === "/api/me" ? 200 : 204, body: url === "/api/me" ? ME : null }));
  renderWithProviders(<DataCard />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer mon compte" }));
  const dialog = await screen.findByRole("dialog");
  const confirm = within(dialog).getByRole("button", { name: "Supprimer définitivement" });
  expect(confirm).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText("Retapez votre adresse mail"), ME.email);
  await userEvent.type(within(dialog).getByLabelText("Mot de passe"), "motdepasse-solide");
  await userEvent.click(confirm);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/me", expect.objectContaining({ method: "DELETE" })));
});

test("compte Google sans mot de passe : propose de se reconnecter", async () => {
  mockFetch((url) => ({ body: url === "/api/me" ? { ...ME, has_password: false, has_google: true } : null }));
  renderWithProviders(<DataCard />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer mon compte" }));
  expect(await screen.findByRole("link", { name: "Se reconnecter avec Google" }))
    .toHaveAttribute("href", expect.stringContaining("/api/auth/google/start?suite=%2Freglages"));
});

test("export échoué : message et nouveau bouton", async () => {
  mockFetch((url) => ({ body: url === "/api/me/export" ? { ...READY, status: "failed", expires_at: null } : ME }));
  renderWithProviders(<DataCard />);
  expect(await screen.findByText(/L'export précédent a échoué/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Exporter mes données" })).toBeInTheDocument();
});
