#!/usr/bin/env node
/** Staged checked-JavaScript closed-state guard; no toolkit imports at runtime. */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const RULE = "no-stringly-state";
const SUFFIXES = new Set([".js", ".jsx", ".mjs", ".cjs"]);
const FIELDS = new Set(["state", "status", "phase"]);
const VENDOR = /^Vendor[A-Za-z0-9]*(?:Payload|Request|Response|Event|Message|Wire)$/;
const NOQA = new RegExp(`//\\s*noqa:\\s*${RULE}:\\s*\\S`);

function fail(message) { throw new Error(message); }

function parse(argv) {
  const options = { root: process.cwd(), config: null, fixture: false, files: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--fixture") options.fixture = true;
    else if (arg === "--project-root" || arg === "--config") {
      const value = argv[++index];
      if (!value) fail(`missing value for ${arg}`);
      options[arg === "--project-root" ? "root" : "config"] = value;
    } else if (arg.startsWith("--")) fail(`unknown option: ${arg}`);
    else options.files.push(arg);
  }
  if (!options.files.length) fail("usage: no_stringly_state_javascript.mjs [--project-root <path>] [--config <path>] [--fixture] <file.js|file.jsx|file.mjs|file.cjs>...");
  options.root = path.resolve(options.root);
  options.config = path.resolve(options.config || path.join(options.root, "jsconfig.json"));
  return options;
}

function compiler(root, config) {
  const packageJson = path.join(root, "package.json");
  if (!fs.existsSync(packageJson)) fail(`project-local TypeScript requires ${packageJson}`);
  if (!fs.existsSync(config)) fail(`unsupported: checked JavaScript requires an explicit jsconfig/tsconfig at ${config}`);
  if (fs.lstatSync(config).isSymbolicLink()) fail(`checked JavaScript config must not be a symbolic link: ${config}`);
  let ts;
  try { ts = createRequire(packageJson)("typescript"); }
  catch (error) { fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`); }
  const read = ts.readConfigFile(config, ts.sys.readFile);
  if (read.error) fail(`cannot read checked JavaScript config: ${ts.flattenDiagnosticMessageText(read.error.messageText, " ")}`);
  const parsed = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(config));
  const error = parsed.errors.find((item) => item.category === ts.DiagnosticCategory.Error);
  if (error) fail(`cannot parse checked JavaScript config: ${ts.flattenDiagnosticMessageText(error.messageText, " ")}`);
  if (!parsed.options.allowJs || !parsed.options.checkJs) fail("unsupported: checked JavaScript requires compilerOptions.allowJs and compilerOptions.checkJs set to true");
  return { ts, parsed };
}

function unwrap(ts, node) { while (ts.isParenthesizedExpression(node)) node = node.expression; return node; }
function literal(ts, node) { node = unwrap(ts, node); return ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) ? node.text : null; }
function property(ts, node) { node = unwrap(ts, node); return ts.isPropertyAccessExpression(node) && FIELDS.has(node.name.text) ? node : null; }
function typeName(type) { const symbol = type.aliasSymbol || type.getSymbol?.(); return symbol?.getName?.() ?? ""; }
function closed(ts, type) {
  if (type.flags & ts.TypeFlags.StringLiteral) return true;
  return Boolean(type.isUnion?.() && type.types.length && type.types.every((part) => part.flags & ts.TypeFlags.StringLiteral));
}
function jsdoc(ts, type) {
  const symbol = type.aliasSymbol || type.getSymbol?.();
  return Boolean(symbol?.declarations?.some((item) => ts.isJSDocTypedefTag(item) || ts.isJSDocPropertyTag(item) || item.getFullText?.().includes("/**")));
}
function noqa(source, node) {
  const line = source.getLineAndCharacterOfPosition(node.getStart(source)).line;
  return NOQA.test(source.text.split(/\r?\n/)[line] ?? "");
}
function operand(ts, checker, node, aliases) {
  const direct = property(ts, node);
  if (direct) return { state: checker.getTypeAtLocation(direct), receiver: checker.getTypeAtLocation(direct.expression) };
  if (!ts.isIdentifier(node)) return null;
  return aliases.get(checker.getSymbolAtLocation(node)) ?? null;
}
function assigned(ts, node) {
  const direct = literal(ts, node);
  if (direct !== null) return direct;
  node = unwrap(ts, node);
  return ts.isBinaryExpression(node) && [ts.SyntaxKind.EqualsToken, ts.SyntaxKind.QuestionQuestionEqualsToken].includes(node.operatorToken.kind) ? assigned(ts, node.right) : null;
}
function collect(ts, source, checker) {
  const hits = [];
  const aliases = new Map();
  const alias = (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && ts.isVariableDeclarationList(node.parent) && (node.parent.flags & ts.NodeFlags.Const)) {
      const direct = property(ts, node.initializer);
      const symbol = checker.getSymbolAtLocation(node.name);
      if (direct && symbol) aliases.set(symbol, { state: checker.getTypeAtLocation(direct), receiver: checker.getTypeAtLocation(direct.expression) });
    }
    ts.forEachChild(node, alias);
  };
  alias(source);
  const visit = (node) => {
    if (ts.isBinaryExpression(node)) {
      const comparison = [ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(node.operatorToken.kind);
      const assignment = [ts.SyntaxKind.EqualsToken, ts.SyntaxKind.QuestionQuestionEqualsToken].includes(node.operatorToken.kind);
      const target = comparison ? operand(ts, checker, node.left, aliases) || operand(ts, checker, node.right, aliases) : operand(ts, checker, node.left, aliases);
      const value = assignment ? assigned(ts, node.right) : literal(ts, node.left) ?? literal(ts, node.right);
      if (target && value !== null && (comparison || assignment) && closed(ts, target.state) && jsdoc(ts, target.state) && !(VENDOR.test(typeName(target.receiver)) && noqa(source, node))) {
        const position = source.getLineAndCharacterOfPosition(node.getStart(source));
        hits.push({ line: position.line + 1, column: position.character + 1, operation: assignment ? "assignment" : "comparison" });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return hits;
}

function main() {
  const options = parse(process.argv.slice(2));
  const { ts, parsed } = compiler(options.root, options.config);
  const files = options.files.map((file) => path.resolve(file));
  const configured = new Set(parsed.fileNames.map((file) => path.resolve(file)));
  for (const file of files) {
    if (!SUFFIXES.has(path.extname(file).toLowerCase())) fail(`unsupported JavaScript suffix: ${file}`);
    if (!fs.existsSync(file) || fs.lstatSync(file).isSymbolicLink()) fail(`cannot read non-symlink JavaScript source: ${file}`);
    if (!options.fixture && !configured.has(file)) fail(`partial: checked JavaScript config does not cover ${file}`);
  }
  const program = ts.createProgram({ rootNames: options.fixture ? files : parsed.fileNames, options: parsed.options });
  let count = 0;
  for (const file of files) {
    const source = program.getSourceFile(file);
    if (!source || source.parseDiagnostics.length) fail(`syntax error in ${file}`);
    for (const hit of collect(ts, source, program.getTypeChecker())) {
      count += 1;
      process.stdout.write(`${file}:${hit.line}:${hit.column}: ${RULE}: bare state ${hit.operation} must use a named authority\n`);
    }
  }
  return count ? 1 : 0;
}

try { process.exitCode = main(); }
catch (error) { process.stderr.write(`error: ${error.message}\n`); process.exitCode = 2; }
