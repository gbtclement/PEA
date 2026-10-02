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
