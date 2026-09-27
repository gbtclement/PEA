import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { HORIZONS, ReliabilityBadge, SignalChip, roundPct, signedPct, tone } from "@/features/forecasts/shared";
import { apiGet, type SecurityForecast } from "@/lib/api/client";

export function ForecastCard({ securityId }: { securityId: number }) {
  const { data, isPending } = useQuery({
    queryKey: ["forecast", securityId],
    queryFn: () => apiGet<SecurityForecast>(`/api/securities/${securityId}/forecast`),
    staleTime: 300_000,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Prévisions court terme</CardTitle>
        <p className="text-sm text-muted-foreground">
          Estimation statistique, pas une certitude ni un conseil : ce qui a suivi les mêmes signaux sur 5 ans, avant frais.
        </p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {isPending ? <p className="text-muted-foreground">Chargement…</p> : !data?.as_of ? (
          <p className="text-muted-foreground">Premier calcul en cours.</p>
        ) : data.signals.length === 0 ? (
          <p className="text-muted-foreground">Aucun signal actif aujourd'hui.</p>
        ) : (
          <>
            <div className="flex flex-wrap gap-1.5">
              {data.signals.map((s) => <SignalChip key={s.key} label={s.label} bullish={s.bullish} />)}
            </div>
            <dl className="grid grid-cols-3 gap-3">
              {HORIZONS.map((h) => {
                const f = data.horizons[h.key];
                return (
                  <div key={h.key} className="rounded-lg bg-muted p-3">
                    <dt className="text-xs text-muted-foreground">Dans {h.label}</dt>
                    {f ? (
                      <dd className="space-y-1">
                        <p className={`text-lg font-semibold tabular-nums ${tone(f.expected_return)}`}>{signedPct(f.expected_return)}</p>
                        <p className="text-xs text-muted-foreground">{roundPct(f.prob_up)} de hausse</p>
                        <p className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                          <ReliabilityBadge value={f.reliability} /> {f.rank}e du jour
                        </p>
                      </dd>
                    ) : <dd className="text-muted-foreground">—</dd>}
                  </div>
                );
              })}
            </dl>
          </>
        )}
        <Link to="/previsions" className="inline-block text-sm font-medium text-primary">Voir toutes les prévisions et leur bulletin de notes →</Link>
      </CardContent>
    </Card>
  );
}
