#!/usr/bin/env node
/**
 * Extract TypeScript/TSX top-level symbols for find-omnibus.
 *
 * This launcher is intentionally family-local. It needs only syntax spans, so
 * it resolves the host's pinned `typescript` package and calls createSourceFile
 * without reading tsconfig, resolving imports, or constructing a type checker.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  if (argv.length !== 4 || argv[0] !== "--file" || argv[2] !== "--project-root") {
    fail("usage: detect_typescript_symbols.mjs --file <ts-or-tsx> --project-root <path>");
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

function symbols(sourceFile, ts) {
  const records = [];
  for (const statement of sourceFile.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.name) {
      records.push({
        name: statement.name.text,
        cluster_name: statement.name.text,
        kind: statement.modifiers?.some((m) => m.kind === ts.SyntaxKind.AsyncKeyword)
          ? "async_function" : "function",
        ...span(sourceFile, statement),
      });
    } else if (ts.isClassDeclaration(statement) && statement.name) {
      records.push({
        name: statement.name.text,
        cluster_name: statement.name.text,
        kind: "class",
        ...span(sourceFile, statement),
      });
    } else if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name) || !declaration.initializer) continue;
        const initializer = unwrapInitializer(declaration.initializer, ts);
        if (!ts.isArrowFunction(initializer) && !ts.isFunctionExpression(initializer)) continue;
        records.push({
          name: declaration.name.text,
          cluster_name: declaration.name.text,
          kind: initializer.modifiers?.some((m) => m.kind === ts.SyntaxKind.AsyncKeyword)
            ? "async_function" : "function",
          ...span(sourceFile, statement),
        });
      }
    }
  }
  return records;
}

function main() {
  const { file, projectRoot } = parseArgs(process.argv.slice(2));
  if (!/\.(?:ts|tsx)$/i.test(file)) fail(`TypeScript source must end in .ts or .tsx: ${file}`);
  if (!fs.existsSync(file)) fail(`TypeScript source does not exist: ${file}`);
  const ts = loadTypeScript(projectRoot);
  const text = fs.readFileSync(file, "utf8");
  const scriptKind = file.toLowerCase().endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, scriptKind);
  if (sourceFile.parseDiagnostics.length > 0) {
    const diagnostic = sourceFile.parseDiagnostics[0];
    const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
    fail(`syntax error in ${file}:${lineOf(sourceFile, diagnostic.start ?? 0)}: ${message}`);
  }
  process.stdout.write(`${JSON.stringify(symbols(sourceFile, ts))}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`[detect_typescript_symbols] ${error.message}\n`);
  process.exitCode = 2;
}
