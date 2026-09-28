import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, apiSend } from "@/lib/api/client";
import { PasswordField } from "./PasswordField";
import { safeNext } from "./redirect";

export function SignInForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);

  const login = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/login", { email, password, remember }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate(safeNext(params.get("suite")), { replace: true });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "email_not_verified") {
        navigate(`/verifier-email?adresse=${encodeURIComponent(email.trim().toLowerCase())}`);
      }
    },
  });

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
      {login.error && <p role="alert" className="text-sm text-red-600">{login.error.message}</p>}
      <Button type="submit" disabled={login.isPending}>{login.isPending ? "Connexion…" : "Me connecter"}</Button>
    </form>
  );
}
