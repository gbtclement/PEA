import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, type HistoryOut } from "@/lib/api/client";
import { PriceChart } from "./PriceChart";

const PERIODS = [
  { value: "1D", label: "1J" }, { value: "1W", label: "1S" }, { value: "1M", label: "1M" },
  { value: "6M", label: "6M" }, { value: "1Y", label: "1A" }, { value: "5Y", label: "5A" },
] as const;

export function PriceChartPanel({ securityId }: { securityId: number }) {
  const [period, setPeriod] = useState<(typeof PERIODS)[number]["value"]>("6M");
  const [toggles, setToggles] = useState({ sma50: true, sma200: true, rsi: false, macd: false });
  const { data, isPending, isError } = useQuery({
    queryKey: ["history", securityId, period],
    queryFn: () => apiGet<HistoryOut>(`/api/securities/${securityId}/history`, { period }),
    refetchInterval: period === "1D" ? 60_000 : false,
  });
  const intraday = data?.intraday ?? (period === "1D" || period === "1W");
  const toggle = (key: keyof typeof toggles, label: string) => (
    <label className="flex items-center gap-1.5 text-sm">
      <input type="checkbox" aria-label={label} disabled={intraday} checked={toggles[key] && !intraday}
             onChange={(e) => setToggles({ ...toggles, [key]: e.target.checked })} />
      {label}
    </label>
  );

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <Button key={p.value} size="sm" variant={p.value === period ? "default" : "outline"} onClick={() => setPeriod(p.value)}>
                {p.label}
              </Button>
            ))}
          </div>
          <div className="flex gap-4">
            {toggle("sma50", "MM50")}
            {toggle("sma200", "MM200")}
            {toggle("rsi", "RSI")}
            {toggle("macd", "MACD")}
          </div>
        </div>
        {isPending ? (
          <Skeleton className="h-[420px] w-full" />
        ) : isError ? (
          <p role="alert" className="py-20 text-center text-sm text-down">Impossible de charger le graphique.</p>
        ) : data.bars.length === 0 ? (
          <p className="py-20 text-center text-sm text-muted-foreground">Pas de données pour cette période (bourse fermée ou source indisponible).</p>
        ) : (
          <PriceChart history={data} showSma50={toggles.sma50 && !intraday} showSma200={toggles.sma200 && !intraday}
                      showRsi={toggles.rsi && !intraday} showMacd={toggles.macd && !intraday} />
        )}
      </CardContent>
    </Card>
  );
}
