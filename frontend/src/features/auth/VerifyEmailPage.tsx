import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiSend, type Me } from "@/lib/api/client";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";

const RESEND_DELAY = 60;

export function VerifyEmailPage() {
  usePageMeta({ title: "Valider votre adresse", description: "Saisissez le code reçu par mail.", noindex: true });
  const [params] = useSearchParams();
  const email = params.get("adresse");
  if (!email) return <Navigate to="/inscription" replace />;
  return <VerifyEmailForm email={email} />;
}

function VerifyEmailForm({ email }: { email: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [wait, setWait] = useState(RESEND_DELAY);
  const [resent, setResent] = useState(false);

  // Le serveur refuse un nouveau code avant 60 s : le bouton reste grisé pendant ce temps.
  useEffect(() => {
    if (wait <= 0) return;
    const timer = setInterval(() => setWait((value) => Math.max(value - 1, 0)), 1000);
    return () => clearInterval(timer);
  }, [wait > 0]); // eslint-disable-line react-hooks/exhaustive-deps

  const verify = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/verify-email", { email, code }) as Promise<Me>,
    onSuccess: (me) => {
      queryClient.setQueryData(["me"], me);
      navigate("/", { replace: true });
    },
  });
  const resend = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/resend-code", { email }),
    onSuccess: () => {
      setResent(true);
      setWait(RESEND_DELAY);
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    verify.mutate();
  }

  return (
    <AuthCard title="Valider votre adresse">
      <p className="text-sm text-muted-foreground">
        Un code à 6 chiffres vient d'être envoyé à <strong className="text-foreground">{email}</strong>. Il est valable 15 minutes.
      </p>
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-1">
          <label htmlFor="verify-code" className="text-sm font-medium">Code à 6 chiffres</label>
          <Input id="verify-code" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                 inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="\d{6}" required autoFocus
                 className="bg-white text-center text-lg tracking-[0.5em]" />
        </div>
        {verify.error && <p role="alert" className="text-sm text-red-600">{verify.error.message}</p>}
        <Button type="submit" className="w-full" disabled={verify.isPending}>{verify.isPending ? "Vérification…" : "Valider"}</Button>
      </form>
      <div className="flex items-center justify-between gap-2 text-sm">
        <Button variant="link" className="h-auto px-0" disabled={wait > 0 || resend.isPending} onClick={() => resend.mutate()}>
          {wait > 0 ? `Renvoyer le code (${wait} s)` : "Renvoyer le code"}
        </Button>
        <Link to="/inscription" className="text-primary underline">Modifier l'adresse</Link>
      </div>
      {resent && <p role="status" className="text-sm text-muted-foreground">Si l'adresse est correcte, un nouveau code arrive.</p>}
      {resend.error && <p role="alert" className="text-sm text-red-600">{resend.error.message}</p>}
    </AuthCard>
  );
}
