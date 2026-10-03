import { expect, test } from "@playwright/test";

// HTML préparé par l'API (bloc F) : ce que lit un robot qui n'exécute pas le JavaScript.
const anonymous = { storageState: { cookies: [], origins: [] } };

async function firstStock(request: import("@playwright/test").APIRequestContext) {
  const page = await (await request.get("/api/screener?kind=stock&region=europe&limit=1")).json();
  return page.items[0] as { id: number; name: string };
}

test.describe("visiteur", () => {
  test.use(anonymous);

  test("la fiche d'un titre arrive complète sans JavaScript", async ({ request }) => {
    const stock = await firstStock(request);
    const response = await request.get(`/titres/${stock.id}`);
    expect(response.status()).toBe(200);
    const html = await response.text();
    expect(html).toMatch(/<title>[^<]+ — cours, score et analyse \| Cotalyx<\/title>/);
    expect(html).toMatch(/<meta name="description" content="[^"]+"/);
    expect(html).toContain(`/titres/${stock.id}"`);
    expect(html).toContain('<link rel="canonical"');
    expect(html).toContain('application/ld+json');
    const root = html.split('<div id="root">')[1];
    expect(root).toContain("<h1>");
    expect(html).toContain('id="cotalyx-data"');
  });

  test("un titre inconnu répond 404 et n'est pas indexé", async ({ request }) => {
    const response = await request.get("/titres/99999999");
    expect(response.status()).toBe(404);
    expect(await response.text()).toContain('content="noindex, nofollow"');
  });

  test("les réponses publiques de l'API se gardent en cache, avec empreinte", async ({ request }) => {
    const first = await request.get("/api/rankings/top");
    expect(first.headers()["cache-control"]).toBe("public, max-age=60");
    const again = await request.get("/api/rankings/top", { headers: { "If-None-Match": first.headers()["etag"] } });
    expect(again.status()).toBe(304);
  });

  test("le titre servi est celui que l'application affiche", async ({ page, request }) => {
    const stock = await firstStock(request);
    const served = (await (await request.get(`/titres/${stock.id}`)).text()).match(/<title>([^<]+)<\/title>/)?.[1];
    const refetches: string[] = [];
    page.on("request", (r) => { if (new URL(r.url()).pathname === `/api/securities/${stock.id}`) refetches.push(r.url()); });
    await page.goto(`/titres/${stock.id}`);
    await expect(page.getByText("Score mixte")).toBeVisible();
    expect(refetches, "les données embarquées servent la fiche sans requête").toEqual([]);
    // document.title fusionne les espaces consécutifs (règle du navigateur)
    expect(await page.title()).toBe(served?.replaceAll("&amp;", "&").replace(/\s+/g, " ").trim());
  });
});

test("une page privée ne reçoit pas de HTML préparé", async ({ request }) => {
  const html = await (await request.get("/portefeuille")).text();
  expect(html).not.toContain('id="cotalyx-data"');
});

test("l'Explorer charge la suite de la liste en défilant", async ({ page }) => {
  await page.goto("/explorer");
  await expect(page.getByRole("row").nth(1)).toBeVisible();
  await page.mouse.move(720, 500);
  const next = page.waitForRequest((r) => r.url().includes("/api/screener?") && r.url().includes("offset=50"));
  for (let i = 0; i < 40; i++) {
    await page.mouse.wheel(0, 2000);
    await page.waitForTimeout(100);
  }
  await next;
});
