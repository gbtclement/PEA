import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, type FeeEstimate, type SimulationOut } from "@/lib/api/client";
import { formatDate, formatPrice, formatRatioPct } from "@/lib/format";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { cn } from "@/lib/utils";

const PERIODS = [
  { value: "1W", label: "1 semaine" }, { value: "1M", label: "1 mois" }, { value: "6M", label: "6 mois" },
  { value: "1Y", label: "1 an" }, { value: "other", label: "Autre durée" },
];
const UNITS = [{ value: "days", label: "jours" }, { value: "weeks", label: "semaines" }, { value: "months", label: "mois" }, { value: "years", label: "ans" }];
const MAX_DURATION = 36500;  // même plafond que l'API
type SimulationRequest = { amount: number; period: string } | { amount: number; duration: number; unit: string };

export function SimulatorCard({ securityId }: { securityId: number }) {
  const [amount, setAmount] = useState("500");
  const [period, setPeriod] = useState("1M");
  const [duration, setDuration] = useState("2");
  const [unit, setUnit] = useState("years");
  const [request, setRequest] = useState<SimulationRequest | null>(null);
  const value = Number(amount.replace(",", "."));
  const debounced = useDebouncedValue(value, 300);
  const fee = useQuery({
    queryKey: ["fee", debounced],
    queryFn: () => apiGet<FeeEstimate>("/api/fees/estimate", { amount: debounced }),
    enabled: Number.isFinite(debounced) && debounced > 0,
  });
  const simulation = useQuery({
    queryKey: ["simulate", securityId, request],
    queryFn: () => apiGet<SimulationOut>(`/api/securities/${securityId}/simulate`, request!),
    enabled: request !== null,
  });
  const result = simulation.data;

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Et si j'avais investi…</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => {
          e.preventDefault();
          if (!(value > 0)) return;
          if (period !== "other") { setRequest({ amount: value, period }); return; }
          const count = Number(duration);
          if (Number.isInteger(count) && count >= 1 && count <= MAX_DURATION) setRequest({ amount: value, duration: count, unit });
        }}>
          <Input aria-label="Montant" inputMode="decimal" className="w-28 bg-white" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <span>€ il y a</span>
          <select aria-label="Période" value={period} onChange={(e) => setPeriod(e.target.value)} className="h-8 rounded-lg border border-input bg-white px-2">
            {PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          {period === "other" && (
            <>
              <Input aria-label="Durée" inputMode="numeric" className="w-16 bg-white" value={duration} onChange={(e) => setDuration(e.target.value)} />
              <select aria-label="Unité" value={unit} onChange={(e) => setUnit(e.target.value)} className="h-8 rounded-lg border border-input bg-white px-2">
                {UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </>
          )}
          <Button type="submit" size="sm" className="max-md:min-h-11">Simuler</Button>
        </form>
        {fee.data && (
          <p className="text-muted-foreground">
            Pour {formatPrice(fee.data.amount)} € : ≈ {formatPrice(fee.data.fee)} € de frais ({formatRatioPct(fee.data.rate)}).
            {fee.data.amount <= 500 && " À partir de 500 €, le taux passe à 0,18 %."}
          </p>
        )}
        {result?.note && <p className="text-muted-foreground">{result.note}</p>}
        {result && (result.message ? (
          <p className="text-amber-700">{result.message}</p>
        ) : (
          <div className="space-y-3 rounded-lg bg-muted p-4">
            <dl className="space-y-1.5">
              <div className="flex flex-wrap justify-between gap-x-4">
                <dt className="text-muted-foreground">Achat le {formatDate(result.start_date)}</dt>
                <dd className="tabular-nums">
                  {result.shares} action{result.shares > 1 ? "s" : ""} × {formatPrice(result.start_price)} € · frais {formatPrice(result.buy_fee)} €
                </dd>
              </div>
              <div className="flex flex-wrap justify-between gap-x-4">
                <dt className="text-muted-foreground">Valeur aujourd'hui</dt>
                <dd className="tabular-nums">{formatPrice(result.current_value)} € · frais de revente {formatPrice(result.sell_fee)} €</dd>
              </div>
            </dl>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 border-t border-border pt-3">
              <span className="text-muted-foreground">Résultat net, frais inclus</span>
              <span className={cn("text-lg font-semibold tabular-nums", result.gain >= 0 ? "text-up" : "text-down")}>
                {result.gain >= 0 ? "+" : ""}{formatPrice(result.gain)} € ({result.gain_pct != null ? `${result.gain_pct >= 0 ? "+" : ""}${formatPrice(result.gain_pct)} %` : "—"})
              </span>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
