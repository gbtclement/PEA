import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { request, type FullConfig } from "@playwright/test";

export const E2E_EMAIL = "e2e@pea-radar.test";
export const E2E_PASSWORD = "motdepasse-e2e-123";
export const STATE = "e2e/.auth/user.json";

/** Compte de test validé (créé dans le conteneur api), connecté une fois pour toutes les pages privées. */
export default async function globalSetup(config: FullConfig) {
  execFileSync("docker", ["compose", "exec", "-T", "api", "python", "-m", "app.cli", "ensure-user", "--email", E2E_EMAIL,
                          "--password", E2E_PASSWORD, "--first-name", "Test", "--last-name", "E2E", "--admin"],
               { cwd: "..", stdio: "inherit" });
  mkdirSync("e2e/.auth", { recursive: true });
  const context = await request.newContext({ baseURL: config.projects[0].use.baseURL });
  const response = await context.post("/api/auth/login", { data: { email: E2E_EMAIL, password: E2E_PASSWORD, remember: true } });
  if (!response.ok()) throw new Error(`Connexion du compte e2e impossible : ${response.status()}`);
  await context.storageState({ path: STATE });
  await context.dispose();
}
