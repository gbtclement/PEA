import { Input } from "@/components/ui/input";
import type { ScreenerRow } from "@/lib/api/client";
import type { ScreenerFilters as Filters } from "./filters";

type Props = {
  rows: ScreenerRow[];
  filters: Filters;
  onChange: (key: string, value: string | null) => void;
  count: number;
};

const unique = (values: (string | null)[]) => [...new Set(values.filter((v): v is string => !!v))].sort((a, b) => a.localeCompare(b, "fr"));

const ELIGIBILITY_LABELS: Record<string, string> = { eligible: "Éligibles PEA", a_verifier: "À vérifier", non_eligible: "Non éligibles" };

function Select({ label, value, options, onChange, labels = {} }: {
  label: string; value: string | null; options: string[]; onChange: (v: string | null) => void; labels?: Record<string, string>;
}) {
  return (
    <select
      aria-label={label}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
    >
      <option value="">{label} : tous</option>
      {options.map((o) => <option key={o} value={o}>{labels[o] ?? o}</option>)}
    </select>
  );
}

export function ScreenerFilters({ rows, filters, onChange, count }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        type="search" aria-label="Rechercher" placeholder="Nom, ticker ou ISIN…" className="w-60 bg-white"
        value={filters.q} onChange={(e) => onChange("q", e.target.value || null)}
      />
      <Select label="Secteur" value={filters.sector} options={unique(rows.map((r) => r.sector))} onChange={(v) => onChange("sector", v)} />
      <Select label="Pays" value={filters.country} options={unique(rows.map((r) => r.country))} onChange={(v) => onChange("country", v)} />
      <Select label="Place" value={filters.market} options={unique(rows.map((r) => r.market))} onChange={(v) => onChange("market", v)} />
      <Select label="Éligibilité" value={filters.eligibility} options={Object.keys(ELIGIBILITY_LABELS)} labels={ELIGIBILITY_LABELS}
              onChange={(v) => onChange("eligibility", v)} />
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
      <span className="ml-auto text-sm text-muted-foreground">{count} {count > 1 ? "titres" : "titre"}</span>
    </div>
  );
}
