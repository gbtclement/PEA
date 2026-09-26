import type { ScreenerRow } from "@/lib/api/client";
import { filterRows, filtersFromParams } from "./filters";

const row = (over: Partial<ScreenerRow>): ScreenerRow => ({
  id: 1, yahoo_ticker: "MC.PA", symbol: "MC", name: "LVMH", kind: "stock", market: "Euronext Paris", country: "FR",
  sector: "Luxe", eligibility: "eligible", price: 600, change_pct: 1, perf_1w: 1, perf_1m: 1, perf_1y: 1, score: 80,
  pe: 20, dividend_yield: 0.02, liquid: true, is_favorite: false, sparkline: [], ...over,
});
const rows = [
  row({}),
  row({ id: 2, symbol: "TTE", name: "TotalEnergies", sector: "Énergie", price: 60, score: 55, is_favorite: true }),
  row({ id: 3, symbol: "SMA", name: "Petite", sector: "Tech", country: "IT", market: "Euronext Milan", price: 5, score: null, liquid: false }),
];

test("filtersFromParams lit l'URL", () => {
  const f = filtersFromParams(new URLSearchParams("q=tot&minScore=50&liquid=1&fav=1&maxPrice=100"));
  expect(f).toMatchObject({ q: "tot", minScore: 50, liquidOnly: true, favoritesOnly: true, maxPrice: 100, minPrice: null });
});

test("filtre par texte sur nom ou symbole, sans tenir compte des accents", () => {
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("q=energies"))).map((r) => r.id)).toEqual([2]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("q=mc"))).map((r) => r.id)).toEqual([1]);
});

test("filtre par secteur, pays, place et score minimum", () => {
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("sector=Tech"))).map((r) => r.id)).toEqual([3]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("country=IT"))).map((r) => r.id)).toEqual([3]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("market=Euronext Milan"))).map((r) => r.id)).toEqual([3]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("minScore=60"))).map((r) => r.id)).toEqual([1]);
});

test("filtre par prix, liquidité et favoris", () => {
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("minPrice=10&maxPrice=100"))).map((r) => r.id)).toEqual([2]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("liquid=1"))).map((r) => r.id)).toEqual([1, 2]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("fav=1"))).map((r) => r.id)).toEqual([2]);
});

test("paramètres invalides ignorés", () => {
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("minScore=abc")))).toHaveLength(3);
});
