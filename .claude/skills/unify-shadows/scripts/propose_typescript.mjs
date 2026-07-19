#!/usr/bin/env node
/**
 * Turn one confirmed TypeScript semantic-duplication finding into a proposal.
 *
 * This consumer is deliberately skill-local. It validates the accepted
 * find-semantic-duplication findings.json contract, cites source spans and the
 * capability matrix, and writes only proposal artifacts. It does not analyze
 * TypeScript again and never edits host source.
 */
import fs from "node:fs";
import path from "node:path";

const SHAPES = new Set([
  "keep_separate_document_why",
  "share_utilities",
  "complete_migration",
  "merge_at_workflow",
]);

class ProposalError extends Error {}

function fail(message) {
  throw new ProposalError(message);
}

function parseArgs(argv) {
  const allowed = new Set([
    "--findings",
    "--finding-id",
    "--project-root",
    "--proposal",
    "--evidence",
  ]);
  if (argv.length % 2 !== 0) fail("every argument requires a value");
  const values = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!allowed.has(flag) || values.has(flag)) {
      fail(
        "usage: propose_typescript.mjs --findings <findings.json> "
        + "--finding-id <TS-SD-NNNN> --project-root <path> "
        + "--proposal <proposal.md> --evidence <evidence.json>",
      );
    }
    values.set(flag, value);
  }
  for (const required of allowed) {
    if (!values.has(required)) fail(`missing required argument: ${required}`);
  }
  return {
    findings: values.get("--findings"),
    findingId: values.get("--finding-id"),
    projectRoot: values.get("--project-root"),
    proposal: values.get("--proposal"),
    evidence: values.get("--evidence"),
  };
}

function isWithin(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === "" || (
    relative !== ".."
    && !relative.startsWith(`..${path.sep}`)
    && !path.isAbsolute(relative)
  );
}

function relativePath(projectRoot, absolutePath) {
  return path.relative(projectRoot, absolutePath).split(path.sep).join("/");
}

function requireProjectRoot(value) {
  const candidate = path.resolve(value);
  if (!fs.existsSync(candidate) || !fs.lstatSync(candidate).isDirectory()) {
    fail(`project root is not a directory: ${value}`);
  }
  return fs.realpathSync(candidate);
}

function assertNoSymlinkTraversal(projectRoot, candidate, label) {
  const parts = path.relative(projectRoot, candidate).split(path.sep).filter(Boolean);
  let current = projectRoot;
  for (const part of parts) {
    current = path.join(current, part);
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) {
      fail(`${label} must not traverse a symbolic link: ${relativePath(projectRoot, candidate)}`);
    }
  }
}

function resolveProjectFile(projectRoot, supplied, label) {
  const candidate = path.resolve(projectRoot, supplied);
  if (!isWithin(projectRoot, candidate)) fail(`${label} must stay inside project root: ${supplied}`);
  assertNoSymlinkTraversal(projectRoot, candidate, label);
  if (!fs.existsSync(candidate) || !fs.lstatSync(candidate).isFile()) {
    fail(`${label} not found: ${supplied}`);
  }
  return candidate;
}

function safeArtifactPath(projectRoot, supplied, label) {
  const candidate = path.resolve(projectRoot, supplied);
  const allowedRoot = path.join(projectRoot, "reports", "unify-shadows");
  if (!isWithin(allowedRoot, candidate) || candidate === allowedRoot) {
    fail(`${label} must stay beneath reports/unify-shadows/: ${supplied}`);
  }
  assertNoSymlinkTraversal(projectRoot, candidate, label);
  return candidate;
}

function loadJson(file, label) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    fail(`${label} is not valid JSON: ${error.message}`);
  }
}

function requirePlainObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(`${label} must be an object`);
  return value;
}

function requireText(value, label) {
  if (typeof value !== "string" || value.trim() === "" || /[\r\n\0]/.test(value)) {
    fail(`${label} must be non-empty single-line text`);
  }
  return value;
}

function selectFinding(payload, findingId) {
  requirePlainObject(payload, "findings payload");
  if (payload.skill !== "find-semantic-duplication") {
    fail(`wrong finding kind: expected skill=find-semantic-duplication, got ${String(payload.skill)}`);
  }
  if (payload.language !== "typescript") {
    fail(`TypeScript proposal requires language=typescript, got ${String(payload.language)}`);
  }
  if (!Array.isArray(payload.confirmed)) fail("findings payload requires a confirmed array");
  const matches = payload.confirmed.filter(
    (item) => item?.finding_id === findingId || item?.id === findingId,
  );
  if (matches.length === 0) {
    const other = [payload.uncertain, payload.rejected]
      .filter(Array.isArray)
      .flat()
      .find((item) => item?.finding_id === findingId || item?.id === findingId);
    if (other) fail(`${findingId} is not confirmed (status=${String(other.investigation_status)})`);
    fail(`${findingId} is missing from confirmed findings`);
  }
  if (matches.length !== 1) fail(`${findingId} must identify exactly one confirmed finding`);
  const finding = requirePlainObject(matches[0], `confirmed finding ${findingId}`);
  if (finding.investigation_status !== "confirmed") {
    fail(`${findingId} must have investigation_status=confirmed`);
  }
  if (finding.level !== "function") fail(`${findingId} requires a function-level finding`);
  if (!SHAPES.has(finding.consolidation_shape)) {
    fail(`${findingId} has unsupported consolidation_shape=${String(finding.consolidation_shape)}`);
  }
  if (!Array.isArray(payload.findings)) fail("TypeScript payload requires the accepted findings array");
  const publicMatches = payload.findings.filter(
    (item) => item?.finding_id === findingId || item?.id === findingId,
  );
  if (publicMatches.length !== 1) fail(`${findingId} must occur exactly once in findings`);
  if (publicMatches[0].consolidation_shape !== finding.consolidation_shape) {
    fail(`${findingId} has inconsistent consolidation_shape across structured output`);
  }
  return finding;
}

function validateMember(projectRoot, rawMember, index) {
  const member = requirePlainObject(rawMember, `member ${index + 1}`);
  const file = requireText(member.file, `member ${index + 1}.file`);
  if (path.isAbsolute(file) || ![".ts", ".tsx"].includes(path.extname(file).toLowerCase())) {
    fail(`member ${index + 1} must cite a project-relative TypeScript source file`);
  }
  const absolute = resolveProjectFile(projectRoot, file, `member ${index + 1} source`);
  const qualifiedName = requireText(
    member.qualified_name,
    `member ${index + 1}.qualified_name`,
  );
  if (!Number.isInteger(member.line) || member.line < 1) {
    fail(`member ${index + 1}.line must be a positive integer`);
  }
  if (!Number.isInteger(member.end_line) || member.end_line < member.line) {
    fail(`member ${index + 1}.end_line must be at or after line`);
  }
  const sourceLines = fs.readFileSync(absolute, "utf8").split(/\r?\n/);
  if (member.end_line > sourceLines.length) {
    fail(`member ${index + 1} source span exceeds ${file}`);
  }
  const symbolTail = qualifiedName.split(".").at(-1);
  const span = sourceLines.slice(member.line - 1, member.end_line).join("\n");
  if (!span.includes(symbolTail)) {
    fail(`member ${index + 1} source span does not contain ${qualifiedName}`);
  }
  const callerCount = member.caller_count;
  if (
    callerCount !== null
    && callerCount !== undefined
    && callerCount !== -1
    && (!Number.isInteger(callerCount) || callerCount < 0)
  ) {
    fail(`member ${index + 1}.caller_count must be a non-negative integer or unknown`);
  }
  return {
    file,
    qualifiedName,
    line: member.line,
    endLine: member.end_line,
    callerCount: callerCount === -1 ? null : callerCount,
    citation: `${file}:${member.line}-${member.end_line}`,
  };
}

function matrixEvidence(projectRoot, findingsFile, finding) {
  const raw = requireText(finding.matrix_path, "confirmed finding.matrix_path");
  const matrix = resolveProjectFile(
    projectRoot,
    path.resolve(path.dirname(findingsFile), raw),
    "capability matrix",
  );
  const lines = fs.readFileSync(matrix, "utf8").split(/\r?\n/);
  const citations = lines
    .map((text, index) => ({ text, line: index + 1 }))
    .filter(({ text }) => /^\| (Static return type|Returned fields|Direct call relationship|Exception \/ async policy) \|/.test(text))
    .map(({ text, line }) => ({
      citation: `${relativePath(projectRoot, matrix)}:${line}`,
      text,
    }));
  if (citations.length < 4) fail("capability matrix is missing required TypeScript evidence rows");
  return { path: relativePath(projectRoot, matrix), citations };
}

function nativeCommands(projectRoot) {
  const packageFile = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageFile)) {
    return { typecheck: null, test: null };
  }
  const payload = loadJson(packageFile, "package.json");
  const scripts = payload?.scripts && typeof payload.scripts === "object" ? payload.scripts : {};
  return {
    typecheck: typeof scripts.typecheck === "string" ? "npm run typecheck" : null,
    test: typeof scripts.test === "string" ? "npm test" : null,
  };
}

function callerEvidence(member) {
  if (member.callerCount === null || member.callerCount === undefined) {
    return "Unknown in the upstream candidate graph; enumerate all project references before approval.";
  }
  const noun = member.callerCount === 1 ? "call" : "calls";
  return `${member.callerCount} compiler-resolved incoming ${noun} from the eligible candidate graph; the v1 finding does not carry full-project caller locations, so enumerate project references before approval.`;
}

function helperName(finding) {
  const typeName = typeof finding.static_return_type === "string"
    ? finding.static_return_type.replace(/[^A-Za-z0-9_$]/g, "")
    : "SharedResult";
  return `build${typeName || "SharedResult"}`;
}

function proposedAction(finding, members, matrix) {
  const shape = finding.consolidation_shape;
  const citations = members.map((member) => `\`${member.citation}\``).join(" and ");
  const matrixCitation = `\`${matrix.citations[0].citation}\``;
  if (shape === "keep_separate_document_why") {
    return [
      `Template: \`${shape}\``,
      "",
      `Preserve both implementations and document why their separate authority is intentional (${citations}).`,
      "",
      "- Add or update an adjacent `INTENTIONAL shadow` comment at each member. The comment must cite the caller/resource or runtime-policy fact established during human review.",
      "- Preserve public signatures, returned fields, exception behavior, and current ownership boundaries.",
      `- The static report proves only a shared typed result (${matrixCitation}); it does not authorize a shared helper unless characterization work demonstrates a deep seam that passes the deletion test.`,
      "- If no deep seam is demonstrated, record `No tractable share` and limit the handoff to documentation.",
    ].join("\n");
  }
  if (shape === "share_utilities") {
    const owner = members[0].file;
    const name = helperName(finding);
    return [
      `Template: \`${shape}\``,
      "",
      `Propose a shared utility seam named \`${name}\` in \`${owner}\`, grounded in the common typed output evidence at ${matrixCitation}.`,
      "",
      `- Keep the existing entry points at ${citations}; each delegates only the repeated result-building mechanism after characterization tests pin its behavior.`,
      "- Preserve each entry point's signature, callers, async/exception policy, and resource ownership.",
      "- Deletion test: removing the utility must push the same non-trivial behavior back into both members. If it would restore only object-construction ceremony, stop and record `No tractable share`.",
      "- The human reviewer must confirm the exact helper body and ownership from current source; static return-shape equality alone is not authority to collapse either implementation.",
    ].join("\n");
  }
  if (shape === "complete_migration") {
    const [survivor, ...retired] = members;
    return [
      `Template: \`${shape}\``,
      "",
      `Provisional surviving implementation: \`${survivor.qualifiedName}\` at \`${survivor.citation}\`. Human review must confirm it preserves the characterized contract before edits begin.`,
      "",
      ...retired.map((member) => `- Retired member: \`${member.qualifiedName}\` at \`${member.citation}\`; inventory and move every project caller, add a temporary adapter only when one atomic change is unsafe, then remove it.`),
      "- Rewrite imports and adapt returned values only where the caller-impact inventory proves a difference.",
      "- Do not leave a permanent parallel path; grep and language-service references must show no live references to retired members.",
      `- The common result evidence (${matrixCitation}) is necessary but not sufficient; runtime/error-policy characterization gates the survivor choice.`,
    ].join("\n");
  }
  return [
    `Template: \`${shape}\``,
    "",
    "The upstream TypeScript detector explicitly says workflow evidence is unavailable. This proposal therefore blocks implementation until a human identifies and cites the workflow authority; it does not invent one.",
    "",
    `- Candidate member boundary: ${citations}.`,
    "- Once identified, the workflow authority owns selection between the current members; lower-level member internals remain stable until workflow characterization passes.",
    "- Define one caller-facing workflow API and name every temporary compatibility adapter in the caller inventory.",
    "- Require workflow tests for every supported selection case and a reference search proving callers no longer choose between the shadows directly.",
  ].join("\n");
}

function stopConditions(finding, members, commands) {
  const common = [
    "- [ ] Every source span and capability-matrix citation in this proposal still matches the working tree.",
    "- [ ] Full-project caller references are inventoried; unknown caller evidence is resolved rather than treated as zero.",
    "- [ ] Characterization tests pin each member's success, failure, and exception/async contract.",
  ];
  const byShape = {
    keep_separate_document_why: [
      "- [ ] Each member has an adjacent, evidence-backed `INTENTIONAL shadow` comment.",
      "- [ ] Public signatures and behavior remain unchanged; any utility work is separately justified by the deletion test.",
    ],
    share_utilities: [
      "- [ ] The shared utility removes non-trivial repeated behavior from every member without changing entry-point contracts.",
      "- [ ] The interface-depth deletion test passes and all affected caller/subsystem tests pass.",
    ],
    complete_migration: [
      "- [ ] Language-service references and grep show no live callers or imports of retired members.",
      "- [ ] Any temporary adapter is removed and every moved subsystem test passes.",
    ],
    merge_at_workflow: [
      "- [ ] The workflow authority and its API are cited from current source; unavailable upstream workflow evidence is resolved.",
      "- [ ] Workflow-level tests cover every selection case and callers no longer select members directly.",
    ],
  };
  const native = [
    commands.typecheck
      ? `- [ ] \`${commands.typecheck}\` passes before and after the approved change.`
      : "- [ ] Add or identify a host-native TypeScript typecheck command; none is declared in package.json.",
    commands.test
      ? `- [ ] \`${commands.test}\` passes before and after the approved change.`
      : "- [ ] Add or identify a host-native test command; none is declared in package.json.",
  ];
  return [...common, ...byShape[finding.consolidation_shape], ...native].join("\n");
}

function renderProposal(projectRoot, findingsFile, finding, members, matrix, commands) {
  const summary = requireText(finding.shared_core_description, "shared_core_description");
  const notes = typeof finding.notes === "string" && finding.notes.trim()
    ? finding.notes.trim().replace(/[\r\n]+/g, " ")
    : "No upstream notes were supplied.";
  const memberRows = members.map((member) => (
    `- \`${member.citation}\` — \`${member.qualifiedName}\`; ${callerEvidence(member)}`
  ));
  const callerRows = members.map((member) => (
    `| \`${member.qualifiedName}\` | \`${member.citation}\` | ${member.callerCount ?? "unknown"} | ${callerEvidence(member)} |`
  ));
  const testRows = [
    commands.typecheck
      ? `| Type safety | \`${commands.typecheck}\` | Must pass before and after approved work. |`
      : "| Type safety | unavailable | Declare a host-native typecheck before approval. |",
    commands.test
      ? `| Native tests | \`${commands.test}\` | Must pass before and after approved work. |`
      : "| Native tests | unavailable | Declare a host-native test command before approval. |",
    `| Characterization | Host-native tests around ${members.map((member) => `\`${member.qualifiedName}\``).join(", ")} | Pin returned fields, errors, async policy, and caller expectations before source changes. |`,
  ];
  return [
    `# TypeScript shadow proposal — ${finding.finding_id}`,
    "",
    `**Shape:** \`${finding.consolidation_shape}\``,
    `**Structured input:** \`${relativePath(projectRoot, findingsFile)}\``,
    `**Capability matrix:** \`${matrix.path}\``,
    "**Status:** `proposal_ready_for_human_review`",
    "",
    "## Summary",
    "",
    summary,
    "",
    `Upstream note: ${notes}`,
    "",
    "## Members and source impact",
    "",
    ...memberRows,
    "",
    "The proposal may affect only these cited TypeScript members and their human-confirmed project callers. Adjacent code is out of scope.",
    "",
    "## Evidence",
    "",
    ...matrix.citations.map(({ citation, text }) => `- \`${citation}\` — ${text}`),
    "",
    "These compiler facts establish a confirmed function-level lead. They do not establish runtime equivalence, framework behavior, or complete external caller coverage.",
    "",
    "## Proposed action",
    "",
    proposedAction(finding, members, matrix),
    "",
    "## Caller impact",
    "",
    "| Member | Source evidence | Upstream caller count | Required impact work |",
    "|---|---|---:|---|",
    ...callerRows,
    "",
    "## Native TypeScript test matrix",
    "",
    "| Gate | Command / suite | Required result |",
    "|---|---|---|",
    ...testRows,
    "",
    "## Stop condition",
    "",
    stopConditions(finding, members, commands),
    "",
    "## Authorization and handoff",
    "",
    `Human approval is required before \`/fix-workflow semantic:${finding.finding_id}\`. The first approval token must be \`approved\`, \`approve\`, \`go\`, \`lgtm\`, \`proceed\`, or \`yes\`. This proposal does not mutate host source.`,
    "",
  ].join("\n");
}

function atomicWrite(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temporary = `${file}.tmp-${process.pid}`;
  fs.writeFileSync(temporary, content, "utf8");
  fs.renameSync(temporary, file);
}

function writeScope(directory, members) {
  const payload = {
    version: 1,
    paths: [...new Set(members.map((member) => member.file))].sort(),
    written_at: new Date().toISOString(),
  };
  atomicWrite(path.join(directory, "scope.json"), `${JSON.stringify(payload, null, 1)}\n`);
}

function run(args) {
  const projectRoot = requireProjectRoot(args.projectRoot);
  const proposal = safeArtifactPath(projectRoot, args.proposal, "proposal path");
  const evidence = safeArtifactPath(projectRoot, args.evidence, "evidence path");
  if (path.dirname(proposal) !== path.dirname(evidence)) {
    fail("proposal and evidence must share one reports/unify-shadows/<finding-id>/ directory");
  }
  const findingsFile = resolveProjectFile(projectRoot, args.findings, "findings file");
  const payload = loadJson(findingsFile, "findings file");
  const finding = selectFinding(payload, requireText(args.findingId, "finding id"));
  if (!Array.isArray(finding.members) || finding.members.length < 2) {
    fail(`${args.findingId} requires at least two members`);
  }
  const members = finding.members.map(
    (member, index) => validateMember(projectRoot, member, index),
  );
  const matrix = matrixEvidence(projectRoot, findingsFile, finding);
  const commands = nativeCommands(projectRoot);
  const rendered = renderProposal(
    projectRoot,
    findingsFile,
    finding,
    members,
    matrix,
    commands,
  );
  const evidencePayload = {
    status: "proposal_ready_for_human_review",
    skill: "unify-shadows",
    language: "typescript",
    finding_id: finding.finding_id,
    shape: finding.consolidation_shape,
    structured_input: relativePath(projectRoot, findingsFile),
    capability_matrix: matrix.path,
    source_evidence: members.map((member) => member.citation),
    caller_evidence: members.map((member) => ({
      member: member.qualifiedName,
      candidate_graph_caller_count: member.callerCount,
      full_project_caller_locations: "unavailable_requires_human_inventory",
    })),
    native_test_matrix: commands,
    source_mutation: false,
    human_approval_required: true,
    handoff: `/fix-workflow semantic:${finding.finding_id}`,
  };
  atomicWrite(proposal, rendered);
  atomicWrite(evidence, `${JSON.stringify(evidencePayload, null, 2)}\n`);
  writeScope(path.dirname(proposal), members);
  console.log(
    `[unify-shadows] wrote ${relativePath(projectRoot, proposal)} and `
    + `${relativePath(projectRoot, evidence)}: ${finding.finding_id} `
    + `(${finding.consolidation_shape}, ${members.length} members)`,
  );
}

try {
  run(parseArgs(process.argv.slice(2)));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[unify-shadows] ERROR: ${message}`);
  process.exitCode = 2;
}
