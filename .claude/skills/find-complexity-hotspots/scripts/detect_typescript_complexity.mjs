#!/usr/bin/env node
/**
 * Extract syntax-only per-function JavaScript/TypeScript complexity facts.
 *
 * This launcher is family-local. It resolves the target host's pinned
 * `typescript` package and uses `createSourceFile`; it never reads a tsconfig,
 * resolves imports, constructs a Program/TypeChecker, or infers framework or
 * receiver identity.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  if (argv.length !== 4 || argv[0] !== "--file" || argv[2] !== "--project-root") {
    fail("usage: detect_typescript_complexity.mjs --file <js-or-ts> --project-root <path>");
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

function span(sourceFile, node) {
  const lineno = lineOf(sourceFile, node.getStart(sourceFile));
  const endLineno = lineOf(sourceFile, node.getEnd());
  return { lineno, end_lineno: endLineno, loc: Math.max(1, endLineno - lineno + 1) };
}

function unwrapInitializer(node, ts) {
  let current = node;
  while (
    current
    && (ts.isParenthesizedExpression(current)
      || ts.isAsExpression(current)
      || ts.isTypeAssertionExpression(current)
      || ts.isSatisfiesExpression?.(current))
  ) {
    current = current.expression;
  }
  return current;
}

function isFunctionBoundary(node, ts) {
  return ts.isFunctionLike(node);
}

function branchScore(body, ts) {
  let score = 0;

  function visit(node) {
    if (node !== body && isFunctionBoundary(node, ts)) return;
    if (
      ts.isIfStatement(node)
      || ts.isForStatement(node)
      || ts.isForInStatement(node)
      || ts.isForOfStatement(node)
      || ts.isWhileStatement(node)
      || ts.isDoStatement(node)
      || ts.isTryStatement(node)
      || ts.isCatchClause(node)
      || ts.isWithStatement(node)
      || ts.isSwitchStatement(node)
      || ts.isConditionalExpression(node)
    ) {
      score += 1;
    } else if (
      ts.isBinaryExpression(node)
      && (node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
        || node.operatorToken.kind === ts.SyntaxKind.BarBarToken)
    ) {
      score += 1;
    }
    ts.forEachChild(node, visit);
  }

  visit(body);
  return score;
}

function nameText(name, ts) {
  return ts.isIdentifier(name) ? name.text : null;
}

function complexityRecord(sourceFile, node, body, name, kind, containers, ts) {
  const symbol = [...containers, name].join(".");
  return {
    name,
    symbol,
    kind,
    branch_score: branchScore(body, ts),
    ...span(sourceFile, node),
  };
}

function functions(sourceFile, ts) {
  const records = [];

  function visit(node, containers) {
    let nextContainers = containers;
    if (ts.isClassDeclaration(node) && node.name) {
      nextContainers = [...containers, node.name.text];
    }

    if (ts.isFunctionDeclaration(node) && node.name && node.body) {
      records.push(complexityRecord(
        sourceFile,
        node,
        node.body,
        node.name.text,
        node.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.AsyncKeyword)
          ? "async_function" : "function",
        containers,
        ts,
      ));
    } else if (ts.isMethodDeclaration(node) && node.body) {
      const name = nameText(node.name, ts);
      if (name) {
        records.push(complexityRecord(sourceFile, node, node.body, name, "method", containers, ts));
      }
    } else if (ts.isVariableDeclaration(node) && node.initializer) {
      const name = nameText(node.name, ts);
      const initializer = unwrapInitializer(node.initializer, ts);
      if (name && ts.isArrowFunction(initializer) && ts.isBlock(initializer.body)) {
        records.push(complexityRecord(
          sourceFile,
          initializer,
          initializer.body,
          name,
          initializer.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.AsyncKeyword)
            ? "async_arrow" : "arrow",
          containers,
          ts,
        ));
      }
    }

    ts.forEachChild(node, (child) => visit(child, nextContainers));
  }

  visit(sourceFile, []);
  return records;
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
  process.stdout.write(`${JSON.stringify(functions(sourceFile, ts))}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`[detect_typescript_complexity] ${error.message}\n`);
  process.exitCode = 2;
}
