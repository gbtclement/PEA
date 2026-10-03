import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { OrderOut } from "@/lib/api/client";
import { formatDate, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useIsMobile } from "@/lib/useIsMobile";
import { useDeleteOrder } from "./api";

const TH = "px-3 py-2 text-right text-xs font-medium text-muted-foreground";
const TD = "px-3 py-2 text-right tabular-nums";

export function OrdersHistory({ orders, onEdit }: { orders: OrderOut[]; onEdit: (order: OrderOut) => void }) {
  const remove = useDeleteOrder();
  const mobile = useIsMobile();  // téléphone : une carte par ordre
  const [error, setError] = useState<string | null>(null);

  function confirmDelete(order: OrderOut) {
    const what = `${order.side === "buy" ? "l'achat" : "la vente"} de ${order.quantity} ${order.name} du ${formatDate(order.trade_date)}`;
    if (!window.confirm(`Supprimer ${what} ?`)) return;
    setError(null);
    remove.mutate(order.id, {
      onSuccess: () => toast.success("Ordre supprimé"),
      onError: (err) => { setError(err.message); toast.error(err.message); },
    });
  }

  return (
    <div className="space-y-2">
      {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-down">{error}</p>}
      {mobile ? (
        <ul aria-label="Ordres" className="space-y-2">
          {orders.map((order) => (
            <li key={order.id} className="rounded-xl border border-border p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="tabular-nums text-muted-foreground">{formatDate(order.trade_date)}</span>
                <Badge variant={order.side === "buy" ? "secondary" : "outline"}>{order.side === "buy" ? "Achat" : "Vente"}</Badge>
              </div>
              <p className="mt-1 font-medium">{order.name}</p>
              {order.note && <p className="text-xs text-muted-foreground">📝 {order.note}</p>}
              <p className="mt-1 tabular-nums">
                {order.quantity} × {formatPrice(order.unit_price)} € + {formatPrice(order.fee)} € de frais = <span className="font-medium">{formatPrice(order.amount)} €</span>
              </p>
              <div className="mt-2 flex gap-2 [&_button]:min-h-11">
                <Button variant="outline" size="sm" onClick={() => onEdit(order)}
                        aria-label={`Modifier l'ordre du ${formatDate(order.trade_date)}`}>Modifier</Button>
                <Button variant="outline" size="sm" className="text-down" disabled={remove.isPending} onClick={() => confirmDelete(order)}
                        aria-label={`Supprimer l'ordre du ${formatDate(order.trade_date)}`}>Supprimer</Button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
      <table className="w-full text-sm">
        <thead className="border-b border-border">
          <tr>
            <th className={cn(TH, "text-left")}>Date</th>
            <th className={cn(TH, "text-left")}>Sens</th>
            <th className={cn(TH, "text-left")}>Titre</th>
            <th className={TH}>Quantité</th>
            <th className={TH}>Prix</th>
            <th className={TH}>Frais</th>
            <th className={TH}>Montant</th>
            <th className={TH}><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {orders.map((order) => (
            <tr key={order.id}>
              <td className="px-3 py-2 tabular-nums">{formatDate(order.trade_date)}</td>
              <td className="px-3 py-2">
                <Badge variant={order.side === "buy" ? "secondary" : "outline"}>{order.side === "buy" ? "Achat" : "Vente"}</Badge>
              </td>
              <td className="px-3 py-2">
                {order.name}
                {order.note && <span className="ml-2 text-xs text-muted-foreground" title={order.note}>📝</span>}
              </td>
              <td className={TD}>{order.quantity}</td>
              <td className={TD}>{formatPrice(order.unit_price)} €</td>
              <td className={TD}>{formatPrice(order.fee)} €</td>
              <td className={TD}>{formatPrice(order.amount)} €</td>
              <td className="px-3 py-2 text-right whitespace-nowrap">
                <Button variant="ghost" size="sm" onClick={() => onEdit(order)}
                        aria-label={`Modifier l'ordre du ${formatDate(order.trade_date)}`}>Modifier</Button>
                <Button variant="ghost" size="sm" className="text-down" disabled={remove.isPending} onClick={() => confirmDelete(order)}
                        aria-label={`Supprimer l'ordre du ${formatDate(order.trade_date)}`}>Supprimer</Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      )}
    </div>
  );
}
