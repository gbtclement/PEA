import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, type HistoryOut } from "@/lib/api/client";
import { PriceChart } from "./PriceChart";

const PERIODS = [
  { value: "1D", label: "1J" }, { value: "1W", label: "1S" }, { value: "1M", label: "1M" },
  { value: "6M", label: "6M" }, { value: "1Y", label: "1A" }, { value: "5Y", label: "5A" },
  { value: "10Y", label: "10A" }, { value: "MAX", label: "Max" }, { value: "custom", label: "Personnalisé" },
] as const;
type Period = (typeof PERIODS)[number]["value"];
const GROUPED: Record<string, string> = {
  week: "Une barre par semaine sur cette période.", month: "Une barre par mois sur cette période.",
};

export function PriceChartPanel({ securityId }: { securityId: number }) {
  const [period, setPeriod] = useState<Period>("6M");
  const [draft, setDraft] = useState({ start: "", end: "" });
  const [range, setRange] = useState<{ start: string; end: string } | null>(null);
  const [toggles, setToggles] = useState({ sma50: true, sma200: true, rsi: false, macd: false });
  const custom = period === "custom";
  const { data, isPending, isError } = useQuery({
    queryKey: ["history", securityId, period, custom ? range : null],
    queryFn: () => apiGet<HistoryOut>(`/api/securities/${securityId}/history`, custom ? { period, ...range } : { period }),
    enabled: !custom || range !== null,
    placeholderData: keepPreviousData,  // en « Personnalisé », la période précédente reste affichée en attendant les dates
    refetchInterval: period === "1D" ? 60_000 : false,
  });
  const reversed = draft.start !== "" && draft.end !== "" && draft.end < draft.start;
  const choose = (value: Period) => {
    if (value === "custom" && !custom) setDraft({ start: data?.first_date ?? "", end: data?.last_date ?? "" });
    setPeriod(value);
  };
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
          <div className="flex flex-wrap gap-1">
            {PERIODS.map((p) => (
              <Button key={p.value} size="sm" variant={p.value === period ? "default" : "outline"} onClick={() => choose(p.value)}>
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
        {custom && (
          <form className="flex flex-wrap items-center gap-2 text-sm"
                onSubmit={(e) => { e.preventDefault(); if (!reversed && draft.start && draft.end) setRange({ ...draft }); }}>
            <label className="flex items-center gap-1.5">Du
              <Input type="date" aria-label="Début" className="w-40 bg-white" value={draft.start}
                     min={data?.first_date ?? undefined} max={data?.last_date ?? undefined}
                     onChange={(e) => setDraft({ ...draft, start: e.target.value })} />
            </label>
            <label className="flex items-center gap-1.5">au
              <Input type="date" aria-label="Fin" className="w-40 bg-white" value={draft.end}
                     min={data?.first_date ?? undefined} max={data?.last_date ?? undefined}
                     onChange={(e) => setDraft({ ...draft, end: e.target.value })} />
            </label>
            <Button type="submit" size="sm" disabled={reversed || !draft.start || !draft.end}>Appliquer</Button>
            {reversed && <p role="alert" className="w-full text-down">La date de fin doit suivre la date de début.</p>}
          </form>
        )}
        {isPending ? (
          <Skeleton className="h-[420px] w-full" />
        ) : isError ? (
          <p role="alert" className="py-20 text-center text-sm text-down">Impossible de charger le graphique.</p>
        ) : data.bars.length === 0 ? (
          <p className="py-20 text-center text-sm text-muted-foreground">Pas de données pour cette période (bourse fermée ou source indisponible).</p>
        ) : (
          <>
            <PriceChart history={data} showSma50={toggles.sma50 && !intraday} showSma200={toggles.sma200 && !intraday}
                        showRsi={toggles.rsi && !intraday} showMacd={toggles.macd && !intraday} />
            {GROUPED[data.interval] && <p className="text-xs text-muted-foreground">{GROUPED[data.interval]}</p>}
          </>
        )}
      </CardContent>
    </Card>
  );
}
