import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PasswordField } from "@/features/auth/PasswordField";
import { useMe } from "@/features/auth/useMe";
import { ApiError, apiSend, type Me } from "@/lib/api/client";

export function EmailCard() {
  const { me } = useMe();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [changed, setChanged] = useState<string | null>(null);
  const request = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/email", {
      new_email: email, ...(me?.has_password ? { password } : {}),
    }) as Promise<{ message: string }>,
  });
  const verify = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/email/verify", { code }) as Promise<Me>,
    onSuccess: (updated) => {
      queryClient.setQueryData(["me"], updated);
      setChanged(updated.email);
      request.reset();
      setEmail("");
      setPassword("");
      setCode("");
    },
  });
  if (!me) return null;
  const error = (request.error ?? verify.error) as ApiError | null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Adresse mail</CardTitle>
        <p className="text-sm text-muted-foreground">Adresse actuelle : {me.email}</p>
      </CardHeader>
      <CardContent className="max-w-md space-y-3">
        {!request.isSuccess ? (
          <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); request.mutate(); }}>
            <label className="text-sm">Nouvelle adresse
              <Input className="mt-1 bg-white" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            {me.has_password && (
              <PasswordField id="email-password" label="Mot de passe" value={password} onChange={setPassword} autoComplete="current-password" />
            )}
            <div><Button type="submit" disabled={request.isPending}>Recevoir un code</Button></div>
          </form>
        ) : (
          <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); verify.mutate(); }}>
            <p role="status" className="text-sm text-muted-foreground">{request.data?.message}</p>
            <label className="text-sm">Code reçu
              <Input className="mt-1 w-40 bg-white" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                     value={code} onChange={(e) => setCode(e.target.value)} required />
            </label>
            <div className="flex gap-2">
              <Button type="submit" disabled={verify.isPending}>Valider la nouvelle adresse</Button>
              <Button type="button" variant="outline" onClick={() => { request.reset(); verify.reset(); }}>Annuler</Button>
            </div>
          </form>
        )}
        {changed && <p role="status" className="text-sm text-muted-foreground">Adresse modifiée : {changed}</p>}
        {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
      </CardContent>
    </Card>
  );
}
