import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, apiGet, apiSend, type AdminSettings } from "@/lib/api/client";

export function AssistantAdminCard() {
  const settings = useQuery({ queryKey: ["admin-settings"], queryFn: () => apiGet<AdminSettings>("/api/admin/settings") });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Assistant IA</CardTitle>
        <p className="text-sm text-muted-foreground">La clé Claude se règle uniquement dans le fichier .env (ANTHROPIC_API_KEY).</p>
      </CardHeader>
      <CardContent>{settings.data && <AssistantForm settings={settings.data} />}</CardContent>
    </Card>
  );
}

function AssistantForm({ settings }: { settings: AdminSettings }) {
  const queryClient = useQueryClient();
  const [model, setModel] = useState(settings.ai_model);
  const [limit, setLimit] = useState(String(settings.ai_monthly_cost_limit_usd).replace(".", ","));
  const save = useMutation({
    mutationFn: () => apiSend("PUT", "/api/admin/settings", {
      ai_model: model, ai_monthly_cost_limit_usd: Number(limit.trim().replace(",", ".")),
    }) as Promise<AdminSettings>,
    onSuccess: (data) => {
      queryClient.setQueryData(["admin-settings"], data);
      queryClient.invalidateQueries({ queryKey: ["assistant-status"] });
    },
  });
  return (
    <form className="grid max-w-sm gap-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <label className="text-sm">Modèle par défaut
        <select className="mt-1 h-9 w-full rounded-lg border border-input bg-white px-2 text-sm" value={model} onChange={(e) => setModel(e.target.value)}>
          {settings.models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
        </select>
      </label>
      <label className="text-sm">Limite mensuelle par utilisateur ($)
        <Input className="mt-1 w-32 bg-white" inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value)} required />
      </label>
      <p className="text-xs text-muted-foreground">Une fois la limite atteinte, l'assistant refuse les nouvelles questions jusqu'au 1er du mois suivant.</p>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={save.isPending}>Enregistrer les réglages de l'assistant</Button>
        {save.isSuccess && <p role="status" className="text-sm text-muted-foreground">Enregistré.</p>}
        {save.error && <p role="alert" className="text-sm text-destructive">{(save.error as ApiError).message}</p>}
      </div>
    </form>
  );
}
