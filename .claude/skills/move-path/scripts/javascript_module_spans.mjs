#!/usr/bin/env node
/** Emit only host-checked literal JavaScript module-specifier spans. */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const SUFFIXES = new Set([".js", ".jsx", ".mjs", ".cjs"]);

function finish(status, payload, code) {
  process.stdout.write(JSON.stringify({ status, ...payload }) + "\n");
  process.exit(code);
}

function fail(message, status = "unsupported", code = 2) {
  finish(status, { error: message }, code);
}

function parse(argv) {
  const options = { files: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--project-root" || arg === "--config") {
      const value = argv[++index];
      if (!value) fail(`missing value for ${arg}`);
      options[arg === "--project-root" ? "projectRoot" : "config"] = value;
    } else if (arg.startsWith("--")) {
      fail(`unknown option: ${arg}`);
    } else {
      options.files.push(arg);
    }
  }
  if (!options.projectRoot || !options.config || !options.files.length) {
    fail("usage: javascript_module_spans.mjs --project-root <path> --config <jsconfig|tsconfig> <file>...");
  }
  return options;
}

function diagnostic(ts, value) {
  const message = ts.flattenDiagnosticMessageText(value.messageText, " ");
  if (!value.file) return message;
  const position = value.file.getLineAndCharacterOfPosition(value.start ?? 0);
  return `${value.file.fileName}:${position.line + 1}:${position.character + 1}: ${message}`;
}

function compiler(projectRoot, configPath) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) fail(`project-local TypeScript requires ${packageJson}`);
  if (!fs.existsSync(configPath)) fail(`unsupported: checked JavaScript requires an explicit jsconfig/tsconfig at ${configPath}`);
  if (fs.lstatSync(configPath).isSymbolicLink()) fail(`checked JavaScript config must not be a symbolic link: ${configPath}`);
  let ts;
  try {
    ts = createRequire(packageJson)("typescript");
  } catch (error) {
    fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`);
  }
  const read = ts.readConfigFile(configPath, ts.sys.readFile);
  if (read.error) fail(`cannot read checked JavaScript config: ${diagnostic(ts, read.error)}`);
  const parsed = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(configPath));
  const error = parsed.errors.find((item) => item.category === ts.DiagnosticCategory.Error);
  if (error) fail(`cannot parse checked JavaScript config: ${diagnostic(ts, error)}`);
  if (!parsed.options.allowJs || !parsed.options.checkJs) {
    fail("unsupported: checked JavaScript requires compilerOptions.allowJs and compilerOptions.checkJs set to true");
  }
  return { ts, parsed };
}

function literal(ts, node) {
  return ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) ? node : null;
}

function spans(ts, root, source) {
  const file = path.relative(root, source.fileName).split(path.sep).join("/");
  const moduleSpecifiers = [];
  const unsupported = [];
  const record = (kind, node) => {
    const position = source.getLineAndCharacterOfPosition(node.getStart(source));
    moduleSpecifiers.push({
      file,
      kind,
      start: node.getStart(source) + 1,
      end: node.getEnd() - 1,
      line: position.line + 1,
      specifier: node.text,
    });
  };
  const visit = (node) => {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier) {
      const value = literal(ts, node.moduleSpecifier);
      if (value) record(ts.isImportDeclaration(node) ? "esm_import" : "esm_export", value);
    } else if (ts.isCallExpression(node)) {
      const dynamic = node.expression.kind === ts.SyntaxKind.ImportKeyword;
      const commonjs = ts.isIdentifier(node.expression) && node.expression.text === "require";
      if (dynamic || commonjs) {
        const value = node.arguments.length === 1 ? literal(ts, node.arguments[0]) : null;
        if (value) record(dynamic ? "dynamic_import" : "cjs_require", value);
        else unsupported.push({ file, kind: dynamic ? "dynamic_import" : "cjs_require" });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return { moduleSpecifiers, unsupported };
}

function main() {
  const args = parse(process.argv.slice(2));
  const root = path.resolve(args.projectRoot);
  const config = path.resolve(args.config);
  const { ts, parsed } = compiler(root, config);
  const files = args.files.map((file) => path.resolve(file));
  const configured = new Set(parsed.fileNames.map((file) => path.resolve(file)));
  const uncovered = [];
  for (const file of files) {
    if (!SUFFIXES.has(path.extname(file).toLowerCase())) fail(`unsupported JavaScript suffix: ${file}`);
    if (!fs.existsSync(file)) fail(`cannot read ${file}`, "failed", 1);
    if (fs.lstatSync(file).isSymbolicLink()) fail(`JavaScript source must not be a symbolic link: ${file}`);
    if (!configured.has(file)) uncovered.push(file);
  }
  if (uncovered.length) finish("partial", { config, uncovered_files: uncovered }, 3);
  const program = ts.createProgram({ rootNames: parsed.fileNames, options: parsed.options });
  const diagnostics = [];
  const moduleSpecifiers = [];
  const unsupported = [];
  for (const file of files) {
    const source = program.getSourceFile(file);
    if (!source) diagnostics.push(`${file}: TypeScript did not load configured source`);
    else {
      diagnostics.push(...ts.getPreEmitDiagnostics(program, source).map((item) => diagnostic(ts, item)));
      const found = spans(ts, root, source);
      moduleSpecifiers.push(...found.moduleSpecifiers);
      unsupported.push(...found.unsupported);
    }
  }
  if (diagnostics.length) finish("failed", { config, diagnostics }, 1);
  finish("complete", { config, checked_files: files, module_specifiers: moduleSpecifiers, unsupported, typescript_version: ts.version }, 0);
}

main();
