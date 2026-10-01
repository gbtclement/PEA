import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { apiGet, apiSend } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";

type LinkInfo = { kind: string | null; label: string | null };

/** Lien « Ne plus recevoir ce mail » des notifications : sans connexion, le jeton signé suffit. */
export function UnsubscribePage() {
  usePageMeta({ title: "Se désinscrire", description: "Ne plus recevoir une notification de PEA Radar.", noindex: true });
  const [params] = useSearchParams();
  const jeton = params.get("jeton") ?? "";
  const type = params.get("type");
  const one = new URLSearchParams(type ? { jeton, type } : { jeton }).toString();
  const all = new URLSearchParams({ jeton }).toString();
  const info = useQuery({ queryKey: ["unsubscribe", one], queryFn: () => apiGet<LinkInfo>(`/api/unsubscribe?${one}`), retry: false });
  const [done, setDone] = useState<string | null>(null);
  const send = useMutation({
    mutationFn: (query: string) => apiSend("POST", `/api/unsubscribe?${query}`) as Promise<{ message: string }>,
    onSuccess: (result) => setDone(result.message),
  });
  return (
    <AuthCard title="Se désinscrire">
      <div className="flex flex-col gap-4 text-sm">
        {info.isError && (
          <p role="alert" className="text-red-600">
            Ce lien de désinscription n'est pas valable. Connectez-vous pour gérer vos notifications dans les Réglages.
          </p>
        )}
        {done && <p role="status" className="font-medium">{done}</p>}
        {info.data && !done && (
          <>
            {info.data.label && (
              <Button disabled={send.isPending} onClick={() => send.mutate(one)}>Ne plus recevoir « {info.data.label} »</Button>
            )}
            <Button variant="outline" disabled={send.isPending} onClick={() => send.mutate(all)}>
              Ne plus recevoir aucune notification
            </Button>
          </>
        )}
        {send.error && <p role="alert" className="text-red-600">{send.error.message}</p>}
        <p className="text-xs text-muted-foreground">
          Les mails liés à votre compte (codes, sécurité) restent envoyés. Vous pouvez tout régler dans{" "}
          <Link to="/reglages#notifications" className="text-primary underline">vos réglages</Link>.
        </p>
      </div>
    </AuthCard>
  );
}
