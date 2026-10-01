import { expect, test, type Page } from "@playwright/test";

const PRIVATE = ["/portefeuille", "/assistant", "/reglages"];
const NOINDEX = [...PRIVATE, "/previsions", "/page-inconnue", "/verifier-email?adresse=a%40b.fr", "/mot-de-passe-oublie",
                 "/accepter-cgu", "/desinscription"];
const AUTH = ["/connexion", "/inscription"];

async function headings(page: Page) {
  return page.evaluate(() => [...document.querySelectorAll("h1, h2, h3, h4, h5, h6")].map((h) => ({ level: Number(h.tagName[1]), text: h.textContent?.trim() ?? "" })));
}

test("structure et métadonnées de chaque page", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/explorer");
  await page.getByRole("row").nth(1).click();
  await expect(page.getByText("Score mixte")).toBeVisible();
  const security = new URL(page.url()).pathname;

  for (const path of ["/", "/explorer", "/etf", ...AUTH, ...NOINDEX, security]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");

    const list = await headings(page);
    expect(list.filter((h) => h.level === 1), `${path} : un seul h1`).toHaveLength(1);
    list.forEach((h, i) => {
      if (i > 0) expect(h.level - list[i - 1].level, `${path} : niveau sauté avant « ${h.text} »`).toBeLessThanOrEqual(1);
    });

    expect(await page.title()).toMatch(/PEA Radar$/);
    expect(await page.locator('meta[name="description"]').getAttribute("content")).toBeTruthy();
    expect(await page.locator('link[rel="canonical"]').getAttribute("href")).toMatch(new RegExp(`${path === "/" ? "/$" : path.split("?")[0]}$`));
    const robots = await page.evaluate(() => document.querySelector('meta[name="robots"]')?.getAttribute("content") ?? null);
    expect(robots, `${path} : indexation`).toBe(NOINDEX.includes(path) ? "noindex, nofollow" : null);
    for (const selector of ["main", "nav", "footer"]) await expect(page.locator(selector)).toHaveCount(1);
  }
});

test("robots.txt, sitemap.xml et llms.txt servis à la racine", async ({ request }) => {
  const robots = await request.get("/robots.txt");
  expect(robots.ok()).toBeTruthy();
  expect(await robots.text()).toContain("Disallow: /");

  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.headers()["content-type"]).toContain("xml");
  const xml = await sitemap.text();
  expect(xml).toContain("<urlset");
  expect(xml).toContain("/explorer</loc>");
  expect(xml).toMatch(/\/titres\/\d+<\/loc>/);
  expect(xml).not.toContain("/portefeuille");

  const llms = await request.get("/llms.txt");
  expect(await llms.text()).toMatch(/^# PEA Radar/);
});
