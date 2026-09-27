import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const SITES = [
  { path: "/guide/", title: "Bienvenue dans PEA Radar", minPages: 20 },
  { path: "/documentation/", title: "Documentation admin", minPages: 15 },
];

test("la barre latérale ouvre le guide, pas la documentation admin", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("a[href^='/documentation']")).toHaveCount(0);
  await page.getByRole("link", { name: "Guide" }).click();
  await expect(page).toHaveURL(/\/guide\/(#\/)?$/);
  await expect(page.locator(".markdown-section h1")).toHaveText("Bienvenue dans PEA Radar");
});

for (const site of SITES) {
  test(`${site.path} : l'adresse sans barre finale redirige`, async ({ page }) => {
    await page.goto(site.path.slice(0, -1));
    await expect(page).toHaveURL(new RegExp(`${site.path}(#/)?$`));
    await expect(page.locator(".markdown-section h1")).toHaveText(site.title);
  });

  test(`${site.path} : chaque page du menu s'affiche, sans lien interne cassé`, async ({ page, request }) => {
    await checkEveryPage(page, request, site.path, site.minPages);
  });
}

test("le retour à l'application fonctionne", async ({ page }) => {
  await page.goto("/guide/#/premiers-pas");
  await page.getByRole("link", { name: "← Retour à l'application" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Accueil" })).toBeVisible();
});

test("la documentation admin n'est pas indexée", async ({ request }) => {
  const html = await (await request.get("/documentation/")).text();
  expect(html).toContain('name="robots" content="noindex');
});

async function checkEveryPage(page: Page, request: APIRequestContext, base: string, minPages: number) {
  await page.goto(base);
  const links = page.locator(".sidebar-nav a[href^='#/']");
  await expect(links.first()).toBeVisible();
  const hrefs = await links.evaluateAll((items) => [...new Set(items.map((a) => a.getAttribute("href") ?? ""))]);
  expect(hrefs.length).toBeGreaterThanOrEqual(minPages);

  const targets = new Set<string>();
  for (const href of hrefs) {
    await page.goto(`${base}${href}`);
    await expect(page.locator(".markdown-section h1"), href).toBeVisible();
    await expect(page.locator(".markdown-section"), href).not.toContainText("404 - Not found");
    for (const target of await page.locator(".markdown-section a[href^='#/']").evaluateAll((items) =>
      items.map((a) => (a.getAttribute("href") ?? "").split("?")[0]),
    )) {
      targets.add(target);
    }
  }
  // Les liens entre pages pointent vers des fichiers qui existent
  for (const target of targets) {
    const path = target.replace(/^#\//, "") || "README";
    const file = path.endsWith(".md") ? path : `${path}.md`;
    const response = await request.get(`${base}${file}`);
    expect(response.status(), `${base}${target} → ${file}`).toBe(200);
  }
}
