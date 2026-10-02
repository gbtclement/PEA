/// <reference types="node" />
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const DOC_DIRS = ["public/documentation", "public/guide", "public/guide/app", "public/guide/bourse"];

test("la documentation ne cite plus les anciens noms de cookies pea_*", () => {
  const hits = DOC_DIRS.flatMap((dir) =>
    readdirSync(dir).filter((f) => f.endsWith(".md")).map((f) => join(dir, f))
      .filter((path) => /\bpea_(session|csrf|device|oauth|google_pending)\b/.test(readFileSync(path, "utf8"))),
  );
  expect(hits).toEqual([]);
});

function allMarkdown(): [string, string][] {
  return ["public/guide", "public/documentation"].flatMap((dir) =>
    (readdirSync(dir, { recursive: true }) as string[]).filter((f) => f.endsWith(".md"))
      .map((f): [string, string] => [join(dir, f), readFileSync(join(dir, f), "utf8")]),
  );
}

test("le guide et la documentation ne parlent plus de l'ancien filtre d'éligibilité", () => {
  const docs = allMarkdown();
  expect(docs.length).toBeGreaterThan(20);
  for (const [path, text] of docs) {
    expect(text, path).not.toMatch(/Éligibles PEA uniquement|Éligibilité PEA — corrections|eligibility_override|\/eligibility\b|services\/eligibility/);
    expect(text, path).not.toMatch(/actions éligibles (au )?PEA (qui ont|les mieux)/i);
  }
});
