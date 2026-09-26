import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiGet, type SecurityList } from "@/lib/api/client";

export const PAGE_SIZE = 50;

export function useSecurities({ q, offset }: { q: string; offset: number }) {
  return useQuery({
    queryKey: ["securities", { q, offset }],
    queryFn: () => apiGet<SecurityList>("/api/securities", { q, limit: PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
}
