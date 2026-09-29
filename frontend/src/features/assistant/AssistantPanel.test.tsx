import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { AskAiButton } from "./AskAiButton";
import { AssistantPanelProvider } from "./AssistantPanel";

afterEach(() => vi.unstubAllGlobals());

test("le bouton ✨ ouvre le panneau avec le titre en contexte et les questions prêtes", async () => {
  mockFetch((url) => ({ body: url === "/api/assistant/status" ? { available: true, reason: null, spent_usd: 0.5, limit_usd: 5, model: "Claude Opus 5 (recommandé)" } : {} }));
  renderWithProviders(<AssistantPanelProvider><AskAiButton security={{ id: 1, name: "LVMH" }} label /></AssistantPanelProvider>);
  await userEvent.click(screen.getByRole("button", { name: "Demander à l'IA à propos de LVMH" }));
  expect(await screen.findByRole("dialog", { name: "Assistant IA — LVMH" })).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Analyse cette action" }, { timeout: 5000 })).toBeInTheDocument();
});

test("hors provider, le bouton ne plante pas", async () => {
  renderWithProviders(<AskAiButton security={{ id: 1, name: "LVMH" }} />);
  await userEvent.click(screen.getByRole("button", { name: "Demander à l'IA à propos de LVMH" }));
});

test("un visiteur qui clique sur ✨ passe par la connexion", async () => {
  mockFetch((url) => (url === "/api/me" ? { status: 401, body: { detail: { code: "not_authenticated", message: "…" } } } : { body: {} }));
  renderWithProviders(<AssistantPanelProvider><AskAiButton security={{ id: 1, name: "LVMH" }} label /></AssistantPanelProvider>);
  await new Promise((resolve) => setTimeout(resolve, 50));
  await userEvent.click(screen.getByRole("button", { name: "Demander à l'IA à propos de LVMH" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});
