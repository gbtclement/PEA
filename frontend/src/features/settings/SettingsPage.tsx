import { usePageMeta } from "@/seo/usePageMeta";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EligibilityBadge } from "@/features/explorer/EligibilityBadge";
import { apiGet, apiSend, type SecurityItem, type SecurityList } from "@/lib/api/client";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { AssistantSettingsCard } from "./AssistantSettingsCard";
import { FeeSettingsCard } from "./FeeSettingsCard";

function OverrideRow({ item }: { item: SecurityItem }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (override: string | null) => apiSend("PATCH", `/api/securities/${item.id}/eligibility`, { override }),
    onSettled: () => {
      for (const key of ["settings-search", "overrides", "screener", "security", "top"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  return (
    <li className="flex items-center justify-between gap-4 py-2">
      <div className="min-w-0">
        <p className="truncate font-medium">{item.name}</p>
        <p className="text-xs text-muted-foreground">{item.symbol} · {item.market}</p>
      </div>
      <div className="flex items-center gap-3">
        <EligibilityBadge status={item.eligibility} />
        <select
          aria-label={`Éligibilité de ${item.name}`}
          value={item.eligibility_override ?? ""}
          onChange={(e) => mutation.mutate(e.target.value || null)}
          className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
        >
          <option value="">Automatique</option>
          <option value="eligible">Éligible</option>
          <option value="non_eligible">Non éligible</option>
        </select>
      </div>
    </li>
  );
}

export function SettingsPage() {
  usePageMeta({ title: "Réglages", description: "Assistant IA, frais de courtage et corrections d'éligibilité PEA.", noindex: true });
  const [search, setSearch] = useState("");
  const q = useDebouncedValue(search.trim(), 300);
  const results = useQuery({
    queryKey: ["settings-search", q],
    queryFn: () => apiGet<SecurityList>("/api/securities", { q, limit: 10 }),
    enabled: q.length >= 2,
  });
  const overrides = useQuery({
    queryKey: ["overrides"],
    queryFn: () => apiGet<SecurityList>("/api/securities", { overridden: "true", limit: 200 }),
  });

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Réglages</h1>
        <p className="mt-1 text-sm text-muted-foreground">Assistant IA, frais de votre caisse régionale et corrections d'éligibilité.</p>
      </header>
      <AssistantSettingsCard />
      <FeeSettingsCard />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Éligibilité PEA — corrections manuelles</CardTitle>
          <p className="text-sm text-muted-foreground">
            L'éligibilité est déduite automatiquement du pays du siège (code ISIN). Si l'application Crédit Agricole
            dit autre chose pour un titre, corrigez-le ici : votre choix est prioritaire et conservé lors des mises à jour.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input type="search" aria-label="Rechercher un titre" placeholder="Nom, ticker ou ISIN (2 caractères minimum)…"
                 className="w-96 bg-white" value={search} onChange={(e) => setSearch(e.target.value)} />
          {results.data && (
            <ul className="divide-y divide-border">
              {results.data.items.map((item) => <OverrideRow key={item.id} item={item} />)}
              {results.data.items.length === 0 && <li className="py-2 text-sm text-muted-foreground">Aucun titre trouvé.</li>}
            </ul>
          )}
          <div>
            <h3 className="mb-1 text-sm font-semibold">Corrections en cours</h3>
            {overrides.data?.items.length ? (
              <ul className="divide-y divide-border">{overrides.data.items.map((item) => <OverrideRow key={item.id} item={item} />)}</ul>
            ) : (
              <p className="text-sm text-muted-foreground">Aucune correction pour l'instant.</p>
            )}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
