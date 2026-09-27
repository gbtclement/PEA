import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { AssistantPage } from "./AssistantPage";

afterEach(() => vi.unstubAllGlobals());
const item = (id: number, title: string, cost: number) => ({ id, title, security_id: null, security_name: null, security_symbol: null,
  input_tokens: 0, output_tokens: 0, cost_usd: cost, created_at: "2026-09-26T10:00:00Z", updated_at: "2026-09-26T10:00:00Z" });

test("liste les conversations avec leur coût et ouvre celle choisie", async () => {
  mockFetch((url) => {
    if (url === "/api/assistant/settings") return { body: { configured: true, source: "settings", model: "claude-opus-5", models: [] } };
    if (url === "/api/assistant/conversations") return { body: [item(2, "Mon portefeuille", 0.0421), item(1, "À propos de LVMH", 0.003)] };
    if (url === "/api/assistant/conversations/2") {
      return { body: { ...item(2, "Mon portefeuille", 0.0421), messages: [{ id: 9, role: "user", content: "Analyse mon portefeuille", tools: [],
        interrupted: false, error: null, cost_usd: 0, created_at: "2026-09-26T10:00:00Z" }] } };
    }
    return { body: {} };
  });
  renderWithProviders(<AssistantPage />);
  expect(await screen.findByRole("heading", { level: 1, name: "Assistant IA" })).toBeInTheDocument();
  expect(await screen.findByText(/≈ 0,04 \$/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /^Mon portefeuille/ }));
  expect(await screen.findByText("Analyse mon portefeuille")).toBeInTheDocument();
});
