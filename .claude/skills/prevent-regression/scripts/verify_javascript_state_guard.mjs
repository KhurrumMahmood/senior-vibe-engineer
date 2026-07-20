#!/usr/bin/env node
/** Verify the staged JavaScript guard's bad/good fixture contract. */
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

function fail(message) { throw new Error(message); }
function parse(argv) {
  const options = { bad: [], good: [] };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index]; const value = argv[index + 1];
    if (!flag?.startsWith("--") || value === undefined) fail("usage: verify_javascript_state_guard.mjs --rule <mjs> --bad <file>... --good <file>...");
    if (flag === "--rule") options.rule = value;
    else if (flag === "--bad") options.bad.push(value);
    else if (flag === "--good") options.good.push(value);
    else fail(`unknown option: ${flag}`);
  }
  if (!options.rule || !options.bad.length || !options.good.length) fail("rule plus bad and good fixtures are required");
  for (const file of [options.rule, ...options.bad, ...options.good]) if (!fs.existsSync(file)) fail(`file not found: ${file}`);
  return options;
}
function run(rule, files) { return spawnSync("node", [rule, "--fixture", ...files.map((file) => path.resolve(file))], { encoding: "utf8" }); }
function main() {
  const args = parse(process.argv.slice(2));
  const bad = run(path.resolve(args.rule), args.bad); const good = run(path.resolve(args.rule), args.good);
  const badHits = bad.stdout.split(/\r?\n/).filter(Boolean).length; const goodHits = good.stdout.split(/\r?\n/).filter(Boolean).length;
  process.stdout.write(`bad   : rc=${bad.status} hits=${badHits}\n`); process.stdout.write(`good  : rc=${good.status} hits=${goodHits}\n`);
  const everyBadFires = args.bad.every((file) => run(path.resolve(args.rule), [file]).status === 1);
  const everyGoodPasses = args.good.every((file) => run(path.resolve(args.rule), [file]).status === 0);
  if (bad.status !== 1 || badHits < 4 || good.status !== 0 || goodHits !== 0 || !everyBadFires || !everyGoodPasses) { process.stdout.write("FAIL: expected bad findings and clean good fixtures.\n"); process.exitCode = 1; return; }
  process.stdout.write("PASS: BAD_RC=1, GOOD_RC=0 across JS/JSX/MJS/CJS fixtures.\n");
}
try { main(); } catch (error) { process.stderr.write(`error: ${error.message}\n`); process.exitCode = 2; }
