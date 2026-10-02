import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import type { SortingState } from "@tanstack/react-table";
import { DataTable, type ColumnSpec } from "@/components/DataTable";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EnvelopeBadges } from "@/features/explorer/EnvelopeBadges";
import { useEnvelopes } from "@/features/settings/useEnvelopes";
import type { ForecastRow } from "@/lib/api/client";
import { formatPrice } from "@/lib/format";
import {
  FirstRunNotice, HORIZONS, RELIABILITY_ORDER, ReliabilityDot, ReliabilityLegend, SignalChip, roundPct, signedPct, tone,
  useForecasts, type HorizonKey,
} from "./shared";

const MAX_CHIPS = 2;

function horizonColumn(key: HorizonKey, label: string): ColumnSpec<ForecastRow> {
  return {
    id: key, header: label, width: "112px", align: "right", sortDescFirst: true, sortUndefined: "last",
    accessorFn: (row) => row.horizons[key]?.expected_return ?? undefined,
    cell: ({ row }) => {
      const h = row.original.horizons[key];
      if (!h) return <span className="text-muted-foreground">—</span>;
      return (
        <div className="text-right leading-tight">
          <div className={`font-medium ${tone(h.expected_return)}`}>{signedPct(h.expected_return)}</div>
          <div className="flex items-center justify-end gap-1 text-xs text-muted-foreground">
            <ReliabilityDot value={h.reliability} /><span>{roundPct(h.prob_up)} de hausse</span>
          </div>
        </div>
      );
    },
  };
}

const COLUMNS: ColumnSpec<ForecastRow>[] = [
  { id: "name", header: "Titre", width: "minmax(170px, 2fr)", accessorFn: (row) => row.security.name,
    sortingFn: (a, b) => a.original.security.name.localeCompare(b.original.security.name, "fr", { numeric: true, sensitivity: "base" }),
    cell: ({ row }) => (
      <div className="min-w-0">
        <div className="truncate font-medium">{row.original.security.name}</div>
        <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
          <span className="truncate">{row.original.security.symbol} · {row.original.security.market}</span>
          <EnvelopeBadges codes={row.original.security.envelopes} />
        </div>
      </div>
    ) },
  { id: "price", header: "Cours", width: "76px", align: "right", sortDescFirst: true, sortUndefined: "last",
    accessorFn: (row) => row.security.price ?? undefined,
    cell: ({ row }) => <span className="font-medium">{formatPrice(row.original.security.price)}</span> },
  { id: "signals", header: "Signaux du jour", width: "minmax(170px, 1.6fr)", enableSorting: false,
    cell: ({ row }) => {
      const signals = row.original.signals;
      return (
        <div className="flex items-center gap-1 overflow-hidden" title={signals.map((s) => s.label).join(" · ")}>
          {signals.slice(0, MAX_CHIPS).map((s) => <SignalChip key={s.key} label={s.label} bullish={s.bullish} />)}
          {signals.length > MAX_CHIPS && <span className="text-xs text-muted-foreground">+{signals.length - MAX_CHIPS}</span>}
        </div>
      );
    } },
  ...HORIZONS.map((h) => horizonColumn(h.key, h.label)),
];

type Direction = "tous" | "hausse" | "baisse";
type MinReliability = "faible" | "moyenne" | "elevee";

export function PredictionsView() {
  const navigate = useNavigate();
  const { data, isPending, isError } = useForecasts();
  const [sorting, setSorting] = useState<SortingState>([{ id: "1w", desc: true }]);
  const [search, setSearch] = useState("");
  const { filtering } = useEnvelopes();
  const [mineOnly, setMineOnly] = useState<boolean | null>(null); // null = défaut : coché si des enveloppes sont choisies
  const onlyMine = filtering.length > 0 && (mineOnly ?? true);
  const [direction, setDirection] = useState<Direction>("tous");
  const [minReliability, setMinReliability] = useState<MinReliability>("faible");
  // Sens et fiabilité s'appliquent à l'horizon trié (1 semaine si le tri porte sur le nom).
  const horizon = (HORIZONS.find((h) => h.key === sorting[0]?.id)?.key ?? "1w") as HorizonKey;

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data?.rows ?? []).filter((row) => {
      const h = row.horizons[horizon];
      if (onlyMine && !row.security.envelopes.some((code) => filtering.includes(code))) return false;
      if (q && !`${row.security.name} ${row.security.symbol}`.toLowerCase().includes(q)) return false;
      if (direction !== "tous" && (!h || (direction === "hausse" ? h.expected_return <= 0 : h.expected_return >= 0))) return false;
      if (minReliability !== "faible" && (!h || RELIABILITY_ORDER[h.reliability as MinReliability] < RELIABILITY_ORDER[minReliability])) return false;
      return true;
    });
  }, [data, search, onlyMine, filtering, direction, minReliability, horizon]);

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (isError) return <p role="alert" className="text-sm text-down">Impossible de charger les prévisions.</p>;
  if (!data.as_of) return <Card className="py-0"><FirstRunNotice /></Card>;

  const horizonLabel = HORIZONS.find((h) => h.key === horizon)!.label;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Input type="search" aria-label="Rechercher" placeholder="Nom ou ticker…" className="w-56 bg-white" value={search}
               onChange={(e) => setSearch(e.target.value)} />
        {filtering.length > 0 && (
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={onlyMine} onChange={(e) => setMineOnly(e.target.checked)} />
            Mes enveloppes uniquement
          </label>
        )}
        <select aria-label="Sens" value={direction} onChange={(e) => setDirection(e.target.value as Direction)}
                className="h-8 rounded-lg border border-input bg-white px-2">
          <option value="tous">Hausse et baisse ({horizonLabel})</option>
          <option value="hausse">Hausse attendue ({horizonLabel})</option>
          <option value="baisse">Baisse attendue ({horizonLabel})</option>
        </select>
        <select aria-label="Fiabilité minimale" value={minReliability} onChange={(e) => setMinReliability(e.target.value as MinReliability)}
                className="h-8 rounded-lg border border-input bg-white px-2">
          <option value="faible">Toute fiabilité</option>
          <option value="moyenne">Fiabilité moyenne ou élevée</option>
          <option value="elevee">Fiabilité élevée</option>
        </select>
        <span className="ml-auto text-muted-foreground">{rows.length} titre{rows.length > 1 ? "s" : ""} avec un signal</span>
      </div>
      <ReliabilityLegend />
      <Card className="overflow-hidden py-0">
        {rows.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">Aucun titre ne correspond à ces filtres.</p>
        ) : (
          <DataTable rows={rows} columns={COLUMNS} sorting={sorting} onSortingChange={setSorting}
                     getRowId={(row) => String(row.security.id)} onRowClick={(row) => navigate(`/titres/${row.security.id}`)}
                     heightClass="h-[calc(100vh-390px)] min-h-[360px]" />
        )}
      </Card>
      <p className="text-xs text-muted-foreground">
        Gain attendu : moyenne de ce qui a suivi les mêmes signaux sur 5 ans, avant frais ; « de hausse » : part des cas où le cours a monté.
        Cliquez sur un titre pour voir sa fiche.
      </p>
    </div>
  );
}
