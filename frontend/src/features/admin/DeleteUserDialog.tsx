import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError, apiSend, type AdminUser } from "@/lib/api/client";

export function DeleteUserDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const [typed, setTyped] = useState("");
  const remove = useMutation({
    mutationFn: () => apiSend("DELETE", `/api/admin/users/${user!.id}`, { confirm_email: typed }),
    onSuccess: () => { setTyped(""); onClose(); },
  });
  const matches = user !== null && typed.trim().toLowerCase() === user.email;
  return (
    <Dialog open={user !== null} onOpenChange={(open) => { if (!open) { setTyped(""); remove.reset(); onClose(); } }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Supprimer {user?.first_name} {user?.last_name} ?</DialogTitle>
          <DialogDescription>
            Le compte et toutes ses données (ordres, favoris, conversations, réglages) seront supprimés définitivement.
            Un mail le confirmera à {user?.email}.
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); remove.mutate(); }}>
          <label className="text-sm">Retapez l'adresse mail pour confirmer
            <Input className="mt-1" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
          </label>
          {remove.error && <p role="alert" className="text-sm text-destructive">{(remove.error as ApiError).message}</p>}
          <Button type="submit" variant="destructive" disabled={!matches || remove.isPending}>Supprimer définitivement</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
