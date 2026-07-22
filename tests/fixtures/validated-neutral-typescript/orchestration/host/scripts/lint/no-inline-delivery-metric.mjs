import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";

const root = new URL("../../src/", import.meta.url);
const canonical = "metrics/delivery.ts";
const violations = [];

async function visit(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      await visit(path);
    } else if (entry.name.endsWith(".ts")) {
      const rel = relative(root.pathname, path);
      const text = await readFile(path, "utf8");
      if (rel !== canonical && /[`'"]delivery\./.test(text)) {
        violations.push(rel);
      }
    }
  }
}

await visit(root.pathname);
if (violations.length > 0) {
  console.error(`inline delivery metric names: ${violations.join(", ")}`);
  process.exitCode = 1;
}
