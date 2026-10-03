import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, type SecurityList } from "@/lib/api/client";
import { useDebouncedValue } from "@/lib/useDebouncedValue";

/** Titre choisi ; `currency` et `price` (cours actuel) servent à rappeler la devise quand elle n'est pas l'euro. */
export type PickedSecurity = { id: number; name: string; symbol: string; currency?: string; price?: number | null };

type Props = { value: PickedSecurity | null; onChange: (security: PickedSecurity | null) => void };

export function SecurityPicker({ value, onChange }: Props) {
  const [search, setSearch] = useState("");
  const q = useDebouncedValue(search.trim(), 300);
  const results = useQuery({
    queryKey: ["security-picker", q],
    queryFn: () => apiGet<SecurityList>("/api/securities", { q, limit: 8 }),
    enabled: value === null && q.length >= 2,
  });

  if (value) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-input px-3 py-2">
        <div>
          <p className="font-medium">{value.name}</p>
          <p className="text-xs text-muted-foreground">{value.symbol}</p>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={() => onChange(null)}>Changer</Button>
      </div>
    );
  }
  const items = (results.data?.items ?? []).filter((item) => item.kind !== "index");
  return (
    <div className="space-y-1">
      <Input type="search" aria-label="Rechercher un titre" placeholder="Nom, ticker ou ISIN…" className="bg-white"
             value={search} onChange={(e) => setSearch(e.target.value)} />
      {results.data && (
        <ul className="max-h-48 overflow-y-auto rounded-lg border border-border">
          {items.map((item) => (
            <li key={item.id}>
              <button type="button" className="flex w-full items-center justify-between px-3 py-1.5 text-left hover:bg-muted"
                      onClick={() => { onChange({ id: item.id, name: item.name, symbol: item.symbol, currency: item.currency, price: item.price }); setSearch(""); }}>
                <span className="truncate">{item.name}</span>
                <span className="ml-2 shrink-0 text-xs text-muted-foreground">{item.symbol} · {item.market}</span>
              </button>
            </li>
          ))}
          {items.length === 0 && <li className="px-3 py-1.5 text-muted-foreground">Aucun titre trouvé.</li>}
        </ul>
      )}
    </div>
  );
}
