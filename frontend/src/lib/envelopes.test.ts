import { filteringEnvelopes } from "./envelopes";

test("le compte-titres ou l'absence de choix veut dire tous les titres", () => {
  expect(filteringEnvelopes([])).toEqual([]);
  expect(filteringEnvelopes(["pea", "cto"])).toEqual([]);
  expect(filteringEnvelopes(["pea_pme", "pea"])).toEqual(["pea", "pea_pme"]);
});
