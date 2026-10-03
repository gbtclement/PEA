export type ScreenerFilters = {
  q: string;
  sector: string | null;
  country: string | null;
  market: string | null;
  envelope: string | null;
  minScore: number | null;
  minPrice: number | null;
  maxPrice: number | null;
  liquidOnly: boolean;
  favoritesOnly: boolean;
};

export const SORT_KEYS = ["name", "price", "change_pct", "perf_1w", "perf_1m", "perf_1y", "score", "pe", "dividend_yield"] as const;
export type SortKey = (typeof SORT_KEYS)[number];

function numberParam(params: URLSearchParams, key: string): number | null {
  const raw = params.get(key);
  if (raw === null || raw.trim() === "") return null;
  const value = Number(raw.replace(",", "."));
  return Number.isFinite(value) ? value : null;
}

export function filtersFromParams(params: URLSearchParams): ScreenerFilters {
  return {
    q: params.get("q") ?? "",
    sector: params.get("sector"),
    country: params.get("country"),
    market: params.get("market"),
    envelope: params.get("envelope"),
    minScore: numberParam(params, "minScore"),
    minPrice: numberParam(params, "minPrice"),
    maxPrice: numberParam(params, "maxPrice"),
    liquidOnly: params.get("liquid") === "1",
    favoritesOnly: params.get("fav") === "1",
  };
}

/** Paramètres envoyés à /api/screener : seulement les filtres renseignés, et le tri. */
export function screenerParams(f: ScreenerFilters, sort: { id: string; desc: boolean }): Record<string, string> {
  const params: Record<string, string> = { sort: sort.id, order: sort.desc ? "desc" : "asc" };
  const q = f.q.trim();
  if (q) params.q = q;
  if (f.sector) params.sector = f.sector;
  if (f.country) params.country = f.country;
  if (f.market) params.market = f.market;
  if (f.envelope) params.envelope = f.envelope;
  if (f.minScore !== null) params.min_score = String(f.minScore);
  if (f.minPrice !== null) params.min_price = String(f.minPrice);
  if (f.maxPrice !== null) params.max_price = String(f.maxPrice);
  if (f.liquidOnly) params.liquid = "true";
  if (f.favoritesOnly) params.fav = "true";
  return params;
}

/** Filtres sous forme de texte stable (clé du cache) ; vide sans filtre — la clé que le serveur utilise pour la
 *  première page embarquée dans le HTML (/api/seo/page). */
export function filtersKey(params: Record<string, string>): string {
  return Object.keys(params).filter((k) => k !== "sort" && k !== "order").sort().map((k) => `${k}=${params[k]}`).join("&");
}
