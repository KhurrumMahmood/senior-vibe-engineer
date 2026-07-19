#!/usr/bin/env node
/** Build a closed-state TypeScript proposal from detector JSONL evidence. */
import fs from "node:fs";
import path from "node:path";

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!flag?.startsWith("--") || value === undefined) {
      fail("usage: collect_typescript_state.mjs --findings <jsonl> --project-root <path> --output <targets.json> --proposal <proposal.md>");
    }
    options[flag.slice(2)] = value;
  }
  for (const key of ["findings", "project-root", "output", "proposal"]) {
    if (!options[key]) fail(`missing required --${key}`);
  }
  return options;
}

function readJsonl(file) {
  if (!fs.existsSync(file)) fail(`detector findings not found: ${file}`);
  const records = [];
  for (const [index, line] of fs.readFileSync(file, "utf8").split(/\r?\n/).entries()) {
    if (!line.trim()) continue;
    try {
      records.push(JSON.parse(line));
    } catch (error) {
      fail(`invalid detector JSON on line ${index + 1}: ${error.message}`);
    }
  }
  return records;
}

function toKebab(name) {
  return name.replace(/([a-z0-9])([A-Z])/g, "$1-$2").replace(/_/g, "-").toLowerCase();
}

function markdown(data) {
  const literals = data.literals.map((item) => `- \`${item.value}\` — ${item.count} first-party operation${item.count === 1 ? "" : "s"}`).join("\n");
  const callers = data.callsites.map((site) => `| \`${site.file}:${site.line}\` | ${site.operation} | \`${site.literal}\` |`).join("\n");
  const boundaries = data.vendor_boundaries.length
    ? data.vendor_boundaries.map((file) => `- \`${file}\` remains a named vendor wire boundary; retain a reasoned \`// noqa: no-stringly-state: <reason>\` only on its literal mapping lines.`).join("\n")
    : "- None observed. Do not add an allow-list unless a real external wire value needs one.";
  return `# Proposal — TypeScript closed state: ${data.state_type_name}

## Evidence and scope

The detector supplied ${data.callsites.length} first-party bare literal operation${data.callsites.length === 1 ? "" : "s"} on \`${data.field}\`, all resolved as \`${data.state_type_name}\`. Test/fixture, open-ended-string, unrelated status-text, and vendor records are retained in \`targets.json\` but are not migration callers.

## Distinct first-party literals

${literals}

## Proposed symbolic authority

Create \`${data.runtime_value_file}\` next to the state carrier. Use a runtime value object, not a TypeScript-only union and not a string enum: the checked fixture establishes no project-native string-enum convention.

\`\`\`ts
export const ${data.runtime_value_name} = {
${data.literals.map((item) => `  ${item.value.replace(/[^a-zA-Z0-9]/g, "_").toUpperCase()}: "${item.value}",`).join("\n")}
} as const;

export type ${data.state_type_name} =
  (typeof ${data.runtime_value_name})[keyof typeof ${data.runtime_value_name}];
\`\`\`

## Caller migration

| Caller | Operation | Before literal |
| --- | --- | --- |
${callers}

1. Import \`${data.runtime_value_name}\` wherever the table has a caller.
2. Replace each listed literal with \`${data.runtime_value_name}.MEMBER\` while retaining the existing operation direction.
3. Export the value object and derived union from the existing public module/barrel if callers import the old type there.
4. Run \`npm run typecheck\` and \`npm test\` before review.

## Vendor boundaries

${boundaries}

## Guard handoff

Stage \`scripts/lint/no_stringly_state.mjs\` through \`/prevent-regression\`; it must reject every caller in this proposal before migration and allow the migrated callers plus the reasoned vendor boundary.
`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectRoot = path.resolve(args["project-root"]);
  const records = readJsonl(path.resolve(args.findings));
  const callsites = records.filter((record) => record.classification === "first_party_state_operation");
  if (!callsites.length) fail("detector result contains no first-party closed-state operations");
  const fields = new Set(callsites.map((record) => record.field));
  const types = new Set(callsites.map((record) => record.carrier_type).filter(Boolean));
  if (fields.size !== 1 || types.size !== 1) {
    fail(`proposal requires one field and state type; found fields=${[...fields]} types=${[...types]}`);
  }
  const stateTypeName = [...types][0];
  const literals = [];
  const byLiteral = new Map();
  for (const record of callsites) {
    const existing = byLiteral.get(record.literal);
    if (existing) existing.count += 1;
    else {
      const item = { value: record.literal, count: 1 };
      byLiteral.set(record.literal, item);
      literals.push(item);
    }
  }
  const callersByFile = {};
  for (const site of callsites) callersByFile[site.file] = (callersByFile[site.file] ?? 0) + 1;
  const vendorBoundaries = [...new Set(records
    .filter((record) => record.classification === "vendor_wire_boundary")
    .map((record) => record.file))].sort();
  const firstCallerDir = path.posix.dirname(callsites[0].file);
  const data = {
    schema_version: 1,
    project_root: projectRoot,
    invariant: "One first-party TypeScript state carrier has an exported runtime value authority; callers do not use bare state literals.",
    field: [...fields][0],
    state_type_name: stateTypeName,
    runtime_value_name: stateTypeName,
    runtime_value_file: `${firstCallerDir}/${toKebab(stateTypeName)}.ts`,
    literals,
    callsites: callsites.map(({ file, line, operation, literal, evidence }) => ({ file, line, operation, literal, evidence })),
    callers_by_file: callersByFile,
    vendor_boundaries: vendorBoundaries,
    exclusions: records.filter((record) => record.classification !== "first_party_state_operation"),
  };
  const output = path.resolve(args.output);
  const proposal = path.resolve(args.proposal);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.mkdirSync(path.dirname(proposal), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify(data, null, 2)}\n`);
  fs.writeFileSync(proposal, markdown(data));
  process.stderr.write(`[collect_typescript_state] ${callsites.length} callers, ${literals.length} literals, ${vendorBoundaries.length} vendor boundaries\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`error: ${error.message}\n`);
  process.exitCode = 2;
}
