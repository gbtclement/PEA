import { expect, test } from "@playwright/test";

test.use({ storageState: { cookies: [], origins: [] } });

async function lastCode(request: import("@playwright/test").APIRequestContext, to: string): Promise<string> {
  for (let i = 0; i < 20; i++) {
    const list = await (await request.get(`http://localhost:8025/api/v1/search?query=to:${encodeURIComponent(to)}`)).json();
    const subject: string | undefined = list.messages?.[0]?.Subject;
    const code = subject?.match(/\b(\d{6})\b/)?.[1];
    if (code) return code;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("Aucun code reçu dans Mailpit");
}

test("inscription, code reçu par mail, déconnexion puis connexion", async ({ page, request }) => {
  const email = `e2e-${Date.now()}@pea-radar.test`;
  await page.goto("/inscription");
  await page.getByLabel("Prénom").fill("Élodie");
  await page.getByLabel("Nom").fill("Test");
  await page.getByLabel("Adresse mail").fill(email);
  await page.getByLabel("Mot de passe", { exact: true }).fill("motdepasse-solide-e2e");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Créer mon compte" }).click();
  await expect(page).toHaveURL(/verifier-email/);
  await page.getByLabel("Code à 6 chiffres").fill(await lastCode(request, email));
  await page.getByRole("button", { name: "Valider" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Accueil" })).toBeVisible();
  await page.getByRole("button", { name: "Se déconnecter" }).click();
  await page.goto("/portefeuille");
  await expect(page).toHaveURL(/\/connexion\?suite=%2Fportefeuille/);
  await page.getByLabel("Adresse mail").fill(email);
  await page.getByLabel("Mot de passe", { exact: true }).fill("motdepasse-solide-e2e");
  await page.getByRole("button", { name: "Me connecter" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Portefeuille" })).toBeVisible();
});

test("le panneau glisse et l'URL suit", async ({ page }) => {
  await page.goto("/inscription");
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/connexion$/);
  await expect(page.getByRole("heading", { level: 1, name: "Se connecter" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { level: 1, name: "Créer un compte" })).toBeVisible();
});

test("un visiteur voit la vitrine", async ({ page }) => {
  await page.goto("/explorer");
  await expect(page.getByRole("heading", { level: 1, name: "Explorer" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Créer un compte gratuit" })).toBeVisible();
});
