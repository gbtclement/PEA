import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { buttonVariants } from "@/components/ui/button";
import { apiGet, apiSend, type Me } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";

const SLOW_AFTER_MS = 30_000;

/** Retour de Stripe (spec 3.3) : applique le paiement sans attendre le webhook, puis attend que Premium soit actif. */
export function PremiumThanksPage() {
  usePageMeta({ title: "Merci", description: "Activation de votre abonnement Premium.", noindex: true });
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const sync = useMutation({ mutationFn: (id: string) => apiSend("POST", "/api/billing/sync", { session_id: id }) });
  const started = useRef(false);
  const [slow, setSlow] = useState(false);
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiGet<Me>("/api/me"),
    refetchInterval: (query) => (query.state.data?.has_premium ? false : 2000),
  });

  useEffect(() => {
    if (sessionId && !started.current) {
      started.current = true;
      sync.mutate(sessionId, { onSettled: () => me.refetch() });
    }
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (me.data?.has_premium) {
    return (
      <section className="mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">Bienvenue dans Premium</h1>
        <p className="text-sm text-muted-foreground">Votre abonnement est actif. Un mail de confirmation vous a été envoyé.</p>
        <div className="flex flex-wrap gap-2">
          <Link to="/assistant" className={buttonVariants()}>Ouvrir l'assistant IA</Link>
          <Link to="/previsions" className={buttonVariants({ variant: "outline" })}>Voir les prévisions</Link>
        </div>
      </section>
    );
  }
  return (
    <section className="mx-auto max-w-2xl space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight">Merci !</h1>
      <p role="status" className="text-sm">Paiement reçu, activation en cours…</p>
      {slow && (
        <p className="text-sm text-muted-foreground">
          L'activation peut prendre quelques minutes ; vous recevrez un mail de confirmation. Vous pouvez quitter cette page.
        </p>
      )}
    </section>
  );
}
