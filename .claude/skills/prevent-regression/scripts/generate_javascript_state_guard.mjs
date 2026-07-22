#!/usr/bin/env node
/** Stage a bounded checked-JavaScript guard only from complete detector evidence. */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SUFFIXES = new Set([".js", ".jsx", ".mjs", ".cjs"]);
function fail(message) { throw new Error(message); }
function parse(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index]; const value = argv[index + 1];
    if (!flag?.startsWith("--") || value === undefined) fail("usage: generate_javascript_state_guard.mjs --id <id> --project-root <path> --config <jsconfig> --findings <jsonl> --manifest <json> --output-root <dir>");
    options[flag.slice(2)] = value;
  }
  for (const key of ["id", "project-root", "config", "findings", "manifest", "output-root"]) if (!options[key]) fail(`missing required --${key}`);
  if (!/^[a-z0-9][a-z0-9-]{1,63}$/.test(options.id)) fail(`invalid report id: ${options.id}`);
  return options;
}
function preflight(root, config) {
  const packageJson = path.join(root, "package.json");
  if (!fs.existsSync(packageJson) || !fs.existsSync(config)) fail("unsupported: checked JavaScript requires host package.json and explicit config");
  let ts;
  try { ts = createRequire(packageJson)("typescript"); } catch (error) { fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`); }
  const read = ts.readConfigFile(config, ts.sys.readFile);
  if (read.error) fail(`cannot read checked JavaScript config: ${ts.flattenDiagnosticMessageText(read.error.messageText, " ")}`);
  const parsed = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(config));
  if (!parsed.options.allowJs || !parsed.options.checkJs) fail("unsupported: checked JavaScript requires compilerOptions.allowJs and compilerOptions.checkJs set to true");
  return ts.version;
}
function proof(findings, manifest) {
  const summary = JSON.parse(fs.readFileSync(manifest, "utf8"));
  if (summary.language !== "javascript" || summary.status !== "complete" || !summary.semantic_evidence?.checked_javascript) fail("unsupported: guard requires complete checked-JavaScript detector manifest");
  const records = fs.readFileSync(findings, "utf8").split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  const actionable = records.filter((item) => item.classification === "first_party_state_operation" && SUFFIXES.has(path.extname(item.file)));
  if (!actionable.length) fail("unsupported: no proven first-party JavaScript closed-state operation in findings");
}
function write(file, value, executable = false) { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, value); if (executable) fs.chmodSync(file, 0o755); }
const BAD = (suffix) => `/** @typedef {"queued" | "done"} JobState */\n/** @type {{ state: JobState }} */\nconst job = { state: "queued" };\njob.state = "queued";\njob.state === "done";\n` + (suffix === ".jsx" ? "export const Chip = () => <span>{job.state === \"queued\" ? \"q\" : \"d\"}</span>;\n" : "");
const GOOD = (suffix) => `/** @typedef {"queued" | "done"} JobState */\nconst JobState = { QUEUED: "queued", DONE: "done" };\n/** @type {{ state: JobState }} */\nconst job = { state: JobState.QUEUED };\njob.state === JobState.DONE;\n/** @typedef {{ state: JobState }} VendorJobPayload */\n/** @type {VendorJobPayload} */\nconst vendor = { state: "queued" };\nvendor.state === "queued"; // noqa: no-stringly-state: vendor wire\n` + (suffix === ".jsx" ? "export const Chip = () => <span>{job.state}</span>;\n" : "");
function main() {
  const args = parse(process.argv.slice(2));
  const root = path.resolve(args["project-root"]); const config = path.resolve(args.config);
  const findings = path.resolve(args.findings); const manifest = path.resolve(args.manifest); const output = path.resolve(args["output-root"]);
  const version = preflight(root, config); proof(findings, manifest);
  const here = path.dirname(fileURLToPath(import.meta.url));
  write(path.join(output, "scripts", "lint", "no_stringly_state_javascript.mjs"), fs.readFileSync(path.join(here, "no_stringly_state_javascript_template.mjs"), "utf8"), true);
  for (const suffix of SUFFIXES) {
    write(path.join(output, "tests", "lint", `no_stringly_state_bad${suffix}`), BAD(suffix));
    write(path.join(output, "tests", "lint", `no_stringly_state_good${suffix}`), GOOD(suffix));
  }
  write(path.join(output, "host-wiring.diff"), "+ entry: node scripts/lint/no_stringly_state_javascript.mjs\n+ types_or: [javascript, jsx]\n");
  process.stdout.write(JSON.stringify({ status: "complete", output_root: output, typescript_version: version }) + "\n");
}
try { main(); } catch (error) { process.stdout.write(JSON.stringify({ status: "unsupported", error: error.message }) + "\n"); process.exitCode = 2; }
