import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, sseResponse } from "@/test/utils";
import { ChatView } from "./ChatView";

afterEach(() => vi.unstubAllGlobals());
const AVAILABLE = { available: true, reason: null, spent_usd: 0.5, limit_usd: 5, model: "Claude Opus 5 (recommandé)" };
const conv = (messages: unknown[] = []) => ({ id: 5, title: "Nouvelle conversation", security_id: null, security_name: null, security_symbol: null,
  input_tokens: 0, output_tokens: 0, cost_usd: 0.0123, created_at: "2026-09-26T10:00:00Z", updated_at: "2026-09-26T10:00:00Z", messages });
const msg = (id: number, role: string, content: string, extra = {}) =>
  ({ id, role, content, tools: [], interrupted: false, error: null, cost_usd: 0, created_at: "2026-09-26T10:00:00Z", ...extra });

function stubFetch(handler: (url: string, init?: RequestInit) => Response | undefined) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => handler(String(input), init) ?? new Response("{}", { status: 404 }));
  vi.stubGlobal("fetch", fn);
  return fn;
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

test("crée la conversation, affiche la réponse en streaming puis la version enregistrée", async () => {
  let saved = false;
  const onCreated = vi.fn();
  stubFetch((url, init) => {
    if (url === "/api/assistant/status") return json(AVAILABLE);
    if (url === "/api/assistant/conversations" && init?.method === "POST") return json(conv(), 201);
    if (url === "/api/assistant/conversations/5/messages") {
      saved = true;
      return sseResponse([
        { type: "start", user_message: msg(1, "user", "Analyse LVMH") },
        { type: "tool", name: "get_security_overview", label: "Fiche du titre" },
        { type: "text", text: "**LVMH** est " }, { type: "text", text: "solide." },
        { type: "done", message: msg(2, "assistant", "**LVMH** est solide."), conversation: conv() },
      ]);
    }
    if (url === "/api/assistant/conversations/5") {
      return json(conv(saved ? [msg(1, "user", "Analyse LVMH"), msg(2, "assistant", "**LVMH** est solide.", { tools: ["get_security_overview"] })] : []));
    }
    return undefined;
  });
  renderWithProviders(<ChatView conversationId={null} onConversationCreated={onCreated} />);
  await userEvent.type(await screen.findByLabelText("Votre question"), "Analyse LVMH{Enter}");
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(5));
  expect(await screen.findByText("LVMH", { selector: "strong" })).toBeInTheDocument();
  expect(screen.getByText(/Fiche du titre/)).toBeInTheDocument();
  expect(screen.getByLabelText("Votre question")).toHaveValue("");
});

test("affiche l'erreur et la mention « réponse interrompue »", async () => {
  stubFetch((url) => {
    if (url === "/api/assistant/status") return json(AVAILABLE);
    if (url === "/api/assistant/conversations/5") {
      return json(conv([msg(1, "user", "Q"), msg(2, "assistant", "Début", { interrupted: true, error: "Le service Claude est momentanément indisponible." })]));
    }
    return undefined;
  });
  renderWithProviders(<ChatView conversationId={5} onConversationCreated={() => {}} />);
  expect(await screen.findByText("réponse interrompue")).toBeInTheDocument();
  expect(screen.getByText(/momentanément indisponible/)).toBeInTheDocument();
});

const renderChat = () => renderWithProviders(<ChatView conversationId={null} onConversationCreated={() => {}} />);

test("non Premium : carte « Réservé aux membres Premium »", async () => {
  stubFetch((url) => (url === "/api/assistant/status" ? json({ ...AVAILABLE, available: false, reason: "premium" }) : undefined));
  renderChat();
  expect(await screen.findByText("Réservé aux membres Premium")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Découvrir Premium" })).toHaveAttribute("href", "/premium");
  expect(screen.queryByRole("textbox")).toBeNull();
});

test("limite du mois atteinte", async () => {
  stubFetch((url) => (url === "/api/assistant/status" ? json({ ...AVAILABLE, available: false, reason: "limit_reached", spent_usd: 5 }) : undefined));
  renderChat();
  expect(await screen.findByText("Limite du mois atteinte")).toBeInTheDocument();
  expect(screen.getByText(/5,00 \$ sur 5,00 \$/)).toBeInTheDocument();
});

test("clé Claude absente du serveur", async () => {
  stubFetch((url) => (url === "/api/assistant/status" ? json({ ...AVAILABLE, available: false, reason: "not_configured" }) : undefined));
  renderChat();
  expect(await screen.findByText("Assistant pas encore configuré")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Ouvrir les Réglages" })).toBeNull();
});

test("rappelle le modèle et la dépense du mois", async () => {
  stubFetch((url) => (url === "/api/assistant/status" ? json(AVAILABLE) : undefined));
  renderChat();
  expect(await screen.findByText(/ce mois-ci : 0,50 \$ sur 5,00 \$/)).toBeInTheDocument();
});

test("questions prêtes pour un titre", async () => {
  stubFetch((url) => (url === "/api/assistant/status" ? json(AVAILABLE) : undefined));
  renderWithProviders(<ChatView conversationId={null} securityId={1} securityName="LVMH" onConversationCreated={() => {}} />);
  expect(await screen.findByRole("button", { name: "Pourquoi est-elle dans le top 10 ?" })).toBeInTheDocument();
});
