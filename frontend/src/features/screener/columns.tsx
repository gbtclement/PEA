import type { ColumnSpec as DataTableColumn } from "@/components/DataTable";
import { FavoriteButton } from "@/components/FavoriteButton";
import { ScoreGauge } from "@/components/ScoreGauge";
import { Sparkline } from "@/components/Sparkline";
import { EnvelopeBadges } from "@/features/explorer/EnvelopeBadges";
import type { ScreenerRow } from "@/lib/api/client";
import { currencyUnit, formatNumber, formatPct, formatPrice, formatRatioPct } from "@/lib/format";
import { cn } from "@/lib/utils";

function Change({ value }: { value: number | null }) {
  return (
    <span className={cn("font-medium", value != null && value > 0 && "text-up", value != null && value < 0 && "text-down")}>
      {formatPct(value)}
    </span>
  );
}

// Les valeurs absentes deviennent `undefined` pour rester en fin de liste dans les deux sens de tri.
const numeric = (key: keyof ScreenerRow) => ({
  accessorFn: (row: ScreenerRow) => (row[key] as number | null) ?? undefined,
  sortUndefined: "last" as const,
});

export type ColumnSpec = DataTableColumn<ScreenerRow>;

export function buildColumns(kind: "stock" | "etf"): ColumnSpec[] {
  const columns: ColumnSpec[] = [
    { id: "favorite", header: "", width: "36px", enableSorting: false,
      cell: ({ row }) => <FavoriteButton securityId={row.original.id} isFavorite={row.original.is_favorite} /> },
    { id: "name", accessorKey: "name", header: "Nom", width: "minmax(150px, 2fr)",
      // Tri « naturel » en français : 2CRSI avant A2A, 10X après 2CRSI, sans tenir compte des majuscules.
      sortingFn: (a, b) => a.original.name.localeCompare(b.original.name, "fr", { numeric: true, sensitivity: "base" }),
      cell: ({ row }) => (
        <div className="min-w-0">
          <div className="truncate font-medium">{row.original.name}</div>
          <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
            <span className="truncate">{row.original.symbol} · {row.original.market}</span>
            <EnvelopeBadges codes={row.original.envelopes} />
          </div>
        </div>
      ) },
    { id: "price", header: "Cours", width: "110px", align: "right", ...numeric("price"),
      cell: ({ row }) => (
        <span className="font-medium whitespace-nowrap">
          {row.original.price == null ? "—" : `${formatPrice(row.original.price)} ${currencyUnit(row.original.currency)}`}
        </span>
      ) },
    { id: "change_pct", header: "1 j", width: "80px", align: "right", ...numeric("change_pct"),
      cell: ({ row }) => <Change value={row.original.change_pct} /> },
    { id: "perf_1w", header: "1 sem", width: "80px", align: "right", ...numeric("perf_1w"),
      cell: ({ row }) => <Change value={row.original.perf_1w} /> },
    { id: "perf_1m", header: "1 mois", width: "80px", align: "right", ...numeric("perf_1m"),
      cell: ({ row }) => <Change value={row.original.perf_1m} /> },
    { id: "perf_1y", header: "1 an", width: "80px", align: "right", ...numeric("perf_1y"),
      cell: ({ row }) => <Change value={row.original.perf_1y} /> },
    { id: "score", header: "Score", width: "56px", align: "right", ...numeric("score"),
      cell: ({ row }) => <ScoreGauge score={row.original.score} size={36} /> },
  ];
  if (kind === "stock") {
    columns.push(
      { id: "pe", header: "PER", width: "60px", align: "right", ...numeric("pe"),
        cell: ({ row }) => formatNumber(row.original.pe, 1) },
      { id: "dividend_yield", header: "Rendement", width: "92px", align: "right", ...numeric("dividend_yield"),
        cell: ({ row }) => formatRatioPct(row.original.dividend_yield) },
    );
  }
  columns.push({ id: "trend", header: "3 mois", width: "88px", enableSorting: false,
    cell: ({ row }) => <Sparkline values={row.original.sparkline} /> });
  return columns;
}
