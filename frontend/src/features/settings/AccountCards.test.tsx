import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ME, mockFetch, renderWithProviders } from "@/test/utils";
import { DevicesCard } from "./DevicesCard";
import { EmailCard } from "./EmailCard";
import { PasswordCard } from "./PasswordCard";
import { ProfileCard } from "./ProfileCard";

afterEach(() => vi.unstubAllGlobals());

const bodyOf = (fetchMock: ReturnType<typeof mockFetch>, url: string) =>
  JSON.parse(String(fetchMock.mock.calls.find(([u, init]) => String(u) === url && init?.body)?.[1]?.body));

test("modifie le prénom et le nom", async () => {
  const fetchMock = mockFetch((_url, init) => ({ body: init?.method === "PATCH" ? { ...ME, first_name: "Jeanne" } : ME }));
  renderWithProviders(<ProfileCard />);
  const first = await screen.findByLabelText("Prénom");
  await userEvent.clear(first);
  await userEvent.type(first, "Jeanne");
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer le profil" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/me")).toEqual({ first_name: "Jeanne", last_name: "Dupont" }));
});

test("change le mot de passe en donnant l'actuel", async () => {
  const fetchMock = mockFetch((url) => ({ body: url === "/api/me" ? ME : { message: "Mot de passe enregistré." } }));
  renderWithProviders(<PasswordCard />);
  await userEvent.type(await screen.findByLabelText("Mot de passe actuel"), "ancien-mot-de-passe");
  await userEvent.type(screen.getByLabelText("Nouveau mot de passe"), "un-nouveau-mot-de-passe");
  await userEvent.click(screen.getByRole("button", { name: "Changer le mot de passe" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/me/password"))
    .toEqual({ current_password: "ancien-mot-de-passe", new_password: "un-nouveau-mot-de-passe" }));
  expect(await screen.findByText("Mot de passe enregistré.")).toBeInTheDocument();
});

test("compte Google sans mot de passe : « Ajouter un mot de passe »", async () => {
  mockFetch(() => ({ body: { ...ME, has_password: false, has_google: true } }));
  renderWithProviders(<PasswordCard />);
  expect(await screen.findByRole("button", { name: "Ajouter un mot de passe" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Mot de passe actuel")).toBeNull();
});

test("change l'adresse mail avec un code", async () => {
  const fetchMock = mockFetch((url) => ({
    body: url === "/api/me" ? ME : url === "/api/me/email" ? { message: "Code envoyé." } : { ...ME, email: "neuf@example.com" },
  }));
  renderWithProviders(<EmailCard />);
  await userEvent.type(await screen.findByLabelText("Nouvelle adresse"), "neuf@example.com");
  await userEvent.type(screen.getByLabelText("Mot de passe"), "motdepasse-solide");
  await userEvent.click(screen.getByRole("button", { name: "Recevoir un code" }));
  await userEvent.type(await screen.findByLabelText("Code reçu"), "123456");
  await userEvent.click(screen.getByRole("button", { name: "Valider la nouvelle adresse" }));
  await waitFor(() => expect(bodyOf(fetchMock, "/api/me/email/verify")).toEqual({ code: "123456" }));
  expect(await screen.findByText("Adresse modifiée : neuf@example.com")).toBeInTheDocument();
});

test("liste les appareils et en déconnecte un", async () => {
  const sessions = [
    { id: "s1", device: "Chrome sur Windows", ip: "203.0.113.0/24", created_at: "2026-09-01T08:00:00Z", last_seen_at: "2026-09-29T08:00:00Z", current: true },
    { id: "s2", device: "Safari sur iPhone", ip: "198.51.100.0/24", created_at: "2026-09-02T08:00:00Z", last_seen_at: "2026-09-28T08:00:00Z", current: false },
  ];
  const fetchMock = mockFetch((_url, init) => (init?.method === "DELETE" ? { status: 204, body: null } : { body: sessions }));
  renderWithProviders(<DevicesCard />);
  expect(await screen.findByText("Cet appareil")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Déconnecter Safari sur iPhone" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/me/sessions/s2", expect.objectContaining({ method: "DELETE" })));
  await userEvent.click(screen.getByRole("button", { name: "Déconnecter tous les autres" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/me/sessions", expect.objectContaining({ method: "DELETE" })));
});
