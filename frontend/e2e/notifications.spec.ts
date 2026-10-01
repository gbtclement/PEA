import { expect, test } from "@playwright/test";

test("réglages des notifications gardés après rechargement", async ({ page }) => {
  await page.goto("/reglages#notifications");
  const recap = page.getByRole("switch", { name: /Récap du soir/ });
  const before = await recap.isChecked();
  await recap.click();
  await expect(recap).toBeChecked({ checked: !before });
  await page.reload();
  await expect(page.getByRole("switch", { name: /Récap du soir/ })).toBeChecked({ checked: !before });
  await page.getByRole("switch", { name: /Récap du soir/ }).click();  // remet l'état de départ
});

test("alerte créée sur une fiche, retrouvée puis supprimée dans les réglages", async ({ page }) => {
  await page.goto("/explorer");
  await page.getByRole("row").nth(1).click();
  await page.waitForURL(/\/titres\//);
  const name = (await page.getByRole("heading", { level: 1 }).textContent())!.trim();
  await page.getByRole("button", { name: "Créer une alerte" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Quand le cours passe").selectOption("above");
  const price = dialog.getByLabel(/Prix/);
  const current = Number((await price.inputValue()).replace(",", "."));
  await price.fill(String(Math.ceil(current * 2)).replace(".", ","));
  await dialog.getByRole("button", { name: "Créer l'alerte" }).click();
  await expect(dialog).toBeHidden();
  await page.goto("/reglages#notifications");
  const remove = page.getByRole("button", { name: `Supprimer l'alerte sur ${name}` }).first();
  await expect(remove).toBeVisible();
  await remove.click();
  await expect(page.getByRole("button", { name: `Supprimer l'alerte sur ${name}` })).toHaveCount(0);
});
