#!/usr/bin/env node
/**
 * Produce the TypeScript/TSX v1 map-subsystem artifact.
 *
 * This is deliberately a family-local Compiler API consumer.  Its named
 * tsconfig resolver supplies the one supported module-resolution contract for
 * this skill: direct relative specifiers plus the host config's aliases and
 * project references.  It does not become a generic parser or fact platform.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const SOURCE_EXTENSIONS = new Set([".ts", ".tsx"]);
const BUILTIN_EXCLUDED_DIRECTORIES = new Set([
  ".git", ".venv", "venv", "node_modules", "dist", "build", "coverage",
  "__tests__", "test", "tests", "fixtures", "fixture", "generated", "vendor",
]);
const UNAVAILABLE_FIELDS = [
  {
    field: "responsibility_clusters",
    reason: "TypeScript v1 maps module facts and does not infer responsibility clusters.",
  },
  {
    field: "open_questions",
    reason: "TypeScript v1 does not generate judgment-oriented open questions.",
  },
];

class MapError extends Error {}

function fail(message) {
  throw new MapError(message);
}

function parseArgs(argv) {
  const values = new Map();
  const allowed = new Set([
    "--target", "--project-root", "--tsconfig", "--output", "--evidence", "--effectiveness-log",
  ]);
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!allowed.has(flag) || value === undefined || values.has(flag)) {
      fail(
        "usage: map_typescript.mjs --target <path> --project-root <path> --tsconfig <path> "
        + "--output <map.md> --evidence <map.json> [--effectiveness-log <jsonl>]",
      );
    }
    values.set(flag, value);
  }
  for (const required of ["--target", "--project-root", "--tsconfig", "--output", "--evidence"]) {
    if (!values.has(required)) fail(`missing required argument: ${required}`);
  }
  return {
    target: values.get("--target"),
    projectRoot: values.get("--project-root"),
    tsconfig: values.get("--tsconfig"),
    output: values.get("--output"),
    evidence: values.get("--evidence"),
    effectivenessLog: values.get("--effectiveness-log") ?? null,
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

function loadProjectTypeScript(projectRoot) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) {
    fail(`project-local TypeScript requires ${packageJson}`);
  }
  try {
    const requireFromProject = createRequire(packageJson);
    const resolved = requireFromProject.resolve("typescript");
    const resolvedRealPath = fs.realpathSync(resolved);
    if (!isWithin(projectRoot, resolvedRealPath)) {
      fail(`project-local TypeScript package is unavailable from ${packageJson}`);
    }
    const ts = requireFromProject("typescript");
    if (typeof ts.createProgram !== "function" || typeof ts.resolveModuleName !== "function") {
      fail("project-local TypeScript package lacks Compiler API module resolution");
    }
    return ts;
  } catch (error) {
    if (error instanceof MapError) throw error;
    fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`);
  }
}

function diagnosticText(ts, diagnostic) {
  const text = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
  if (!diagnostic.file) return text;
  const position = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start ?? 0);
  return `${diagnostic.file.fileName}:${position.line + 1}: ${text}`;
}

/** Resolve one named, project-local tsconfig into Compiler API program inputs. */
function resolveProjectTsconfig(ts, projectRoot, suppliedTsconfig) {
  const tsconfigPath = resolveProjectPath(projectRoot, suppliedTsconfig, "tsconfig");
  if (!fs.existsSync(tsconfigPath)) {
    fail(`project-local TypeScript requires tsconfig: ${tsconfigPath}`);
  }
  const tsconfigStats = fs.lstatSync(tsconfigPath);
  if (tsconfigStats.isSymbolicLink()) fail(`tsconfig must not be a symbolic link: ${tsconfigPath}`);
  if (!tsconfigStats.isFile()) fail(`project-local TypeScript requires tsconfig: ${tsconfigPath}`);
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

  function matchesDeclaredExclude(relative, directory) {
    return rules.some(({ rule, regex }) => {
      if (regex) return regex.test(relative) || (directory && regex.test(`${relative}/`));
      return relative === rule || relative.startsWith(`${rule}/`);
    });
  }

  return {
    isExcluded(absolutePath, directory = false) {
      const normalized = path.resolve(absolutePath);
      if (!isWithin(projectRoot, normalized)) return true;
      const relative = relativePath(projectRoot, normalized);
      const parts = relative.split("/");
      const directoryParts = directory ? parts : parts.slice(0, -1);
      if (directoryParts.some((part) => BUILTIN_EXCLUDED_DIRECTORIES.has(part.toLowerCase()))) return true;
      const filename = parts.at(-1)?.toLowerCase() ?? "";
      if (!directory && (
        filename.endsWith(".d.ts")
        || filename.endsWith(".d.tsx")
        || filename.endsWith(".test.ts")
        || filename.endsWith(".test.tsx")
        || filename.endsWith(".spec.ts")
        || filename.endsWith(".spec.tsx")
        || filename.endsWith(".generated.ts")
        || filename.endsWith(".generated.tsx")
        || filename.endsWith(".min.ts")
        || filename.endsWith(".min.tsx")
        || filename.endsWith(".bundle.ts")
        || filename.endsWith(".bundle.tsx")
        || filename.startsWith("test_")
        || filename.startsWith("tests_")
        || filename.endsWith("_test.ts")
        || filename.endsWith("_test.tsx")
      )) return true;
      return matchesDeclaredExclude(relative, directory);
    },
  };
}

function isSourcePath(absolutePath) {
  return SOURCE_EXTENSIONS.has(path.extname(absolutePath).toLowerCase())
    && !absolutePath.toLowerCase().endsWith(".d.ts")
    && !absolutePath.toLowerCase().endsWith(".d.tsx");
}

function collectTargetSources(target, projectRoot, exclusions) {
  if (traversesSymbolicLink(projectRoot, target)) {
    fail(`target must not traverse a symbolic link: ${target}`);
  }
  const targetStats = fs.lstatSync(target);
  if (targetStats.isSymbolicLink()) fail(`target must not be a symbolic link: ${target}`);
  if (targetStats.isFile()) {
    if (!isSourcePath(target)) fail(`target must be a .ts or .tsx file, or a directory: ${target}`);
    return exclusions.isExcluded(target) ? [] : [target];
  }
  if (!targetStats.isDirectory()) fail(`target must be a file or directory: ${target}`);
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

function moduleSpecifiers(sourceFile, ts) {
  const records = [];
  for (const statement of sourceFile.statements) {
    if (ts.isImportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteralLike(statement.moduleSpecifier)) {
      records.push({ kind: "import", specifier: statement.moduleSpecifier.text });
    } else if (ts.isExportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteralLike(statement.moduleSpecifier)) {
      records.push({ kind: "re_export", specifier: statement.moduleSpecifier.text });
    } else if (
      ts.isImportEqualsDeclaration(statement)
      && ts.isExternalModuleReference(statement.moduleReference)
      && statement.moduleReference.expression
      && ts.isStringLiteralLike(statement.moduleReference.expression)
    ) {
      records.push({ kind: "import_equals", specifier: statement.moduleReference.expression.text });
    }
  }
  return records;
}

function resolveSpecifier(ts, specifier, containingFile, options, moduleResolutionCache, projectRoot, exclusions) {
  const result = ts.resolveModuleName(specifier, containingFile, options, ts.sys, moduleResolutionCache);
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

function exportedSurface(program, targetFiles, projectRoot, ts) {
  const checker = program.getTypeChecker();
  const records = [];
  for (const file of targetFiles) {
    const sourceFile = program.getSourceFile(file);
    if (!sourceFile) continue;
    const moduleSymbol = checker.getSymbolAtLocation(sourceFile) ?? sourceFile.symbol;
    if (!moduleSymbol) continue;
    for (const symbol of checker.getExportsOfModule(moduleSymbol)) {
      const isAlias = Boolean(symbol.flags & ts.SymbolFlags.Alias);
      const resolvedSymbol = isAlias ? checker.getAliasedSymbol(symbol) : symbol;
      const declaration = resolvedSymbol.valueDeclaration ?? resolvedSymbol.declarations?.[0] ?? null;
      const declarationFile = declaration?.getSourceFile()?.fileName ?? sourceFile.fileName;
      records.push({
        file: relativePath(projectRoot, file),
        name: symbol.getName(),
        kind: symbolKind(ts, resolvedSymbol),
        reexported: isAlias || path.resolve(declarationFile) !== path.resolve(file),
      });
    }
  }
  return records.sort((left, right) => (
    left.file.localeCompare(right.file) || left.name.localeCompare(right.name)
  ));
}

function mapImports(program, targetFiles, projectRoot, config, exclusions, ts) {
  const targetSet = new Set(targetFiles.map((file) => path.resolve(file)));
  const moduleResolutionCache = ts.createModuleResolutionCache(
    projectRoot,
    (fileName) => fileName,
    config.options,
  );
  const sourceFiles = program.getSourceFiles().filter((sourceFile) => {
    const absolute = path.resolve(sourceFile.fileName);
    return (
      isWithin(projectRoot, absolute)
      && !traversesSymbolicLink(projectRoot, absolute)
      && isSourcePath(absolute)
      && !exclusions.isExcluded(absolute)
    );
  });
  const outbound = [];
  const inbound = [];
  const unresolved = [];
  const barrels = new Map();
  for (const sourceFile of sourceFiles) {
    const sourceAbsolute = path.resolve(sourceFile.fileName);
    const isTarget = targetSet.has(sourceAbsolute);
    for (const item of moduleSpecifiers(sourceFile, ts)) {
      const resolved = resolveSpecifier(
        ts,
        item.specifier,
        sourceAbsolute,
        config.options,
        moduleResolutionCache,
        projectRoot,
        exclusions,
      );
      if (resolved.resolution === "unresolved" || resolved.resolution === "unsafe_symlink") {
        if (isTarget) {
          unresolved.push({
            file: relativePath(projectRoot, sourceAbsolute),
            ...item,
            ...(resolved.resolution === "unsafe_symlink" ? { reason: "unsafe_symlink" } : {}),
          });
        }
        if (isTarget) outbound.push({ file: relativePath(projectRoot, sourceAbsolute), ...item, ...resolved });
        continue;
      }
      const resolvedAbsolute = resolved.resolved_file
        ? path.resolve(projectRoot, resolved.resolved_file)
        : null;
      const barrelBoundary = Boolean(
        resolvedAbsolute
        && targetSet.has(resolvedAbsolute)
        && /^index\.tsx?$/i.test(path.basename(resolvedAbsolute))
      );
      if (isTarget) {
        outbound.push({ file: relativePath(projectRoot, sourceAbsolute), ...item, ...resolved });
        if (item.kind === "re_export" && resolved.resolution === "resolved" && /^index\.tsx?$/i.test(path.basename(sourceAbsolute))) {
          const barrel = barrels.get(relativePath(projectRoot, sourceAbsolute)) ?? [];
          barrel.push({ specifier: item.specifier, resolved_file: resolved.resolved_file });
          barrels.set(relativePath(projectRoot, sourceAbsolute), barrel);
        }
      }
      if (!isTarget && resolvedAbsolute && targetSet.has(resolvedAbsolute)) {
        inbound.push({
          source_file: relativePath(projectRoot, sourceAbsolute),
          ...item,
          ...resolved,
          barrel_boundary: barrelBoundary,
        });
      }
    }
  }
  return {
    outbound: outbound.sort((left, right) => left.file.localeCompare(right.file) || left.specifier.localeCompare(right.specifier)),
    inbound: inbound.sort((left, right) => left.source_file.localeCompare(right.source_file) || left.specifier.localeCompare(right.specifier)),
    unresolved: unresolved.sort((left, right) => left.file.localeCompare(right.file) || left.specifier.localeCompare(right.specifier)),
    barrels: [...barrels.entries()]
      .map(([file, reExports]) => ({ file, re_exports: reExports.sort((left, right) => left.specifier.localeCompare(right.specifier)) }))
      .sort((left, right) => left.file.localeCompare(right.file)),
  };
}

function collectWorkflowParticipation(projectRoot, targetFiles) {
  const workflowRoot = path.join(projectRoot, ".claude", "docs", "workflows");
  if (!fs.existsSync(workflowRoot) || !fs.statSync(workflowRoot).isDirectory()) {
    return { availability: "unavailable", reason: "No .claude/docs/workflows directory exists in this host.", entries: [] };
  }
  const targetPaths = targetFiles.map((file) => relativePath(projectRoot, file));
  const entries = [];
  const pending = [workflowRoot];
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      if (entry.isSymbolicLink()) continue;
      const file = path.join(current, entry.name);
      if (entry.isDirectory()) {
        pending.push(file);
      } else if (entry.isFile() && entry.name.endsWith(".md")) {
        const text = fs.readFileSync(file, "utf8");
        const matchedPaths = targetPaths.filter((targetPath) => text.includes(targetPath));
        if (matchedPaths.length > 0) {
          entries.push({
            name: path.basename(entry.name, ".md"),
            path: relativePath(projectRoot, file),
            matched_paths: matchedPaths,
          });
        }
      }
    }
  }
  return {
    availability: "available",
    entries: entries.sort((left, right) => left.path.localeCompare(right.path)),
  };
}

function targetDiagnostics(ts, program, targetFiles) {
  const targetSet = new Set(targetFiles.map((file) => path.resolve(file)));
  const diagnostics = ts.getPreEmitDiagnostics(program).filter((diagnostic) => (
    diagnostic.file && targetSet.has(path.resolve(diagnostic.file.fileName))
  ));
  return {
    availability: "available",
    count: diagnostics.length,
    diagnostics: diagnostics.map((diagnostic) => ({
      code: diagnostic.code,
      message: diagnosticText(ts, diagnostic),
    })),
  };
}

function renderMap(payload) {
  const lines = [
    "---",
    `subsystem: ${payload.name}`,
    `target: ${payload.target.path}`,
    `language: ${payload.language}`,
    `status: ${payload.status}`,
    `source_files: ${payload.counts.source_files}`,
    `exported_symbols: ${payload.counts.exported_symbols}`,
    `inbound_imports: ${payload.counts.inbound_imports}`,
    `outbound_imports: ${payload.counts.outbound_imports}`,
    "---",
    "",
    `# ${payload.name}`,
    "",
    `Status: **${payload.status}**. Compiler-backed map using the host project's pinned TypeScript package and \`${payload.tsconfig}\`.`,
    "",
    "## Counts",
    "",
    "| Source files | Exported symbols | Outbound imports | Inbound imports | Unresolved imports | Workflow entries |",
    "|--:|--:|--:|--:|--:|--:|",
    `| ${payload.counts.source_files} | ${payload.counts.exported_symbols} | ${payload.counts.outbound_imports} | ${payload.counts.inbound_imports} | ${payload.counts.unresolved_imports} | ${payload.counts.workflow_entries} |`,
    "",
    "## Exported surface",
    "",
  ];
  if (payload.exported_surface.length === 0) lines.push("No eligible TypeScript/TSX source files were in scope.");
  for (const item of payload.exported_surface) {
    lines.push(`- \`${item.file}\` — \`${item.name}\` (${item.kind}${item.reexported ? ", re-export" : ""})`);
  }
  lines.push("", "## Resolved outbound imports", "");
  if (payload.outbound_imports.length === 0) lines.push("None.");
  for (const edge of payload.outbound_imports) {
    lines.push(`- \`${edge.file}\` — \`${edge.specifier}\` → ${edge.resolved_file ? `\`${edge.resolved_file}\`` : edge.resolution} (${edge.resolution})`);
  }
  lines.push("", "## Resolved inbound imports", "");
  if (payload.inbound_imports.length === 0) lines.push("None.");
  for (const edge of payload.inbound_imports) {
    lines.push(`- \`${edge.source_file}\` — \`${edge.specifier}\` → \`${edge.resolved_file}\`${edge.barrel_boundary ? " (barrel boundary)" : ""}`);
  }
  lines.push("", "## Barrel boundaries", "");
  if (payload.barrel_boundaries.length === 0) lines.push("None.");
  for (const barrel of payload.barrel_boundaries) {
    lines.push(`- \`${barrel.file}\`: ${barrel.re_exports.map((edge) => `\`${edge.specifier}\` → \`${edge.resolved_file}\``).join(", ")}`);
  }
  lines.push("", "## Workflow participation", "");
  if (payload.workflow_participation.availability === "unavailable") {
    lines.push(`Unavailable: ${payload.workflow_participation.reason}`);
  } else if (payload.workflow_participation.entries.length === 0) {
    lines.push("No workflow map references the selected source files.");
  } else {
    for (const entry of payload.workflow_participation.entries) {
      lines.push(`- \`${entry.path}\` — ${entry.matched_paths.map((item) => `\`${item}\``).join(", ")}`);
    }
  }
  lines.push("", "## Applicable compliance", "");
  lines.push(`- TypeScript diagnostics: ${payload.compliance.typescript_diagnostics.count} (${payload.compliance.typescript_diagnostics.availability})`);
  lines.push(`- ESLint: ${payload.compliance.eslint.availability} — ${payload.compliance.eslint.reason}`);
  lines.push("", "## Unavailable fields", "");
  for (const field of payload.unavailable_fields) lines.push(`- \`${field.field}\` — ${field.reason}`);
  if (payload.unresolved_imports.length > 0) {
    lines.push("", "## Incomplete module resolution", "");
    for (const unresolved of payload.unresolved_imports) {
      lines.push(`- \`${unresolved.file}\` — \`${unresolved.specifier}\` (${unresolved.kind})`);
    }
  }
  lines.push("", "## How to regenerate", "", "Run the documented TypeScript map command from the project root.", "");
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
  const projectRoot = requireExistingDirectory(path.resolve(args.projectRoot), "project root");
  const target = resolveProjectPath(projectRoot, args.target, "target");
  if (!fs.existsSync(target)) fail(`target does not exist: ${target}`);
  if (traversesSymbolicLink(projectRoot, target)) fail(`target must not traverse a symbolic link: ${target}`);
  const targetStats = fs.lstatSync(target);
  if (targetStats.isSymbolicLink()) fail(`target must not be a symbolic link: ${target}`);
  const ts = loadProjectTypeScript(projectRoot);
  const config = resolveProjectTsconfig(ts, projectRoot, args.tsconfig);
  const exclusions = buildExclusionPolicy(projectRoot, config.declaredExcludes);
  const targetFiles = collectTargetSources(target, projectRoot, exclusions);
  const rootNames = [...new Set([...config.fileNames, ...targetFiles])];
  const program = ts.createProgram({
    rootNames,
    options: config.options,
    projectReferences: config.projectReferences,
  });
  const syntaxDiagnostics = targetFiles.flatMap((file) => program.getSyntacticDiagnostics(program.getSourceFile(file)));
  if (syntaxDiagnostics.length > 0) {
    fail(`TypeScript syntax errors: ${diagnosticText(ts, syntaxDiagnostics[0])}`);
  }
  const imports = mapImports(program, targetFiles, projectRoot, config, exclusions, ts);
  const exported = exportedSurface(program, targetFiles, projectRoot, ts);
  const workflows = collectWorkflowParticipation(projectRoot, targetFiles);
  const typeDiagnostics = targetDiagnostics(ts, program, targetFiles);
  const targetExcluded = targetFiles.length === 0 && exclusions.isExcluded(target, targetStats.isDirectory());
  const status = imports.unresolved.length > 0 ? "partial" : "complete";
  const name = path.basename(target, path.extname(target)) || "typescript-subsystem";
  const payload = {
    schema_version: 1,
    name,
    language: "typescript",
    analyzer: "typescript-compiler-api",
    status,
    target: {
      path: relativePath(projectRoot, target),
      kind: targetStats.isDirectory() ? "directory" : "file",
      exclusion: targetExcluded ? "excluded" : "included",
    },
    tsconfig: relativePath(projectRoot, config.path),
    completeness: {
      inventory: "complete",
      exports: "complete",
      module_resolution: imports.unresolved.length > 0 ? "partial" : "complete",
      workflow_participation: workflows.availability === "available" ? "complete" : "unavailable",
    },
    counts: {
      source_files: targetFiles.length,
      exported_symbols: exported.length,
      outbound_imports: imports.outbound.length,
      inbound_imports: imports.inbound.length,
      unresolved_imports: imports.unresolved.length,
      workflow_entries: workflows.entries.length,
    },
    files: targetFiles.map((file) => ({ file: relativePath(projectRoot, file) })),
    exported_surface: exported,
    outbound_imports: imports.outbound,
    inbound_imports: imports.inbound,
    unresolved_imports: imports.unresolved,
    barrel_boundaries: imports.barrels,
    workflow_participation: workflows,
    compliance: {
      typescript_diagnostics: typeDiagnostics,
      eslint: {
        availability: "unavailable",
        reason: "TypeScript v1 does not infer or execute a host ESLint policy.",
      },
    },
    unavailable_fields: UNAVAILABLE_FIELDS,
  };
  writeAtomically(path.resolve(args.evidence), `${JSON.stringify(payload, null, 2)}\n`);
  writeAtomically(path.resolve(args.output), renderMap(payload));
  if (args.effectivenessLog) {
    const logPath = path.resolve(args.effectivenessLog);
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    fs.appendFileSync(logPath, `${JSON.stringify({
      skill: "map-subsystem",
      scan_id: `map-typescript-${Date.now()}`,
      ts: new Date().toISOString(),
      target: payload.target.path,
      findings_total: payload.counts.exported_symbols,
      buckets: payload.counts,
      status,
    })}\n`, "utf8");
  }
  process.stdout.write(`wrote ${args.output} and ${args.evidence} (${status})\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`[map_typescript] ${error.message}\n`);
  process.exitCode = 2;
}
