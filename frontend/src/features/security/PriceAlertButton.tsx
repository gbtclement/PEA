import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useLocation, useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { loginPath } from "@/features/auth/redirect";
import { useMe } from "@/features/auth/useMe";
import { apiSend } from "@/lib/api/client";
import { currencyUnit } from "@/lib/format";

type Security = { id: number; name: string; price: number | null; currency: string };

const toText = (value: number | null) => (value == null ? "" : value.toFixed(2).replace(".", ","));

export function PriceAlertButton({ security }: { security: Security }) {
  const { me } = useMe();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [price, setPrice] = useState(toText(security.price));
  const unit = currencyUnit(security.currency);
  const create = useMutation({
    mutationFn: () => apiSend("POST", "/api/me/price-alerts",
      { security_id: security.id, direction, price: Number(price.replace(",", ".")) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["price-alerts"] });
      toast.success("Alerte créée : un mail partira quand le seuil sera franchi.");
      setOpen(false);
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => (me === null ? navigate(loginPath(location)) : setOpen(true))}>
        <Bell className="size-4" aria-hidden />Créer une alerte
      </Button>
      <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) create.reset(); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Alerte de prix : {security.name}</DialogTitle>
            <DialogDescription>Un mail part une seule fois quand le cours franchit ce seuil, puis l'alerte se désactive.</DialogDescription>
          </DialogHeader>
          <form className="grid gap-3" onSubmit={submit}>
            <label className="text-sm">Quand le cours passe
              <select className="mt-1 block w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                      value={direction} onChange={(e) => setDirection(e.target.value as "above" | "below")}>
                <option value="above">au-dessus de</option>
                <option value="below">en dessous de</option>
              </select>
            </label>
            <div className="space-y-1">
              <label htmlFor="alert-price" className="text-sm">Prix ({unit})</label>
              <Input id="alert-price" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} required />
            </div>
            {create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
            <Button type="submit" disabled={create.isPending}>Créer l'alerte</Button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
