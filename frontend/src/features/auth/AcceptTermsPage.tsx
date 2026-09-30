import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { apiSend, type Me } from "@/lib/api/client";
import { DataCard } from "@/features/settings/DataCard";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";
import { isExternalSuite, safeNext } from "./redirect";
import { useMe } from "./useMe";

/** Nouvelle version des CGU : tant qu'elle n'est pas acceptée, le compte est renvoyé ici (spec 3.5). */
export function AcceptTermsPage() {
  usePageMeta({ title: "Accepter les CGU", description: "Nouvelle version des conditions d'utilisation.", noindex: true });
  const { me } = useMe();
  if (me === null) return <Navigate to="/connexion" replace />;
  return (
    <AuthCard title="Nos conditions ont changé">
      {me && <AcceptForm />}
      {me && (
        <details className="mt-6 text-sm">
          <summary className="cursor-pointer text-muted-foreground">Vous ne souhaitez pas les accepter ?</summary>
          <p className="my-3 text-muted-foreground">Vous pouvez récupérer vos données, puis supprimer votre compte.</p>
          <DataCard />
        </details>
      )}
    </AuthCard>
  );
}

function AcceptForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const [terms, setTerms] = useState(false);
  const accept = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/accept-terms", { accept_terms: true }) as Promise<Me>,
    onSuccess: (me) => {
      queryClient.setQueryData(["me"], me);
      const suite = safeNext(params.get("suite"));
      if (isExternalSuite(suite)) window.location.assign(suite);
      else navigate(suite, { replace: true });
    },
  });
  const logout = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/logout"),
    onSuccess: () => {
      queryClient.clear();
      navigate("/", { replace: true });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (terms) accept.mutate();
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">Pour continuer à utiliser PEA Radar, lisez et acceptez la nouvelle version.</p>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-1" />
        <span>J'accepte les <Link to="/cgu" className="text-primary underline">CGU</Link> et la{" "}
          <Link to="/confidentialite" className="text-primary underline">politique de confidentialité</Link>.</span>
      </label>
      {accept.error && <p role="alert" className="text-sm text-red-600">{accept.error.message}</p>}
      <Button type="submit" disabled={!terms || accept.isPending}>{accept.isPending ? "Enregistrement…" : "Accepter et continuer"}</Button>
      <button type="button" disabled={logout.isPending} onClick={() => logout.mutate()}
              className="text-sm text-muted-foreground underline hover:text-foreground">
        Se déconnecter
      </button>
    </form>
  );
}
