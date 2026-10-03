import { createQueryClient, seedFromPage } from "./queryClient";

afterEach(() => { document.body.innerHTML = ""; });

function embed(text: string) {
  const script = document.createElement("script");
  script.id = "cotalyx-data";
  script.type = "application/json";
  script.textContent = text;
  document.body.appendChild(script);
}

test("les données embarquées dans la page remplissent le cache des requêtes", () => {
  embed(JSON.stringify([[["me"], null], [["security", "7"], { id: 7, name: "LVMH" }]]));
  const client = createQueryClient();
  seedFromPage(client);
  expect(client.getQueryData(["me"])).toBeNull();
  expect(client.getQueryData(["security", "7"])).toEqual({ id: 7, name: "LVMH" });
});

test("des données illisibles sont ignorées sans casser l'application", () => {
  embed("{pas du json");
  const client = createQueryClient();
  expect(() => seedFromPage(client)).not.toThrow();
  expect(client.getQueryData(["me"])).toBeUndefined();
});
