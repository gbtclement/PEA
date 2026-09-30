import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { PasswordField } from "@/features/auth/PasswordField";
import { useMe } from "@/features/auth/useMe";
import { apiGet, apiSend, type DataExport, type Me } from "@/lib/api/client";

const day = (iso: string) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" });

/** Droits d'accès, de portabilité et d'effacement (spec 6.2) : export JSON et suppression du compte. */
export function DataCard() {
  const { me } = useMe();
  return (
    <Card id="mes-donnees">
      <CardHeader><CardTitle className="text-base">Mes données</CardTitle></CardHeader>
      <CardContent className="space-y-6">
        <ExportSection />
        {me && <DeleteSection me={me} />}
      </CardContent>
    </Card>
  );
}

function ExportSection() {
  const queryClient = useQueryClient();
  const latest = useQuery({
    queryKey: ["data-export"],
    queryFn: () => apiGet<DataExport | null>("/api/me/export"),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 10_000 : false),
  });
  const request = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/export"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["data-export"] }),
  });
  const row = latest.data;
  const ready = row?.status === "ready" && row.expires_at !== null && new Date(row.expires_at) > new Date();

  if (row?.status === "pending") return <p className="text-sm">Export en préparation : vous recevrez un mail.</p>;
  return (
    <div className="space-y-2">
      {ready && (
        <p className="text-sm">
          <a href={`/api/me/export/${row.id}`} download className="font-medium text-primary underline">Télécharger mes données</a>
          <span className="text-muted-foreground"> · disponible jusqu'au {day(row.expires_at!)}</span>
        </p>
      )}
      <p className="text-sm text-muted-foreground">
        Un fichier JSON avec votre profil, vos réglages, vos ordres, vos favoris et vos conversations. Vous recevrez un mail quand il
        sera prêt.
      </p>
      {request.error && <p role="alert" className="text-sm text-destructive">{request.error.message}</p>}
      <Button variant="outline" disabled={request.isPending} onClick={() => request.mutate()}>Exporter mes données</Button>
    </div>
  );
}

function DeleteSection({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [password, setPassword] = useState("");
  const remove = useMutation({
    mutationFn: () => apiSend("DELETE", "/api/me", { confirm_email: typed, password: me.has_password ? password : null }),
    onSuccess: () => {
      queryClient.clear();
      window.location.assign("/");
    },
  });
  const matches = typed.trim().toLowerCase() === me.email;
  function close(next: boolean) {
    setOpen(next);
    if (!next) { setTyped(""); setPassword(""); remove.reset(); }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">La suppression est immédiate et définitive.</p>
      <Button variant="destructive" onClick={() => setOpen(true)}>Supprimer mon compte</Button>
      <Dialog open={open} onOpenChange={close}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Supprimer mon compte ?</DialogTitle>
            <DialogDescription>
              Votre compte, vos ordres, vos favoris, vos conversations et vos réglages seront supprimés immédiatement et
              définitivement.
            </DialogDescription>
          </DialogHeader>
          <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); remove.mutate(); }}>
            <div className="space-y-1">
              <label htmlFor="delete-email" className="text-sm font-medium">Retapez votre adresse mail</label>
              <Input id="delete-email" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
            </div>
            {me.has_password ? (
              <PasswordField id="delete-password" label="Mot de passe" value={password} onChange={setPassword} autoComplete="current-password" />
            ) : (
              <p className="text-sm">
                Par sécurité,{" "}
                <a href="/api/auth/google/start?suite=%2Freglages&remember=1" className="font-medium text-primary underline">
                  Se reconnecter avec Google
                </a>
                , puis revenez ici dans les 5 minutes.
              </p>
            )}
            {remove.error && <p role="alert" className="text-sm text-destructive">{remove.error.message}</p>}
            <Button type="submit" variant="destructive" disabled={!matches || remove.isPending}>Supprimer définitivement</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
