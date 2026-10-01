import { expect, test } from "@playwright/test";

test("admin : Premium offert, prévisions ouvertes", async ({ page }) => {
  await page.goto("/premium");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Cotalyx Premium/);
  await expect(page.getByText("L'abonnement arrive bientôt.")).toBeVisible();
  await page.goto("/previsions");
  await expect(page.getByRole("button", { name: "Prédictions" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("Réservé aux membres Premium")).toHaveCount(0);
});

test("réglages : carte Abonnement", async ({ page }) => {
  await page.goto("/reglages#abonnement");
  await expect(page.getByRole("heading", { name: "Abonnement" })).toBeVisible();
  await expect(page.getByText("Premium vous est offert.")).toBeVisible();
});

test("visiteur : CGV et page Premium publiques", async ({ browser }) => {
  const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const page = await context.newPage();
  await page.goto("/cgv");
  await expect(page.getByRole("heading", { level: 1, name: "Conditions générales de vente" })).toBeVisible();
  await page.goto("/premium");
  await expect(page.getByText("L'abonnement arrive bientôt.")).toBeVisible();
  await context.close();
});
