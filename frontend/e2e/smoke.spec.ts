import { expect, test } from "@playwright/test";

test("accueil, explorateur et fiche s'affichent", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Accueil" })).toBeVisible();
  await expect(page.getByText("Top 10 du moment")).toBeVisible();

  await page.getByRole("link", { name: "Explorer" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Explorer" })).toBeVisible();
  await page.getByRole("searchbox", { name: "Rechercher" }).fill("LVMH");
  await page.getByRole("row").filter({ hasText: "LVMH" }).first().click();

  await expect(page.getByRole("heading", { level: 1, name: /LVMH/i })).toBeVisible();
  await expect(page.getByText("Score mixte")).toBeVisible();
});
