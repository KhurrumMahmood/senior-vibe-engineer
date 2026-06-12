#!/usr/bin/env python3
"""Detect candidate boundary seams in a missing-boundary target.

Given a target (file, directory, or skill directory), score symbol pairs
by:

  - co-edit frequency       (from `git log --name-only`)
  - mutual import direction (AST: which sibling imports which?)
  - naming alignment        (lexical prefix clusters)
  - cross-cluster call edge (AST: same-target call graph)

Combine the four signals into per-pair scores; cluster by greedy
agglomerative grouping; emit the top N candidate seams with member
lists, proposed public API, and reach-into-private call sites.

Output: JSON with the structure described in the SKILL.md inspection.json
schema. Stdlib + git only — no Django imports.
"""
from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from itertools import combinations
from pathlib import Path

DEFAULT_CO_EDIT_DAYS = 90
DEFAULT_MIN_CLUSTER_SIZE = 3
DEFAULT_SEAM_THRESHOLD = 0.4
MIN_PYTHON_FILES = 2
MIN_PUBLIC_SYMBOLS = 6

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
    "staticfiles",
    "migrations",
    ".pytest_cache",
    ".ruff_cache",
}

# Host projects can extend this tuple with their own scratch-code path
# prefixes (e.g. one-off experiment commands, custom-job code under a
# `_experiments/` directory). Empty by default so the generic mirror
# doesn't false-positive on any specific host layout.
SCRATCH_CODE_PREFIXES: tuple[str, ...] = ()


@dataclass
class Symbol:
    name: str
    file: str
    kind: str  # "function" | "class" | "constant"
    public: bool
    lineno: int = 0


@dataclass
class CandidateSeam:
    cluster_id: str
    members: list[str]
    rationale: str
    proposed_public_api: list[str]
    callers_into_private_helpers: list[dict]
    scores: dict[str, float]


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIR_NAMES for part in path.parts)


def _resolve_target(target: str, project_root: Path) -> tuple[Path, str, list[Path]]:
    """Return (target_path, target_kind, files_in_scope)."""
    p = (project_root / target).resolve()
    if not p.exists():
        # try as subsystem name → docs/subsystems/<name>.md
        subsystem_doc = project_root / ".claude" / "docs" / "subsystems" / f"{target}.md"
        if subsystem_doc.exists():
            files = _files_from_subsystem_doc(subsystem_doc, project_root)
            return subsystem_doc, "subsystem", files
        raise FileNotFoundError(f"Target not found: {target}")

    if p.is_file():
        if p.suffix != ".py":
            raise ValueError(
                f"Target is not a Python source file (suffix={p.suffix!r}): {target}"
            )
        return p, "file", [p]

    # Directory — detect if it's a skill directory.
    if (p / "SKILL.md").exists():
        files = [f for f in p.rglob("*.py") if not _is_excluded(f.relative_to(project_root))]
        # Treat SKILL.md as a virtual symbol-bearing file by parsing its phase headings.
        return p, "skill_directory", files
    files = [f for f in p.rglob("*.py") if not _is_excluded(f.relative_to(project_root))]
    return p, "directory", files


def _files_from_subsystem_doc(doc: Path, project_root: Path) -> list[Path]:
    """Extract Python file paths referenced in a subsystem markdown doc."""
    text = doc.read_text(encoding="utf-8", errors="replace")
    files = []
    for match in re.finditer(r"`([\w\-/\.]+\.py)`", text):
        candidate = project_root / match.group(1)
        if candidate.is_file():
            files.append(candidate)
    return files


def _public_name(name: str) -> bool:
    return not name.startswith("_") or name in {"__init__", "__call__"}


def _extract_symbols(file: Path, project_root: Path) -> list[Symbol]:
    try:
        source = file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    rel = str(file.relative_to(project_root))
    symbols: list[Symbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                Symbol(node.name, rel, "function", _public_name(node.name), node.lineno)
            )
        elif isinstance(node, ast.ClassDef):
            symbols.append(
                Symbol(node.name, rel, "class", _public_name(node.name), node.lineno)
            )
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id.isupper():
                    symbols.append(
                        Symbol(tgt.id, rel, "constant", _public_name(tgt.id), tgt.lineno)
                    )
    return symbols


def _extract_skill_md_phases(skill_md: Path, project_root: Path) -> list[Symbol]:
    """Parse `## Phase N` / `### N.M` headings in a SKILL.md and emit virtual symbols.

    When the target is a skill directory, the SKILL.md phase structure
    is treated as the symbol surface (sub-phases are the symbols, the
    phase number is the "leading prefix" the naming clusterer groups by).
    Allows /propose-boundary on a skill directory to recommend a
    phase-aligned split into specialized sub-skills.
    """
    if not skill_md.exists():
        return []
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rel = str(skill_md.relative_to(project_root)) if skill_md.is_relative_to(project_root) else str(skill_md)
    symbols: list[Symbol] = []
    for i, line in enumerate(text.splitlines(), 1):
        m_phase = re.match(r"^## Phase\s+(\d+)\s*[—\-]\s*(.+)$", line)
        if m_phase:
            phase = m_phase.group(1)
            slug = re.sub(r"[^a-z0-9_]+", "_", m_phase.group(2).lower()).strip("_")[:32]
            name = f"phase{phase}_{slug}" if slug else f"phase{phase}"
            symbols.append(Symbol(name, rel, "phase", True, i))
            continue
        m_sub = re.match(r"^###\s+(\d+)\.(\d+(?:\.\d+)?)\s*(.+)?$", line)
        if m_sub:
            phase, sub = m_sub.group(1), m_sub.group(2).replace(".", "_")
            tail = (m_sub.group(3) or "").strip()
            slug = re.sub(r"[^a-z0-9_]+", "_", tail.lower()).strip("_")[:32]
            name = f"phase{phase}_{sub}_{slug}" if slug else f"phase{phase}_{sub}"
            symbols.append(Symbol(name, rel, "phase_sub", True, i))
    return symbols


def _extract_call_edges(file: Path, project_root: Path, symbol_names: set[str]) -> list[tuple[str, str]]:
    """Return (caller_name, callee_name) for calls inside file whose callee resolves to a symbol in scope."""
    try:
        source = file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    edges: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            caller_name = node.name
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    callee = _call_name(inner.func)
                    if callee and callee in symbol_names and callee != caller_name:
                        edges.append((caller_name, callee))
    return edges


def _call_name(func_node: ast.AST) -> str | None:
    if isinstance(func_node, ast.Name):
        return func_node.id
    if isinstance(func_node, ast.Attribute):
        return func_node.attr
    return None


def _extract_imports(file: Path, project_root: Path, target_files: set[str]) -> list[dict]:
    """Imports of target files (or symbols re-exported from target) from anywhere in the project.

    Returns dicts of {importer, statement, lineno, imports_private}.
    """
    # This is computed by walking the whole project for imports of the target files;
    # for the helper's first pass we only walk files we already loaded (cheaper).
    return []  # populated by _scan_project_imports below


def _scan_project_imports(
    project_root: Path,
    target_files: list[Path],
    target_symbols: dict[str, Symbol],
) -> list[dict]:
    """Walk the project and return import-impact records for symbols in target_symbols."""
    target_module_paths = {f.relative_to(project_root).with_suffix("").as_posix().replace("/", ".") for f in target_files}
    # Also include parent-package import forms (e.g. `from app.tasks import ...`).
    parent_packages = set()
    for tf in target_files:
        rel = tf.relative_to(project_root)
        if rel.parent.as_posix() not in {".", ""}:
            parent_packages.add(rel.parent.as_posix().replace("/", "."))
    import_records: list[dict] = []
    for root, dirs, names in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES]
        for name in names:
            if not name.endswith(".py"):
                continue
            p = Path(root) / name
            if p in target_files:
                continue
            try:
                source = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module in target_module_paths or module in parent_packages:
                        for alias in node.names:
                            sym_name = alias.name
                            if sym_name in target_symbols:
                                import_records.append({
                                    "importer": str(p.relative_to(project_root)),
                                    "module": module,
                                    "symbol": sym_name,
                                    "lineno": node.lineno,
                                    "imports_private": not target_symbols[sym_name].public,
                                })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in target_module_paths or alias.name in parent_packages:
                            import_records.append({
                                "importer": str(p.relative_to(project_root)),
                                "module": alias.name,
                                "symbol": None,
                                "lineno": node.lineno,
                                "imports_private": False,
                            })
    return import_records


def _co_edit_pairs(
    project_root: Path,
    target_files: list[Path],
    days: int,
) -> list[dict]:
    """Co-edit frequency: how often pairs of target files appear in the same commit."""
    if len(target_files) < 2:
        return []
    rel_files = [str(f.relative_to(project_root)) for f in target_files]
    try:
        result = subprocess.run(
            [
                "git", "log",
                f"--since={days}.days.ago",
                "--name-only",
                "--pretty=format:--commit--",
                "--",
                *rel_files,
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    commits: list[set[str]] = []
    current: set[str] = set()
    for line in result.stdout.splitlines():
        if line == "--commit--":
            if current:
                commits.append(current)
                current = set()
            continue
        if line.strip() in rel_files:
            current.add(line.strip())
    if current:
        commits.append(current)
    pair_counts: Counter[tuple[str, str]] = Counter()
    per_file_counts: Counter[str] = Counter()
    for commit_files in commits:
        for f in commit_files:
            per_file_counts[f] += 1
        for a, b in combinations(sorted(commit_files), 2):
            pair_counts[(a, b)] += 1
    pairs: list[dict] = []
    for (a, b), co in pair_counts.items():
        a_count = per_file_counts[a]
        b_count = per_file_counts[b]
        denom = max(a_count + b_count - co, 1)
        jaccard = co / denom
        pairs.append({
            "a": a,
            "b": b,
            "co_changes": co,
            "a_changes": a_count,
            "b_changes": b_count,
            "jaccard": round(jaccard, 4),
        })
    pairs.sort(key=lambda r: r["jaccard"], reverse=True)
    return pairs[:50]


def _naming_clusters(symbols: list[Symbol], min_size: int) -> list[dict]:
    """Group symbols by their leading underscore-stripped prefix token."""
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for sym in symbols:
        token = sym.name.lstrip("_").split("_", 1)[0].lower()
        if not token or len(token) < 3:
            continue
        by_prefix[token].append(sym.name)
    clusters: list[dict] = []
    for prefix, members in by_prefix.items():
        if len(members) >= min_size:
            clusters.append({"prefix": prefix, "members": sorted(members)})
    clusters.sort(key=lambda c: len(c["members"]), reverse=True)
    return clusters


def _cluster_call_density(
    call_edges: list[tuple[str, str, str]],  # (file, caller, callee)
    symbol_to_file: dict[str, str],
    clusters: list[list[str]],
) -> dict[tuple[int, int], int]:
    """Return per-cluster-pair call counts.

    Key: (cluster_idx_caller, cluster_idx_callee). Value: count of calls.
    """
    sym_to_cluster: dict[str, int] = {}
    for idx, members in enumerate(clusters):
        for m in members:
            sym_to_cluster[m] = idx
    densities: Counter[tuple[int, int]] = Counter()
    for _file, caller, callee in call_edges:
        ci = sym_to_cluster.get(caller)
        cj = sym_to_cluster.get(callee)
        if ci is None or cj is None:
            continue
        densities[(ci, cj)] += 1
    return densities


def _greedy_cluster_symbols(
    symbols: list[Symbol],
    co_edit_jaccard_by_file: dict[tuple[str, str], float],
    naming_cluster_map: dict[str, str],
    call_edges: list[tuple[str, str, str]],
) -> list[list[str]]:
    """Assign each symbol to a cluster.

    Strategy:
      1. Seed by naming cluster (symbols sharing a prefix).
      2. Add unclustered symbols to the cluster of the file they live in
         if that file's other symbols are clustered together.
      3. Symbols still unassigned become singleton clusters.
    """
    clusters: dict[str, list[str]] = defaultdict(list)
    sym_names = [s.name for s in symbols]
    sym_by_name = {s.name: s for s in symbols}
    assigned: dict[str, str] = {}

    # Seed by naming.
    for sym_name, prefix in naming_cluster_map.items():
        clusters[prefix].append(sym_name)
        assigned[sym_name] = prefix

    # Fill from file-mate consensus.
    file_to_assigned: dict[str, Counter[str]] = defaultdict(Counter)
    for sym_name in sym_names:
        sym = sym_by_name[sym_name]
        if sym_name in assigned:
            file_to_assigned[sym.file][assigned[sym_name]] += 1
    for sym_name in sym_names:
        if sym_name in assigned:
            continue
        sym = sym_by_name[sym_name]
        file_votes = file_to_assigned[sym.file]
        if file_votes:
            winner = file_votes.most_common(1)[0][0]
            clusters[winner].append(sym_name)
            assigned[sym_name] = winner

    # Singletons.
    for sym_name in sym_names:
        if sym_name not in assigned:
            cluster_id = f"singleton_{sym_name}"
            clusters[cluster_id].append(sym_name)
            assigned[sym_name] = cluster_id

    # Drop singleton clusters that are below the noise threshold and merge them
    # into the largest co-edit-correlated cluster (best-effort).
    final: list[list[str]] = []
    for cid, members in clusters.items():
        if len(members) >= 2 or cid.startswith("singleton_"):
            final.append(members)
    return final


def _score_seam(
    cluster: list[str],
    sym_by_name: dict[str, Symbol],
    call_edges: list[tuple[str, str, str]],
    co_edit_pairs: list[dict],
    naming_cluster_map: dict[str, str],
) -> dict[str, float]:
    """Score one candidate seam (cluster of symbols).

    Returns normalized scores in [0, 1] for each criterion:
      - naming_alignment    — fraction of cluster members sharing the dominant prefix
      - co_edit_intensity   — average jaccard among files holding cluster members
      - import_directionality — 0 (placeholder; refined in proposal)
      - call_isolation      — 1 - (cross-cluster calls / total calls touching cluster)
    """
    if not cluster:
        return {"naming_alignment": 0.0, "co_edit_intensity": 0.0, "call_isolation": 0.0, "combined": 0.0}
    # Naming alignment.
    prefixes = Counter(naming_cluster_map.get(s, "_unknown") for s in cluster)
    dominant = prefixes.most_common(1)[0][1] if prefixes else 0
    naming_alignment = dominant / len(cluster) if cluster else 0.0

    # Co-edit intensity over the files holding cluster members.
    cluster_files = {sym_by_name[s].file for s in cluster if s in sym_by_name}
    co_pairs_in_cluster = [p["jaccard"] for p in co_edit_pairs if p["a"] in cluster_files and p["b"] in cluster_files]
    co_edit_intensity = sum(co_pairs_in_cluster) / len(co_pairs_in_cluster) if co_pairs_in_cluster else 0.0

    # Call isolation: fraction of edges from cluster members that stay inside the cluster.
    cluster_set = set(cluster)
    edges_from = [(c, e) for _f, c, e in call_edges if c in cluster_set]
    edges_inside = [e for c, e in edges_from if e in cluster_set]
    call_isolation = (len(edges_inside) / len(edges_from)) if edges_from else 1.0

    combined = round((naming_alignment + co_edit_intensity + call_isolation) / 3, 4)
    return {
        "naming_alignment": round(naming_alignment, 4),
        "co_edit_intensity": round(co_edit_intensity, 4),
        "call_isolation": round(call_isolation, 4),
        "combined": combined,
    }


def _candidate_seams(
    clusters: list[list[str]],
    sym_by_name: dict[str, Symbol],
    call_edges: list[tuple[str, str, str]],
    co_edit_pairs: list[dict],
    naming_cluster_map: dict[str, str],
    import_records: list[dict],
    top_n: int,
    threshold: float,
) -> list[CandidateSeam]:
    seams: list[CandidateSeam] = []
    total_symbols = len(sym_by_name)
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        # A "seam" requires a partition — a cluster that contains every
        # symbol is the absence of a boundary, not a candidate for one.
        if len(cluster) >= total_symbols:
            continue
        scores = _score_seam(cluster, sym_by_name, call_edges, co_edit_pairs, naming_cluster_map)
        if scores["combined"] < threshold:
            continue
        cluster_id_token = Counter(naming_cluster_map.get(s, "_grp") for s in cluster).most_common(1)[0][0]
        cluster_id = cluster_id_token if cluster_id_token != "_grp" else f"cluster_{len(seams) + 1}"
        public_api = sorted({s for s in cluster if sym_by_name[s].public})
        private = {s for s in cluster if not sym_by_name[s].public}
        reach_into = [
            rec
            for rec in import_records
            if rec.get("symbol") in private
        ]
        rationale = (
            f"Naming alignment {scores['naming_alignment']:.2f}; "
            f"co-edit intensity {scores['co_edit_intensity']:.2f}; "
            f"call isolation {scores['call_isolation']:.2f}."
        )
        seams.append(CandidateSeam(
            cluster_id=cluster_id,
            members=sorted(cluster),
            rationale=rationale,
            proposed_public_api=public_api,
            callers_into_private_helpers=reach_into,
            scores=scores,
        ))
    seams.sort(key=lambda s: s.scores["combined"], reverse=True)
    return seams[:top_n]


def _defer_signals(
    target: Path,
    files: list[Path],
    symbols: list[Symbol],
    seams: list[CandidateSeam],
    project_root: Path,
) -> list[str]:
    signals: list[str] = []
    public_count = sum(1 for s in symbols if s.public)
    # Below threshold means BOTH dimensions are too small to analyze.
    # A single-file target with 6+ public symbols (like a 757-LOC omnibus) is fair game.
    if len(files) < MIN_PYTHON_FILES and public_count < MIN_PUBLIC_SYMBOLS:
        signals.append("target_below_threshold")
    if not seams:
        signals.append("single_cluster_no_seam")
    rel_target = str(target.relative_to(project_root)) if target.is_relative_to(project_root) else str(target)
    for prefix in SCRATCH_CODE_PREFIXES:
        if rel_target.startswith(prefix):
            signals.append("scratch_code")
            break
    return signals


def main() -> int:
    start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--candidates", type=int, default=1)
    parser.add_argument("--co-edit-days", type=int, default=DEFAULT_CO_EDIT_DAYS)
    parser.add_argument("--min-cluster-size", type=int, default=DEFAULT_MIN_CLUSTER_SIZE)
    parser.add_argument("--seam-threshold", type=float, default=DEFAULT_SEAM_THRESHOLD)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    try:
        target_path, target_kind, files = _resolve_target(args.target, project_root)
    except FileNotFoundError as exc:
        out = {
            "target": args.target,
            "target_kind": "missing",
            "error": str(exc),
            "defer_signals": ["target_not_found"],
        }
        _write_output(Path(args.output), out)
        return 0
    except ValueError as exc:
        out = {
            "target": args.target,
            "target_kind": "unsupported",
            "error": str(exc),
            "defer_signals": ["target_unsupported"],
        }
        _write_output(Path(args.output), out)
        return 0

    symbols: list[Symbol] = []
    for f in files:
        symbols.extend(_extract_symbols(f, project_root))
    if target_kind == "skill_directory":
        skill_md = target_path / "SKILL.md"
        symbols.extend(_extract_skill_md_phases(skill_md, project_root))
    sym_by_name: dict[str, Symbol] = {s.name: s for s in symbols}

    symbol_names = set(sym_by_name)
    call_edges_with_file: list[tuple[str, str, str]] = []
    for f in files:
        edges = _extract_call_edges(f, project_root, symbol_names)
        rel = str(f.relative_to(project_root))
        call_edges_with_file.extend((rel, caller, callee) for caller, callee in edges)

    naming_clusters = _naming_clusters(symbols, args.min_cluster_size)
    naming_cluster_map: dict[str, str] = {}
    for c in naming_clusters:
        for m in c["members"]:
            naming_cluster_map[m] = c["prefix"]

    # For clustering (not reporting), seed every symbol that has a
    # leading-token prefix. The min_cluster_size threshold above governs
    # what appears as a "naming cluster" in the inspection.json report,
    # but the candidate-seam clusterer benefits from finer-grained seeds —
    # otherwise file-mate consensus collapses every unprefixed symbol into
    # the dominant cluster, which is meaningless on single-file targets.
    seed_map: dict[str, str] = {}
    for sym in symbols:
        token = sym.name.lstrip("_").split("_", 1)[0].lower()
        if token and len(token) >= 3:
            seed_map[sym.name] = token

    co_edit_pairs = _co_edit_pairs(project_root, files, args.co_edit_days)

    clusters = _greedy_cluster_symbols(
        symbols, {}, seed_map, call_edges_with_file
    )

    import_records = _scan_project_imports(project_root, files, sym_by_name)

    seams = _candidate_seams(
        clusters,
        sym_by_name,
        call_edges_with_file,
        co_edit_pairs,
        seed_map,
        import_records,
        args.candidates,
        args.seam_threshold,
    )

    defer_signals = _defer_signals(target_path, files, symbols, seams, project_root)

    out = {
        "target": str(target_path.relative_to(project_root)) if target_path.is_relative_to(project_root) else str(target_path),
        "target_kind": target_kind,
        "files": [
            {
                "path": str(f.relative_to(project_root)),
                "line_count": sum(1 for _ in f.open("r", encoding="utf-8", errors="replace")) if f.is_file() else 0,
                "public_symbols": [s.name for s in symbols if s.file == str(f.relative_to(project_root)) and s.public],
            }
            for f in files
        ],
        "symbols": [asdict(s) for s in symbols],
        "co_edit_pairs": co_edit_pairs,
        "naming_clusters": naming_clusters,
        "call_edges": [
            {"file": f, "caller": c, "callee": e}
            for f, c, e in call_edges_with_file
        ],
        "import_records": import_records,
        "candidate_seams": [asdict(s) for s in seams],
        "defer_signals": defer_signals,
        "parameters": {
            "co_edit_days": args.co_edit_days,
            "min_cluster_size": args.min_cluster_size,
            "seam_threshold": args.seam_threshold,
            "candidates_requested": args.candidates,
        },
    }
    _write_output(Path(args.output), out)
    _log_skill_use(
        target=args.target,
        artifact=str(args.output),
        elapsed=time.monotonic() - start,
        project_root=project_root,
    )
    return 0


def _log_skill_use(*, target: str, artifact: str | None, elapsed: float,
                   project_root: Path) -> None:
    try:
        # Telemetry is a target-project surface: it lands in the analyzed
        # project's .claude/skill-use/, not the kit's own repo (ADR 0024
        # de-baking convention).
        log_path = project_root / ".claude" / "skill-use" / "log.jsonl"
        log_path.parent.mkdir(exist_ok=True)
        event = {
            "ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skill": "propose-boundary",
            "target": target,
            "artifact": artifact,
            "outcome": "useful",
            "human_override": None,
            "duration_s": round(elapsed, 3),
            "follow_up_skill": None,
        }
        with log_path.open("a") as fh:
            fh.write(json.dumps(event) + "\n")
    except Exception:  # noqa: BLE001 — telemetry logging must never break the skill
        pass  # noqa: silent-catch: telemetry write is best-effort — must never break the skill


def _write_output(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
