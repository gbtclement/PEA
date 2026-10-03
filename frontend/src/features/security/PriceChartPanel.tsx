import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, type HistoryOut } from "@/lib/api/client";
import { useIsMobile } from "@/lib/useIsMobile";
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
  const mobile = useIsMobile();
  const [showIndicators, setShowIndicators] = useState(false);  // téléphone : cases repliées dans un menu
  const [basePeriod, setBasePeriod] = useState<Exclude<Period, "custom">>("6M");
  const custom = period === "custom";
  // En « Personnalisé » sans dates appliquées, la dernière période choisie reste chargée : graphique et bornes des dates.
  const shown = custom && range === null ? basePeriod : period;
  const { data, isPending, isError, isPlaceholderData, isFetching } = useQuery({
    queryKey: ["history", securityId, shown, shown === "custom" ? range : null],
    queryFn: () => apiGet<HistoryOut>(`/api/securities/${securityId}/history`,
                                      shown === "custom" ? { period: shown, ...range } : { period: shown }),
    // Pendant le chargement d'une autre période, l'ancienne reste affichée (jamais celle d'un autre titre).
    placeholderData: (previous, previousQuery) => (previousQuery?.queryKey[1] === securityId ? previous : undefined),
    refetchInterval: shown === "1D" ? 60_000 : false,
  });
  const loadingOther = isFetching && isPlaceholderData;  // nouvelle période en route (Max : plusieurs secondes)
  const reversed = draft.start !== "" && draft.end !== "" && draft.end < draft.start;
  const choose = (value: Period) => {
    // Revenir sur « Personnalisé » reprend la période appliquée ; sinon tout l'historique connu.
    if (value === "custom" && !custom) setDraft(range ?? { start: data?.first_date ?? "", end: data?.last_date ?? "" });
    if (value !== "custom") setBasePeriod(value);
    setPeriod(value);
  };
  // « Personnalisé » choisi avant l'arrivée des premières données : les bornes sont remplies dès qu'elles arrivent.
  useEffect(() => {
    if (custom && draft.start === "" && draft.end === "" && data?.first_date && data?.last_date) {
      setDraft({ start: data.first_date, end: data.last_date });
    }
  }, [custom, data?.first_date, data?.last_date]); // eslint-disable-line react-hooks/exhaustive-deps
  const intraday = data?.intraday ?? (shown === "1D" || shown === "1W");
  const toggle = (key: keyof typeof toggles, label: string) => (
    <label className="flex items-center gap-1.5 text-sm">
      <input type="checkbox" aria-label={label} disabled={intraday} checked={toggles[key] && !intraday}
             onChange={(e) => setToggles({ ...toggles, [key]: e.target.checked })} />
      {label}
    </label>
  );

  const indicators = <>{toggle("sma50", "MM50")}{toggle("sma200", "MM200")}{toggle("rsi", "RSI")}{toggle("macd", "MACD")}</>;

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div role="group" aria-label="Période" className="-mx-1 flex max-w-full gap-1 overflow-x-auto px-1 pb-1 md:flex-wrap md:overflow-visible md:pb-0">
            {PERIODS.map((p) => (
              <Button key={p.value} size="sm" variant={p.value === period ? "default" : "outline"} onClick={() => choose(p.value)}
                      className="shrink-0 max-md:min-h-11">
                {p.label}
              </Button>
            ))}
          </div>
          {mobile ? (
            <Button variant="outline" size="sm" className="min-h-11" aria-expanded={showIndicators}
                    onClick={() => setShowIndicators((v) => !v)}>Indicateurs</Button>
          ) : (
            <div className="flex gap-4">{indicators}</div>
          )}
        </div>
        {mobile && showIndicators && (
          <div role="group" aria-label="Indicateurs" className="flex flex-wrap gap-x-5 gap-y-2 [&_label]:min-h-11">{indicators}</div>
        )}
        {custom && (
          <form className="flex flex-wrap items-center gap-2 text-sm"
                onSubmit={(e) => { e.preventDefault(); if (!reversed && draft.start && draft.end) setRange({ ...draft }); }}>
            <label className="flex items-center gap-1.5">Du
              <Input type="date" aria-label="Début" className="w-full bg-white sm:w-40" value={draft.start}
                     min={data?.first_date ?? undefined} max={data?.last_date ?? undefined}
                     onChange={(e) => setDraft({ ...draft, start: e.target.value })} />
            </label>
            <label className="flex items-center gap-1.5">au
              <Input type="date" aria-label="Fin" className="w-full bg-white sm:w-40" value={draft.end}
                     min={data?.first_date ?? undefined} max={data?.last_date ?? undefined}
                     onChange={(e) => setDraft({ ...draft, end: e.target.value })} />
            </label>
            <Button type="submit" size="sm" disabled={reversed || !draft.start || !draft.end}>Appliquer</Button>
            {reversed && <p role="alert" className="w-full text-down">La date de fin doit suivre la date de début.</p>}
          </form>
        )}
        {isPending ? (
          <Skeleton className="h-[300px] w-full md:h-[420px]" />
        ) : isError ? (
          <p role="alert" className="py-20 text-center text-sm text-down">Impossible de charger le graphique.</p>
        ) : data.bars.length === 0 ? (
          <p className="py-20 text-center text-sm text-muted-foreground">
            {shown === "custom"
              ? "Aucun cours sur cette période : le titre n'était peut-être pas encore coté."
              : "Pas de données pour cette période (bourse fermée ou source indisponible)."}
          </p>
        ) : (
          <>
            <PriceChart history={data} showSma50={toggles.sma50 && !intraday} showSma200={toggles.sma200 && !intraday}
                        showRsi={toggles.rsi && !intraday} showMacd={toggles.macd && !intraday} />
            {GROUPED[data.interval] && <p className="text-xs text-muted-foreground">{GROUPED[data.interval]}</p>}
            {loadingOther && <p role="status" className="text-xs text-muted-foreground">Chargement de la période…</p>}
          </>
        )}
      </CardContent>
    </Card>
  );
}
