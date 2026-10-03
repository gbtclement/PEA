// Génère l'image de partage (Open Graph, 1200×630) et l'icône Apple (180×180) à partir du logo, avec Chromium.
// Usage : node scripts/make-images.mjs (à relancer si le logo ou le slogan change).
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const logo = readFileSync("public/favicon.svg", "utf8");
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
await page.setContent(`<html><body style="margin:0;font-family:Inter,system-ui,sans-serif">
  <div style="width:1200px;height:630px;display:flex;flex-direction:column;justify-content:center;padding:0 96px;box-sizing:border-box;
              background:linear-gradient(135deg,#eef2ff 0%,#ffffff 60%)">
    <div style="display:flex;align-items:center;gap:28px">
      <div style="width:120px;height:120px">${logo.replace("<svg", '<svg width="120" height="120"')}</div>
      <div style="font-size:96px;font-weight:700;color:#18181b;letter-spacing:-2px">Cotalyx</div>
    </div>
    <div style="margin-top:36px;font-size:40px;color:#3f3f46;line-height:1.35;max-width:980px">
      Top 10 des actions et ETF, score expliqué, graphiques et simulateur.
    </div>
    <div style="margin-top:28px;font-size:26px;color:#71717a">Outil d'aide à la décision, pas un conseil en investissement.</div>
  </div></body></html>`);
await page.screenshot({ path: "public/og-image.png" });
await page.setViewportSize({ width: 180, height: 180 });
await page.setContent(`<html><body style="margin:0;background:#ffffff;display:flex;align-items:center;justify-content:center;width:180px;height:180px">
  ${logo.replace("<svg", '<svg width="140" height="140"')}</body></html>`);
await page.screenshot({ path: "public/apple-touch-icon.png" });
await browser.close();
console.log("public/og-image.png et public/apple-touch-icon.png générés");
