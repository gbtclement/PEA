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

test("portefeuille et compteur d'ordres", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Portefeuille" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Portefeuille" })).toBeVisible();
  await expect(page.getByText(/\d+\/\d+ ordres en \d{4}/)).toBeVisible();
  await page.getByRole("button", { name: "+ Nouvel ordre" }).click();
  await expect(page.getByRole("dialog")).toContainText("Nouvel ordre");
});

test("assistant, réglages du compte et onglet Admin", async ({ page }) => {
  await page.goto("/assistant");
  await expect(page.getByRole("heading", { level: 1, name: "Assistant IA" })).toBeVisible();
  await page.goto("/reglages");
  await expect(page.getByText("Appareils connectés", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Cet appareil")).toBeVisible();
  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Admin" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "e2e@example.com" })).toBeVisible();
  await expect(page.getByRole("list", { name: "État de la configuration" })).toBeVisible();
});
