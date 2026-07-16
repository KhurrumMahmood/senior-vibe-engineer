"use strict";

const fs = require("fs");
const path = require("path");

const typescriptRoot = process.argv[2];
const corpusRoot = path.resolve(process.argv[3]);
if (!typescriptRoot || !corpusRoot) {
  console.error("usage: node typescript_compiler_probe.cjs <typescript-package-root> <corpus-root>");
  process.exit(2);
}
const ts = require(typescriptRoot);
const configPath = path.join(corpusRoot, "tsconfig.json");
const config = ts.readConfigFile(configPath, ts.sys.readFile);
if (config.error) {
  console.error(ts.flattenDiagnosticMessageText(config.error.messageText, "\n"));
  process.exit(1);
}
const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, corpusRoot);
const program = ts.createProgram(parsed.fileNames, parsed.options);
const checker = program.getTypeChecker();
const diagnostics = ts.getPreEmitDiagnostics(program);
if (diagnostics.length) {
  console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCanonicalFileName: (name) => name,
    getCurrentDirectory: () => corpusRoot,
    getNewLine: () => "\n",
  }));
  process.exit(1);
}

const facts = {
  definitions: new Set(),
  imports: new Set(),
  calls: new Set(),
  writes: new Set(),
  references: new Set(),
};

function declarationName(node) {
  return node.name && ts.isIdentifier(node.name) ? node.name.text : null;
}

for (const sourceFile of program.getSourceFiles()) {
  if (!sourceFile.fileName.startsWith(corpusRoot) || sourceFile.isDeclarationFile) continue;
  function visit(node) {
    if (
      ts.isFunctionDeclaration(node) ||
      ts.isEnumDeclaration(node) ||
      ts.isInterfaceDeclaration(node) ||
      ts.isVariableDeclaration(node)
    ) {
      const name = declarationName(node);
      if (name) facts.definitions.add(name);
    }
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      facts.imports.add(node.moduleSpecifier.text);
    }
    if (ts.isCallExpression(node)) {
      facts.calls.add(node.expression.getText(sourceFile));
    }
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment &&
      node.operatorToken.kind <= ts.SyntaxKind.LastAssignment
    ) {
      facts.writes.add(node.left.getText(sourceFile));
    }
    if (ts.isIdentifier(node)) {
      const parent = node.parent;
      const isDeclarationName = parent && parent.name === node && (
        ts.isFunctionDeclaration(parent) ||
        ts.isEnumDeclaration(parent) ||
        ts.isInterfaceDeclaration(parent) ||
        ts.isVariableDeclaration(parent) ||
        ts.isParameter(parent)
      );
      if (!isDeclarationName) {
        const symbol = checker.getSymbolAtLocation(node);
        if (symbol) facts.references.add(symbol.getName());
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
}

const output = Object.fromEntries(
  Object.entries(facts).map(([key, values]) => [key, [...values].sort()])
);
console.log(JSON.stringify(output));
