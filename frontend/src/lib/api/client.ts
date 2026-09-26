import type { components } from "./schema";

export type SecurityItem = components["schemas"]["SecurityItem"];
export type SecurityList = components["schemas"]["SecurityList"];
export type StatusResponse = components["schemas"]["StatusResponse"];
export type JobStatus = components["schemas"]["JobStatus"];

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiGet<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  const response = await fetch(query ? `${path}?${query}` : path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new ApiError(response.status, `Erreur ${response.status} sur ${path}`);
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

async function errorFrom(response: Response, path: string): Promise<ApiError> {
  let message = `Erreur ${response.status} sur ${path}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // corps absent ou non JSON : message générique
  }
  return new ApiError(response.status, message);
}

export async function apiSend(method: "POST" | "PUT" | "DELETE" | "PATCH", path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(path, {
    method,
    headers: { Accept: "application/json", ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw await errorFrom(response, path);
  return response.status === 204 ? null : response.json();
}
