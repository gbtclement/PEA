import { Link } from "react-router";
import { FavoriteButton } from "@/components/FavoriteButton";
import { EnvelopeBadges } from "@/features/explorer/EnvelopeBadges";
import type { ScreenerRow } from "@/lib/api/client";
import { currencyUnit, formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Ligne de l'Explorer sur téléphone : tout tient dans 328 px, un nom long est tronqué. */
export function ScreenerCard({ row }: { row: ScreenerRow }) {
  const change = row.change_pct ?? 0;
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-card p-3">
      <Link to={`/titres/${row.id}`} className="min-w-0 flex-1">
        <p className="truncate font-medium">{row.name}</p>
        <p className="truncate text-xs text-muted-foreground">{row.symbol} · {row.market}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm tabular-nums">
          <span className="font-medium whitespace-nowrap">
            {row.price == null ? "—" : `${formatPrice(row.price)} ${currencyUnit(row.currency)}`}
          </span>
          <span className={cn("whitespace-nowrap", change > 0 && "text-up", change < 0 && "text-down")}>{formatPct(row.change_pct)}</span>
          <EnvelopeBadges codes={row.envelopes} />
        </div>
      </Link>
      <div className="flex flex-col items-end gap-1">
        {row.score != null && (
          <span className="flex flex-col items-center rounded-md bg-muted px-2 py-0.5 leading-tight">
            <span className="text-[10px] text-muted-foreground">Score</span>
            <span className="text-sm font-semibold tabular-nums">{Math.round(row.score)}</span>
          </span>
        )}
        <FavoriteButton securityId={row.id} isFavorite={row.is_favorite} />
      </div>
    </div>
  );
}
