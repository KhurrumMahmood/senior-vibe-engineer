#!/usr/bin/env node
/** Verify the staged no-stringly-state guard's 0/1/2 fixture contract. */
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!flag?.startsWith("--") || value === undefined) {
      fail("usage: verify_typescript_state_guard.mjs --rule <mjs> --bad <ts> --bad-tsx <tsx> --good <ts> --good-tsx <tsx>");
    }
    options[flag.slice(2)] = value;
  }
  for (const key of ["rule", "bad", "bad-tsx", "good", "good-tsx"]) {
    if (!options[key]) fail("missing required --" + key);
    if (!fs.existsSync(options[key])) fail("file not found: " + options[key]);
  }
  return options;
}

function run(rule, files) {
  return spawnSync("node", [rule, ...files], { encoding: "utf8" });
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const rule = path.resolve(args.rule);
  const bad = run(rule, [path.resolve(args.bad), path.resolve(args["bad-tsx"])]);
  const good = run(rule, [path.resolve(args.good), path.resolve(args["good-tsx"])]);
  const badHits = bad.stdout.split(/\r?\n/).filter(Boolean).length;
  const goodHits = good.stdout.split(/\r?\n/).filter(Boolean).length;
  process.stdout.write("rule  : " + rule + "\n");
  process.stdout.write("bad   : rc=" + bad.status + " hits=" + badHits + "\n");
  process.stdout.write("good  : rc=" + good.status + " hits=" + goodHits + "\n");
  if (bad.status !== 1 || badHits !== 4 || good.status !== 0 || goodHits !== 0) {
    process.stdout.write("FAIL: expected BAD_RC=1 with 4 hits and GOOD_RC=0 with 0 hits.\n");
    process.exitCode = 1;
    return;
  }
  process.stdout.write("PASS: BAD_RC=1, GOOD_RC=0, TS/TSX fixtures and vendor noqa behave as expected.\n");
}

try {
  main();
} catch (error) {
  process.stderr.write("error: " + error.message + "\n");
  process.exitCode = 2;
}
