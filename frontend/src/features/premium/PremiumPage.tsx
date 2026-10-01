import { useMutation } from "@tanstack/react-query";
import { Check, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { loginPath } from "@/features/auth/redirect";
import { useMe } from "@/features/auth/useMe";
import { ApiError, apiSend, type RedirectOut } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { usePageMeta } from "@/seo/usePageMeta";
import { formatAmount, usePlans } from "./api";
import { ManageSubscriptionButton } from "./ManageSubscriptionButton";
import { redirectTo } from "./redirect";

type Interval = "month" | "year";

const FEATURES = [
  "L'assistant IA : posez vos questions sur une action, un ETF ou votre portefeuille, en français.",
  "La liste des prévisions court terme (1 jour, 1 semaine, 1 mois) et le bloc prévision de chaque fiche.",
  "Tout le reste de PEA Radar, qui reste gratuit : classement, fiches, portefeuille, notifications.",
];

export function PremiumPage() {
  usePageMeta({ title: "Premium", description: "L'assistant IA et les prévisions court terme de PEA Radar, en abonnement mensuel ou annuel, résiliable à tout moment." });
  const { me } = useMe();
  const plans = usePlans();
  const [interval, setInterval] = useState<Interval>("month");
  const plan = plans.data?.plans.find((p) => p.interval === interval);
  const monthly = plans.data?.plans.find((p) => p.interval === "month");

  return (
    <section className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-2">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><Sparkles className="size-6 text-primary" aria-hidden />PEA Radar Premium</h1>
        <p className="text-sm text-muted-foreground">Pour aller plus loin : l'assistant IA et les prévisions court terme.</p>
      </header>
      <ul className="space-y-2 text-sm">
        {FEATURES.map((f) => <li key={f} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />{f}</li>)}
      </ul>
      <p className="text-sm">
        Avant de vous abonner, regardez ce que valent les prévisions :{" "}
        <Link to="/previsions?vue=bulletin" className="font-medium text-primary">le bilan des prévisions passées</Link> est ouvert à tous les membres.
      </p>
      <Card>
        <CardContent className="space-y-4 pt-6">
          {plans.isPending ? <Skeleton className="h-24 w-full" /> : !plans.data?.configured ? (
            <p className="text-sm">L'abonnement arrive bientôt.</p>
          ) : !plan ? (
            <p className="text-sm text-muted-foreground">Prix indisponibles pour le moment : réessayez dans quelques minutes.</p>
          ) : (
            <>
              <div role="group" aria-label="Formule" className="flex gap-2">
                {(["month", "year"] as const).map((key) => (
                  <Button key={key} size="sm" variant={interval === key ? "default" : "outline"} aria-pressed={interval === key} onClick={() => setInterval(key)}>
                    {key === "month" ? "Mensuel" : `Annuel${plans.data?.yearly_saving_pct ? ` (−${plans.data.yearly_saving_pct} %)` : ""}`}
                  </Button>
                ))}
              </div>
              <p>
                <span className="text-3xl font-semibold tabular-nums">{formatAmount(plan.amount, plan.currency)}</span>
                <span className="text-muted-foreground"> {interval === "month" ? "par mois" : "par an"}, TTC</span>
              </p>
              {interval === "year" && monthly && (
                <p className="text-sm text-muted-foreground">
                  Soit {formatAmount(Math.round(plan.amount / 12), plan.currency)} par mois au lieu de {formatAmount(monthly.amount, monthly.currency)}.
                </p>
              )}
              <Action me={me} interval={interval} />
            </>
          )}
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">
        Paiement sécurisé par Stripe : PEA Radar ne voit jamais votre carte. Résiliable à tout moment depuis les Réglages, effet à la fin
        de la période payée. Voir les <Link to="/cgv" className="underline">conditions générales de vente</Link>. PEA Radar est un outil
        d'aide à la décision, pas un conseil en investissement.
      </p>
    </section>
  );
}

function Action({ me, interval }: { me: ReturnType<typeof useMe>["me"]; interval: Interval }) {
  const [cgv, setCgv] = useState(false);
  const [waiver, setWaiver] = useState(false);
  const checkout = useMutation({
    mutationFn: () => apiSend("POST", "/api/billing/checkout", { interval, accept_cgv: cgv, waive_withdrawal: waiver }) as Promise<RedirectOut>,
    onSuccess: (data) => redirectTo(data.url),
  });
  if (me === undefined) return null;
  if (me === null) {
    return (
      <div className="flex flex-wrap gap-2">
        <Link to="/inscription" className={buttonVariants()}>Créer un compte</Link>
        <Link to={loginPath({ pathname: "/premium", search: "" })} className={buttonVariants({ variant: "outline" })}>Se connecter</Link>
      </div>
    );
  }
  if (me.premium_source === "subscription") {
    return <div className="space-y-2"><p className="font-medium">Vous êtes Premium.</p><ManageSubscriptionButton /></div>;
  }
  if (me.premium_source === "offered" || me.premium_source === "admin") return <p className="font-medium">Premium vous est offert.</p>;
  return (
    <div className="space-y-3 text-sm">
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-0.5 size-4 accent-primary" checked={cgv} onChange={(e) => setCgv(e.target.checked)} />
        <span>J'ai lu et j'accepte les <Link to="/cgv" className="underline">CGV</Link>.</span>
      </label>
      <label className="flex items-start gap-2">
        <input type="checkbox" className="mt-0.5 size-4 accent-primary" checked={waiver} onChange={(e) => setWaiver(e.target.checked)} />
        <span>Je demande l'accès immédiat à Premium et je renonce à mon droit de rétractation de 14 jours.</span>
      </label>
      <Button disabled={!cgv || !waiver || checkout.isPending} onClick={() => checkout.mutate()} className={cn("w-full sm:w-auto")}>S'abonner</Button>
      {checkout.error && <p role="alert" className="text-destructive">{(checkout.error as ApiError).message}</p>}
    </div>
  );
}
