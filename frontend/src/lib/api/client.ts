import type { components } from "./schema";

export type SecurityItem = components["schemas"]["SecurityItem"];
export type SecurityList = components["schemas"]["SecurityList"];
export type StatusResponse = components["schemas"]["StatusResponse"];
export type JobStatus = components["schemas"]["JobStatus"];

export type Me = components["schemas"]["MeOut"];
export type AuthConfig = components["schemas"]["AuthConfigOut"];
export type DataExport = components["schemas"]["ExportOut"];
export type NotificationPrefs = components["schemas"]["NotificationPrefsOut"];
export type PriceAlert = components["schemas"]["PriceAlertOut"];
export type BillingPlans = components["schemas"]["PlansOut"];
export type BillingSubscription = components["schemas"]["SubscriptionOut"];
export type RedirectOut = components["schemas"]["RedirectOut"];

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** Jeton anti-CSRF posé par l'API à la connexion (cookie lisible), renvoyé dans un en-tête à chaque modification. */
export function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)cotalyx_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function writeHeaders(accept: string, json: boolean): Record<string, string> {
  const token = csrfToken();
  return { Accept: accept, ...(json ? { "Content-Type": "application/json" } : {}), ...(token ? { "X-CSRF-Token": token } : {}) };
}

export async function apiGet<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  const response = await fetch(query ? `${path}?${query}` : path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw await errorFrom(response, path);
  return (await response.json()) as T;
}

export type ScreenerRow = components["schemas"]["ScreenerRow"];
export type TopItem = components["schemas"]["TopItem"];
export type Movers = components["schemas"]["Movers"];
export type HeatmapItem = components["schemas"]["HeatmapItem"];
export type SecurityDetail = components["schemas"]["SecurityDetail"];
export type HistoryOut = components["schemas"]["HistoryOut"];
export type NewsOut = components["schemas"]["NewsOut"];
export type SimulationOut = components["schemas"]["SimulationOut"];
export type FeeEstimate = components["schemas"]["FeeEstimate"];
export type ComponentOut = components["schemas"]["ComponentOut"];

export type OrderIn = components["schemas"]["OrderIn"];
export type OrderOut = components["schemas"]["OrderOut"];
export type CounterOut = components["schemas"]["CounterOut"];
export type PortfolioOut = components["schemas"]["PortfolioOut"];
export type PositionOut = components["schemas"]["PositionOut"];
export type HistoryPointOut = components["schemas"]["HistoryPointOut"];
export type SettingsOut = components["schemas"]["SettingsOut"];
export type AssistantStatus = components["schemas"]["AssistantStatusOut"];
export type SessionItem = components["schemas"]["SessionOut"];
export type AdminUser = components["schemas"]["AdminUserOut"];
export type AdminUserList = components["schemas"]["AdminUserListOut"];
export type AdminSettings = components["schemas"]["AdminSettingsOut"];
export type ConfigStatus = components["schemas"]["ConfigStatusOut"];
export type ConversationOut = components["schemas"]["ConversationOut"];
export type ConversationDetail = components["schemas"]["ConversationDetail"];
export type MessageOut = components["schemas"]["MessageOut"];
export type ForecastList = components["schemas"]["ForecastListOut"];
export type ForecastRow = components["schemas"]["ForecastRowOut"];
export type HorizonForecast = components["schemas"]["HorizonForecastOut"];
export type SignalStats = components["schemas"]["SignalStatsOut"];
export type SignalStatsRow = components["schemas"]["SignalStatsRowOut"];
export type SignalStat = components["schemas"]["SignalStatOut"];
export type TrackRecord = components["schemas"]["TrackRecordOut"];
export type Backtest = components["schemas"]["BacktestOut"];
export type RealTrack = components["schemas"]["RealTrackOut"];
export type SecurityForecast = components["schemas"]["SecurityForecastOut"];

async function errorFrom(response: Response, path: string): Promise<ApiError> {
  let message = `Erreur ${response.status} sur ${path}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") message = body.detail;
    else if (body.detail && typeof body.detail === "object" && "message" in body.detail) {
      const detail = body.detail as { code?: string; message: string };
      return new ApiError(response.status, detail.message, detail.code ?? null);
    }
  } catch {
    // corps absent ou non JSON : message générique
  }
  return new ApiError(response.status, message);
}

export async function apiSend(method: "POST" | "PUT" | "DELETE" | "PATCH", path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(path, {
    method,
    headers: writeHeaders("application/json", body !== undefined),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw await errorFrom(response, path);
  return response.status === 204 ? null : response.json();
}

export type ChatEvent =
  | { type: "start"; user_message: MessageOut }
  | { type: "text"; text: string }
  | { type: "tool"; name: string; label: string }
  | { type: "error"; message: string }
  | { type: "done"; message: MessageOut; conversation: ConversationOut };

/** Envoie un POST et lit la réponse SSE au fil de l'eau (EventSource ne sait pas faire de POST). */
export async function streamSSE(path: string, body: unknown, onEvent: (event: ChatEvent) => void, signal?: AbortSignal): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: writeHeaders("text/event-stream", true),
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw await errorFrom(response, path);
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index;
    while ((index = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const data = block.split("\n").filter((line) => line.startsWith("data: ")).map((line) => line.slice(6)).join("\n");
      if (data) onEvent(JSON.parse(data) as ChatEvent);
    }
  }
}
