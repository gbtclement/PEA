import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { FavoriteButton } from "@/components/FavoriteButton";
import { AskAiButton } from "@/features/assistant/AskAiButton";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EligibilityBadge } from "@/features/explorer/EligibilityBadge";
import { OrderDialog } from "@/features/portfolio/OrderDialog";
import { ApiError, apiGet, type SecurityDetail } from "@/lib/api/client";
import { formatDateTime, formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { FundamentalsCard } from "./FundamentalsCard";
import { NewsCard } from "./NewsCard";
import { PriceChartPanel } from "./PriceChartPanel";
import { ScoreCard } from "./ScoreCard";
import { SimulatorCard } from "./SimulatorCard";

export function SecurityPage() {
  const id = Number(useParams().id);
  const [ordering, setOrdering] = useState(false);
  const { data, isPending, error } = useQuery({
    queryKey: ["security", id],
    queryFn: () => apiGet<SecurityDetail>(`/api/securities/${id}`),
    refetchInterval: 60_000,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !data) {
    return (
      <section className="py-20 text-center">
        <p className="text-lg font-medium">{error instanceof ApiError && error.status === 404 ? "Titre introuvable." : "Impossible de charger ce titre."}</p>
        <Link to="/explorer" className="mt-2 inline-block text-sm text-primary">Retour à l'explorateur</Link>
      </section>
    );
  }
  const change = data.change_pct ?? 0;
  return (
    <section className="space-y-6">
      <header className="flex items-start justify-between gap-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{data.name}</h1>
            <FavoriteButton securityId={data.id} isFavorite={data.is_favorite} />
            {data.kind !== "index" && (
              <>
                <Button variant="outline" size="sm" className="ml-2" onClick={() => setOrdering(true)}>+ J'ai acheté</Button>
                <AskAiButton security={{ id: data.id, name: data.name }} label />
              </>
            )}
          </div>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            {data.symbol} · {data.market}{data.isin && ` · ${data.isin}`} <EligibilityBadge status={data.eligibility} />
          </p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-semibold">{formatPrice(data.price)} {data.currency === "EUR" ? "€" : data.currency}</p>
          <p className={cn("text-sm font-medium", change > 0 && "text-up", change < 0 && "text-down")}>{formatPct(data.change_pct)} aujourd'hui</p>
          <p className="text-xs text-muted-foreground">Mis à jour {formatDateTime(data.as_of)}</p>
        </div>
      </header>
      <PriceChartPanel securityId={data.id} />
      <div className="grid grid-cols-2 gap-6">
        <ScoreCard detail={data} />
        <FundamentalsCard detail={data} />
        <SimulatorCard securityId={data.id} />
        <NewsCard securityId={data.id} />
      </div>
      <OrderDialog open={ordering} onOpenChange={setOrdering} security={{ id: data.id, name: data.name, symbol: data.symbol }}
                   price={data.currency === "EUR" ? data.price : null} />
    </section>
  );
}
