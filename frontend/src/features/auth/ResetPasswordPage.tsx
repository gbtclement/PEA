import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { Button, buttonVariants } from "@/components/ui/button";
import { ApiError, apiSend } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { usePageMeta } from "@/seo/usePageMeta";
import { AuthCard } from "./AuthCard";
import { PasswordField } from "./PasswordField";

export function ResetPasswordPage() {
  usePageMeta({ title: "Nouveau mot de passe", description: "Choisissez un nouveau mot de passe.", noindex: true });
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const reset = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/reset-password", { token: params.get("jeton") ?? "", password }) as Promise<{ message: string }>,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirmation) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    reset.mutate();
  }

  if (reset.data) {
    return (
      <AuthCard title="Nouveau mot de passe">
        <p role="status" className="text-sm">{reset.data.message}</p>
        <Link to="/connexion" className={cn(buttonVariants(), "w-full")}>Se connecter</Link>
      </AuthCard>
    );
  }

  const expired = reset.error instanceof ApiError && reset.error.code === "invalid_token";
  return (
    <AuthCard title="Nouveau mot de passe">
      <form onSubmit={submit} className="space-y-4">
        <PasswordField id="reset-password" label="Nouveau mot de passe" value={password} onChange={setPassword}
                       autoComplete="new-password" showStrength />
        <PasswordField id="reset-confirmation" label="Confirmer le mot de passe" value={confirmation} onChange={setConfirmation}
                       autoComplete="new-password" />
        {mismatch && <p role="alert" className="text-sm text-red-600">Les deux mots de passe sont différents.</p>}
        {!mismatch && reset.error && (
          <p role="alert" className="text-sm text-red-600">
            {reset.error.message}{" "}
            {expired && <Link to="/mot-de-passe-oublie" className="text-primary underline">Refaire une demande</Link>}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={reset.isPending}>{reset.isPending ? "Enregistrement…" : "Enregistrer"}</Button>
      </form>
    </AuthCard>
  );
}
