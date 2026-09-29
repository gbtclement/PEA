import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiSend, type Me } from "@/lib/api/client";
import { GoogleButton } from "./GoogleButton";
import { PasswordField } from "./PasswordField";
import { safeNext } from "./redirect";

const GOOGLE_ERRORS: Record<string, string> = {
  google: "La connexion avec Google n'a pas abouti. Réessayez.",
  google_email: "Votre adresse Google n'est pas validée par Google : utilisez une autre méthode.",
};

export function SignInForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);

  const login = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/login", { email, password, remember }) as Promise<Me>,
    onSuccess: (me) => {
      // Le compte renvoyé remplace tout de suite le « visiteur » en cache : RequireAuth ne doit pas le relire
      queryClient.setQueryData(["me"], me);
      navigate(safeNext(params.get("suite")), { replace: true });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "email_not_verified") {
        navigate(`/verifier-email?adresse=${encodeURIComponent(email.trim().toLowerCase())}`);
      }
    },
  });

  const googleError = GOOGLE_ERRORS[params.get("erreur") ?? ""];

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate();
  }

  return (
    <form onSubmit={submit} className="mx-auto flex max-w-sm flex-col gap-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Se connecter</h1>
        <p className="text-sm text-muted-foreground">Content de vous revoir.</p>
      </div>
      <GoogleButton suite={params.get("suite")} remember={remember} />
      <div className="space-y-1">
        <label htmlFor="signin-email" className="text-sm font-medium">Adresse mail</label>
        <Input id="signin-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
               autoComplete="email" required autoFocus className="bg-white" />
      </div>
      <PasswordField id="signin-password" label="Mot de passe" value={password} onChange={setPassword}
                     autoComplete="current-password" />
      <div className="flex items-center justify-between gap-2 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          Rester connecté
        </label>
        <Link to="/mot-de-passe-oublie" className="text-primary underline">Mot de passe oublié ?</Link>
      </div>
      {googleError && !login.error && <p role="alert" className="text-sm text-red-600">{googleError}</p>}
      {login.error && <p role="alert" className="text-sm text-red-600">{login.error.message}</p>}
      <Button type="submit" disabled={login.isPending}>{login.isPending ? "Connexion…" : "Me connecter"}</Button>
    </form>
  );
}
