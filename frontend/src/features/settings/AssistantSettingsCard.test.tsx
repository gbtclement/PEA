import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { AssistantSettingsCard } from "./AssistantSettingsCard";

afterEach(() => vi.unstubAllGlobals());
const MODELS = [{ id: "claude-opus-5", label: "Claude Opus 5 (recommandé)" }, { id: "claude-sonnet-5", label: "Claude Sonnet 5 (plus rapide)" }];
const settings = (configured: boolean, source: string | null = configured ? "settings" : null) =>
  ({ configured, source, model: "claude-opus-5", models: MODELS });

test("enregistre la clé et le modèle sans jamais réafficher la clé", async () => {
  const fetchMock = mockFetch((url) => ({ body: url === "/api/assistant/settings" ? settings(false) : {} }));
  renderWithProviders(<AssistantSettingsCard />);
  expect(await screen.findByText("Non configurée")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Clé API Claude"), "sk-ant-test-1234567890abcdef");
  await userEvent.selectOptions(screen.getByLabelText("Modèle IA"), "claude-sonnet-5");
  fetchMock.mockImplementation(async () => new Response(JSON.stringify({ ...settings(true), model: "claude-sonnet-5" }), { status: 200 }));
  await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  await waitFor(() => expect(screen.getByText("Configurée")).toBeInTheDocument());
  const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")!;
  expect(JSON.parse(put[1]!.body as string)).toEqual({ api_key: "sk-ant-test-1234567890abcdef", model: "claude-sonnet-5" });
  expect(screen.getByLabelText("Clé API Claude")).toHaveValue("");
});

test("clé définie dans le fichier .env", async () => {
  mockFetch(() => ({ body: settings(true, "env") }));
  renderWithProviders(<AssistantSettingsCard />);
  expect(await screen.findByText("Définie dans le fichier .env")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Supprimer la clé" })).not.toBeInTheDocument();
});

test("supprimer la clé", async () => {
  const fetchMock = mockFetch(() => ({ body: settings(true) }));
  renderWithProviders(<AssistantSettingsCard />);
  await userEvent.click(await screen.findByRole("button", { name: "Supprimer la clé" }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(true));
  const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")!;
  expect(JSON.parse(put[1]!.body as string)).toEqual({ remove_key: true, model: "claude-opus-5" });
});
