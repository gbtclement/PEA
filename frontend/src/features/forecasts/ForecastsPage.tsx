import { useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { useMe } from "@/features/auth/useMe";
import { PremiumCard } from "@/features/premium/PremiumCard";
import { formatDate, formatRatioPct } from "@/lib/format";
import { usePageMeta } from "@/seo/usePageMeta";
import { PredictionsView } from "./PredictionsView";
import { useForecasts } from "./shared";
import { SignalStatsView } from "./SignalStatsView";
import { TrackRecordView } from "./TrackRecordView";

const VIEWS = [
  { key: "predictions", label: "Prédictions" },
  { key: "statistiques", label: "Statistiques des signaux" },
  { key: "bulletin", label: "Bulletin de notes" },
] as const;
type View = (typeof VIEWS)[number]["key"];

export function ForecastsPage() {
  // Jamais indexée, même en ligne : des « paris » boursiers publiés au grand public relèveraient du cadre de l'AMF.
  usePageMeta({
    title: "Prévisions court terme",
    description: "Prédictions à 1 jour, 1 semaine et 1 mois calculées à partir des statistiques historiques des signaux techniques.",
    noindex: true,
  });
  const { me } = useMe();
  const premium = !!me?.has_premium;
  const fallback: View = premium ? "predictions" : "bulletin";  // un membre gratuit arrive sur le bilan (spec 2)
  const [params, setParams] = useSearchParams();
  const view: View = VIEWS.some((v) => v.key === params.get("vue")) ? (params.get("vue") as View) : fallback;
  const { data } = useForecasts(premium);

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Prévisions court terme</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Les actions dont l'historique récent ressemble à des situations qui ont souvent précédé une hausse (ou une baisse), et ce
          que ces situations ont vraiment donné par le passé.
          {data?.as_of && <> Données du {formatDate(data.as_of)} (clôture), mises à jour chaque matin de bourse.</>}
        </p>
      </header>
      <p role="note" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
        Ces prévisions sont des estimations statistiques tirées de l'historique des cours : pas des certitudes ni des conseils en
        investissement. Une nouvelle inattendue (résultats, rachat…) peut tout changer.
        {data?.round_trip_cost != null && <> Frais d'un achat puis d'une revente de 500 € : {formatRatioPct(data.round_trip_cost)}.</>}
      </p>
      <div role="group" aria-label="Vues des prévisions" className="flex gap-2">
        {VIEWS.map((v) => (
          <Button key={v.key} variant={v.key === view ? "default" : "outline"} size="sm" aria-current={v.key === view ? "page" : undefined}
                  onClick={() => setParams(v.key === fallback ? {} : { vue: v.key }, { replace: true })}>
            {v.label}
          </Button>
        ))}
      </div>
      {view === "predictions" && (premium ? <PredictionsView /> : <PremiumCard feature="La liste des prévisions" />)}
      {view === "statistiques" && <SignalStatsView />}
      {view === "bulletin" && <TrackRecordView />}
    </section>
  );
}
