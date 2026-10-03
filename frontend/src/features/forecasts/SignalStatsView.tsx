import { useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { SignalStat, SignalStatsRow } from "@/lib/api/client";
import { formatNumber, formatRatioPct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { FirstRunNotice, HORIZONS, ReliabilityBadge, roundPct, signedPct, tone, useSignalStats, type HorizonKey } from "./shared";

type SignalRow = SignalStatsRow;
type Metric = "n" | "hit_rate" | "mean" | "median" | "after_fees" | "beat_index";

const METRICS: { key: Metric; label: string; hint: string }[] = [
  { key: "n", label: "Cas", hint: "Nombre de fois où le signal est apparu sur 5 ans (actions liquides)" },
  { key: "hit_rate", label: "En hausse", hint: "Part des cas où le cours a monté à l'horizon choisi" },
  { key: "mean", label: "Gain moyen", hint: "Variation moyenne du cours à l'horizon choisi, avant frais" },
  { key: "median", label: "Gain médian", hint: "La moitié des cas a fait mieux, l'autre moitié moins bien" },
  { key: "after_fees", label: "Après frais", hint: "Gain moyen moins les frais d'un achat puis d'une revente" },
  { key: "beat_index", label: "Bat le CAC 40", hint: "Part des cas qui ont fait mieux que le CAC 40 sur la même période" },
];

const value = (stat: SignalStat, metric: Metric, cost: number) => (metric === "after_fees" ? stat.mean - cost : stat[metric]);

type SortKey = Metric | "label" | "reliability";
type Sort = { key: SortKey; desc: boolean };
const RELIABILITY_RANK: Record<string, number> = { faible: 0, moyenne: 1, elevee: 2 };

/** Ordre croissant de deux signaux ; ceux sans statistique à cet horizon restent en bas quel que soit le sens. */
function compare(a: SignalRow, b: SignalRow, horizon: HorizonKey, sort: Sort, cost: number): number {
  if (sort.key === "label") return a.label.localeCompare(b.label, "fr", { sensitivity: "base" });
  const sa = a.horizons[horizon];
  const sb = b.horizons[horizon];
  if (!sa || !sb) return 0;
  return sort.key === "reliability"
    ? (RELIABILITY_RANK[sa.reliability] ?? 0) - (RELIABILITY_RANK[sb.reliability] ?? 0)
    : value(sa, sort.key, cost) - value(sb, sort.key, cost);
}

function SortButton({ label, sortKey, sort, onSort, className }: {
  label: string; sortKey: SortKey; sort: Sort; onSort: (key: SortKey) => void; className?: string;
}) {
  const active = sort.key === sortKey;
  return (
    <button type="button" onClick={() => onSort(sortKey)}
            className={cn("inline-flex items-center gap-1 whitespace-nowrap hover:text-foreground max-md:min-h-11", active && "text-foreground", className)}>
      {label}
      {active && (sort.desc ? <ArrowDown className="size-3" aria-hidden /> : <ArrowUp className="size-3" aria-hidden />)}
    </button>
  );
}

const ariaSort = (sort: Sort, key: SortKey) => (sort.key === key ? (sort.desc ? "descending" : "ascending") : undefined);

function Cells({ stat, cost, reference = false }: { stat: SignalStat | null | undefined; cost: number; reference?: boolean }) {
  if (!stat) {
    return <>{METRICS.map((m) => <td key={m.key} className="px-3 py-2 text-right text-muted-foreground">—</td>)}<td className="px-3 py-2 text-right text-muted-foreground">—</td></>;
  }
  return (
    <>
      <td className="px-3 py-2 text-right">{formatNumber(stat.n, 0)}</td>
      <td className="px-3 py-2 text-right">{roundPct(stat.hit_rate)}</td>
      <td className={cn("px-3 py-2 text-right font-medium", tone(stat.mean))}>{signedPct(stat.mean)}</td>
      <td className={cn("px-3 py-2 text-right", tone(stat.median))}>{signedPct(stat.median)}</td>
      <td className={cn("px-3 py-2 text-right", tone(stat.mean - cost))}>{signedPct(stat.mean - cost)}</td>
      <td className="px-3 py-2 text-right">{roundPct(stat.beat_index)}</td>
      <td className="px-3 py-2 text-right">{reference ? <span className="text-muted-foreground">—</span> : <ReliabilityBadge value={stat.reliability} />}</td>
    </>
  );
}

export function SignalStatsView() {
  const { data, isPending, isError } = useSignalStats();
  const [horizon, setHorizon] = useState<HorizonKey>("1w");
  const [sort, setSort] = useState<Sort>({ key: "mean", desc: true });
  // Même colonne : on inverse le sens. Nouvelle colonne : le signal par ordre alphabétique, les chiffres du plus grand au plus petit.
  const onSort = (key: SortKey) => setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: key !== "label" }));

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (isError) return <p role="alert" className="text-sm text-down">Impossible de charger les statistiques.</p>;
  if (!data.as_of) return <Card className="py-0"><FirstRunNotice /></Card>;

  const cost = data.round_trip_cost ?? 0;
  const rows = [...data.signals].sort((a, b) => {
    if (sort.key !== "label" && (!a.horizons[horizon] || !b.horizons[horizon])) {
      return a.horizons[horizon] ? -1 : b.horizons[horizon] ? 1 : 0;
    }
    const order = compare(a, b, horizon, sort, cost);
    return sort.desc ? -order : order;
  });
  const horizonLabel = HORIZONS.find((h) => h.key === horizon)!;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Ce qui a suivi chaque signal au bout de :</span>
        {HORIZONS.map((h) => (
          <Button key={h.key} size="sm" variant={h.key === horizon ? "default" : "outline"} aria-pressed={h.key === horizon}
                  onClick={() => setHorizon(h.key)}>{h.label}</Button>
        ))}
      </div>
      <Card className="overflow-hidden py-0">
        <div className="overflow-x-auto">
          <table aria-label="Statistiques des signaux" className="w-full min-w-[560px] text-sm tabular-nums">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground">
                <th scope="col" className="px-3 py-2 text-left font-medium" aria-sort={ariaSort(sort, "label")}>
                  <SortButton label="Signal" sortKey="label" sort={sort} onSort={onSort} />
                </th>
                {METRICS.map((m) => (
                  <th key={m.key} scope="col" className="px-3 py-2 text-right font-medium" title={m.hint} aria-sort={ariaSort(sort, m.key)}>
                    <SortButton label={m.label} sortKey={m.key} sort={sort} onSort={onSort} />
                  </th>
                ))}
                <th scope="col" className="px-3 py-2 text-right font-medium" aria-sort={ariaSort(sort, "reliability")}>
                  <SortButton label="Fiabilité" sortKey="reliability" sort={sort} onSort={onSort} />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <tr className="bg-muted/60">
                <th scope="row" className="px-3 py-2 text-left font-medium">
                  Toutes les actions (référence)
                  <p className="text-xs font-normal text-muted-foreground">N'importe quelle action liquide, n'importe quel jour : le point de comparaison.</p>
                </th>
                <Cells stat={data.baseline[horizon]} cost={cost} reference />
              </tr>
              {rows.map((row) => (
                <tr key={row.key}>
                  <th scope="row" className="max-w-80 px-3 py-2 text-left font-normal">
                    <span className="font-medium">
                      <span className={row.bullish ? "text-up" : "text-down"} aria-label={row.bullish ? "haussier" : "baissier"}>{row.bullish ? "↗" : "↘"}</span> {row.label}
                    </span>
                    <p className="text-xs text-muted-foreground">{row.description}</p>
                  </th>
                  <Cells stat={row.horizons[horizon]} cost={cost} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="text-xs text-muted-foreground">
        Horizon : {horizonLabel.label} ({horizonLabel.sessions}). Frais aller-retour comptés : {formatRatioPct(cost)} (ordre de 500 €).
        La flèche indique l'intuition courante ; les chiffres disent ce qui s'est vraiment passé sur 5 ans. Fiabilité « élevée » : l'écart
        avec le CAC 40 est trop régulier pour être dû au hasard seul — ce qui ne garantit pas qu'il se répétera.
      </p>
    </div>
  );
}
