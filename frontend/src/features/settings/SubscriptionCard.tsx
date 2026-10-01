import { Link } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ManageSubscriptionButton } from "@/features/premium/ManageSubscriptionButton";
import { useSubscription } from "@/features/premium/api";

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR", { timeZone: "Europe/Paris" }) : "");

/** État de l'abonnement Premium (spec 3.4) ; tout se gère dans le portail Stripe. */
export function SubscriptionCard() {
  const { data } = useSubscription();
  return (
    <Card id="abonnement">
      <CardHeader>
        <CardTitle className="text-base">Abonnement</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {!data ? null : data.source === "offered" || data.source === "admin" ? (
          <p>Premium vous est offert.</p>
        ) : data.source === "subscription" ? (
          <>
            <p className="font-medium">Premium {data.interval === "year" ? "annuel" : "mensuel"}</p>
            <p className="text-muted-foreground">
              {data.cancel_at_period_end ? `Premium s'arrête le ${day(data.current_period_end)}.` : `Renouvellement le ${day(data.current_period_end)}.`}
            </p>
            {data.status === "past_due" && (
              <p role="alert" className="rounded-md border border-amber-300 bg-amber-50 p-2 text-amber-900">
                Le dernier paiement a échoué. Mettez à jour votre carte pour garder Premium.
              </p>
            )}
            <ManageSubscriptionButton />
          </>
        ) : (
          <>
            <p>Vous n'êtes pas abonné.</p>
            <div className="flex flex-wrap items-start gap-2">
              <Link to="/premium" className={buttonVariants({ size: "sm" })}>Découvrir Premium</Link>
              {data.has_customer && <ManageSubscriptionButton />}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
