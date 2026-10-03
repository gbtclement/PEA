import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";

/** Une page restée ouverte au changement des CGU : l'API répond 403 terms_outdated, le compte relu déclenche la redirection. */
function onError(error: Error, client: () => QueryClient) {
  if (error instanceof ApiError && error.code === "terms_outdated") client().invalidateQueries({ queryKey: ["me"] });
}

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError: (error) => onError(error, () => client) }),
    mutationCache: new MutationCache({ onError: (error) => onError(error, () => client) }),
    defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
  });
  return client;
}

/** Données de la page servies dans le HTML (`#cotalyx-data`, voir /api/seo/page) : affichées sans attendre l'API. */
export function seedFromPage(client: QueryClient, doc: Document = document): void {
  const script = doc.getElementById("cotalyx-data");
  if (!script?.textContent) return;
  try {
    const entries = JSON.parse(script.textContent) as [readonly unknown[], unknown][];
    for (const [key, data] of entries) client.setQueryData(key, data);
  } catch {
    // HTML mal formé : l'application charge ses données comme d'habitude
  }
}
