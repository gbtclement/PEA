import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { SecuritiesTable } from "./SecuritiesTable";
import { PAGE_SIZE, useSecurities } from "./useSecurities";

export function ExplorerPage() {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(search.trim(), 300);
  useEffect(() => setOffset(0), [q]);
  const { data, isPending, isError } = useSecurities({ q, offset });

  return (
    <section>
      <header className="flex items-end justify-between gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Explorer</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Les actions européennes et les ETF, avec leur éligibilité au PEA.
          </p>
        </div>
        <Input
          type="search"
          aria-label="Rechercher"
          placeholder="Rechercher un nom, un ticker ou un ISIN…"
          className="w-80 bg-white"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </header>

      <Card className="mt-6 overflow-hidden py-0">
        {isPending ? (
          <div className="space-y-3 p-6">
            {Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-8 w-full" />)}
          </div>
        ) : isError ? (
          <p role="alert" className="p-6 text-sm text-down">
            Impossible de charger les titres. Vérifiez que l'application est bien démarrée.
          </p>
        ) : data.items.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">Aucun titre ne correspond à « {q} ».</p>
        ) : (
          <SecuritiesTable items={data.items} />
        )}
      </Card>

      {data && data.total > PAGE_SIZE && (
        <footer className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>{offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} sur {data.total}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Précédent</Button>
            <Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= data.total}
                    onClick={() => setOffset(offset + PAGE_SIZE)}>Suivant</Button>
          </div>
        </footer>
      )}
    </section>
  );
}
