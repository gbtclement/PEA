import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiGet, type FeeEstimate, type SimulationOut } from "@/lib/api/client";
import { formatDate, formatPrice, formatRatioPct } from "@/lib/format";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { cn } from "@/lib/utils";

const PERIODS = [{ value: "1W", label: "1 semaine" }, { value: "1M", label: "1 mois" }, { value: "6M", label: "6 mois" }, { value: "1Y", label: "1 an" }];

export function SimulatorCard({ securityId }: { securityId: number }) {
  const [amount, setAmount] = useState("500");
  const [period, setPeriod] = useState("1M");
  const [request, setRequest] = useState<{ amount: number; period: string } | null>(null);
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
        <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (value > 0) setRequest({ amount: value, period }); }}>
          <Input aria-label="Montant" inputMode="decimal" className="w-28 bg-white" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <span>€ il y a</span>
          <select aria-label="Période" value={period} onChange={(e) => setPeriod(e.target.value)} className="h-8 rounded-lg border border-input bg-white px-2">
            {PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <Button type="submit" size="sm">Simuler</Button>
        </form>
        {fee.data && (
          <p className="text-muted-foreground">
            Pour {formatPrice(fee.data.amount)} € : ≈ {formatPrice(fee.data.fee)} € de frais ({formatRatioPct(fee.data.rate)}).
            {fee.data.amount <= 500 && " À partir de 500 €, le taux passe à 0,18 %."}
          </p>
        )}
        {result && (result.message ? (
          <p className="text-amber-700">{result.message}</p>
        ) : (
          <div className="rounded-lg bg-muted p-3">
            <p>{result.shares} action{result.shares > 1 ? "s" : ""} achetée{result.shares > 1 ? "s" : ""} le {formatDate(result.start_date)} à {formatPrice(result.start_price)} € (frais {formatPrice(result.buy_fee)} €)</p>
            <p>Valeur aujourd'hui : {formatPrice(result.current_value)} € (frais de revente {formatPrice(result.sell_fee)} €)</p>
            <p className={cn("mt-1 text-base font-semibold", result.gain >= 0 ? "text-up" : "text-down")}>
              {result.gain >= 0 ? "+" : ""}{formatPrice(result.gain)} € ({result.gain_pct != null ? `${result.gain_pct >= 0 ? "+" : ""}${formatPrice(result.gain_pct)} %` : "—"})
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
