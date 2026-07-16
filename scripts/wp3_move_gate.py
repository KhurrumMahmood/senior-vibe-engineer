#!/usr/bin/env python3
"""Blocking WP3-local evidence gate for tracked foundation/exemplar moves.
Validates Git moves, ADR 0024 concept evidence, ADR 0028 self-anchors, batch
imports/assets, and changed-file disk targets without moving or mutating ADRs.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
CONCEPT_SCANNER = TOOLKIT_ROOT / ".claude/skills/find-concept-divergence/scripts/scan.py"
REQUIRED_NON_REWRITE_CLASSES = {"ambiguous prose", "unsupported import forms"}
IMPORT_SMOKE = r"""
import importlib.util
import pathlib
import sys
root = pathlib.Path(sys.argv[1]).resolve()
for number, raw in enumerate(sys.argv[2:]):
    path = (root / raw).resolve()
    sys.path[:0] = [str(root), str(path.parent)]
    spec = importlib.util.spec_from_file_location(f"wp3_move_smoke_{number}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot create import spec for {raw}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    print(f"imported {raw}")
""".strip()


@dataclass(frozen=True)
class Anchor:
    line: int
    expression: str
    target: str | None
    classification: str


def _finding(findings: list[dict[str, Any]], rule: str, message: str, **context: Any) -> None:
    findings.append({"rule": rule, "message": message, **context})


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


def _safe_rel(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        return None
    normalized = path.as_posix()
    return normalized[2:] if normalized.startswith("./") else normalized


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("evidence root must be an object")
    return data


def _diff(root: Path, base: str) -> tuple[list[str], list[tuple[str, str]]]:
    names = _run_git(root, "diff", "--name-only", "--diff-filter=ACMR", base, "--")
    statuses = _run_git(root, "diff", "--name-status", "-M20%", base, "--")
    if names.returncode or statuses.returncode:
        detail = names.stderr.strip() or statuses.stderr.strip() or "git diff failed"
        raise ValueError(detail)
    files = sorted(line for line in names.stdout.splitlines() if line)
    moves: list[tuple[str, str]] = []
    for line in statuses.stdout.splitlines():
        fields = line.split("\t")
        if fields and fields[0].startswith("R") and len(fields) == 3:
            moves.append((fields[1], fields[2]))
    return files, sorted(moves)


def _base_text(root: Path, base: str, relative: str) -> str | None:
    result = _run_git(root, "show", f"{base}:{relative}")
    return result.stdout if result.returncode == 0 else None


def _contains_anchor(node: ast.AST, anchored_names: set[str]) -> bool:
    return any(
        isinstance(child, ast.Name)
        and (child.id == "__file__" or child.id in anchored_names)
        for child in ast.walk(node)
    )


def _contains_file_literal(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Name) and child.id == "__file__" for child in ast.walk(node))


def _assignment_name(node: ast.Assign | ast.AnnAssign | ast.NamedExpr) -> str | None:
    targets: list[ast.expr]
    if isinstance(node, ast.Assign):
        targets = node.targets
    else:
        targets = [node.target]
    names = [target.id for target in targets if isinstance(target, ast.Name)]
    return names[0] if names else None


def _eval_path(node: ast.AST, file_path: Path, env: dict[str, Path]) -> Path | None:
    if isinstance(node, ast.Name):
        if node.id == "__file__":
            return file_path
        return env.get(node.id)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "Path" and len(node.args) == 1:
            return _eval_path(node.args[0], file_path, env)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in {"resolve", "absolute"}
            and not node.args
        ):
            value = _eval_path(node.func.value, file_path, env)
            return value.resolve() if value is not None else None
        return None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        value = _eval_path(node.value, file_path, env)
        return value.parent if value is not None else None
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, int)
    ):
        value = _eval_path(node.value.value, file_path, env)
        if value is None or node.slice.value < 0:
            return None
        try:
            return value.parents[node.slice.value]
        except IndexError:
            return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _eval_path(node.left, file_path, env)
        if left is None:
            return None
        if isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
            return left / node.right.value
        return None
    return None


def _relative_target(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    normalized = Path(os.path.normpath(path))
    try:
        return normalized.relative_to(root.resolve()).as_posix()
    except ValueError:
        return normalized.as_posix()


def _anchors_from_text(text: str, file_path: Path, root: Path) -> list[Anchor]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr))
    ]
    assignments.sort(key=lambda node: (node.lineno, node.col_offset))
    anchored_names: set[str] = set()
    for _ in range(len(assignments) + 1):
        changed = False
        for node in assignments:
            value = node.value
            name = _assignment_name(node)
            if name and name not in anchored_names and _contains_anchor(value, anchored_names):
                anchored_names.add(name)
                changed = True
        if not changed:
            break

    env: dict[str, Path] = {}
    anchors: list[Anchor] = []
    covered: set[int] = set()
    for node in assignments:
        value = node.value
        name = _assignment_name(node)
        if not _contains_anchor(value, anchored_names):
            continue
        covered.update(id(child) for child in ast.walk(value))
        resolved = _eval_path(value, file_path, env)
        if name and resolved is not None:
            env[name] = resolved
        expression = ast.get_source_segment(text, value) or ast.unparse(value)
        anchors.append(
            Anchor(
                line=node.lineno,
                expression=expression,
                target=_relative_target(resolved, root),
                classification="tractable" if resolved is not None else "unhandled",
            )
        )
    parents = {
        id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
    }
    direct_roots: dict[int, ast.expr] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or node.id != "__file__" or id(node) in covered:
            continue
        current: ast.AST = node
        while isinstance(parents.get(id(current)), ast.expr):
            parent = parents[id(current)]
            if id(parent) in covered:
                current = parent
                break
            current = parent
        if isinstance(current, ast.expr) and id(current) not in covered:
            direct_roots[id(current)] = current
    for node in sorted(direct_roots.values(), key=lambda item: (item.lineno, item.col_offset)):
        if not _contains_file_literal(node):
            continue
        resolved = _eval_path(node, file_path, env)
        expression = ast.get_source_segment(text, node) or ast.unparse(node)
        anchors.append(
            Anchor(
                line=node.lineno,
                expression=expression,
                target=_relative_target(resolved, root),
                classification="tractable" if resolved is not None else "unhandled",
            )
        )
    anchors.sort(key=lambda item: (item.line, item.expression))
    return anchors


def _inventory_anchors(
    root: Path,
    base: str,
    moves: list[dict[str, Any]],
    declared: Any,
    findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, int], str], dict[tuple[str, int], str]]:
    actual: list[dict[str, Any]] = []
    kinds: dict[tuple[str, int], str] = {}
    pins: dict[tuple[str, int], str] = {}
    declared_list = declared if isinstance(declared, list) else []
    declared_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in declared_list:
        if not isinstance(row, dict):
            continue
        pair = (_safe_rel(row.get("source_before")) or "", _safe_rel(row.get("source_after")) or "")
        declared_by_pair.setdefault(pair, []).append(row)

    for move in moves:
        before = _safe_rel(move.get("from"))
        after = _safe_rel(move.get("to"))
        if not before or not after:
            continue
        before_text = _base_text(root, base, before)
        after_path = root / after
        after_text = after_path.read_text(encoding="utf-8") if after_path.is_file() else None
        before_anchors = (
            _anchors_from_text(before_text, root / before, root)
            if before_text is not None and before.endswith(".py")
            else []
        )
        after_anchors = (
            _anchors_from_text(after_text, after_path, root)
            if after_text is not None and after.endswith(".py")
            else []
        )
        rows = sorted(
            declared_by_pair.get((before, after), []),
            key=lambda row: int(row.get("line_before", -1)),
        )
        if len(rows) != len(before_anchors) or len(rows) != len(after_anchors):
            _finding(
                findings,
                "anchor_inventory",
                "every pre/post self-anchor requires exactly one inventory row",
                source_before=before,
                source_after=after,
                before_count=len(before_anchors),
                after_count=len(after_anchors),
                declared_count=len(rows),
            )
        for index, row in enumerate(rows):
            if index >= len(before_anchors) or index >= len(after_anchors):
                continue
            old = before_anchors[index]
            new = after_anchors[index]
            expected = {
                "line_before": old.line,
                "line_after": new.line,
                "expression_before": old.expression,
                "expression_after": new.expression,
                "classification": (
                    "tractable"
                    if old.classification == new.classification == "tractable"
                    else "unhandled"
                ),
            }
            mismatches = {
                field: {"declared": row.get(field), "actual": value}
                for field, value in expected.items()
                if row.get(field) != value
            }
            classification = expected["classification"]
            if classification == "tractable":
                for field, value in {
                    "target_before": old.target,
                    "target_after": new.target,
                }.items():
                    if row.get(field) != value:
                        mismatches[field] = {"declared": row.get(field), "actual": value}
                target_before = old.target
                target_after = new.target
            else:
                target_before = _safe_rel(row.get("target_before"))
                target_after = _safe_rel(row.get("target_after"))
                if not target_before or not target_after:
                    _finding(
                        findings,
                        "anchor_target_pin",
                        "unhandled anchors require explicit bounded before/after target pins",
                        source_after=after,
                        line=new.line,
                    )
            if mismatches:
                _finding(
                    findings,
                    "anchor_target_mismatch",
                    "self-anchor inventory does not match the executable path expression",
                    source_after=after,
                    mismatches=mismatches,
                )
            if target_before != target_after:
                _finding(
                    findings,
                    "anchor_target_mismatch",
                    "the moved anchor no longer resolves to its pre-move target",
                    source_after=after,
                    target_before=target_before,
                    target_after=target_after,
                )
            note_key = "rewrite_note" if classification == "tractable" else "reviewer_note"
            if not isinstance(row.get(note_key), str) or len(row[note_key].strip()) < 20:
                _finding(
                    findings,
                    "anchor_classification",
                    f"{classification} anchor requires a substantive {note_key}",
                    source_after=after,
                    line=new.line,
                )
            kind = row.get("target_kind")
            if kind not in {"file", "directory"}:
                _finding(
                    findings,
                    "anchor_target_kind",
                    "target_kind must be file or directory",
                    source_after=after,
                    line=new.line,
                )
            else:
                kinds[(after, new.line)] = kind
                if target_after:
                    pins[(after, new.line)] = target_after
            actual.append(
                {
                    "batch": move.get("batch"),
                    "source_before": before,
                    "source_after": after,
                    **expected,
                    "target_before": target_before,
                    "target_after": target_after,
                    "target_kind": kind,
                }
            )

    expected_pairs = {
        (_safe_rel(move.get("from")) or "", _safe_rel(move.get("to")) or "")
        for move in moves
    }
    extra_pairs = sorted(set(declared_by_pair) - expected_pairs)
    if extra_pairs:
        _finding(
            findings,
            "anchor_inventory",
            "self-anchor rows may only describe declared moves",
            extra_pairs=extra_pairs,
        )
    return actual, kinds, pins


def _normalize_concept(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _bounded_scan_target(root: Path, raw: Any) -> str | None:
    relative = _safe_rel(raw)
    if not relative or relative == ".":
        return None
    try:
        (root / relative).resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return relative


def _load_glossary(root: Path) -> list[dict[str, Any]]:
    path = root / ".claude" / "contracts" / "concepts.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    concepts = data.get("concepts") if isinstance(data, dict) else None
    if not isinstance(concepts, list):
        raise ValueError("glossary must contain a concepts list")
    return [row for row in concepts if isinstance(row, dict)]


def _avoid_phrases(row: dict[str, Any]) -> set[str]:
    phrases: set[str] = set()
    for entry in row.get("avoid") or []:
        if isinstance(entry, str):
            phrase = entry.split("(", 1)[0].strip().strip("\"'").rstrip(",.;:")
            if phrase:
                phrases.add(phrase.casefold())
    return phrases


def _run_two_band(
    root: Path,
    rename: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    old = str(rename.get("old") or "")
    new = str(rename.get("new") or "")
    targets = [_bounded_scan_target(root, item) for item in rename.get("scan_targets") or []]
    targets = [item for item in targets if item]
    with tempfile.TemporaryDirectory(prefix="wp3-move-gate-") as raw_temp:
        temp = Path(raw_temp)
        output = temp / "findings.jsonl"
        report = temp / "report.md"
        command = [
            sys.executable,
            str(CONCEPT_SCANNER),
            "--project-root",
            str(root),
            "--glossary",
            str(root / ".claude" / "contracts" / "concepts.yaml"),
            "--output",
            str(output),
            "--report",
            str(report),
            *targets,
        ]
        completed = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False
        )
        raw_findings: list[dict[str, Any]] = []
        if completed.returncode == 0 and output.is_file():
            try:
                raw_findings = [
                    json.loads(line)
                    for line in output.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except json.JSONDecodeError as exc:
                _finding(findings, "two_band_unavailable", f"invalid scanner JSONL: {exc}")
        else:
            _finding(
                findings,
                "two_band_unavailable",
                "concept divergence scanner did not complete cleanly",
                exit_code=completed.returncode,
                stderr=completed.stderr,
            )
        retired = {str(term).casefold() for term in rename.get("retired_terms") or []}
        band3 = [
            row
            for row in raw_findings
            if row.get("band") == "superseded_co_occurrence"
            and _normalize_concept(str(row.get("concept") or ""))
            == _normalize_concept(old)
        ]
        band1 = [
            row
            for row in raw_findings
            if row.get("band") == "avoid_term_hit"
            and _normalize_concept(str(row.get("concept") or ""))
            in {_normalize_concept(old), _normalize_concept(new)}
            and str(row.get("term") or "").casefold() in retired
        ]
        if band3:
            _finding(
                findings,
                "superseded_identifier",
                "superseded_co_occurrence must be clean",
                old=old,
                new=new,
                hits=band3,
            )
        if band1:
            _finding(
                findings,
                "retired_prose",
                "avoid_term_hit must be clean; stale retired prose remains",
                old=old,
                new=new,
                hits=band1,
            )
        return {
            "old": old,
            "new": new,
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "bands": {
                "avoid_term_hit": band1,
                "superseded_co_occurrence": band3,
            },
        }


def _validate_renames(
    root: Path,
    base: str,
    moves: list[dict[str, Any]],
    renames: Any,
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = renames if isinstance(renames, list) else []
    if not rows:
        _finding(findings, "two_band_evidence", "at least one concept rename is required")
        return []
    try:
        glossary = _load_glossary(root)
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
        _finding(findings, "two_band_unavailable", f"cannot load concept glossary: {exc}")
        return []
    by_name = {
        _normalize_concept(str(row.get("name") or "")): row for row in glossary
    }
    reports: list[dict[str, Any]] = []
    for rename in rows:
        if not isinstance(rename, dict):
            _finding(findings, "two_band_evidence", "rename entries must be objects")
            continue
        old = str(rename.get("old") or "")
        new = str(rename.get("new") or "")
        old_row = by_name.get(_normalize_concept(old))
        new_row = by_name.get(_normalize_concept(new))
        if not old_row or not new_row or old_row.get("superseded_by") != new_row.get("name"):
            _finding(
                findings,
                "two_band_evidence",
                "old/new must be a glossary supersession pair",
                old=old,
                new=new,
            )
        retired_terms = rename.get("retired_terms")
        if not isinstance(retired_terms, list) or not retired_terms:
            _finding(findings, "avoid_scope", "retired_terms must be non-empty", old=old)
            retired_terms = []
        avoid = _avoid_phrases(old_row or {}) | _avoid_phrases(new_row or {})
        for term in retired_terms:
            normalized = str(term).strip().casefold()
            distinctive = len(normalized) >= 8 and (" " in normalized or "-" in normalized)
            if normalized not in avoid or not distinctive:
                _finding(
                    findings,
                    "avoid_scope",
                    "each retired phrasing needs a matching distinctively scoped avoid entry",
                    term=term,
                )

        expected_reviews: set[str] = set()
        lowered_terms = [str(term).casefold() for term in retired_terms]
        for move in moves:
            before = _safe_rel(move.get("from"))
            after = _safe_rel(move.get("to"))
            if not before or not after:
                continue
            old_text = _base_text(root, base, before) or ""
            if any(term in old_text.casefold() for term in lowered_terms):
                expected_reviews.add(after)
        reviews = rename.get("prose_review")
        reviews = reviews if isinstance(reviews, list) else []
        reviewed_files = {
            _safe_rel(review.get("file"))
            for review in reviews
            if isinstance(review, dict) and _safe_rel(review.get("file"))
        }
        if reviewed_files != expected_reviews:
            _finding(
                findings,
                "prose_review",
                "substantive prose review must cover every moved file containing retired prose",
                expected=sorted(expected_reviews),
                declared=sorted(reviewed_files),
            )
        for review in reviews:
            if not isinstance(review, dict):
                continue
            valid = (
                len(str(review.get("reviewer") or "").strip()) >= 3
                and len(str(review.get("before_summary") or "").strip()) >= 12
                and len(str(review.get("after_summary") or "").strip()) >= 12
                and review.get("before_summary") != review.get("after_summary")
                and len(str(review.get("rationale") or "").strip()) >= 24
            )
            if not valid:
                _finding(
                    findings,
                    "prose_review",
                    "prose review needs reviewer, distinct before/after summaries, and rationale",
                    file=review.get("file"),
                )
        targets = [_bounded_scan_target(root, item) for item in rename.get("scan_targets") or []]
        if not targets or any(target is None for target in targets):
            _finding(findings, "two_band_evidence", "scan_targets must be explicit bounded roots")
        elif any(
            not any(path == target or path.startswith(f"{target}/") for target in targets)
            for path in expected_reviews
        ):
            _finding(
                findings,
                "two_band_evidence",
                "scan_targets do not cover every affected moved file",
            )
        reports.append(_run_two_band(root, rename, findings))
    return reports


def _validate_smokes(
    root: Path,
    moves: list[dict[str, Any]],
    anchor_rows: list[dict[str, Any]],
    smokes: Any,
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    declared = smokes if isinstance(smokes, list) else []
    batches = sorted({str(move.get("batch") or "") for move in moves})
    by_batch = {
        str(row.get("batch") or ""): row for row in declared if isinstance(row, dict)
    }
    if sorted(by_batch) != batches or len(by_batch) != len(declared):
        _finding(
            findings,
            "batch_smoke_scope",
            "exactly one import-and-asset smoke is required per move batch",
            expected=batches,
            declared=sorted(by_batch),
        )
    reports: list[dict[str, Any]] = []
    for batch in batches:
        row = by_batch.get(batch, {})
        expected_imports = sorted(
            str(move["to"])
            for move in moves
            if str(move.get("batch") or "") == batch
            and str(move.get("to") or "").endswith(".py")
        )
        expected_assets = sorted(
            str(anchor["target_after"])
            for anchor in anchor_rows
            if str(anchor.get("batch") or "") == batch and anchor.get("target_after")
        )
        imports = sorted(row.get("imports") or [])
        assets = sorted(row.get("assets") or [])
        if imports != expected_imports or assets != expected_assets:
            _finding(
                findings,
                "batch_smoke_scope",
                "batch smoke must cover every moved Python file and pinned asset",
                batch=batch,
                expected_imports=expected_imports,
                declared_imports=imports,
                expected_assets=expected_assets,
                declared_assets=assets,
            )
        command = [sys.executable, "-c", IMPORT_SMOKE, str(root), *expected_imports]
        completed = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False
        )
        if completed.returncode:
            _finding(
                findings,
                "batch_import_smoke",
                "moved Python batch did not import cleanly",
                batch=batch,
                exit_code=completed.returncode,
                stderr=completed.stderr,
            )
        asset_results: list[dict[str, Any]] = []
        batch_kinds = {
            str(anchor.get("target_after")): anchor.get("target_kind")
            for anchor in anchor_rows
            if str(anchor.get("batch") or "") == batch
        }
        for asset in expected_assets:
            asset_path = root / asset
            kind = str(batch_kinds.get(asset) or "")
            clean = kind in {"file", "directory"} and _target_type(asset_path, kind)
            asset_results.append({"path": asset, "target_kind": kind, "clean": clean})
            if not clean:
                _finding(
                    findings,
                    "batch_asset_smoke",
                    "pinned batch asset is missing or has the wrong type",
                    batch=batch,
                    path=asset,
                    target_kind=kind,
                )
        reports.append(
            {
                "batch": batch,
                "command": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "assets": expected_assets,
                "asset_results": asset_results,
            }
        )
    return reports


def _target_type(path: Path, kind: str) -> bool:
    return path.is_file() if kind == "file" else path.is_dir()


def _disk_scan(
    root: Path,
    diff_files: list[str],
    declared: Any,
    kinds: dict[tuple[str, int], str],
    pins: dict[tuple[str, int], str],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    declared_files = sorted(declared.get("files") or []) if isinstance(declared, dict) else []
    if declared_files != diff_files:
        _finding(
            findings,
            "disk_scan_scope",
            "disk scan must name the complete non-deleted Git diff",
            expected=diff_files,
            declared=declared_files,
        )
    scanned: list[dict[str, Any]] = []
    for relative in diff_files:
        path = root / relative
        if not path.is_file() or path.suffix != ".py":
            continue
        try:
            anchors = _anchors_from_text(path.read_text(encoding="utf-8"), path, root)
        except UnicodeDecodeError:
            _finding(findings, "disk_scan_unreadable", "changed Python file is not UTF-8", file=relative)
            continue
        for anchor in anchors:
            entry = {
                "file": relative,
                "line": anchor.line,
                "expression": anchor.expression,
                "target": anchor.target,
                "classification": anchor.classification,
            }
            scanned.append(entry)
            if anchor.classification != "tractable" or anchor.target is None:
                pinned = pins.get((relative, anchor.line))
                if not pinned:
                    _finding(
                        findings,
                        "disk_anchor_unhandled",
                        "full-diff scan cannot resolve an unpinned changed self-anchor",
                        **entry,
                    )
                    continue
                entry["target"] = pinned
                entry["pin_used"] = True
            target = Path(str(entry["target"]))
            target_path = target if target.is_absolute() else root / target
            if not target_path.exists():
                _finding(
                    findings,
                    "disk_target_missing",
                    "full-diff self-anchor target does not exist",
                    **entry,
                )
                continue
            kind = kinds.get((relative, anchor.line))
            if kind and not _target_type(target_path, kind):
                _finding(
                    findings,
                    "disk_target_type",
                    f"self-anchor target exists but is not the required {kind}",
                    target_kind=kind,
                    **entry,
                )
    return {"files": diff_files, "anchors": scanned}


def _validate_non_rewrite(root: Path, ack: Any, findings: list[dict[str, Any]]) -> None:
    if not isinstance(ack, dict):
        _finding(findings, "non_rewrite_ack", "move-tool non-rewrite acknowledgment is required")
        return
    document = _safe_rel(ack.get("document"))
    path = root / document if document else None
    try:
        content = path.read_text(encoding="utf-8") if path else ""
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path else ""
    except (OSError, UnicodeDecodeError):
        content = ""
        digest = ""
    classes = set(ack.get("acknowledged_classes") or [])
    omission = str(ack.get("acknowledged_omission") or "").casefold()
    normalized_content = " ".join(content.casefold().split())
    omission_names_gap = (
        "self-anchored" in omission
        and "not documented" in omission
        and ("not rewritten" in omission or "or rewritten" in omission)
    )
    valid = (
        bool(document)
        and digest == ack.get("sha256")
        and classes == REQUIRED_NON_REWRITE_CLASSES
        and all(item in normalized_content for item in REQUIRED_NON_REWRITE_CLASSES)
        and omission_names_gap
        and len(str(ack.get("reviewer") or "").strip()) >= 3
    )
    if not valid:
        _finding(
            findings,
            "non_rewrite_ack",
            "acknowledge the hashed move-tool non-rewrite list and its self-anchor omission",
        )


def _validate_lessons(root: Path, capture: Any, findings: list[dict[str, Any]]) -> None:
    primary_rules = sorted({row["rule"] for row in findings if not row["rule"].startswith("lesson_")})
    declared = (
        sorted(set(capture.get("fired_rules") or [])) if isinstance(capture, dict) else []
    )
    if declared != primary_rules:
        _finding(
            findings,
            "lesson_capture_missing",
            "declared fired_rules must exactly match every fired gate rule",
            expected=primary_rules,
            declared=declared,
        )
        return
    if not primary_rules:
        return
    log = _safe_rel(capture.get("log")) if isinstance(capture, dict) else None
    try:
        lines = (root / log).read_text(encoding="utf-8").splitlines() if log else []
    except (OSError, UnicodeDecodeError):
        lines = []
    missing = []
    for rule in primary_rules:
        marker = f"[wp3-move-gate:{rule}]"
        if not any(
            marker in line and "cause:" in line.casefold() and "how:" in line.casefold()
            for line in lines
        ):
            missing.append(rule)
    if missing:
        _finding(
            findings,
            "lesson_capture_missing",
            "each fired rule needs a lesson line with marker, cause, and how",
            missing=missing,
            log=log,
        )


# spec:portable-skill-layer-distribution::IM-3
def run_gate(*, evidence_path: Path, project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    findings: list[dict[str, Any]] = []
    generated: dict[str, Any] = {
        "two_band": [],
        "self_anchors": [],
        "batch_smokes": [],
        "disk_scan": {"files": [], "anchors": []},
    }
    try:
        evidence = _read_json(evidence_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {
            "schema_version": 1,
            "ok": False,
            "findings": [{"rule": "evidence_schema", "message": str(exc)}],
            "evidence": generated,
        }
    if evidence.get("schema_version") != 1:
        _finding(findings, "evidence_schema", "schema_version must equal 1")
    base = str(evidence.get("base_revision") or "")
    try:
        diff_files, actual_moves = _diff(root, base)
    except ValueError as exc:
        _finding(findings, "git_diff", str(exc))
        diff_files, actual_moves = [], []
    moves = evidence.get("moves")
    moves = moves if isinstance(moves, list) else []
    declared_moves: list[tuple[str, str]] = []
    batches_valid = True
    for move in moves:
        if not isinstance(move, dict):
            batches_valid = False
            continue
        before = _safe_rel(move.get("from"))
        after = _safe_rel(move.get("to"))
        batch = str(move.get("batch") or "").strip()
        if not before or not after or not batch:
            batches_valid = False
            continue
        declared_moves.append((before, after))
    if sorted(declared_moves) != actual_moves or not actual_moves or not batches_valid:
        _finding(
            findings,
            "move_scope",
            "declared moves must exactly match tracked Git renames and have batch IDs",
            actual=actual_moves,
            declared=sorted(declared_moves),
        )
    declared_diff = sorted(evidence.get("diff_files") or [])
    if declared_diff != diff_files:
        _finding(
            findings,
            "diff_scope",
            "diff_files must exactly match the complete non-deleted Git diff",
            actual=diff_files,
            declared=declared_diff,
        )

    generated["two_band"] = _validate_renames(
        root, base, moves, evidence.get("concept_renames"), findings
    )
    generated["self_anchors"], kinds, pins = _inventory_anchors(
        root, base, moves, evidence.get("self_anchors"), findings
    )
    generated["batch_smokes"] = _validate_smokes(
        root, moves, generated["self_anchors"], evidence.get("batch_smokes"), findings
    )
    generated["disk_scan"] = _disk_scan(
        root, diff_files, evidence.get("disk_scan"), kinds, pins, findings
    )
    _validate_non_rewrite(root, evidence.get("non_rewrite_ack"), findings)
    _validate_lessons(root, evidence.get("lesson_capture"), findings)
    return {
        "schema_version": 1,
        "ok": not findings,
        "base_revision": base,
        "project_root": str(root),
        "findings": findings,
        "evidence": generated,
        "safety_only": {
            "adr_0024_status_mutated": False,
            "adr_0028_status_mutated": False,
            "embodiment_mutated": False,
        },
    }


# spec:portable-skill-layer-distribution::IM-4
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    result = run_gate(evidence_path=args.evidence, project_root=args.project_root)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
