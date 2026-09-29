import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { AdminPage } from "./AdminPage";

vi.mock("./EligibilityOverridesCard", () => ({ EligibilityOverridesCard: () => null }));
afterEach(() => vi.unstubAllGlobals());

const ADMIN = { ...ME, role: "admin", has_premium: true };
const PAUL = { id: "u2", email: "paul@example.com", first_name: "Paul", last_name: "Martin", role: "user",
  is_premium: false, verified: true, has_password: true, has_google: false, created_at: "2026-09-01T08:00:00Z", last_login_at: null };
const LIST = { items: [PAUL], total: 1, page: 1, page_size: 50 };
const SETTINGS = { ai_model: "claude-opus-5", ai_monthly_cost_limit_usd: 5, models: [
  { id: "claude-opus-5", label: "Claude Opus 5 (recommandé)" }, { id: "claude-haiku-4-5", label: "Claude Haiku 4.5 (économique)" }] };
const STATUS = { claude: true, smtp: true, google: false, turnstile: false, app_secret: true, admin_email: true };

function api(overrides: Record<string, unknown> = {}) {
  return mockFetch((url) => {
    if (url in overrides) return { body: overrides[url] };
    if (url === "/api/me") return { body: ADMIN };
    if (url.startsWith("/api/admin/users?")) return { body: LIST };
    if (url === "/api/admin/settings") return { body: SETTINGS };
    if (url === "/api/admin/config-status") return { body: STATUS };
    return { body: {} };
  });
}

const bodyOf = (fetchMock: ReturnType<typeof mockFetch>, url: string, method: string) =>
  JSON.parse(String(fetchMock.mock.calls.find(([u, init]) => String(u) === url && init?.method === method)?.[1]?.body));

test("liste les inscrits, cherche et trie côté serveur", async () => {
  const fetchMock = api();
  renderWithProviders(<AdminPage />);
  expect(await screen.findByText("paul@example.com")).toBeInTheDocument();
  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher un utilisateur" }), "hélène");
  await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes("q=h%C3%A9l%C3%A8ne"))).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: /Mail/ }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => /sort=email&order=asc/.test(String(u)))).toBe(true));
});

test("bascule Premium dans le tableau", async () => {
  const fetchMock = api({ "/api/admin/users/u2": { ...PAUL, is_premium: true } });
  renderWithProviders(<AdminPage />);
  await userEvent.click(await screen.findByRole("switch", { name: "Premium pour Paul Martin" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/admin/users/u2", "PATCH")).toEqual({ is_premium: true }));
});

test("modifie un compte", async () => {
  const fetchMock = api({ "/api/admin/users/u2": PAUL });
  renderWithProviders(<AdminPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Modifier Paul Martin" }));
  const dialog = await screen.findByRole("dialog");
  const last = within(dialog).getByLabelText("Nom");
  await userEvent.clear(last);
  await userEvent.type(last, "Durand");
  await userEvent.selectOptions(within(dialog).getByLabelText("Rôle"), "admin");
  await userEvent.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/admin/users/u2", "PATCH"))
    .toEqual({ first_name: "Paul", last_name: "Durand", email: "paul@example.com", role: "admin", is_premium: false }));
});

test("supprime seulement après avoir retapé le mail", async () => {
  const fetchMock = api({ "/api/admin/users/u2": null });
  renderWithProviders(<AdminPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer Paul Martin" }));
  const dialog = await screen.findByRole("dialog");
  const confirm = within(dialog).getByRole("button", { name: "Supprimer définitivement" });
  expect(confirm).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText("Retapez l'adresse mail pour confirmer"), "paul@example.com");
  await userEvent.click(confirm);
  await waitFor(() => expect(bodyOf(fetchMock, "/api/admin/users/u2", "DELETE")).toEqual({ confirm_email: "paul@example.com" }));
});

test("règle l'assistant et affiche l'état de la configuration sans valeur", async () => {
  const fetchMock = api();
  renderWithProviders(<AdminPage />);
  await screen.findByRole("option", { name: "Claude Haiku 4.5 (économique)" });  // modèles chargés
  await userEvent.selectOptions(screen.getByLabelText("Modèle par défaut"), "claude-haiku-4-5");
  const limit = screen.getByLabelText("Limite mensuelle par utilisateur ($)");
  await userEvent.clear(limit);
  await userEvent.type(limit, "10");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer les réglages de l'assistant" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/admin/settings", "PUT"))
    .toEqual({ ai_model: "claude-haiku-4-5", ai_monthly_cost_limit_usd: 10 }));
  const status = screen.getByRole("list", { name: "État de la configuration" });
  expect(within(status).getByText("Claude").closest("li")).toHaveTextContent("Renseigné");
  expect(within(status).getByText("Google").closest("li")).toHaveTextContent("Manquant");
  await userEvent.click(screen.getByRole("button", { name: "Envoyer un mail de test" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/admin/test-email", expect.objectContaining({ method: "POST" })));
  expect(screen.getByRole("link", { name: "Documentation admin" })).toHaveAttribute("href", "/documentation/");
});
