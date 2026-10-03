import { useId, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { apiGet, type FeeEstimate, type OrderOut } from "@/lib/api/client";
import { formatPrice } from "@/lib/format";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { useSaveOrder } from "./api";
import { SecurityPicker, type PickedSecurity } from "./SecurityPicker";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  security?: PickedSecurity;
  price?: number | null;
  order?: OrderOut;
};

const parisDay = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Paris" });

function parseDecimal(value: string): number {
  const trimmed = value.trim().replace(/\s/g, "").replace(",", ".");
  return trimmed === "" ? Number.NaN : Number(trimmed);
}

function toInput(value: number, digits?: number): string {
  return (digits === undefined ? String(Math.round(value * 10_000) / 10_000) : value.toFixed(digits)).replace(".", ",");
}

export function OrderDialog({ open, onOpenChange, ...rest }: Props) {
  return (
    <Dialog open={open} onOpenChange={(next) => onOpenChange(next)}>
      <DialogContent className="sm:max-w-lg">{open && <OrderForm onDone={() => onOpenChange(false)} {...rest} />}</DialogContent>
    </Dialog>
  );
}

function Field({ label, children, htmlFor }: { label: string; children: ReactNode; htmlFor: string }) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="text-xs font-medium text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

function OrderForm({ security, price, order, onDone }: Omit<Props, "open" | "onOpenChange"> & { onDone: () => void }) {
  const id = useId();
  const today = parisDay.format(new Date());
  const [date, setDate] = useState(order?.trade_date ?? today);
  const [side, setSide] = useState(order?.side ?? "buy");
  const [picked, setPicked] = useState<PickedSecurity | null>(
    order ? { id: order.security_id, name: order.name, symbol: order.symbol } : security ?? null);
  const [quantity, setQuantity] = useState(order ? String(order.quantity) : "");
  const [unitPrice, setUnitPrice] = useState(order ? toInput(order.unit_price) : price ? toInput(price) : "");
  const [feeTouched, setFeeTouched] = useState(Boolean(order));
  const [feeInput, setFeeInput] = useState(order ? toInput(order.fee, 2) : "");
  const [note, setNote] = useState(order?.note ?? "");
  const foreign = Boolean(picked?.currency && picked.currency !== "EUR");  // titre coté hors euro (dollar, franc suisse…)
  const [error, setError] = useState<string | null>(null);
  const save = useSaveOrder();

  const qty = Number(quantity.trim());
  const unit = parseDecimal(unitPrice);
  const validQty = Number.isInteger(qty) && qty > 0;
  const validPrice = Number.isFinite(unit) && unit > 0;
  const amount = validQty && validPrice ? Math.round(qty * unit * 100) / 100 : 0;
  const debouncedAmount = useDebouncedValue(amount, 300);
  const estimate = useQuery({
    queryKey: ["fee", debouncedAmount],
    queryFn: () => apiGet<FeeEstimate>("/api/fees/estimate", { amount: debouncedAmount }),
    enabled: !feeTouched && debouncedAmount > 0,
  });
  const feeShown = feeTouched ? feeInput : estimate.data && amount > 0 ? toInput(estimate.data.fee, 2) : "";
  const manualFee = feeTouched && feeInput.trim() !== "" ? parseDecimal(feeInput) : null;
  const validFee = manualFee === null || (Number.isFinite(manualFee) && manualFee >= 0);
  const canSubmit = picked !== null && validQty && validPrice && validFee && date !== "" && date <= today && !save.isPending;

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit || !picked) return;
    setError(null);
    save.mutate(
      {
        id: order?.id,
        order: { security_id: picked.id, trade_date: date, side: side as "buy" | "sell", quantity: qty, unit_price: unit,
                 fee: manualFee, note: note.trim() || null },
      },
      {
        onSuccess: () => { toast.success("Ordre enregistré"); onDone(); },
        onError: (err) => setError(err.message),
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <DialogHeader>
        <DialogTitle>{order ? "Modifier l'ordre" : "Nouvel ordre"}</DialogTitle>
        <DialogDescription>Recopiez l'ordre passé chez votre courtier. Les frais sont calculés selon votre grille.</DialogDescription>
      </DialogHeader>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Date" htmlFor={`${id}-date`}>
          <Input id={`${id}-date`} type="date" max={today} className="bg-white" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <Field label="Sens" htmlFor={`${id}-side`}>
          <select id={`${id}-side`} value={side} onChange={(e) => setSide(e.target.value)}
                  className="h-8 w-full rounded-lg border border-input bg-white px-2 text-sm">
            <option value="buy">Achat</option>
            <option value="sell">Vente</option>
          </select>
        </Field>
      </div>
      <SecurityPicker value={picked} onChange={setPicked} />
      {foreign && picked && (
        <p className="text-xs text-muted-foreground">
          {picked.name} cote en {picked.currency}
          {picked.price != null && ` (cours actuel : ${formatPrice(picked.price)} ${picked.currency})`}. Saisissez le prix payé
          en euros, tel qu'indiqué par votre courtier : le portefeuille compte en euros.
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Quantité" htmlFor={`${id}-qty`}>
          <Input id={`${id}-qty`} inputMode="numeric" className="bg-white" value={quantity} onChange={(e) => { setQuantity(e.target.value); setFeeTouched(false); }} />
        </Field>
        <Field label={foreign ? "Prix unitaire payé (€)" : "Prix unitaire (€)"} htmlFor={`${id}-price`}>
          <Input id={`${id}-price`} inputMode="decimal" className="bg-white" value={unitPrice} onChange={(e) => { setUnitPrice(e.target.value); setFeeTouched(false); }} />
        </Field>
        <Field label="Frais (€)" htmlFor={`${id}-fee`}>
          <Input id={`${id}-fee`} inputMode="decimal" className="bg-white" value={feeShown}
                 onChange={(e) => { setFeeTouched(true); setFeeInput(e.target.value); }}
                 onBlur={() => { if (feeInput.trim() === "") setFeeTouched(false); }} />
        </Field>
      </div>
      <Field label="Note (facultatif)" htmlFor={`${id}-note`}>
        <Input id={`${id}-note`} maxLength={200} className="bg-white" value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <p className="text-sm text-muted-foreground">
        Montant : <span className="font-medium text-foreground tabular-nums">{formatPrice(amount)} €</span>
        {feeTouched ? " · frais saisis à la main" : " · frais estimés automatiquement"}
      </p>
      {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-down">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onDone}>Annuler</Button>
        <Button type="submit" disabled={!canSubmit}>Enregistrer</Button>
      </div>
    </form>
  );
}
