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

The script-family path is syntax-only: it needs Node and a ``typescript`` package
resolvable from ``--project-root`` but does not need a tsconfig, type checker,
module resolution, framework model, or semantic responsibility claims.
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


_LANGUAGES: tuple[str, ...] = ("go", "javascript", "python", "typescript")
_LANGUAGE_EXTENSIONS: dict[str, frozenset[str]] = {
    "go": frozenset({".go"}),
    "python": frozenset({".py"}),
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
) -> dict[str, object] | None:
    language = _language_for(filepath)
    if language is None:
        return None
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if language == "python":
        extracted = _python_symbols(source)
        analyzer = "python-ast"
    elif language == "go":
        extracted = go_symbols[filepath.resolve()]
        analyzer = "go-parser-go-ast"
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
    if not args.target.is_dir():
        print(f"[detect_omnibus] ERROR: {args.target} is not a directory", file=sys.stderr)
        return 2
    project_root = args.project_root.resolve()
    wanted = set(args.language) or set(_LANGUAGES)
    extensions = frozenset(extension for language in wanted for extension in _LANGUAGE_EXTENSIONS[language])
    files = _walk_source_files(
        args.target.resolve(),
        _DEFAULT_SKIP_FILE_GLOBS + tuple(args.skip_file_glob),
        _DEFAULT_SKIP_PATH_GLOBS + tuple(args.skip_path_glob),
        project_root,
        extensions,
    )
    go_files = [path for path in files if path.suffix.lower() == ".go"]
    try:
        go_symbols = _go_symbols(go_files) if go_files else {}
    except GoExtractionError as exc:
        print(f"[detect_omnibus] ERROR: {exc}", file=sys.stderr)
        return 2
    records: list[dict[str, object]] = []
    for filepath in files:
        try:
            rel = filepath.relative_to(project_root).as_posix()
        except ValueError:
            rel = str(filepath)
        try:
            record = _scan_file(filepath, rel, project_root, go_symbols)
        except (TypeScriptExtractionError, GoExtractionError) as exc:
            print(f"[detect_omnibus] ERROR: {filepath}: {exc}", file=sys.stderr)
            return 2
        if record is not None:
            records.append(record)
    records.sort(key=lambda record: (-int(record["score"]), str(record["file"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record) + "\n")
    print(
        f"[detect_omnibus] wrote {args.output} ({len(records)} omnibus candidates across {len(files)} files)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
