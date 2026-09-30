import { expect, test } from "@playwright/test";

test.describe("visiteur", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("la documentation admin renvoie un visiteur vers la connexion", async ({ page }) => {
    await page.goto("/documentation/");
    await expect(page).toHaveURL(/\/connexion\?suite=%2Fdocumentation%2F$/);
  });

  test("la documentation admin refuse aussi ses fichiers à un visiteur", async ({ request }) => {
    const response = await request.get("/documentation/README.md", { maxRedirects: 0 });
    expect(response.status()).toBe(302);
  });

  test("le guide et les fichiers Docsify communs restent publics", async ({ request }) => {
    expect((await request.get("/guide/")).status()).toBe(200);
    expect((await request.get("/docsify/theme.css")).status()).toBe(200);
  });

  test("un visiteur ne voit pas l'onglet Admin", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
  });
});

test("un admin lit la documentation admin, jamais mise en cache", async ({ request }) => {
  const response = await request.get("/documentation/README.md");
  expect(response.status()).toBe(200);
  expect(response.headers()["cache-control"]).toBe("no-store");
  expect(response.headers()["x-frame-options"]).toBe("DENY");
});
