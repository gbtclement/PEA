import { expect, test, type Page } from "@playwright/test";

// Écran zoomé (125 %) ou fenêtre non maximisée : la page ne doit ni déborder à droite ni couper le contenu des cartes.
const WIDTHS = [1100, 1280, 1440];

async function clipped(page: Page) {
  return page.evaluate(() => {
    const problems: string[] = [];
    if (document.documentElement.scrollWidth > window.innerWidth) {
      problems.push(`page plus large que la fenêtre (${document.documentElement.scrollWidth} > ${window.innerWidth})`);
    }
    document.querySelectorAll<HTMLElement>("[data-slot=card]").forEach((card) => {
      const title = card.querySelector("[data-slot=card-title]")?.textContent ?? card.textContent?.slice(0, 30);
      const box = card.getBoundingClientRect();
      if (box.right > window.innerWidth + 1) problems.push(`carte « ${title} » coupée à droite`);
      if (card.scrollWidth > card.clientWidth + 1) problems.push(`contenu de « ${title} » plus large que la carte`);
    });
    return problems;
  });
}

async function firstSecurityPath(page: Page) {
  await page.goto("/explorer");
  await page.getByRole("row").nth(1).click();
  await expect(page.getByText("Score mixte")).toBeVisible();
  return new URL(page.url()).pathname;
}

for (const width of WIDTHS) {
  test(`mise en page sans coupure à ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const security = await firstSecurityPath(page);
    for (const path of ["/", "/explorer", "/etf", "/previsions", "/previsions?vue=statistiques", "/previsions?vue=bulletin",
                        "/portefeuille", "/assistant", "/reglages", "/connexion", "/inscription", security]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForLoadState("networkidle");
      if (path === security) {
        await page.getByRole("button", { name: "Simuler" }).click();
        await expect(page.getByText(/Valeur aujourd'hui|Pas assez|historique/i).first()).toBeVisible();
      }
      expect(await clipped(page), `${path} à ${width} px`).toEqual([]);
    }
  });
}

test("écrans de compte sans défilement horizontal sur mobile (390 px)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ["/connexion", "/inscription"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${path} à 390 px`).toBeLessThanOrEqual(0);
  }
});
