#!/usr/bin/env python3
"""Detect omnibus modules — files that answer questions from 3+ domains.

The detector groups trustworthy top-level symbols into head-noun clusters. A
file becomes a candidate when four clusters contain at least two symbols each
(an SRP ``and_count`` of at least three). Extraction is deliberately local to
this skill so a copied installation has its complete runtime closure:

* Python uses the stdlib ``ast`` module, including the existing god-class
  method expansion.
* JavaScript, JSX, TypeScript, and TSX use the host project's pinned TypeScript Compiler API
  through the bundled ``detect_typescript_symbols.mjs`` launcher. It reports
  exact top-level spans for functions, function-valued variables, and classes.
* Go uses the host's Go 1.22+ standard-library parser through the bundled
  ``detect_go_symbols.go`` launcher. Build-constrained files are refused rather
  than silently treated as analyzed.
* Java uses the public JDK 17+ compiler tree API through the bundled
  ``detect_java_symbols.java`` launcher. It reports direct methods and
  constructors of named top-level types only.
* Swift uses successful Swift 6+ compiler typechecking and the compiler's
  textual ``-dump-ast`` output through ``detect_swift_symbols.py``. It does
  not claim SwiftSyntax, resolved references, or complete project semantics.

The script-family path is syntax-only: TypeScript needs Node and a
``typescript`` package resolvable from ``--project-root``; Java needs JDK 17+
on ``PATH``. Neither path needs a tsconfig, type checker, module resolution,
framework model, or semantic responsibility claims.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


class Symbol:
    """A top-level symbol and its source span."""

    __slots__ = ("name", "cluster_name", "kind", "lineno", "end_lineno", "loc")

    def __init__(
        self,
        name: str,
        cluster_name: str,
        kind: str,
        lineno: int,
        end_lineno: int,
        loc: int,
    ) -> None:
        self.name = name
        self.cluster_name = cluster_name
        self.kind = kind
        self.lineno = lineno
        self.end_lineno = end_lineno
        self.loc = loc


class TypeScriptExtractionError(RuntimeError):
    """Raised when the bundled TypeScript parser cannot establish facts."""


class GoExtractionError(RuntimeError):
    """Raised when the bundled Go parser cannot establish facts honestly."""


class JavaExtractionError(RuntimeError):
    """Raised when the bundled Java parser cannot establish facts honestly."""


class SwiftExtractionError(RuntimeError):
    """Raised when the bundled Swift compiler helper emits invalid evidence."""


_LANGUAGES: tuple[str, ...] = ("go", "java", "javascript", "python", "swift", "typescript")
_LANGUAGE_EXTENSIONS: dict[str, frozenset[str]] = {
    "go": frozenset({".go"}),
    "java": frozenset({".java"}),
    "python": frozenset({".py"}),
    "swift": frozenset({".swift"}),
    "javascript": frozenset({".js", ".jsx", ".mjs", ".cjs"}),
    "typescript": frozenset({".ts", ".tsx"}),
}
_DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    "migrations", "__pycache__", "staticfiles", "node_modules", ".git",
    ".venv", "venv", "dist", "build",
})
_TYPESCRIPT_SKIP_DIRS: frozenset[str] = frozenset({
    "__tests__", "fixtures", "generated", "test", "tests", "vendor",
})
_GO_SKIP_DIRS: frozenset[str] = frozenset({
    "fixture", "fixtures", "gen", "generated", "test", "testdata", "tests", "vendor",
})
_GO_SKIP_FILE_GLOBS: tuple[str, ...] = ("*_test.go", "*.generated.go", "*_generated.go")
_GO_MIN_VERSION = (1, 22, 0)
_JAVA_SKIP_DIRS: frozenset[str] = frozenset({
    ".gradle", "build", "coverage", "dist", "fixture", "fixtures", "generated",
    "integrationtest", "out", "reports", "target", "test", "testdata",
    "testfixtures", "tests", "vendor",
})
_JAVA_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "*test.java", "*tests.java", "*it.java", "*generated.java",
    "*.generated.java", "*_generated.java",
)
_JAVA_MIN_VERSION = (17, 0, 0)
_SWIFT_SKIP_DIRS: frozenset[str] = frozenset({
    ".build", "deriveddata", "fixture", "fixtures", "generated", "reports",
    "test", "tests", "vendor",
})
_SWIFT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "*test.swift", "*tests.swift", "*generated.swift", "*.generated.swift",
    "*_generated.swift",
)
_SWIFT_MIN_VERSION = (6, 0, 0)
_DEFAULT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "tests_*.py", "test_*.py", "tests.py", "conftest.py", "__init__.py",
    "*.min.js", "*.min.jsx", "*.min.mjs", "*.min.cjs", "*.min.css",
    "*-min.js", "*-min.jsx", "*-min.mjs", "*-min.cjs",
    "*.bundle.js", "*.bundle.jsx", "*.bundle.mjs", "*.bundle.cjs",
    "*.test.js", "*.test.jsx", "*.test.mjs", "*.test.cjs",
    "*.spec.js", "*.spec.jsx", "*.spec.mjs", "*.spec.cjs",
    "*.d.ts", "*.d.tsx", "*.min.ts", "*.min.tsx", "*-min.ts",
    "*-min.tsx", "*.bundle.ts", "*.bundle.tsx", "*.generated.ts",
    "*.generated.tsx", "*.test.ts", "*.test.tsx", "*.spec.ts",
    "*.spec.tsx", "test_*.ts", "test_*.tsx", "tests_*.ts", "tests_*.tsx",
    "*_test.ts", "*_test.tsx",
)
_DEFAULT_SKIP_PATH_GLOBS: tuple[str, ...] = ("sites/*/scrape.py",)

_STRIP_TOKENS: frozenset[str] = frozenset({
    "bulk", "get", "list", "create", "update", "delete", "remove",
    "fetch", "load", "save", "handle", "process", "check", "validate",
    "build", "make", "run", "do", "set", "put", "patch", "post",
    "start", "stop", "cancel", "retry", "reset", "clear", "apply",
    "ensure", "try", "find", "search", "sync", "refresh", "render",
    "init", "setup", "is", "has", "can", "should", "was", "were",
    "show", "hide", "open", "close", "toggle", "display", "select",
    "initialize", "wire", "populate", "task", "view", "service", "helper",
    "util", "utils", "client", "manager", "factory", "handler", "worker",
    "callback", "hook", "page", "all", "one", "api", "v1", "v2", "data",
    "row", "rows", "config", "with", "for", "to", "from", "by", "or", "and",
})
_RISK_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("credentials", ("credential", "credentials", "password", "secret", "token", "api_key", "apikey")),
    ("admin_auth", ("admin", "staff", "csrf", "auth", "permission", "login")),
    ("raw_sql", ("raw sql", "cursor", "execute(", "mysql", "sql")),
    ("command_execution", ("subprocess", "shell", "command", "curl", "popen", "system(")),
    ("network_diagnostics", ("proxy", "email", "smtp", "recaptcha", "external_source", "requests.", "httpx", "urllib", "scraperapi", "whi")),
    ("persistence", (".save(", ".create(", ".update(", ".delete(", "bulk_create", "bulk_update")),
    ("filesystem", ("open(", "write(", "read_text", "write_text", "pathlib", "os.path")),
    ("task_dispatch", (".delay(", ".apply_async(", "safe_dispatch", "celery", "task")),
    ("import_export", ("export", "csv", "excel", "xlsx", "workbook")),
)
_CAMEL_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _node_loc(node: ast.AST) -> int:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None) or start
    return max(1, end - start + 1) if start is not None and end is not None else 0


def _python_symbols(source: str) -> list[Symbol] | None:
    """Preserve the pre-TypeScript Python AST extractor exactly."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    symbols: list[Symbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _is_dunder(node.name):
                symbols.append(Symbol(
                    node.name, node.name,
                    "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                    node.lineno, node.end_lineno or node.lineno, _node_loc(node),
                ))
        elif isinstance(node, ast.ClassDef) and not _is_dunder(node.name):
            methods = [
                method for method in node.body
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not _is_dunder(method.name)
            ]
            if len(methods) >= 3:
                for method in methods:
                    symbols.append(Symbol(
                        f"{node.name}.{method.name}", method.name,
                        "async_method" if isinstance(method, ast.AsyncFunctionDef) else "method",
                        method.lineno, method.end_lineno or method.lineno,
                        _node_loc(method),
                    ))
            else:
                symbols.append(Symbol(
                    node.name, node.name, "class", node.lineno,
                    node.end_lineno or node.lineno, _node_loc(node),
                ))
    return symbols


def _typescript_symbols(filepath: Path, project_root: Path) -> list[Symbol]:
    launcher = Path(__file__).resolve().with_name("detect_typescript_symbols.mjs")
    try:
        result = subprocess.run(
            ["node", str(launcher), "--file", str(filepath), "--project-root", str(project_root)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise TypeScriptExtractionError(f"cannot run bundled TypeScript parser: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown parser failure"
        raise TypeScriptExtractionError(detail)
    try:
        records = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise TypeScriptExtractionError("bundled TypeScript parser emitted invalid JSON") from exc
    if not isinstance(records, list):
        raise TypeScriptExtractionError("bundled TypeScript parser emitted a non-list result")
    try:
        return [
            Symbol(
                str(record["name"]), str(record["cluster_name"]), str(record["kind"]),
                int(record["lineno"]), int(record["end_lineno"]), int(record["loc"]),
            )
            for record in records
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise TypeScriptExtractionError("bundled TypeScript parser emitted an invalid symbol") from exc


def _go_toolchain() -> str:
    executable = shutil.which("go")
    if executable is None:
        raise GoExtractionError("Go toolchain is unavailable on PATH")
    try:
        result = subprocess.run(
            [executable, "version"], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise GoExtractionError(f"cannot run Go toolchain: {exc}") from exc
    rendered = (result.stdout or result.stderr).strip()
    match = re.search(r"\bgo(\d+)\.(\d+)(?:\.(\d+))?\b", rendered)
    if result.returncode != 0 or match is None:
        raise GoExtractionError(f"cannot determine Go version: {rendered or 'unknown error'}")
    version = tuple(int(part or 0) for part in match.groups())
    if version < _GO_MIN_VERSION:
        raise GoExtractionError(
            "Go parser requires Go >= 1.22.0; found go" + ".".join(map(str, version))
        )
    return executable


def _go_symbols(filepaths: list[Path]) -> dict[Path, list[Symbol]]:
    """Extract every eligible Go file through one compiler-driver launch."""
    executable = _go_toolchain()
    launcher = Path(__file__).resolve().with_name("detect_go_symbols.go")
    try:
        result = subprocess.run(
            [executable, "run", str(launcher), "--", *(str(path) for path in filepaths)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GoExtractionError(f"cannot run bundled Go parser: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown parser failure"
        raise GoExtractionError(detail)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GoExtractionError("bundled Go parser emitted invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise GoExtractionError("bundled Go parser emitted an invalid payload")
    if payload.get("analyzer") != "go-parser-go-ast" or not isinstance(payload.get("files"), list):
        raise GoExtractionError("bundled Go parser emitted invalid symbol evidence")
    requested = {path.resolve() for path in filepaths}
    extracted: dict[Path, list[Symbol]] = {}
    for file_payload in payload["files"]:
        try:
            path = Path(file_payload["file"]).resolve()
            status = file_payload["status"]
            records = file_payload["symbols"]
        except (KeyError, TypeError) as exc:
            raise GoExtractionError("bundled Go parser emitted invalid file evidence") from exc
        if path not in requested or path in extracted or not isinstance(records, list):
            raise GoExtractionError("bundled Go parser emitted mismatched file evidence")
        if status == "syntax-error":
            raise GoExtractionError(
                f"syntax error in {path}: {file_payload.get('error') or 'unknown parse error'}"
            )
        if status == "build-constraint-unsupported":
            raise GoExtractionError(f"build-constrained Go source is unsupported in v1: {path}")
        if status not in {"complete", "generated"}:
            raise GoExtractionError("bundled Go parser emitted an invalid status")
        try:
            extracted[path] = [
                Symbol(
                    str(record["name"]), str(record["cluster_name"]), str(record["kind"]),
                    int(record["lineno"]), int(record["end_lineno"]), int(record["loc"]),
                )
                for record in records
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise GoExtractionError("bundled Go parser emitted an invalid symbol") from exc
    if set(extracted) != requested:
        raise GoExtractionError("bundled Go parser omitted requested file evidence")
    return extracted


def _parse_java_version(rendered: str, tool: str) -> tuple[int, int, int]:
    """Parse a tool's own version line while ignoring startup warnings."""
    pattern = (
        re.compile(r'\bversion\s+"(\d+)(?:\.(\d+))?(?:\.(\d+))?')
        if tool == "java"
        else re.compile(r"\bjavac\s+(\d+)(?:\.(\d+))?(?:\.(\d+))?\b")
    )
    for line in rendered.splitlines():
        match = pattern.search(line.strip())
        if match is None:
            continue
        major, minor, patch = (int(part or 0) for part in match.groups())
        if major == 1 and minor:
            major, minor, patch = minor, patch, 0
        return major, minor, patch
    raise JavaExtractionError(
        f"cannot parse {tool} version: {rendered.strip() or 'unknown version'}"
    )


def _java_toolchain() -> tuple[str, str, tuple[int, int, int], tuple[int, int, int]]:
    """Resolve a complete JDK 17+ without requiring Maven or Gradle."""
    java = shutil.which("java")
    javac = shutil.which("javac")
    missing = [name for name, executable in (("java", java), ("javac", javac)) if executable is None]
    if missing:
        raise JavaExtractionError(
            "Java JDK is unavailable on PATH (missing " + ", ".join(missing) + ")"
        )
    assert java is not None and javac is not None
    versions: dict[str, tuple[int, int, int]] = {}
    for tool, executable in (("java", java), ("javac", javac)):
        try:
            result = subprocess.run(
                [executable, "-version"], capture_output=True, text=True, check=False
            )
        except OSError as exc:
            raise JavaExtractionError(f"cannot run {tool}: {exc}") from exc
        rendered = "\n".join(part for part in (result.stdout, result.stderr) if part)
        if result.returncode:
            raise JavaExtractionError(
                f"cannot determine {tool} version: {rendered.strip() or f'exit {result.returncode}'}"
            )
        version = _parse_java_version(rendered, tool)
        if version < _JAVA_MIN_VERSION:
            raise JavaExtractionError(
                "Java parser requires JDK >= "
                + ".".join(map(str, _JAVA_MIN_VERSION))
                + f"; found {tool} "
                + ".".join(map(str, version))
            )
        versions[tool] = version
    return java, javac, versions["java"], versions["javac"]


def _java_symbols(
    filepaths: list[Path], project_root: Path
) -> tuple[dict[Path, list[Symbol]], dict[str, object], set[Path]]:
    """Extract eligible Java symbols through one JDK source-launcher run."""
    java, _javac, java_version, javac_version = _java_toolchain()
    launcher = Path(__file__).resolve().with_name("detect_java_symbols.java")
    command = [java, str(launcher), "--project-root", str(project_root)]
    for path in filepaths:
        command.extend(("--file", str(path)))
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise JavaExtractionError(f"cannot run bundled Java parser: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown parser failure"
        raise JavaExtractionError(detail)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise JavaExtractionError("bundled Java parser emitted invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise JavaExtractionError("bundled Java parser emitted an invalid payload")
    if payload.get("analyzer") != "jdk-compiler-tree-api" or not isinstance(payload.get("files"), list):
        raise JavaExtractionError("bundled Java parser emitted invalid symbol evidence")
    requested = {path.resolve() for path in filepaths}
    extracted: dict[Path, list[Symbol]] = {}
    generated: set[Path] = set()
    for file_payload in payload["files"]:
        try:
            rendered_path = file_payload["file"]
            status = file_payload["status"]
            records = file_payload["symbols"]
        except (KeyError, TypeError) as exc:
            raise JavaExtractionError("bundled Java parser emitted invalid file evidence") from exc
        if not isinstance(rendered_path, str):
            raise JavaExtractionError("bundled Java parser emitted invalid file evidence")
        candidate = Path(rendered_path)
        path = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
        if path not in requested or path in extracted or not isinstance(records, list):
            raise JavaExtractionError("bundled Java parser emitted mismatched file evidence")
        if status == "syntax-error":
            raise JavaExtractionError(
                f"syntax error in {path}: {file_payload.get('error') or 'unknown parse error'}"
            )
        if status == "read-error":
            raise JavaExtractionError(
                f"cannot read Java source {path}: {file_payload.get('error') or 'unknown read error'}"
            )
        if status not in {"complete", "generated"}:
            raise JavaExtractionError("bundled Java parser emitted an invalid status")
        if status == "generated":
            generated.add(path)
        try:
            extracted[path] = [
                Symbol(
                    str(record["name"]), str(record["cluster_name"]), str(record["kind"]),
                    int(record["lineno"]), int(record["end_lineno"]), int(record["loc"]),
                )
                for record in records
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise JavaExtractionError("bundled Java parser emitted an invalid symbol") from exc
    if set(extracted) != requested:
        raise JavaExtractionError("bundled Java parser omitted requested file evidence")
    return extracted, {
        "analyzer": "jdk-compiler-tree-api",
        "minimum_jdk_version": ".".join(map(str, _JAVA_MIN_VERSION)),
        "actual_java_version": ".".join(map(str, java_version)),
        "actual_javac_version": ".".join(map(str, javac_version)),
    }, generated


def _swift_symbols(
    filepaths: list[Path], project_root: Path
) -> tuple[dict[Path, list[Symbol]], dict[str, object]]:
    """Extract bounded declarations through the copied Swift compiler helper."""
    launcher = Path(__file__).resolve().with_name("detect_swift_symbols.py")
    command = [sys.executable, "-I", "-S", str(launcher)]
    for path in filepaths:
        command.extend(("--file", str(path)))
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SwiftExtractionError(f"cannot run bundled Swift compiler helper: {exc}") from exc
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        detail = result.stderr.strip() or result.stdout.strip() or "invalid JSON"
        raise SwiftExtractionError(f"bundled Swift compiler helper failed: {detail}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise SwiftExtractionError("bundled Swift compiler helper emitted an invalid payload")
    if payload.get("analyzer") != "swiftc-typecheck-dump-ast":
        raise SwiftExtractionError("bundled Swift compiler helper emitted invalid provenance")
    status = payload.get("status")
    if status not in {"complete", "partial", "unsupported", "failed"}:
        raise SwiftExtractionError("bundled Swift compiler helper emitted an invalid status")
    if status in {"unsupported", "failed"}:
        return {}, payload
    rows = payload.get("files")
    if not isinstance(rows, list):
        raise SwiftExtractionError("bundled Swift compiler helper omitted file evidence")
    requested = {path.resolve() for path in filepaths}
    extracted: dict[Path, list[Symbol]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("file"), str):
            raise SwiftExtractionError("bundled Swift compiler helper emitted invalid file evidence")
        path = Path(row["file"]).resolve()
        if path not in requested or path in extracted:
            raise SwiftExtractionError("bundled Swift compiler helper emitted mismatched file evidence")
        row_status = row.get("status")
        records = row.get("symbols")
        if row_status == "partial":
            if records != []:
                raise SwiftExtractionError("partial Swift evidence may not contain symbols")
            extracted[path] = []
            continue
        if row_status != "complete" or not isinstance(records, list):
            raise SwiftExtractionError("bundled Swift compiler helper emitted invalid symbol evidence")
        try:
            extracted[path] = [
                Symbol(
                    str(record["name"]), str(record["cluster_name"]), str(record["kind"]),
                    int(record["lineno"]), int(record["end_lineno"]), int(record["loc"]),
                )
                for record in records
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise SwiftExtractionError("bundled Swift compiler helper emitted an invalid symbol") from exc
    if set(extracted) != requested:
        raise SwiftExtractionError("bundled Swift compiler helper omitted requested file evidence")
    return extracted, payload


def _language_for(path: Path) -> str | None:
    suffix = path.suffix.lower()
    for language, extensions in _LANGUAGE_EXTENSIONS.items():
        if suffix in extensions:
            return language
    return None


def _typescript_path_is_excluded(path: Path, target: Path) -> bool:
    try:
        parts = path.relative_to(target).parts
    except ValueError:
        parts = path.parts
    return any(part.lower() in _TYPESCRIPT_SKIP_DIRS for part in parts[:-1])


def _go_path_is_excluded(path: Path, project_root: Path) -> bool:
    try:
        logical = path.relative_to(project_root).parts
        physical = path.resolve().relative_to(project_root).parts
    except ValueError:
        return True
    return (
        any(part.lower() in _GO_SKIP_DIRS for part in logical[:-1])
        or any(part.lower() in _GO_SKIP_DIRS for part in physical[:-1])
        or any(fnmatch.fnmatchcase(path.name.lower(), glob) for glob in _GO_SKIP_FILE_GLOBS)
    )


def _java_exclusion_reason(path: Path, project_root: Path) -> str | None:
    """Name why a Java path is outside the first-party source boundary."""
    try:
        logical = path.relative_to(project_root).parts
        physical = path.resolve().relative_to(project_root).parts
    except ValueError:
        return "outside-project-root"
    if any(part.lower() in _DEFAULT_SKIP_DIRS for part in logical[:-1]):
        return "default-skip-tree"
    if any(part.lower() in _JAVA_SKIP_DIRS for part in logical[:-1]):
        return "java-skip-tree"
    if any(part.lower() in _JAVA_SKIP_DIRS for part in physical[:-1]):
        return "java-skip-tree"
    if any(fnmatch.fnmatchcase(path.name.lower(), glob) for glob in _JAVA_SKIP_FILE_GLOBS):
        return "java-skip-file"
    return None


def _java_path_is_excluded(path: Path, project_root: Path) -> bool:
    """Apply Java's first-party source policy against logical and physical paths."""
    return _java_exclusion_reason(path, project_root) is not None


def _swift_exclusion_reason(path: Path, project_root: Path) -> str | None:
    """Name Swift files outside the bounded first-party SwiftPM source set."""
    if path.is_symlink():
        return "symlink"
    try:
        logical = path.relative_to(project_root).parts
        physical = path.resolve().relative_to(project_root).parts
    except ValueError:
        return "outside-project-root"
    if any(part.lower() in _DEFAULT_SKIP_DIRS for part in logical[:-1]):
        return "default-skip-tree"
    if any(part.lower() in _SWIFT_SKIP_DIRS for part in logical[:-1]):
        return "swift-skip-tree"
    if any(part.lower() in _SWIFT_SKIP_DIRS for part in physical[:-1]):
        return "swift-skip-tree"
    if any(fnmatch.fnmatchcase(path.name.lower(), glob) for glob in _SWIFT_SKIP_FILE_GLOBS):
        return "swift-skip-file"
    return None


def _swift_path_is_excluded(path: Path, project_root: Path) -> bool:
    return _swift_exclusion_reason(path, project_root) is not None


def _java_inventory(
    target: Path,
    project_root: Path,
    skip_file_globs: tuple[str, ...],
    skip_path_globs: tuple[str, ...],
) -> tuple[list[dict[str, str]], list[Path]]:
    """Inventory every Java file before deciding whether zero candidates are clean."""
    inventory: list[dict[str, str]] = []
    eligible: list[Path] = []
    for path in sorted(target.rglob("*")):
        if path.suffix.lower() != ".java" or not path.is_file():
            continue
        try:
            rel = path.relative_to(project_root).as_posix()
        except ValueError:
            rel = path.as_posix()
        reason = _java_exclusion_reason(path, project_root)
        if reason is None and any(fnmatch.fnmatchcase(path.name, glob) for glob in skip_file_globs):
            reason = "declared-skip-file"
        if reason is None and any(fnmatch.fnmatchcase(rel, glob) for glob in skip_path_globs):
            reason = "declared-skip-path"
        if reason is not None:
            inventory.append({"file": rel, "role": "excluded", "reason": reason})
            continue
        inventory.append({"file": rel, "role": "eligible"})
        eligible.append(path)
    return inventory, eligible


def _swift_inventory(
    target: Path,
    project_root: Path,
    skip_file_globs: tuple[str, ...],
    skip_path_globs: tuple[str, ...],
) -> tuple[list[dict[str, str]], list[Path]]:
    """Inventory Swift source roles before deciding completeness or cleanliness."""
    inventory: list[dict[str, str]] = []
    eligible: list[Path] = []
    for path in sorted(target.rglob("*")):
        if path.suffix.lower() != ".swift" or not path.is_file():
            continue
        try:
            rel = path.relative_to(project_root).as_posix()
        except ValueError:
            rel = path.as_posix()
        reason = _swift_exclusion_reason(path, project_root)
        if reason is None and any(fnmatch.fnmatchcase(path.name, glob) for glob in skip_file_globs):
            reason = "declared-skip-file"
        if reason is None and any(fnmatch.fnmatchcase(rel, glob) for glob in skip_path_globs):
            reason = "declared-skip-path"
        if reason is not None:
            inventory.append({"file": rel, "role": "excluded", "reason": reason})
            continue
        inventory.append({"file": rel, "role": "eligible"})
        eligible.append(path)
    return inventory, eligible


def _java_scan_payload(
    inventory: list[dict[str, str]], provenance: dict[str, object] | None
) -> dict[str, object]:
    """Carry Java detector completeness and parser provenance to the final report."""
    summary = {
        "discovered": len(inventory),
        "eligible": sum(row["role"] == "eligible" for row in inventory),
        "excluded": sum(row["role"] == "excluded" for row in inventory),
    }
    return {
        "status": "complete",
        "language": "java",
        "analyzer": "jdk-compiler-tree-api",
        "minimum_jdk_version": ".".join(map(str, _JAVA_MIN_VERSION)),
        "actual_java_version": (
            provenance["actual_java_version"] if provenance is not None else None
        ),
        "actual_javac_version": (
            provenance["actual_javac_version"] if provenance is not None else None
        ),
        "inventory": inventory,
        "summary": summary,
    }


def _swift_scan_payload(
    inventory: list[dict[str, str]],
    provenance: dict[str, object] | None,
    project_root: Path,
) -> dict[str, object]:
    """Carry Swift completeness, compiler provenance, and bounded fact claims."""
    summary = {
        "discovered": len(inventory),
        "eligible": sum(row["role"] == "eligible" for row in inventory),
        "excluded": sum(row["role"] == "excluded" for row in inventory),
        "analyzed": 0,
        "incomplete": 0,
    }
    payload: dict[str, object] = {
        "status": "complete",
        "language": "swift",
        "analyzer": "swiftc-typecheck-dump-ast",
        "minimum_swift_version": ".".join(map(str, _SWIFT_MIN_VERSION)),
        "actual_swift_version": None,
        "claim_boundary": {
            "swift_syntax": False,
            "resolved_references": False,
            "complete_project_semantics": False,
        },
        "inventory": inventory,
        "source_fingerprints": {},
        "declarations": [],
        "summary": summary,
    }
    if provenance is None:
        return payload
    for key in ("status", "failure_kind", "message", "actual_swift_version", "claim_boundary"):
        if key in provenance and provenance[key] is not None:
            payload[key] = provenance[key]
    files = provenance.get("files")
    if isinstance(files, list):
        fingerprints: dict[str, str] = {}
        declarations: list[dict[str, object]] = []
        for row in files:
            if not isinstance(row, dict) or not isinstance(row.get("file"), str):
                continue
            path = Path(row["file"])
            try:
                rel = path.resolve().relative_to(project_root).as_posix()
            except ValueError:
                rel = str(path)
            if isinstance(row.get("source_sha256"), str):
                fingerprints[rel] = row["source_sha256"]
            if row.get("status") == "complete":
                summary["analyzed"] += 1
            else:
                summary["incomplete"] += 1
            raw_declarations = row.get("declarations")
            if isinstance(raw_declarations, list):
                declarations.extend({"file": rel, **record} for record in raw_declarations if isinstance(record, dict))
        payload["source_fingerprints"] = dict(sorted(fingerprints.items()))
        payload["declarations"] = declarations
    return payload


def _remove_output_artifact(path: Path) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _invalidate_pipeline_artifacts(output: Path) -> None:
    """Remove every generated artifact that could make a failed rerun look clean."""
    for artifact in (
        output,
        output.with_name("scan.json"),
        output.with_name("candidates.jsonl"),
        output.with_name("report.md"),
        output.with_name("findings.json"),
        output.with_name("scout"),
    ):
        _remove_output_artifact(artifact)


def _write_jsonl(records: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def _write_java_scan(scan: dict[str, object], output: Path) -> None:
    output.with_name("scan.json").write_text(
        json.dumps(scan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_scan(scan: dict[str, object], output: Path) -> None:
    output.with_name("scan.json").write_text(
        json.dumps(scan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _first_kotlin_source(target: Path, project_root: Path) -> Path | None:
    """Surface Kotlin explicitly for a Java-only scan rather than omitting it."""
    for path in sorted(target.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".kt", ".kts"}:
            continue
        if not _java_path_is_excluded(path, project_root):
            return path
    return None


def _walk_source_files(
    target: Path,
    skip_file_globs: tuple[str, ...],
    skip_path_globs: tuple[str, ...],
    project_root: Path,
    extensions: frozenset[str],
) -> list[Path]:
    files: list[Path] = []
    for path in sorted(target.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if any(part in _DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in _LANGUAGE_EXTENSIONS["typescript"] and _typescript_path_is_excluded(path, target):
            continue
        if path.suffix.lower() == ".go" and _go_path_is_excluded(path, project_root):
            continue
        if path.suffix.lower() == ".java" and _java_path_is_excluded(path, project_root):
            continue
        if path.suffix.lower() == ".swift" and _swift_path_is_excluded(path, project_root):
            continue
        if any(fnmatch.fnmatchcase(path.name, glob) for glob in skip_file_globs):
            continue
        try:
            rel = path.relative_to(project_root).as_posix()
        except ValueError:
            rel = path.as_posix()
        if any(fnmatch.fnmatchcase(rel, glob) for glob in skip_path_globs):
            continue
        files.append(path)
    return files


def _tokenize(name: str) -> list[str]:
    tokens: list[str] = []
    for segment in name.split("_"):
        tokens.extend(piece.lower() for piece in _CAMEL_SPLIT.split(segment) if piece)
    return tokens


def _cluster_key(name: str) -> str:
    if name.startswith("_"):
        name = name.lstrip("_") or name
    for token in _tokenize(name):
        if token not in _STRIP_TOKENS:
            return token
    return "_unclassified"


def _risk_signals(rel: str, source: str, symbol_names: list[str]) -> tuple[int, list[str]]:
    haystack = "\n".join([rel, *symbol_names, source]).lower()
    signals = [label for label, terms in _RISK_TERMS if any(term in haystack for term in terms)]
    return len(signals), signals


def _scan_file(
    filepath: Path,
    rel: str,
    project_root: Path,
    go_symbols: dict[Path, list[Symbol]],
    java_symbols: dict[Path, list[Symbol]],
    swift_symbols: dict[Path, list[Symbol]],
) -> dict[str, object] | None:
    language = _language_for(filepath)
    if language is None:
        return None
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        if language == "java":
            raise JavaExtractionError(f"cannot read Java source {filepath}: {exc}") from exc
        return None
    if language == "python":
        extracted = _python_symbols(source)
        analyzer = "python-ast"
    elif language == "go":
        extracted = go_symbols[filepath.resolve()]
        analyzer = "go-parser-go-ast"
    elif language == "java":
        extracted = java_symbols[filepath.resolve()]
        analyzer = "jdk-compiler-tree-api"
    elif language == "swift":
        extracted = swift_symbols[filepath.resolve()]
        analyzer = "swiftc-typecheck-dump-ast"
    else:
        extracted = _typescript_symbols(filepath, project_root)
        analyzer = "typescript-compiler-api"
    if extracted is None:
        return None

    file_loc = len(source.splitlines())
    clusters: dict[str, dict[str, object]] = {}
    symbol_names: list[str] = []
    for symbol in extracted:
        symbol_names.append(symbol.name)
        cluster = clusters.setdefault(_cluster_key(symbol.cluster_name), {"symbols": [], "loc": 0})
        cluster["symbols"].append(symbol.name)  # type: ignore[union-attr]
        cluster["loc"] = int(cluster["loc"]) + symbol.loc

    genuine = [
        (name, data) for name, data in clusters.items()
        if name != "_unclassified" and len(data["symbols"]) >= 2  # type: ignore[arg-type]
    ]
    and_count = max(0, len(genuine) - 1)
    if and_count < 3:
        return None
    ordered_clusters = sorted(
        (
            {"name": name, "symbols": sorted(data["symbols"]), "loc": int(data["loc"])}
            for name, data in genuine
        ),
        key=lambda cluster: (-int(cluster["loc"]), str(cluster["name"])),
    )
    names = [str(cluster["name"]) for cluster in ordered_clusters]
    risk_score, risk_signals = _risk_signals(rel, source, symbol_names)
    return {
        "type": "omnibus",
        "file": rel,
        "language": language,
        "analyzer": analyzer,
        "loc": file_loc,
        "cluster_count": len(ordered_clusters),
        "and_count": and_count,
        "risk_score": risk_score,
        "risk_signals": risk_signals,
        "score": and_count * 1000 + risk_score * 250 + file_loc,
        "clusters": ordered_clusters,
        "srp_sentence": f"This file handles {' and '.join(names)}.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path, help="Directory to scan")
    parser.add_argument("--project-root", required=True, type=Path, help="Project root for output and TypeScript resolution")
    parser.add_argument("--output", required=True, type=Path, help="Output JSONL file")
    parser.add_argument("--skip-file-glob", action="append", default=[], help="Extra file-name globs to skip")
    parser.add_argument("--skip-path-glob", action="append", default=[], help="Extra relative-path globs to skip")
    parser.add_argument("--language", action="append", default=[], choices=list(_LANGUAGES), help="Restrict to these languages")
    args = parser.parse_args(argv)
    _invalidate_pipeline_artifacts(args.output)
    wanted = set(args.language) or set(_LANGUAGES)
    java_mode = bool(args.language) and wanted == {"java"}
    swift_mode = bool(args.language) and wanted == {"swift"}
    if "swift" in wanted and len(wanted) > 1 and args.language:
        print(
            "[detect_omnibus] ERROR: Swift compiler analysis must be selected alone in v1",
            file=sys.stderr,
        )
        return 2
    if not args.target.is_dir():
        print(f"[detect_omnibus] ERROR: {args.target} is not a directory", file=sys.stderr)
        return 2
    project_root = args.project_root.resolve()
    target = args.target.resolve()
    skip_file_globs = _DEFAULT_SKIP_FILE_GLOBS + tuple(args.skip_file_glob)
    skip_path_globs = _DEFAULT_SKIP_PATH_GLOBS + tuple(args.skip_path_glob)
    java_inventory: list[dict[str, str]] = []
    java_scan: dict[str, object] | None = None
    swift_inventory: list[dict[str, str]] = []
    swift_scan: dict[str, object] | None = None
    java_files: list[Path] = []
    swift_files: list[Path] = []
    selected_files: list[Path] | None = None
    if not args.language:
        all_extensions = frozenset(
            extension for extensions in _LANGUAGE_EXTENSIONS.values() for extension in extensions
        )
        selected_files = _walk_source_files(
            target, skip_file_globs, skip_path_globs, project_root, all_extensions
        )
        selected_languages = {
            language for path in selected_files if (language := _language_for(path)) is not None
        }
        if selected_languages:
            java_mode = selected_languages == {"java"}
            swift_mode = selected_languages == {"swift"}
            if "swift" in selected_languages and len(selected_languages) > 1:
                selected_files = [path for path in selected_files if path.suffix.lower() != ".swift"]
        else:
            java_inventory, _java_files = _java_inventory(
                target, project_root, skip_file_globs, skip_path_globs
            )
            if java_inventory:
                java_mode = True
            else:
                swift_inventory, _swift_files = _swift_inventory(
                    target, project_root, skip_file_globs, skip_path_globs
                )
                if swift_inventory:
                    swift_mode = True
                project_files = _walk_source_files(
                    project_root,
                    skip_file_globs,
                    skip_path_globs,
                    project_root,
                    all_extensions,
                )
                project_languages = {
                    language
                    for path in project_files
                    if (language := _language_for(path)) is not None
                }
                java_mode = project_languages == {"java"}
                swift_mode = swift_mode or project_languages == {"swift"}
    if swift_mode:
        try:
            target.relative_to(project_root)
        except ValueError:
            swift_scan = _swift_scan_payload([], None, project_root)
            swift_scan.update({
                "status": "unsupported",
                "failure_kind": "unsafe-target",
                "message": "Swift target must stay within the project root",
            })
            _write_jsonl([], args.output)
            _write_scan(swift_scan, args.output)
            print("[detect_omnibus] ERROR: Swift target escapes project root", file=sys.stderr)
            return 2
        if not (project_root / "Package.swift").is_file():
            swift_scan = _swift_scan_payload([], None, project_root)
            swift_scan.update({
                "status": "unsupported",
                "failure_kind": "swiftpm-project-marker-missing",
                "message": "bounded Swift v1 requires Package.swift at the project root",
            })
            _write_jsonl([], args.output)
            _write_scan(swift_scan, args.output)
            print("[detect_omnibus] ERROR: SwiftPM Package.swift is required", file=sys.stderr)
            return 2
    if java_mode:
        kotlin = _first_kotlin_source(target, project_root)
        if kotlin is not None:
            print(
                "[detect_omnibus] ERROR: Kotlin source is unsupported by Java v1: " + str(kotlin),
                file=sys.stderr,
            )
            return 2
    if java_mode:
        if not java_inventory:
            java_inventory, java_files = _java_inventory(
                target, project_root, skip_file_globs, skip_path_globs
            )
        else:
            java_files = [
                project_root / row["file"]
                for row in java_inventory
                if row["role"] == "eligible"
            ]
        if not java_files:
            java_scan = _java_scan_payload(java_inventory, None)
            java_scan["status"] = "unsupported"
            java_scan["failure_kind"] = (
                "no-java-files" if not java_inventory else "no-eligible-java-source"
            )
            _write_jsonl([], args.output)
            _write_java_scan(java_scan, args.output)
            print(
                "[detect_omnibus] ERROR: no eligible Java source under target; "
                "zero candidates are not a clean result",
                file=sys.stderr,
            )
            return 2
        files = list(java_files)
    elif swift_mode:
        if not swift_inventory:
            swift_inventory, swift_files = _swift_inventory(
                target, project_root, skip_file_globs, skip_path_globs
            )
        else:
            swift_files = [
                project_root / row["file"]
                for row in swift_inventory
                if row["role"] == "eligible"
            ]
        if not swift_files:
            swift_scan = _swift_scan_payload(swift_inventory, None, project_root)
            swift_scan.update({
                "status": "unsupported",
                "failure_kind": (
                    "no-swift-files" if not swift_inventory else "no-eligible-swift-source"
                ),
                "message": "no eligible first-party Swift source under target",
            })
            _write_jsonl([], args.output)
            _write_scan(swift_scan, args.output)
            print(
                "[detect_omnibus] ERROR: no eligible Swift source under target; "
                "zero candidates are not a clean result",
                file=sys.stderr,
            )
            return 2
        files = list(swift_files)
    else:
        if selected_files is not None:
            files = selected_files
        else:
            extensions = frozenset(
                extension for language in wanted for extension in _LANGUAGE_EXTENSIONS[language]
            )
            files = _walk_source_files(
                target,
                skip_file_globs,
                skip_path_globs,
                project_root,
                extensions,
            )
        java_files = [path for path in files if path.suffix.lower() == ".java"]
        swift_files = [path for path in files if path.suffix.lower() == ".swift"]
    go_files = [path for path in files if path.suffix.lower() == ".go"]
    java_symbols: dict[Path, list[Symbol]] = {}
    swift_symbols: dict[Path, list[Symbol]] = {}
    generated_java: set[Path] = set()
    try:
        go_symbols = _go_symbols(go_files) if go_files else {}
        if java_files:
            java_symbols, java_provenance, generated_java = _java_symbols(java_files, project_root)
        else:
            java_provenance = None
        if swift_files:
            swift_symbols, swift_provenance = _swift_symbols(swift_files, project_root)
        else:
            swift_provenance = None
    except (GoExtractionError, JavaExtractionError, SwiftExtractionError) as exc:
        print(f"[detect_omnibus] ERROR: {exc}", file=sys.stderr)
        return 2
    if java_mode:
        for row in java_inventory:
            path = (project_root / row["file"]).resolve()
            if row["role"] == "eligible" and path in generated_java:
                row["role"] = "excluded"
                row["reason"] = "generated"
        java_files = [path for path in java_files if path.resolve() not in generated_java]
        files = list(java_files)
        java_scan = _java_scan_payload(java_inventory, java_provenance)
        if not java_files:
            java_scan["status"] = "unsupported"
            java_scan["failure_kind"] = "no-eligible-java-source"
            _write_jsonl([], args.output)
            _write_java_scan(java_scan, args.output)
            print(
                "[detect_omnibus] ERROR: no eligible Java source under target; "
                "zero candidates are not a clean result",
                file=sys.stderr,
            )
            return 2
    if swift_mode:
        assert swift_provenance is not None
        swift_scan = _swift_scan_payload(swift_inventory, swift_provenance, project_root)
        swift_status = swift_scan["status"]
        if swift_status in {"unsupported", "failed"}:
            _write_jsonl([], args.output)
            _write_scan(swift_scan, args.output)
            print(
                "[detect_omnibus] ERROR: "
                + str(swift_scan.get("message") or swift_scan.get("failure_kind")),
                file=sys.stderr,
            )
            return 2
    records: list[dict[str, object]] = []
    for filepath in files:
        try:
            rel = filepath.relative_to(project_root).as_posix()
        except ValueError:
            rel = str(filepath)
        try:
            record = _scan_file(
                filepath, rel, project_root, go_symbols, java_symbols, swift_symbols
            )
        except (TypeScriptExtractionError, GoExtractionError, JavaExtractionError, SwiftExtractionError) as exc:
            print(f"[detect_omnibus] ERROR: {filepath}: {exc}", file=sys.stderr)
            return 2
        if record is not None:
            records.append(record)
    records.sort(key=lambda record: (-int(record["score"]), str(record["file"])))
    _write_jsonl(records, args.output)
    if java_scan is not None:
        _write_java_scan(java_scan, args.output)
    if swift_scan is not None:
        _write_scan(swift_scan, args.output)
    print(
        f"[detect_omnibus] wrote {args.output} ({len(records)} omnibus candidates across {len(files)} files)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
