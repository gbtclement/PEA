// Mesure Lighthouse (mode téléphone) des pages publiques : performances, accessibilité, bonnes pratiques, SEO.
// Usage : npm run lighthouse   (application lancée sur http://localhost:8095, ou LIGHTHOUSE_BASE_URL)
// Le SEO n'atteint 100 que si l'indexation est permise (SEO_INDEXING=true), sinon robots.txt interdit tout.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { chromium } from "@playwright/test";

const BASE = process.env.LIGHTHOUSE_BASE_URL ?? "http://localhost:8095";
const TARGET = 95;
const CATEGORIES = ["performance", "accessibility", "best-practices", "seo"];

const page = await (await fetch(`${BASE}/api/screener?kind=stock&region=europe&limit=1`)).json();
const pages = ["/", "/explorer", `/titres/${page.items[0].id}`];
const out = mkdtempSync(path.join(tmpdir(), "lighthouse-"));
let failed = false;

for (const pagePath of pages) {
  const report = path.join(out, `${pagePath.replaceAll("/", "_") || "_"}.json`);
  execFileSync("npx", ["--yes", "lighthouse@12", `${BASE}${pagePath}`, "--quiet", "--output=json", `--output-path=${report}`,
    `--only-categories=${CATEGORIES.join(",")}`, "--chrome-flags=--headless=new --no-sandbox"],
    { env: { ...process.env, CHROME_PATH: chromium.executablePath() }, stdio: ["ignore", "ignore", "inherit"], shell: process.platform === "win32" });
  const result = JSON.parse(readFileSync(report, "utf8"));
  const scores = CATEGORIES.map((c) => Math.round(result.categories[c].score * 100));
  console.log(`${pagePath.padEnd(16)} ${CATEGORIES.map((c, i) => `${c} ${scores[i]}`).join(" · ")}`);
  for (const [i, category] of CATEGORIES.entries()) {
    if (scores[i] >= TARGET) continue;
    failed = true;
    for (const ref of result.categories[category].auditRefs) {
      const audit = result.audits[ref.id];
      if (ref.weight > 0 && audit.score !== null && audit.score < 0.9) {
        console.log(`    ${category} : ${audit.title}${audit.displayValue ? ` (${audit.displayValue})` : ""}`);
      }
    }
  }
}
console.log(failed ? `Sous l'objectif (${TARGET}) : voir les points ci-dessus.` : `Toutes les notes atteignent ${TARGET}.`);
process.exit(failed ? 1 : 0);
