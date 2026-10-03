import { useQuery } from "@tanstack/react-query";
import { ApiError, apiGet, type Me } from "@/lib/api/client";

/** Le compte connecté, `null` pour un visiteur, `undefined` pendant le premier chargement. */
export function useMe() {
  const { data, isPending } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await apiGet<Me>("/api/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });
  return { me: data, isPending };
}

/** Clé de cache propre au compte (« visiteur » sans compte) : une liste qui dépend des enveloppes est relue à la connexion.
 *  `undefined` tant que le compte n'est pas connu : la requête attend (`enabled`). */
export function useAccountKey(): string | undefined {
  const { me } = useMe();
  return me === undefined ? undefined : (me?.id ?? "visiteur");
}
