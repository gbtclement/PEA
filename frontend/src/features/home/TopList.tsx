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
              // Téléphone : grille (rang, jauge, nom, cours ; puis raisons sur toute la largeur ; puis boutons).
              // Ordinateur (md) : une seule rangée, comme avant.
              <li key={item.id}
                  className="grid grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 px-4 py-3 md:flex md:gap-4 md:px-6">
                <span className="w-5 text-sm font-semibold text-muted-foreground">{index + 1}</span>
                <ScoreGauge score={item.score} />
                <div className="contents md:block md:min-w-0 md:flex-1">
                  <Link to={`/titres/${item.id}`} className="min-w-0 font-medium hover:text-primary max-md:inline-flex max-md:min-h-11 max-md:flex-wrap max-md:items-center max-md:gap-x-1">
                    {item.name} <span className="text-xs font-normal text-muted-foreground">{item.symbol}</span>
                  </Link>
                  <ul className="col-span-full row-start-2 flex flex-wrap gap-1.5 md:mt-1">
                    {item.reasons.map((reason) => (
                      <li key={reason} className="rounded-md bg-muted px-2 py-0.5 text-xs text-neutral-600">{reason}</li>
                    ))}
                  </ul>
                </div>
                <div className="hidden md:block"><Sparkline values={item.sparkline} /></div>
                <div className="col-start-4 row-start-1 text-right md:w-24">
                  <p className="font-medium">{item.price == null ? "—" : `${formatPrice(item.price)} ${currencyUnit(item.currency)}`}</p>
                  <p className={cn("text-xs font-medium", (item.change_pct ?? 0) > 0 && "text-up", (item.change_pct ?? 0) < 0 && "text-down")}>
                    {formatPct(item.change_pct)}
                  </p>
                </div>
                <div className="col-span-full flex justify-end gap-1 md:contents">
                  <AskAiButton security={{ id: item.id, name: item.name }} />
                  <FavoriteButton securityId={item.id} isFavorite={item.is_favorite} />
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
