import type { ScreenerRow } from "@/lib/api/client";

export type ScreenerFilters = {
  q: string;
  sector: string | null;
  country: string | null;
  market: string | null;
  eligibility: string | null;
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
    eligibility: params.get("eligibility"),
    minScore: numberParam(params, "minScore"),
    minPrice: numberParam(params, "minPrice"),
    maxPrice: numberParam(params, "maxPrice"),
    liquidOnly: params.get("liquid") === "1",
    favoritesOnly: params.get("fav") === "1",
  };
}

export const normalize = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function filterRows(rows: ScreenerRow[], f: ScreenerFilters): ScreenerRow[] {
  const q = normalize(f.q.trim());
  return rows.filter((r) =>
    (!q || normalize(r.name).includes(q) || normalize(r.symbol).includes(q) || normalize(r.isin ?? "").includes(q))
    && (!f.sector || r.sector === f.sector)
    && (!f.country || r.country === f.country)
    && (!f.market || r.market === f.market)
    && (!f.eligibility || r.eligibility === f.eligibility)
    && (f.minScore === null || (r.score !== null && r.score >= f.minScore))
    && (f.minPrice === null || (r.price !== null && r.price >= f.minPrice))
    && (f.maxPrice === null || (r.price !== null && r.price <= f.maxPrice))
    && (!f.liquidOnly || r.liquid)
    && (!f.favoritesOnly || r.is_favorite));
}
