#!/usr/bin/env node
/**
 * Stage a self-contained TypeScript closed-state guard with paired TS/TSX
 * fixtures. The host owns the pinned TypeScript Compiler API dependency.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!flag?.startsWith("--") || value === undefined) {
      fail("usage: generate_typescript_state_guard.mjs --id <id> --project-root <path> --tsconfig <path> --output-root <report-dir>");
    }
    options[flag.slice(2)] = value;
  }
  for (const key of ["id", "project-root", "tsconfig", "output-root"]) {
    if (!options[key]) fail("missing required --" + key);
  }
  if (!/^[a-z0-9][a-z0-9-]{1,63}$/.test(options.id)) fail("invalid report id: " + options.id);
  return options;
}

function preflight(projectRoot, tsconfigPath) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) fail("project-local TypeScript requires " + packageJson);
  if (!fs.existsSync(tsconfigPath)) fail("project-local TypeScript requires tsconfig at " + tsconfigPath);
  let ts;
  try {
    ts = createRequire(packageJson)("typescript");
  } catch (error) {
    fail("project-local TypeScript package is unavailable from " + packageJson + ": " + error.message);
  }
  if (typeof ts.createProgram !== "function" || typeof ts.readConfigFile !== "function") {
    fail("project-local TypeScript package lacks the required Compiler API");
  }
  const config = ts.readConfigFile(tsconfigPath, ts.sys.readFile);
  if (config.error) fail("cannot read tsconfig " + tsconfigPath);
  return ts.version;
}

const BAD_TS = [
  'type JobState = "queued" | "running" | "done";',
  "interface Job { state: JobState; }",
  "declare const job: Job;",
  'job.state = "queued";',
  'job.state === "running";',
  '"done" === job.state;',
  "const currentState = job.state;",
  'currentState === "queued";',
  'job.state ??= "queued";',
  "declare const backup: Job;",
  'job.state = backup.state = "queued";',
  'job.state === "done"; // noqa: no-stringly-state: forged vendor claim',
  "",
].join("\n");

const BAD_TSX = [
  'type JobState = "queued" | "running" | "done";',
  "declare const job: { state: JobState };",
  'export const JobChip = () => <span>{job.state === "queued" ? "queued" : "other"}</span>;',
  "",
].join("\n");

const GOOD_TS = [
  'const JobState = { QUEUED: "queued", RUNNING: "running", DONE: "done" } as const;',
  "type JobState = (typeof JobState)[keyof typeof JobState];",
  "declare const job: { state: JobState };",
  "job.state = JobState.QUEUED;",
  "job.state === JobState.RUNNING;",
  'interface VendorPayload { state: "queued" | "running" | "done"; }',
  "declare const payload: VendorPayload;",
  'payload.state === "queued"; // noqa: no-stringly-state: vendor wire value',
  'enum ImportedJobState { QUEUED = "queued" }',
  'declare const imported: { state: ImportedJobState };',
  'imported.state === ImportedJobState.QUEUED;',
  'export const statusHeading = "Status overview";',
  'export const echo = (reason: string) => reason === "queued";',
  "",
].join("\n");

const GOOD_TSX = [
  'const JobState = { QUEUED: "queued" } as const;',
  "type JobState = (typeof JobState)[keyof typeof JobState];",
  "declare const job: { state: JobState };",
  'export const JobChip = () => <span>{job.state === JobState.QUEUED ? "queued" : "other"}</span>;',
  "",
].join("\n");

const HOST_WIRING = [
  "diff --git a/.pre-commit-config.yaml b/.pre-commit-config.yaml",
  "@@",
  "+      - id: no-stringly-state",
  "+        name: no-stringly-state",
  "+        entry: node scripts/lint/no_stringly_state.mjs",
  "+        types_or: [ts, tsx]",
  "diff --git a/scripts/lint/run.py b/scripts/lint/run.py",
  "@@",
  "+# Integrator-owned: register no-stringly-state as a diff-scoped TypeScript rule.",
  "",
].join("\n");

function write(file, content, executable = false) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
  if (executable) fs.chmodSync(file, 0o755);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectRoot = path.resolve(args["project-root"]);
  const tsconfig = path.resolve(args.tsconfig);
  const outputRoot = path.resolve(args["output-root"]);
  const version = preflight(projectRoot, tsconfig);
  const ownDirectory = path.dirname(fileURLToPath(import.meta.url));
  const guard = fs.readFileSync(path.join(ownDirectory, "no_stringly_state_template.mjs"), "utf8");
  write(path.join(outputRoot, "scripts", "lint", "no_stringly_state.mjs"), guard, true);
  write(path.join(outputRoot, "tests", "lint", "no_stringly_state_bad.ts"), BAD_TS);
  write(path.join(outputRoot, "tests", "lint", "no_stringly_state_bad.tsx"), BAD_TSX);
  write(path.join(outputRoot, "tests", "lint", "no_stringly_state_good.ts"), GOOD_TS);
  write(path.join(outputRoot, "tests", "lint", "no_stringly_state_good.tsx"), GOOD_TSX);
  write(path.join(outputRoot, "host-wiring.diff"), HOST_WIRING);
  process.stderr.write("[generate_typescript_state_guard] staged no-stringly-state with host TypeScript " + version + "\n");
}

try {
  main();
} catch (error) {
  process.stderr.write("error: " + error.message + "\n");
  process.exitCode = 2;
}
