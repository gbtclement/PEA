import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { CounterOut } from "@/lib/api/client";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useOrderCounter } from "./api";

export function OrderCounterCard({ className }: { className?: string }) {
  const { data, isError } = useOrderCounter();
  return (
    <Card className={className}>
      <CardHeader><CardTitle className="text-base">Compteur d'ordres</CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm">
        {isError && <p className="text-muted-foreground">Compteur indisponible pour le moment.</p>}
        {!data && !isError && <Skeleton className="h-16 w-full" />}
        {data && <CounterBody counter={data} />}
      </CardContent>
    </Card>
  );
}

function CounterBody({ counter }: { counter: CounterOut }) {
  const { year, count, min_orders: min, remaining, expected_by_now: expected, behind, penalty_fee: penalty } = counter;
  const progress = min > 0 ? Math.min(100, (count / min) * 100) : 100;
  return (
    <>
      <p className="text-2xl font-semibold tabular-nums">{count}/{min} ordres en {year}</p>
      <div className="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={count} aria-valuemin={0}
           aria-valuemax={min} aria-label="Ordres passés cette année">
        <div className={cn("h-full rounded-full", remaining === 0 ? "bg-up" : behind ? "bg-amber-500" : "bg-primary")}
             style={{ width: `${progress}%` }} />
      </div>
      {remaining === 0 ? (
        <p className="font-medium text-up">Objectif atteint ✅ Pas de frais de non-respect cette année.</p>
      ) : (
        <p className="text-muted-foreground">Il en reste {remaining} d'ici le 31/12 pour éviter ≈ {formatPrice(penalty)} € de frais.</p>
      )}
      {behind && remaining > 0 && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-800">
          ⚠️ En retard sur le rythme : environ {Math.floor(expected)} ordres attendus à cette date.
        </p>
      )}
    </>
  );
}
