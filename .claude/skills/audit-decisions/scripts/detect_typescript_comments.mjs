#!/usr/bin/env node
/**
 * Discover real JavaScript/TypeScript comments containing decision references.
 *
 * This launcher deliberately uses the host's pinned TypeScript Compiler API.
 * A hand lexer cannot reliably distinguish code trivia from JSX text, regexes,
 * template text, and the ambiguous generic/JSX boundary.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const REFERENCE = /\bdecision:(\d{4})\b/g;

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  if (argv.length !== 4 || argv[0] !== "--file" || argv[2] !== "--project-root") {
    fail("usage: detect_typescript_comments.mjs --file <js-or-ts> --project-root <path>");
  }
  return { file: path.resolve(argv[1]), projectRoot: path.resolve(argv[3]) };
}

function loadTypeScript(projectRoot) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) {
    fail(`project-local TypeScript requires ${packageJson}`);
  }
  try {
    const ts = createRequire(packageJson)("typescript");
    if (typeof ts.createSourceFile !== "function") {
      fail("project-local TypeScript package lacks createSourceFile");
    }
    return ts;
  } catch (error) {
    fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`);
  }
}

function lineOf(sourceFile, position) {
  return sourceFile.getLineAndCharacterOfPosition(position).line + 1;
}

function isLiteralText(node, ts) {
  return ts.isStringLiteral(node)
    || ts.isNoSubstitutionTemplateLiteral(node)
    || ts.isRegularExpressionLiteral(node)
    || ts.isJsxText(node)
    || ts.isTemplateHead(node)
    || ts.isTemplateMiddle(node)
    || ts.isTemplateTail(node);
}

function literalRanges(sourceFile, ts) {
  const ranges = [];

  function visit(node) {
    if (isLiteralText(node, ts)) {
      ranges.push({ start: node.getStart(sourceFile), end: node.getEnd() });
    }
    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  ranges.sort((left, right) => left.start - right.start || right.end - left.end);
  return ranges;
}

function references(sourceFile, ts) {
  const text = sourceFile.text;
  const excluded = literalRanges(sourceFile, ts);
  const found = [];

  for (let position = 0, rangeIndex = 0; position < text.length; position += 1) {
    while (rangeIndex < excluded.length && excluded[rangeIndex].end <= position) {
      rangeIndex += 1;
    }
    if (rangeIndex < excluded.length && excluded[rangeIndex].start <= position) {
      position = excluded[rangeIndex].end - 1;
      continue;
    }
    const line = text.startsWith("//", position);
    const block = text.startsWith("/*", position);
    if (!line && !block) {
      continue;
    }
    const end = line
      ? (text.indexOf("\n", position) < 0 ? text.length : text.indexOf("\n", position))
      : text.indexOf("*/", position + 2) + 2;
    const comment = text.slice(position, end);
    const form = block && comment.startsWith("/**") ? "jsdoc" : (line ? "line" : "block");
    for (const match of comment.matchAll(REFERENCE)) {
      const offset = position + match.index;
      found.push({ offset, line: lineOf(sourceFile, offset), id: match[1], comment_form: form });
    }
    position = end - 1;
  }
  return found;
}

function main() {
  const { file, projectRoot } = parseArgs(process.argv.slice(2));
  if (!/\.(?:js|jsx|mjs|cjs|ts|tsx)$/i.test(file)) fail(`JavaScript/TypeScript source has an unsupported suffix: ${file}`);
  if (!fs.existsSync(file)) fail(`source does not exist: ${file}`);
  const ts = loadTypeScript(projectRoot);
  const text = fs.readFileSync(file, "utf8");
  const lower = file.toLowerCase();
  const scriptKind = lower.endsWith(".tsx")
    ? ts.ScriptKind.TSX
    : lower.endsWith(".jsx")
      ? ts.ScriptKind.JSX
      : /\.(?:js|mjs|cjs)$/.test(lower)
        ? ts.ScriptKind.JS
        : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, scriptKind);
  if (sourceFile.parseDiagnostics.length > 0) {
    const diagnostic = sourceFile.parseDiagnostics[0];
    const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
    fail(`syntax error in ${file}:${lineOf(sourceFile, diagnostic.start ?? 0)}: ${message}`);
  }
  process.stdout.write(`${JSON.stringify(references(sourceFile, ts))}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`[detect_typescript_comments] ${error.message}\n`);
  process.exitCode = 2;
}
