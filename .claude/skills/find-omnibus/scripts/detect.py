#!/usr/bin/env python3
"""Detect omnibus modules — files that answer questions from 3+ domains.

Language-general by architecture (ADR 0032): the clustering, scoring and
reporting below are language-neutral; per-language **symbol extraction
adapters** (keyed by file extension) feed them top-level symbols.

- ``python-ast`` adapter: full ``ast`` walk (exact), including god-class
  method expansion.
- ``js-heuristic`` adapter: column-0 declaration scan for JavaScript /
  TypeScript (``function name(``, ``const name = (…) =>``, ``class
  Name``, ``window.Name =``). Deliberately coarse — IIFE-wrapped or
  deeply indented module bodies under-detect; if that proves material,
  the adapter graduates to a real parser per ADR 0032 rather than
  growing regex epicycles. Findings carry the adapter name so reviewers
  can calibrate trust.

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
import ast
import fnmatch
import json
import re
import sys
from pathlib import Path


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
) -> list[Path]:
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


def _node_loc(node: ast.AST) -> int:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None) or start
    if start is None or end is None:
        return 0
    return max(1, end - start + 1)


def _risk_signals(rel: str, source: str, symbol_names: list[str]) -> tuple[int, list[str]]:
    haystack = "\n".join([rel, *symbol_names, source]).lower()
    signals = [
        label
        for label, terms in _RISK_TERMS
        if any(term in haystack for term in terms)
    ]
    return len(signals), signals


def _python_symbols(source: str) -> list[tuple[str, str, int]] | None:
    """Python adapter: exact ``ast`` extraction.

    Returns ``(symbol_name, cluster_name, loc)`` triples — cluster_name
    is the name fed to head-noun extraction (method name for expanded
    god-class methods, so ``Service.parse_html`` clusters as ``html``
    not ``Service``). ``None`` means unparseable.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    symbols: list[tuple[str, str, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            symbols.append((node.name, node.name, _node_loc(node)))
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            # God-class expansion: when a class exposes 3+ non-dunder
            # methods the method names drive the SRP signal (a service
            # class with `get_samples`, `save_samples`, `generate_html`,
            # `parse_html`, `send_feedback` is genuinely multi-domain).
            # Small classes count as a single symbol by the class name.
            method_nodes = [
                m for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not (m.name.startswith("__") and m.name.endswith("__"))
            ]
            if len(method_nodes) >= 3:
                for m in method_nodes:
                    symbols.append(
                        (f"{node.name}.{m.name}", m.name, _node_loc(m))
                    )
            else:
                symbols.append((node.name, node.name, _node_loc(node)))
    return symbols


_JS_DECL = re.compile(
    r"^(?:"
    r"(?:async\s+)?function\s+(?P<fn>[A-Za-z_$][\w$]*)\s*\("
    r"|(?:const|let|var)\s+(?P<assigned>[A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s*)?(?:function\b|\([^)\n]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"
    r"|class\s+(?P<cls>[A-Za-z_$][\w$]*)"
    r"|window\.(?P<ns>[A-Za-z_$][\w$]*)\s*="
    r")",
    re.MULTILINE,
)


def _javascript_symbols(source: str) -> list[tuple[str, str, int]] | None:
    """JavaScript/TypeScript adapter: column-0 declaration heuristic.

    Counts top-level function declarations, function-valued const/let/var
    assignments, class declarations, and ``window.X =`` namespace
    exports. Symbol LOC is the span to the next top-level declaration —
    coarse, but ranking-grade. Known under-detection: IIFE-wrapped
    module bodies (declarations indented one level) yield no symbols;
    such files come back ``None``-equivalent (empty) rather than wrong.
    """
    lines = source.splitlines()
    matches: list[tuple[int, str]] = []  # (line_index, name)
    for m in _JS_DECL.finditer(source):
        name = m.group("fn") or m.group("assigned") or m.group("cls") or m.group("ns")
        if not name:
            continue
        line_index = source.count("\n", 0, m.start())
        matches.append((line_index, name))
    symbols: list[tuple[str, str, int]] = []
    for i, (line_index, name) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else len(lines)
        loc = max(1, end - line_index)
        symbols.append((name, name, loc))
    return symbols


# Extension → (adapter_name, extractor). The analysis below is
# language-neutral; this table is the only per-language seam (ADR 0032).
_ANALYZERS: dict[str, tuple[str, object]] = {
    ".py": ("python-ast", _python_symbols),
    ".js": ("js-heuristic", _javascript_symbols),
    ".mjs": ("js-heuristic", _javascript_symbols),
    ".cjs": ("js-heuristic", _javascript_symbols),
    ".ts": ("js-heuristic", _javascript_symbols),
    ".tsx": ("js-heuristic", _javascript_symbols),
}

_LANGUAGE_BY_ADAPTER: dict[str, str] = {
    "python-ast": "python",
    "js-heuristic": "javascript",
}


def _scan_file(filepath: Path, rel: str) -> dict[str, object] | None:
    adapter_name, extractor = _ANALYZERS[filepath.suffix.lower()]
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    extracted = extractor(source)  # type: ignore[operator]
    if extracted is None:
        return None

    file_loc = len(source.splitlines())
    clusters: dict[str, dict[str, object]] = {}
    symbol_names: list[str] = []
    for symbol_name, cluster_name, loc in extracted:
        symbol_names.append(symbol_name)
        key = _cluster_key(cluster_name)
        bucket = clusters.setdefault(key, {"symbols": [], "loc": 0})
        bucket["symbols"].append(symbol_name)  # type: ignore[arg-type]
        bucket["loc"] = int(bucket["loc"]) + loc  # type: ignore[operator]

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
        "language": _LANGUAGE_BY_ADAPTER[adapter_name],
        "analyzer": adapter_name,
        "loc": file_loc,
        "cluster_count": len(ordered_clusters),
        "and_count": and_count,
        "risk_score": risk_score,
        "risk_signals": risk_signals,
        "score": score,
        "clusters": ordered_clusters,
        "srp_sentence": srp_sentence,
    }


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
                   choices=sorted(set(_LANGUAGE_BY_ADAPTER.values())),
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

    skip_files = _DEFAULT_SKIP_FILE_GLOBS + tuple(args.skip_file_glob)
    skip_paths = _DEFAULT_SKIP_PATH_GLOBS + tuple(args.skip_path_glob)
    project_root = args.project_root.resolve()

    wanted = set(args.language) or set(_LANGUAGE_BY_ADAPTER.values())
    extensions = frozenset(
        ext
        for ext, (adapter_name, _) in _ANALYZERS.items()
        if _LANGUAGE_BY_ADAPTER[adapter_name] in wanted
    )
    files = _walk_source_files(
        args.target.resolve(), skip_files, skip_paths, project_root, extensions,
    )
    records: list[dict[str, object]] = []
    for filepath in files:
        try:
            rel = str(filepath.relative_to(project_root))
        except ValueError:
            rel = str(filepath)
        rec = _scan_file(filepath, rel)
        if rec is not None:
            records.append(rec)

    # Sort by score descending so collapse.py sees the worst offenders
    # first.
    records.sort(key=lambda r: (-int(r["score"]), str(r["file"])))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    print(
        f"[detect_omnibus] wrote {args.output} "
        f"({len(records)} omnibus candidates across {len(files)} files)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
