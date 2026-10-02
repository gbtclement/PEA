import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, apiSend, type SecurityItem, type SecurityList } from "@/lib/api/client";
import { ENVELOPE_LABELS, RULE_ENVELOPES, STATUS_LABELS } from "@/lib/envelopes";
import { useDebouncedValue } from "@/lib/useDebouncedValue";

type Code = (typeof RULE_ENVELOPES)[number];

function OverrideRow({ item, code }: { item: SecurityItem; code: Code }) {
  const queryClient = useQueryClient();
  const current = item.envelopes.find((e) => e.code === code);
  const mutation = useMutation({
    mutationFn: (override: string | null) => apiSend("PATCH", `/api/securities/${item.id}/envelopes/${code}`, { override }),
    onSettled: () => {
      for (const key of ["settings-search", "overrides", "screener", "security", "top", "movers", "heatmap"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
    },
  });
  return (
    <li className="flex items-center justify-between gap-4 py-2">
      <div className="min-w-0">
        <p className="truncate font-medium">{item.name}</p>
        <p className="text-xs text-muted-foreground">{item.symbol} · {item.market}</p>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{STATUS_LABELS[current?.status ?? "a_verifier"]}</span>
        <select
          aria-label={`${ENVELOPE_LABELS[code]} : statut de ${item.name}`}
          value={current?.override ?? ""}
          onChange={(e) => mutation.mutate(e.target.value || null)}
          className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
        >
          <option value="">Automatique</option>
          <option value="eligible">Éligible</option>
          <option value="a_verifier">À vérifier</option>
          <option value="non_eligible">Non éligible</option>
        </select>
      </div>
    </li>
  );
}

/** Corrections des enveloppes : communes à tous les comptes, donc réservées à l'administrateur. */
export function EnvelopeOverridesCard() {
  const [code, setCode] = useState<Code>("pea");
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
  const corrected = (overrides.data?.items ?? []).filter((item) => item.envelopes.some((e) => e.code === code && e.override));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Enveloppes — corrections manuelles</CardTitle>
        <p className="text-sm text-muted-foreground">
          Le PEA est déduit du pays du siège (code ISIN), le PEA-PME en plus de la taille de l'entreprise (effectif, chiffre
          d'affaires, capitalisation). Si votre banque ou votre courtier dit autre chose pour un titre, corrigez-le ici : votre
          choix est prioritaire et conservé lors des mises à jour. Corriger le PEA d'un titre recalcule aussi son PEA-PME.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <select aria-label="Enveloppe à corriger" value={code} onChange={(e) => setCode(e.target.value as Code)}
                  className="h-8 rounded-lg border border-input bg-white px-2 text-sm">
            {RULE_ENVELOPES.map((c) => <option key={c} value={c}>{ENVELOPE_LABELS[c]}</option>)}
          </select>
          <Input type="search" aria-label="Rechercher un titre" placeholder="Nom, ticker ou ISIN (2 caractères minimum)…"
                 className="w-96 bg-white" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {results.data && (
          <ul className="divide-y divide-border">
            {results.data.items.map((item) => <OverrideRow key={item.id} item={item} code={code} />)}
            {results.data.items.length === 0 && <li className="py-2 text-sm text-muted-foreground">Aucun titre trouvé.</li>}
          </ul>
        )}
        <div>
          <h3 className="mb-1 text-sm font-semibold">Corrections en cours ({ENVELOPE_LABELS[code]})</h3>
          {corrected.length ? (
            <ul className="divide-y divide-border">{corrected.map((item) => <OverrideRow key={item.id} item={item} code={code} />)}</ul>
          ) : (
            <p className="text-sm text-muted-foreground">Aucune correction pour l'instant.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
