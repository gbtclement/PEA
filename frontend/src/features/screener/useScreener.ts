import { useQuery } from "@tanstack/react-query";
import { apiGet, type ScreenerRow } from "@/lib/api/client";

export type Region = "europe" | "us";

export function useScreener(kind: "stock" | "etf", region: Region) {
  return useQuery({
    queryKey: ["screener", kind, region],
    queryFn: () => apiGet<ScreenerRow[]>("/api/screener", { kind, region }),
    refetchInterval: 60_000,
  });
}
