#!/usr/bin/env python3
"""Detect omnibus modules — files that answer questions from 3+ domains.

Language-general by architecture (ADR 0032): the clustering, scoring and
reporting below are language-neutral; per-language **symbol extraction
adapters** (keyed by file extension) feed them top-level symbols. Those
adapters now live in the shared ``_lib.lang_adapter`` package and are
selected here via ``get_adapter(path)``:

- ``python-ast`` adapter: exact Python syntax facts, including god-class
  method expansion.
- Tree-sitter adapters: exact normalized syntax facts for JavaScript,
  TypeScript/TSX, Rust, and Go. WP5's batch-sweep member deliberately selects
  only Python and TypeScript; Rust and Go retain their native sweep shims.

For each source file, groups top-level declarations into **domain
clusters** by extracting the head-noun(s) from the symbol name:

  1. Split the name on ``_`` (``bulk_crawl_task`` → ``['bulk', 'crawl',
     'task']``).
  2. Strip generic verbs (``bulk``, ``get``, ``list``, ``create``,
     ``update``, ``delete``, ``fetch``, ``load``, ``save``, ``handle``,
     ``process``, ``check``, ``validate``, ``build``, ``make``,
     ``task``, ``view``, ``service``, and the class-name suffix
     ``View``/``Task``/``Service``).
  3. The first remaining token is the cluster key. Symbols with no
     remaining token join an ``_unclassified`` cluster.

The SRP "and"-count is the number of clusters with ≥2 symbols — a file
with 4 such clusters scores 3 "and"s (clusters joined by three "and"s).
Single-symbol clusters are noise (one helper doesn't make a domain).
A file qualifies as a candidate when ``and_count >= 3``.

Score: responsibility count first, then security/side-effect sensitivity,
then LOC. Cap at top 30 candidates downstream (collapse.py).

Output (one JSON record per flagged file at ``--output``):

    {
      "type": "omnibus",
      "file": "core/views/sitemaps.py",
      "loc": 2425,
      "cluster_count": 4,
      "and_count": 3,
      "score": 5425,
      "risk_score": 3,
      "risk_signals": ["credentials", "admin_auth", "network"],
      "clusters": [
        {"name": "sitemap", "symbols": ["SitemapDiscoveryView", ...],
         "loc": 812},
        ...
      ],
      "srp_sentence": "This file handles sitemap and discovery and import and filter."
    }

The scout applies the evaluation rule from refactor-subsystem §1.2.5
(facets-of-one-job vs independently-understandable domains) to bucket
each candidate as ``confirmed_omnibus``, ``facets_not_domains``, or
``borderline``.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

# Per-language symbol extraction now lives in the shared adapter package
# (ADR 0032's seam, extracted from this file). Wire the repo ``scripts/``
# dir onto sys.path so the package imports when this skill script runs
# standalone, then route by file suffix via ``get_adapter``.
PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _lib.lang_adapter import (  # noqa: E402
    CAP_SYMBOLS,
    AnalysisFailure,
    Symbol,
    get_adapter,
    iter_adapters,
)

# Languages the registered adapters cover, derived from the shared seam —
# drives the ``--language`` CLI filter and the extension set to walk.
_LANGUAGES: tuple[str, ...] = tuple(sorted({a.language for a in iter_adapters()}))


_DEFAULT_SKIP_DIRS: frozenset[str] = frozenset({
    "migrations", "__pycache__", "staticfiles", "node_modules",
    ".git", ".venv", "venv", "dist", "build",
})

_DEFAULT_SKIP_FILE_GLOBS: tuple[str, ...] = (
    "tests_*.py", "test_*.py", "tests.py", "conftest.py",
    "__init__.py",
    "*.min.js", "*.min.css", "*-min.js", "*.bundle.js",
    "*.test.js", "*.spec.js", "*.test.ts", "*.spec.ts",
)

# Skip additional paths that are structurally expected to aggregate
# across domains. Custom-site scrapers and the skill's own scripts get
# a pass.
_DEFAULT_SKIP_PATH_GLOBS: tuple[str, ...] = (
    "sites/*/scrape.py",
)


# Generic verbs / role suffixes stripped before head-noun extraction.
# Kept deliberately small — aggressive stripping collapses too many
# clusters. We strip obvious CRUD verbs, dispatch words, and layer
# suffixes, not domain nouns. Stripping is applied iteratively so a
# name like `update_brand_view` reduces to `brand`.
_STRIP_TOKENS: frozenset[str] = frozenset({
    # CRUD / dispatch verbs
    "bulk", "get", "list", "create", "update", "delete", "remove",
    "fetch", "load", "save", "handle", "process", "check", "validate",
    "build", "make", "run", "do", "set", "put", "patch", "post",
    "start", "stop", "cancel", "retry", "reset", "clear", "apply",
    "ensure", "try", "find", "search", "sync", "refresh", "render",
    "init", "setup", "is", "has", "can", "should", "was", "were",
    "show", "hide", "open", "close", "toggle", "display", "select",
    "initialize", "wire", "populate",
    # Role suffixes (also stripped from ClassDef names)
    "task", "view", "service", "helper", "util", "utils", "client",
    "manager", "factory", "handler", "worker", "callback", "hook",
    # Structural words that don't identify a domain on their own
    "page", "all", "one", "api", "v1", "v2", "data", "row", "rows",
    "config", "with", "for", "to", "from", "by", "or", "and",
})

_RISK_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("credentials", ("credential", "credentials", "password", "secret", "token", "api_key", "apikey")),
    ("admin_auth", ("admin", "staff", "csrf", "auth", "permission", "login")),
    ("raw_sql", ("raw sql", "cursor", "execute(", "mysql", "sql")),
    ("command_execution", ("subprocess", "shell", "command", "curl", "popen", "system(")),
    (
        "network_diagnostics",
        ("proxy", "email", "smtp", "recaptcha", "external_source", "requests.", "httpx", "urllib", "scraperapi", "whi"),
    ),
    ("persistence", (".save(", ".create(", ".update(", ".delete(", "bulk_create", "bulk_update")),
    ("filesystem", ("open(", "write(", "read_text", "write_text", "pathlib", "os.path")),
    ("task_dispatch", (".delay(", ".apply_async(", "safe_dispatch", "celery", "task")),
    ("import_export", ("export", "csv", "excel", "xlsx", "workbook")),
)


def _walk_source_files(
    target: Path,
    skip_file_globs: tuple[str, ...],
    skip_path_globs: tuple[str, ...],
    project_root: Path,
    extensions: frozenset[str],
    roots: tuple[Path, ...],
    exclusions: tuple[Path, ...],
    case_sensitive: bool,
) -> list[Path]:
    def within(path: Path, boundary: Path) -> bool:
        rendered_path = path.as_posix()
        rendered_boundary = boundary.as_posix()
        if not case_sensitive:
            rendered_path = rendered_path.casefold()
            rendered_boundary = rendered_boundary.casefold()
        return rendered_path == rendered_boundary or rendered_path.startswith(
            f"{rendered_boundary}/"
        )

    files: list[Path] = []
    for path in sorted(target.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if any(part in _DEFAULT_SKIP_DIRS for part in path.parts):
            continue
        if any(fnmatch.fnmatchcase(path.name, g) for g in skip_file_globs):
            continue
        try:
            rel = path.relative_to(project_root).as_posix()
        except ValueError:
            rel = path.as_posix()
        if any(fnmatch.fnmatchcase(rel, g) for g in skip_path_globs):
            continue
        if not any(within(path, root) for root in roots):
            continue
        if any(within(path, exclusion) for exclusion in exclusions):
            continue
        files.append(path)
    return files


_CAMEL_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _tokenize(name: str) -> list[str]:
    """Split snake_case OR CamelCase names into lowercase tokens."""
    if not name:
        return []
    # snake_case first; for each segment, split camel then lowercase.
    tokens: list[str] = []
    for seg in name.split("_"):
        if not seg:
            continue
        for piece in _CAMEL_SPLIT.split(seg):
            if piece:
                tokens.append(piece.lower())
    return tokens


def _cluster_key(name: str) -> str:
    """Extract the head-noun cluster key from a symbol name.

    Returns ``_unclassified`` when every token is a generic verb / role
    suffix. This puts miscellaneous helpers in a known bucket instead of
    inflating ``and_count``.
    """
    if name.startswith("_"):
        # Private helpers still get classified — they participate in
        # domain clusters. Strip one leading underscore only.
        name = name.lstrip("_") or name
    tokens = _tokenize(name)
    for tok in tokens:
        if tok not in _STRIP_TOKENS:
            return tok
    return "_unclassified"


def _risk_signals(rel: str, source: str, symbol_names: list[str]) -> tuple[int, list[str]]:
    haystack = "\n".join([rel, *symbol_names, source]).lower()
    signals = [
        label
        for label, terms in _RISK_TERMS
        if any(term in haystack for term in terms)
    ]
    return len(signals), signals


def _scan_file(filepath: Path, rel: str) -> dict[str, object] | None:
    adapter = get_adapter(filepath, capability=CAP_SYMBOLS)
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AnalysisFailure(
            "tool_failure",
            adapter=adapter.name,
            path=rel,
            capability=CAP_SYMBOLS,
            detail=f"could not read source: {exc}",
        ) from exc
    result = adapter.analyze(source, path=rel, capabilities={CAP_SYMBOLS})
    extracted = [
        Symbol(
            name=fact.name,
            cluster_name=fact.name.rsplit(".", 1)[-1],
            kind=fact.kind,
            lineno=fact.line,
            end_lineno=fact.end_line,
            loc=max(1, fact.end_line - fact.line + 1),
            parent=fact.parent,
        )
        for fact in result.for_capability(CAP_SYMBOLS)
    ]

    file_loc = len(source.splitlines())
    clusters: dict[str, dict[str, object]] = {}
    symbol_names: list[str] = []
    for sym in extracted:
        symbol_names.append(sym.name)
        key = _cluster_key(sym.cluster_name)
        bucket = clusters.setdefault(key, {"symbols": [], "loc": 0})
        bucket["symbols"].append(sym.name)  # type: ignore[arg-type]
        bucket["loc"] = int(bucket["loc"]) + sym.loc  # type: ignore[operator]

    # SRP "and"-count: clusters with ≥2 symbols are genuine clusters;
    # single-symbol clusters are noise. Exclude _unclassified from the
    # count — miscellaneous helpers aren't a domain.
    genuine = [
        (name, data)
        for name, data in clusters.items()
        if name != "_unclassified" and len(data["symbols"]) >= 2  # type: ignore[arg-type]
    ]
    and_count = max(0, len(genuine) - 1)

    if and_count < 3:
        return None

    # Sort clusters by LOC descending for report readability.
    ordered_clusters = sorted(
        (
            {
                "name": name,
                "symbols": sorted(data["symbols"]),  # type: ignore[arg-type]
                "loc": int(data["loc"]),  # type: ignore[arg-type]
            }
            for name, data in clusters.items()
            if name != "_unclassified" and len(data["symbols"]) >= 2  # type: ignore[arg-type]
        ),
        key=lambda c: (-int(c["loc"]), str(c["name"])),
    )

    # SRP sentence uses the cluster names in LOC order — readable output
    # that also makes the "and"s visible to the scout.
    names = [str(c["name"]) for c in ordered_clusters]
    if len(names) >= 2:
        srp_sentence = (
            f"This file handles {' and '.join(names)}."
        )
    else:
        srp_sentence = f"This file handles {names[0] if names else '(nothing)'}."

    risk_score, risk_signals = _risk_signals(rel, source, symbol_names)
    score = and_count * 1000 + risk_score * 250 + file_loc

    return {
        "type": "omnibus",
        "file": rel,
        "language": adapter.language,
        "analyzer": adapter.name,
        "loc": file_loc,
        "cluster_count": len(ordered_clusters),
        "and_count": and_count,
        "risk_score": risk_score,
        "risk_signals": risk_signals,
        "score": score,
        "clusters": ordered_clusters,
        "srp_sentence": srp_sentence,
    }


def detect(
    target: Path,
    project_root: Path,
    *,
    languages: set[str] | frozenset[str] | None = None,
    skip_file_globs: tuple[str, ...] = (),
    skip_path_globs: tuple[str, ...] = (),
    roots: tuple[str | Path, ...] | None = None,
    exclusions: tuple[str | Path, ...] = (),
    case_sensitive: bool = True,
) -> list[dict[str, object]]:
    """Return parser-backed candidates or raise a contextual analysis failure."""
    records, _file_count = detect_with_file_count(
        target,
        project_root,
        languages=languages,
        skip_file_globs=skip_file_globs,
        skip_path_globs=skip_path_globs,
        roots=roots,
        exclusions=exclusions,
        case_sensitive=case_sensitive,
    )
    return records


def select_source_files(
    target: Path,
    project_root: Path,
    *,
    languages: set[str] | frozenset[str] | None = None,
    skip_file_globs: tuple[str, ...] = (),
    skip_path_globs: tuple[str, ...] = (),
    roots: tuple[str | Path, ...] | None = None,
    exclusions: tuple[str | Path, ...] = (),
    case_sensitive: bool = True,
) -> list[Path]:
    """Return the exact files eligible under the omnibus selection contract."""
    if not target.exists():
        raise ValueError(f"target not found: {target}")
    if not target.is_dir():
        raise ValueError(f"target is not a directory: {target}")
    wanted = set(languages or _LANGUAGES)
    unknown = sorted(wanted - set(_LANGUAGES))
    if unknown:
        raise ValueError(f"unsupported omnibus languages: {unknown}")
    extensions = frozenset(
        ext
        for adapter in iter_adapters()
        if adapter.language in wanted
        for ext in adapter.extensions
    )
    project_root = project_root.resolve()

    def resolved(raw: str | Path) -> Path:
        path = Path(raw)
        return (path if path.is_absolute() else project_root / path).resolve()

    root_paths = tuple(resolved(root) for root in (roots or (project_root,)))
    excluded_paths = tuple(resolved(path) for path in exclusions)
    return _walk_source_files(
        target.resolve(),
        _DEFAULT_SKIP_FILE_GLOBS + tuple(skip_file_globs),
        _DEFAULT_SKIP_PATH_GLOBS + tuple(skip_path_globs),
        project_root,
        extensions,
        root_paths,
        excluded_paths,
        case_sensitive,
    )


def detect_with_file_count(
    target: Path,
    project_root: Path,
    *,
    languages: set[str] | frozenset[str] | None = None,
    skip_file_globs: tuple[str, ...] = (),
    skip_path_globs: tuple[str, ...] = (),
    roots: tuple[str | Path, ...] | None = None,
    exclusions: tuple[str | Path, ...] = (),
    case_sensitive: bool = True,
) -> tuple[list[dict[str, object]], int]:
    """Return candidates and the exact selected-file count from one walk."""
    files = select_source_files(
        target,
        project_root,
        languages=languages,
        skip_file_globs=skip_file_globs,
        skip_path_globs=skip_path_globs,
        roots=roots,
        exclusions=exclusions,
        case_sensitive=case_sensitive,
    )
    project_root = project_root.resolve()
    records: list[dict[str, object]] = []
    for filepath in files:
        try:
            rel = filepath.relative_to(project_root).as_posix()
        except ValueError:
            rel = filepath.as_posix()
        record = _scan_file(filepath, rel)
        if record is not None:
            records.append(record)
    ordered = sorted(records, key=lambda row: (-int(row["score"]), str(row["file"])))
    return ordered, len(files)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", required=True, type=Path,
                   help="Directory to scan")
    p.add_argument("--project-root", required=True, type=Path,
                   help="Project root (for relative paths in output)")
    p.add_argument("--output", required=True, type=Path,
                   help="Output JSONL file")
    p.add_argument("--skip-file-glob", action="append", default=[],
                   help="Extra file-name globs to skip (repeatable)")
    p.add_argument("--skip-path-glob", action="append", default=[],
                   help="Extra relative-path globs to skip (repeatable)")
    p.add_argument("--language", action="append", default=[],
                   choices=list(_LANGUAGES),
                   help="Restrict to these languages (default: all adapters)")
    args = p.parse_args(argv)

    if not args.target.exists():
        print(
            f"[detect_omnibus] ERROR: {args.target} not found",
            file=sys.stderr,
        )
        return 2
    if not args.target.is_dir():
        print(
            f"[detect_omnibus] ERROR: {args.target} is not a directory",
            file=sys.stderr,
        )
        return 2

    project_root = args.project_root.resolve()
    wanted = set(args.language) or set(_LANGUAGES)
    records, file_count = detect_with_file_count(
        args.target,
        project_root,
        languages=wanted,
        skip_file_globs=tuple(args.skip_file_glob),
        skip_path_globs=tuple(args.skip_path_glob),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    print(
        f"[detect_omnibus] wrote {args.output} "
        f"({len(records)} omnibus candidates across {file_count} files)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
