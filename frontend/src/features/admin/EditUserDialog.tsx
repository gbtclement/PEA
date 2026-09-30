import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError, apiSend, type AdminUser } from "@/lib/api/client";

export function EditUserDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  return (
    <Dialog open={user !== null} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Modifier le compte</DialogTitle>
          <DialogDescription>Changer l'adresse la marque comme validée ; l'ancienne et la nouvelle adresse sont prévenues.</DialogDescription>
        </DialogHeader>
        {user && <EditUserForm key={user.id} user={user} onDone={onClose} />}
      </DialogContent>
    </Dialog>
  );
}

function EditUserForm({ user, onDone }: { user: AdminUser; onDone: () => void }) {
  const [form, setForm] = useState({ first_name: user.first_name, last_name: user.last_name, email: user.email, role: user.role,
                                     is_premium: user.is_premium });
  const save = useMutation({
    mutationFn: () => apiSend("PATCH", `/api/admin/users/${user.id}`, form),
    onSuccess: onDone,
  });
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [key]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value });
  return (
    <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <label className="text-sm">Prénom<Input className="mt-1" value={form.first_name} onChange={set("first_name")} required /></label>
      <label className="text-sm">Nom<Input className="mt-1" value={form.last_name} onChange={set("last_name")} required /></label>
      <label className="text-sm">Mail<Input className="mt-1" type="email" value={form.email} onChange={set("email")} required /></label>
      <label className="text-sm">Rôle
        <select className="mt-1 h-9 w-full rounded-lg border border-input bg-white px-2 text-sm" value={form.role} onChange={set("role")}>
          <option value="user">Utilisateur</option>
          <option value="admin">Admin</option>
        </select>
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="size-4 accent-primary" checked={form.is_premium} onChange={set("is_premium")} />Premium
      </label>
      {save.error && <p role="alert" className="text-sm text-destructive">{(save.error as ApiError).message}</p>}
      <Button type="submit" disabled={save.isPending}>Enregistrer</Button>
    </form>
  );
}
