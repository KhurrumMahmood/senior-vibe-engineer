#!/usr/bin/env node
/**
 * Produce a conservative TypeScript function-level semantic-duplication triage.
 *
 * This is a family-local Compiler API consumer. It proves only typed top-level
 * function candidates that share an explicit output shape and are not direct
 * caller/callee or lexical-clone pairs. Direct-call resolution is used for
 * those exclusions; dynamic and declaration-only calls remain uncertainty.
 * It deliberately does not infer workflows, class/protocol semantics, or a
 * structural/module-level duplication claim.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";


const TYPESCRIPT_SOURCE_EXTENSIONS = new Set([".ts", ".tsx"]);
const JAVASCRIPT_SOURCE_EXTENSIONS = new Set([".js", ".jsx", ".mjs", ".cjs"]);
const EXCLUDED_DIRECTORIES = new Set([
  ".git", ".venv", "venv", "node_modules", "dist", "build", "coverage",
  "__tests__", "test", "tests", "fixtures", "fixture", "generated", "vendor",
]);


class SemanticDuplicationError extends Error {}


function fail(message) {
  throw new SemanticDuplicationError(message);
}


function parseArgs(argv) {
  const values = new Map();
  const allowed = new Set(["--target", "--project-root", "--tsconfig", "--report-dir", "--language"]);
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!allowed.has(flag) || value === undefined || values.has(flag)) {
      fail(
        "usage: detect_typescript.mjs --target <path> --project-root <path> "
        + "--tsconfig <path> --report-dir <reports/semantic-duplication/scan>",
      );
    }
    values.set(flag, value);
  }
  for (const required of ["--target", "--project-root", "--tsconfig", "--report-dir"]) {
    if (!values.has(required)) fail(`missing required argument: ${required}`);
  }
  const language = values.get("--language") ?? "typescript";
  if (!["typescript", "javascript"].includes(language)) fail("--language must be typescript or javascript");
  return {
    target: values.get("--target"),
    projectRoot: values.get("--project-root"),
    tsconfig: values.get("--tsconfig"),
    reportDir: values.get("--report-dir"),
    language,
  };
}


function isWithin(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}


function relativePath(projectRoot, absolutePath) {
  return path.relative(projectRoot, absolutePath).split(path.sep).join("/");
}


function requireProjectRoot(supplied) {
  if (!fs.existsSync(supplied) || !fs.statSync(supplied).isDirectory()) {
    fail(`project root is not a directory: ${supplied}`);
  }
  return fs.realpathSync(supplied);
}


function resolveProjectPath(projectRoot, supplied, label) {
  const candidate = path.resolve(projectRoot, supplied);
  if (!isWithin(projectRoot, candidate)) fail(`${label} must stay inside project root: ${supplied}`);
  return candidate;
}


function traversesSymbolicLink(projectRoot, candidate) {
  if (!isWithin(projectRoot, candidate)) return true;
  const parts = relativePath(projectRoot, candidate).split("/").filter(Boolean);
  let current = projectRoot;
  for (const part of parts) {
    current = path.join(current, part);
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) return true;
  }
  return false;
}


function safeReportDirectory(projectRoot, supplied) {
  const reportDir = resolveProjectPath(projectRoot, supplied, "report directory");
  const allowedRoot = path.join(projectRoot, "reports", "semantic-duplication");
  if (!isWithin(allowedRoot, reportDir) || reportDir === allowedRoot) {
    fail(`report directory must stay beneath reports/semantic-duplication/: ${supplied}`);
  }
  if (traversesSymbolicLink(projectRoot, reportDir)) {
    fail(`report directory must not traverse a symbolic link: ${supplied}`);
  }
  return reportDir;
}


function loadProjectTypeScript(projectRoot) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) fail(`project-local TypeScript requires ${packageJson}`);
  try {
    const requireFromProject = createRequire(packageJson);
    const resolved = fs.realpathSync(requireFromProject.resolve("typescript"));
    if (!isWithin(projectRoot, resolved)) {
      fail(`project-local TypeScript package is unavailable from ${packageJson}`);
    }
    const ts = requireFromProject("typescript");
    if (
      typeof ts.createProgram !== "function"
      || typeof ts.resolveModuleName !== "function"
      || typeof ts.createModuleResolutionCache !== "function"
    ) {
      fail("project-local TypeScript package lacks the required Compiler API");
    }
    return ts;
  } catch (error) {
    if (error instanceof SemanticDuplicationError) throw error;
    fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`);
  }
}


function diagnosticText(ts, diagnostic) {
  const text = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
  if (!diagnostic.file) return text;
  const position = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start ?? 0);
  return `${diagnostic.file.fileName}:${position.line + 1}: ${text}`;
}


function resolveTsconfig(ts, projectRoot, supplied, language) {
  const tsconfig = resolveProjectPath(projectRoot, supplied, "tsconfig");
  if (!fs.existsSync(tsconfig) || !fs.lstatSync(tsconfig).isFile() || fs.lstatSync(tsconfig).isSymbolicLink()) {
    fail(language === "javascript"
      ? `unsupported: checked JavaScript requires an explicit jsconfig/tsconfig: ${tsconfig}`
      : `project-local TypeScript requires tsconfig: ${tsconfig}`);
  }
  const read = ts.readConfigFile(tsconfig, ts.sys.readFile);
  if (read.error) fail(`invalid tsconfig: ${diagnosticText(ts, read.error)}`);
  const parsed = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(tsconfig), undefined, tsconfig);
  const errors = parsed.errors.filter((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error);
  if (errors.length > 0) fail(`invalid tsconfig: ${diagnosticText(ts, errors[0])}`);
  if (language === "javascript" && (!parsed.options.allowJs || !parsed.options.checkJs)) {
    fail("unsupported: checked JavaScript requires compilerOptions.allowJs and compilerOptions.checkJs set to true");
  }
  return {
    path: tsconfig,
    options: parsed.options,
    fileNames: parsed.fileNames.map((fileName) => path.resolve(fileName)),
    projectReferences: parsed.projectReferences ?? [],
  };
}


function isSourcePath(candidate, language) {
  const lower = candidate.toLowerCase();
  const extensions = language === "javascript" ? JAVASCRIPT_SOURCE_EXTENSIONS : TYPESCRIPT_SOURCE_EXTENSIONS;
  return extensions.has(path.extname(lower)) && !lower.endsWith(".d.ts") && !lower.endsWith(".d.tsx");
}


function isExcluded(projectRoot, candidate, directory = false, language = "typescript") {
  if (!isWithin(projectRoot, candidate)) return true;
  const relative = relativePath(projectRoot, candidate);
  const parts = relative.split("/");
  const directoryParts = directory ? parts : parts.slice(0, -1);
  if (directoryParts.some((part) => EXCLUDED_DIRECTORIES.has(part.toLowerCase()))) return true;
  if (directory) return false;
  const filename = parts.at(-1).toLowerCase();
  const extension = language === "javascript" ? "(?:js|jsx|mjs|cjs)" : "(?:ts|tsx)";
  return (
    filename.endsWith(".d.ts") || filename.endsWith(".d.tsx")
    || new RegExp(`\\.(?:test|spec|generated|min|bundle)\\.${extension}$`).test(filename)
    || filename.startsWith("test_") || filename.startsWith("tests_")
    || filename.endsWith("_test.ts") || filename.endsWith("_test.tsx")
  );
}


function collectTargetSources(projectRoot, supplied, language) {
  const target = resolveProjectPath(projectRoot, supplied, "target");
  if (!fs.existsSync(target)) fail(`target does not exist: ${supplied}`);
  if (traversesSymbolicLink(projectRoot, target) || fs.lstatSync(target).isSymbolicLink()) {
    fail(`target must not traverse a symbolic link: ${supplied}`);
  }
  const stats = fs.lstatSync(target);
  if (stats.isFile()) {
    if (!isSourcePath(target, language)) fail(`target must be a ${language === "javascript" ? ".js, .jsx, .mjs, or .cjs" : ".ts or .tsx"} file, or a directory: ${supplied}`);
    return { target, exclusion: isExcluded(projectRoot, target, false, language) ? "excluded" : null, files: isExcluded(projectRoot, target, false, language) ? [] : [target] };
  }
  if (!stats.isDirectory()) fail(`target must be a source file or directory: ${supplied}`);
  if (isExcluded(projectRoot, target, true, language)) return { target, exclusion: "excluded", files: [] };
  const files = [];
  const pending = [target];
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const child = path.join(current, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        if (!isExcluded(projectRoot, child, true, language)) pending.push(child);
      } else if (entry.isFile() && isSourcePath(child, language) && !isExcluded(projectRoot, child, false, language)) {
        files.push(child);
      }
    }
  }
  return {
    target,
    exclusion: null,
    files: files.sort((left, right) => relativePath(projectRoot, left).localeCompare(relativePath(projectRoot, right))),
  };
}


function isTypedTopLevelFunction(node, ts, language) {
  if (language === "javascript") return Boolean(node.name && node.body);
  return Boolean(
    node.name && node.body && node.type
    && node.parameters.length > 0
    && node.parameters.every((parameter) => parameter.type),
  );
}


function isTypedBlockArrow(node, ts, language) {
  if (language === "javascript") return Boolean(ts.isArrowFunction(node) && ts.isBlock(node.body));
  return Boolean(
    ts.isArrowFunction(node)
    && ts.isBlock(node.body)
    && node.type
    && node.parameters.length > 0
    && node.parameters.every((parameter) => parameter.type),
  );
}


function visitFunctionBody(node, ts, callback) {
  const root = node.body;
  const visit = (child) => {
    if (child !== node && (ts.isFunctionLike(child) || ts.isClassDeclaration(child) || ts.isClassExpression(child))) return;
    callback(child);
    ts.forEachChild(child, visit);
  };
  ts.forEachChild(root, visit);
}


function returnFields(node, ts) {
  const values = new Set();
  visitFunctionBody(node, ts, (child) => {
    if (!ts.isReturnStatement(child) || !child.expression || !ts.isObjectLiteralExpression(child.expression)) return;
    for (const property of child.expression.properties) {
      if (ts.isPropertyAssignment(property) || ts.isShorthandPropertyAssignment(property)) {
        const name = property.name?.getText() ?? property.name?.escapedText;
        if (typeof name === "string") values.add(name.replace(/["']/g, ""));
      }
    }
  });
  return [...values].sort();
}


function lexicalTokens(node, sourceFile, ts) {
  const text = sourceFile.text.slice(node.getStart(sourceFile), node.end)
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/\/\/.*$/gm, " ")
    .replace(/(["'`])(?:\\.|(?!\1)[^\\])*\1/g, " string ");
  return new Set(text.match(/[A-Za-z_$][\w$]*|\d+|=>|===|!==|==|!=|\+\+|--|&&|\|\||[{}()[\].,;:+\-*/<>?=]/g) ?? []);
}


function lexicalSimilarity(left, right) {
  let intersection = 0;
  for (const token of left) if (right.has(token)) intersection += 1;
  const union = new Set([...left, ...right]).size;
  return union === 0 ? 0 : intersection / union;
}


function policyFacts(node, ts) {
  const facts = new Set();
  visitFunctionBody(node, ts, (child) => {
    if (ts.isThrowStatement(child)) facts.add("throw");
    if (ts.isTryStatement(child)) facts.add("try_catch");
    if (ts.isAwaitExpression(child)) facts.add("await");
  });
  return [...facts].sort();
}


function hasDeclarationOnlySymbol(symbol, ts) {
  const declarations = symbol?.declarations ?? [];
  if (declarations.length === 0) return true;
  return declarations.every((declaration) => (
    (ts.isFunctionDeclaration(declaration) && !declaration.body)
    || Boolean(ts.getCombinedModifierFlags(declaration) & ts.ModifierFlags.Ambient)
  ));
}


function resolvedSymbol(checker, symbol, ts) {
  if (!symbol) return null;
  try {
    return symbol.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(symbol) : symbol;
  } catch {
    return null;
  }
}


function callFacts(candidate, checker, ts) {
  const directSymbols = [];
  const concerns = [];
  visitFunctionBody(candidate.node, ts, (child) => {
    if (!ts.isCallExpression(child)) return;
    const expression = child.expression;
    if (ts.isElementAccessExpression(expression)) {
      concerns.push("dynamic_element_call");
      return;
    }
    if (!ts.isIdentifier(expression)) return;
    const symbol = resolvedSymbol(checker, checker.getSymbolAtLocation(expression), ts);
    if (!symbol || hasDeclarationOnlySymbol(symbol, ts)) {
      concerns.push("unresolved_or_declaration_only_call");
      return;
    }
    directSymbols.push(symbol);
  });
  return { directSymbols, concerns: [...new Set(concerns)].sort() };
}


function candidateRecord(node, sourceFile, projectRoot, checker, ts) {
  const signature = checker.getSignatureFromDeclaration(node);
  if (!signature) return null;
  const returnType = checker.typeToString(checker.getReturnTypeOfSignature(signature));
  if (!returnType || returnType === "any" || returnType === "unknown") return null;
  const name = ts.isFunctionDeclaration(node) ? node.name.text : node.parent.name.text;
  const symbolLocation = ts.isFunctionDeclaration(node) ? node.name : node.parent.name;
  const start = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
  const end = sourceFile.getLineAndCharacterOfPosition(node.end).line + 1;
  return {
    key: `${path.resolve(sourceFile.fileName)}::${name}`,
    file: relativePath(projectRoot, path.resolve(sourceFile.fileName)),
    qualified_name: name,
    line: start,
    end_line: end,
    size: end - start + 1,
    return_type: returnType,
    return_fields: returnFields(node, ts),
    tokens: lexicalTokens(node, sourceFile, ts),
    policy: policyFacts(node, ts),
    symbol: resolvedSymbol(checker, checker.getSymbolAtLocation(symbolLocation), ts),
    node,
    sourceFile,
  };
}


function collectCandidates(program, targetFiles, projectRoot, checker, ts, language) {
  const candidates = [];
  for (const file of targetFiles) {
    const sourceFile = program.getSourceFile(file);
    if (!sourceFile) continue;
    for (const statement of sourceFile.statements) {
      if (ts.isFunctionDeclaration(statement) && isTypedTopLevelFunction(statement, ts, language)) {
        const record = candidateRecord(statement, sourceFile, projectRoot, checker, ts);
        if (record && !/^(mock|fake|stub)/i.test(record.qualified_name)) candidates.push(record);
      }
      if (!ts.isVariableStatement(statement)) continue;
      for (const declaration of statement.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name) || !declaration.initializer || !isTypedBlockArrow(declaration.initializer, ts, language)) continue;
        const record = candidateRecord(declaration.initializer, sourceFile, projectRoot, checker, ts);
        if (record && !/^(mock|fake|stub)/i.test(record.qualified_name)) candidates.push(record);
      }
    }
  }
  for (const candidate of candidates) candidate.calls = callFacts(candidate, checker, ts);
  return candidates.sort((left, right) => left.key.localeCompare(right.key));
}


function sameFields(left, right) {
  return left.length >= 2 && left.length === right.length && left.every((value, index) => value === right[index]);
}


function samePolicy(left, right) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}


function member(candidate, callerCount) {
  return {
    file: candidate.file,
    qualified_name: candidate.qualified_name,
    line: candidate.line,
    end_line: candidate.end_line,
    size: candidate.size,
    caller_count: callerCount,
  };
}


function matrixFor(finding) {
  const [left, right] = finding.members;
  return [
    `## ${finding.finding_id}: ${left.qualified_name} and ${right.qualified_name}`,
    "",
    "### Implementations",
    `- **A:** \`${left.file}:${left.line}-${left.end_line}\` — \`${left.qualified_name}\` (${left.size} lines)`,
    `- **B:** \`${right.file}:${right.line}-${right.end_line}\` — \`${right.qualified_name}\` (${right.size} lines)`,
    "",
    "### Capability comparison",
    "",
    "| Capability | A | B | Notes |",
    "|---|---|---|---|",
    `| Static return type | ${finding.static_return_type} | ${finding.static_return_type} | TypeChecker reports the same explicit return type. |`,
    `| Returned fields | ${finding.return_fields.join(", ")} | ${finding.return_fields.join(", ")} | Both return the same object shape through different bodies. |`,
    "| Direct call relationship | None | None | Compiler-resolved direct calls do not make either member the other's wrapper. |",
    "| Exception / async policy | Same | Same | No incompatible throw/try/await policy was detected. |",
    "",
    "### Recommendation",
    "",
    "Review a shared utility or a deeper shared interface with a human. This static result is a confirmed function-level lead, not an automatic refactor.",
    "",
  ].join("\n");
}


function triage(candidates) {
  const symbolToCandidate = new Map(candidates.filter((candidate) => candidate.symbol).map((candidate) => [candidate.symbol, candidate]));
  const incoming = new Map(candidates.map((candidate) => [candidate.key, 0]));
  for (const candidate of candidates) {
    for (const symbol of candidate.calls.directSymbols) {
      const callee = symbolToCandidate.get(symbol);
      if (callee) incoming.set(callee.key, incoming.get(callee.key) + 1);
    }
  }
  const confirmed = [];
  const uncertain = [];
  const rejected = [];
  let nextId = 1;
  for (let leftIndex = 0; leftIndex < candidates.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < candidates.length; rightIndex += 1) {
      const left = candidates[leftIndex];
      const right = candidates[rightIndex];
      if (left.return_type !== right.return_type || !sameFields(left.return_fields, right.return_fields)) continue;
      const members = [member(left, incoming.get(left.key)), member(right, incoming.get(right.key))];
      const shared = {
        level: "function",
        members,
        static_return_type: left.return_type,
        return_fields: left.return_fields,
        similarity: Number(lexicalSimilarity(left.tokens, right.tokens).toFixed(3)),
      };
      const leftCallsRight = left.calls.directSymbols.some((symbol) => symbolToCandidate.get(symbol)?.key === right.key);
      const rightCallsLeft = right.calls.directSymbols.some((symbol) => symbolToCandidate.get(symbol)?.key === left.key);
      if (leftCallsRight || rightCallsLeft) {
        rejected.push({ ...shared, investigation_status: "rejected", reason_code: "caller_callee", notes: "Compiler-resolved direct call makes this a caller/callee relationship, not parallel duplication." });
        continue;
      }
      if (shared.similarity >= 0.9) {
        rejected.push({ ...shared, investigation_status: "rejected", reason_code: "token_similar_belongs_in_find_duplication", notes: "The function token sets are near-identical; this belongs in lexical duplication triage." });
        continue;
      }
      if (!samePolicy(left.policy, right.policy)) {
        rejected.push({ ...shared, investigation_status: "rejected", reason_code: "load_bearing_divergence", notes: "The exception or asynchronous policy differs, so a shared implementation would change caller-visible behavior." });
        continue;
      }
      const callConcerns = [...new Set([...left.calls.concerns, ...right.calls.concerns])].sort();
      if (callConcerns.length > 0) {
        uncertain.push({ ...shared, investigation_status: "uncertain", reason_code: "direct_call_unresolved_or_dynamic", notes: `Direct-call analysis could not resolve all behavior: ${callConcerns.join(", ")}.` });
        continue;
      }
      const findingId = `TS-SD-${String(nextId).padStart(4, "0")}`;
      nextId += 1;
      confirmed.push({
        ...shared,
        finding_id: findingId,
        id: findingId,
        investigation_status: "confirmed",
        reason_code: null,
        shared_core_description: `Both typed functions return ${left.return_type} with ${left.return_fields.join(", ")} through different implementation shapes.`,
        divergence: { accidental: [], load_bearing: [] },
        consolidation_shape: "share_utilities",
        maintenance_risk_domain: "unknown",
        matrix_path: `capability_matrices/${findingId}.md`,
        tests_that_guard_this_area: [],
        notes: "Function-level static lead only. Review runtime behavior and caller contracts before any refactor.",
      });
    }
  }
  return { confirmed, uncertain, rejected };
}


function renderTriage(payload) {
  const section = (title, items, formatter) => {
    const lines = [`## ${title}`, ""];
    if (items.length === 0) return [...lines, "(none)", ""].join("\n");
    for (const item of items) lines.push(formatter(item), "");
    return lines.join("\n");
  };
  const confirmed = section("Confirmed findings", payload.confirmed, (finding) => [
    `### ${finding.finding_id}: ${finding.members.map((item) => item.qualified_name).join(" / ")}`,
    "",
    `- **Members:** ${finding.members.map((item) => `\`${item.file}:${item.line}-${item.end_line}\``).join(", ")}`,
    `- **Shared core:** ${finding.shared_core_description}`,
    `- **Capability matrix:** \`${finding.matrix_path}\``,
    `- **Next step:** \`/fix-workflow semantic:${finding.finding_id}\` after human approval.`,
  ].join("\n"));
  const uncertain = section("Uncertain candidates", payload.uncertain, (finding) => [
    `- **${finding.members.map((item) => item.qualified_name).join(" / ")}** (\`${finding.reason_code}\`): ${finding.notes}`,
  ].join("\n"));
  const rejected = section("Rejected candidates", payload.rejected, (finding) => [
    `- **${finding.members.map((item) => item.qualified_name).join(" / ")}** (\`${finding.reason_code}\`): ${finding.notes}`,
  ].join("\n"));
  return [
    `# ${payload.language === "javascript" ? "Checked JavaScript" : "TypeScript"} semantic-duplication triage`,
    "",
    `**Confirmed:** ${payload.confirmed.length}   **Uncertain:** ${payload.uncertain.length}   **Rejected:** ${payload.rejected.length}`,
    "",
    "## Capability matrix",
    "",
    "| Capability | State |",
    "|---|---|",
    "| Function-level typed candidates | available |",
    "| Direct-call resolution | available for direct static identifiers |",
    "| Dynamic/declaration-only call evidence | uncertain |",
    "| Workflow or structural analysis | unavailable |",
    "| Protocol/class-method semantics | unavailable |",
    "",
    confirmed,
    uncertain,
    rejected,
  ].join("\n");
}


function writeArtifacts(reportDir, payload, analysis, language) {
  fs.mkdirSync(path.join(reportDir, "capability_matrices"), { recursive: true });
  for (const finding of payload.confirmed) {
    fs.writeFileSync(path.join(reportDir, finding.matrix_path), matrixFor(finding), "utf8");
  }
  fs.writeFileSync(path.join(reportDir, "analysis.json"), JSON.stringify(analysis, null, 2), "utf8");
  fs.writeFileSync(path.join(reportDir, "findings.json"), JSON.stringify({
    skill: "find-semantic-duplication",
    language,
    analyzer: language === "javascript" ? "typescript-compiler-api-checked-javascript" : "typescript-compiler-api",
    status: payload.status,
    config: analysis.config,
    diagnostics: analysis.diagnostics,
    unresolved_modules: analysis.unresolved_modules,
    uncovered_files: analysis.uncovered_files,
    semantic_evidence: analysis.semantic_evidence,
    capability_matrix: {
      function_level_typed_candidates: "available",
      direct_call_resolution: "available_for_direct_static_identifiers",
      dynamic_or_declaration_only_calls: "uncertain",
      workflow_or_structural_analysis: "unavailable",
      protocol_or_class_method_semantics: "unavailable",
    },
    counts: {
      confirmed: payload.confirmed.length,
      uncertain: payload.uncertain.length,
      rejected: payload.rejected.length,
    },
    findings: payload.confirmed,
    confirmed: payload.confirmed,
    uncertain: payload.uncertain,
    rejected: payload.rejected,
  }, null, 2), "utf8");
  fs.writeFileSync(path.join(reportDir, "triage.md"), renderTriage(payload), "utf8");
}


function run(args) {
  const projectRoot = requireProjectRoot(args.projectRoot);
  const reportDir = safeReportDirectory(projectRoot, args.reportDir);
  const ts = loadProjectTypeScript(projectRoot);
  const config = resolveTsconfig(ts, projectRoot, args.tsconfig, args.language);
  const target = collectTargetSources(projectRoot, args.target, args.language);
  const configuredFiles = new Set(config.fileNames.map((file) => path.resolve(file)));
  const uncoveredFiles = args.language === "javascript"
    ? target.files.filter((file) => !configuredFiles.has(file)).map((file) => ({
      file: relativePath(projectRoot, file), reason: "not_in_explicit_jsconfig_or_tsconfig",
    }))
    : [];
  const targetFiles = args.language === "javascript"
    ? target.files.filter((file) => configuredFiles.has(file))
    : target.files;
  if (args.language === "javascript" && target.exclusion) {
    uncoveredFiles.push({ file: relativePath(projectRoot, target.target), reason: "excluded_by_project_config_or_policy" });
  }
  const program = ts.createProgram({
    rootNames: config.fileNames,
    options: config.options,
    projectReferences: config.projectReferences,
  });
  const syntaxErrors = program.getSyntacticDiagnostics().filter((diagnostic) => (
    diagnostic.category === ts.DiagnosticCategory.Error && diagnostic.file && targetFiles.includes(path.resolve(diagnostic.file.fileName))
  ));
  if (syntaxErrors.length > 0) fail(`${args.language === "javascript" ? "JavaScript" : "TypeScript"} syntax errors: ${diagnosticText(ts, syntaxErrors[0])}`);
  const checker = program.getTypeChecker();
  const candidates = collectCandidates(program, targetFiles, projectRoot, checker, ts, args.language);
  const results = triage(candidates);
  const semanticDiagnostics = args.language === "javascript"
    ? program.getSemanticDiagnostics().filter((diagnostic) => diagnostic.file && targetFiles.includes(path.resolve(diagnostic.file.fileName)))
    : [];
  const unresolved = semanticDiagnostics.filter((diagnostic) => diagnostic.code === 2307).map((diagnostic) => ({
    file: relativePath(projectRoot, diagnostic.file.fileName),
    message: diagnosticText(ts, diagnostic),
  }));
  const finalResults = {
    ...results,
    language: args.language,
    status: semanticDiagnostics.length || uncoveredFiles.length ? "partial" : "complete",
  };
  const analysis = {
    target: {
      path: relativePath(projectRoot, target.target),
      exclusion: target.exclusion,
    },
    eligible_files: targetFiles.map((file) => relativePath(projectRoot, file)),
    config: relativePath(projectRoot, config.path),
    diagnostics: semanticDiagnostics.map((diagnostic) => diagnosticText(ts, diagnostic)),
    unresolved_modules: unresolved,
    uncovered_files: uncoveredFiles,
    semantic_evidence: args.language === "javascript" ? {
      checked_javascript: true,
      jsdoc: { declarations: targetFiles.reduce((count, file) => count + (program.getSourceFile(file)?.text.match(/\/\*\*/g)?.length ?? 0), 0) },
      compiler_inferred: { compatible_return_shapes: candidates.length },
    } : undefined,
    typed_function_candidates: candidates.map((candidate) => ({
      file: candidate.file,
      qualified_name: candidate.qualified_name,
      line: candidate.line,
      end_line: candidate.end_line,
      return_type: candidate.return_type,
      return_fields: candidate.return_fields,
    })),
    unavailable: [
      "workflow_or_structural_analysis",
      "protocol_or_class_method_semantics",
      "runtime_or_framework_dispatch",
    ],
  };
  writeArtifacts(reportDir, finalResults, analysis, args.language);
  console.log(
    `[semantic-duplication] confirmed=${finalResults.confirmed.length} `
    + `uncertain=${finalResults.uncertain.length} rejected=${finalResults.rejected.length}`,
  );
  console.log(`[semantic-duplication] wrote ${reportDir}`);
}


try {
  run(parseArgs(process.argv.slice(2)));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[semantic-duplication] ERROR: ${message}`);
  process.exitCode = 2;
}
