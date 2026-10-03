import { expect, test, type Page } from "@playwright/test";

// Téléphones : 390 px (iPhone récent) et 360 px (Android courant). Hauteur réduite = clavier ouvert.
const PHONES = [{ width: 390, height: 844 }, { width: 360, height: 780 }];

async function problems(page: Page) {
  return page.evaluate(() => {
    const found: string[] = [];
    if (document.documentElement.scrollWidth > window.innerWidth) {
      found.push(`page plus large que l'écran (${document.documentElement.scrollWidth} > ${window.innerWidth})`);
    }
    document.querySelectorAll<HTMLElement>("[data-slot=card], li, [role=toolbar]").forEach((el) => {
      const box = el.getBoundingClientRect();
      if (box.width > 0 && box.right > window.innerWidth + 1) found.push(`« ${el.textContent?.slice(0, 30)} » coupé à droite`);
    });
    document.querySelectorAll<HTMLElement>("a, button").forEach((el) => {
      if (el.tagName === "A" && el.closest("p, label, li > span, dd")) return;  // lien dans une phrase : exempté (WCAG 2.5.8)
      const box = el.getBoundingClientRect();
      if (box.width > 0 && box.height > 0 && box.height < 32 && el.closest("main, header, [role=toolbar]")) {
        const name = (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 30)
          || `<${el.tagName.toLowerCase()} class="${el.className.toString().slice(0, 60)}">`;
        found.push(`zone tactile trop petite : « ${name} » (${Math.round(box.height)} px)`);
      }
    });
    return found;
  });
}

for (const phone of PHONES) {
  test(`toutes les pages hors Admin à ${phone.width} px`, async ({ page }) => {
    await page.setViewportSize(phone);
    await page.goto("/explorer");
    await page.locator("main a[href^='/titres/']").first().click();
    await expect(page.getByText("Score mixte")).toBeVisible();
    const security = new URL(page.url()).pathname;
    for (const path of ["/", "/explorer", "/explorer?region=us", "/etf", "/previsions", "/previsions?vue=statistiques",
                        "/previsions?vue=bulletin", "/portefeuille", "/assistant", "/reglages", "/premium", "/cgu",
                        "/mentions-legales", "/connexion", "/inscription", security]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(await page.getByRole("heading", { level: 1 }).count(), `${path} : un seul h1`).toBe(1);
      expect.soft(await problems(page), `${path} à ${phone.width} px`).toEqual([]);
    }
  });
}

test("menu mobile : ouvrir, naviguer, refermé", async ({ page }) => {
  await page.setViewportSize(PHONES[0]);
  await page.goto("/");
  await page.getByRole("button", { name: "Ouvrir le menu" }).click();
  await page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "ETF" }).click();
  await expect(page).toHaveURL(/\/etf$/);
  await expect(page.getByRole("navigation", { name: "Navigation principale" })).toBeHidden();
});

test("clavier ouvert : la saisie de l'assistant reste visible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 664 });
  await page.goto("/assistant");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const box = page.getByRole("textbox", { name: "Votre question" });
  test.skip(await box.count() === 0, "assistant non configuré sur ce serveur (clé Claude absente)");
  await box.focus();
  await expect(box).toBeInViewport();
});

test("clavier ouvert : un champ du bas d'une fenêtre plein écran reste atteignable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 664 });
  await page.goto("/portefeuille");
  await page.getByRole("button", { name: /Nouvel ordre|Ajouter mon premier ordre/ }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box?.width).toBeGreaterThanOrEqual(380);  // plein écran (à l'arrondi près)
  const note = dialog.getByRole("textbox").last();
  await note.focus();
  await expect(note).toBeInViewport();
});

test("fiche sur téléphone : barre d'actions dans l'écran, pied de page lisible au-dessus", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto("/explorer");
  await page.locator("main a[href^='/titres/']").first().click();
  const bar = page.getByRole("toolbar", { name: "Actions sur ce titre" });
  await expect(bar).toBeVisible();
  for (const button of await bar.getByRole("button").all()) {
    const box = await button.boundingBox();
    expect(box!.x + box!.width, "bouton de la barre coupé à droite").toBeLessThanOrEqual(360);
  }
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const legal = page.getByRole("contentinfo").getByRole("link", { name: "CGU" });
  const barTop = (await bar.boundingBox())!.y;
  const legalBox = (await legal.boundingBox())!;
  expect(legalBox.y + legalBox.height, "liens légaux cachés par la barre").toBeLessThanOrEqual(barTop);
});
