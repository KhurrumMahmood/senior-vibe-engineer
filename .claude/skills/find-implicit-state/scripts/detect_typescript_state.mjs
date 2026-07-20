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
const VENDOR_BOUNDARY_TYPE = /^Vendor[A-Za-z0-9]*(?:Payload|Request|Response|Event|Message|Wire)$/;
const SKIP_DIRS = new Set([
  ".git", "node_modules", "dist", "build", "coverage", ".test-dist",
]);
const JAVASCRIPT_SUFFIXES = new Set([".js", ".jsx", ".mjs", ".cjs"]);

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
  const language = options.language ?? "typescript";
  if (!["typescript", "javascript"].includes(language)) fail("--language must be typescript or javascript");
  for (const key of ["target", "project-root", "tsconfig", "output"]) {
    if (!options[key]) fail(`missing required --${key}`);
  }
  if (language === "javascript" && !options.manifest) fail("checked JavaScript requires --manifest <json>");
  options.language = language;
  return options;
}

function loadTypeScript(projectRoot, tsconfigPath, language) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) {
    fail(`project-local TypeScript requires ${packageJson}`);
  }
  if (!fs.existsSync(tsconfigPath)) {
    fail(language === "javascript"
      ? `unsupported: checked JavaScript requires an explicit jsconfig/tsconfig at ${tsconfigPath}`
      : `project-local TypeScript requires tsconfig at ${tsconfigPath}`);
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
  if (language === "javascript" && (!parsed.options.allowJs || !parsed.options.checkJs)) {
    fail("unsupported: checked JavaScript requires compilerOptions.allowJs and compilerOptions.checkJs set to true");
  }
  return {
    ts,
    options: parsed.options,
    fileNames: parsed.fileNames.map((file) => path.resolve(file)),
    configPath: tsconfigPath,
  };
}

function walkTypeScriptFiles(target, language) {
  const files = [];
  const visit = (current) => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const candidate = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(entry.name)) visit(candidate);
      } else if (
        (language === "javascript" ? JAVASCRIPT_SUFFIXES.has(path.extname(entry.name).toLowerCase()) : /\.(?:ts|tsx)$/.test(entry.name))
        && !/\.d\.ts$/.test(entry.name)
      ) {
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
  return /(^|\/)(?:tests?|__tests__|fixtures?)(\/|$)|\.(?:test|spec)\.(?:ts|tsx|js|jsx|mjs|cjs)$/.test(file);
}

function sourceLine(sourceFile, node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
}

function evidence(sourceFile, node) {
  const line = sourceFile.text.split(/\r?\n/)[sourceLine(sourceFile, node) - 1] ?? "";
  return line.trim().slice(0, 240);
}

function unwrapParentheses(node, ts) {
  let current = node;
  while (current && ts.isParenthesizedExpression(current)) current = current.expression;
  return current;
}

function stringLiteral(node, ts) {
  const current = unwrapParentheses(node, ts);
  return ts.isStringLiteral(current) || ts.isNoSubstitutionTemplateLiteral(current) ? current.text : null;
}

function stateProperty(node, ts) {
  const current = unwrapParentheses(node, ts);
  return ts.isPropertyAccessExpression(current) && STATE_FIELDS.has(current.name.text) ? current : null;
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

function isVendorBoundary(receiverType) {
  return VENDOR_BOUNDARY_TYPE.test(typeName(receiverType) ?? "");
}

function recordBase(projectRoot, sourceFile, node) {
  return {
    file: relative(projectRoot, sourceFile.fileName),
    line: sourceLine(sourceFile, node),
    evidence: evidence(sourceFile, node),
  };
}

function stateOperand(node, aliases, checker, ts) {
  const property = stateProperty(node, ts);
  if (property) {
    const receiverType = checker.getTypeAtLocation(property.expression);
    const stateType = checker.getTypeAtLocation(property);
    const typeSymbol = stateType.aliasSymbol || stateType.getSymbol?.();
    const jsdocAuthority = Boolean(typeSymbol?.declarations?.some((declaration) => (
      ts.isJSDocTypedefTag(declaration)
      || ts.isJSDocPropertyTag(declaration)
      || declaration.getFullText?.().includes("/**")
    )));
    return {
      field: property.name.text,
      stateType,
      receiverType,
      jsdocAuthority,
    };
  }
  if (!ts.isIdentifier(node)) return null;
  const symbol = checker.getSymbolAtLocation(node);
  return symbol ? aliases.get(symbol) ?? null : null;
}

function emitStateOperation(records, projectRoot, sourceFile, node, operand, literal, operation, ts, language) {
  const base = {
    ...recordBase(projectRoot, sourceFile, node),
    field: operand.field,
    operation,
    literal,
    carrier_type: typeName(operand.stateType),
    receiver_type: typeName(operand.receiverType),
  };
  if (isTestOrFixture(base.file)) {
    records.push({ ...base, classification: "excluded_test_or_fixture" });
    return;
  }
  if (isVendorBoundary(operand.receiverType)) {
    records.push({ ...base, classification: "vendor_wire_boundary" });
    return;
  }
  const kind = typeKind(operand.stateType, ts);
  if (kind && (language !== "javascript" || operand.jsdocAuthority)) {
    records.push({
      ...base,
      classification: "first_party_state_operation",
      state_type_kind: kind,
    });
    return;
  }
  records.push({
    ...base,
    classification: language === "javascript" && kind ? "missing_jsdoc_state_authority" : "open_ended_string",
  });
}

function isStringLiteralUnion(node, ts) {
  return ts.isUnionTypeNode(node) && node.types.length > 0 && node.types.every((member) => {
    return ts.isLiteralTypeNode(member) && stringLiteral(member.literal, ts) !== null;
  });
}

function terminalAssignedLiteral(node, ts) {
  const current = unwrapParentheses(node, ts);
  const direct = stringLiteral(current, ts);
  if (direct !== null) return direct;
  if (ts.isBinaryExpression(current) && [
    ts.SyntaxKind.EqualsToken,
    ts.SyntaxKind.QuestionQuestionEqualsToken,
  ].includes(current.operatorToken.kind)) {
    return terminalAssignedLiteral(current.right, ts);
  }
  return null;
}

function staticModuleSpecifiers(ts, sourceFile) {
  const specifiers = [];
  const visit = (node) => {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteralLike(node.moduleSpecifier)) {
      specifiers.push(node.moduleSpecifier.text);
    } else if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "require" && node.arguments.length === 1 && ts.isStringLiteralLike(node.arguments[0])) {
      specifiers.push(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return specifiers;
}

function detect(projectRoot, target, tsconfigPath, language) {
  const config = loadTypeScript(projectRoot, tsconfigPath, language);
  const { ts, options } = config;
  const files = walkTypeScriptFiles(target, language);
  const configured = new Set(config.fileNames);
  const uncoveredFiles = language === "javascript"
    ? files.filter((file) => !configured.has(file)).map((file) => ({ file: relative(projectRoot, file), reason: "not_in_explicit_jsconfig_or_tsconfig" }))
    : [];
  const selectedFiles = language === "javascript" ? files.filter((file) => configured.has(file)) : files;
  const program = ts.createProgram({ rootNames: language === "javascript" ? config.fileNames : files, options });
  const syntaxError = program.getSyntacticDiagnostics().find((diagnostic) => {
    return diagnostic.category === ts.DiagnosticCategory.Error;
  });
  if (syntaxError) {
    const filename = syntaxError.file?.fileName ?? `${language === "javascript" ? "JavaScript" : "TypeScript"} input`;
    const message = ts.flattenDiagnosticMessageText(syntaxError.messageText, " ");
    fail(`syntax-error: ${language === "javascript" ? "JavaScript" : "TypeScript"} syntax error in ${filename}: ${message}`);
  }
  const checker = program.getTypeChecker();
  const records = [];

  for (const sourceFile of program.getSourceFiles()) {
    if (!selectedFiles.includes(sourceFile.fileName)) continue;
    const aliases = new Map();
    const collectAliases = (node) => {
      if (
        ts.isVariableDeclaration(node)
        && ts.isIdentifier(node.name)
        && node.initializer
        && ts.isVariableDeclarationList(node.parent)
        && (node.parent.flags & ts.NodeFlags.Const)
      ) {
        const property = stateProperty(node.initializer, ts);
        const symbol = checker.getSymbolAtLocation(node.name);
        if (property && symbol) {
          aliases.set(symbol, {
            field: property.name.text,
            stateType: checker.getTypeAtLocation(property),
            receiverType: checker.getTypeAtLocation(property.expression),
          });
        }
      }
      ts.forEachChild(node, collectAliases);
    };
    collectAliases(sourceFile);
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
        const operand = stateOperand(node.left, aliases, checker, ts)
          || stateOperand(node.right, aliases, checker, ts);
        if (isComparison && operand && (leftLiteral ?? rightLiteral) !== null) {
          emitStateOperation(records, projectRoot, sourceFile, node, operand, leftLiteral ?? rightLiteral, "comparison", ts, language);
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
      if (ts.isBinaryExpression(node) && [
        ts.SyntaxKind.EqualsToken,
        ts.SyntaxKind.QuestionQuestionEqualsToken,
      ].includes(node.operatorToken.kind)) {
        const operand = stateOperand(node.left, aliases, checker, ts);
        const literal = terminalAssignedLiteral(node.right, ts);
        if (operand && literal !== null) {
          emitStateOperation(records, projectRoot, sourceFile, node, operand, literal, "assignment", ts, language);
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  const sourceFiles = selectedFiles.map((file) => program.getSourceFile(file)).filter(Boolean);
  const cache = ts.createModuleResolutionCache(projectRoot, (file) => file, options);
  const unresolved = sourceFiles.flatMap((sourceFile) => staticModuleSpecifiers(ts, sourceFile)
    .filter((specifier) => !ts.resolveModuleName(specifier, sourceFile.fileName, options, ts.sys, cache).resolvedModule)
    .map((specifier) => ({ file: relative(projectRoot, sourceFile.fileName), specifier })));
  const diagnostics = language === "javascript"
    ? program.getSemanticDiagnostics().filter((diagnostic) => diagnostic.file && selectedFiles.includes(diagnostic.file.fileName)).map((diagnostic) => ({
      file: relative(projectRoot, diagnostic.file.fileName),
      message: ts.flattenDiagnosticMessageText(diagnostic.messageText, " "),
    }))
    : [];
  const jsdocDeclarations = sourceFiles.reduce((count, sourceFile) => count + (sourceFile.text.match(/\/\*\*/g)?.length ?? 0), 0);
  return {
    records,
    manifest: {
      language,
      analyzer: language === "javascript" ? "typescript-compiler-api-checked-javascript" : "typescript-compiler-api",
      status: unresolved.length || uncoveredFiles.length || diagnostics.length ? "partial" : "complete",
      config: relative(projectRoot, config.configPath),
      diagnostics,
      unresolved_modules: unresolved,
      uncovered_files: uncoveredFiles,
      semantic_evidence: language === "javascript" ? {
        checked_javascript: true,
        jsdoc: { declarations: jsdocDeclarations, authority: "finite JSDoc type only" },
        compiler_inferred: { state_operations: records.filter((record) => record.classification === "first_party_state_operation").length },
      } : undefined,
    },
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectRoot = path.resolve(args["project-root"]);
  const target = path.resolve(args.target);
  const tsconfig = path.resolve(args.tsconfig);
  if (!fs.existsSync(target) || !fs.statSync(target).isDirectory() || fs.lstatSync(target).isSymbolicLink()) fail(`target directory not found or is symbolic link: ${target}`);
  const outcome = detect(projectRoot, target, tsconfig, args.language);
  const records = outcome.records;
  fs.mkdirSync(path.dirname(path.resolve(args.output)), { recursive: true });
  fs.writeFileSync(path.resolve(args.output), `${records.map((record) => JSON.stringify(record)).join("\n")}${records.length ? "\n" : ""}`);
  if (args.language === "javascript") {
    const manifest = path.resolve(args.manifest);
    if (!manifest.startsWith(`${projectRoot}${path.sep}`) || (fs.existsSync(manifest) && fs.lstatSync(manifest).isSymbolicLink())) {
      fail("manifest must stay inside the project root and must not be a symbolic link");
    }
    fs.mkdirSync(path.dirname(manifest), { recursive: true });
    fs.writeFileSync(manifest, `${JSON.stringify(outcome.manifest, null, 2)}\n`);
  }
  const actionable = records.filter((record) => record.classification === "first_party_state_operation").length;
  process.stderr.write(`[detect_${args.language}_state] ${records.length} records; ${actionable} first-party state operations\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`error: ${error.message}\n`);
  process.exitCode = 2;
}
