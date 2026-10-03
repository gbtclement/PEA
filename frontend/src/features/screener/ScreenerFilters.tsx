import { Input } from "@/components/ui/input";
import { useIsMobile } from "@/lib/useIsMobile";
import { FiltersSheet } from "./FiltersSheet";
import type { ScreenerFacets } from "@/lib/api/client";
import { ENVELOPE_LABELS } from "@/lib/envelopes";
import { SORT_KEYS, type ScreenerFilters as Filters, type SortKey } from "./filters";

type Props = {
  facets?: ScreenerFacets;  // valeurs proposées (secteurs, pays, places), données par le serveur
  filters: Filters;
  onChange: (key: string, value: string | null) => void;
  count: number;
  /** Tri courant (téléphone : pas d'en-têtes de colonnes à cliquer). */
  sort?: { key: string; desc: boolean };
  onSortChange?: (key: SortKey, desc: boolean) => void;
};

const SORT_LABELS: Record<SortKey, string> = {
  name: "Nom", price: "Cours", change_pct: "Variation du jour", perf_1w: "1 semaine", perf_1m: "1 mois", perf_1y: "1 an",
  score: "Score", pe: "PER", dividend_yield: "Rendement",
};

function countActive(f: Filters): number {
  return [f.sector, f.country, f.market, f.envelope, f.minScore, f.minPrice, f.maxPrice].filter((v) => v !== null).length
    + (f.liquidOnly ? 1 : 0) + (f.favoritesOnly ? 1 : 0);
}


function Select({ label, value, options, onChange, labels = {}, allLabel = `${label} : tous` }: {
  label: string; value: string | null; options: string[]; onChange: (v: string | null) => void; labels?: Record<string, string>;
  allLabel?: string;
}) {
  return (
    <select
      aria-label={label}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
    >
      <option value="">{allLabel}</option>
      {options.map((o) => <option key={o} value={o}>{labels[o] ?? o}</option>)}
    </select>
  );
}

export function ScreenerFilters({ facets, filters, onChange, count, sort, onSortChange }: Props) {
  const mobile = useIsMobile();
  const search = (
    <Input
      type="search" aria-label="Rechercher" placeholder="Nom, ticker ou ISIN…" className="w-full bg-white md:w-60"
      value={filters.q} onChange={(e) => onChange("q", e.target.value || null)}
    />
  );
  const counter = <span className="ml-auto text-sm text-muted-foreground">{count} {count > 1 ? "titres" : "titre"}</span>;
  if (mobile) {
    return (
      <div className="space-y-2">
        {search}
        <div className="flex items-center gap-2">
          <FiltersSheet active={countActive(filters)}>
            {sort && onSortChange && (
              <>
                <select aria-label="Trier par" value={sort.key} className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
                        onChange={(e) => onSortChange(e.target.value as SortKey, sort.desc)}>
                  {SORT_KEYS.map((key) => <option key={key} value={key}>Trier par : {SORT_LABELS[key]}</option>)}
                </select>
                <select aria-label="Ordre" value={sort.desc ? "desc" : "asc"} className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
                        onChange={(e) => onSortChange(sort.key as SortKey, e.target.value === "desc")}>
                  <option value="desc">Du plus grand au plus petit</option>
                  <option value="asc">Du plus petit au plus grand</option>
                </select>
              </>
            )}
            <FilterFields facets={facets} filters={filters} onChange={onChange} />
          </FiltersSheet>
          {counter}
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      {search}
      <FilterFields facets={facets} filters={filters} onChange={onChange} />
      {counter}
    </div>
  );
}

function FilterFields({ facets, filters, onChange }: Pick<Props, "facets" | "filters" | "onChange">) {
  return (
    <>
      <Select label="Secteur" value={filters.sector} options={facets?.sectors ?? []} onChange={(v) => onChange("sector", v)} />
      <Select label="Pays" value={filters.country} options={facets?.countries ?? []} onChange={(v) => onChange("country", v)} />
      <Select label="Place" value={filters.market} options={facets?.markets ?? []} onChange={(v) => onChange("market", v)} />
      <Select label="Enveloppe" allLabel="Enveloppe : toutes" value={filters.envelope} options={["pea", "pea_pme"]}
              labels={ENVELOPE_LABELS} onChange={(v) => onChange("envelope", v)} />
      <Input type="number" aria-label="Score minimum" placeholder="Score min" className="w-28 bg-white" min={0} max={100}
             value={filters.minScore ?? ""} onChange={(e) => onChange("minScore", e.target.value || null)} />
      <Input type="number" aria-label="Prix minimum" placeholder="Prix min" className="w-24 bg-white" min={0}
             value={filters.minPrice ?? ""} onChange={(e) => onChange("minPrice", e.target.value || null)} />
      <Input type="number" aria-label="Prix maximum" placeholder="Prix max" className="w-24 bg-white" min={0}
             value={filters.maxPrice ?? ""} onChange={(e) => onChange("maxPrice", e.target.value || null)} />
      <label className="flex items-center gap-1.5 text-sm">
        <input type="checkbox" checked={filters.liquidOnly} onChange={(e) => onChange("liquid", e.target.checked ? "1" : null)} />
        Liquides uniquement
      </label>
      <label className="flex items-center gap-1.5 text-sm">
        <input type="checkbox" checked={filters.favoritesOnly} onChange={(e) => onChange("fav", e.target.checked ? "1" : null)} />
        Favoris
      </label>
    </>
  );
}
