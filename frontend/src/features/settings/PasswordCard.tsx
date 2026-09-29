import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PasswordField } from "@/features/auth/PasswordField";
import { useMe } from "@/features/auth/useMe";
import { ApiError, apiSend } from "@/lib/api/client";

export function PasswordCard() {
  const { me } = useMe();
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const save = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/password", {
      ...(me?.has_password ? { current_password: current } : {}), new_password: next,
    }) as Promise<{ message: string }>,
    onSuccess: () => {
      setCurrent("");
      setNext("");
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
  if (!me) return null;
  const label = me.has_password ? "Changer le mot de passe" : "Ajouter un mot de passe";
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Mot de passe</CardTitle>
        {!me.has_password && (
          <p className="text-sm text-muted-foreground">Vous vous connectez avec Google. Un mot de passe vous permettra aussi de vous connecter sans Google.</p>
        )}
      </CardHeader>
      <CardContent>
        <form className="grid max-w-md gap-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          {me.has_password && (
            <PasswordField id="current-password" label="Mot de passe actuel" value={current} onChange={setCurrent} autoComplete="current-password" />
          )}
          <PasswordField id="new-password" label="Nouveau mot de passe" value={next} onChange={setNext} autoComplete="new-password" showStrength />
          <p className="text-xs text-muted-foreground">Vos autres appareils seront déconnectés.</p>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={save.isPending}>{label}</Button>
            {save.data && <p role="status" className="text-sm text-muted-foreground">{save.data.message}</p>}
            {save.error && <p role="alert" className="text-sm text-destructive">{(save.error as ApiError).message}</p>}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
