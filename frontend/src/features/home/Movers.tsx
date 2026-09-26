import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type Movers as MoversData, type ScreenerRow } from "@/lib/api/client";
import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

function MoverList({ title, rows }: { title: string; rows: ScreenerRow[] }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <ul className="space-y-1.5">
        {rows.map((row) => (
          <li key={row.id} className="flex items-center justify-between text-sm">
            <Link to={`/titres/${row.id}`} className="truncate hover:text-primary">{row.name}</Link>
            <span className={cn("font-medium", (row.change_pct ?? 0) >= 0 ? "text-up" : "text-down")}>{formatPct(row.change_pct)}</span>
          </li>
        ))}
        {rows.length === 0 && <li className="text-sm text-muted-foreground">—</li>}
      </ul>
    </div>
  );
}

export function Movers() {
  const { data } = useQuery({ queryKey: ["movers"], queryFn: () => apiGet<MoversData>("/api/rankings/movers", { limit: 5 }), refetchInterval: 60_000 });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">🔥 Hausses et baisses du jour</CardTitle></CardHeader>
      <CardContent className="space-y-5">
        <MoverList title="Plus fortes hausses" rows={data?.gainers ?? []} />
        <MoverList title="Plus fortes baisses" rows={data?.losers ?? []} />
      </CardContent>
    </Card>
  );
}
