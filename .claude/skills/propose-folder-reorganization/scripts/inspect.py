#!/usr/bin/env python3
"""Inspect a folder-topology cluster and its import impact.

Given a parent directory and a leading-underscore prefix, gather:
  - cluster_files:   each cluster file's path, line count, public symbols
  - import_impact:   every import line in the project that resolves to
                     a cluster member, with the after-rename target
                     precomputed
  - matched_tests:   tests_<prefix>_*.py files at the parent (or at the
                     project root / an app root) that exercise cluster
                     members
  - singletons_at_parent: count of sibling files at the parent that are
                     NOT in the cluster and NOT in noise tokens
  - defer_signals:   guardrail trips (cluster_below_threshold,
                     scratch_code, framework_convention)

Output: JSON with the keys above. Stdlib only.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import sys
from pathlib import Path

DEFAULT_MIN_CLUSTER_SIZE = 3

DEFAULT_EXCLUDE_DIR_NAMES = {
    "__pycache__",
    "migrations",
    "data",
    ".venv",
    "node_modules",
    "staticfiles",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
}

# Same noise-token list as /find-folder-topology-drift's detect.py.
NOISE_TOKENS = {
    "__init__",
    "conftest",
    "apps",
    "admin",
    "urls",
    "wsgi",
    "asgi",
    "manage",
    "settings",
    "models",
    "views",
    "tests",
}

# Path *segments* that mark a directory as scratch / experimental code,
# matched anywhere in the parent's path (location-independent — no app-root
# literal). e.g. `_experiments` matches `core/.../_experiments/x`,
# `app/.../_experiments/x`, or a top-level `experiments/x`.
SCRATCH_CODE_SEGMENTS = (
    "_experiments",
    "experiments",
    "sandbox",
    "scratch",
    "tmp",
    "_archive",
)

# Django (and similar frameworks) discover modules by file name in some
# directories; collapsing into subfolders breaks the contract. These are
# matched as path *suffixes* so they hold for ANY app root (`core/`, `app/`,
# `src/x/`, …) rather than a single hardcoded directory. The proposal flags
# a hit so the orchestrator can recommend `defer_framework_convention`.
FRAMEWORK_CONVENTION_SUFFIXES = (
    "management/commands",
    "management",
    "migrations",
    "templatetags",
)


def _posix(parent_rel: str) -> str:
    """Normalize a relative parent path to POSIX separators for matching."""
    return parent_rel.replace("\\", "/").strip("/")


def _is_scratch(parent_rel: str) -> bool:
    """True when any path segment marks scratch / experimental code."""
    segments = _posix(parent_rel).split("/")
    return any(seg in SCRATCH_CODE_SEGMENTS for seg in segments)


def _is_framework_convention(parent_rel: str) -> bool:
    """True when the parent equals or ends with a framework-convention dir
    (``management/commands``, ``management``, ``migrations``, ``templatetags``)
    for any app root — the sanctioned "assume the Django convention, not a
    specific directory" case.
    """
    rel = _posix(parent_rel)
    for suffix in FRAMEWORK_CONVENTION_SUFFIXES:
        if rel == suffix or rel.endswith("/" + suffix):
            return True
    return False


def _is_excluded_dir(path: Path, extra_globs: list[str]) -> bool:
    if any(part in DEFAULT_EXCLUDE_DIR_NAMES for part in path.parts):
        return True
    rel = str(path)
    for pattern in extra_globs:
        if fnmatch.fnmatch(rel, pattern):
            return True
    return False


def _line_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _public_symbols(path: Path) -> list[str]:
    """Top-level public functions, classes, and module-level names.

    A name counts as public if it doesn't start with `_`. Module-level
    assignments are included (they are often constants the cluster
    re-exports).
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                symbols.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    symbols.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if not node.target.id.startswith("_"):
                symbols.append(node.target.id)
    return symbols


def _cluster_files(parent: Path, prefix: str) -> list[Path]:
    if not parent.is_dir():
        return []
    if prefix == "tests":
        return sorted(
            p for p in parent.iterdir()
            if p.is_file() and p.suffix == ".py" and p.stem.startswith("tests_") and p.stem != "tests"
        )
    return sorted(
        p for p in parent.iterdir()
        if p.is_file() and p.suffix == ".py" and p.stem.startswith(f"{prefix}_")
    )


def _singletons_at_parent(parent: Path, cluster: set[Path]) -> int:
    if not parent.is_dir():
        return 0
    count = 0
    for entry in parent.iterdir():
        if not entry.is_file() or entry.suffix != ".py":
            continue
        if entry in cluster:
            continue
        if entry.stem in NOISE_TOKENS:
            continue
        count += 1
    return count


def _module_path(project_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(project_root)
    parts = list(rel.with_suffix("").parts)
    return ".".join(parts)


def _new_module_path(parent_module: str, prefix: str, old_stem: str) -> str:
    if prefix == "tests":
        # tests_X.py at parent-root → parent/tests/test_X.py
        suffix = old_stem[len("tests_"):]
        return f"{parent_module}.tests.test_{suffix}"
    suffix = old_stem[len(prefix) + 1:]  # strip "<prefix>_"
    return f"{parent_module}.{prefix}.{suffix}"


def _walk_python_files(project_root: Path, exclude_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for path in project_root.rglob("*.py"):
        try:
            if any(part in DEFAULT_EXCLUDE_DIR_NAMES for part in path.relative_to(project_root).parts):
                continue
        except ValueError:
            continue
        rel = str(path.relative_to(project_root))
        if any(fnmatch.fnmatch(rel, pat) for pat in exclude_globs):
            continue
        files.append(path)
    return files


def _resolve_relative_module(
    importer_path: Path,
    project_root: Path,
    module: str | None,
    level: int,
) -> str | None:
    """Turn a `from .X import Y` style ImportFrom into an absolute dotted module.

    `level=0` is an absolute import; the original `module` is the
    answer. `level>=1` strips that many components from the importing
    file's package path.
    """
    if level == 0:
        return module
    try:
        rel = importer_path.relative_to(project_root)
    except ValueError:
        return None
    package_parts = list(rel.with_suffix("").parts[:-1])  # drop the file stem
    if level > len(package_parts):
        return None
    base_parts = package_parts[: len(package_parts) - (level - 1)]
    if module:
        base_parts = base_parts + module.split(".")
    return ".".join(base_parts) if base_parts else None


def _import_impact(
    project_root: Path,
    cluster_modules: dict[str, str],
    cluster_paths: set[Path],
    exclude_globs: list[str],
) -> list[dict]:
    """Find every import line whose target lives in cluster_modules.

    Returns one record per import line:
      {importer, lineno, statement, current_module, new_module}

    The importer path is project-relative. statement is the source line
    text (truncated to 200 chars). current_module is the dotted path
    that resolves to a cluster member; new_module is the
    after-rename target. Both absolute (`from pkg.views.site_config_x
    import Y`) and relative (`from .site_config_x import Y`) imports
    are matched.
    """
    impact: list[dict] = []

    cluster_module_set = set(cluster_modules.keys())

    for path in _walk_python_files(project_root, exclude_globs):
        if path in cluster_paths:
            # Skip imports within the cluster itself — those rename
            # mechanically alongside the move. The orchestrator notes
            # them in the migration step but they don't show up as
            # external impact.
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        source_lines = source.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in cluster_module_set:
                        impact.append({
                            "importer": str(path.relative_to(project_root)),
                            "lineno": node.lineno,
                            "statement": _line_at(source_lines, node.lineno),
                            "current_module": alias.name,
                            "new_module": cluster_modules[alias.name],
                            "form": "import",
                        })
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve_relative_module(
                    path, project_root, node.module, node.level or 0,
                )
                if resolved and resolved in cluster_module_set:
                    for alias in node.names:
                        impact.append({
                            "importer": str(path.relative_to(project_root)),
                            "lineno": node.lineno,
                            "statement": _line_at(source_lines, node.lineno),
                            "current_module": resolved,
                            "current_symbol": alias.name,
                            "new_module": cluster_modules[resolved],
                            "form": "from",
                        })
    return impact


def _line_at(source_lines: list[str], lineno: int) -> str:
    if 1 <= lineno <= len(source_lines):
        return source_lines[lineno - 1].strip()[:200]
    return ""


def _matched_tests(
    project_root: Path,
    parent: Path,
    prefix: str,
    cluster_paths: set[Path],
) -> list[dict]:
    """Find tests_<prefix>_*.py files exercising cluster members.

    Searches:
      - the parent itself (e.g. `<package>/views/`)
      - the project root (matches the common complaint of many
        `tests_*.py` siblings piled at the repo root)
      - the parent's top-level app root (e.g. tests piled at
        `<app>/` for a `<app>/views/<prefix>_*` cluster)
    """
    results: list[dict] = []
    candidates: list[Path] = []

    # Same-parent tests (only meaningful when parent != project root).
    if parent != project_root:
        candidates.extend(
            p for p in parent.iterdir()
            if p.is_file() and p.suffix == ".py" and p.stem.startswith(f"tests_{prefix}_")
        )

    # Tests at project root that name the cluster prefix.
    for p in project_root.iterdir():
        if not (p.is_file() and p.suffix == ".py"):
            continue
        if p.stem.startswith(f"tests_{prefix}_"):
            if p not in candidates:
                candidates.append(p)

    # Tests piled at the parent's top-level app root when the cluster
    # lives a level or more below it (e.g. `<app>/tests_<prefix>_*.py`
    # for a `<app>/views/<prefix>_*` cluster). Derived from the parent's
    # own path — no hardcoded app-root name.
    try:
        parent_rel_parts = parent.relative_to(project_root).parts
    except ValueError:
        parent_rel_parts = ()
    if len(parent_rel_parts) > 1:
        app_root = project_root / parent_rel_parts[0]
        if app_root.is_dir() and app_root != parent:
            for p in app_root.iterdir():
                if not (p.is_file() and p.suffix == ".py"):
                    continue
                if p.stem.startswith(f"tests_{prefix}_"):
                    if p not in candidates:
                        candidates.append(p)

    for test_path in sorted(candidates):
        # Pair the test with the most-likely cluster file by stem
        # similarity. e.g. tests_site_config_save.py → site_config_save.py.
        test_stem = test_path.stem  # tests_site_config_save
        suffix = test_stem[len(f"tests_{prefix}_"):]  # save
        match = None
        for cluster_path in cluster_paths:
            if cluster_path.stem == f"{prefix}_{suffix}":
                match = cluster_path
                break
        results.append({
            "test_path": str(test_path.relative_to(project_root)),
            "subject_path": str(match.relative_to(project_root)) if match else None,
            "new_test_path": (
                f"{parent.relative_to(project_root)}/{prefix}/tests/test_{suffix}.py"
            ) if match else None,
        })
    return results


def _defer_signals(
    parent_rel: str,
    cluster_paths: list[Path],
    min_cluster_size: int,
) -> list[str]:
    signals: list[str] = []
    if len(cluster_paths) < min_cluster_size:
        signals.append("cluster_below_threshold")
    if _is_scratch(parent_rel):
        signals.append("scratch_code")
    if _is_framework_convention(parent_rel):
        signals.append("framework_convention")
    return signals


def inspect(
    *,
    project_root: Path,
    parent: Path,
    prefix: str,
    min_cluster_size: int,
    exclude_globs: list[str],
) -> dict:
    cluster_paths = _cluster_files(parent, prefix)
    cluster_set: set[Path] = set(cluster_paths)
    parent_module = _module_path(project_root, parent)

    cluster_files: list[dict] = []
    cluster_modules: dict[str, str] = {}
    for path in cluster_paths:
        current_module = _module_path(project_root, path)
        new_module = _new_module_path(parent_module, prefix, path.stem)
        cluster_modules[current_module] = new_module
        cluster_files.append({
            "path": str(path.relative_to(project_root)),
            "module": current_module,
            "new_module": new_module,
            "line_count": _line_count(path),
            "public_symbols": _public_symbols(path),
        })

    parent_rel = str(parent.relative_to(project_root))

    impact = _import_impact(project_root, cluster_modules, cluster_set, exclude_globs)
    matched = _matched_tests(project_root, parent, prefix, cluster_set)
    singletons = _singletons_at_parent(parent, cluster_set)
    signals = _defer_signals(parent_rel, cluster_paths, min_cluster_size)

    return {
        "target": {
            "parent": parent_rel,
            "prefix": prefix,
            "parent_module": parent_module,
            "target_slug": f"{parent_rel.replace('/', '-')}__{prefix}",
        },
        "cluster_files": cluster_files,
        "import_impact": impact,
        "matched_tests": matched,
        "singletons_at_parent": singletons,
        "defer_signals": signals,
        "summary": {
            "cluster_size": len(cluster_paths),
            "total_loc": sum(c["line_count"] for c in cluster_files),
            "import_impact_count": len(impact),
            "matched_tests_count": len(matched),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parent",
        type=Path,
        required=True,
        help="Parent directory containing the cluster (e.g. <package>/views).",
    )
    parser.add_argument(
        "--prefix",
        required=True,
        help="Leading-underscore prefix without trailing _ (e.g. site_config). "
             "Special value `tests` triggers tests_by_prefix mode.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: cwd).",
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=DEFAULT_MIN_CLUSTER_SIZE,
        help="Minimum siblings to count as a cluster (default: 3).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional glob pattern to exclude (additive; repeatable).",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    parent = args.parent if args.parent.is_absolute() else (project_root / args.parent).resolve()

    if not parent.is_dir():
        print(f"inspect: parent {args.parent} is not a directory", file=sys.stderr)
        return 2

    data = inspect(
        project_root=project_root,
        parent=parent,
        prefix=args.prefix,
        min_cluster_size=args.min_cluster_size,
        exclude_globs=args.exclude,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    summary = data["summary"]
    print(
        f"inspect: cluster={summary['cluster_size']} loc={summary['total_loc']} "
        f"impact={summary['import_impact_count']} tests={summary['matched_tests_count']}",
        file=sys.stderr,
    )
    print(f"inspect: wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
