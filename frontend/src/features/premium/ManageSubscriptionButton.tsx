import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ApiError, apiSend, type RedirectOut } from "@/lib/api/client";
import { redirectTo } from "./redirect";

/** Ouvre le portail client Stripe : carte, factures, changement de formule, résiliation (spec 3.4). */
export function ManageSubscriptionButton({ variant = "outline" }: { variant?: "default" | "outline" }) {
  const portal = useMutation({
    mutationFn: () => apiSend("POST", "/api/billing/portal") as Promise<RedirectOut>,
    onSuccess: (data) => redirectTo(data.url),
  });
  return (
    <div className="space-y-1">
      <Button variant={variant} disabled={portal.isPending} onClick={() => portal.mutate()}>Gérer mon abonnement</Button>
      {portal.error && <p role="alert" className="text-sm text-destructive">{(portal.error as ApiError).message}</p>}
    </div>
  );
}
