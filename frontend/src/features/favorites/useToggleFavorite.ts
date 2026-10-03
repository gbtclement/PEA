import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { apiSend, type ScreenerRow, type SecurityDetail } from "@/lib/api/client";

type Snapshot = [readonly unknown[], unknown][];

function patchFavorite(queryClient: QueryClient, securityId: number, favorite: boolean): Snapshot {
  const snapshot: Snapshot = [];
  for (const key of ["screener", "top", "security"]) {
    for (const [queryKey, data] of queryClient.getQueriesData({ queryKey: [key] })) {
      snapshot.push([queryKey, data]);
      queryClient.setQueryData(queryKey, (old: unknown) => {
        const infinite = old as { pages?: { items: ScreenerRow[] }[] } | undefined;
        if (infinite?.pages) {  // Explorer : pages chargées au fil du défilement
          return { ...infinite, pages: infinite.pages.map((page) => ({
            ...page, items: page.items.map((row) => (row.id === securityId ? { ...row, is_favorite: favorite } : row)),
          })) };
        }
        if (Array.isArray(old)) {
          return (old as ScreenerRow[]).map((row) => (row.id === securityId ? { ...row, is_favorite: favorite } : row));
        }
        const detail = old as SecurityDetail | undefined;
        return detail && detail.id === securityId ? { ...detail, is_favorite: favorite } : old;
      });
    }
  }
  return snapshot;
}

/** Mise à jour immédiate de l'étoile (sans recharger toute la liste), annulée si le serveur refuse. */
export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ securityId, favorite }: { securityId: number; favorite: boolean }) =>
      apiSend(favorite ? "PUT" : "DELETE", `/api/favorites/${securityId}`),
    onMutate: async ({ securityId, favorite }) => {
      await queryClient.cancelQueries({ queryKey: ["screener"] });
      return patchFavorite(queryClient, securityId, favorite);
    },
    onError: (_error, _variables, snapshot) => {
      for (const [queryKey, data] of snapshot ?? []) queryClient.setQueryData(queryKey, data);
    },
  });
}
