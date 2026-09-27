import { expect, test } from "@playwright/test";

// Barres de défilement visibles, comme sous Windows (Chromium les masque par défaut en mode headless).
test.use({ launchOptions: { ignoreDefaultArgs: ["--hide-scrollbars"] } });

// Les titres de colonnes doivent tomber exactement au-dessus des valeurs, barre de défilement comprise.
for (const width of [1100, 1440]) {
  for (const path of ["/explorer", "/etf"]) {
    test(`${path} : titres de colonnes alignés sur les valeurs à ${width} px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(path);
      await expect(page.getByRole("row").nth(1)).toBeVisible();
      const gaps = await page.evaluate(() => {
        const headers = [...document.querySelectorAll("[role=columnheader]")];
        const cells = [...document.querySelectorAll("[role=row]")[1].querySelectorAll("[role=cell]")];
        return headers.map((h, i) => {
          const a = h.getBoundingClientRect();
          const b = cells[i].getBoundingClientRect();
          return { column: h.textContent, left: Math.round(a.left - b.left), right: Math.round(a.right - b.right) };
        }).filter((g) => g.left !== 0 || g.right !== 0);
      });
      expect(gaps).toEqual([]);
    });
  }
}

// Deux colonnes voisines ne doivent jamais se toucher (ex. « +24,82 %+112,94 % »).
for (const width of [1280, 1440]) {
  test(`/explorer : au moins 6 px entre deux colonnes à ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/explorer");
    await expect(page.getByRole("row").nth(1)).toBeVisible();
    const tooClose = await page.evaluate(() => {
      const contentBox = (el: Element) => {
        const range = document.createRange();
        range.selectNodeContents(el);
        return range.getBoundingClientRect();
      };
      const problems: string[] = [];
      for (const row of [...document.querySelectorAll("[role=row]")].slice(0, 30)) {
        const cells = [...row.querySelectorAll("[role=cell], [role=columnheader]")].filter((c) => c.textContent?.trim());
        for (let i = 1; i < cells.length; i++) {
          const gap = contentBox(cells[i]).left - contentBox(cells[i - 1]).right;
          if (gap < 6) problems.push(`« ${cells[i - 1].textContent} » / « ${cells[i].textContent} » : ${Math.round(gap)} px`);
        }
      }
      return [...new Set(problems)].slice(0, 10);
    });
    expect(tooClose).toEqual([]);
  });
}
