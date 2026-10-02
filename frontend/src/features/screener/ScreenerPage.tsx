import { breadcrumb } from "@/seo/schema";
import { usePageMeta } from "@/seo/usePageMeta";
import { useMemo } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router";
import type { SortingState } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { buildColumns } from "./columns";
import { filterRows, filtersFromParams, SORT_KEYS } from "./filters";
import { ScreenerFilters } from "./ScreenerFilters";
import { DataTable } from "@/components/DataTable";
import { type Region, useScreener } from "./useScreener";

const REGIONS: { value: Region; label: string }[] = [{ value: "europe", label: "Europe" }, { value: "us", label: "États-Unis" }];

type Props = { kind: "stock" | "etf"; title: string; description: string };

export function ScreenerPage({ kind, title, description }: Props) {
  const { pathname } = useLocation();
  usePageMeta({ title, description, jsonLd: breadcrumb([{ name: "Accueil", path: "/" }, { name: title, path: pathname }]) });
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const region: Region = params.get("region") === "us" ? "us" : "europe";
  const { data, isPending, isError } = useScreener(kind, region);
  const filters = filtersFromParams(params);
  const columns = useMemo(() => buildColumns(kind), [kind]);
  const rows = useMemo(() => filterRows(data ?? [], filtersFromParams(params)), [data, params]);

  const sortKey = params.get("sort");
  const sorting: SortingState = SORT_KEYS.includes(sortKey as never)
    ? [{ id: sortKey as string, desc: params.get("dir") !== "asc" }]
    : [{ id: "name", desc: false }];

  const update = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };
  const chooseRegion = (value: Region) => {
    const next = new URLSearchParams(params);
    if (value === "europe") next.delete("region");
    else next.set("region", value);
    next.delete("market"); // une place européenne n'existe pas aux États-Unis (et inversement)
    setParams(next, { replace: true });
  };
  const onSortingChange = (next: SortingState) => {
    const updated = new URLSearchParams(params);
    if (next.length === 0) {
      updated.delete("sort");
      updated.delete("dir");
    } else {
      updated.set("sort", next[0].id);
      updated.set("dir", next[0].desc ? "desc" : "asc");
    }
    setParams(updated, { replace: true });
  };

  return (
    <section>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </header>
      <div className="mb-3 flex gap-1" role="group" aria-label="Région">
        {REGIONS.map((r) => (
          <Button key={r.value} size="sm" variant={r.value === region ? "default" : "outline"} aria-pressed={r.value === region}
                  onClick={() => chooseRegion(r.value)}>
            {r.label}
          </Button>
        ))}
      </div>
      <ScreenerFilters rows={data ?? []} filters={filters} onChange={update} count={rows.length} />
      <Card className="mt-4 overflow-hidden py-0">
        {isPending ? (
          <div className="space-y-3 p-6">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        ) : isError ? (
          <p role="alert" className="p-6 text-sm text-down">Impossible de charger les titres. Vérifiez que l'application est bien démarrée.</p>
        ) : rows.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">
            {data.length === 0 ? "Les titres sont en cours de chargement (premier démarrage)." : "Aucun titre ne correspond à ces filtres."}
          </p>
        ) : (
          <DataTable rows={rows} columns={columns} sorting={sorting} onSortingChange={onSortingChange}
                         onRowClick={(row) => navigate(`/titres/${row.id}`)} />
        )}
      </Card>
    </section>
  );
}
