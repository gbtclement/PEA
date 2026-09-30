import { expect, test } from "@playwright/test";

test("pages légales publiques, complètes et indexables", async ({ page }) => {
  for (const [path, title] of [["/cgu", "Conditions générales d'utilisation"], ["/confidentialite", "Politique de confidentialité"],
                               ["/mentions-legales", "Mentions légales"]]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(page.locator('meta[name="robots"][content*="noindex"]')).toHaveCount(0);  // indexable : pas de noindex
  }
});

test("export des données depuis les réglages", async ({ page }) => {
  await page.goto("/reglages#mes-donnees");
  const card = page.locator("#mes-donnees");
  const button = card.getByRole("button", { name: "Exporter mes données" });
  const link = card.getByRole("link", { name: /Télécharger/ });
  await expect(button.or(link).first()).toBeVisible();  // carte chargée ; l'export du jour peut déjà exister (relance)
  if (!(await link.isVisible())) await button.click();
  await expect(link).toBeVisible({ timeout: 30_000 });  // worker : 15 s max
});
