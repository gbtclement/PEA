import { expect, test } from "@playwright/test";

test("en-têtes de sécurité sur l'application", async ({ request }) => {
  const headers = (await request.get("/")).headers();
  expect(headers["content-security-policy"]).toContain("default-src 'self'");
  expect(headers["content-security-policy"]).toContain("https://challenges.cloudflare.com");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["permissions-policy"]).toContain("camera=()");
  expect(headers["strict-transport-security"]).toBeUndefined(); // HTTP en local
  const asset = (await request.get("/")).text();
  const script = (await asset).match(/\/assets\/[^"]+\.js/)?.[0];
  expect((await request.get(script!)).headers()["x-content-type-options"]).toBe("nosniff"); // aussi sous /assets/
});

for (const path of ["/", "/explorer", "/connexion", "/inscription", "/guide/", "/documentation/"]) {
  test(`aucune violation CSP sur ${path}`, async ({ page }) => {
    const violations: string[] = [];
    page.on("console", (message) => { if (/Content Security Policy/i.test(message.text())) violations.push(message.text()); });
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(violations).toEqual([]);
  });
}
