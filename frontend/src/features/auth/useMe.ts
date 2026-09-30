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
