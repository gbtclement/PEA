import { useMutation } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { ApiError, apiSend } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";

/** Lien « Ce n'était pas moi » du mail de nouvel appareil : l'action attend un clic, car les antivirus ouvrent les liens des mails. */
export function NotMePage() {
  usePageMeta({ title: "Sécuriser mon compte", description: "Déconnectez tous vos appareils.", noindex: true });
  const [params] = useSearchParams();
  const secure = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/not-me", { token: params.get("jeton") ?? "" }) as Promise<{ message: string }>,
  });

  return (
    <AuthCard title="Sécuriser mon compte">
      {secure.data ? (
        <p role="status" className="text-sm">{secure.data.message}</p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Vous n'êtes pas à l'origine de cette connexion ? Nous allons déconnecter tous vos appareils, désactiver votre mot de
            passe actuel et vous envoyer un lien pour en choisir un nouveau.
          </p>
          {secure.error && (
            <p role="alert" className="text-sm text-red-600">
              {secure.error.message}{" "}
              {secure.error instanceof ApiError && secure.error.code === "invalid_token" && (
                <Link to="/mot-de-passe-oublie" className="text-primary underline">Refaire une demande</Link>
              )}
            </p>
          )}
          <Button className="w-full" disabled={secure.isPending} onClick={() => secure.mutate()}>
            {secure.isPending ? "Sécurisation…" : "Sécuriser mon compte"}
          </Button>
        </>
      )}
    </AuthCard>
  );
}
