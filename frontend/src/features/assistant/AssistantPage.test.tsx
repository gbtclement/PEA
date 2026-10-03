import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link } from "react-router";
import { mockFetch, renderWithProviders, setViewportWidth } from "@/test/utils";
import { AssistantPage } from "./AssistantPage";

afterEach(() => vi.unstubAllGlobals());
const item = (id: number, title: string, cost: number) => ({ id, title, security_id: null, security_name: null, security_symbol: null,
  input_tokens: 0, output_tokens: 0, cost_usd: cost, created_at: "2026-09-26T10:00:00Z", updated_at: "2026-09-26T10:00:00Z" });

test("liste les conversations avec leur coût et ouvre celle choisie", async () => {
  mockFetch((url) => {
    if (url === "/api/assistant/status") return { body: { available: true, reason: null, spent_usd: 0.5, limit_usd: 5, model: "Claude Opus 5 (recommandé)" } };
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

test("suit l'adresse : lien ou retour arrière vers une autre conversation", async () => {
  const detail = (id: number, content: string) => ({ ...item(id, `Conv ${id}`, 0), messages: [{ id: id * 10, role: "user", content, tools: [],
    interrupted: false, error: null, cost_usd: 0, created_at: "2026-09-26T10:00:00Z" }] });
  mockFetch((url) => {
    if (url === "/api/assistant/status") return { body: { available: true, reason: null, spent_usd: 0.5, limit_usd: 5, model: "Claude Opus 5 (recommandé)" } };
    if (url === "/api/assistant/conversations") return { body: [item(2, "Conv 2", 0), item(1, "Conv 1", 0)] };
    if (url === "/api/assistant/conversations/2") return { body: detail(2, "Question deux") };
    if (url === "/api/assistant/conversations/1") return { body: detail(1, "Question une") };
    return { body: {} };
  });
  renderWithProviders(<><AssistantPage /><Link to="/assistant?c=1">aller à 1</Link><Link to="/assistant">accueil assistant</Link></>,
    { route: "/assistant?c=2" });
  expect(await screen.findByText("Question deux")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "aller à 1" }));
  expect(await screen.findByText("Question une")).toBeInTheDocument();
  expect(screen.queryByText("Question deux")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "accueil assistant" }));
  expect(await screen.findByRole("button", { name: "Analyse mon portefeuille" })).toBeInTheDocument();
});

test("membre gratuit : ne demande ni la liste ni une conversation", async () => {
  const fetch = mockFetch((url) => {
    if (url === "/api/assistant/status") return { body: { available: false, reason: "premium", spent_usd: 0, limit_usd: 5, model: "Claude" } };
    return { status: 403, body: { detail: "premium_required" } };
  });
  renderWithProviders(<AssistantPage />, { route: "/assistant?c=3" });
  expect(await screen.findByText("Réservé aux membres Premium")).toBeInTheDocument();
  expect(fetch.mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/conversations"))).toEqual([]);
});

test("sur téléphone, la conversation prend l'écran et la liste s'ouvre à la demande", async () => {
  setViewportWidth(390);
  try {
    mockFetch((url) => {
      if (url === "/api/assistant/status") return { body: { available: true, reason: null, spent_usd: 0.5, limit_usd: 5, model: "Claude Opus 5 (recommandé)" } };
      if (url === "/api/assistant/conversations") return { body: [item(2, "Mon portefeuille", 0.0421)] };
      return { body: {} };
    });
    renderWithProviders(<AssistantPage />);
    expect(await screen.findByRole("heading", { level: 1, name: "Assistant IA" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+ Nouvelle conversation" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Conversations" }));
    expect(await screen.findByRole("button", { name: "+ Nouvelle conversation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Mon portefeuille/ })).toBeInTheDocument();
  } finally {
    setViewportWidth(1200);
  }
});

test("tourner le téléphone garde la conversation et la question en cours de saisie", async () => {
  const { act } = await import("@testing-library/react");
  mockFetch((url) => {
    if (url === "/api/assistant/status") return { body: { available: true, reason: null, spent_usd: 0.5, limit_usd: 5, model: "Claude Opus 5 (recommandé)" } };
    if (url === "/api/assistant/conversations") return { body: [] };
    return { body: {} };
  });
  renderWithProviders(<AssistantPage />);
  const box = await screen.findByRole("textbox", { name: "Votre question" });
  await userEvent.type(box, "Que penser de LVMH ?");
  try {
    act(() => setViewportWidth(390));
    expect(screen.getByRole("textbox", { name: "Votre question" })).toHaveValue("Que penser de LVMH ?");
  } finally {
    act(() => setViewportWidth(1200));
  }
});
