#!/usr/bin/env python3
"""Find compiler-resolved Rust struct-literal sweep omissions."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


def _facts_module():
    candidates = [Path(__file__).with_name("rust_semantic_facts.py")]
    candidates.extend(
        parent / "map-subsystem" / "scripts" / "rust_semantic_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Rust semantic fact pack is missing")
    spec = importlib.util.spec_from_file_location("rust_sweep_facts", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _structs(root: Path, target: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for path in sorted((target / "src").rglob("*.rs")):
        if path.is_symlink():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        index = 0
        while index < len(lines):
            match = re.search(r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", lines[index])
            if not match:
                index += 1
                continue
            name = match.group(1)
            start = index + 1
            body = []
            depth = lines[index].count("{") - lines[index].count("}")
            index += 1
            while index < len(lines) and depth > 0:
                body.append(lines[index])
                depth += lines[index].count("{") - lines[index].count("}")
                index += 1
            fields = []
            for line in body:
                field = re.search(r"(?:pub(?:\([^)]*\))?\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
                if field:
                    fields.append(field.group(1))
            rows[name] = {
                "name": name,
                "file": path.relative_to(root).as_posix(),
                "line": start,
                "fields": fields,
            }
    return rows


def _sites(root: Path, facts: dict, structs: dict[str, dict]) -> dict[str, list[dict]]:
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    by_type = {name: [] for name in structs}
    for file, role in roles.items():
        if role != "production-module":
            continue
        text = (root / file).read_text(encoding="utf-8")
        for name, declaration in structs.items():
            pattern = re.compile(rf"\b{re.escape(name)}\s*\{{(?P<body>[^{{}}]*)\}}", re.DOTALL)
            for match in pattern.finditer(text):
                prefix = text[max(0, match.start() - 12) : match.start()]
                if re.search(r"(?:struct|->)\s*$", prefix):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                if any(
                    row.get("source") == file and row.get("line") == line
                    for row in facts.get("macro_boundaries", [])
                ) or any(
                    row["source"] == file and row["start_line"] <= line <= row["end_line"]
                    for row in facts.get("macro_regions", [])
                ):
                    continue
                if any(
                    row["source"] == file and row["start_line"] <= line <= row["end_line"]
                    for row in facts.get("unsafe_ffi_boundaries", [])
                ):
                    continue
                macro_prefix = text[max(0, match.start() - 500) : match.start()]
                if re.search(r"!\s*[({\[][^)}\]]*$", macro_prefix, re.DOTALL):
                    continue
                semantic = any(
                    edge.get("name") == name
                    and edge.get("source") == file
                    and edge.get("line") == line
                    and any(
                        item.get("file") == declaration["file"]
                        and item.get("line") == declaration["line"]
                        for item in edge.get("definitions", [])
                    )
                    for edge in facts.get("definition_edges", [])
                )
                if not semantic:
                    continue
                present = sorted(
                    set(re.findall(r"(?:^|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", match.group("body")))
                )
                by_type[name].append(
                    {
                        "file": file,
                        "line": line,
                        "present": present,
                        "snippet": " ".join(match.group(0).split())[:200],
                    }
                )
    return by_type


def _blame(root: Path, site: dict) -> tuple[int | None, str]:
    result = subprocess.run(
        [
            "git",
            "blame",
            "--line-porcelain",
            "-L",
            f"{site['line']},{site['line']}",
            "--",
            site["file"],
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"^committer-time (\d+)$", result.stdout, re.MULTILINE)
    if (
        result.returncode
        or not match
        or result.stdout.startswith("0000000000000000000000000000000000000000")
    ):
        return None, "failed" if result.returncode else "insufficient"
    return int(match.group(1)), "available"


def _replace(staged: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    if destination.exists():
        destination.replace(backup)
    try:
        staged.replace(destination)
    except OSError:
        if backup.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--rust-analyzer", default="rust-analyzer")
    parser.add_argument("--cargo-target-dir", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    target = (root / args.target).resolve()
    structs = _structs(root, target)
    facts = _facts_module().load_or_collect(
        facts=args.facts,
        project_root=root,
        target=args.target,
        queries=sorted(structs),
        cargo=args.cargo,
        rustc=args.rustc,
        rust_analyzer=args.rust_analyzer,
        cargo_target_dir=args.cargo_target_dir,
    )
    findings, gated_out, deferred = [], [], []
    boundary_structs = {
        name
        for name, declaration in structs.items()
        if any(
            row.get("source") == declaration["file"]
            and row.get("line", 0) <= declaration["line"] <= row.get("line", 0) + 2
            for row in [
                *facts.get("cfg_boundaries", []),
                *[
                    item
                    for item in facts.get("attribute_boundaries", [])
                    if item.get("classification") == "procedural_or_unknown"
                ],
            ]
        )
    }
    for name in sorted(boundary_structs):
        declaration = structs[name]
        deferred.append(
            {
                "file": declaration["file"],
                "line": declaration["line"],
                "reason": "cfg/procedural attribute struct is outside sweep claims",
                "detail": name,
            }
        )
    git_state = "available"
    if facts.get("status") == "complete":
        for name, sites in _sites(root, facts, structs).items():
            if name in boundary_structs:
                continue
            for field in structs[name]["fields"]:
                present = [site for site in sites if field in site["present"]]
                missing = [site for site in sites if field not in site["present"]]
                if len(present) < 2 or not missing or len(present) / len(sites) < 0.6:
                    continue
                for straggler in missing:
                    old_time, old_state = _blame(root, straggler)
                    present_stamps = [_blame(root, site) for site in present]
                    states = [old_state, *[state for _, state in present_stamps]]
                    if any(state != "available" for state in states) or old_time is None:
                        git_state = "failed" if "failed" in states else "insufficient"
                        deferred.append(
                            {
                                "file": straggler["file"],
                                "line": straggler["line"],
                                "reason": f"{git_state}_git_evidence",
                                "detail": name,
                            }
                        )
                        continue
                    newer = all(
                        stamp is not None and stamp > old_time for stamp, _ in present_stamps
                    )
                    row = {
                        "callee": name,
                        "kwarg": field,
                        "group_size": len(sites),
                        "present_count": len(present),
                        "majority_frac": len(present) / len(sites),
                        "straggler": f"{straggler['file']}:{straggler['line']}",
                        "present_sites": [
                            {"file": site["file"], "line": site["line"]} for site in present
                        ],
                        "gated_in": newer,
                        "value": "explicit field",
                        "default_value": "omitted/defaulted",
                        "trajectory": f"{len(present)}/{len(present)} option-present sites touched AFTER the straggler — consistent with a sweep that missed it"
                        if newer
                        else "not every option-present site is newer than the straggler — likely deliberate divergence",
                    }
                    (findings if newer else gated_out).append(row)
    else:
        deferred.append(
            {
                "file": args.target,
                "line": 0,
                "reason": facts.get("failure_kind") or "semantic_evidence_incomplete",
                "detail": "no compiler-resolved sweep claim",
            }
        )
    status = (
        "failed"
        if facts.get("status") == "failed"
        else (
            "complete"
            if facts.get("status") == "complete" and git_state == "available"
            else "partial"
        )
    )
    payload = {
        "schema_version": 1,
        "read_only": True,
        "band": "rust-struct-literal-omission",
        "language": "rust",
        "analyzer": "cargo-compiler+rust-analyzer-direct-struct-literals",
        "status": status,
        "project_root": str(root),
        "target": {"path": args.target},
        "project_resolution": {"state": status, "git_evidence": git_state},
        "source_inventory": facts.get("source_inventory", []),
        "source_hashes": facts.get("source_hashes", []),
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "findings": findings,
        "gated_out": gated_out,
        "deferred": deferred,
        "summary": {
            "gated_in": len(findings),
            "gated_out": len(gated_out),
            "deferred": len(deferred),
        },
        "limits": facts.get("limits", []),
    }
    report = args.report_dir if args.report_dir.is_absolute() else root / args.report_dir
    try:
        report.resolve(strict=False).relative_to(
            (root / "reports/find-incomplete-sweep").resolve(strict=False)
        )
    except ValueError:
        parser.error("report-dir must stay beneath reports/find-incomplete-sweep")
    report.parent.mkdir(parents=True, exist_ok=True)
    staged = report.with_name(f".{report.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir()
    (staged / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# find-incomplete-sweep — Rust",
        "",
        "> Read-only candidates; a human verdict is required before any completion handoff.",
        "",
        f"Status: `{status}`",
        "",
        "## Gated in",
        "",
    ]
    lines.extend(
        f"- `{row['straggler']}` — `{row['callee']}` omits `{row['kwarg']}`; {row['trajectory']}"
        for row in findings
    )
    if not findings:
        lines.append("None.")
    (staged / "findings.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _replace(staged, report)
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
