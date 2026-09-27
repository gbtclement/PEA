import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, apiSend, type AssistantSettingsOut } from "@/lib/api/client";

const STATUS = { settings: "Configurée", env: "Définie dans le fichier .env" } as const;

export function AssistantSettingsCard() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["assistant-settings"], queryFn: () => apiGet<AssistantSettingsOut>("/api/assistant/settings") });
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (body: object) => apiSend("PUT", "/api/assistant/settings", body) as Promise<AssistantSettingsOut>,
    onSuccess: (next) => {
      queryClient.setQueryData(["assistant-settings"], next);
      setApiKey("");
      setError(null);
      toast.success("Réglages de l'assistant enregistrés");
    },
    onError: (err) => setError(err.message),
  });
  if (!data) return null;
  const selected = model ?? data.model;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Assistant IA (Claude)</CardTitle>
        <p className="text-sm text-muted-foreground">
          Créez une clé sur console.anthropic.com (rubrique API Keys). Elle est chiffrée sur votre ordinateur et n'est jamais
          renvoyée au navigateur. Chaque question est facturée par Anthropic selon le modèle choisi.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2 text-sm">
          Statut : <Badge variant={data.configured ? "default" : "secondary"}>{data.source ? STATUS[data.source] : "Non configurée"}</Badge>
        </div>
        <form className="flex flex-wrap items-end gap-3"
              onSubmit={(e) => { e.preventDefault(); save.mutate({ ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}), model: selected }); }}>
          <label className="space-y-1 text-xs font-medium text-muted-foreground">
            Clé API Claude
            <Input type="password" autoComplete="off" className="w-96 bg-white"
                   placeholder={data.configured ? "•••••••• (laisser vide pour la garder)" : "sk-ant-…"}
                   value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          </label>
          <label className="space-y-1 text-xs font-medium text-muted-foreground">
            Modèle IA
            <select value={selected} onChange={(e) => setModel(e.target.value)}
                    className="block h-8 rounded-lg border border-input bg-white px-2 text-sm text-foreground">
              {data.models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </label>
          <Button type="submit" disabled={save.isPending}>Enregistrer</Button>
          {data.source === "settings" && (
            <Button type="button" variant="outline" disabled={save.isPending} onClick={() => save.mutate({ remove_key: true, model: selected })}>
              Supprimer la clé
            </Button>
          )}
        </form>
        {error && <p role="alert" className="text-sm text-down">{error}</p>}
      </CardContent>
    </Card>
  );
}
