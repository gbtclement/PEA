import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { apiGet, type ScreenerFacets, type ScreenerPageOut } from "@/lib/api/client";
import { filtersKey } from "./filters";

export type Region = "europe" | "us";
export const PAGE_SIZE = 50;

/** Explorer et ETF : pages de 50 titres filtrées et triées par le serveur, chargées au fil du défilement. */
export function useScreener(kind: "stock" | "etf", region: Region, params: Record<string, string>) {
  return useInfiniteQuery({
    // Même clé que la première page embarquée dans le HTML par le serveur (filtres par défaut).
    queryKey: ["screener", kind, region, params.sort, params.order, filtersKey(params)],
    queryFn: ({ pageParam }) => apiGet<ScreenerPageOut>("/api/screener", { kind, region, ...params, limit: PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((count, page) => count + page.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
    refetchInterval: 60_000,
  });
}

/** Valeurs proposées par les filtres Secteur, Pays et Place. */
export function useScreenerFacets(kind: "stock" | "etf", region: Region) {
  return useQuery({
    queryKey: ["screener-facets", kind, region],
    queryFn: () => apiGet<ScreenerFacets>("/api/screener/facets", { kind, region }),
    staleTime: 10 * 60_000,
  });
}
