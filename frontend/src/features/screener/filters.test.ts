import { filtersFromParams, filtersKey, screenerParams } from "./filters";

test("filtersFromParams lit l'URL", () => {
  const f = filtersFromParams(new URLSearchParams("q=tot&minScore=50&liquid=1&fav=1&maxPrice=100"));
  expect(f).toMatchObject({ q: "tot", minScore: 50, liquidOnly: true, favoritesOnly: true, maxPrice: 100, minPrice: null });
});

test("paramètres de l'API : seulement les filtres renseignés, tri compris", () => {
  const f = filtersFromParams(new URLSearchParams("q= tot &sector=Luxe&minScore=50&liquid=1&fav=1"));
  expect(screenerParams(f, { id: "score", desc: true })).toEqual({
    sort: "score", order: "desc", q: "tot", sector: "Luxe", min_score: "50", liquid: "true", fav: "true",
  });
  expect(screenerParams(filtersFromParams(new URLSearchParams("")), { id: "name", desc: false })).toEqual({ sort: "name", order: "asc" });
});

test("clé des filtres stable et vide sans filtre (la même que celle des données embarquées par le serveur)", () => {
  const params = screenerParams(filtersFromParams(new URLSearchParams("sector=Luxe&q=a")), { id: "name", desc: false });
  expect(filtersKey(params)).toBe("q=a&sector=Luxe");
  expect(filtersKey({ sort: "name", order: "asc" })).toBe("");
});

test("paramètres invalides ignorés", () => {
  expect(filtersFromParams(new URLSearchParams("minScore=abc")).minScore).toBeNull();
});
