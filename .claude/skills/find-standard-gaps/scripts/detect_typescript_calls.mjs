#!/usr/bin/env node
/**
 * Extract direct TypeScript/TSX call facts for find-standard-gaps.
 *
 * The launcher resolves only the host project's pinned `typescript` package
 * and creates a syntax tree. It never reads a tsconfig, builds a Program,
 * resolves aliases/types/receivers, or infers framework behavior.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  if (argv.length === 3 && argv[0] === "--check" && argv[1] === "--project-root") {
    return { check: true, projectRoot: path.resolve(argv[2]) };
  }
  if (argv.length === 4 && argv[0] === "--file" && argv[2] === "--project-root") {
    return { check: false, file: path.resolve(argv[1]), projectRoot: path.resolve(argv[3]) };
  }
  fail("usage: detect_typescript_calls.mjs --check --project-root <path> | --file <ts-or-tsx> --project-root <path>");
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

function sourceLine(sourceFile, position) {
  const line = lineOf(sourceFile, position) - 1;
  return sourceFile.text.split(/\r?\n/)[line]?.trim() ?? "";
}

function dotted(node, ts) {
  if (ts.isIdentifier(node)) return node.text;
  if (ts.isPropertyAccessExpression(node)) {
    const base = dotted(node.expression, ts);
    return base ? `${base}.${node.name.text}` : "";
  }
  if (
    ts.isParenthesizedExpression(node)
    || ts.isAsExpression(node)
    || ts.isTypeAssertionExpression(node)
    || ts.isNonNullExpression(node)
    || ts.isSatisfiesExpression?.(node)
  ) {
    return dotted(node.expression, ts);
  }
  return "";
}

function calls(sourceFile, ts) {
  const records = [];

  function visit(node, inTry) {
    if (ts.isCallExpression(node)) {
      records.push({
        name: dotted(node.expression, ts),
        line: lineOf(sourceFile, node.getStart(sourceFile)),
        text: sourceLine(sourceFile, node.getStart(sourceFile)),
        in_try: inTry,
      });
    }

    // A lexical outer try does not establish runtime protection for calls in a
    // nested function/callback body. Keep this conservative syntax boundary.
    if (node !== sourceFile && ts.isFunctionLike(node)) {
      ts.forEachChild(node, (child) => visit(child, false));
      return;
    }
    if (ts.isTryStatement(node)) {
      visit(node.tryBlock, true);
      if (node.catchClause) visit(node.catchClause, inTry);
      if (node.finallyBlock) visit(node.finallyBlock, inTry);
      return;
    }
    ts.forEachChild(node, (child) => visit(child, inTry));
  }

  visit(sourceFile, false);
  return records;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const ts = loadTypeScript(args.projectRoot);
  if (args.check) {
    process.stdout.write('{"ok":true}\n');
    return;
  }
  if (!/\.(?:ts|tsx)$/i.test(args.file)) {
    fail(`TypeScript source must end in .ts or .tsx: ${args.file}`);
  }
  if (!fs.existsSync(args.file)) fail(`TypeScript source does not exist: ${args.file}`);
  const text = fs.readFileSync(args.file, "utf8");
  const scriptKind = args.file.toLowerCase().endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(args.file, text, ts.ScriptTarget.Latest, true, scriptKind);
  if (sourceFile.parseDiagnostics.length > 0) {
    const diagnostic = sourceFile.parseDiagnostics[0];
    const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
    fail(`syntax error in ${args.file}:${lineOf(sourceFile, diagnostic.start ?? 0)}: ${message}`);
  }
  process.stdout.write(`${JSON.stringify(calls(sourceFile, ts))}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`[detect_typescript_calls] ${error.message}\n`);
  process.exitCode = 2;
}
