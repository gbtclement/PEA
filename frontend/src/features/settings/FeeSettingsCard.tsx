import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, apiSend, type SettingsOut } from "@/lib/api/client";

type TierForm = { upTo: string; ratePct: string };
type Form = { minOrders: string; penalty: string; tiers: TierForm[] };

const INTEGRAL: SettingsOut["fee_grid"] = [{ up_to: 500, rate: 0.0048 }, { up_to: 1000, rate: 0.0018 }, { up_to: null, rate: 0.0012 }];

const toInput = (value: number) => String(Math.round(value * 10_000) / 10_000).replace(".", ",");
const parse = (value: string) => {
  const cleaned = value.trim().replace(/\s/g, "").replace(",", ".");
  return cleaned === "" ? Number.NaN : Number(cleaned);
};

function tiersToForm(grid: SettingsOut["fee_grid"]): TierForm[] {
  return grid.map((t) => ({ upTo: t.up_to == null ? "" : toInput(t.up_to), ratePct: toInput(t.rate * 100) }));
}

function toPayload(form: Form): SettingsOut | null {
  const minOrders = Number(form.minOrders.trim());
  const penalty = parse(form.penalty);
  const grid = form.tiers.map((t, i) => ({
    up_to: i === form.tiers.length - 1 ? null : parse(t.upTo),
    rate: Math.round(parse(t.ratePct) * 10_000) / 1_000_000,
  }));
  const bounds = grid.slice(0, -1).map((t) => t.up_to as number);
  const valid = Number.isInteger(minOrders) && minOrders >= 0 && minOrders <= 100 && Number.isFinite(penalty) && penalty >= 0
    && bounds.every((b, i) => Number.isFinite(b) && b > 0 && (i === 0 || b > bounds[i - 1]))
    && grid.every((t) => Number.isFinite(t.rate) && t.rate >= 0 && t.rate <= 0.05);
  return valid ? { min_orders_per_year: minOrders, penalty_fee: penalty, fee_grid: grid } : null;
}

export function FeeSettingsCard() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => apiGet<SettingsOut>("/api/settings") });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Frais et obligations de la caisse régionale</CardTitle>
        <p className="text-sm text-muted-foreground">
          Valeurs par défaut : formule Invest Store Intégral (caisse de Paris). Vérifiez-les dans la brochure tarifaire de votre caisse.
        </p>
      </CardHeader>
      <CardContent>
        {settings.isError && <p className="text-sm text-down">Impossible de charger les réglages.</p>}
        {settings.isPending && <Skeleton className="h-40 w-full" />}
        {settings.data && <FeeForm initial={settings.data} />}
      </CardContent>
    </Card>
  );
}

function FeeForm({ initial }: { initial: SettingsOut }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Form>({
    minOrders: String(initial.min_orders_per_year), penalty: toInput(initial.penalty_fee), tiers: tiersToForm(initial.fee_grid),
  });
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (payload: SettingsOut) => apiSend("PUT", "/api/settings", payload),
    onSuccess: () => {
      toast.success("Réglages enregistrés");
      for (const key of ["settings", "order-counter", "portfolio", "fee", "simulate"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
    onError: (err) => setError(err.message),
  });

  const setTier = (index: number, patch: Partial<TierForm>) =>
    setForm((f) => ({ ...f, tiers: f.tiers.map((t, i) => (i === index ? { ...t, ...patch } : t)) }));

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const payload = toPayload(form);
    if (!payload) {
      setError("Vérifiez les valeurs : bornes croissantes, taux entre 0 et 5 %, nombre d'ordres entre 0 et 100.");
      return;
    }
    setError(null);
    save.mutate(payload);
  }

  return (
    <form onSubmit={submit} className="space-y-4 text-sm">
      <div className="flex gap-6">
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Ordres minimum par an</span>
          <Input aria-label="Ordres minimum par an" inputMode="numeric" className="w-32 bg-white" value={form.minOrders}
                 onChange={(e) => setForm({ ...form, minOrders: e.target.value })} />
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-muted-foreground">Frais en cas de non-respect (€ / an)</span>
          <Input aria-label="Frais en cas de non-respect (€)" inputMode="decimal" className="w-32 bg-white" value={form.penalty}
                 onChange={(e) => setForm({ ...form, penalty: e.target.value })} />
        </label>
      </div>
      <div>
        <h3 className="mb-1 text-xs font-semibold text-muted-foreground">Grille de courtage (le taux de la tranche s'applique au montant total de l'ordre)</h3>
        <ul className="space-y-2">
          {form.tiers.map((tier, index) => {
            const last = index === form.tiers.length - 1;
            return (
              <li key={index} className="flex items-center gap-2">
                <span className="w-24 text-muted-foreground">{last ? (index === 0 ? "Tout montant" : "Au-delà") : "Jusqu'à"}</span>
                {!last && (
                  <Input aria-label={`Borne haute de la tranche ${index + 1} (€)`} inputMode="decimal" className="w-28 bg-white"
                         value={tier.upTo} onChange={(e) => setTier(index, { upTo: e.target.value })} />
                )}
                {!last && <span>€ :</span>}
                <Input aria-label={`Taux de la tranche ${index + 1} (%)`} inputMode="decimal" className="w-20 bg-white"
                       value={tier.ratePct} onChange={(e) => setTier(index, { ratePct: e.target.value })} />
                <span>%</span>
                {!last && (
                  <Button type="button" variant="ghost" size="sm" aria-label={`Supprimer la tranche ${index + 1}`}
                          onClick={() => setForm((f) => ({ ...f, tiers: f.tiers.filter((_, i) => i !== index) }))}>✕</Button>
                )}
              </li>
            );
          })}
        </ul>
        {form.tiers.length < 6 && (
          <Button type="button" variant="ghost" size="sm" className="mt-1"
                  onClick={() => setForm((f) => ({ ...f, tiers: [...f.tiers.slice(0, -1), { upTo: "", ratePct: "" }, f.tiers[f.tiers.length - 1]] }))}>
            + Ajouter une tranche
          </Button>
        )}
      </div>
      {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-down">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending}>Enregistrer les frais</Button>
        <Button type="button" variant="outline" onClick={() => setForm({ minOrders: "12", penalty: "96", tiers: tiersToForm(INTEGRAL) })}>
          Revenir à la grille Intégral
        </Button>
      </div>
    </form>
  );
}
