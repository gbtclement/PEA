import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiSend } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";

export function ForgotPasswordPage() {
  usePageMeta({ title: "Mot de passe oublié", description: "Recevez un lien pour choisir un nouveau mot de passe.", noindex: true });
  const [email, setEmail] = useState("");
  const send = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/forgot-password", { email }) as Promise<{ message: string }>,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    send.mutate();
  }

  return (
    <AuthCard title="Mot de passe oublié">
      {send.data ? (
        <p role="status" className="text-sm">{send.data.message}</p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <p className="text-sm text-muted-foreground">Indiquez votre adresse : vous recevrez un lien valable 30 minutes.</p>
          <div className="space-y-1">
            <label htmlFor="forgot-email" className="text-sm font-medium">Adresse mail</label>
            <Input id="forgot-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                   autoComplete="email" required autoFocus className="bg-white" />
          </div>
          {send.error && <p role="alert" className="text-sm text-red-600">{send.error.message}</p>}
          <Button type="submit" className="w-full" disabled={send.isPending}>{send.isPending ? "Envoi…" : "Envoyer le lien"}</Button>
        </form>
      )}
      <Link to="/connexion" className="block text-sm text-primary underline">Retour à la connexion</Link>
    </AuthCard>
  );
}
