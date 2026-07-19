#!/usr/bin/env node
/**
 * Detect closed TypeScript state operations with the host's Compiler API.
 *
 * This is intentionally family-local. It requires a host-owned `typescript`
 * dependency and tsconfig because receiver identity is a semantic fact, not a
 * regex convention. Output is JSONL so `/extract-enum` can consume only the
 * first-party records and retain explicit exclusions as boundary evidence.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const STATE_FIELDS = new Set(["state", "status", "phase"]);
const SKIP_DIRS = new Set([
  ".git", "node_modules", "dist", "build", "coverage", ".test-dist",
]);

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!flag?.startsWith("--") || value === undefined) {
      fail("usage: detect_typescript_state.mjs --target <path> --project-root <path> --tsconfig <path> --output <jsonl>");
    }
    options[flag.slice(2)] = value;
  }
  for (const key of ["target", "project-root", "tsconfig", "output"]) {
    if (!options[key]) fail(`missing required --${key}`);
  }
  return options;
}

function loadTypeScript(projectRoot, tsconfigPath) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) {
    fail(`project-local TypeScript requires ${packageJson}`);
  }
  if (!fs.existsSync(tsconfigPath)) {
    fail(`project-local TypeScript requires tsconfig at ${tsconfigPath}`);
  }
  let ts;
  try {
    ts = createRequire(packageJson)("typescript");
  } catch (error) {
    fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`);
  }
  const read = ts.readConfigFile(tsconfigPath, ts.sys.readFile);
  if (read.error) {
    fail(`cannot read tsconfig ${tsconfigPath}: ${ts.flattenDiagnosticMessageText(read.error.messageText, " ")}`);
  }
  const parsed = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(tsconfigPath));
  const configError = parsed.errors.find((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error);
  if (configError) {
    fail(`cannot parse tsconfig ${tsconfigPath}: ${ts.flattenDiagnosticMessageText(configError.messageText, " ")}`);
  }
  return { ts, options: parsed.options };
}

function walkTypeScriptFiles(target) {
  const files = [];
  const visit = (current) => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const candidate = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(entry.name)) visit(candidate);
      } else if (/\.(?:ts|tsx)$/.test(entry.name) && !/\.d\.ts$/.test(entry.name)) {
        files.push(candidate);
      }
    }
  };
  visit(target);
  return files;
}

function relative(projectRoot, file) {
  return path.relative(projectRoot, file).split(path.sep).join("/");
}

function isTestOrFixture(file) {
  return /(^|\/)(?:tests?|__tests__|fixtures?)(\/|$)|\.(?:test|spec)\.(?:ts|tsx)$/.test(file);
}

function sourceLine(sourceFile, node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
}

function evidence(sourceFile, node) {
  const line = sourceFile.text.split(/\r?\n/)[sourceLine(sourceFile, node) - 1] ?? "";
  return line.trim().slice(0, 240);
}

function stringLiteral(node, ts) {
  return ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) ? node.text : null;
}

function stateProperty(node, ts) {
  return ts.isPropertyAccessExpression(node) && STATE_FIELDS.has(node.name.text) ? node : null;
}

function typeKind(type, ts) {
  if (type.flags & ts.TypeFlags.StringLiteral) return "literal_union";
  const symbol = type.getSymbol?.();
  if (symbol && (symbol.flags & ts.SymbolFlags.Enum)) return "enum";
  if (type.isUnion?.() && type.types.length > 0) {
    if (type.types.every((member) => member.flags & ts.TypeFlags.StringLiteral)) return "literal_union";
    if (type.types.every((member) => {
      const memberSymbol = member.getSymbol?.();
      return memberSymbol && (memberSymbol.flags & ts.SymbolFlags.EnumMember);
    })) return "enum";
  }
  return null;
}

function typeName(type) {
  const symbol = type.aliasSymbol || type.getSymbol?.();
  return symbol?.getName?.() ?? null;
}

function isOpenEndedString(type, ts) {
  return Boolean(type.flags & ts.TypeFlags.String) && !(type.flags & ts.TypeFlags.StringLiteral);
}

function isVendorBoundary(sourceFile) {
  return /(?:^|\/)vendor(?:\.|\/|$)/i.test(sourceFile.fileName) || /\bVendor[A-Za-z]/.test(sourceFile.text);
}

function recordBase(projectRoot, sourceFile, node) {
  return {
    file: relative(projectRoot, sourceFile.fileName),
    line: sourceLine(sourceFile, node),
    evidence: evidence(sourceFile, node),
  };
}

function emitStateOperation(records, projectRoot, sourceFile, node, property, literal, operation, checker, ts) {
  const stateType = checker.getTypeAtLocation(property);
  const base = {
    ...recordBase(projectRoot, sourceFile, node),
    field: property.name.text,
    operation,
    literal,
    carrier_type: typeName(stateType),
  };
  if (isTestOrFixture(base.file)) {
    records.push({ ...base, classification: "excluded_test_or_fixture" });
    return;
  }
  if (isVendorBoundary(sourceFile)) {
    records.push({ ...base, classification: "vendor_wire_boundary" });
    return;
  }
  const kind = typeKind(stateType, ts);
  if (kind) {
    records.push({
      ...base,
      classification: "first_party_state_operation",
      state_type_kind: kind,
    });
    return;
  }
  records.push({ ...base, classification: "open_ended_string" });
}

function isStringLiteralUnion(node, ts) {
  return ts.isUnionTypeNode(node) && node.types.length > 0 && node.types.every((member) => {
    return ts.isLiteralTypeNode(member) && stringLiteral(member.literal, ts) !== null;
  });
}

function detect(projectRoot, target, tsconfigPath) {
  const { ts, options } = loadTypeScript(projectRoot, tsconfigPath);
  const files = walkTypeScriptFiles(target);
  const program = ts.createProgram({ rootNames: files, options });
  const checker = program.getTypeChecker();
  const records = [];

  for (const sourceFile of program.getSourceFiles()) {
    if (!files.includes(sourceFile.fileName)) continue;
    const visit = (node) => {
      if (ts.isTypeAliasDeclaration(node) && /(?:state|status|phase)$/i.test(node.name.text) && isStringLiteralUnion(node.type, ts)) {
        records.push({
          ...recordBase(projectRoot, sourceFile, node),
          classification: "typed_state_authority",
          authority_kind: "literal_union",
          carrier_type: node.name.text,
          values: node.type.types.map((member) => stringLiteral(member.literal, ts)),
        });
      }
      if (ts.isEnumDeclaration(node) && /(?:state|status|phase)$/i.test(node.name.text)) {
        records.push({
          ...recordBase(projectRoot, sourceFile, node),
          classification: "typed_state_authority",
          authority_kind: "string_enum",
          carrier_type: node.name.text,
        });
      }
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
        const initializerText = node.initializer?.getText(sourceFile) ?? "";
        if (/(?:state|status|phase)$/i.test(node.name.text) && /\bas const\b/.test(initializerText)) {
          records.push({
            ...recordBase(projectRoot, sourceFile, node),
            classification: "typed_state_authority",
            authority_kind: "runtime_value_object",
            carrier_type: node.name.text,
          });
        } else if (/status/i.test(node.name.text) && stringLiteral(node.initializer, ts) !== null) {
          records.push({
            ...recordBase(projectRoot, sourceFile, node),
            classification: "unrelated_status_text",
            literal: stringLiteral(node.initializer, ts),
          });
        }
      }
      if (ts.isBinaryExpression(node)) {
        const operator = node.operatorToken.kind;
        const isComparison = [
          ts.SyntaxKind.EqualsEqualsToken,
          ts.SyntaxKind.EqualsEqualsEqualsToken,
          ts.SyntaxKind.ExclamationEqualsToken,
          ts.SyntaxKind.ExclamationEqualsEqualsToken,
        ].includes(operator);
        const leftLiteral = stringLiteral(node.left, ts);
        const rightLiteral = stringLiteral(node.right, ts);
        const property = stateProperty(node.left, ts) || stateProperty(node.right, ts);
        if (isComparison && property && (leftLiteral ?? rightLiteral) !== null) {
          emitStateOperation(records, projectRoot, sourceFile, node, property, leftLiteral ?? rightLiteral, "comparison", checker, ts);
        } else if (isComparison && (leftLiteral ?? rightLiteral) !== null) {
          const expression = leftLiteral === null ? node.left : node.right;
          if (isOpenEndedString(checker.getTypeAtLocation(expression), ts)) {
            records.push({
              ...recordBase(projectRoot, sourceFile, node),
              classification: "open_ended_string",
              literal: leftLiteral ?? rightLiteral,
            });
          }
        }
      }
      if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
        const property = stateProperty(node.left, ts);
        const literal = stringLiteral(node.right, ts);
        if (property && literal !== null) {
          emitStateOperation(records, projectRoot, sourceFile, node, property, literal, "assignment", checker, ts);
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return records;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectRoot = path.resolve(args["project-root"]);
  const target = path.resolve(args.target);
  const tsconfig = path.resolve(args.tsconfig);
  if (!fs.existsSync(target) || !fs.statSync(target).isDirectory()) fail(`target directory not found: ${target}`);
  const records = detect(projectRoot, target, tsconfig);
  fs.mkdirSync(path.dirname(path.resolve(args.output)), { recursive: true });
  fs.writeFileSync(path.resolve(args.output), `${records.map((record) => JSON.stringify(record)).join("\n")}${records.length ? "\n" : ""}`);
  const actionable = records.filter((record) => record.classification === "first_party_state_operation").length;
  process.stderr.write(`[detect_typescript_state] ${records.length} records; ${actionable} first-party state operations\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`error: ${error.message}\n`);
  process.exitCode = 2;
}
