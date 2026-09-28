import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  // Compte e2e connecté une fois (voir global-setup.ts) ; auth.spec.ts repart sans cookies
  globalSetup: "./e2e/global-setup.ts",
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8095", viewport: { width: 1440, height: 900 }, storageState: "e2e/.auth/user.json" },
});
