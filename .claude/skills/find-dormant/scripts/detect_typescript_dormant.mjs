#!/usr/bin/env node
/**
 * Produce a conservative TypeScript/TSX dormant-code review report.
 *
 * This is a family-local Compiler API consumer. It establishes only one fact:
 * a non-exported top-level implementation has no statically resolved symbol
 * references in the eligible project sources. Dynamic, external, registry,
 * event, and framework reachability remain uncertainty, never deletion proof.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const SOURCE_EXTENSIONS = new Set([".ts", ".tsx"]);
const BUILTIN_EXCLUDED_DIRECTORIES = new Set([
  ".git", ".venv", "venv", "node_modules", "dist", "build", "coverage",
  "__tests__", "test", "tests", "fixtures", "fixture", "generated", "vendor",
]);

class DormantError extends Error {}

function fail(message) {
  throw new DormantError(message);
}

function parseArgs(argv) {
  const values = new Map();
  const allowed = new Set(["--target", "--project-root", "--tsconfig", "--report-dir"]);
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!allowed.has(flag) || value === undefined || values.has(flag)) {
      fail(
        "usage: detect_typescript_dormant.mjs --target <path> --project-root <path> "
        + "--tsconfig <path> --report-dir <reports/find-dormant/scan>",
      );
    }
    values.set(flag, value);
  }
  for (const required of ["--target", "--project-root", "--tsconfig", "--report-dir"]) {
    if (!values.has(required)) fail(`missing required argument: ${required}`);
  }
  return {
    target: values.get("--target"),
    projectRoot: values.get("--project-root"),
    tsconfig: values.get("--tsconfig"),
    reportDir: values.get("--report-dir"),
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
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) return true;
  }
  return false;
}

function safeReportDirectory(projectRoot, suppliedPath) {
  const reportDir = resolveProjectPath(projectRoot, suppliedPath, "report directory");
  const allowedRoot = path.join(projectRoot, "reports", "find-dormant");
  if (!isWithin(allowedRoot, reportDir) || reportDir === allowedRoot) {
    fail(`report directory must stay beneath reports/find-dormant/: ${suppliedPath}`);
  }
  if (traversesSymbolicLink(projectRoot, reportDir)) {
    fail(`report directory must not traverse a symbolic link: ${suppliedPath}`);
  }
  return reportDir;
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
    if (
      typeof ts.createProgram !== "function"
      || typeof ts.resolveModuleName !== "function"
      || typeof ts.createModuleResolutionCache !== "function"
    ) {
      fail("project-local TypeScript package lacks the required Compiler API");
    }
    return ts;
  } catch (error) {
    if (error instanceof DormantError) throw error;
    fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`);
  }
}

function diagnosticText(ts, diagnostic) {
  const text = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
  if (!diagnostic.file) return text;
  const position = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start ?? 0);
  return `${diagnostic.file.fileName}:${position.line + 1}: ${text}`;
}

function resolveProjectTsconfig(ts, projectRoot, suppliedTsconfig) {
  const tsconfigPath = resolveProjectPath(projectRoot, suppliedTsconfig, "tsconfig");
  if (!fs.existsSync(tsconfigPath)) {
    fail(`project-local TypeScript requires tsconfig: ${tsconfigPath}`);
  }
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

function collectEligibleProgramSources(program, projectRoot, exclusions) {
  return program.getSourceFiles().filter((sourceFile) => {
    const absolute = path.resolve(sourceFile.fileName);
    return (
      isWithin(projectRoot, absolute)
      && !traversesSymbolicLink(projectRoot, absolute)
      && isSourcePath(absolute)
      && !exclusions.isExcluded(absolute)
    );
  });
}

function canonicalSymbol(checker, symbol, ts) {
  if (symbol && (symbol.flags & ts.SymbolFlags.Alias)) return checker.getAliasedSymbol(symbol);
  return symbol;
}

function exportedSymbols(checker, sourceFile, ts) {
  const moduleSymbol = checker.getSymbolAtLocation(sourceFile) ?? sourceFile.symbol;
  if (!moduleSymbol) return new Set();
  return new Set(
    checker.getExportsOfModule(moduleSymbol).map((symbol) => canonicalSymbol(checker, symbol, ts)),
  );
}

function hasDecorators(node, ts) {
  return ts.canHaveDecorators(node) && (ts.getDecorators(node)?.length ?? 0) > 0;
}

function candidateDeclarations(targetFiles, program, projectRoot, ts) {
  const checker = program.getTypeChecker();
  const candidates = [];
  for (const file of targetFiles) {
    const sourceFile = program.getSourceFile(file);
    if (!sourceFile) continue;
    const exported = exportedSymbols(checker, sourceFile, ts);
    const add = (nameNode, kind, declaration) => {
      if (!nameNode || hasDecorators(declaration, ts)) return;
      const symbol = canonicalSymbol(checker, checker.getSymbolAtLocation(nameNode), ts);
      if (!symbol || exported.has(symbol)) return;
      const line = sourceFile.getLineAndCharacterOfPosition(nameNode.getStart(sourceFile)).line + 1;
      const filePath = relativePath(projectRoot, file);
      candidates.push({
        id: `${filePath.replaceAll("/", "-").replace(/[^A-Za-z0-9_-]/g, "-")}-${nameNode.text}-${line}`,
        file: filePath,
        line,
        name: nameNode.text,
        kind,
        symbol,
        nameNode,
      });
    };
    for (const statement of sourceFile.statements) {
      if (ts.isFunctionDeclaration(statement) && statement.name) {
        add(statement.name, "function", statement);
      } else if (ts.isClassDeclaration(statement) && statement.name) {
        add(statement.name, "class", statement);
      } else if (ts.isVariableStatement(statement)) {
        for (const declaration of statement.declarationList.declarations) {
          if (
            ts.isIdentifier(declaration.name)
            && declaration.initializer
            && (ts.isArrowFunction(declaration.initializer) || ts.isFunctionExpression(declaration.initializer))
          ) {
            add(declaration.name, "variable_function", declaration);
          }
        }
      }
    }
  }
  return candidates.sort((left, right) => left.id.localeCompare(right.id));
}

function resolveStaticModuleSpecifiers(ts, sourceFile) {
  const specifiers = [];
  for (const statement of sourceFile.statements) {
    if (ts.isImportDeclaration(statement) && ts.isStringLiteralLike(statement.moduleSpecifier)) {
      specifiers.push(statement.moduleSpecifier.text);
    } else if (ts.isExportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteralLike(statement.moduleSpecifier)) {
      specifiers.push(statement.moduleSpecifier.text);
    } else if (
      ts.isImportEqualsDeclaration(statement)
      && ts.isExternalModuleReference(statement.moduleReference)
      && statement.moduleReference.expression
      && ts.isStringLiteralLike(statement.moduleReference.expression)
    ) {
      specifiers.push(statement.moduleReference.expression.text);
    }
  }
  return specifiers;
}

function unresolvedModules(ts, sourceFiles, config, projectRoot) {
  const cache = ts.createModuleResolutionCache(projectRoot, (fileName) => fileName, config.options);
  const unresolved = [];
  for (const sourceFile of sourceFiles) {
    const sourceAbsolute = path.resolve(sourceFile.fileName);
    for (const specifier of resolveStaticModuleSpecifiers(ts, sourceFile)) {
      const result = ts.resolveModuleName(specifier, sourceAbsolute, config.options, ts.sys, cache);
      if (!result.resolvedModule) {
        unresolved.push({ file: relativePath(projectRoot, sourceAbsolute), specifier });
      }
    }
  }
  return unresolved.sort((left, right) => left.file.localeCompare(right.file) || left.specifier.localeCompare(right.specifier));
}

function countStaticReferences(candidates, sourceFiles, program, ts) {
  const checker = program.getTypeChecker();
  const bySymbol = new Map(candidates.map((candidate) => [candidate.symbol, candidate]));
  const references = new Map(candidates.map((candidate) => [candidate, 0]));
  const namesInStrings = new Set();
  for (const sourceFile of sourceFiles) {
    const visit = (node) => {
      if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
        namesInStrings.add(node.text);
      }
      if (ts.isIdentifier(node)) {
        const symbol = canonicalSymbol(checker, checker.getSymbolAtLocation(node), ts);
        const candidate = bySymbol.get(symbol);
        if (candidate && node !== candidate.nameNode) {
          references.set(candidate, (references.get(candidate) ?? 0) + 1);
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return { references, namesInStrings };
}

function finalFindings(candidates, staticFacts) {
  const reviewCandidates = [];
  const uncertainSymbols = [];
  for (const candidate of candidates) {
    const staticReferences = staticFacts.references.get(candidate) ?? 0;
    if (staticReferences > 0) continue;
    if (staticFacts.namesInStrings.has(candidate.name)) {
      uncertainSymbols.push({
        file: candidate.file,
        line: candidate.line,
        name: candidate.name,
        kind: candidate.kind,
        reason: "A matching string literal may be dynamic reachability; static analysis cannot resolve it.",
        verdict: "uncertain",
      });
      continue;
    }
    reviewCandidates.push({
      id: candidate.id,
      file: candidate.file,
      line: candidate.line,
      name: candidate.name,
      kind: candidate.kind,
      static_references: 0,
      verdict: "review_required",
      recommendation: "human_review_only",
      uncertainty: [
        "Static analysis cannot establish dynamic, external, registry, event, or framework reachability.",
      ],
    });
  }
  return {
    candidates: reviewCandidates.sort((left, right) => left.id.localeCompare(right.id)),
    uncertainSymbols: uncertainSymbols.sort((left, right) => (
      left.file.localeCompare(right.file) || left.line - right.line || left.name.localeCompare(right.name)
    )),
  };
}

function renderReport(payload) {
  const lines = [
    "# TypeScript dormant-code audit",
    "",
    `Status: **${payload.status}**. Compiler-backed static reference inventory for \`${payload.target.path}\`.`,
    "",
    "## Never safe deletion from static evidence",
    "",
    "Every result is human-review-only. Dynamic, external, registry, event, and framework reachability are outside this v1 contract.",
    "",
    "## Summary",
    "",
    `- Review-required static candidates: ${payload.summary.review_required}`,
    `- Uncertain symbols: ${payload.summary.uncertain}`,
    "- Certain-delete findings: 0 (not a TypeScript v1 outcome)",
    "",
    "## Review-required static candidates",
    "",
  ];
  if (payload.candidates.length === 0) lines.push("None.");
  for (const candidate of payload.candidates) {
    lines.push(`- \`${candidate.file}:${candidate.line}\` — \`${candidate.name}\` (${candidate.kind}); ${candidate.recommendation}`);
  }
  lines.push("", "## Uncertain symbols", "");
  if (payload.uncertain_symbols.length === 0) lines.push("None.");
  for (const item of payload.uncertain_symbols) {
    lines.push(`- \`${item.file}:${item.line}\` — \`${item.name}\`: ${item.reason}`);
  }
  lines.push("", "## Project resolution", "");
  lines.push(`State: **${payload.project_resolution.state}**.`);
  if (payload.project_resolution.unresolved_modules.length === 0) {
    lines.push("All eligible static module specifiers resolved through the named tsconfig.");
  } else {
    for (const item of payload.project_resolution.unresolved_modules) {
      lines.push(`- \`${item.file}\` — unresolved \`${item.specifier}\``);
    }
  }
  lines.push("", "## How to act", "");
  lines.push("Inspect each result with runtime/framework knowledge before any deletion discussion; this report does not authorize a deletion.", "");
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
  const reportDir = safeReportDirectory(projectRoot, args.reportDir);
  const ts = loadProjectTypeScript(projectRoot);
  const config = resolveProjectTsconfig(ts, projectRoot, args.tsconfig);
  const exclusions = buildExclusionPolicy(projectRoot, config.declaredExcludes);
  const targetFiles = collectTargetSources(target, projectRoot, exclusions);
  const program = ts.createProgram({
    rootNames: [...new Set([...config.fileNames, ...targetFiles])],
    options: config.options,
    projectReferences: config.projectReferences,
  });
  const syntaxDiagnostics = program.getSyntacticDiagnostics().filter((diagnostic) => {
    if (!diagnostic.file) return false;
    const source = path.resolve(diagnostic.file.fileName);
    return isWithin(projectRoot, source) && !exclusions.isExcluded(source);
  });
  if (syntaxDiagnostics.length > 0) {
    fail(`TypeScript syntax errors: ${diagnosticText(ts, syntaxDiagnostics[0])}`);
  }
  const eligibleSources = collectEligibleProgramSources(program, projectRoot, exclusions);
  const staticCandidates = candidateDeclarations(targetFiles, program, projectRoot, ts);
  const staticFacts = countStaticReferences(staticCandidates, eligibleSources, program, ts);
  const findings = finalFindings(staticCandidates, staticFacts);
  const unresolved = unresolvedModules(ts, eligibleSources, config, projectRoot);
  const targetExcluded = targetFiles.length === 0 && exclusions.isExcluded(target, targetStats.isDirectory());
  const payload = {
    schema_version: 1,
    language: "typescript",
    analyzer: "typescript-compiler-api",
    status: unresolved.length > 0 ? "partial" : "complete",
    target: {
      path: relativePath(projectRoot, target),
      kind: targetStats.isDirectory() ? "directory" : "file",
      exclusion: targetExcluded ? "excluded" : "included",
    },
    tsconfig: relativePath(projectRoot, config.path),
    project_resolution: {
      state: unresolved.length > 0 ? "partial" : "complete",
      unresolved_modules: unresolved,
    },
    scope: {
      supported: "Non-exported top-level TypeScript/TSX implementation declarations with zero statically resolved references.",
      excluded: "Routes, endpoints, error swallowing, dynamic imports, external consumers, and framework/runtime reachability.",
    },
    candidates: findings.candidates,
    uncertain_symbols: findings.uncertainSymbols,
    summary: {
      review_required: findings.candidates.length,
      uncertain: findings.uncertainSymbols.length,
      certain_delete: 0,
    },
  };
  writeAtomically(path.join(reportDir, "findings.json"), `${JSON.stringify(payload, null, 2)}\n`);
  writeAtomically(path.join(reportDir, "report.md"), renderReport(payload));
  console.error(
    `[find-dormant-typescript] wrote ${reportDir} `
    + `(review_required=${payload.summary.review_required} uncertain=${payload.summary.uncertain} status=${payload.status})`,
  );
}

try {
  main();
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[find-dormant-typescript] ERROR: ${message}`);
  process.exitCode = 2;
}
