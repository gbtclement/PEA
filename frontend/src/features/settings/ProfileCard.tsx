import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useMe } from "@/features/auth/useMe";
import { ApiError, apiSend, type Me } from "@/lib/api/client";

export function ProfileCard() {
  const { me } = useMe();
  if (!me) return null;
  return <ProfileForm me={me} />;
}

function ProfileForm({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const [first, setFirst] = useState(me.first_name);
  const [last, setLast] = useState(me.last_name);
  const save = useMutation({
    mutationFn: () => apiSend("PATCH", "/api/me", { first_name: first, last_name: last }) as Promise<Me>,
    onSuccess: (updated) => queryClient.setQueryData(["me"], updated),
  });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Profil</CardTitle></CardHeader>
      <CardContent>
        <form className="grid max-w-xl gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <label className="text-sm">Prénom
            <Input className="mt-1 bg-white" value={first} onChange={(e) => setFirst(e.target.value)} required maxLength={100} />
          </label>
          <label className="text-sm">Nom
            <Input className="mt-1 bg-white" value={last} onChange={(e) => setLast(e.target.value)} required maxLength={100} />
          </label>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" disabled={save.isPending}>Enregistrer le profil</Button>
            {save.isSuccess && <p role="status" className="text-sm text-muted-foreground">Profil enregistré.</p>}
            {save.error && <p role="alert" className="text-sm text-destructive">{(save.error as ApiError).message}</p>}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
