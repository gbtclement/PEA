import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FavoriteButton } from "@/components/FavoriteButton";
import { AskAiButton } from "@/features/assistant/AskAiButton";
import { useAccountKey } from "@/features/auth/useMe";
import { useEnvelopes } from "@/features/settings/useEnvelopes";
import { ScoreGauge } from "@/components/ScoreGauge";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkline } from "@/components/Sparkline";
import { apiGet, type TopItem } from "@/lib/api/client";
import { ENVELOPE_LABELS } from "@/lib/envelopes";
import { currencyUnit, formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

export function TopList() {
  const { filtering } = useEnvelopes();
  const account = useAccountKey();
  const { data, isPending, isError } = useQuery({
    queryKey: ["top", account],
    enabled: account !== undefined,
    queryFn: () => apiGet<TopItem[]>("/api/rankings/top", { limit: 10 }),
    refetchInterval: 60_000,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">🏆 Top 10 du moment</CardTitle>
        <p className="text-sm text-muted-foreground">
          Actions les mieux notées par le score mixte (technique + fondamentaux)
          {filtering.length ? `, parmi les titres compatibles avec vos enveloppes (${filtering.map((c) => ENVELOPE_LABELS[c]).join(", ")}).` : "."}
        </p>
      </CardHeader>
      <CardContent className="px-0">
        {isPending ? (
          <div className="space-y-3 px-6">{Array.from({ length: 10 }, (_, i) => <Skeleton key={i} className="h-20 w-full" />)}</div>
        ) : isError ? (
          <p role="alert" className="px-6 text-sm text-down">Impossible de charger le classement.</p>
        ) : data.length === 0 ? (
          <p className="px-6 text-sm text-muted-foreground">
            Le classement sera disponible une fois les données chargées (quelques minutes au premier démarrage).
          </p>
        ) : (
          <ol className="divide-y divide-border">
            {data.map((item, index) => (
              <li key={item.id} className="flex items-center gap-4 px-6 py-3">
                <span className="w-5 text-sm font-semibold text-muted-foreground">{index + 1}</span>
                <ScoreGauge score={item.score} />
                <div className="min-w-0 flex-1">
                  <Link to={`/titres/${item.id}`} className="font-medium hover:text-primary">
                    {item.name} <span className="text-xs font-normal text-muted-foreground">{item.symbol}</span>
                  </Link>
                  <ul className="mt-1 flex flex-wrap gap-1.5">
                    {item.reasons.map((reason) => (
                      <li key={reason} className="rounded-md bg-muted px-2 py-0.5 text-xs text-neutral-600">{reason}</li>
                    ))}
                  </ul>
                </div>
                <Sparkline values={item.sparkline} />
                <div className="w-24 text-right">
                  <p className="font-medium">{item.price == null ? "—" : `${formatPrice(item.price)} ${currencyUnit(item.currency)}`}</p>
                  <p className={cn("text-xs font-medium", (item.change_pct ?? 0) > 0 && "text-up", (item.change_pct ?? 0) < 0 && "text-down")}>
                    {formatPct(item.change_pct)}
                  </p>
                </div>
                <AskAiButton security={{ id: item.id, name: item.name }} />
                <FavoriteButton securityId={item.id} isFavorite={item.is_favorite} />
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
