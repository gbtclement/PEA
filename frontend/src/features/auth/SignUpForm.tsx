import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiSend } from "@/lib/api/client";
import { PasswordField, passwordStrength } from "./PasswordField";

const TOO_SHORT = "Le mot de passe doit contenir au moins 12 caractères.";
const TERMS = "Acceptez les CGU et la politique de confidentialité pour créer votre compte.";

export function SignUpForm() {
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const register = useMutation({
    mutationFn: () => apiSend("POST", "/api/auth/register", {
      first_name: firstName, last_name: lastName, email, password, accept_terms: true,
    }),
    onSuccess: () => navigate(`/verifier-email?adresse=${encodeURIComponent(email.trim().toLowerCase())}`),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (passwordStrength(password) === 0) {
      setLocalError(TOO_SHORT);
      return;
    }
    if (!accepted) {
      setLocalError(TERMS);
      return;
    }
    setLocalError(null);
    register.mutate();
  }

  const error = localError ?? (register.error ? register.error.message : null);
  return (
    <form onSubmit={submit} className="mx-auto flex max-w-sm flex-col gap-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Créer un compte</h1>
        <p className="text-sm text-muted-foreground">Gratuit, sans engagement.</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field id="signup-first-name" label="Prénom">
          <Input id="signup-first-name" value={firstName} onChange={(e) => setFirstName(e.target.value)}
                 autoComplete="given-name" required maxLength={100} autoFocus className="bg-white" />
        </Field>
        <Field id="signup-last-name" label="Nom">
          <Input id="signup-last-name" value={lastName} onChange={(e) => setLastName(e.target.value)}
                 autoComplete="family-name" required maxLength={100} className="bg-white" />
        </Field>
      </div>
      <Field id="signup-email" label="Adresse mail">
        <Input id="signup-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
               autoComplete="email" required className="bg-white" />
      </Field>
      <PasswordField id="signup-password" label="Mot de passe" value={password} onChange={setPassword}
                     autoComplete="new-password" showStrength />
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} required className="mt-1" />
        <span>
          J'accepte les <Link to="/cgu" target="_blank" className="text-primary underline">CGU</Link> et
          la <Link to="/confidentialite" target="_blank" className="text-primary underline">politique de confidentialité</Link>.
        </span>
      </label>
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <Button type="submit" disabled={register.isPending}>
        {register.isPending ? "Création…" : "Créer mon compte"}
      </Button>
    </form>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      {children}
    </div>
  );
}
