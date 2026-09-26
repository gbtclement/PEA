import { useQuery } from "@tanstack/react-query";
import { apiGet, type ScreenerRow } from "@/lib/api/client";

export function useScreener(kind: "stock" | "etf") {
  return useQuery({
    queryKey: ["screener", kind],
    queryFn: () => apiGet<ScreenerRow[]>("/api/screener", { kind }),
    refetchInterval: 60_000,
  });
}
