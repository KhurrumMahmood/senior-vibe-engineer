#!/usr/bin/env python3
"""Detect drift on the folder-topology surface (ADR 0006).

Stage 1 detection bands:
  - flat_prefix_cluster:   a directory contains N+ Python modules
                           sharing the same `<prefix>_` token, where
                           `prefix` names a domain (>= 2 chars).
  - tests_by_prefix:       a directory contains N+ files matching
                           `tests_*.py` AND has no `tests/` subfolder.
  - sparse_folder_package: a folder package (has `__init__.py`)
                           contains FEWER than N source modules at
                           its top level — the demotion direction
                           added by ADR 0006 Rule 5. The threshold is
                           the same N as the promotion bands; folders
                           earn packaging at ≥3 siblings and lose it
                           below ≥3.
  - pages_route_mirror:    a file under `pages/<parent>/` whose
                           basename starts with a token matching a
                           singularization of the parent folder name
                           (e.g. `pages/sites/site_wizard.py` — the
                           `site_` prefix duplicates the parent
                           `sites/`). Implements ADR 0010: filenames
                           under route-mirrored `pages/` folders strip
                           parent-folder prefixes so a reader who
                           knows the route knows the file.

Stage 2 bands (deferred — see SKILL.md):
  - route_folder_misalignment
  - same_domain_helper_sprawl

Output: JSONL with one finding per line. Python records preserve their
existing Stage 1 bands. TypeScript records add ``language: typescript`` and
are only the narrow ``flat_prefix_cluster`` invariant.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from support import (  # noqa: E402
    BUILTIN_SKIP_DIRS,
    Scope,
    go_scan_payload,
    inventory_go,
    inventory_java,
    iter_paths,
    load_scope,
    matches_any,
    probe_go,
    java_scan_payload,
    write_json,
)

SKILL_NAME = "find-folder-topology-drift"

DEFAULT_MIN_CLUSTER_SIZE = 3

# Folder packages whose existence is mandated by a framework runtime
# (Django auto-discovery, py.test convention) — these never demote
# even when their source-module count is below threshold.
FRAMEWORK_FOLDER_NAMES = {
    "tests",          # py.test / Django test runner discovery
    "commands",       # management/commands/<cmd>.py — Django convention
    "management",     # management/ — Django parent of commands
    "templatetags",   # Django template-tag library
    "migrations",     # already excluded; defensive
    "fixtures",       # py.test fixtures package
}

# Tokens that should not count as a "prefix" — they're noise (e.g. the
# Django app's own conftest, init shims, single-purpose files that
# happen to share a leading word). These are treated as singletons by
# the prefix-cluster scan.
PREFIX_NOISE_TOKENS = {
    "__init__",
    "conftest",
    "apps",
    "admin",
    "urls",
    "wsgi",
    "asgi",
    "manage",
    "settings",  # Django global settings — distinct from views/settings_*
    "models",
    "views",
    "tests",  # caught by the tests_by_prefix band, not flat_prefix_cluster
}


def _has_subfolder(directory: Path, name: str) -> bool:
    target = directory / name
    return target.is_dir() and (target / "__init__.py").exists() or target.is_dir()


def _python_modules_in(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix == ".py")


def _prefix_clusters(
    modules: list[Path],
    min_cluster_size: int,
) -> dict[str, list[Path]]:
    """Group modules by leading `<prefix>_` token; return clusters of >= N."""
    by_prefix: dict[str, list[Path]] = defaultdict(list)
    for module in modules:
        stem = module.stem
        if "_" not in stem:
            continue
        prefix = stem.split("_", 1)[0]
        if len(prefix) < 2:
            continue
        if prefix in PREFIX_NOISE_TOKENS:
            continue
        by_prefix[prefix].append(module)
    return {prefix: paths for prefix, paths in by_prefix.items() if len(paths) >= min_cluster_size}


def _tests_by_prefix(modules: list[Path], min_cluster_size: int) -> list[Path]:
    """Return tests_*.py files in `modules` if their count >= min_cluster_size."""
    hits = [m for m in modules if m.stem.startswith("tests_") and m.stem != "tests"]
    return hits if len(hits) >= min_cluster_size else []


def _is_folder_package(directory: Path) -> bool:
    return (directory / "__init__.py").is_file()


def _source_modules_in(directory: Path) -> list[Path]:
    """Return non-init, non-test source modules at the top of `directory`.

    Used by the `sparse_folder_package` band — counts only files that
    represent first-class source content. Skips `__init__.py`,
    `conftest.py`, and any `tests_*.py` file (those are covered by
    `tests_by_prefix` if at threshold).
    """
    if not directory.is_dir():
        return []
    out: list[Path] = []
    for p in directory.iterdir():
        if not (p.is_file() and p.suffix == ".py"):
            continue
        if p.stem in {"__init__", "conftest"}:
            continue
        if p.stem.startswith("tests_") or p.stem.startswith("test_"):
            continue
        out.append(p)
    return sorted(out)


def _child_packages_in(directory: Path) -> list[Path]:
    """Return immediate child packages (subdirs with `__init__.py`)."""
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir()
        if p.is_dir() and (p / "__init__.py").is_file()
    )


def _is_framework_folder(directory: Path) -> bool:
    """True if directory is a known framework-mandated folder name.

    The check is name-based and applies to any directory whose final
    component is in FRAMEWORK_FOLDER_NAMES, so subfolders like
    `core/views/site_config/tests/` are also exempted.
    """
    if directory.name in FRAMEWORK_FOLDER_NAMES:
        return True
    # Defensive: a `commands` folder anywhere under `management/` is a
    # framework dir even if the literal name check above already
    # caught it.
    parts = directory.parts
    if "management" in parts and "commands" in parts:
        return True
    return False


def _is_under_tests_tree(directory: Path) -> bool:
    """True if directory is `tests/` or any descendant of one.

    Within a tests tree, `test_` is the canonical Python/Django test-
    runner naming convention — not a domain prefix. Files like
    `tests/test_foo.py` and `tests/test_bar.py` should never trip
    `flat_prefix_cluster` on the `test` token even when ≥3 siblings
    share it. This sibling clustering IS the convention.
    """
    return any(part == "tests" for part in directory.parts)


def _is_namespace_package(directory: Path) -> bool:
    """True if directory has __init__.py, zero source modules, and ≥1
    child package.

    Such a folder is a Python *namespace* package — its purpose is to
    group child subpackages under a shared dotted-path prefix
    (`app.ai.runtime`, `app.ai.ai_sidecar`). It carries no
    first-class source surface of its own and is intentionally below
    ADR 0006's ≥3-module threshold. Treating it as `sparse_folder_
    package` would force collapsing the namespace, which contradicts
    the grouping decision the redesign embodied (ADR 0008/0009).
    """
    if not (directory / "__init__.py").is_file():
        return False
    has_source_modules = any(
        p.is_file()
        and p.suffix == ".py"
        and p.stem not in {"__init__", "conftest"}
        and not p.stem.startswith("test_")
        and not p.stem.startswith("tests_")
        for p in directory.iterdir()
    )
    if has_source_modules:
        return False
    has_child_pkg = any(
        p.is_dir() and (p / "__init__.py").is_file()
        for p in directory.iterdir()
    )
    return has_child_pkg


# Threshold for treating an `__init__.py` as a substantive re-export
# shim rather than a stub doc-string. Calibrated empirically: the
# transitional shims at `core/models/__init__.py` (3614 bytes),
# `core/views/brand_downloads/__init__.py` (2641 bytes), and
# `core/views/crawling/__init__.py` (2923 bytes) all sit well above
# this floor; trivially-stubbed packages (e.g. `"""<doc>"""\n` only)
# fall under it.
_SHIM_INIT_SIZE_FLOOR = 500


def _is_reexport_shim(directory: Path) -> bool:
    """True if directory's only `.py` content is a substantive re-export
    `__init__.py` — typically a backwards-compat redirect surviving a
    move. ADR 0006's ≥3-module threshold is about folder structure;
    a re-export shim adds NO folder structure to evaluate (its sole
    purpose is keeping legacy import paths resolvable while callers
    migrate). Demoting it to a sibling `.py` file would yield exactly
    the same shim at a different path, not a structural improvement.
    """
    init_file = directory / "__init__.py"
    if not init_file.is_file():
        return False
    # Must be the sole organizational content: 0 source modules, 0 child packages.
    if any(
        p.is_file()
        and p.suffix == ".py"
        and p.stem not in {"__init__", "conftest"}
        and not p.stem.startswith("test_")
        and not p.stem.startswith("tests_")
        for p in directory.iterdir()
    ):
        return False
    if any(
        p.is_dir() and (p / "__init__.py").is_file()
        for p in directory.iterdir()
    ):
        return False
    try:
        size = init_file.stat().st_size
    except OSError:
        return False
    if size < _SHIM_INIT_SIZE_FLOOR:
        return False
    try:
        text = init_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    # A re-export shim's signature: import statements that name another
    # package. A substantive `__init__.py` without imports is something
    # else (configuration, constants, etc.) and stays subject to the
    # sparse-folder rule.
    has_imports = any(
        line.strip().startswith(("from ", "import "))
        for line in text.splitlines()
    )
    return has_imports


# Pages-mirror-routes (ADR 0010): the parent folder name and the
# leading filename token form a duplicated prefix that should be
# stripped. Common singularizations only — keeps the band high
# precision; novel folder names are flagged once added here.
_PAGES_PARENT_TO_TOKEN = {
    "sites": "site",
    "runs": "run",
    "jobs": "job",
    "brands": "brand",
    "products": "product",
    "exports": "export",
    "ptid": "ptid",
}


def _scan_pages_route_mirror(
    pages_root: Path,
    project_root: Path,
) -> list[dict]:
    """Find files under `pages/<parent>/` whose name duplicates the
    parent folder as a prefix.

    Implements ADR 0010 Stage-1 detection: filename `<token>_*.py` under
    `<parent>/` where `<token>` singularizes `<parent>` is the canonical
    drift shape — the file should be `*.py` (parent-prefix stripped).
    """
    out: list[dict] = []
    if not pages_root.is_dir():
        return out

    def rel(path: Path) -> str:
        try:
            return str(path.relative_to(project_root))
        except ValueError:
            return str(path)

    for parent in sorted(pages_root.iterdir()):
        if not parent.is_dir():
            continue
        if parent.name in BUILTIN_SKIP_DIRS:
            continue
        token = _PAGES_PARENT_TO_TOKEN.get(parent.name)
        if token is None:
            continue
        parent_pkg = rel(parent).replace("/", ".")
        for module in sorted(parent.iterdir()):
            if not (module.is_file() and module.suffix == ".py"):
                continue
            stem = module.stem
            if stem in {"__init__", "conftest"}:
                continue
            if not stem.startswith(f"{token}_"):
                continue
            stripped = stem[len(token) + 1:]
            if not stripped:
                continue
            out.append({
                "pattern": "pages_route_mirror",
                "file": rel(module),
                "lineno": 1,
                "summary": (
                    f"`{rel(module)}` duplicates parent-folder prefix "
                    f"`{token}_` under `{rel(parent)}/`. ADR 0010 says "
                    f"filenames strip parent-folder prefixes."
                ),
                "recommendation": (
                    f"Rename `{module.name}` to `{stripped}.py` so the "
                    f"file path mirrors the route. The full path becomes "
                    f"`{rel(parent)}/{stripped}.py` and a reader who "
                    f"knows the route can navigate to it directly. "
                    f"Update template "
                    f"`{{% include %}}`, `template_name`, and any "
                    f"`from {parent_pkg} import "
                    f"{stem}` callers in the same PR."
                ),
            })
    return out


def detect(
    *,
    project_root: Path,
    scope: Scope,
    min_cluster_size: int,
) -> list[dict]:
    findings: list[dict] = []

    def rel(path: Path) -> str:
        try:
            return str(path.relative_to(project_root))
        except ValueError:
            return str(path)

    # Candidate directories = every directory holding an in-scope file.
    # Scope is ignore-first (BUILTIN_SKIP_DIRS + repo-wide ignore.md +
    # this skill's `## Ignore`), so there is no baked host scan root or
    # exclude list — narrowing is entirely host-authored (ADR 0021). The
    # bands below re-read each directory from disk, so the scan only needs
    # to supply the directory list.
    files = iter_paths(project_root, scope)
    directories = sorted({f.parent for f in files} | {project_root})

    seen_dirs: set[Path] = set()
    for directory in directories:
        try:
            resolved = directory.resolve()
        except OSError:
            continue
        if resolved in seen_dirs:
            continue
        seen_dirs.add(resolved)

        modules = _python_modules_in(directory)

        # Band 3 — sparse_folder_package (Rule 5, demotion direction).
        # Fires on a folder that has __init__.py but fewer than
        # min_cluster_size first-class source modules. Skip the scan
        # root itself (it is by definition the entry point — its
        # cluster size is the whole project). Namespace packages
        # (0 modules + ≥1 child package) are exempt — collapsing
        # them would dissolve an intentional grouping prefix.
        if (
            directory != project_root
            and _is_folder_package(directory)
            and not _is_namespace_package(directory)
            and not _is_reexport_shim(directory)
            and not _is_under_tests_tree(directory)
        ):
            if not _is_framework_folder(directory):
                source_modules = _source_modules_in(directory)
                child_packages = _child_packages_in(directory)
                # Hybrid count: source modules + child packages count
                # toward the ≥3 threshold. A folder with 2 source
                # modules + 2 child subpackages has 4 organizational
                # children — it is a healthy mid-tree node, not a
                # sparse leaf candidate for demotion.
                organizational_children = len(source_modules) + len(child_packages)
                if organizational_children < min_cluster_size:
                    sample_modules = ", ".join(p.name for p in source_modules)
                    sample_pkgs = ", ".join(p.name + "/" for p in child_packages)
                    pieces = [s for s in (sample_modules, sample_pkgs) if s]
                    sample = "; ".join(pieces) or "(none)"
                    findings.append({
                        "pattern": "sparse_folder_package",
                        "file": rel(directory),
                        "lineno": 1,
                        "summary": (
                            f"Folder package `{rel(directory)}` has "
                            f"{len(source_modules)} source module(s) and "
                            f"{len(child_packages)} child package(s), below "
                            f"the ≥{min_cluster_size} threshold: {sample}."
                        ),
                        "recommendation": (
                            f"Demote `{rel(directory)}/` per ADR 0006 Rule 5 — "
                            "the survivors migrate up to the parent as sibling "
                            "files and the folder is removed. Run "
                            "`/propose-folder-reorganization` (demote mode) for "
                            "the per-folder proposal — current → proposed tree, "
                            "file-move table, import-impact summary, "
                            "characterization-test matrix. The migration lands "
                            "as one PR via `/refactor-subsystem` (decomposition "
                            "mode). If the folder is in-flight to grow back "
                            "above threshold, the proposal records "
                            "`defer_in_flight` instead of an action."
                        ),
                    })

        if not modules:
            continue

        # Band 1 — flat_prefix_cluster
        # Suppress entirely when scanning under a tests/ tree (the
        # `test_*.py` convention is canonical Python/Django) or when
        # scanning a framework-mandated folder like
        # `core/management/commands/` (Django auto-discovers commands
        # by leaf-file basename, so subfolders would break dispatch
        # and `run_*` / `setup_*` siblings are a feature, not drift).
        if _is_under_tests_tree(directory) or _is_framework_folder(directory):
            clusters: dict[str, list[Path]] = {}
        else:
            clusters = _prefix_clusters(modules, min_cluster_size)
        for prefix, paths in sorted(clusters.items()):
            sample = ", ".join(p.name for p in paths[:5])
            extra = f" (+{len(paths) - 5} more)" if len(paths) > 5 else ""
            findings.append({
                "pattern": "flat_prefix_cluster",
                "file": rel(directory),
                "lineno": 1,
                "summary": (
                    f"Directory `{rel(directory)}` has {len(paths)} sibling modules "
                    f"sharing the prefix `{prefix}_`: {sample}{extra}."
                ),
                "recommendation": (
                    f"Collapse the `{prefix}_` cluster into `{rel(directory)}/{prefix}/` per "
                    "ADR 0006 Rule 2. Run `/propose-folder-reorganization` for the per-cluster "
                    "proposal — current → proposed tree, file-move table, import-impact summary, "
                    "characterization-test matrix. The migration lands as one PR via "
                    "`/refactor-subsystem` (decomposition mode)."
                ),
            })

        # Band 2 — tests_by_prefix
        tests_hits = _tests_by_prefix(modules, min_cluster_size)
        if tests_hits:
            has_tests_subfolder = (directory / "tests").is_dir()
            if not has_tests_subfolder:
                sample = ", ".join(p.name for p in tests_hits[:5])
                extra = f" (+{len(tests_hits) - 5} more)" if len(tests_hits) > 5 else ""
                findings.append({
                    "pattern": "tests_by_prefix",
                    "file": rel(directory),
                    "lineno": 1,
                    "summary": (
                        f"Directory `{rel(directory)}` has {len(tests_hits)} `tests_*.py` "
                        f"files and no `tests/` subfolder: {sample}{extra}."
                    ),
                    "recommendation": (
                        f"Introduce `{rel(directory)}/tests/` per ADR 0006 Rule 1. New tests go "
                        "into `tests/test_<area>.py`; existing `tests_*.py` files migrate "
                        "alongside the code they exercise — not in a one-shot rename PR. "
                        "The Django test runner discovers both forms identically."
                    ),
                })

    # Band 4 — pages_route_mirror (ADR 0010). Runs on any `pages/`
    # directory beneath an in-scope file (location-independent —
    # `package/pages`, `src/pages`, …), not a baked application root.
    pages_roots = sorted({
        parent for f in files for parent in f.parents
        if parent.name == "pages"
    })
    for pages_root in pages_roots:
        findings.extend(_scan_pages_route_mirror(pages_root, project_root))

    return findings


TYPESCRIPT_SUFFIXES = {".ts", ".tsx"}
TYPESCRIPT_SKIP_DIRS = {
    "tests",
    "test",
    "__tests__",
    "specs",
    "generated",
    "vendor",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "reports",
}


def _typescript_source_files_in(directory: Path) -> list[Path]:
    """Return direct TypeScript siblings eligible for the v1 lexical band."""
    if not directory.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(directory.iterdir()):
        if not (path.is_file() and path.suffix.lower() in TYPESCRIPT_SUFFIXES):
            continue
        name = path.name.lower()
        stem = path.stem
        if name in {"index.ts", "index.tsx"} or name.endswith(".d.ts"):
            continue
        if stem.endswith(".spec") or stem.endswith(".test"):
            continue
        files.append(path)
    return files


def _typescript_prefix_clusters(
    modules: list[Path], min_cluster_size: int
) -> dict[str, list[Path]]:
    """Group direct `.ts`/`.tsx` siblings by their first `_` or `-` token."""
    by_prefix: dict[str, list[Path]] = defaultdict(list)
    for module in modules:
        stem = module.stem
        positions = [position for position in (stem.find("_"), stem.find("-")) if position > 0]
        if not positions:
            continue
        prefix = stem[: min(positions)]
        if len(prefix) < 2:
            continue
        by_prefix[prefix].append(module)
    return {
        prefix: paths
        for prefix, paths in by_prefix.items()
        if len(paths) >= min_cluster_size
    }


def _typescript_directories(
    source_root: Path,
    project_root: Path,
    excludes: list[str],
) -> list[Path]:
    """Walk one declared TypeScript source root without crossing v1 boundaries."""
    root_parts = {
        part.lower()
        for part in source_root.relative_to(project_root).parts
    }
    if root_parts & TYPESCRIPT_SKIP_DIRS:
        return []
    directories: list[Path] = []
    for directory, child_dirs, _files in os.walk(source_root):
        current = Path(directory)
        relative = current.relative_to(project_root).as_posix()
        if matches_any(relative, excludes):
            child_dirs[:] = []
            continue
        directories.append(current)
        kept: list[str] = []
        for child in child_dirs:
            candidate = current / child
            child_relative = candidate.relative_to(project_root).as_posix()
            if child in TYPESCRIPT_SKIP_DIRS or matches_any(child_relative, excludes):
                continue
            kept.append(child)
        child_dirs[:] = kept
    return sorted(directories)


def detect_typescript(
    *,
    project_root: Path,
    source_roots: list[Path],
    excludes: list[str],
    min_cluster_size: int,
) -> list[dict]:
    """Detect only explicit-root TypeScript flat-prefix clusters.

    This is deliberately additive to the Python bands above.  It does not
    inspect package density, test-folder placement, Next/pages topology,
    barrels, module resolution, or imports.
    """
    findings: list[dict] = []
    seen: set[Path] = set()
    for source_root in source_roots:
        for directory in _typescript_directories(source_root, project_root, excludes):
            resolved = directory.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            for prefix, paths in sorted(
                _typescript_prefix_clusters(
                    _typescript_source_files_in(directory), min_cluster_size
                ).items()
            ):
                files = [path.relative_to(project_root).as_posix() for path in paths]
                location = directory.relative_to(project_root).as_posix()
                findings.append({
                    "language": "typescript",
                    "pattern": "flat_prefix_cluster",
                    "file": location,
                    "lineno": 1,
                    "prefix": prefix,
                    "files": files,
                    "summary": (
                        f"TypeScript directory `{location}` has {len(files)} direct "
                        f"siblings sharing the first domain token `{prefix}`: "
                        f"{', '.join(path.name for path in paths)}."
                    ),
                    "recommendation": (
                        f"Review the `{prefix}` files as a possible folder boundary. "
                        "This TypeScript v1 finding is lexical only: it does not prove "
                        "a move, import safety, or a framework-specific package layout."
                    ),
                })
    return findings


JAVASCRIPT_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs"}
JAVASCRIPT_SKIP_DIRS = TYPESCRIPT_SKIP_DIRS


def _javascript_source_files_in(directory: Path) -> list[Path]:
    """Return direct first-party JavaScript siblings for the lexical band."""
    if not directory.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(directory.iterdir()):
        if not (path.is_file() and not path.is_symlink() and path.suffix.lower() in JAVASCRIPT_SUFFIXES):
            continue
        name = path.name.lower()
        stem = path.stem
        if name in {"index.js", "index.jsx", "index.mjs", "index.cjs"}:
            continue
        if stem.endswith((".spec", ".test", ".generated", ".min")):
            continue
        files.append(path)
    return files


def _javascript_prefix_clusters(
    modules: list[Path], min_cluster_size: int
) -> dict[str, list[Path]]:
    """Group direct JavaScript siblings by their first `_` or `-` token."""
    by_prefix: dict[str, list[Path]] = defaultdict(list)
    for module in modules:
        stem = module.stem
        positions = [position for position in (stem.find("_"), stem.find("-")) if position > 0]
        if not positions:
            continue
        prefix = stem[: min(positions)]
        if len(prefix) < 2:
            continue
        by_prefix[prefix].append(module)
    return {
        prefix: paths
        for prefix, paths in by_prefix.items()
        if len(paths) >= min_cluster_size
    }


def _javascript_directories(
    source_root: Path,
    project_root: Path,
    excludes: list[str],
) -> list[Path]:
    """Walk an explicit JavaScript root without following generated trees."""
    root_parts = {
        part.lower()
        for part in source_root.relative_to(project_root).parts
    }
    if root_parts & JAVASCRIPT_SKIP_DIRS:
        return []
    directories: list[Path] = []
    for directory, child_dirs, _files in os.walk(source_root, followlinks=False):
        current = Path(directory)
        relative = current.relative_to(project_root).as_posix()
        if matches_any(relative, excludes):
            child_dirs[:] = []
            continue
        directories.append(current)
        kept: list[str] = []
        for child in child_dirs:
            candidate = current / child
            child_relative = candidate.relative_to(project_root).as_posix()
            if (
                candidate.is_symlink()
                or child.lower() in JAVASCRIPT_SKIP_DIRS
                or matches_any(child_relative, excludes)
            ):
                continue
            kept.append(child)
        child_dirs[:] = kept
    return sorted(directories)


def detect_javascript(
    *,
    project_root: Path,
    source_roots: list[Path],
    excludes: list[str],
    min_cluster_size: int,
) -> list[dict]:
    """Detect explicit-root JavaScript lexical flat-prefix clusters only."""
    findings: list[dict] = []
    seen: set[Path] = set()
    for source_root in source_roots:
        for directory in _javascript_directories(source_root, project_root, excludes):
            resolved = directory.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            for prefix, paths in sorted(
                _javascript_prefix_clusters(
                    _javascript_source_files_in(directory), min_cluster_size
                ).items()
            ):
                files = [path.relative_to(project_root).as_posix() for path in paths]
                location = directory.relative_to(project_root).as_posix()
                findings.append({
                    "language": "javascript",
                    "pattern": "flat_prefix_cluster",
                    "file": location,
                    "lineno": 1,
                    "prefix": prefix,
                    "files": files,
                    "summary": (
                        f"JavaScript directory `{location}` has {len(files)} direct "
                        f"siblings sharing the first domain token `{prefix}`: "
                        f"{', '.join(path.name for path in paths)}."
                    ),
                    "recommendation": (
                        f"Review the `{prefix}` files as a possible folder boundary. "
                        "This JavaScript v1 finding is lexical only: it does not prove "
                        "a move, import safety, or a framework-specific package layout."
                    ),
                })
    return findings


def _go_prefix_clusters(
    files: list[Path], min_cluster_size: int
) -> dict[tuple[Path, str], list[Path]]:
    """Group eligible direct Go siblings by the first underscore token."""
    grouped: dict[tuple[Path, str], list[Path]] = defaultdict(list)
    for path in files:
        stem = path.name[:-3]
        if "_" not in stem:
            continue
        prefix = stem.split("_", 1)[0]
        if len(prefix) < 2:
            continue
        grouped[(path.parent, prefix)].append(path)
    return {
        key: paths
        for key, paths in grouped.items()
        if len(paths) >= min_cluster_size
    }


def detect_go(
    *, project_root: Path, files: list[Path], min_cluster_size: int
) -> list[dict]:
    """Detect Go direct-sibling prefix clusters from inventoried eligible files."""
    findings: list[dict] = []
    for (directory, prefix), paths in sorted(
        _go_prefix_clusters(files, min_cluster_size).items(),
        key=lambda item: (item[0][0].as_posix(), item[0][1]),
    ):
        rel_files = [path.relative_to(project_root).as_posix() for path in sorted(paths)]
        location = directory.relative_to(project_root).as_posix()
        findings.append(
            {
                "language": "go",
                "pattern": "flat_prefix_cluster",
                "file": location,
                "lineno": 1,
                "prefix": prefix,
                "files": rel_files,
                "summary": (
                    f"Go directory `{location}` has {len(rel_files)} direct production "
                    f"siblings sharing the first underscore token `{prefix}`: "
                    f"{', '.join(path.name for path in sorted(paths))}."
                ),
                "recommendation": (
                    f"Review the `{prefix}` files as a possible folder boundary. "
                    "This Go v1 finding is filename-only: it does not prove package "
                    "cohesion, import safety, build-tag equivalence, or a safe move."
                ),
            }
        )
    return findings


JAVA_LEADING_DOMAIN_RE = re.compile(
    r"^(?:(?P<acronym>[A-Z]+)(?=[A-Z][a-z])|(?P<word>[A-Z][a-z0-9]+))"
)


def _java_prefix_clusters(
    files: list[Path], min_cluster_size: int
) -> dict[tuple[Path, str], list[Path]]:
    """Group Java siblings by the leading CamelCase domain token."""
    grouped: dict[tuple[Path, str], list[Path]] = defaultdict(list)
    for path in files:
        if path.name in {"module-info.java", "package-info.java"}:
            continue
        match = JAVA_LEADING_DOMAIN_RE.match(path.stem)
        if not match or match.end() == len(path.stem):
            continue
        prefix = (match.group("acronym") or match.group("word")).casefold()
        if len(prefix) < 2:
            continue
        grouped[(path.parent, prefix)].append(path)
    return {
        key: paths
        for key, paths in grouped.items()
        if len(paths) >= min_cluster_size
    }


def detect_java(
    *, project_root: Path, files: list[Path], min_cluster_size: int
) -> list[dict]:
    """Detect Java direct-sibling CamelCase clusters from inventory facts."""
    findings: list[dict] = []
    for (directory, prefix), paths in sorted(
        _java_prefix_clusters(files, min_cluster_size).items(),
        key=lambda item: (item[0][0].as_posix(), item[0][1]),
    ):
        rel_files = [path.relative_to(project_root).as_posix() for path in sorted(paths)]
        location = directory.relative_to(project_root).as_posix()
        findings.append(
            {
                "language": "java",
                "pattern": "flat_prefix_cluster",
                "file": location,
                "lineno": 1,
                "prefix": prefix,
                "files": rel_files,
                "summary": (
                    f"Java directory `{location}` has {len(rel_files)} direct production "
                    f"siblings sharing the leading CamelCase domain token `{prefix}`: "
                    f"{', '.join(path.name for path in sorted(paths))}."
                ),
                "recommendation": (
                    f"Review the `{prefix}` files as a possible package boundary. "
                    "This Java v1 finding is filename-only: it does not prove package "
                    "cohesion, import safety, build equivalence, or a safe move."
                ),
            }
        )
    return findings


def _resolve_within_project(
    value: Path, project_root: Path, flag: str
) -> Path | None:
    path = value if value.is_absolute() else project_root / value
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(project_root)
    except (OSError, ValueError):
        print(f"detect: {flag} must name an existing path within --project-root: {value}", file=sys.stderr)
        return None
    return resolved


def _invalidate_java_artifacts(output: Path) -> None:
    """Remove same-run artifacts before a Java rerun can fail."""
    for path in (
        output,
        output.with_name("scan.json"),
        output.with_name("report.md"),
        output.with_name("findings.json"),
    ):
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help=(
            "Optional subtree to narrow the scan to (per-invocation override). "
            "Default: the whole repo, narrowed only by the host's scope/ignore "
            "descriptors (.engineering/docs/<skill>-scope.md and ignore.md)."
        ),
    )
    parser.add_argument(
        "--typescript-root",
        action="append",
        type=Path,
        default=[],
        help=(
            "Declared TypeScript/TSX source root. Repeat for separate roots. "
            "With no --root, scan TypeScript only; pass both root forms for "
            "an additive Python and TypeScript scan."
        ),
    )
    parser.add_argument(
        "--javascript-root",
        action="append",
        type=Path,
        default=[],
        help=(
            "Declared JavaScript/JSX/MJS/CJS source root. Repeat for separate roots. "
            "With no --root, scan JavaScript only; pass both root forms for "
            "an additive Python and JavaScript scan."
        ),
    )
    parser.add_argument(
        "--go-root",
        action="append",
        type=Path,
        default=[],
        help=(
            "Declared Go source root. Repeat for separate roots. With no --root "
            "or JavaScript/TypeScript root, scan Go only."
        ),
    )
    parser.add_argument(
        "--java-root",
        action="append",
        type=Path,
        default=[],
        help=(
            "Declared Java source root. Repeat for separate roots. With no --root "
            "or JavaScript/TypeScript/Go root, scan Java only."
        ),
    )
    # spec:project-structure-redesign-phase-2::IM-26
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root for relative-path display (default: cwd)",
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=DEFAULT_MIN_CLUSTER_SIZE,
        help="Minimum siblings to count as a cluster (default: 3, per ADR 0006)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional ignore glob, additive on top of scope (repeatable)",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    if args.java_root:
        _invalidate_java_artifacts(args.output)
    if not (args.go_root or args.java_root):
        args.output.with_name("scan.json").unlink(missing_ok=True)
    scope = load_scope(project_root, SKILL_NAME)
    if args.root is not None:
        root = _resolve_within_project(args.root, project_root, "--root")
        if root is None:
            return 2
        scope.roots = [root.relative_to(project_root).as_posix()]
    if args.exclude:
        scope.ignore = list(scope.ignore) + list(args.exclude)

    typescript_roots: list[Path] = []
    for raw_root in args.typescript_root:
        root = _resolve_within_project(raw_root, project_root, "--typescript-root")
        if root is None or not root.is_dir():
            if root is not None:
                print(f"detect: --typescript-root must name a directory: {raw_root}", file=sys.stderr)
            return 2
        typescript_roots.append(root)

    javascript_roots: list[Path] = []
    for raw_root in args.javascript_root:
        root = _resolve_within_project(raw_root, project_root, "--javascript-root")
        if root is None or not root.is_dir():
            if root is not None:
                print(f"detect: --javascript-root must name a directory: {raw_root}", file=sys.stderr)
            return 2
        javascript_roots.append(root)

    go_roots: list[Path] = []
    for raw_root in args.go_root:
        root = _resolve_within_project(raw_root, project_root, "--go-root")
        if root is None or not root.is_dir():
            if root is not None:
                print(f"detect: --go-root must name a directory: {raw_root}", file=sys.stderr)
            return 2
        go_roots.append(root)

    java_roots: list[Path] = []
    for raw_root in args.java_root:
        candidate = raw_root if raw_root.is_absolute() else project_root / raw_root
        if candidate.is_symlink():
            print(
                f"detect: --java-root must not be a symlink: {raw_root}",
                file=sys.stderr,
            )
            return 2
        root = _resolve_within_project(raw_root, project_root, "--java-root")
        if root is None or not root.is_dir():
            if root is not None:
                print(f"detect: --java-root must name a directory: {raw_root}", file=sys.stderr)
            return 2
        java_roots.append(root)

    if go_roots and java_roots:
        print(
            "detect: --go-root and --java-root require separate scans so scan.json has one language owner",
            file=sys.stderr,
        )
        return 2

    go_scan: dict | None = None
    go_rc = 0
    go_files: list[Path] = []
    if go_roots:
        tool, go_rc = probe_go()
        if go_rc:
            go_scan = {
                **tool,
                "language": "go",
                "analyzer": "python-filesystem-names",
                "syntax_contract": "filename-only; Go parse validity is not inspected",
                "inventory": [],
                "errors": [],
                "summary": {"discovered": 0, "eligible": 0, "excluded": 0, "failed": 0},
            }
        else:
            inventory, go_files, errors = inventory_go(
                go_roots, project_root, list(args.exclude)
            )
            go_scan = go_scan_payload(tool, inventory, errors)
            if not inventory:
                go_scan["status"] = "unsupported"
                go_scan["failure_kind"] = "no-go-files"
                go_rc = 2

    java_scan: dict | None = None
    java_rc = 0
    java_files: list[Path] = []
    if java_roots:
        inventory, java_files, errors = inventory_java(
            java_roots, project_root, list(args.exclude)
        )
        java_scan = java_scan_payload(inventory, errors)
        if not inventory:
            java_scan["status"] = "unsupported"
            java_scan["failure_kind"] = "no-java-files"
            java_rc = 2

    # A TypeScript-root-only invocation is intentionally TypeScript-only. The
    # preserved Python scan runs when TypeScript was not requested, or when the
    # caller explicitly supplies --root to request a combined scan.
    findings = (
        detect(
            project_root=project_root,
            scope=scope,
            min_cluster_size=args.min_cluster_size,
        )
        if not (typescript_roots or javascript_roots or go_roots or java_roots)
        or args.root is not None
        else []
    )
    if typescript_roots:
        findings.extend(
            detect_typescript(
                project_root=project_root,
                source_roots=typescript_roots,
                excludes=list(args.exclude),
                min_cluster_size=args.min_cluster_size,
            )
        )
    if javascript_roots:
        findings.extend(
            detect_javascript(
                project_root=project_root,
                source_roots=javascript_roots,
                excludes=list(args.exclude),
                min_cluster_size=args.min_cluster_size,
            )
        )
    if go_roots and go_rc == 0:
        findings.extend(
            detect_go(
                project_root=project_root,
                files=go_files,
                min_cluster_size=args.min_cluster_size,
            )
        )
    if java_roots and java_rc == 0:
        findings.extend(
            detect_java(
                project_root=project_root,
                files=java_files,
                min_cluster_size=args.min_cluster_size,
            )
        )
    findings.sort(key=lambda finding: (
        str(finding.get("language", "python")),
        str(finding.get("pattern", "")),
        str(finding.get("file", "")),
        str(finding.get("prefix", "")),
    ))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for finding in findings:
            f.write(json.dumps(finding) + "\n")
    if go_scan is not None:
        write_json(go_scan, args.output.with_name("scan.json"))
    if java_scan is not None:
        write_json(java_scan, args.output.with_name("scan.json"))

    print(f"detect: wrote {len(findings)} findings to {args.output}", file=sys.stderr)
    return go_rc or java_rc


if __name__ == "__main__":
    sys.exit(main())
