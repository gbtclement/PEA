import { expect, test } from "@playwright/test";

test("la barre latérale ouvre la documentation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Documentation" }).click();
  await expect(page).toHaveURL(/\/documentation\/(#\/)?$/);
  await expect(page.locator(".markdown-section h1")).toHaveText("PEA Radar");
});

test("/documentation sans barre finale redirige vers la documentation", async ({ page }) => {
  await page.goto("/documentation");
  await expect(page).toHaveURL(/\/documentation\/(#\/)?$/);
  await expect(page.locator(".sidebar-nav")).toBeVisible();
});

test("chaque page du menu s'affiche avec un titre, sans lien interne cassé", async ({ page, request }) => {
  await page.goto("/documentation/");
  const links = page.locator(".sidebar-nav a[href^='#/']");
  await expect(links.first()).toBeVisible();
  const hrefs = await links.evaluateAll((items) => [...new Set(items.map((a) => a.getAttribute("href") ?? ""))]);
  expect(hrefs.length).toBeGreaterThanOrEqual(20);

  const mdLinks = new Set<string>();
  for (const href of hrefs) {
    await page.goto(`/documentation/${href}`);
    await expect(page.locator(".markdown-section h1"), href).toBeVisible();
    await expect(page.locator(".markdown-section"), href).not.toContainText("404 - Not found");
    for (const target of await page.locator(".markdown-section a[href^='#/']").evaluateAll((items) =>
      items.map((a) => (a.getAttribute("href") ?? "").split("?")[0]),
    )) {
      mdLinks.add(target);
    }
  }
  // Les liens entre pages pointent vers des fichiers qui existent
  for (const target of mdLinks) {
    const path = target.replace(/^#\//, "") || "README";
    const file = path.endsWith(".md") ? path : `${path}.md`;
    const response = await request.get(`/documentation/${file}`);
    expect(response.status(), `${target} → ${file}`).toBe(200);
  }
});

test("le retour à l'application fonctionne", async ({ page }) => {
  await page.goto("/documentation/#/guide/demarrer");
  await page.getByRole("link", { name: "← Retour à l'application" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Accueil" })).toBeVisible();
});
