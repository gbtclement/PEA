// Budget du premier affichage de l'accueil : JavaScript compressé chargé pour « / » (entrée + accueil + leurs imports
// statiques ; les imports dynamiques — graphiques, autres pages — ne comptent pas). Lit dist/.vite/manifest.json.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

// 150 Ko : React 19, le routeur, le cache de requêtes et la fusion de classes forment ~140 Ko incompressibles.
const BUDGET_KB = Number(process.env.BUNDLE_BUDGET_KB ?? 150);
const manifest = JSON.parse(readFileSync("dist/.vite/manifest.json", "utf8"));
const seen = new Set();

function collect(key) {
  const chunk = manifest[key];
  if (!chunk || seen.has(key)) return;
  seen.add(key);
  for (const dep of chunk.imports ?? []) collect(dep);
}

collect("index.html");
const home = Object.keys(manifest).find((key) => key.endsWith("features/home/HomePage.tsx"));
collect(home);
let total = 0;
for (const key of seen) {
  const size = gzipSync(readFileSync(`dist/${manifest[key].file}`)).length;
  total += size;
  console.log(`${(size / 1024).toFixed(1).padStart(7)} Ko  ${manifest[key].file}`);
}
console.log(`${(total / 1024).toFixed(1).padStart(7)} Ko  total pour « / » (budget ${BUDGET_KB} Ko)`);
process.exit(total / 1024 > BUDGET_KB ? 1 : 0);
