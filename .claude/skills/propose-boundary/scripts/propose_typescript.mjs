#!/usr/bin/env node
/**
 * Produce a read-only TypeScript boundary proposal from compiler-resolved facts.
 *
 * The resolver is deliberately family-local: this proposal needs static module
 * edges, target-local symbols, and call targets. It is not a generic analysis
 * platform or a framework-aware architecture detector.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const SOURCE_EXTENSIONS = new Set([".ts", ".tsx"]);
const EXCLUDED_DIRECTORIES = new Set([
  ".git", ".venv", "venv", "node_modules", "dist", "build", "coverage",
  "__tests__", "test", "tests", "fixtures", "fixture", "generated", "vendor",
  "reports",
]);

class ProposalError extends Error {}

function fail(message) {
  throw new ProposalError(message);
}

function parseArgs(argv) {
  const allowed = new Set([
    "--target", "--project-root", "--tsconfig", "--candidates", "--inspection", "--proposal",
  ]);
  const values = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!allowed.has(flag) || value === undefined || values.has(flag)) {
      fail(
        "usage: propose_typescript.mjs --target <path> --project-root <path> --tsconfig <path> "
        + "--candidates <N> --inspection <inspection.json> --proposal <proposal.md>",
      );
    }
    values.set(flag, value);
  }
  for (const required of ["--target", "--project-root", "--tsconfig", "--inspection", "--proposal"]) {
    if (!values.has(required)) fail(`missing required argument: ${required}`);
  }
  const candidates = Number(values.get("--candidates") ?? "1");
  if (!Number.isInteger(candidates) || candidates < 1) fail("--candidates must be a positive integer");
  return {
    target: values.get("--target"),
    projectRoot: values.get("--project-root"),
    tsconfig: values.get("--tsconfig"),
    candidates,
    inspection: values.get("--inspection"),
    proposal: values.get("--proposal"),
  };
}

function isWithin(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}

function requireExistingDirectory(candidate, label) {
  if (!fs.existsSync(candidate) || !fs.statSync(candidate).isDirectory()) {
    fail(`${label} is not a directory: ${candidate}`);
  }
  return fs.realpathSync(candidate);
}

function resolveProjectPath(projectRoot, value, label) {
  const candidate = path.resolve(projectRoot, value);
  if (!isWithin(projectRoot, candidate)) fail(`${label} must stay inside project root: ${value}`);
  return candidate;
}

function relativePath(projectRoot, absolutePath) {
  return path.relative(projectRoot, absolutePath).split(path.sep).join("/");
}

function traversesSymbolicLink(projectRoot, absolutePath) {
  if (!isWithin(projectRoot, absolutePath)) return true;
  const parts = path.relative(projectRoot, absolutePath).split(path.sep).filter(Boolean);
  let current = projectRoot;
  for (const part of parts) {
    current = path.join(current, part);
    if (fs.lstatSync(current).isSymbolicLink()) return true;
  }
  return false;
}

function safeArtifactPath(projectRoot, suppliedPath, allowedRoot, label) {
  const artifact = resolveProjectPath(projectRoot, suppliedPath, label);
  if (!isWithin(allowedRoot, artifact) || artifact === allowedRoot) {
    fail(`${label} must stay beneath ${relativePath(projectRoot, allowedRoot)}/: ${suppliedPath}`);
  }
  const parts = path.relative(projectRoot, artifact).split(path.sep).filter(Boolean);
  let current = projectRoot;
  for (const part of parts) {
    current = path.join(current, part);
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) {
      fail(`${label} must not traverse a symbolic link: ${suppliedPath}`);
    }
  }
  return artifact;
}

function loadProjectTypeScript(projectRoot) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) fail(`project-local TypeScript requires ${packageJson}`);
  try {
    const requireFromProject = createRequire(packageJson);
    const resolved = requireFromProject.resolve("typescript");
    if (!isWithin(projectRoot, fs.realpathSync(resolved))) {
      fail(`project-local TypeScript package is unavailable from ${packageJson}`);
    }
    const ts = requireFromProject("typescript");
    if (typeof ts.createProgram !== "function" || typeof ts.resolveModuleName !== "function") {
      fail("project-local TypeScript package lacks Compiler API module resolution");
    }
    return ts;
  } catch (error) {
    if (error instanceof ProposalError) throw error;
    fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`);
  }
}

function diagnosticText(ts, diagnostic) {
  const text = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
  if (!diagnostic.file) return text;
  const position = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start ?? 0);
  return `${relativePath(path.dirname(path.dirname(diagnostic.file.fileName)), diagnostic.file.fileName)}:${position.line + 1}: ${text}`;
}

function resolveProjectTsconfig(ts, projectRoot, suppliedTsconfig) {
  const tsconfigPath = resolveProjectPath(projectRoot, suppliedTsconfig, "tsconfig");
  if (!fs.existsSync(tsconfigPath)) fail(`project-local TypeScript requires tsconfig: ${tsconfigPath}`);
  const stats = fs.lstatSync(tsconfigPath);
  if (stats.isSymbolicLink()) fail(`tsconfig must not be a symbolic link: ${tsconfigPath}`);
  if (!stats.isFile()) fail(`project-local TypeScript requires tsconfig: ${tsconfigPath}`);
  const read = ts.readConfigFile(tsconfigPath, ts.sys.readFile);
  if (read.error) fail(`invalid tsconfig: ${diagnosticText(ts, read.error)}`);
  const parsed = ts.parseJsonConfigFileContent(
    read.config,
    ts.sys,
    path.dirname(tsconfigPath),
    undefined,
    tsconfigPath,
  );
  const errors = parsed.errors.filter((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error);
  if (errors.length > 0) fail(`invalid tsconfig: ${diagnosticText(ts, errors[0])}`);
  return {
    path: tsconfigPath,
    options: parsed.options,
    fileNames: parsed.fileNames.map((file) => path.resolve(file)),
    projectReferences: parsed.projectReferences ?? [],
    declaredExcludes: Array.isArray(read.config.exclude) ? read.config.exclude.map(String) : [],
  };
}

function globToRegExp(glob) {
  let result = "^";
  for (let index = 0; index < glob.length; index += 1) {
    const char = glob[index];
    if (char === "*") {
      if (glob[index + 1] === "*") {
        if (glob[index + 2] === "/") {
          result += "(?:.*/)?";
          index += 2;
        } else {
          result += ".*";
          index += 1;
        }
      } else {
        result += "[^/]*";
      }
    } else if (char === "?") {
      result += "[^/]";
    } else {
      result += char.replace(/[|\\{}()[\]^$+?.]/g, "\\$&");
    }
  }
  return new RegExp(`${result}$`);
}

function buildExclusionPolicy(projectRoot, declaredExcludes) {
  const rules = declaredExcludes
    .map((rule) => rule.replaceAll("\\", "/").replace(/^\.\//, "").replace(/\/$/, ""))
    .filter(Boolean)
    .map((rule) => ({ rule, regex: /[*?]/.test(rule) ? globToRegExp(rule) : null }));
  const declared = (relative, directory) => rules.some(({ rule, regex }) => {
    if (regex) return regex.test(relative) || (directory && regex.test(`${relative}/`));
    return relative === rule || relative.startsWith(`${rule}/`);
  });
  return {
    isExcluded(absolutePath, directory = false) {
      const normalized = path.resolve(absolutePath);
      if (!isWithin(projectRoot, normalized)) return true;
      const relative = relativePath(projectRoot, normalized);
      const parts = relative.split("/");
      const directoryParts = directory ? parts : parts.slice(0, -1);
      if (directoryParts.some((part) => EXCLUDED_DIRECTORIES.has(part.toLowerCase()))) return true;
      const filename = parts.at(-1)?.toLowerCase() ?? "";
      if (!directory && (
        filename.endsWith(".d.ts") || filename.endsWith(".d.tsx")
        || filename.endsWith(".test.ts") || filename.endsWith(".test.tsx")
        || filename.endsWith(".spec.ts") || filename.endsWith(".spec.tsx")
        || filename.endsWith(".generated.ts") || filename.endsWith(".generated.tsx")
        || filename.endsWith(".min.ts") || filename.endsWith(".min.tsx")
        || filename.endsWith(".bundle.ts") || filename.endsWith(".bundle.tsx")
        || filename.startsWith("test_") || filename.startsWith("tests_")
        || filename.endsWith("_test.ts") || filename.endsWith("_test.tsx")
      )) return true;
      return declared(relative, directory);
    },
  };
}

function isSourcePath(absolutePath) {
  return SOURCE_EXTENSIONS.has(path.extname(absolutePath).toLowerCase())
    && !absolutePath.toLowerCase().endsWith(".d.ts")
    && !absolutePath.toLowerCase().endsWith(".d.tsx");
}

function collectTargetSources(target, projectRoot, exclusions) {
  if (traversesSymbolicLink(projectRoot, target)) fail(`target must not traverse a symbolic link: ${target}`);
  const stats = fs.lstatSync(target);
  if (stats.isSymbolicLink()) fail(`target must not be a symbolic link: ${target}`);
  if (stats.isFile()) {
    if (!isSourcePath(target)) fail(`target must be a .ts or .tsx file, or a directory: ${target}`);
    return exclusions.isExcluded(target) ? [] : [target];
  }
  if (!stats.isDirectory()) fail(`target must be a file or directory: ${target}`);
  if (exclusions.isExcluded(target, true)) return [];
  const files = [];
  const pending = [target];
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const child = path.join(current, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        if (!exclusions.isExcluded(child, true)) pending.push(child);
      } else if (entry.isFile() && isSourcePath(child) && !exclusions.isExcluded(child)) {
        files.push(child);
      }
    }
  }
  return files.sort((left, right) => relativePath(projectRoot, left).localeCompare(relativePath(projectRoot, right)));
}

function sourceFilesInProject(program, projectRoot, exclusions) {
  return program.getSourceFiles().filter((sourceFile) => {
    const absolute = path.resolve(sourceFile.fileName);
    return isWithin(projectRoot, absolute)
      && !traversesSymbolicLink(projectRoot, absolute)
      && isSourcePath(absolute)
      && !exclusions.isExcluded(absolute);
  });
}

function importBindings(statement, ts) {
  if (ts.isImportDeclaration(statement)) {
    const clause = statement.importClause;
    if (!clause) return [];
    const bindings = clause.name ? ["default"] : [];
    if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
      for (const item of clause.namedBindings.elements) bindings.push(item.propertyName?.text ?? item.name.text);
    } else if (clause.namedBindings && ts.isNamespaceImport(clause.namedBindings)) {
      bindings.push("*");
    }
    return bindings;
  }
  if (ts.isExportDeclaration(statement) && statement.exportClause && ts.isNamedExports(statement.exportClause)) {
    return statement.exportClause.elements.map((item) => item.propertyName?.text ?? item.name.text);
  }
  return [];
}

function moduleSpecifiers(sourceFile, ts) {
  const records = [];
  for (const statement of sourceFile.statements) {
    if (ts.isImportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteralLike(statement.moduleSpecifier)) {
      records.push({ kind: "import", specifier: statement.moduleSpecifier.text, bindings: importBindings(statement, ts) });
    } else if (ts.isExportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteralLike(statement.moduleSpecifier)) {
      records.push({ kind: "re_export", specifier: statement.moduleSpecifier.text, bindings: importBindings(statement, ts) });
    } else if (
      ts.isImportEqualsDeclaration(statement)
      && ts.isExternalModuleReference(statement.moduleReference)
      && statement.moduleReference.expression
      && ts.isStringLiteralLike(statement.moduleReference.expression)
    ) {
      records.push({ kind: "import_equals", specifier: statement.moduleReference.expression.text, bindings: [statement.name.text] });
    }
  }
  return records;
}

function resolveSpecifier(ts, specifier, containingFile, options, cache, projectRoot, exclusions) {
  const result = ts.resolveModuleName(specifier, containingFile, options, ts.sys, cache);
  const resolved = result.resolvedModule?.resolvedFileName;
  if (!resolved) return { resolution: "unresolved", resolved_file: null };
  const absolute = path.resolve(resolved);
  if (!isWithin(projectRoot, absolute)) return { resolution: "external", resolved_file: null };
  if (traversesSymbolicLink(projectRoot, absolute)) return { resolution: "unsafe_symlink", resolved_file: null };
  if (exclusions.isExcluded(absolute) || !isSourcePath(absolute)) {
    return { resolution: "resolved_excluded", resolved_file: relativePath(projectRoot, absolute) };
  }
  return { resolution: "resolved", resolved_file: relativePath(projectRoot, absolute) };
}

function modifierExported(node, ts) {
  return Boolean(node.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword));
}

function symbolKind(node, ts) {
  if (ts.isFunctionDeclaration(node)) return "function";
  if (ts.isClassDeclaration(node)) return "class";
  if (ts.isInterfaceDeclaration(node)) return "interface";
  if (ts.isTypeAliasDeclaration(node)) return "type";
  if (ts.isEnumDeclaration(node)) return "enum";
  if (ts.isVariableDeclaration(node)) return "variable";
  return "unknown";
}

function signatureFor(checker, symbol, declaration, ts) {
  if (ts.isFunctionDeclaration(declaration)) {
    const signature = checker.getSignatureFromDeclaration(declaration);
    if (signature) return checker.signatureToString(signature, declaration, ts.TypeFormatFlags.NoTruncation);
  }
  const type = ts.isTypeAliasDeclaration(declaration) || ts.isInterfaceDeclaration(declaration)
    ? checker.getDeclaredTypeOfSymbol(symbol)
    : checker.getTypeOfSymbolAtLocation(symbol, declaration);
  return checker.typeToString(type, declaration, ts.TypeFormatFlags.NoTruncation);
}

function collectSymbols(program, targetFiles, projectRoot, ts) {
  const checker = program.getTypeChecker();
  const records = [];
  const bySymbol = new Map();
  const targetSet = new Set(targetFiles.map((file) => path.resolve(file)));
  for (const sourceFile of program.getSourceFiles()) {
    const file = path.resolve(sourceFile.fileName);
    if (!targetSet.has(file)) continue;
    const declarations = [];
    for (const statement of sourceFile.statements) {
      if (
        ts.isFunctionDeclaration(statement) || ts.isClassDeclaration(statement) || ts.isInterfaceDeclaration(statement)
        || ts.isTypeAliasDeclaration(statement) || ts.isEnumDeclaration(statement)
      ) {
        if (statement.name) declarations.push({ declaration: statement, name: statement.name, exported: modifierExported(statement, ts) });
      } else if (ts.isVariableStatement(statement)) {
        const exported = modifierExported(statement, ts);
        for (const declaration of statement.declarationList.declarations) {
          if (ts.isIdentifier(declaration.name)) declarations.push({ declaration, name: declaration.name, exported });
        }
      }
    }
    for (const item of declarations) {
      const symbol = checker.getSymbolAtLocation(item.name);
      if (!symbol) continue;
      const name = item.name.text;
      const position = sourceFile.getLineAndCharacterOfPosition(item.declaration.getStart(sourceFile));
      const record = {
        name,
        file: relativePath(projectRoot, file),
        kind: symbolKind(item.declaration, ts),
        public: item.exported && !name.startsWith("_"),
        exported: item.exported,
        private_by_convention: name.startsWith("_"),
        line: position.line + 1,
        signature: signatureFor(checker, symbol, item.declaration, ts),
        start: item.declaration.getStart(sourceFile),
        end: item.declaration.getEnd(),
      };
      records.push(record);
      bySymbol.set(symbol, record);
    }
  }
  return { checker, records, bySymbol };
}

function resolveSymbol(checker, symbol, ts) {
  if (!symbol) return null;
  return symbol.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(symbol) : symbol;
}

function collectCallEdges(program, targetFiles, symbols, projectRoot, ts) {
  const targetSet = new Set(targetFiles.map((file) => path.resolve(file)));
  const edges = [];
  for (const sourceFile of program.getSourceFiles()) {
    const file = path.resolve(sourceFile.fileName);
    if (!targetSet.has(file)) continue;
    const fileSymbols = symbols.records
      .filter((record) => record.file === relativePath(projectRoot, file) && record.kind === "function")
      .sort((left, right) => (left.end - left.start) - (right.end - right.start));
    const callerFor = (position) => fileSymbols.find((record) => record.start <= position && position <= record.end) ?? null;
    const visit = (node) => {
      if (ts.isCallExpression(node)) {
        const caller = callerFor(node.getStart(sourceFile));
        const signature = symbols.checker.getResolvedSignature(node);
        const declaration = signature?.declaration;
        const calleeSymbol = declaration?.name
          ? resolveSymbol(symbols.checker, symbols.checker.getSymbolAtLocation(declaration.name), ts)
          : null;
        const callee = calleeSymbol ? symbols.bySymbol.get(calleeSymbol) : null;
        if (caller && callee) {
          edges.push({
            file: relativePath(projectRoot, file),
            caller_symbol: caller.name,
            caller_file: caller.file,
            callee_symbol: callee.name,
            callee_file: callee.file,
            resolution: "resolved",
          });
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return edges.sort((left, right) => (
    left.file.localeCompare(right.file) || left.caller_symbol.localeCompare(right.caller_symbol)
      || left.callee_symbol.localeCompare(right.callee_symbol)
  ));
}

function collectModuleGraph(program, targetFiles, symbols, projectRoot, config, exclusions, ts) {
  const targetSet = new Set(targetFiles.map((file) => path.resolve(file)));
  const cache = ts.createModuleResolutionCache(projectRoot, (fileName) => fileName, config.options);
  const inbound = [];
  const outbound = [];
  const unresolved = [];
  for (const sourceFile of sourceFilesInProject(program, projectRoot, exclusions)) {
    const sourceAbsolute = path.resolve(sourceFile.fileName);
    const isTarget = targetSet.has(sourceAbsolute);
    for (const item of moduleSpecifiers(sourceFile, ts)) {
      const resolved = resolveSpecifier(ts, item.specifier, sourceAbsolute, config.options, cache, projectRoot, exclusions);
      const record = { file: relativePath(projectRoot, sourceAbsolute), ...item, ...resolved };
      if (isTarget) outbound.push(record);
      if (isTarget && (resolved.resolution === "unresolved" || resolved.resolution === "unsafe_symlink")) {
        unresolved.push({ file: record.file, kind: record.kind, specifier: record.specifier });
      }
      if (isTarget || !resolved.resolved_file) continue;
      const resolvedAbsolute = path.resolve(projectRoot, resolved.resolved_file);
      if (!targetSet.has(resolvedAbsolute)) continue;
      const privateBindings = item.bindings.filter((binding) => (
        symbols.records.some((symbol) => symbol.name === binding && !symbol.public)
      ));
      const barrel = /^index\.tsx?$/i.test(path.basename(resolvedAbsolute));
      inbound.push({
        source_file: record.file,
        kind: record.kind,
        specifier: record.specifier,
        bindings: item.bindings,
        style: barrel ? "barrel" : (item.specifier.startsWith(".") ? "direct" : "alias"),
        resolved_file: resolved.resolved_file,
        imports_private: privateBindings.length > 0,
        private_bindings: privateBindings,
      });
    }
  }
  return {
    inbound: inbound.sort((left, right) => left.source_file.localeCompare(right.source_file) || left.specifier.localeCompare(right.specifier)),
    outbound: outbound.sort((left, right) => left.file.localeCompare(right.file) || left.specifier.localeCompare(right.specifier)),
    unresolved: unresolved.sort((left, right) => left.file.localeCompare(right.file) || left.specifier.localeCompare(right.specifier)),
  };
}

function leadingDomain(name) {
  const normalized = name.replace(/^_+/, "");
  const match = normalized.match(/^[A-Z]?[a-z]+/);
  return match ? match[0].toLowerCase() : null;
}

function candidateSeams(symbols, calls, inbound, requested) {
  const grouped = new Map();
  for (const symbol of symbols) {
    const domain = leadingDomain(symbol.name);
    if (!domain || domain.length < 3) continue;
    const group = grouped.get(domain) ?? [];
    group.push(symbol);
    grouped.set(domain, group);
  }
  const viable = [...grouped.entries()].filter(([, members]) => members.length >= 2);
  if (viable.length < 2) return [];
  const allNames = new Set(symbols.map((symbol) => symbol.name));
  const seams = viable.map(([clusterId, members]) => {
    const memberNames = new Set(members.map((member) => member.name));
    const callsFrom = calls.filter((edge) => memberNames.has(edge.caller_symbol));
    const callsInside = callsFrom.filter((edge) => memberNames.has(edge.callee_symbol));
    const callIsolation = callsFrom.length === 0 ? 1 : callsInside.length / callsFrom.length;
    const privateMembers = members.filter((member) => !member.public).map((member) => member.name);
    const privateCallers = calls
      .filter((edge) => !memberNames.has(edge.caller_symbol) && privateMembers.includes(edge.callee_symbol));
    const externalPrivate = inbound.filter((impact) => impact.private_bindings.some((binding) => privateMembers.includes(binding)));
    const namingAlignment = members.filter((member) => leadingDomain(member.name) === clusterId).length / members.length;
    const combined = Number(((namingAlignment + callIsolation) / 2).toFixed(4));
    return {
      cluster_id: clusterId,
      members: members.map((member) => member.name).sort(),
      proposed_public_api: members.filter((member) => member.public).map((member) => member.name).sort(),
      callers_into_private_helpers: [
        ...externalPrivate.map((impact) => ({ kind: "import", ...impact })),
        ...privateCallers.map((edge) => ({ kind: "call", ...edge })),
      ],
      scores: {
        naming_alignment: Number(namingAlignment.toFixed(4)),
        call_isolation: Number(callIsolation.toFixed(4)),
        combined,
      },
      rationale: `Resolved symbols share the ${clusterId} domain token; ${callsInside.length}/${callsFrom.length || 0} target-local calls remain inside the cluster.`,
      graph_evidence: {
        symbols: members.map((member) => ({ name: member.name, file: member.file, line: member.line })),
        private_members: privateMembers,
        cross_cluster_calls: callsFrom.filter((edge) => !memberNames.has(edge.callee_symbol)),
      },
    };
  });
  return seams
    .filter((seam) => seam.members.length < allNames.size)
    .sort((left, right) => right.scores.combined - left.scores.combined || left.cluster_id.localeCompare(right.cluster_id))
    .slice(0, requested);
}

function ambiguousSymbols(ts, program, targetFiles, projectRoot) {
  const targetSet = new Set(targetFiles.map((file) => path.resolve(file)));
  return ts.getPreEmitDiagnostics(program)
    .filter((diagnostic) => diagnostic.code === 2308 && diagnostic.file && targetSet.has(path.resolve(diagnostic.file.fileName)))
    .map((diagnostic) => {
      const position = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start ?? 0);
      return {
        file: relativePath(projectRoot, diagnostic.file.fileName),
        line: position.line + 1,
        code: diagnostic.code,
        message: ts.flattenDiagnosticMessageText(diagnostic.messageText, " "),
      };
    });
}

function nativeCommands(projectRoot) {
  try {
    const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, "package.json"), "utf8"));
    const scripts = packageJson.scripts ?? {};
    const commands = [];
    if (scripts.typecheck) commands.push("npm run typecheck");
    else commands.push("npx tsc --noEmit");
    if (scripts.test) commands.push("npm test");
    return commands;
  } catch {
    return ["npx tsc --noEmit"];
  }
}

function renderProposal(payload) {
  const lines = [
    "---",
    "skill: propose-boundary",
    "language: typescript",
    `target: ${payload.target.path}`,
    `recommendation: ${payload.recommendation}`,
    `graph_status: ${payload.graph.module_resolution}`,
    "---",
    "",
    `# Boundary proposal — ${payload.target.path}`,
    "",
    "> **Detected by:** `/propose-boundary` TypeScript / TSX v1 (read-only; no edits applied)",
    "> **Executed by:** `/refactor-subsystem` only after human approval.",
    "",
    `Recommendation: **${payload.recommendation}**`,
    "",
    "## Resolved graph evidence",
    "",
    `- Compiler API: host-pinned TypeScript with \`${payload.tsconfig}\`.`,
    `- Eligible source files: ${payload.target.source_files}.`,
    `- Resolved inbound module edges: ${payload.graph.inbound_imports.length}; resolved target call edges: ${payload.graph.call_edges.length}.`,
    `- Unresolved target imports: ${payload.graph.unresolved_imports.length}; ambiguous exported symbols: ${payload.graph.ambiguous_symbols.length}.`,
    "",
  ];
  if (payload.recommendation !== "refactor") {
    lines.push("## Stop condition", "");
    if (payload.graph.unresolved_imports.length > 0) lines.push("No extraction proposal is safe while unresolved static module specifiers remain in the target graph.");
    if (payload.graph.ambiguous_symbols.length > 0) lines.push("No extraction proposal is safe while ambiguous exported symbols remain in the target graph.");
    if (payload.defer_signals.includes("single_cluster_no_seam")) lines.push("No extraction proposal is safe: the eligible symbols form one cohesive domain rather than a partition.");
    lines.push("", "Resolve the graph or choose a different target, then rerun this read-only proposal.", "");
  } else {
    for (const [index, seam] of payload.candidate_seams.entries()) {
      lines.push(`## Candidate seam ${index + 1} — ${seam.cluster_id} (score: ${seam.scores.combined})`, "");
      lines.push(`**Resolved rationale.** ${seam.rationale}`, "", "**Proposed public API.**", "");
      lines.push("| Symbol | Signature | Purpose |", "|---|---|---|");
      for (const name of seam.proposed_public_api) {
        const symbol = payload.symbols.find((item) => item.name === name);
        lines.push(`| \`${name}\` | \`${symbol?.signature ?? "unavailable"}\` | Preserve the current ${seam.cluster_id} contract across the extracted boundary. |`);
      }
      if (seam.proposed_public_api.length === 0) lines.push("| _None_ | _None_ | Do not create an API until a human chooses an explicit contract. |");
      lines.push("", "**Private-boundary blockers.**", "");
      if (seam.callers_into_private_helpers.length === 0) {
        lines.push("None found in compiler-resolved static imports or target-local calls.");
      } else {
        for (const blocker of seam.callers_into_private_helpers) {
          if (blocker.kind === "import") {
            const privateBindings = blocker.private_bindings.map((name) => `\`${name}\``).join(", ");
            lines.push(`- \`${blocker.source_file}\` imports private ${privateBindings} via \`${blocker.specifier}\` (${blocker.style}). Migrate it before extraction.`);
          } else {
            lines.push(`- \`${blocker.caller_symbol}\` reaches private \`${blocker.callee_symbol}\` across the candidate boundary. Replace it with the chosen public contract before extraction.`);
          }
        }
      }
      lines.push("");
    }
    lines.push("## Compatibility and barrel plan", "");
    lines.push("- Preserve the existing barrel `index.ts`/`index.tsx` as a compatibility entry point while it re-exports the chosen public symbols from the extracted modules.");
    lines.push("- Keep alias and direct import paths observable in the caller-impact table; migrate direct deep imports deliberately, not by an unverified codemod.");
    lines.push("- Do not re-export underscore-prefixed helpers. Callers reaching them are Phase 1 blockers, not compatibility coverage.", "");
    lines.push("## Caller impact", "", "| Importer | Specifier | Resolved target | Style | Private reach |", "|---|---|---|---|---|");
    if (payload.caller_impact.length === 0) lines.push("| _None_ | _None_ | _None_ | _None_ | no |");
    for (const impact of payload.caller_impact) {
      const privateReach = impact.imports_private
        ? `yes: ${impact.private_bindings.map((name) => `\`${name}\``).join(", ")}`
        : "no";
      lines.push(`| \`${impact.source_file}\` | \`${impact.specifier}\` | \`${impact.resolved_file}\` | ${impact.style} | ${privateReach} |`);
    }
    lines.push("", "## Characterization and native verification plan", "");
    lines.push("1. Pin each proposed public API symbol with input/output tests before moving implementation.");
    lines.push("2. Add one compatibility test per currently resolved direct, alias, and barrel importer.");
    lines.push("3. Migrate every private-helper reach before removing the legacy implementation.");
    lines.push("4. Run the host-native checks before and after the refactor:");
    for (const command of payload.native_verification.commands) lines.push(`   - \`${command}\``);
    lines.push("", "## Stop condition", "", "Every resolved importer uses the new public boundary, private reaches are gone, and the listed native checks stay green.", "");
  }
  return `${lines.join("\n")}\n`;
}

function writeAtomically(destination, contents) {
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  const temporary = `${destination}.tmp-${process.pid}`;
  fs.writeFileSync(temporary, contents, "utf8");
  fs.renameSync(temporary, destination);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectRoot = requireExistingDirectory(path.resolve(args.projectRoot), "project root");
  const target = resolveProjectPath(projectRoot, args.target, "target");
  if (!fs.existsSync(target)) fail(`target does not exist: ${target}`);
  if (traversesSymbolicLink(projectRoot, target)) fail(`target must not traverse a symbolic link: ${target}`);
  const targetStats = fs.lstatSync(target);
  if (targetStats.isSymbolicLink()) fail(`target must not be a symbolic link: ${target}`);
  const reportRoot = path.join(projectRoot, "reports", "propose-boundary");
  const inspectionPath = safeArtifactPath(projectRoot, args.inspection, reportRoot, "inspection artifact");
  const proposalPath = safeArtifactPath(projectRoot, args.proposal, reportRoot, "proposal artifact");
  const ts = loadProjectTypeScript(projectRoot);
  const config = resolveProjectTsconfig(ts, projectRoot, args.tsconfig);
  const exclusions = buildExclusionPolicy(projectRoot, config.declaredExcludes);
  const targetFiles = collectTargetSources(target, projectRoot, exclusions);
  const program = ts.createProgram({
    rootNames: [...new Set([...config.fileNames, ...targetFiles])],
    options: config.options,
    projectReferences: config.projectReferences,
  });
  const syntaxDiagnostics = targetFiles.flatMap((file) => program.getSyntacticDiagnostics(program.getSourceFile(file)));
  if (syntaxDiagnostics.length > 0) fail(`TypeScript syntax errors: ${diagnosticText(ts, syntaxDiagnostics[0])}`);
  const symbolFacts = collectSymbols(program, targetFiles, projectRoot, ts);
  const moduleGraph = collectModuleGraph(program, targetFiles, symbolFacts, projectRoot, config, exclusions, ts);
  const calls = collectCallEdges(program, targetFiles, symbolFacts, projectRoot, ts);
  const ambiguous = ambiguousSymbols(ts, program, targetFiles, projectRoot);
  const graphBlocked = moduleGraph.unresolved.length > 0 || ambiguous.length > 0;
  const seams = graphBlocked ? [] : candidateSeams(symbolFacts.records, calls, moduleGraph.inbound, args.candidates);
  const deferSignals = [];
  if (moduleGraph.unresolved.length > 0) deferSignals.push("unresolved_module_resolution");
  if (ambiguous.length > 0) deferSignals.push("ambiguous_symbol_resolution");
  if (!graphBlocked && seams.length === 0) deferSignals.push("single_cluster_no_seam");
  const recommendation = graphBlocked
    ? "defer_unresolved_graph"
    : (seams.length === 0 ? "defer_no_seam" : "refactor");
  const targetExcluded = targetFiles.length === 0 && exclusions.isExcluded(target, targetStats.isDirectory());
  const payload = {
    schema_version: 1,
    skill: "propose-boundary",
    language: "typescript",
    analyzer: "typescript-compiler-api",
    status: recommendation === "refactor" ? "complete" : "deferred",
    recommendation,
    target: {
      path: relativePath(projectRoot, target),
      kind: targetStats.isDirectory() ? "directory" : "file",
      exclusion: targetExcluded ? "excluded" : "included",
      source_files: targetFiles.length,
    },
    tsconfig: relativePath(projectRoot, config.path),
    symbols: symbolFacts.records.map(({ start, end, ...record }) => record),
    graph: {
      module_resolution: graphBlocked ? "partial" : "complete",
      inbound_imports: moduleGraph.inbound,
      outbound_imports: moduleGraph.outbound,
      unresolved_imports: moduleGraph.unresolved,
      ambiguous_symbols: ambiguous,
      call_edges: calls,
    },
    candidate_seams: seams,
    caller_impact: moduleGraph.inbound,
    defer_signals: deferSignals,
    native_verification: {
      commands: nativeCommands(projectRoot),
      scope: "Host commands are cited for the human-approved refactor; this read-only proposal does not modify source.",
    },
  };
  writeAtomically(inspectionPath, `${JSON.stringify(payload, null, 2)}\n`);
  writeAtomically(proposalPath, renderProposal(payload));
  process.stdout.write(`wrote ${args.inspection} and ${args.proposal} (${recommendation})\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`[propose_typescript] ${error.message}\n`);
  process.exitCode = 2;
}
