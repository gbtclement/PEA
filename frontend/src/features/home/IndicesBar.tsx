import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkline } from "@/components/Sparkline";
import { apiGet, type HistoryOut, type StatusResponse } from "@/lib/api/client";
import { formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

function IndexCard({ index }: { index: StatusResponse["indices"][number] }) {
  const { data } = useQuery({
    queryKey: ["history", index.id, "1D"],
    queryFn: () => apiGet<HistoryOut>(`/api/securities/${index.id}/history`, { period: "1D" }),
    refetchInterval: 120_000,
  });
  const change = index.change_pct ?? 0;
  return (
    <Card className="flex flex-row items-center justify-between gap-4 px-5 py-4">
      <div>
        <p className="text-sm font-medium text-muted-foreground">{index.name}</p>
        <p className="mt-0.5 text-lg font-semibold">{formatPrice(index.price)}</p>
        <p className={cn("text-sm font-medium", change > 0 && "text-up", change < 0 && "text-down")}>{formatPct(index.change_pct)}</p>
      </div>
      <Sparkline values={(data?.bars ?? []).map((b) => b.close)} width={110} height={40} />
    </Card>
  );
}

export function IndicesBar() {
  const { data } = useQuery({ queryKey: ["status"], queryFn: () => apiGet<StatusResponse>("/api/status"), refetchInterval: 60_000 });
  // Place réservée pendant le chargement : sans elle, toute la page descend quand les indices arrivent.
  if (!data) return <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-[102px] rounded-xl" />)}</div>;
  if (!data.indices.length) return null;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
      {data.indices.map((index) => <IndexCard key={index.id} index={index} />)}
    </div>
  );
}
