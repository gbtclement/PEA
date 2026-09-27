import { useQuery } from "@tanstack/react-query";
import { apiGet, type ForecastList, type SignalStats, type TrackRecord } from "@/lib/api/client";
import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

export const HORIZONS = [
  { key: "1d", label: "1 jour", sessions: "1 séance" },
  { key: "1w", label: "1 semaine", sessions: "5 séances" },
  { key: "1m", label: "1 mois", sessions: "21 séances" },
] as const;
export type HorizonKey = (typeof HORIZONS)[number]["key"];

export const useForecasts = () =>
  useQuery({ queryKey: ["forecasts"], queryFn: () => apiGet<ForecastList>("/api/forecasts"), staleTime: 300_000 });
export const useSignalStats = () =>
  useQuery({ queryKey: ["forecasts", "signals"], queryFn: () => apiGet<SignalStats>("/api/forecasts/signals"), staleTime: 300_000 });
export const useTrackRecord = () =>
  useQuery({ queryKey: ["forecasts", "track-record"], queryFn: () => apiGet<TrackRecord>("/api/forecasts/track-record"), staleTime: 300_000 });

/** Fraction → pourcentage signé : 0,009 → « +0,90 % ». */
export const signedPct = (fraction: number | null | undefined) => formatPct(fraction == null ? null : fraction * 100);
/** Fraction → pourcentage arrondi : 0,564 → « 56 % ». */
export const roundPct = (fraction: number | null | undefined) => (fraction == null ? "—" : `${Math.round(fraction * 100)} %`);

export const tone = (value: number | null | undefined) => cn(value != null && value > 0 && "text-up", value != null && value < 0 && "text-down");

const RELIABILITY = {
  elevee: { label: "Fiabilité élevée", short: "élevée", dot: "bg-up", badge: "bg-green-50 text-green-800 ring-green-200" },
  moyenne: { label: "Fiabilité moyenne", short: "moyenne", dot: "bg-amber-500", badge: "bg-amber-50 text-amber-800 ring-amber-200" },
  faible: { label: "Fiabilité faible", short: "faible", dot: "bg-neutral-400", badge: "bg-neutral-100 text-neutral-700 ring-neutral-200" },
} as const;
export const RELIABILITY_ORDER = { faible: 0, moyenne: 1, elevee: 2 } as const;

const reliabilityOf = (value: string) => RELIABILITY[value as keyof typeof RELIABILITY] ?? RELIABILITY.faible;

export function ReliabilityDot({ value }: { value: string }) {
  const r = reliabilityOf(value);
  return <span className={cn("inline-block size-2 shrink-0 rounded-full", r.dot)} title={r.label}><span className="sr-only">{r.label}</span></span>;
}

export function ReliabilityBadge({ value }: { value: string }) {
  const r = reliabilityOf(value);
  return <span className={cn("rounded-md px-1.5 py-0.5 text-xs font-medium ring-1", r.badge)}>{r.short}</span>;
}

export function ReliabilityLegend() {
  return (
    <p className="flex items-center gap-3 text-xs text-muted-foreground">
      Fiabilité statistique :
      {(["elevee", "moyenne", "faible"] as const).map((key) => (
        <span key={key} className="inline-flex items-center gap-1"><ReliabilityDot value={key} />{RELIABILITY[key].short}</span>
      ))}
    </p>
  );
}

export function SignalChip({ label, bullish }: { label: string; bullish: boolean }) {
  return (
    <span className={cn("rounded-md px-1.5 py-0.5 text-xs whitespace-nowrap", bullish ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800")}>
      {bullish ? "↗" : "↘"} {label}
    </span>
  );
}

export function FirstRunNotice() {
  return (
    <p className="p-6 text-sm text-muted-foreground">
      Premier calcul en cours : les statistiques et les prévisions apparaîtront dans quelques minutes, une fois l'historique des cours chargé.
    </p>
  );
}
