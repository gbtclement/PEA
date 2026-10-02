import { useQuery } from "@tanstack/react-query";
import { useMe } from "@/features/auth/useMe";
import { apiGet, type EnvelopesOut } from "@/lib/api/client";
import { filteringEnvelopes } from "@/lib/envelopes";

/** Enveloppes choisies dans les réglages ; un visiteur n'en a aucune (tous les titres). */
export function useEnvelopes() {
  const { me } = useMe();
  const query = useQuery({
    queryKey: ["envelopes"],
    queryFn: () => apiGet<EnvelopesOut>("/api/settings/envelopes"),
    enabled: !!me,
  });
  const chosen = query.data?.envelopes ?? [];
  return { chosen, filtering: filteringEnvelopes(chosen), isPending: me === undefined || (!!me && query.isPending) };
}
