import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiSend } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";
import { Turnstile } from "./Turnstile";
import { useAuthConfig } from "./useAuthConfig";

const CHECK_BOX = "Cochez la case anti-robot.";

export function ForgotPasswordPage() {
  usePageMeta({ title: "Mot de passe oublié", description: "Recevez un lien pour choisir un nouveau mot de passe.", noindex: true });
  const [email, setEmail] = useState("");
  const siteKey = useAuthConfig()?.turnstile_site_key ?? null;
  const [captcha, setCaptcha] = useState<string | null>(null);
  const [captchaRound, setCaptchaRound] = useState(0); // nouvelle case après chaque refus : un jeton ne sert qu'une fois
  const [localError, setLocalError] = useState<string | null>(null);
  const send = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/forgot-password", { email, captcha }) as Promise<{ message: string }>,
    onError: () => { setCaptcha(null); setCaptchaRound((n) => n + 1); },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (siteKey && !captcha) {
      setLocalError(CHECK_BOX);
      return;
    }
    setLocalError(null);
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
          {siteKey && <Turnstile key={captchaRound} siteKey={siteKey} onToken={setCaptcha} />}
          {(localError ?? send.error) && (
            <p role="alert" className="text-sm text-red-600">{localError ?? send.error?.message}</p>
          )}
          <Button type="submit" className="w-full" disabled={send.isPending}>{send.isPending ? "Envoi…" : "Envoyer le lien"}</Button>
        </form>
      )}
      <Link to="/connexion" className="block text-sm text-primary underline">Retour à la connexion</Link>
    </AuthCard>
  );
}
