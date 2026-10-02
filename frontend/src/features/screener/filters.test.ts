import type { ScreenerRow } from "@/lib/api/client";
import { filterRows, filtersFromParams } from "./filters";

const row = (over: Partial<ScreenerRow>): ScreenerRow => ({
  id: 1, yahoo_ticker: "MC.PA", symbol: "MC", name: "LVMH", kind: "stock", market: "Euronext Paris", country: "FR",
  sector: "Luxe", envelopes: ["pea"], price: 600, change_pct: 1, perf_1w: 1, perf_1m: 1, perf_1y: 1, score: 80,
  pe: 20, dividend_yield: 0.02, liquid: true, available_ratio: 1, isin: null, is_favorite: false, sparkline: [], ...over,
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

test("recherche par ISIN et filtre d'enveloppe", () => {
  const withIsin = [row({ isin: "FR0000121014" }), row({ id: 9, symbol: "X", name: "Exclue", isin: null, envelopes: [] })];
  expect(filterRows(withIsin, filtersFromParams(new URLSearchParams("q=fr0000121014"))).map((r) => r.id)).toEqual([1]);
  const rows = [row({ isin: "FR0000121014", envelopes: ["pea", "pea_pme"] }),
                row({ id: 9, symbol: "X", name: "Étrangère", isin: null, envelopes: [] }),
                row({ id: 10, symbol: "Y", name: "Grande", isin: null, envelopes: ["pea"] })];
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("envelope=pea"))).map((r) => r.id)).toEqual([1, 10]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("envelope=pea_pme"))).map((r) => r.id)).toEqual([1]);
  expect(filterRows(rows, filtersFromParams(new URLSearchParams("eligibility=non_eligible"))).map((r) => r.id)).toEqual([1, 9, 10]); // ancien lien : ignoré
});
