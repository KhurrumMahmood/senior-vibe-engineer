#!/usr/bin/env node
/**
 * Staged by generate_typescript_state_guard.mjs. Uses the host project's
 * TypeScript Compiler API; it never imports toolkit code.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const RULE = "no-stringly-state";
const STATE_FIELDS = new Set(["state", "status", "phase"]);
const NOQA = new RegExp("//\\s*noqa:\\s*" + RULE + ":\\s*\\S");

function failure(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = {
    projectRoot: process.cwd(),
    tsconfig: null,
    stdin: false,
    filename: "<stdin>",
    files: [],
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--stdin") {
      options.stdin = true;
    } else if (arg === "--project-root" || arg === "--tsconfig") {
      const value = argv[++index];
      if (!value) failure("missing value for " + arg);
      options[arg === "--project-root" ? "projectRoot" : "tsconfig"] = value;
    } else if (arg === "--filename") {
      const value = argv[++index];
      if (!value) failure("missing value for --filename");
      options.filename = value;
    } else if (arg.startsWith("--filename=")) {
      options.filename = arg.slice("--filename=".length);
    } else if (arg.startsWith("--")) {
      failure("unknown option: " + arg);
    } else {
      options.files.push(arg);
    }
  }
  if (options.stdin && options.files.length) failure("--stdin cannot be combined with file paths");
  if (!options.stdin && !options.files.length) {
    failure("usage: no_stringly_state.mjs [--project-root <path>] [--tsconfig <path>] <file.ts|file.tsx>...");
  }
  options.projectRoot = path.resolve(options.projectRoot);
  options.tsconfig = path.resolve(options.tsconfig || path.join(options.projectRoot, "tsconfig.json"));
  return options;
}

function loadCompiler(projectRoot, tsconfigPath) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) failure("project-local TypeScript requires " + packageJson);
  if (!fs.existsSync(tsconfigPath)) failure("project-local TypeScript requires tsconfig at " + tsconfigPath);
  let ts;
  try {
    ts = createRequire(packageJson)("typescript");
  } catch (error) {
    failure("project-local TypeScript package is unavailable from " + packageJson + ": " + error.message);
  }
  if (typeof ts.createProgram !== "function") failure("project-local TypeScript package lacks the required Compiler API");
  const read = ts.readConfigFile(tsconfigPath, ts.sys.readFile);
  if (read.error) failure("cannot read tsconfig " + tsconfigPath);
  const parsed = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(tsconfigPath));
  const configError = parsed.errors.find((item) => item.category === ts.DiagnosticCategory.Error);
  if (configError) {
    failure("cannot parse tsconfig " + tsconfigPath + ": " + ts.flattenDiagnosticMessageText(configError.messageText, " "));
  }
  return { ts, options: { ...parsed.options, jsx: parsed.options.jsx ?? ts.JsxEmit.Preserve } };
}

function literal(node, ts) {
  return ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) ? node.text : null;
}

function stateProperty(node, ts) {
  return ts.isPropertyAccessExpression(node) && STATE_FIELDS.has(node.name.text) ? node : null;
}

function closedState(type, ts) {
  if (type.flags & ts.TypeFlags.StringLiteral) return true;
  const symbol = type.getSymbol?.();
  if (symbol && (symbol.flags & ts.SymbolFlags.Enum)) return true;
  if (type.isUnion?.() && type.types.length > 0) {
    return type.types.every((member) => {
      if (member.flags & ts.TypeFlags.StringLiteral) return true;
      const memberSymbol = member.getSymbol?.();
      return Boolean(memberSymbol && (memberSymbol.flags & ts.SymbolFlags.EnumMember));
    });
  }
  return false;
}

function hasNoqa(sourceFile, node) {
  const line = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line;
  return NOQA.test(sourceFile.text.split(/\r?\n/)[line] ?? "");
}

function collect(sourceFile, checker, ts, semantic) {
  const hits = [];
  const visit = (node) => {
    if (ts.isBinaryExpression(node)) {
      const leftLiteral = literal(node.left, ts);
      const rightLiteral = literal(node.right, ts);
      const property = stateProperty(node.left, ts) || stateProperty(node.right, ts);
      const comparison = [
        ts.SyntaxKind.EqualsEqualsToken,
        ts.SyntaxKind.EqualsEqualsEqualsToken,
        ts.SyntaxKind.ExclamationEqualsToken,
        ts.SyntaxKind.ExclamationEqualsEqualsToken,
      ].includes(node.operatorToken.kind);
      const assignment = node.operatorToken.kind === ts.SyntaxKind.EqualsToken;
      if (property && (leftLiteral ?? rightLiteral) !== null && (comparison || assignment)) {
        const typed = semantic ? closedState(checker.getTypeAtLocation(property), ts) : true;
        if (typed && !hasNoqa(sourceFile, node)) {
          const position = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
          hits.push({
            line: position.line + 1,
            column: position.character + 1,
            operation: assignment ? "assignment" : "comparison",
          });
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return hits;
}

function checkFiles(options) {
  const compiler = loadCompiler(options.projectRoot, options.tsconfig);
  const { ts, options: compilerOptions } = compiler;
  if (options.stdin) {
    const source = fs.readFileSync(0, "utf8");
    const kind = options.filename.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
    const sourceFile = ts.createSourceFile(options.filename, source, ts.ScriptTarget.Latest, true, kind);
    if (sourceFile.parseDiagnostics.length) failure("syntax error in " + options.filename);
    return [{ filename: options.filename, hits: collect(sourceFile, null, ts, false) }];
  }
  const files = options.files.map((file) => path.resolve(file));
  for (const file of files) {
    if (!/\.(?:ts|tsx)$/.test(file)) failure("unsupported file suffix: " + file);
    if (!fs.existsSync(file)) failure("cannot read " + file);
  }
  const program = ts.createProgram({ rootNames: [...new Set(files)], options: compilerOptions });
  const checker = program.getTypeChecker();
  return files.map((file) => {
    const sourceFile = program.getSourceFile(file);
    if (!sourceFile) failure("TypeScript did not load " + file);
    if (sourceFile.parseDiagnostics.length) failure("syntax error in " + file);
    return { filename: file, hits: collect(sourceFile, checker, ts, true) };
  });
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const results = checkFiles(options);
  let total = 0;
  for (const result of results) {
    for (const hit of result.hits) {
      total += 1;
      process.stdout.write(
        result.filename + ":" + hit.line + ":" + hit.column + ": " + RULE
        + ": bare state " + hit.operation
        + " must use an exported value object; use // noqa: " + RULE
        + ": <vendor-boundary reason> only at a vendor boundary\n",
      );
    }
  }
  return total ? 1 : 0;
}

try {
  process.exitCode = main();
} catch (error) {
  process.stderr.write("error: " + error.message + "\n");
  process.exitCode = 2;
}
