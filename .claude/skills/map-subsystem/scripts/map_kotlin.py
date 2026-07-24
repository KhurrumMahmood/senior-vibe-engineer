#!/usr/bin/env python3
"""Render a bounded Kotlin/JVM subsystem map from copied Kotlin fact providers."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any


LIMITS = [
    "Only exact lowercase .kt sources enumerated by a current complete kotlin-project.json are eligible; generated, test, vendor, build, tooling, symlink, .kts, and Java inputs are excluded from the selected map.",
    "Qualified declarations and direct resolved calls/references come from the pinned Kotlin/JVM 2.4.10 compiler helper; unresolved rows remain counts/examples and never become inferred edges.",
    "Public and private surfaces report Kotlin descriptor visibility only; internal/protected/local visibility, JVM file facades, binary compatibility, and external consumers remain separate boundaries.",
    "Explicit override descriptors are retained on declarations but do not establish runtime dispatch edges or complete override hierarchies.",
    "Reflection, callable references, delegated properties, dynamic/framework registration, generated KAPT/KSP inputs, compiler plugins, Gradle variants, Java callers/sources, expect/actual, Android, Multiplatform, and runtime reachability are not mapped.",
]
EMPTY_KEYS = (
    "packages",
    "files",
    "qualified_declarations",
    "public_surface",
    "private_surface",
    "other_visibility",
    "direct_resolved_calls",
    "direct_resolved_references",
    "package_edges",
)


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _json(path: Path, payload: Any) -> None:
    _atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load copied Kotlin provider: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _providers() -> tuple[ModuleType | None, ModuleType | None]:
    skills = next(
        (
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "_kotlin/kotlin_facts.py").is_file()
            or (parent / "_kotlin-semantic/kotlin_semantic_facts.py").is_file()
        ),
        None,
    )
    if skills is None:
        return None, None
    lexical_path = skills / "_kotlin/kotlin_facts.py"
    semantic_path = skills / "_kotlin-semantic/kotlin_semantic_facts.py"
    lexical = _load(lexical_path, "kotlin_map_lexical") if lexical_path.is_file() else None
    semantic = (
        _load(semantic_path, "kotlin_map_semantic") if semantic_path.is_file() else None
    )
    return lexical, semantic


def _safe_destination(root: Path, supplied: Path, allowed: Path, label: str) -> Path:
    destination = Path(
        os.path.abspath(supplied if supplied.is_absolute() else root / supplied)
    )
    try:
        relative = destination.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"{label} must stay beneath {allowed.relative_to(root)}") from exc
    if not relative.parts:
        raise ValueError(f"{label} must name a file")
    current = allowed
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} cannot traverse a symbolic link")
    return destination


def _safe_target(root: Path, supplied: Path) -> Path:
    target = supplied if supplied.is_absolute() else root / supplied
    target = target.resolve(strict=True)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("target must stay inside project root") from exc
    if target.is_symlink() or not (target.is_file() or target.is_dir()):
        raise ValueError("target must be a regular file or directory")
    return target


def _selected(root: Path, target: Path, relative: str) -> bool:
    candidate = root / relative
    return candidate == target if target.is_file() else target in candidate.parents


def _empty(
    *,
    name: str,
    target: Path,
    status: str,
    failure_kind: str,
    lexical: dict[str, Any] | None = None,
    semantic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "kotlin-jvm-subsystem-map-v1",
        "name": name,
        "target": str(target),
        "status": status,
        "failure_kind": failure_kind,
        "manifest_state": "incomplete",
        "semantic_authority": {},
        "native_checks": {},
        "source_preservation": {
            "verified": bool(
                lexical and lexical.get("source_manifest", {}).get("preserved")
            )
        },
        "analysis": {"kotlin": lexical, "kotlin_semantic": semantic},
        **{key: [] for key in EMPTY_KEYS},
        "unresolved": {"calls": 0, "references": 0, "examples": []},
        "limits": LIMITS,
    }


def _declaration(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": row["path"],
        "line": row["line"],
        "kind": row["kind"],
        "name": row.get("name"),
        "fq_name": row.get("fq_name"),
        "signature": row.get("signature"),
        "visibility": row.get("visibility"),
        "override": row.get("override", False),
        "overrides": row.get("overrides", []),
        "extension_receiver": row.get("extension_receiver"),
    }


def _direction(source_selected: bool, target_selected: bool) -> str:
    if source_selected and target_selected:
        return "internal"
    return "outbound" if source_selected else "inbound"


def _edge(row: dict[str, Any], direction: str) -> dict[str, Any]:
    caller = row.get("caller") or {}
    return {
        "path": row["path"],
        "line": row["line"],
        "role": row.get("role"),
        "source": row.get("source"),
        "caller_fq_name": caller.get("fq_name"),
        "caller_signature": caller.get("signature"),
        "target_fq_name": row.get("target_fq_name"),
        "target_signature": row.get("target_signature"),
        "direction": direction,
    }


def _map_payload(
    *,
    root: Path,
    name: str,
    target: Path,
    lexical: dict[str, Any],
    semantic: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    project = lexical["project_manifest"]
    semantic_manifest = semantic["manifest"]
    if (
        project["sources"] != semantic_manifest["sources"]
        or project["tests"] != semantic_manifest["tests"]
    ):
        return {}, "kotlin_manifest_universe_mismatch"
    lexical_hashes = {
        row["file"]: row.get("source_sha256") for row in lexical["inventory"]
    }
    if any(
        lexical_hashes.get(row["path"]) != row["sha256"]
        for row in semantic["source_inventory"]
    ):
        return {}, "kotlin_provider_snapshot_mismatch"
    lexical_files = {row["file"]: row for row in lexical["files"]}
    selected_paths = {
        path for path in project["sources"] if _selected(root, target, path)
    }
    if not selected_paths:
        return {}, "kotlin_target_has_no_manifest_sources"
    selected_declarations = [
        row
        for row in semantic["declarations"]
        if row.get("role") == "source" and row["path"] in selected_paths
    ]
    declaration_rows = sorted(
        (_declaration(row) for row in selected_declarations),
        key=lambda row: (row["path"], row["line"], row["signature"] or ""),
    )
    all_declarations = [
        row for row in semantic["declarations"] if row.get("role") == "source"
    ]
    signature_paths = {
        row.get("signature"): row["path"]
        for row in all_declarations
        if row.get("signature")
    }
    selected_signatures = {
        row.get("signature") for row in selected_declarations if row.get("signature")
    }
    package_by_path = {
        path: row["package"] for path, row in lexical_files.items()
    }
    packages: dict[str, list[str]] = defaultdict(list)
    for path in sorted(selected_paths):
        packages[package_by_path[path]].append(path)
    files = []
    for path in sorted(selected_paths):
        declarations = [row for row in declaration_rows if row["path"] == path]
        files.append(
            {
                "path": path,
                "package": package_by_path[path],
                "loc": len((root / path).read_text(encoding="utf-8").splitlines()),
                "source_sha256": lexical_hashes[path],
                "declarations": len(declarations),
                "public": sum(row["visibility"] == "public" for row in declarations),
                "private": sum(row["visibility"] == "private" for row in declarations),
                "other_visibility": sum(
                    row["visibility"] not in {"public", "private"}
                    for row in declarations
                ),
            }
        )
    calls = []
    for row in semantic["calls"]:
        if not row.get("resolved"):
            continue
        source_selected = row["path"] in selected_paths
        target_selected = row.get("target_signature") in selected_signatures
        if source_selected or target_selected:
            calls.append(_edge(row, _direction(source_selected, target_selected)))
    references = []
    seen_references: set[tuple[Any, ...]] = set()
    for row in semantic["references"]:
        if not row.get("resolved"):
            continue
        source_selected = row["path"] in selected_paths
        target_selected = row.get("target_signature") in selected_signatures
        if not (source_selected or target_selected):
            continue
        edge = _edge(row, _direction(source_selected, target_selected))
        key = (
            edge["path"], edge["line"], edge["source"], edge["caller_signature"],
            edge["target_signature"], edge["direction"],
        )
        if key not in seen_references:
            seen_references.add(key)
            references.append(edge)
    unresolved_rows = [
        {"kind": kind, "path": row["path"], "line": row["line"], "source": row.get("source")}
        for kind, rows in (("call", semantic["calls"]), ("reference", semantic["references"]))
        for row in rows
        if row["path"] in selected_paths and not row.get("resolved")
    ]
    package_edges = set()
    for edge in calls:
        if edge["path"] not in selected_paths:
            continue
        target_path = signature_paths.get(edge["target_signature"])
        if target_path is None:
            continue
        source_package = package_by_path[edge["path"]]
        target_package = package_by_path[target_path]
        if source_package != target_package:
            package_edges.add((source_package, target_package, edge["direction"]))
    authority = semantic["semantic_authority"]
    tools = semantic["tools"]
    native = semantic["commands"]
    payload = {
        "schema_version": "kotlin-jvm-subsystem-map-v1",
        "name": name,
        "target": target.relative_to(root).as_posix(),
        "status": "complete",
        "failure_kind": "none",
        "manifest_state": "current-complete-and-coherent",
        "semantic_authority": {
            "kind": authority["kind"],
            "kotlin_version": authority["kotlin_version"],
            "compiler_jar_sha256": tools["compiler_jar"]["sha256"],
            "stdlib_jar_sha256": tools["stdlib_jar"]["sha256"],
            "helper_sha256": authority["helper_sha256"],
            "fact_pack_sha256": semantic["fact_pack_sha256"],
        },
        "native_checks": {
            "lexical_evidence_state": lexical["native_evidence"]["state"],
            "test_returncode": native["test"]["returncode"],
            "test_stdout": native["test"]["stdout"],
            "smoke_returncode": native["smoke"]["returncode"],
            "smoke_stdout": native["smoke"]["stdout"],
        },
        "source_preservation": {
            "verified": lexical["source_manifest"]["preserved"],
            "source_manifest_sha256": semantic["source_manifest_sha256"],
            "lexical_before_sha256": lexical["source_manifest"]["before_sha256"],
            "lexical_after_sha256": lexical["source_manifest"]["after_sha256"],
        },
        "analysis": {"kotlin": lexical, "kotlin_semantic": semantic},
        "packages": [
            {"name": package, "files": paths} for package, paths in sorted(packages.items())
        ],
        "files": files,
        "qualified_declarations": declaration_rows,
        "public_surface": [row for row in declaration_rows if row["visibility"] == "public"],
        "private_surface": [row for row in declaration_rows if row["visibility"] == "private"],
        "other_visibility": [
            row for row in declaration_rows if row["visibility"] not in {"public", "private"}
        ],
        "direct_resolved_calls": sorted(
            calls, key=lambda row: (row["path"], row["line"], row["target_signature"] or "")
        ),
        "direct_resolved_references": sorted(
            references,
            key=lambda row: (row["path"], row["line"], row["target_signature"] or ""),
        ),
        "package_edges": [
            {"source_package": source, "target_package": destination, "direction": direction}
            for source, destination, direction in sorted(package_edges)
        ],
        "unresolved": {
            "calls": sum(row["kind"] == "call" for row in unresolved_rows),
            "references": sum(row["kind"] == "reference" for row in unresolved_rows),
            "examples": unresolved_rows[:20],
        },
        "limits": LIMITS,
    }
    return payload, None


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "---",
        f"subsystem: {payload['name']}",
        f"target: {payload['target']}",
        f"files: {len(payload['files'])}",
        f"public_symbols: {len(payload['public_surface'])}",
        "---",
        "",
        f"# {payload['name']}",
        "",
        f"Status: **{payload['status']}**",
        f"Manifest: **{payload['manifest_state']}**",
        "",
    ]
    if payload["status"] != "complete":
        lines.extend(
            [
                f"No map is available: `{payload['failure_kind']}`.",
                "",
                "## Limits",
                "",
                *[f"- {item}" for item in LIMITS],
                "",
            ]
        )
        return "\n".join(lines)
    lines.extend(["## Files", "", "| Path | Package | LOC | Public | Private |", "|---|---|---:|---:|---:|"])
    lines.extend(
        f"| `{row['path']}` | `{row['package']}` | {row['loc']} | {row['public']} | {row['private']} |"
        for row in payload["files"]
    )
    lines.extend(["", "## Qualified declarations", ""])
    lines.extend(
        f"- `{row['fq_name']}` — `{row['visibility']}` `{row['signature']}`"
        for row in payload["qualified_declarations"]
    )
    lines.extend(
        [
            "",
            "## Dependency graph",
            "",
            f"Direct resolved calls/references: **{len(payload['direct_resolved_calls'])} / {len(payload['direct_resolved_references'])}**.",
            f"Unresolved calls/references retained: **{payload['unresolved']['calls']} / {payload['unresolved']['references']}**.",
            "",
        ]
    )
    lines.extend(
        f"- `{row['direction']}` `{row['caller_fq_name']}` → `{row['target_fq_name']}`"
        for row in payload["direct_resolved_calls"]
    )
    lines.extend(["", "## Limits", "", *[f"- {item}" for item in LIMITS], ""])
    return "\n".join(lines)


def _write(output: Path, evidence: Path, payload: dict[str, Any]) -> None:
    markdown = _markdown(payload)
    payload["artifacts"] = {
        "markdown": output.relative_to(Path(payload["analysis"]["kotlin"]["project_root"])).as_posix(),
        "markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
    }
    _atomic(output, markdown)
    _json(evidence, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--semantic-manifest", type=Path, default=Path("kotlin-semantic-project.json"))
    parser.add_argument("--kotlinc", required=True, type=Path)
    parser.add_argument("--java", required=True, type=Path)
    args = parser.parse_args(argv)
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.name) is None:
        parser.error("name must be a simple slug")
    try:
        root = args.project_root.resolve(strict=True)
        target = _safe_target(root, args.target)
        output = _safe_destination(
            root, args.output, root / ".engineering/docs/subsystems", "output"
        )
        evidence = _safe_destination(
            root, args.evidence, root / "reports/map" / args.name, "evidence"
        )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    fact_pack = root / f"reports/kotlin-semantic/map-subsystem/{args.name}-facts.json"
    for path in (output, evidence, fact_pack):
        path.unlink(missing_ok=True)
    lexical_provider, semantic_provider = _providers()
    if lexical_provider is None or semantic_provider is None:
        missing = "kotlin_lexical_provider_missing" if lexical_provider is None else "kotlin_semantic_provider_missing"
        lexical = {
            "status": "partial",
            "failure_kind": missing,
            "project_root": str(root),
            "source_manifest": {"preserved": True},
        }
        payload = _empty(
            name=args.name, target=target, status="partial", failure_kind=missing, lexical=lexical
        )
        _write(output, evidence, payload)
        return 2
    lexical, lexical_code = lexical_provider.produce(
        root, Path("."), kotlinc=str(args.kotlinc), java=str(args.java)
    )
    if lexical["status"] != "complete":
        payload = _empty(
            name=args.name,
            target=target,
            status=lexical["status"],
            failure_kind=lexical["failure_kind"],
            lexical=lexical,
        )
        _write(output, evidence, payload)
        return lexical_code
    semantic, semantic_code = semantic_provider.collect(
        project_root=root,
        manifest_path=args.semantic_manifest,
        output=fact_pack,
        kotlinc=args.kotlinc,
        java=args.java,
    )
    if semantic["status"] != "complete":
        payload = _empty(
            name=args.name,
            target=target,
            status="partial",
            failure_kind=semantic["failure_kind"],
            lexical=lexical,
            semantic=semantic,
        )
        _write(output, evidence, payload)
        return semantic_code
    payload, failure = _map_payload(
        root=root,
        name=args.name,
        target=target,
        lexical=lexical,
        semantic=semantic,
    )
    if failure is not None:
        payload = _empty(
            name=args.name,
            target=target,
            status="partial",
            failure_kind=failure,
            lexical=lexical,
            semantic=semantic,
        )
        _write(output, evidence, payload)
        return 2
    _write(output, evidence, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
