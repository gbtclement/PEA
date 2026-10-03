import { Link } from "react-router";
import type { PositionOut } from "@/lib/api/client";
import { formatPct, formatPrice, formatRatioPct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useIsMobile } from "@/lib/useIsMobile";

const TH = "px-3 py-2 text-right text-xs font-medium text-muted-foreground";
const TD = "px-3 py-2 text-right tabular-nums";

export function PositionsTable({ positions }: { positions: PositionOut[] }) {
  if (useIsMobile()) return <PositionCards positions={positions} />;
  return (
    <table className="w-full text-sm">
      <thead className="border-b border-border">
        <tr>
          <th className={cn(TH, "text-left")}>Titre</th>
          <th className={TH}>Quantité</th>
          <th className={TH} title="Prix de revient unitaire, frais d'achat inclus">PRU</th>
          <th className={TH}>Cours</th>
          <th className={TH}>Valeur</th>
          <th className={TH}>+/- value</th>
          <th className={TH}>Poids</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {positions.map((p) => (
          <tr key={p.security_id} className="hover:bg-muted/50">
            <td className="px-3 py-2">
              <Link to={`/titres/${p.security_id}`} className="font-medium hover:text-primary">{p.name}</Link>
              <span className="ml-2 text-xs text-muted-foreground">{p.symbol}</span>
            </td>
            <td className={TD}>{p.quantity}</td>
            <td className={TD}>{formatPrice(p.avg_cost)} €</td>
            <td className={TD}>
              {p.price == null ? "—" : `${formatPrice(p.price)} €`}
              {p.change_pct != null && (
                <span className={cn("ml-1 text-xs", p.change_pct >= 0 ? "text-up" : "text-down")}>{formatPct(p.change_pct)}</span>
              )}
            </td>
            <td className={TD}>{formatPrice(p.value)} €</td>
            <td className={cn(TD, p.gain > 0 && "text-up", p.gain < 0 && "text-down")}>
              {p.gain > 0 ? "+" : ""}{formatPrice(p.gain)} € <span className="text-xs">({formatPct(p.gain_pct)})</span>
            </td>
            <td className={TD}>{formatRatioPct(p.weight)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Téléphone : une carte par position ; le PRU est expliqué en clair (pas d'infobulle au survol). */
function PositionCards({ positions }: { positions: PositionOut[] }) {
  return (
    <ul aria-label="Positions" className="space-y-2">
      {positions.map((p) => (
        <li key={p.security_id} className="rounded-xl border border-border p-3 text-sm">
          <Link to={`/titres/${p.security_id}`} className="font-medium">{p.name}</Link>
          <span className="ml-2 text-xs text-muted-foreground">{p.symbol}</span>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 tabular-nums">
            <dt className="text-muted-foreground">Quantité</dt><dd className="text-right">{p.quantity}</dd>
            <dt className="text-muted-foreground">PRU (frais inclus)</dt><dd className="text-right">{formatPrice(p.avg_cost)} €</dd>
            <dt className="text-muted-foreground">Cours</dt>
            <dd className="text-right">
              {p.price == null ? "—" : `${formatPrice(p.price)} €`}
              {p.change_pct != null && (
                <span className={cn("ml-1 text-xs", p.change_pct >= 0 ? "text-up" : "text-down")}>{formatPct(p.change_pct)}</span>
              )}
            </dd>
            <dt className="text-muted-foreground">Valeur</dt><dd className="text-right">{formatPrice(p.value)} €</dd>
            <dt className="text-muted-foreground">+/- value</dt>
            <dd className={cn("text-right", p.gain > 0 && "text-up", p.gain < 0 && "text-down")}>
              {p.gain > 0 ? "+" : ""}{formatPrice(p.gain)} € <span className="text-xs">({formatPct(p.gain_pct)})</span>
            </dd>
            <dt className="text-muted-foreground">Poids</dt><dd className="text-right">{formatRatioPct(p.weight)}</dd>
          </dl>
        </li>
      ))}
    </ul>
  );
}
