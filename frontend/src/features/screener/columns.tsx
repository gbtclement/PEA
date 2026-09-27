import type { ColumnDef } from "@tanstack/react-table";
import { FavoriteButton } from "@/components/FavoriteButton";
import { ScoreGauge } from "@/components/ScoreGauge";
import { Sparkline } from "@/components/Sparkline";
import { EligibilityBadge } from "@/features/explorer/EligibilityBadge";
import type { ScreenerRow } from "@/lib/api/client";
import { formatNumber, formatPct, formatPrice, formatRatioPct } from "@/lib/format";
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

export type ColumnSpec = ColumnDef<ScreenerRow> & { width: string; align?: "right" };

export function buildColumns(kind: "stock" | "etf"): ColumnSpec[] {
  const columns: ColumnSpec[] = [
    { id: "favorite", header: "", width: "40px", enableSorting: false,
      cell: ({ row }) => <FavoriteButton securityId={row.original.id} isFavorite={row.original.is_favorite} /> },
    { id: "name", accessorKey: "name", header: "Nom", width: "minmax(180px, 2fr)",
      cell: ({ row }) => (
        <div className="min-w-0">
          <div className="truncate font-medium">{row.original.name}</div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {row.original.symbol} · {row.original.market}
            {row.original.eligibility !== "eligible" && <EligibilityBadge status={row.original.eligibility} />}
          </div>
        </div>
      ) },
    { id: "price", header: "Cours", width: "80px", align: "right", ...numeric("price"),
      cell: ({ row }) => <span className="font-medium">{formatPrice(row.original.price)}</span> },
    { id: "change_pct", header: "1 j", width: "72px", align: "right", ...numeric("change_pct"),
      cell: ({ row }) => <Change value={row.original.change_pct} /> },
    { id: "perf_1w", header: "1 sem", width: "72px", align: "right", ...numeric("perf_1w"),
      cell: ({ row }) => <Change value={row.original.perf_1w} /> },
    { id: "perf_1m", header: "1 mois", width: "72px", align: "right", ...numeric("perf_1m"),
      cell: ({ row }) => <Change value={row.original.perf_1m} /> },
    { id: "perf_1y", header: "1 an", width: "72px", align: "right", ...numeric("perf_1y"),
      cell: ({ row }) => <Change value={row.original.perf_1y} /> },
    { id: "score", header: "Score", width: "60px", align: "right", ...numeric("score"),
      cell: ({ row }) => <ScoreGauge score={row.original.score} size={36} /> },
  ];
  if (kind === "stock") {
    columns.push(
      { id: "pe", header: "PER", width: "60px", align: "right", ...numeric("pe"),
        cell: ({ row }) => formatNumber(row.original.pe, 1) },
      { id: "dividend_yield", header: "Rendement", width: "88px", align: "right", ...numeric("dividend_yield"),
        cell: ({ row }) => formatRatioPct(row.original.dividend_yield) },
    );
  }
  columns.push({ id: "trend", header: "3 mois", width: "90px", enableSorting: false,
    cell: ({ row }) => <Sparkline values={row.original.sparkline} /> });
  return columns;
}
