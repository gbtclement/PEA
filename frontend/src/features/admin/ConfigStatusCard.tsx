import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, apiGet, apiSend, type ConfigStatus } from "@/lib/api/client";

const ITEMS: { key: keyof ConfigStatus; label: string; variables: string }[] = [
  { key: "claude", label: "Claude", variables: "ANTHROPIC_API_KEY" },
  { key: "smtp", label: "Envoi des mails", variables: "SMTP_HOST, SMTP_USER, SMTP_PASSWORD" },
  { key: "google", label: "Google", variables: "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET" },
  { key: "turnstile", label: "Turnstile", variables: "TURNSTILE_SITE_KEY, TURNSTILE_SECRET_KEY" },
  { key: "app_secret", label: "Secret de l'application", variables: "APP_SECRET" },
  { key: "admin_email", label: "Adresse de l'admin", variables: "ADMIN_EMAIL" },
];

export function ConfigStatusCard() {
  const status = useQuery({ queryKey: ["config-status"], queryFn: () => apiGet<ConfigStatus>("/api/admin/config-status") });
  const test = useMutation({ mutationFn: () => apiSend("POST", "/api/admin/test-email") as Promise<{ message: string }> });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">État de la configuration</CardTitle>
        <p className="text-sm text-muted-foreground">Ce qui est renseigné dans le fichier .env. Aucune valeur n'est affichée.</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul aria-label="État de la configuration" className="divide-y divide-border text-sm">
          {ITEMS.map(({ key, label, variables }) => {
            const ok = status.data?.[key];
            return (
              <li key={key} className="flex items-center justify-between gap-4 py-2">
                <div>
                  <p className="font-medium">{label}</p>
                  <p className="text-xs text-muted-foreground">{variables}</p>
                </div>
                {status.data && (
                  <span className={ok ? "flex items-center gap-1 text-emerald-700" : "flex items-center gap-1 text-muted-foreground"}>
                    {ok ? <Check className="size-4" aria-hidden /> : <X className="size-4" aria-hidden />}
                    {ok ? "Renseigné" : "Manquant"}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
        <div className="flex items-center gap-3">
          <Button variant="outline" disabled={test.isPending} onClick={() => test.mutate()}>Envoyer un mail de test</Button>
          {test.data && <p role="status" className="text-sm text-muted-foreground">{test.data.message}</p>}
          {test.error && <p role="alert" className="text-sm text-destructive">{(test.error as ApiError).message}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
