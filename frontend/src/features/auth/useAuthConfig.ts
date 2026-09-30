import { useQuery } from "@tanstack/react-query";
import { apiGet, type AuthConfig } from "@/lib/api/client";

/** Ce que le serveur active : bouton Google, clé publique Turnstile. Ne change pas pendant la visite. */
export function useAuthConfig(): AuthConfig | undefined {
  return useQuery({ queryKey: ["auth-config"], queryFn: () => apiGet<AuthConfig>("/api/auth/config"), staleTime: Infinity }).data;
}
