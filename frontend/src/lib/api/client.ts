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
