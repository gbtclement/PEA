import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Backtest, RealTrack } from "@/lib/api/client";
import { formatDate, formatRatioPct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { FirstRunNotice, HORIZONS, roundPct, signedPct, tone, useTrackRecord } from "./shared";

type Result = Pick<Backtest, "picks" | "hit_rate" | "mean_return" | "mean_after_fees" | "baseline_mean" | "edge">;

function Figure({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("text-lg font-semibold tabular-nums", className)}>{value}</dd>
    </div>
  );
}

function Verdict({ result, cost, compared }: { result: Result; cost: number; compared: string }) {
  const comparison = result.edge > 0
    ? <>Le top 10 a fait mieux que {compared} ({signedPct(result.edge)} par période). </>
    : <>Le top 10 n'a pas fait mieux que {compared} ({signedPct(result.edge)} par période). </>;
  const fees = result.mean_return <= 0
    ? <>Le gain moyen était déjà négatif avant frais ({signedPct(result.mean_return)}) ; après frais : {signedPct(result.mean_after_fees)}.</>
    : result.mean_after_fees > 0
      ? <>Après frais, le gain moyen reste positif ({signedPct(result.mean_after_fees)}).</>
      : <>Mais une fois les frais déduits ({formatRatioPct(cost)} aller-retour), le gain moyen devient négatif ({signedPct(result.mean_after_fees)}).</>;
  return <p className="text-sm">{comparison}{fees}</p>;
}

function ResultCard({ title, result, cost, footer, baselineLabel, compared }: {
  title: string; result: Result; cost: number; footer: string; baselineLabel: string; compared: string;
}) {
  return (
    <Card className="gap-3 px-5">
      <h3 className="font-medium">{title}</h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
        <Figure label="Choix gagnants" value={roundPct(result.hit_rate)} />
        <Figure label="Gain moyen" value={signedPct(result.mean_return)} className={tone(result.mean_return)} />
        <Figure label="Après frais" value={signedPct(result.mean_after_fees)} className={tone(result.mean_after_fees)} />
        <Figure label={baselineLabel} value={signedPct(result.baseline_mean)} className="text-muted-foreground" />
      </dl>
      <Verdict result={result} cost={cost} compared={compared} />
      <p className="text-xs text-muted-foreground">{footer}</p>
    </Card>
  );
}

function EmptyCard({ title, sessions }: { title: string; sessions: string }) {
  return (
    <Card className="gap-2 px-5">
      <h3 className="font-medium">{title}</h3>
      <p className="text-sm text-muted-foreground">
        Pas encore de prédiction vérifiée : chaque prédiction enregistrée le matin est vérifiée automatiquement après {sessions}.
      </p>
    </Card>
  );
}

export function TrackRecordView() {
  const { data, isPending, isError } = useTrackRecord();
  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (isError) return <p role="alert" className="text-sm text-down">Impossible de charger le bulletin.</p>;
  if (!data.cutoff && Object.values(data.simulated).every((v) => !v)) return <Card className="py-0"><FirstRunNotice /></Card>;
  const cost = data.round_trip_cost ?? 0;

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Test sur l'année écoulée</h2>
          <p className="text-sm text-muted-foreground">
            Les statistiques ont été recalculées <strong>sans</strong> la dernière année (avant le {formatDate(data.cutoff)}). Puis, chaque jour
            de cette année, on a pris les 10 meilleures prédictions de hausse et regardé ce qui s'est vraiment passé. Limite : seules les
            entreprises encore connues de Yahoo sont incluses ; certaines entreprises disparues manquent, ce qui peut embellir un peu
            les résultats.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {HORIZONS.map((h) => {
            const result = data.simulated[h.key];
            return result ? (
              <ResultCard key={h.key} title={h.label} result={result} cost={cost} baselineLabel="Moyenne des actions" compared="la moyenne des actions"
                          footer={`${result.picks.toLocaleString("fr-FR")} choix sur ${result.days} jours de bourse.`} />
            ) : <EmptyCard key={h.key} title={h.label} sessions={h.sessions} />;
          })}
        </div>
      </section>
      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Suivi réel</h2>
          <p className="text-sm text-muted-foreground">
            Les prédictions de chaque matin sont enregistrées, puis comparées à ce qui s'est réellement passé : le vrai test, jour après jour.
            Comparaison : la moyenne de tous les titres qui avaient une prédiction les mêmes jours.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {HORIZONS.map((h) => {
            const real: RealTrack | null | undefined = data.real[h.key];
            return real ? (
              <ResultCard key={h.key} title={h.label} result={real} cost={cost} baselineLabel="Moyenne des titres suivis" compared="la moyenne des titres suivis"
                          footer={`${real.picks} prédictions vérifiées depuis le ${formatDate(real.first_day)}.`} />
            ) : <EmptyCard key={h.key} title={h.label} sessions={h.sessions} />;
          })}
        </div>
      </section>
    </div>
  );
}
