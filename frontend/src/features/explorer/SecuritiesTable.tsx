import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { SecurityItem } from "@/lib/api/client";
import { formatDateTime, formatPct, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";
import { EligibilityBadge } from "./EligibilityBadge";

export function SecuritiesTable({ items }: { items: SecurityItem[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="pl-6">Nom</TableHead>
          <TableHead>Place</TableHead>
          <TableHead>Éligibilité</TableHead>
          <TableHead className="text-right">Cours</TableHead>
          <TableHead className="text-right">Var. jour</TableHead>
          <TableHead className="pr-6 text-right">Mise à jour</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            <TableCell className="pl-6">
              <div className="font-medium">{item.name}</div>
              <div className="text-xs text-muted-foreground">{item.symbol}</div>
            </TableCell>
            <TableCell className="text-muted-foreground">{item.market}</TableCell>
            <TableCell><EligibilityBadge status={item.eligibility} /></TableCell>
            <TableCell className="text-right font-medium">{formatPrice(item.price)}</TableCell>
            <TableCell
              className={cn(
                "text-right font-medium",
                item.change_pct != null && item.change_pct > 0 && "text-up",
                item.change_pct != null && item.change_pct < 0 && "text-down",
              )}
            >
              {formatPct(item.change_pct)}
            </TableCell>
            <TableCell className="pr-6 text-right text-xs text-muted-foreground">{formatDateTime(item.as_of)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
