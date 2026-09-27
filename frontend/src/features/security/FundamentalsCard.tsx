import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SecurityDetail } from "@/lib/api/client";
import { formatCompactEur, formatNumber, formatRatioPct } from "@/lib/format";

export function FundamentalsCard({ detail }: { detail: SecurityDetail }) {
  const f = detail.fundamentals;
  const rows: [string, string][] = f ? [
    ["PER", formatNumber(f.pe, 1)],
    ["Bénéfice par action", formatNumber(f.eps, 2)],
    ["Croissance des bénéfices", formatRatioPct(f.earnings_growth)],
    ["Croissance du chiffre d'affaires", formatRatioPct(f.revenue_growth)],
    ["Dette / capitaux propres", formatNumber(f.debt_to_equity, 2)],
    ["Marge nette", formatRatioPct(f.profit_margin)],
    ["Rendement du dividende", formatRatioPct(f.dividend_yield)],
    ["Capitalisation", f.currency && f.currency !== "EUR" ? `${formatNumber(f.market_cap, 0)} ${f.currency}` : formatCompactEur(f.market_cap)],
  ] : [];
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Données fondamentales</CardTitle></CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-muted-foreground">{detail.sector ?? "Secteur inconnu"} · {detail.industry ?? "—"}</p>
        {!f ? (
          <p className="text-sm text-muted-foreground">Données fondamentales indisponibles pour ce titre.</p>
        ) : (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {rows.map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-3 border-b border-border py-1">
                <dt className="text-muted-foreground">{label}</dt><dd className="shrink-0 whitespace-nowrap font-medium tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
