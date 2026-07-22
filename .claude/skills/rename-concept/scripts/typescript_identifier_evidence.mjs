#!/usr/bin/env node
/**
 * Resolve TypeScript identifier evidence for rename-concept without mutation.
 *
 * The host owns the pinned `typescript` package. This runner loads that package
 * from <project-root>/node_modules, receives only Python-vetted root-contained
 * TS/TSX files, and emits JSON evidence. It never edits source files.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";


function usage(message) {
  if (message) process.stderr.write(`${message}\n`);
  process.stderr.write(
    "usage: typescript_identifier_evidence.mjs --project-root DIR --old-terms JSON --new-terms JSON --sources JSON --output FILE [--language typescript|javascript] [--config jsconfig.json]\n",
  );
  process.exit(2);
}


function argumentsMap(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) usage(`invalid argument: ${key ?? ""}`);
    values.set(key.slice(2), value);
  }
  return values;
}


function writeJson(output, payload) {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}


function isWithin(candidate, root) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== "..");
}


function lineOf(sourceFile, position) {
  return sourceFile.getLineAndCharacterOfPosition(position).line + 1;
}


function sourceLabel(sourceFile, root) {
  return path.relative(root, sourceFile.fileName).split(path.sep).join("/");
}


function statementFor(node, ts) {
  let cursor = node;
  while (cursor && !ts.isSourceFile(cursor)) {
    if (
      ts.isVariableStatement(cursor)
      || ts.isFunctionDeclaration(cursor)
      || ts.isClassDeclaration(cursor)
      || ts.isInterfaceDeclaration(cursor)
      || ts.isTypeAliasDeclaration(cursor)
      || ts.isEnumDeclaration(cursor)
    ) {
      return cursor;
    }
    cursor = cursor.parent;
  }
  return undefined;
}


function isTopLevelExport(node, ts) {
  const statement = statementFor(node, ts);
  return Boolean(
    statement
      && ts.isSourceFile(statement.parent)
      && (ts.getCombinedModifierFlags(statement) & ts.ModifierFlags.Export),
  );
}


function identifierName(node, ts) {
  if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) return node.name;
  if (
    (ts.isFunctionDeclaration(node)
      || ts.isClassDeclaration(node)
      || ts.isInterfaceDeclaration(node)
      || ts.isTypeAliasDeclaration(node)
      || ts.isEnumDeclaration(node))
    && node.name
    && ts.isIdentifier(node.name)
  ) {
    return node.name;
  }
  return undefined;
}


function isPropertyName(node, ts) {
  const parent = node.parent;
  return Boolean(
    (ts.isPropertyAssignment(parent) && parent.name === node)
      || (ts.isPropertyDeclaration(parent) && parent.name === node)
      || (ts.isPropertySignature(parent) && parent.name === node)
      || (ts.isMethodDeclaration(parent) && parent.name === node)
      || (ts.isMethodSignature(parent) && parent.name === node)
      || (ts.isPropertyAccessExpression(parent) && parent.name === node),
  );
}


function isLocalDeclaration(symbol, ts) {
  const declaration = symbol?.valueDeclaration ?? symbol?.declarations?.[0];
  if (!declaration) return false;
  const statement = statementFor(declaration, ts);
  return Boolean(statement && !ts.isSourceFile(statement.parent));
}


function isTopLevelUnexportedDeclaration(symbol, ts) {
  const declaration = symbol?.valueDeclaration ?? symbol?.declarations?.[0];
  const statement = declaration ? statementFor(declaration, ts) : undefined;
  return Boolean(statement && ts.isSourceFile(statement.parent) && !isTopLevelExport(declaration, ts));
}


function resolvedSymbol(symbol, checker, ts) {
  if (symbol && (symbol.flags & ts.SymbolFlags.Alias)) {
    try {
      return checker.getAliasedSymbol(symbol) || symbol;
    } catch {
      return symbol;
    }
  }
  return symbol;
}


function parseJson(value, name) {
  try {
    return JSON.parse(value);
  } catch {
    usage(`${name} must be JSON`);
  }
}


const values = argumentsMap(process.argv.slice(2));
const projectRootRaw = values.get("project-root");
const outputRaw = values.get("output");
if (!projectRootRaw || !outputRaw) usage("--project-root and --output are required");

const projectRoot = fs.realpathSync(projectRootRaw);
const output = path.resolve(outputRaw);
const oldTerms = parseJson(values.get("old-terms") ?? "[]", "--old-terms");
const newTerms = parseJson(values.get("new-terms") ?? "[]", "--new-terms");
const sourceLabels = parseJson(values.get("sources") ?? "[]", "--sources");
if (![oldTerms, newTerms, sourceLabels].every(Array.isArray)) usage("terms and sources must be JSON arrays");
const language = values.get("language") ?? "typescript";
if (!["typescript", "javascript"].includes(language)) usage("--language must be typescript or javascript");
const suppliedConfig = values.get("config") ?? (language === "javascript" ? "jsconfig.json" : "tsconfig.json");

let ts;
try {
  const hostRequire = createRequire(path.join(projectRoot, "__rename_concept_host__.cjs"));
  const packagePath = fs.realpathSync(hostRequire.resolve("typescript"));
  if (!isWithin(packagePath, projectRoot)) {
    throw new Error("resolved TypeScript package is outside the project root");
  }
  ts = hostRequire(packagePath);
} catch (error) {
  writeJson(output, {
    status: "unavailable",
    reason: "host TypeScript package is unavailable",
    detail: String(error?.message ?? error),
  });
  process.exit(3);
}

const sourcePaths = [];
const sourceSuffixes = language === "javascript" ? new Set([".js", ".jsx", ".mjs", ".cjs"]) : new Set([".ts", ".tsx"]);
for (const label of sourceLabels) {
  if (typeof label !== "string") continue;
  const candidate = path.resolve(projectRoot, label);
  try {
    const resolved = fs.realpathSync(candidate);
    if (isWithin(resolved, projectRoot) && fs.statSync(resolved).isFile() && sourceSuffixes.has(path.extname(resolved).toLowerCase())) sourcePaths.push(resolved);
  } catch {
    // The Python caller already filtered safe files. A concurrent deletion is
    // represented by absence rather than following a new filesystem path.
  }
}

function diagnosticRecord(diagnostic, kind) {
  const sourceFile = diagnostic.file;
  return {
    kind,
    code: diagnostic.code,
    category: ts.DiagnosticCategory[diagnostic.category],
    file: sourceFile ? sourceLabel(sourceFile, projectRoot) : null,
    line: sourceFile && diagnostic.start !== undefined ? lineOf(sourceFile, diagnostic.start) : null,
    message: ts.flattenDiagnosticMessageText(diagnostic.messageText, " "),
  };
}

const configPath = path.resolve(projectRoot, suppliedConfig);
let compilerOptions = {
  target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.NodeNext,
  moduleResolution: ts.ModuleResolutionKind.NodeNext,
  noEmit: true,
  skipLibCheck: true,
};
const configDiagnostics = [];
if (fs.existsSync(configPath) && isWithin(configPath, projectRoot) && !fs.lstatSync(configPath).isSymbolicLink()) {
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  if (config.error) {
    configDiagnostics.push(diagnosticRecord(config.error, "config"));
  } else {
    const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, projectRoot);
    configDiagnostics.push(...parsed.errors.map((diagnostic) => diagnosticRecord(diagnostic, "config")));
    compilerOptions = { ...compilerOptions, ...parsed.options };
  }
} else if (language === "javascript") {
  writeJson(output, {
    status: "unsupported",
    language,
    reason: "checked JavaScript requires an explicit project-local jsconfig/tsconfig",
    config: suppliedConfig,
  });
  process.exit(3);
}
if (language === "javascript" && (!compilerOptions.allowJs || !compilerOptions.checkJs)) {
  writeJson(output, {
    status: "unsupported",
    language,
    reason: "checked JavaScript requires compilerOptions.allowJs and compilerOptions.checkJs set to true",
    config: sourceLabel({ fileName: configPath }, projectRoot),
  });
  process.exit(3);
}

const configForCoverage = ts.readConfigFile(configPath, ts.sys.readFile);
const parsedForCoverage = configForCoverage.error ? null : ts.parseJsonConfigFileContent(configForCoverage.config, ts.sys, path.dirname(configPath));
const configuredFiles = new Set((parsedForCoverage?.fileNames ?? sourcePaths).map((source) => path.resolve(source)));
const uncoveredFiles = language === "javascript"
  ? sourcePaths.filter((source) => !configuredFiles.has(source)).map((source) => sourceLabel({ fileName: source }, projectRoot))
  : [];
const coveredSources = language === "javascript" ? sourcePaths.filter((source) => configuredFiles.has(source)) : sourcePaths;
const program = ts.createProgram({ rootNames: language === "javascript" ? [...configuredFiles] : sourcePaths, options: compilerOptions });
const checker = program.getTypeChecker();
const oldNames = new Set(oldTerms.filter((term) => typeof term === "string"));
const newNames = new Set(newTerms.filter((term) => typeof term === "string"));
const oldSymbols = new Set();
const newSymbols = new Set();
const declarations = { old: [], new: [] };

for (const sourcePath of coveredSources) {
  const sourceFile = program.getSourceFile(sourcePath);
  if (!sourceFile) continue;
  const visitDeclaration = (node) => {
    const name = identifierName(node, ts);
    if (name && isTopLevelExport(node, ts) && (oldNames.has(name.text) || newNames.has(name.text))) {
      const symbol = resolvedSymbol(checker.getSymbolAtLocation(name), checker, ts);
      if (symbol) {
        const bucket = oldNames.has(name.text) ? "old" : "new";
        (bucket === "old" ? oldSymbols : newSymbols).add(symbol);
        declarations[bucket].push({
          file: sourceLabel(sourceFile, projectRoot),
          line: lineOf(sourceFile, name.getStart(sourceFile)),
          name: name.text,
        });
      }
    }
    ts.forEachChild(node, visitDeclaration);
  };
  visitDeclaration(sourceFile);
}

const occurrences = [];
for (const sourcePath of coveredSources) {
  const sourceFile = program.getSourceFile(sourcePath);
  if (!sourceFile) continue;
  const visitOccurrence = (node) => {
    if (ts.isIdentifier(node) && (oldNames.has(node.text) || newNames.has(node.text))) {
      const original = checker.getSymbolAtLocation(node);
      const symbol = resolvedSymbol(original, checker, ts);
      let classification;
      if (symbol && oldSymbols.has(symbol)) {
        classification = "old_concept_symbol";
      } else if (symbol && newSymbols.has(symbol)) {
        classification = "new_concept_symbol";
      } else if (isPropertyName(node, ts)) {
        classification = "property_key";
      } else if (original && (original.flags & ts.SymbolFlags.Alias)) {
        classification = "import_alias";
      } else if (isLocalDeclaration(symbol, ts)) {
        classification = "shadowed_local";
      } else if (isTopLevelUnexportedDeclaration(symbol, ts)) {
        classification = "internal_or_unexported_identifier";
      } else {
        classification = "unresolved_identifier";
      }
      occurrences.push({
        file: sourceLabel(sourceFile, projectRoot),
        line: lineOf(sourceFile, node.getStart(sourceFile)),
        name: node.text,
        classification,
      });
    }
    ts.forEachChild(node, visitOccurrence);
  };
  visitOccurrence(sourceFile);
}

const parseDiagnostics = [];
const semanticDiagnostics = [];
for (const sourcePath of coveredSources) {
  const sourceFile = program.getSourceFile(sourcePath);
  if (!sourceFile) continue;
  parseDiagnostics.push(...sourceFile.parseDiagnostics.map((diagnostic) => diagnosticRecord(diagnostic, "parse")));
  semanticDiagnostics.push(...program.getSemanticDiagnostics(sourceFile).map((diagnostic) => diagnosticRecord(diagnostic, "semantic")));
}
const candidateLines = new Set(occurrences.map((item) => `${item.file}:${item.line}`));
const resolutionDiagnostics = [
  ...configDiagnostics,
  ...parseDiagnostics,
  ...semanticDiagnostics.filter((diagnostic) => (
    diagnostic.category === "Error"
      && (
        candidateLines.has(`${diagnostic.file}:${diagnostic.line}`)
        || [2304, 2305, 2307, 2552].includes(diagnostic.code)
      )
  )),
];
const diagnostics = ts.getPreEmitDiagnostics(program).slice(0, 20).map((diagnostic) => diagnosticRecord(diagnostic, "pre_emit"));
if (language === "javascript" && parseDiagnostics.length > 0) {
  writeJson(output, {
    status: "syntax-error",
    language,
    config: sourceLabel({ fileName: configPath }, projectRoot),
    diagnostics: parseDiagnostics,
    unresolved_files: uncoveredFiles,
  });
  process.exit(2);
}
const textualBoundaries = [];
for (const sourcePath of coveredSources) {
  const sourceFile = program.getSourceFile(sourcePath);
  if (!sourceFile) continue;
  sourceFile.text.split(/\r?\n/).forEach((line, index) => {
    if (![...oldNames, ...newNames].some((term) => line.includes(term))) return;
    if (/\/\/|\/\*|["'`]/.test(line)) {
      textualBoundaries.push({ file: sourceLabel(sourceFile, projectRoot), line: index + 1, classification: "string_or_comment_boundary" });
    }
  });
}
writeJson(output, {
  status: language === "javascript" && (uncoveredFiles.length || resolutionDiagnostics.length) ? "partial" : "resolved",
  language,
  typescript_version: ts.version,
  config: sourceLabel({ fileName: configPath }, projectRoot),
  source_files: coveredSources.map((sourcePath) => path.relative(projectRoot, sourcePath).split(path.sep).join("/")),
  uncovered_files: uncoveredFiles,
  semantic_evidence: language === "javascript" ? {
    checked_javascript: true,
    jsdoc: { declarations: coveredSources.reduce((count, source) => count + (program.getSourceFile(source)?.text.match(/\/\*\*/g)?.length ?? 0), 0) },
    compiler_inferred: { resolved_identifiers: occurrences.length },
  } : undefined,
  declarations,
  occurrences,
  textual_boundaries: textualBoundaries,
  config_diagnostics: configDiagnostics,
  resolution_diagnostics: resolutionDiagnostics,
  diagnostics,
});
