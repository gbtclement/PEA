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
