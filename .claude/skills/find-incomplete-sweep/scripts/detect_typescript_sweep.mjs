#!/usr/bin/env node
/**
 * Compiler-backed TypeScript / TSX incomplete-sweep detector.
 *
 * This family-local consumer resolves one named host tsconfig and groups only
 * static calls whose callee resolves to a project function declaration.  It
 * follows import aliases and locally-declared object-literal spreads, keeps
 * overload signatures distinct, and reads destructured option defaults.  It
 * intentionally defers method/framework APIs, dynamic receivers, unresolved
 * spreads, and runtime conventions rather than approximating them lexically.
 */
import { createRequire } from "node:module";
import childProcess from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const TYPESCRIPT_SOURCE_EXTENSIONS = new Set([".ts", ".tsx"]);
const JAVASCRIPT_SOURCE_EXTENSIONS = new Set([".js", ".jsx", ".mjs", ".cjs"]);
const BUILTIN_EXCLUDED_DIRECTORIES = new Set([
  ".git", ".venv", "venv", "node_modules", "dist", "build", "coverage",
  "__tests__", "test", "tests", "fixtures", "fixture", "generated", "vendor",
]);

class SweepError extends Error {}

function fail(message) {
  throw new SweepError(message);
}

function parseArgs(argv) {
  const values = new Map();
  let noGate = false;
  const allowed = new Set([
    "--target", "--project-root", "--tsconfig", "--report-dir", "--min-callsites", "--majority-frac", "--min-present", "--language",
  ]);
  for (let index = 0; index < argv.length;) {
    const flag = argv[index];
    if (flag === "--no-gate") {
      if (noGate) fail("--no-gate may be supplied once");
      noGate = true;
      index += 1;
      continue;
    }
    const value = argv[index + 1];
    if (!allowed.has(flag) || value === undefined || values.has(flag)) {
      fail(
        "usage: detect_typescript_sweep.mjs --target <path> --project-root <path> --tsconfig <path> "
        + "--report-dir <reports/find-incomplete-sweep/name> [--min-callsites 4] [--majority-frac 0.75] [--min-present 3] [--no-gate]",
      );
    }
    values.set(flag, value);
    index += 2;
  }
  for (const required of ["--target", "--project-root", "--tsconfig", "--report-dir"]) {
    if (!values.has(required)) fail(`missing required argument: ${required}`);
  }
  const minCallsites = Number(values.get("--min-callsites") ?? "4");
  const majorityFrac = Number(values.get("--majority-frac") ?? "0.75");
  const minPresent = Number(values.get("--min-present") ?? "3");
  if (!Number.isInteger(minCallsites) || minCallsites < 2) fail("--min-callsites must be an integer >= 2");
  if (!Number.isFinite(majorityFrac) || majorityFrac <= 0 || majorityFrac > 1) fail("--majority-frac must be in (0, 1]");
  if (!Number.isInteger(minPresent) || minPresent < 1) fail("--min-present must be an integer >= 1");
  const language = values.get("--language") ?? "typescript";
  if (!["typescript", "javascript"].includes(language)) fail("--language must be typescript or javascript");
  return {
    target: values.get("--target"),
    projectRoot: values.get("--project-root"),
    tsconfig: values.get("--tsconfig"),
    reportDir: values.get("--report-dir"),
    minCallsites,
    majorityFrac,
    minPresent,
    noGate,
    language,
  };
}

function isWithin(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}

function relativePath(projectRoot, absolutePath) {
  return path.relative(projectRoot, absolutePath).split(path.sep).join("/");
}

function requireExistingDirectory(candidate, label) {
  if (!fs.existsSync(candidate) || !fs.statSync(candidate).isDirectory()) {
    fail(`${label} is not a directory: ${candidate}`);
  }
  return fs.realpathSync(candidate);
}

function resolveProjectPath(projectRoot, value, label) {
  const candidate = path.resolve(projectRoot, value);
  if (!isWithin(projectRoot, candidate)) fail(`${label} must stay inside project root: ${value}`);
  return candidate;
}

function traversesSymbolicLink(projectRoot, absolutePath) {
  if (!isWithin(projectRoot, absolutePath)) return true;
  const parts = path.relative(projectRoot, absolutePath).split(path.sep).filter(Boolean);
  let current = projectRoot;
  for (const part of parts) {
    current = path.join(current, part);
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) return true;
  }
  return false;
}

function safeReportDirectory(projectRoot, suppliedPath) {
  const reportDir = resolveProjectPath(projectRoot, suppliedPath, "report directory");
  const allowedRoot = path.join(projectRoot, "reports", "find-incomplete-sweep");
  if (!isWithin(allowedRoot, reportDir) || reportDir === allowedRoot) {
    fail(`report directory must stay beneath reports/find-incomplete-sweep/: ${suppliedPath}`);
  }
  if (traversesSymbolicLink(projectRoot, reportDir)) {
    fail(`report directory must not traverse a symbolic link: ${suppliedPath}`);
  }
  return reportDir;
}

function loadProjectTypeScript(projectRoot) {
  const packageJson = path.join(projectRoot, "package.json");
  if (!fs.existsSync(packageJson)) fail(`project-local TypeScript requires ${packageJson}`);
  try {
    const requireFromProject = createRequire(packageJson);
    const resolved = requireFromProject.resolve("typescript");
    if (!isWithin(projectRoot, fs.realpathSync(resolved))) {
      fail(`project-local TypeScript package is unavailable from ${packageJson}`);
    }
    const ts = requireFromProject("typescript");
    if (
      typeof ts.createProgram !== "function"
      || typeof ts.resolveModuleName !== "function"
      || typeof ts.createModuleResolutionCache !== "function"
    ) fail("project-local TypeScript package lacks the required Compiler API");
    return ts;
  } catch (error) {
    if (error instanceof SweepError) throw error;
    fail(`project-local TypeScript package is unavailable from ${packageJson}: ${error.message}`);
  }
}

function diagnosticText(ts, diagnostic) {
  const text = ts.flattenDiagnosticMessageText(diagnostic.messageText, " ");
  if (!diagnostic.file) return text;
  const position = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start ?? 0);
  return `${diagnostic.file.fileName}:${position.line + 1}: ${text}`;
}

function resolveProjectTsconfig(ts, projectRoot, suppliedTsconfig, language) {
  const tsconfigPath = resolveProjectPath(projectRoot, suppliedTsconfig, "tsconfig");
  if (!fs.existsSync(tsconfigPath)) fail(language === "javascript"
    ? `unsupported: checked JavaScript requires an explicit jsconfig/tsconfig: ${tsconfigPath}`
    : `project-local TypeScript requires tsconfig: ${tsconfigPath}`);
  const stats = fs.lstatSync(tsconfigPath);
  if (stats.isSymbolicLink()) fail(`${language === "javascript" ? "JavaScript config" : "tsconfig"} must not be a symbolic link: ${tsconfigPath}`);
  if (!stats.isFile()) fail(`project config is not a file: ${tsconfigPath}`);
  const read = ts.readConfigFile(tsconfigPath, ts.sys.readFile);
  if (read.error) fail(`invalid tsconfig: ${diagnosticText(ts, read.error)}`);
  const parsed = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(tsconfigPath), undefined, tsconfigPath);
  const errors = parsed.errors.filter((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error);
  if (errors.length > 0) fail(`invalid tsconfig: ${diagnosticText(ts, errors[0])}`);
  if (language === "javascript" && (!parsed.options.allowJs || !parsed.options.checkJs)) {
    fail("unsupported: checked JavaScript requires compilerOptions.allowJs and compilerOptions.checkJs set to true");
  }
  return {
    path: tsconfigPath,
    options: parsed.options,
    fileNames: parsed.fileNames.map((file) => path.resolve(file)),
    projectReferences: parsed.projectReferences ?? [],
    declaredExcludes: Array.isArray(read.config.exclude) ? read.config.exclude.map(String) : [],
  };
}

function globToRegExp(glob) {
  let result = "^";
  for (let index = 0; index < glob.length; index += 1) {
    const char = glob[index];
    if (char === "*") {
      if (glob[index + 1] === "*") {
        if (glob[index + 2] === "/") {
          result += "(?:.*/)?";
          index += 2;
        } else {
          result += ".*";
          index += 1;
        }
      } else result += "[^/]*";
    } else if (char === "?") result += "[^/]";
    else result += char.replace(/[|\\{}()[\]^$+?.]/g, "\\$&");
  }
  return new RegExp(`${result}$`);
}

function buildExclusionPolicy(projectRoot, declaredExcludes, language) {
  const rules = declaredExcludes
    .map((rule) => rule.replaceAll("\\", "/").replace(/^\.\//, "").replace(/\/$/, ""))
    .filter(Boolean)
    .map((rule) => ({ rule, regex: /[*?]/.test(rule) ? globToRegExp(rule) : null }));
  function matchesDeclaredExclude(relative, directory) {
    return rules.some(({ rule, regex }) => {
      if (regex) return regex.test(relative) || (directory && regex.test(`${relative}/`));
      return relative === rule || relative.startsWith(`${rule}/`);
    });
  }
  return {
    isExcluded(absolutePath, directory = false) {
      const normalized = path.resolve(absolutePath);
      if (!isWithin(projectRoot, normalized)) return true;
      const relative = relativePath(projectRoot, normalized);
      const parts = relative.split("/");
      const directoryParts = directory ? parts : parts.slice(0, -1);
      if (directoryParts.some((part) => BUILTIN_EXCLUDED_DIRECTORIES.has(part.toLowerCase()))) return true;
      const filename = parts.at(-1)?.toLowerCase() ?? "";
      const extension = language === "javascript" ? "(?:js|jsx|mjs|cjs)" : "(?:ts|tsx)";
      if (!directory && (
        filename.endsWith(".d.ts") || filename.endsWith(".d.tsx")
        || new RegExp(`\\.(?:test|spec|generated|min|bundle)\\.${extension}$`).test(filename)
        || filename.startsWith("test_") || filename.startsWith("tests_")
        || filename.endsWith("_test.ts") || filename.endsWith("_test.tsx")
      )) return true;
      return matchesDeclaredExclude(relative, directory);
    },
  };
}

function isSourcePath(absolutePath, language) {
  const extensions = language === "javascript" ? JAVASCRIPT_SOURCE_EXTENSIONS : TYPESCRIPT_SOURCE_EXTENSIONS;
  return extensions.has(path.extname(absolutePath).toLowerCase())
    && !absolutePath.toLowerCase().endsWith(".d.ts")
    && !absolutePath.toLowerCase().endsWith(".d.tsx");
}

function collectTargetSources(target, projectRoot, exclusions, language) {
  if (traversesSymbolicLink(projectRoot, target)) fail(`target must not traverse a symbolic link: ${target}`);
  const stats = fs.lstatSync(target);
  if (stats.isSymbolicLink()) fail(`target must not be a symbolic link: ${target}`);
  if (stats.isFile()) {
    if (!isSourcePath(target, language)) fail(`target must be a ${language === "javascript" ? ".js, .jsx, .mjs, or .cjs" : ".ts or .tsx"} file, or a directory: ${target}`);
    return exclusions.isExcluded(target) ? [] : [target];
  }
  if (!stats.isDirectory()) fail(`target must be a file or directory: ${target}`);
  if (exclusions.isExcluded(target, true)) return [];
  const files = [];
  const pending = [target];
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const child = path.join(current, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        if (!exclusions.isExcluded(child, true)) pending.push(child);
      } else if (entry.isFile() && isSourcePath(child, language) && !exclusions.isExcluded(child)) files.push(child);
    }
  }
  return files.sort((left, right) => relativePath(projectRoot, left).localeCompare(relativePath(projectRoot, right)));
}

function collectEligibleProgramSources(program, projectRoot, exclusions, language) {
  return program.getSourceFiles().filter((sourceFile) => {
    const absolute = path.resolve(sourceFile.fileName);
    return isWithin(projectRoot, absolute)
      && !traversesSymbolicLink(projectRoot, absolute)
      && isSourcePath(absolute, language)
      && !exclusions.isExcluded(absolute);
  });
}

function canonicalSymbol(checker, symbol, ts) {
  if (symbol && (symbol.flags & ts.SymbolFlags.Alias)) return checker.getAliasedSymbol(symbol);
  return symbol;
}

function unwrapExpression(node, ts) {
  let current = node;
  while (ts.isAsExpression(current) || ts.isTypeAssertionExpression(current) || ts.isParenthesizedExpression(current)) {
    current = current.expression;
  }
  return current;
}

function optionName(name, ts) {
  if (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)) return name.text;
  return null;
}

function valueSignature(node, ts) {
  const value = unwrapExpression(node, ts);
  if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) return JSON.stringify(value.text);
  if (ts.isNumericLiteral(value)) return value.text;
  if (value.kind === ts.SyntaxKind.TrueKeyword) return "true";
  if (value.kind === ts.SyntaxKind.FalseKeyword) return "false";
  if (value.kind === ts.SyntaxKind.NullKeyword) return "null";
  return null;
}

function resolveObjectExpression(node, checker, ts, seen = new Set()) {
  const expression = unwrapExpression(node, ts);
  if (ts.isObjectLiteralExpression(expression)) return expression;
  if (!ts.isIdentifier(expression)) return null;
  const symbol = canonicalSymbol(checker, checker.getSymbolAtLocation(expression), ts);
  const declaration = symbol?.valueDeclaration;
  if (!declaration || !ts.isVariableDeclaration(declaration) || !declaration.initializer || seen.has(declaration)) return null;
  seen.add(declaration);
  return resolveObjectExpression(declaration.initializer, checker, ts, seen);
}

function readOptionObject(node, checker, ts, seen = new Set()) {
  const object = resolveObjectExpression(node, checker, ts, seen);
  if (!object) return { properties: new Map(), unknownSpread: true, isObject: false };
  const properties = new Map();
  let unknownSpread = false;
  for (const property of object.properties) {
    if (ts.isPropertyAssignment(property)) {
      const name = optionName(property.name, ts);
      if (name) properties.set(name, valueSignature(property.initializer, ts));
    } else if (ts.isShorthandPropertyAssignment(property)) {
      properties.set(property.name.text, null);
    } else if (ts.isSpreadAssignment(property)) {
      const expanded = readOptionObject(property.expression, checker, ts, seen);
      if (!expanded.isObject || expanded.unknownSpread) unknownSpread = true;
      for (const [name, value] of expanded.properties) properties.set(name, value);
    } else unknownSpread = true;
  }
  return { properties, unknownSpread, isObject: true };
}

function optionArgument(call, checker, ts) {
  for (const argument of call.arguments) {
    const options = readOptionObject(argument, checker, ts);
    if (options.isObject) return options;
  }
  return null;
}

function declarationName(declaration, fallback) {
  return declaration.name?.text ?? fallback;
}

function sourcePosition(sourceFile, node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
}

function functionDefaults(declaration, ts) {
  const defaults = new Map();
  for (const parameter of declaration.parameters ?? []) {
    if (!ts.isObjectBindingPattern(parameter.name)) continue;
    for (const element of parameter.name.elements) {
      const name = element.propertyName ? optionName(element.propertyName, ts) : element.name.text;
      if (name && element.initializer) defaults.set(name, valueSignature(element.initializer, ts));
    }
  }
  return defaults;
}

function staticModuleSpecifiers(ts, sourceFile) {
  const specifiers = [];
  for (const statement of sourceFile.statements) {
    if (ts.isImportDeclaration(statement) && ts.isStringLiteralLike(statement.moduleSpecifier)) specifiers.push(statement.moduleSpecifier.text);
    else if (ts.isExportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteralLike(statement.moduleSpecifier)) specifiers.push(statement.moduleSpecifier.text);
    else if (
      ts.isImportEqualsDeclaration(statement)
      && ts.isExternalModuleReference(statement.moduleReference)
      && statement.moduleReference.expression
      && ts.isStringLiteralLike(statement.moduleReference.expression)
    ) specifiers.push(statement.moduleReference.expression.text);
  }
  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "require" && node.arguments.length === 1 && ts.isStringLiteralLike(node.arguments[0])) {
      specifiers.push(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return specifiers;
}

function unresolvedModules(ts, sourceFiles, config, projectRoot) {
  const cache = ts.createModuleResolutionCache(projectRoot, (fileName) => fileName, config.options);
  const unresolved = [];
  for (const sourceFile of sourceFiles) {
    const sourceAbsolute = path.resolve(sourceFile.fileName);
    for (const specifier of staticModuleSpecifiers(ts, sourceFile)) {
      const result = ts.resolveModuleName(specifier, sourceAbsolute, config.options, ts.sys, cache);
      if (!result.resolvedModule) unresolved.push({ file: relativePath(projectRoot, sourceAbsolute), specifier });
    }
  }
  return unresolved.sort((left, right) => left.file.localeCompare(right.file) || left.specifier.localeCompare(right.specifier));
}

function addCallFacts(targetFiles, program, projectRoot, exclusions, ts, language) {
  const checker = program.getTypeChecker();
  const supported = new Map();
  const deferredGroups = new Map();
  const unresolvedCalls = [];
  const projectSources = new Set(collectEligibleProgramSources(program, projectRoot, exclusions, language).map((sourceFile) => path.resolve(sourceFile.fileName)));

  function addGroup(groups, key, details, call) {
    if (!groups.has(key)) groups.set(key, { ...details, calls: [] });
    groups.get(key).calls.push(call);
  }
  for (const file of targetFiles) {
    const sourceFile = program.getSourceFile(file);
    if (!sourceFile) continue;
    const visit = (node) => {
      if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
        const options = optionArgument(node, checker, ts);
        if (options) {
          const signature = checker.getResolvedSignature(node);
          const declaration = signature?.getDeclaration?.() ?? signature?.declaration;
          const line = sourcePosition(sourceFile, node);
          const call = {
            file: relativePath(projectRoot, file),
            line,
            properties: options.properties,
            unknownSpread: options.unknownSpread,
          };
          if (!declaration) {
            unresolvedCalls.push({ file: call.file, line, reason: "dynamic_or_unresolved_callee" });
          } else {
            const declarationSource = declaration.getSourceFile?.();
            const declarationFile = declarationSource ? path.resolve(declarationSource.fileName) : null;
            const display = declarationName(declaration, node.expression.getText(sourceFile));
            if (ts.isFunctionDeclaration(declaration) && declarationFile && projectSources.has(declarationFile)) {
              const key = `${relativePath(projectRoot, declarationFile)}:${declaration.getStart(declarationSource)}`;
              addGroup(supported, key, {
                callee: display,
                defaults: functionDefaults(declaration, ts),
              }, call);
            } else {
              const key = declarationFile
                ? `${relativePath(projectRoot, declarationFile)}:${declaration.getStart(declarationSource)}:${display}`
                : `${display}:${declaration.kind}`;
              addGroup(deferredGroups, key, { callee: display }, call);
            }
          }
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }
  return { supported, deferredGroups, unresolvedCalls };
}

function candidateRows(groups, thresholds, gate) {
  const findings = [];
  const downRanked = [];
  const gatedOut = [];
  const unresolvedSpreads = [];
  for (const group of groups.values()) {
    const size = group.calls.length;
    if (size < thresholds.minCallsites) continue;
    const propertyCounts = new Map();
    for (const call of group.calls) {
      for (const property of call.properties.keys()) propertyCounts.set(property, (propertyCounts.get(property) ?? 0) + 1);
    }
    const threshold = Math.max(thresholds.minPresent, Math.ceil(thresholds.majorityFrac * size));
    for (const [kwarg, presentCount] of propertyCounts) {
      if (presentCount < threshold || presentCount >= size) continue;
      const present = group.calls.filter((call) => call.properties.has(kwarg));
      const missing = group.calls.filter((call) => !call.properties.has(kwarg) && !call.unknownSpread);
      const unknown = group.calls.filter((call) => !call.properties.has(kwarg) && call.unknownSpread);
      for (const call of unknown) unresolvedSpreads.push({ file: call.file, line: call.line, reason: "unresolved_object_spread" });
      const defaultValue = group.defaults.get(kwarg);
      const presentValues = new Set(present.map((call) => call.properties.get(kwarg)).filter((value) => value !== null));
      const promoted = defaultValue !== undefined && defaultValue !== null && presentValues.size === 1 && !presentValues.has(defaultValue);
      const optionalByDefault = defaultValue !== undefined && !promoted;
      const overrideValue = promoted ? [...presentValues][0] : null;
      for (const straggler of missing) {
        const row = {
          callee: group.callee,
          kwarg,
          group_size: size,
          present_count: presentCount,
          majority_frac: Number((presentCount / size).toFixed(2)),
          straggler: `${straggler.file}:${straggler.line}`,
          present_sites: present.map((call) => ({ file: call.file, line: call.line })),
          gated_in: false,
          optional_by_default: optionalByDefault,
          override_value: overrideValue,
          default_value: promoted ? defaultValue : (optionalByDefault ? defaultValue : null),
          trajectory: "",
        };
        if (optionalByDefault) {
          downRanked.push({
            callee: row.callee,
            kwarg: row.kwarg,
            group_size: row.group_size,
            present_count: row.present_count,
            optional_by_default: true,
            default_value: row.default_value,
          });
        } else {
          gate(row, straggler, present);
          if (row.gated_in) findings.push(row);
          else gatedOut.push(row);
        }
      }
    }
  }
  return { findings, downRanked, gatedOut, unresolvedSpreads };
}

function lineCommitTime(absoluteFile, line) {
  const result = childProcess.spawnSync("git", ["blame", "--porcelain", "-L", `${line},${line}`, "--", path.basename(absoluteFile)], {
    cwd: path.dirname(absoluteFile), encoding: "utf8", timeout: 20_000,
  });
  if (result.status !== 0 || !result.stdout) return null;
  const lines = result.stdout.split("\n");
  if (lines[0]?.split(" ")[0]?.match(/^0+$/)) return null;
  const time = lines.find((lineText) => lineText.startsWith("committer-time "));
  if (!time) return null;
  const parsed = Number(time.slice("committer-time ".length));
  return Number.isFinite(parsed) ? parsed : null;
}

function trajectoryGate(projectRoot, noGate) {
  return (row, straggler, present) => {
    if (noGate) {
      row.trajectory = "git-trajectory gate skipped by --no-gate";
      return;
    }
    const stragglerTime = lineCommitTime(path.join(projectRoot, straggler.file), straggler.line);
    const presentTimes = present
      .map((call) => lineCommitTime(path.join(projectRoot, call.file), call.line))
      .filter((time) => time !== null);
    if (stragglerTime === null || presentTimes.length === 0) {
      row.trajectory = "no blame data — cannot establish trajectory";
      return;
    }
    const newer = presentTimes.filter((time) => time > stragglerTime).length;
    if (newer / presentTimes.length >= 0.5) {
      row.gated_in = true;
      row.trajectory = `${newer}/${presentTimes.length} option-present sites touched AFTER the straggler — consistent with a sweep that missed it`;
    } else row.trajectory = `only ${newer}/${presentTimes.length} option-present sites newer than straggler — likely deliberate`;
  };
}

function deferredRows(groups, thresholds) {
  const rows = [];
  for (const group of groups.values()) {
    const size = group.calls.length;
    if (size < thresholds.minCallsites) continue;
    const counts = new Map();
    for (const call of group.calls) for (const property of call.properties.keys()) counts.set(property, (counts.get(property) ?? 0) + 1);
    const threshold = Math.max(thresholds.minPresent, Math.ceil(thresholds.majorityFrac * size));
    for (const [property, count] of counts) {
      if (count < threshold || count >= size) continue;
      for (const call of group.calls) {
        if (!call.properties.has(property) && !call.unknownSpread) {
          rows.push({ file: call.file, line: call.line, reason: "framework_or_external_method_signature" });
        }
      }
    }
  }
  return rows;
}

function renderFindings(payload) {
  const languageLabel = payload.language === "javascript" ? "checked JavaScript v1" : "TypeScript v1";
  const lines = [
    `# find-incomplete-sweep — findings (${languageLabel})`,
    "",
    `Status: **${payload.status}**. Compiler-backed resolved call and object-option evidence only.`,
    "",
    "## Gated IN — likely forgotten sweeps",
    "",
  ];
  if (payload.findings.length === 0) lines.push("_none_");
  for (const finding of payload.findings) {
    lines.push(`### \`${finding.callee}\` missing \`${finding.kwarg}\``, "");
    lines.push(`- straggler: \`${finding.straggler}\``);
    lines.push(`- majority: ${finding.present_count}/${finding.group_size} (${Math.round(finding.majority_frac * 100)}%)`);
    if (finding.override_value !== null) lines.push(`- value override: \`${finding.override_value}\` differs from default \`${finding.default_value}\``);
    lines.push(`- trajectory: ${finding.trajectory}`, "");
  }
  lines.push("## Down-ranked defaults", "");
  if (payload.down_ranked.length === 0) lines.push("_none_");
  for (const row of payload.down_ranked) lines.push(`- \`${row.callee}\` omits \`${row.kwarg}\` and takes declared default \`${row.default_value}\``);
  lines.push("", "## Deferred boundaries", "");
  if (payload.deferred.length === 0) lines.push("_none_");
  for (const row of payload.deferred) lines.push(`- \`${row.file}:${row.line}\` — ${row.reason}`);
  lines.push("", "## Project resolution", "");
  lines.push(`State: **${payload.project_resolution.state}**.`);
  for (const row of payload.project_resolution.unresolved_modules) lines.push(`- \`${row.file}\` — unresolved \`${row.specifier}\``);
  return `${lines.join("\n")}\n`;
}

function writeAtomically(destination, contents) {
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  const temporary = `${destination}.tmp-${process.pid}`;
  fs.writeFileSync(temporary, contents, "utf8");
  fs.renameSync(temporary, destination);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectRoot = requireExistingDirectory(path.resolve(args.projectRoot), "project root");
  const target = resolveProjectPath(projectRoot, args.target, "target");
  if (!fs.existsSync(target)) fail(`target does not exist: ${target}`);
  if (traversesSymbolicLink(projectRoot, target)) fail(`target must not traverse a symbolic link: ${target}`);
  const targetStats = fs.lstatSync(target);
  if (targetStats.isSymbolicLink()) fail(`target must not be a symbolic link: ${target}`);
  const reportDir = safeReportDirectory(projectRoot, args.reportDir);
  const ts = loadProjectTypeScript(projectRoot);
  const config = resolveProjectTsconfig(ts, projectRoot, args.tsconfig, args.language);
  const exclusions = buildExclusionPolicy(projectRoot, config.declaredExcludes, args.language);
  const targetFiles = collectTargetSources(target, projectRoot, exclusions, args.language);
  const configuredFiles = new Set(config.fileNames.map((file) => path.resolve(file)));
  const uncoveredFiles = args.language === "javascript"
    ? targetFiles.filter((file) => !configuredFiles.has(file)).map((file) => ({
      file: relativePath(projectRoot, file), reason: "not_in_explicit_jsconfig_or_tsconfig",
    }))
    : [];
  const coveredTargetFiles = args.language === "javascript"
    ? targetFiles.filter((file) => configuredFiles.has(file))
    : targetFiles;
  if (args.language === "javascript" && targetFiles.length === 0 && exclusions.isExcluded(target, targetStats.isDirectory())) {
    uncoveredFiles.push({ file: relativePath(projectRoot, target), reason: "excluded_by_project_config" });
  }
  const program = ts.createProgram({
    rootNames: args.language === "javascript" ? config.fileNames : [...new Set([...config.fileNames, ...targetFiles])],
    options: config.options,
    projectReferences: config.projectReferences,
  });
  const syntaxDiagnostics = program.getSyntacticDiagnostics().filter((diagnostic) => {
    if (!diagnostic.file) return false;
    const source = path.resolve(diagnostic.file.fileName);
    return isWithin(projectRoot, source) && !exclusions.isExcluded(source) && isSourcePath(source, args.language);
  });
  if (syntaxDiagnostics.length > 0) fail(`${args.language === "javascript" ? "JavaScript" : "TypeScript"} syntax errors: ${diagnosticText(ts, syntaxDiagnostics[0])}`);
  const targetSources = coveredTargetFiles.map((file) => program.getSourceFile(file)).filter(Boolean);
  const unresolved = unresolvedModules(ts, targetSources, config, projectRoot);
  const facts = addCallFacts(coveredTargetFiles, program, projectRoot, exclusions, ts, args.language);
  const thresholds = {
    minCallsites: args.minCallsites,
    majorityFrac: args.majorityFrac,
    minPresent: args.minPresent,
  };
  const candidates = candidateRows(facts.supported, thresholds, trajectoryGate(projectRoot, args.noGate));
  const deferred = [
    ...deferredRows(facts.deferredGroups, thresholds),
    ...facts.unresolvedCalls,
    ...candidates.unresolvedSpreads,
  ].sort((left, right) => left.file.localeCompare(right.file) || left.line - right.line || left.reason.localeCompare(right.reason));
  const targetExcluded = targetFiles.length === 0 && exclusions.isExcluded(target, targetStats.isDirectory());
  const semanticDiagnostics = args.language === "javascript"
    ? program.getSemanticDiagnostics().filter((diagnostic) => diagnostic.file && coveredTargetFiles.includes(path.resolve(diagnostic.file.fileName)))
    : [];
  const partial = unresolved.length > 0 || facts.unresolvedCalls.length > 0 || candidates.unresolvedSpreads.length > 0 || uncoveredFiles.length > 0 || semanticDiagnostics.length > 0;
  const payload = {
    schema_version: 1,
    band: `${args.language}-option-omission`,
    language: args.language,
    analyzer: args.language === "javascript" ? "typescript-compiler-api-checked-javascript" : "typescript-compiler-api",
    status: partial ? "partial" : "complete",
    project_root: projectRoot,
    target: {
      path: relativePath(projectRoot, target),
      kind: targetStats.isDirectory() ? "directory" : "file",
      exclusion: targetExcluded ? "excluded" : "included",
    },
    tsconfig: relativePath(projectRoot, config.path),
    ...(args.language === "javascript" ? {
      config: relativePath(projectRoot, config.path),
      diagnostics: semanticDiagnostics.map((diagnostic) => diagnosticText(ts, diagnostic)),
      uncovered_files: uncoveredFiles,
      semantic_evidence: {
        checked_javascript: true,
        jsdoc: { declarations: targetSources.reduce((count, source) => count + (source.text.match(/\/\*\*/g)?.length ?? 0), 0) },
        compiler_inferred: {
          resolved_direct_calls: [...facts.supported.values()].reduce((count, group) => count + group.calls.length, 0),
        },
      },
    } : {}),
    project_resolution: {
      state: partial ? "partial" : "complete",
      unresolved_modules: unresolved,
    },
    scope: {
      supported: args.language === "javascript"
        ? "Checked JavaScript TypeChecker-resolved direct calls to project functions with explicit object-option property presence."
        : "Resolved calls to project function declarations with object-option property presence.",
      deferred: "Method/framework APIs, dynamic receivers, unresolved spreads, runtime dispatch, and framework semantics.",
    },
    findings: candidates.findings.sort((left, right) => left.straggler.localeCompare(right.straggler)),
    down_ranked: candidates.downRanked.sort((left, right) => left.callee.localeCompare(right.callee) || left.kwarg.localeCompare(right.kwarg)),
    gated_out: candidates.gatedOut.sort((left, right) => left.straggler.localeCompare(right.straggler)),
    deferred,
    summary: {
      raw_divergence_candidates: candidates.findings.length + candidates.downRanked.length + candidates.gatedOut.length,
      gated_in: candidates.findings.length,
      down_ranked: candidates.downRanked.length,
      gated_out: candidates.gatedOut.length,
      deferred: deferred.length,
    },
  };
  writeAtomically(path.join(reportDir, "manifest.json"), `${JSON.stringify(payload, null, 2)}\n`);
  writeAtomically(path.join(reportDir, "findings.md"), renderFindings(payload));
  console.error(
    `[find-incomplete-sweep-${args.language}] wrote ${reportDir} `
    + `(gated_in=${payload.summary.gated_in} raw=${payload.summary.raw_divergence_candidates} status=${payload.status})`,
  );
}

try {
  main();
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[find-incomplete-sweep] ERROR: ${message}`);
  process.exitCode = 2;
}
