import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiSend, type EnvelopesOut } from "@/lib/api/client";
import { ENVELOPE_LABELS, filteringEnvelopes } from "@/lib/envelopes";
import { useEnvelopes } from "./useEnvelopes";

const HINTS: Record<string, string> = {
  pea: "Actions européennes et ETF éligibles, avantage fiscal après 5 ans.",
  pea_pme: "Petites et moyennes entreprises européennes (moins de 5 000 salariés, capitalisation sous 1 Md€) : estimation.",
  cto: "Tous les titres, sans avantage fiscal.",
};

export function EnvelopesCard() {
  const { chosen, isPending } = useEnvelopes();
  return (
    <Card id="enveloppes">
      <CardHeader>
        <CardTitle className="text-base">Mes enveloppes</CardTitle>
        <p className="text-sm text-muted-foreground">
          Les comptes sur lesquels vous investissez. Le top 10, les classements et les prévisions ne montrent que les titres
          compatibles. Rien de coché, ou le compte-titres coché : tous les titres.
        </p>
      </CardHeader>
      <CardContent>
        {isPending ? <Skeleton className="h-24 w-full" /> : <EnvelopesForm key={chosen.join()} initial={chosen} />}
      </CardContent>
    </Card>
  );
}

function EnvelopesForm({ initial }: { initial: string[] }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>(initial);
  const save = useMutation({
    mutationFn: (envelopes: string[]) => apiSend("PUT", "/api/settings/envelopes", { envelopes }) as Promise<EnvelopesOut>,
    onSuccess: (data) => {
      queryClient.setQueryData(["envelopes"], data);
      for (const key of ["top", "movers", "heatmap"]) queryClient.invalidateQueries({ queryKey: [key] });
      toast.success("Enveloppes enregistrées.");
    },
  });
  const toggle = (code: string, on: boolean) =>
    setSelected((current) => Object.keys(ENVELOPE_LABELS).filter((c) => (c === code ? on : current.includes(c))));
  const scope = filteringEnvelopes(selected);
  return (
    <div className="space-y-3">
      <ul className="space-y-2">
        {Object.entries(ENVELOPE_LABELS).map(([code, label]) => (
          <li key={code} className="flex items-start gap-2">
            <input id={`envelope-${code}`} type="checkbox" className="mt-1 size-4 accent-primary"
                   checked={selected.includes(code)} onChange={(e) => toggle(code, e.target.checked)} />
            <label htmlFor={`envelope-${code}`}>
              <span className="block font-medium">{label}</span>
              <span className="block text-xs text-muted-foreground">{HINTS[code]}</span>
            </label>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">
        {scope.length
          ? `Vous verrez les titres compatibles avec : ${scope.map((c) => ENVELOPE_LABELS[c]).join(", ")}.`
          : "Vous verrez tous les titres."}
      </p>
      {save.error && <p role="alert" className="text-sm text-destructive">{save.error.message}</p>}
      <Button onClick={() => save.mutate(selected)} disabled={save.isPending}>Enregistrer mes enveloppes</Button>
    </div>
  );
}
