import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, apiSend, type SessionItem } from "@/lib/api/client";

const when = (iso: string) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });

export function DevicesCard() {
  const queryClient = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => apiGet<SessionItem[]>("/api/me/sessions") });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["sessions"] });
  const revoke = useMutation({
    mutationFn: (session: SessionItem) => apiSend("DELETE", `/api/me/sessions/${session.id}`),
    onSuccess: (_data, session) => (session.current ? queryClient.clear() : refresh()),
  });
  const revokeOthers = useMutation({ mutationFn: () => apiSend("DELETE", "/api/me/sessions"), onSuccess: refresh });
  const others = (sessions.data ?? []).filter((s) => !s.current).length;
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Appareils connectés</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <ul className="divide-y divide-border">
          {(sessions.data ?? []).map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-4 py-2">
              <div className="min-w-0">
                <p className="flex items-center gap-2 font-medium">{s.device}{s.current && <Badge variant="secondary">Cet appareil</Badge>}</p>
                <p className="text-xs text-muted-foreground">Dernière activité le {when(s.last_seen_at)}{s.ip ? ` · réseau ${s.ip}` : ""}</p>
              </div>
              <Button size="sm" variant="outline" aria-label={`Déconnecter ${s.device}`} disabled={revoke.isPending}
                      onClick={() => revoke.mutate(s)}>Déconnecter</Button>
            </li>
          ))}
        </ul>
        {others > 0 && (
          <Button variant="outline" disabled={revokeOthers.isPending} onClick={() => revokeOthers.mutate()}>Déconnecter tous les autres</Button>
        )}
      </CardContent>
    </Card>
  );
}
