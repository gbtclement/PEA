import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiSend, type Me } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";

type Pending = { email: string; first_name: string; last_name: string };

export function FinishSignUpPage() {
  usePageMeta({ title: "Finaliser l'inscription", description: "Derniers détails avant d'utiliser PEA Radar.", noindex: true });
  const pending = useQuery({ queryKey: ["google-pending"], queryFn: () => apiGet<Pending>("/api/auth/google/pending"), retry: false });
  if (pending.isError) return <Navigate to="/inscription" replace />;
  return (
    <AuthCard title="Finaliser l'inscription">
      {pending.data && <FinishForm pending={pending.data} />}
    </AuthCard>
  );
}

function FinishForm({ pending }: { pending: Pending }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [firstName, setFirstName] = useState(pending.first_name);
  const [lastName, setLastName] = useState(pending.last_name);
  const [terms, setTerms] = useState(false);
  const [local, setLocal] = useState<string | null>(null);
  const complete = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/google/complete",
      { first_name: firstName, last_name: lastName, accept_terms: terms }) as Promise<Me>,
    onSuccess: (me) => {
      queryClient.setQueryData(["me"], me);
      navigate("/", { replace: true });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!terms) return setLocal("Acceptez les CGU et la politique de confidentialité pour continuer.");
    setLocal(null);
    complete.mutate();
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">Compte Google : <strong>{pending.email}</strong></p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor="finish-first-name" className="text-sm font-medium">Prénom</label>
          <Input id="finish-first-name" value={firstName} onChange={(e) => setFirstName(e.target.value)} required maxLength={100} className="bg-white" />
        </div>
        <div className="space-y-1">
          <label htmlFor="finish-last-name" className="text-sm font-medium">Nom</label>
          <Input id="finish-last-name" value={lastName} onChange={(e) => setLastName(e.target.value)} required maxLength={100} className="bg-white" />
        </div>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-1" />
        <span>J'accepte les <Link to="/cgu" className="text-primary underline">CGU</Link> et la{" "}
          <Link to="/confidentialite" className="text-primary underline">politique de confidentialité</Link>.</span>
      </label>
      {(local || complete.error) && <p role="alert" className="text-sm text-red-600">{local ?? complete.error?.message}</p>}
      <Button type="submit" disabled={complete.isPending}>{complete.isPending ? "Création…" : "Terminer mon inscription"}</Button>
    </form>
  );
}
