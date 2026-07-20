#!/usr/bin/env node
/**
 * Produce one read-only TypeScript or checked-JavaScript folder-reorganization proposal.
 *
 * This is deliberately a family-local Compiler API consumer.  The accepted
 * v1 contract needs only a named host tsconfig, direct relative and paths
 * alias resolution, and a durable move-impact proposal.  It is not a shared
 * parser platform or a refactor executor.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const SOURCE_EXTENSIONS = {
  typescript: new Set([".ts", ".tsx"]),
  javascript: new Set([".js", ".jsx", ".mjs", ".cjs"]),
};
let activeLanguage = "typescript";
const EXCLUDED_DIRECTORIES = new Set([
  ".git", ".venv", "venv", "node_modules", "dist", "build", "coverage",
  "__tests__", "test", "tests", "specs", "fixtures", "fixture", "generated",
  "vendor", "reports",
]);
const SCRATCH_SEGMENTS = new Set(["_experiments", "experiments", "sandbox", "scratch", "tmp", "_archive"]);

class ProposalError extends Error {}

function fail(message) {
  throw new ProposalError(message);
}

function parseArgs(argv) {
  const allowed = new Set([
    "--parent", "--prefix", "--cluster-judgment", "--project-root", "--tsconfig", "--proposal", "--inspection", "--language",
  ]);
  const values = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!allowed.has(flag) || value === undefined || values.has(flag)) {
      fail(
        "usage: propose_typescript.mjs --parent <path> --prefix <token> "
        + "--cluster-judgment <split|cohesive> --project-root <path> --tsconfig <path> "
        + "--proposal <proposal.md> --inspection <inspection.json>",
      );
    }
    values.set(flag, value);
  }
  for (const required of ["--parent", "--prefix", "--cluster-judgment", "--project-root", "--tsconfig", "--proposal", "--inspection"]) {
    if (!values.has(required)) fail(`missing required argument: ${required}`);
  }
  const judgment = values.get("--cluster-judgment");
  if (judgment !== "split" && judgment !== "cohesive") {
    fail("--cluster-judgment must be split or cohesive");
  }
  const prefix = values.get("--prefix");
  if (!/^[A-Za-z][A-Za-z0-9_-]*$/.test(prefix)) {
    fail("--prefix must be a filename domain token");
  }
  const language = values.get("--language") ?? "typescript";
  if (!["typescript", "javascript"].includes(language)) fail("--language must be typescript or javascript");
  return {
    parent: values.get("--parent"),
    prefix,
    judgment,
    projectRoot: values.get("--project-root"),
    tsconfig: values.get("--tsconfig"),
    proposal: values.get("--proposal"),
    inspection: values.get("--inspection"),
    language,
  };
}

function isWithin(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}

function requireProjectRoot(value) {
  const candidate = path.resolve(value);
  if (!fs.existsSync(candidate) || !fs.statSync(candidate).isDirectory()) {
    fail(`project root is not a directory: ${candidate}`);
  }
  return fs.realpathSync(candidate);
}

function resolveProjectPath(projectRoot, supplied, label) {
  const candidate = path.resolve(projectRoot, supplied);
  if (!isWithin(projectRoot, candidate)) fail(`${label} must stay inside project root: ${supplied}`);
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
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) return true;
  }
  return false;
}

function existingPathWithoutSymlink(projectRoot, absolutePath, label) {
  if (traversesSymbolicLink(projectRoot, absolutePath)) {
    fail(`${label} must not traverse a symbolic link: ${absolutePath}`);
  }
  if (!fs.existsSync(absolutePath)) fail(`${label} does not exist: ${absolutePath}`);
  return absolutePath;
}

function safeArtifactPath(projectRoot, suppliedPath, label) {
  const artifact = resolveProjectPath(projectRoot, suppliedPath, label);
  const allowedRoot = path.join(projectRoot, "reports", "propose-folder-reorganization");
  if (!isWithin(allowedRoot, artifact) || artifact === allowedRoot) {
    fail(`${label} must stay beneath reports/propose-folder-reorganization/: ${suppliedPath}`);
  }
  if (traversesSymbolicLink(projectRoot, artifact)) {
    fail(`${label} must not traverse a symbolic link: ${suppliedPath}`);
  }
  return artifact;
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
  return `${diagnostic.file.fileName}:${position.line + 1}: ${text}`;
}

function loadTsconfig(ts, projectRoot, supplied, language) {
  const configPath = resolveProjectPath(projectRoot, supplied, "tsconfig");
  existingPathWithoutSymlink(projectRoot, configPath, "tsconfig");
  if (!fs.lstatSync(configPath).isFile()) fail(`project-local TypeScript requires tsconfig: ${configPath}`);
  const read = ts.readConfigFile(configPath, ts.sys.readFile);
  if (read.error) fail(`invalid tsconfig: ${diagnosticText(ts, read.error)}`);
  const parsed = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(configPath), undefined, configPath);
  const errors = parsed.errors.filter((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error);
  if (errors.length > 0) fail(`invalid tsconfig: ${diagnosticText(ts, errors[0])}`);
  if (language === "javascript" && (!parsed.options.allowJs || !parsed.options.checkJs)) {
    fail("unsupported: checked JavaScript requires compilerOptions.allowJs and compilerOptions.checkJs set to true");
  }
  return {
    path: configPath,
    options: parsed.options,
    fileNames: parsed.fileNames.map((file) => path.resolve(file)),
    projectReferences: parsed.projectReferences ?? [],
    declaredExcludes: Array.isArray(read.config.exclude) ? read.config.exclude.map(String) : [],
    paths: read.config.compilerOptions?.paths ?? {},
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

  function matchesDeclaredExclude(relative, directory) {
    return rules.some(({ rule, regex }) => {
      if (regex) return regex.test(relative) || (directory && regex.test(`${relative}/`));
      return relative === rule || relative.startsWith(`${rule}/`);
    });
  }

  return {
    isExcluded(absolutePath, directory = false, allowBarrel = false) {
      const normalized = path.resolve(absolutePath);
      if (!isWithin(projectRoot, normalized)) return true;
      const relative = relativePath(projectRoot, normalized);
      const parts = relative.split("/").filter(Boolean);
      const directoryParts = directory ? parts : parts.slice(0, -1);
      if (directoryParts.some((part) => EXCLUDED_DIRECTORIES.has(part.toLowerCase()))) return true;
      const filename = parts.at(-1)?.toLowerCase() ?? "";
      const suffix = activeLanguage === "javascript" ? "(?:js|jsx|mjs|cjs)" : "(?:ts|tsx)";
      if (!directory && (
        (!allowBarrel && new RegExp(`^index\\.${suffix}$`).test(filename)) || filename.endsWith(".d.ts") || filename.endsWith(".d.tsx")
        || new RegExp(`\\.(?:test|spec|generated|min|bundle)\\.${suffix}$`).test(filename)
        || filename.startsWith("test_") || filename.startsWith("tests_")
      )) return true;
      return matchesDeclaredExclude(relative, directory);
    },
  };
}

function isSourcePath(absolutePath) {
  const lower = absolutePath.toLowerCase();
  return SOURCE_EXTENSIONS[activeLanguage].has(path.extname(lower)) && !lower.endsWith(".d.ts") && !lower.endsWith(".d.tsx");
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function collectCluster(parent, prefix, exclusions) {
  if (exclusions.isExcluded(parent, true)) return [];
  const matcher = new RegExp(`^${escapeRegExp(prefix)}[-_]`);
  return fs.readdirSync(parent, { withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => path.join(parent, entry.name))
    .filter((file) => isSourcePath(file) && !exclusions.isExcluded(file) && matcher.test(path.basename(file, path.extname(file))))
    .sort((left, right) => left.localeCompare(right));
}

function newPathFor(parent, prefix, current) {
  const extension = path.extname(current);
  const stem = path.basename(current, extension);
  const suffix = stem.slice(prefix.length + 1);
  return path.join(parent, prefix, `${suffix}${extension}`);
}

function moduleSpecifiers(sourceFile, ts) {
  const records = [];
  for (const statement of sourceFile.statements) {
    if (ts.isImportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteralLike(statement.moduleSpecifier)) {
      records.push({ kind: "import", specifier: statement.moduleSpecifier.text, statement });
    } else if (ts.isExportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteralLike(statement.moduleSpecifier)) {
      records.push({ kind: "re_export", specifier: statement.moduleSpecifier.text, statement });
    } else if (
      ts.isImportEqualsDeclaration(statement)
      && ts.isExternalModuleReference(statement.moduleReference)
      && statement.moduleReference.expression
      && ts.isStringLiteralLike(statement.moduleReference.expression)
    ) {
      records.push({ kind: "import_equals", specifier: statement.moduleReference.expression.text, statement });
    } else if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        const initializer = declaration.initializer;
        if (
          initializer
          && ts.isCallExpression(initializer)
          && ts.isIdentifier(initializer.expression)
          && initializer.expression.text === "require"
          && initializer.arguments.length === 1
          && ts.isStringLiteralLike(initializer.arguments[0])
        ) {
          records.push({ kind: "require", specifier: initializer.arguments[0].text, statement });
        }
      }
    }
  }
  return records;
}

function resolveSpecifier(ts, specifier, containingFile, options, cache, projectRoot, exclusions) {
  const result = ts.resolveModuleName(specifier, containingFile, options, ts.sys, cache);
  const resolved = result.resolvedModule?.resolvedFileName;
  if (!resolved) return { resolution: "unresolved", absolute: null, resolvedFile: null };
  const absolute = path.resolve(resolved);
  if (!isWithin(projectRoot, absolute)) return { resolution: "external", absolute: null, resolvedFile: null };
  if (traversesSymbolicLink(projectRoot, absolute)) return { resolution: "unsafe_symlink", absolute, resolvedFile: null };
  if (!isSourcePath(absolute) || exclusions.isExcluded(absolute)) {
    return { resolution: "resolved_excluded", absolute, resolvedFile: relativePath(projectRoot, absolute) };
  }
  return { resolution: "resolved", absolute, resolvedFile: relativePath(projectRoot, absolute) };
}

function withoutExtension(value) {
  return value.replace(/\.(?:tsx?|mts|cts|js|jsx|mjs|cjs)$/i, "");
}

function relativeSpecifier(fromFile, newTarget) {
  const relative = path.relative(path.dirname(fromFile), newTarget).split(path.sep).join("/");
  let value = activeLanguage === "javascript" ? relative : withoutExtension(relative);
  if (!value.startsWith(".")) value = `./${value}`;
  return value;
}

function wildcardMatch(pattern, value) {
  const star = pattern.indexOf("*");
  if (star < 0) return pattern === value ? "" : null;
  const before = pattern.slice(0, star);
  const after = pattern.slice(star + 1);
  if (!value.startsWith(before) || !value.endsWith(after)) return null;
  return value.slice(before.length, value.length - after.length);
}

function aliasSpecifier(config, projectRoot, oldTarget, newTarget, original) {
  const oldPath = relativePath(projectRoot, oldTarget);
  const newPath = relativePath(projectRoot, newTarget);
  const oldRelative = activeLanguage === "javascript" ? oldPath : withoutExtension(oldPath);
  const newRelative = activeLanguage === "javascript" ? newPath : withoutExtension(newPath);
  for (const [aliasPattern, targets] of Object.entries(config.paths)) {
    const aliasValue = wildcardMatch(aliasPattern, original);
    if (aliasValue === null) continue;
    for (const targetPatternValue of targets) {
      const targetPattern = withoutExtension(String(targetPatternValue).replaceAll("\\", "/"));
      const oldWildcard = wildcardMatch(targetPattern, oldRelative);
      if (oldWildcard === null) continue;
      const newWildcard = wildcardMatch(targetPattern, newRelative);
      if (newWildcard === null) continue;
      return aliasPattern.includes("*") ? aliasPattern.replace("*", newWildcard) : aliasPattern;
    }
  }
  return null;
}

function afterMoveSpecifier(config, projectRoot, importer, oldTarget, newTarget, original) {
  if (original.startsWith(".")) return relativeSpecifier(importer, newTarget);
  return aliasSpecifier(config, projectRoot, oldTarget, newTarget, original);
}

function symbolKind(ts, symbol) {
  const flags = symbol.flags;
  if (flags & ts.SymbolFlags.Class) return "class";
  if (flags & ts.SymbolFlags.Function) return "function";
  if (flags & ts.SymbolFlags.Interface) return "interface";
  if (flags & ts.SymbolFlags.TypeAlias) return "type";
  if (flags & ts.SymbolFlags.Enum) return "enum";
  if (flags & ts.SymbolFlags.ValueModule) return "namespace";
  if (flags & (ts.SymbolFlags.BlockScopedVariable | ts.SymbolFlags.FunctionScopedVariable)) return "variable";
  return "unknown";
}

function exportedSymbols(program, clusterPaths, projectRoot, ts) {
  const checker = program.getTypeChecker();
  return clusterPaths.map((file) => {
    const sourceFile = program.getSourceFile(file);
    const moduleSymbol = sourceFile ? (checker.getSymbolAtLocation(sourceFile) ?? sourceFile.symbol) : null;
    const symbols = moduleSymbol
      ? checker.getExportsOfModule(moduleSymbol)
        .map((symbol) => {
          const resolved = symbol.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(symbol) : symbol;
          return { name: symbol.getName(), kind: symbolKind(ts, resolved) };
        })
        .sort((left, right) => left.name.localeCompare(right.name))
      : [];
    return { path: relativePath(projectRoot, file), symbols };
  });
}

function sourceStatement(sourceFile, statement) {
  return statement.getText(sourceFile).replace(/\s+/g, " ").trim();
}

function collectModuleFacts(program, clusterMoves, config, projectRoot, exclusions, ts) {
  const moveByOldPath = new Map(clusterMoves.map((move) => [path.resolve(move.current), path.resolve(move.next)]));
  const clusterSet = new Set(moveByOldPath.keys());
  const cache = ts.createModuleResolutionCache(projectRoot, (value) => value, config.options);
  const impacts = [];
  const unresolved = [];
  const unsupported = [];
  const eligibleSources = program.getSourceFiles().filter((sourceFile) => {
    const absolute = path.resolve(sourceFile.fileName);
    return isWithin(projectRoot, absolute)
      && !traversesSymbolicLink(projectRoot, absolute)
      && isSourcePath(absolute)
      && !exclusions.isExcluded(absolute, false, true);
  });

  for (const sourceFile of eligibleSources) {
    const importer = path.resolve(sourceFile.fileName);
    const importerIsClusterMember = clusterSet.has(importer);
    for (const item of moduleSpecifiers(sourceFile, ts)) {
      const resolved = resolveSpecifier(ts, item.specifier, importer, config.options, cache, projectRoot, exclusions);
      if (importerIsClusterMember && (resolved.resolution === "unresolved" || resolved.resolution === "unsafe_symlink")) {
        unresolved.push({
          file: relativePath(projectRoot, importer),
          kind: item.kind,
          specifier: item.specifier,
          ...(resolved.resolution === "unsafe_symlink" ? { reason: "unsafe_symlink" } : {}),
        });
      }
      if (resolved.resolution !== "resolved" || !resolved.absolute || !moveByOldPath.has(path.resolve(resolved.absolute))) continue;
      const newTarget = moveByOldPath.get(path.resolve(resolved.absolute));
      const afterImporter = moveByOldPath.get(importer) ?? importer;
      const after = afterMoveSpecifier(config, projectRoot, afterImporter, resolved.absolute, newTarget, item.specifier);
      if (after === null) {
        unsupported.push({
          file: relativePath(projectRoot, importer),
          kind: item.kind,
          specifier: item.specifier,
          reason: "unsupported_nonrelative_or_nonpaths_specifier",
        });
        continue;
      }
      const position = sourceFile.getLineAndCharacterOfPosition(item.statement.getStart(sourceFile));
      impacts.push({
        importer: relativePath(projectRoot, importer),
        lineno: position.line + 1,
        kind: item.kind,
        statement: sourceStatement(sourceFile, item.statement),
        specifier: item.specifier,
        resolved_file: relativePath(projectRoot, resolved.absolute),
        after_move_specifier: after,
        new_resolved_file: relativePath(projectRoot, newTarget),
        scope: importerIsClusterMember ? "cluster_internal" : "project_importer",
      });
    }
  }
  return {
    impacts: impacts.sort((left, right) => left.importer.localeCompare(right.importer) || left.lineno - right.lineno || left.specifier.localeCompare(right.specifier)),
    unresolved: unresolved.sort((left, right) => left.file.localeCompare(right.file) || left.specifier.localeCompare(right.specifier)),
    unsupported: unsupported.sort((left, right) => left.file.localeCompare(right.file) || left.specifier.localeCompare(right.specifier)),
  };
}

function containsScratchSegment(projectRoot, parent) {
  return relativePath(projectRoot, parent).split("/").some((part) => SCRATCH_SEGMENTS.has(part));
}

function determineStatus({ targetExcluded, clusterSize, scratch, judgment, unresolved, unsupported, partial }) {
  if (targetExcluded) return { status: "deferred", recommendation: "defer_excluded_target" };
  if (clusterSize < 3) return { status: "deferred", recommendation: "defer_below_threshold" };
  if (scratch) return { status: "deferred", recommendation: "defer_scratch_code" };
  if (judgment === "cohesive") return { status: "deferred", recommendation: "defer_cohesive_cluster" };
  if (partial) return { status: "partial", recommendation: "defer_partial_config" };
  if (unresolved.length > 0) return { status: "blocked", recommendation: "defer_unresolved_imports" };
  if (unsupported.length > 0) return { status: "blocked", recommendation: "defer_unsupported_import_rewrite" };
  return { status: "ready", recommendation: "refactor" };
}

function makeCompatibility(projectRoot, parent, prefix, clusterFiles, impacts) {
  const parentRelative = relativePath(projectRoot, parent);
  const existingBarrels = [...new Set(
    impacts
      .filter((impact) => (activeLanguage === "javascript"
        ? /^index\.(?:js|jsx|mjs|cjs)$/i
        : /^index\.tsx?$/i).test(path.basename(impact.importer)))
      .map((impact) => impact.importer),
  )].sort();
  return {
    decision: "preserve_existing_barrels_migrate_subpaths",
    existing_barrels: existingBarrels,
    new_barrel: {
      path: `${parentRelative}/${prefix}/index.${activeLanguage === "javascript" ? "js" : "ts"}`,
      re_exports: clusterFiles.map((file) => ({
        specifier: `./${path.basename(file.new_path, path.extname(file.new_path))}`,
        symbols: file.exported_symbol_kinds
          .filter((symbol) => symbol.kind !== "interface" && symbol.kind !== "type")
          .map((symbol) => symbol.name),
        type_symbols: file.exported_symbol_kinds
          .filter((symbol) => symbol.kind === "interface" || symbol.kind === "type")
          .map((symbol) => symbol.name),
      })),
    },
    subpath_compatibility: "rewrite every resolved direct subpath importer; do not retain legacy file shims",
  };
}

function treeLines(items) {
  return items.length > 0 ? items.map((item) => `├── ${item}`).join("\n") : "└── (no eligible cluster files)";
}

function tableCell(value) {
  return String(value).replaceAll("|", "\\|");
}

function renderProposal(payload) {
  const languageLabel = payload.language === "javascript" ? "Checked-JavaScript" : "TypeScript";
  const barrelName = payload.language === "javascript" ? "index.js" : "index.ts";
  const lines = [
    `# ${languageLabel} folder reorganization proposal — ${payload.target.parent}::${payload.target.prefix}`,
    "",
    `> **Detected by:** an explicit ${languageLabel} cluster target or confirmed \`find-folder-topology-drift\` finding.`,
    "> **Executed by:** `/refactor-subsystem` only after human approval; this proposal is read-only.",
    "",
    `**Status:** \`${payload.status}\``,
    `**Recommendation:** \`${payload.recommendation}\``,
    `**Cluster size:** ${payload.summary.cluster_size} eligible source files`,
    `**Resolved import impact:** ${payload.summary.resolved_import_impact_count} static lines`,
    `**Named tsconfig:** \`${payload.tsconfig}\``,
    "",
    "## Scope and judgment boundary",
    "",
    `${languageLabel} v1 resolves only static \`import\`, \`export … from\`, \`import = require\`, and literal \`require(...)\` edges through the named host config. A human supplies \`split\` only after confirming the cluster creates a navigation problem; \`cohesive\` deliberately defers. Dynamic/runtime loading, framework conventions, and unresolvable non-\`paths\` package specifiers are not guessed.`,
    "",
    "## Current tree",
    "",
    "```text",
    `${payload.target.parent}/`,
    treeLines(payload.cluster_files.map((item) => item.current_path.slice(payload.target.parent.length + 1))),
    "```",
    "",
    "## Proposed tree",
    "",
    "```text",
    `${payload.target.parent}/`,
    `├── ${payload.target.prefix}/`,
    `│   ├── ${barrelName}  # new public barrel`,
    ...payload.cluster_files.map((item) => `│   ├── ${item.new_path.slice(`${payload.target.parent}/${payload.target.prefix}/`.length)}`),
    ...payload.compatibility.existing_barrels.map((barrel) => `├── ${barrel.slice(payload.target.parent.length + 1)}  # compatibility barrel updated`),
    "```",
    "",
    "## File-move table",
    "",
    "| Current path | New path | Exported symbols |",
    "|---|---|---|",
    ...payload.cluster_files.map((item) => `| \`${item.current_path}\` | \`${item.new_path}\` | ${item.public_symbols.map((symbol) => `\`${symbol}\``).join(", ") || "(none)"} |`),
    "",
    "## Complete resolved import-impact table",
    "",
    "| Importer | Kind | Current specifier | Resolved file | After-move specifier | New file | Scope |",
    "|---|---|---|---|---|---|---|",
    ...(payload.import_impact.length > 0
      ? payload.import_impact.map((item) => `| \`${item.importer}:${item.lineno}\` | ${item.kind} | \`${tableCell(item.specifier)}\` | \`${item.resolved_file}\` | \`${tableCell(item.after_move_specifier)}\` | \`${item.new_resolved_file}\` | ${item.scope} |`)
      : ["| (none) | — | — | — | — | — | — |"]),
    "",
    "## Barrel and subpath compatibility decision",
    "",
    `**Decision:** \`${payload.compatibility.decision}\`. ${payload.compatibility.subpath_compatibility}.`,
    "",
    `- Existing compatibility barrels: ${payload.compatibility.existing_barrels.length ? payload.compatibility.existing_barrels.map((item) => `\`${item}\``).join(", ") : "none"}.`,
    `- New domain barrel: \`${payload.compatibility.new_barrel.path}\`.`,
    ...payload.compatibility.new_barrel.re_exports.map((item) => `  - \`${item.specifier}\` re-exports ${[...item.symbols, ...item.type_symbols].map((symbol) => `\`${symbol}\``).join(", ") || "no public symbols"}.`),
    "",
    "## Characterization-test and native verification plan",
    "",
    "| Subject | Pre-move characterization action | Post-move proof |",
    "|---|---|---|",
    ...payload.cluster_files.map((item) => `| \`${item.current_path}\` | Pin its exported behavior before the move. | Run the same test after \`${item.new_path}\` is in place. |`),
    "",
    "Run the host-native check before and after the behavior-preserving move:",
    "",
    "```bash",
    "npm run typecheck",
    "```",
    "",
    "## Migration sequence",
    "",
    "1. Add the characterization tests named above and run them green against the current layout.",
    "2. Create the proposed directory and new domain barrel, then move every row in the file-move table.",
    "3. Apply every row in the complete resolved import-impact table; update existing barrels and direct subpath importers together.",
    "4. Run the characterization matrix and `npm run typecheck`. Do not include a behavior change in this move commit.",
  ];
  if (payload.unresolved_imports.length > 0 || payload.unsupported_import_rewrites.length > 0) {
    lines.push("", "## Unresolved module facts — proposal blocked", "");
    for (const item of [...payload.unresolved_imports, ...payload.unsupported_import_rewrites]) {
      lines.push(`- \`${item.file}\` — \`${item.specifier}\` (${item.kind}${item.reason ? `; ${item.reason}` : ""})`);
    }
    lines.push("Resolve these facts and re-run before treating the impact table as complete.");
  }
  if (payload.status === "deferred") {
    lines.push("", "## Deferral", "", `The proposal is intentionally deferred as \`${payload.recommendation}\`; no move is authorized.`);
  }
  if (payload.uncovered_files.length > 0) {
    lines.push("", "## Partial checked-JavaScript coverage", "");
    for (const file of payload.uncovered_files) lines.push(`- \`${file}\` is outside the named checked-JavaScript config.`);
    lines.push("Add every selected cluster file to the named config and rerun before treating this move plan as complete.");
  }
  lines.push("", "## Stop condition", "", "A human-approved refactor has moved every listed file, applied every listed resolved import rewrite, preserved the stated barrel surface, and passed its characterization tests plus `npm run typecheck`.", "");
  return lines.join("\n");
}

function writeAtomically(destination, contents) {
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  const temporary = `${destination}.tmp-${process.pid}`;
  fs.writeFileSync(temporary, contents, "utf8");
  fs.renameSync(temporary, destination);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  activeLanguage = args.language;
  const projectRoot = requireProjectRoot(args.projectRoot);
  const parent = resolveProjectPath(projectRoot, args.parent, "parent");
  existingPathWithoutSymlink(projectRoot, parent, "parent");
  if (!fs.lstatSync(parent).isDirectory()) fail(`parent is not a directory: ${parent}`);
  const proposalPath = safeArtifactPath(projectRoot, args.proposal, "proposal artifact");
  const inspectionPath = safeArtifactPath(projectRoot, args.inspection, "inspection artifact");
  const ts = loadProjectTypeScript(projectRoot);
  const config = loadTsconfig(ts, projectRoot, args.tsconfig, args.language);
  const exclusions = buildExclusionPolicy(projectRoot, config.declaredExcludes);
  const targetExcluded = exclusions.isExcluded(parent, true);
  const clusterPaths = collectCluster(parent, args.prefix, exclusions);
  const configuredFiles = new Set(config.fileNames);
  const uncoveredFiles = args.language === "javascript"
    ? clusterPaths.filter((file) => !configuredFiles.has(file)).map((file) => relativePath(projectRoot, file))
    : [];
  const clusterMoves = clusterPaths.map((current) => ({ current, next: newPathFor(parent, args.prefix, current) }));
  const program = ts.createProgram({
    rootNames: [...new Set([...config.fileNames, ...clusterPaths])],
    options: config.options,
    projectReferences: config.projectReferences,
  });
  const syntaxDiagnostics = clusterPaths.flatMap((file) => program.getSyntacticDiagnostics(program.getSourceFile(file)));
  if (syntaxDiagnostics.length > 0) fail(`${args.language === "javascript" ? "JavaScript" : "TypeScript"} syntax errors: ${diagnosticText(ts, syntaxDiagnostics[0])}`);
  const symbols = exportedSymbols(program, clusterPaths, projectRoot, ts);
  const moduleFacts = collectModuleFacts(program, clusterMoves, config, projectRoot, exclusions, ts);
  const clusterFiles = clusterMoves.map((move) => {
    const symbolRecord = symbols.find((item) => item.path === relativePath(projectRoot, move.current));
    return {
      current_path: relativePath(projectRoot, move.current),
      new_path: relativePath(projectRoot, move.next),
      public_symbols: symbolRecord?.symbols.map((item) => item.name) ?? [],
      exported_symbol_kinds: symbolRecord?.symbols ?? [],
    };
  });
  const status = determineStatus({
    targetExcluded,
    clusterSize: clusterFiles.length,
    scratch: containsScratchSegment(projectRoot, parent),
    judgment: args.judgment,
    unresolved: moduleFacts.unresolved,
    unsupported: moduleFacts.unsupported,
    partial: uncoveredFiles.length > 0,
  });
  const payload = {
    schema_version: 1,
    language: args.language,
    analyzer: args.language === "javascript" ? "typescript-compiler-api-checked-javascript" : "typescript-compiler-api",
    status: status.status,
    recommendation: status.recommendation,
    target: {
      parent: relativePath(projectRoot, parent),
      prefix: args.prefix,
      cluster_judgment: args.judgment,
      exclusion: targetExcluded ? "excluded" : "included",
    },
    tsconfig: relativePath(projectRoot, config.path),
    uncovered_files: uncoveredFiles,
    cluster_files: clusterFiles,
    import_impact: moduleFacts.impacts,
    unresolved_imports: moduleFacts.unresolved,
    unsupported_import_rewrites: moduleFacts.unsupported,
    compatibility: makeCompatibility(projectRoot, parent, args.prefix, clusterFiles, moduleFacts.impacts),
    summary: {
      cluster_size: clusterFiles.length,
      resolved_import_impact_count: moduleFacts.impacts.length,
      unresolved_import_count: moduleFacts.unresolved.length + moduleFacts.unsupported.length,
    },
    native_verification: {
      command: "npm run typecheck",
      required_before_and_after_move: true,
    },
  };
  writeAtomically(inspectionPath, `${JSON.stringify(payload, null, 2)}\n`);
  writeAtomically(proposalPath, renderProposal(payload));
  process.stdout.write(`wrote ${args.proposal} and ${args.inspection} (${payload.status})\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`[propose_typescript] ${error.message}\n`);
  process.exitCode = 2;
}
