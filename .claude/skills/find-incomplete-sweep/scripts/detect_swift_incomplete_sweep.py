#!/usr/bin/env python3
"""Find one SourceKit-resolved Swift defaulted-argument sweep omission shape."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


def _provider():
    candidates = [Path(__file__).with_name("swift_semantic_facts.py")]
    for parent in Path(__file__).resolve().parents:
        candidates.extend(
            [
                parent / "_swift-semantic-readonly/swift_semantic_facts.py",
                parent / ".claude/skills/_swift-semantic-readonly/swift_semantic_facts.py",
            ]
        )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Swift semantic provider is missing")
    spec = importlib.util.spec_from_file_location("swift_sweep_semantic_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _safe_dir(root: Path, supplied: Path) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    allowed = root / "reports/find-incomplete-sweep"
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("report-dir must stay beneath reports/find-incomplete-sweep/") from exc
    if not relative.parts:
        raise ValueError("report-dir must name a scan")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise ValueError("report-dir must not traverse a symbolic link")
    return output


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


def _functions(root: Path, target: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        r"^\s*(?:(?:public|package|internal|fileprivate|private)\s+)?func\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^()]*)\)\s*(?:async\s+)?(?:throws\s+)?(?:->[^\{]+)?\{"
    )
    default = re.compile(
        r"(?:^|,)\s*(?:_\s+)?(?P<label>[A-Za-z_]\w*)\s*:\s*[^,=]+\s*=\s*(?P<value>true|false|nil|-?\d+(?:\.\d+)?|\"[^\"]*\")"
    )
    for source in sorted(target.rglob("*.swift")):
        if source.is_symlink():
            continue
        depth = 0
        for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            match = pattern.match(re.sub(r"//.*$", "", line))
            if match and depth == 0:
                defaults = {
                    item.group("label"): item.group("value")
                    for item in default.finditer(match.group("params"))
                }
                if defaults:
                    rows.append(
                        {
                            "name": match.group("name"),
                            "file": source.relative_to(root).as_posix(),
                            "line": line_no,
                            "column": match.start("name") + 1,
                            "defaulted_arguments": defaults,
                        }
                    )
            code = re.sub(r"//.*$", "", line)
            depth += code.count("{") - code.count("}")
            depth = max(depth, 0)
    return rows


def _arguments(line: str, name: str, column: int) -> str | None:
    offset = column - 1
    if line[offset : offset + len(name)] != name:
        return None
    tail = line[offset + len(name) :]
    opening = re.match(r"\s*\(", tail)
    if opening is None:
        return None
    start = offset + len(name) + opening.end() - 1
    depth = 0
    quote = False
    escaped = False
    for index in range(start, len(line)):
        character = line[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quote = False
            continue
        if character == '"':
            quote = True
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return line[start + 1 : index]
    return None


def _blame(root: Path, site: dict[str, Any]) -> tuple[int | None, str]:
    try:
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
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None, "failed"
    match = re.search(r"^committer-time (\d+)$", result.stdout, re.MULTILINE)
    if result.returncode or match is None:
        return None, "failed" if result.returncode else "insufficient"
    if result.stdout.startswith("0000000000000000000000000000000000000000"):
        return None, "insufficient"
    return int(match.group(1)), "available"


def _write(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = output.with_name(f".{output.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir()
    (staged / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# find-incomplete-sweep — Swift",
        "",
        "> Resolved read-only candidates; a hash-bound human verdict is required.",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Gated in",
        "",
    ]
    lines.extend(
        f"- `{row['straggler']}` — `{row['callee']}` omits `{row['kwarg']}`; {row['trajectory']}"
        for row in payload["findings"]
    )
    if not payload["findings"]:
        lines.append("None.")
    (staged / "findings.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _replace(staged, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    target = Path(os.path.realpath((root / args.target).resolve(strict=True)))
    try:
        target.relative_to(root)
        output = _safe_dir(root, args.report_dir)
    except ValueError as exc:
        parser.error(str(exc))
    functions = _functions(root, target)
    provider = _provider()
    try:
        facts = provider.load_fact_pack(
            args.facts, root, args.target_name, [row["name"] for row in functions]
        )
    except provider.SwiftFactError as exc:
        payload = {
            "schema_version": "swift-incomplete-sweep-v1",
            "language": "swift",
            "status": "failed",
            "failure_kind": exc.kind,
            "failure_detail": str(exc),
            "project_root": str(root),
            "findings": [],
            "gated_out": [],
            "deferred": [],
            "summary": {"gated_in": 0, "gated_out": 0, "deferred": 0},
        }
        _write(output, payload)
        return 2
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    symbols = facts.get("symbols", [])
    occurrences = facts.get("definition_occurrences", [])
    findings: list[dict[str, Any]] = []
    gated_out: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    git_states: set[str] = set()
    if facts.get("status") == "complete":
        for function in functions:
            matches = [
                row
                for row in symbols
                if row.get("name") == function["name"]
                and row.get("file") == function["file"]
                and row.get("line") == function["line"]
                and row.get("top_level")
                and row.get("semantic_id")
            ]
            if len(matches) != 1:
                deferred.append(
                    {**function, "reason": "resolved top-level callee identity is unavailable"}
                )
                continue
            symbol = matches[0]
            sites: list[dict[str, Any]] = []
            references = [
                {
                    "path": occurrence.get("source"),
                    "line": occurrence.get("line"),
                    "column": occurrence.get("column"),
                }
                for occurrence in occurrences
                if occurrence.get("name") == function["name"]
                and any(
                    definition.get("path") == function["file"]
                    and definition.get("line") == function["line"]
                    for definition in occurrence.get("definitions", [])
                )
            ]
            for reference in references:
                if roles.get(reference.get("path")) != "selected-production":
                    continue
                if (
                    reference.get("path") == function["file"]
                    and reference.get("line") == function["line"]
                ):
                    continue
                source = root / reference["path"]
                lines = source.read_text(encoding="utf-8").splitlines()
                if not 1 <= reference["line"] <= len(lines):
                    continue
                arguments = _arguments(
                    lines[reference["line"] - 1], function["name"], reference["column"]
                )
                if arguments is None:
                    continue
                named = {
                    match.group("name"): match.group("value")
                    for match in re.finditer(
                        r"\b(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<value>true|false|nil|-?\d+(?:\.\d+)?|\"[^\"]*\")",
                        arguments,
                    )
                }
                sites.append(
                    {
                        "file": reference["path"],
                        "line": reference["line"],
                        "column": reference["column"],
                        "named_arguments": sorted(named),
                        "named_values": named,
                        "snippet": lines[reference["line"] - 1].strip()[:200],
                        "callee_semantic_id": symbol["semantic_id"],
                    }
                )
            for option, default in function["defaulted_arguments"].items():
                present = [site for site in sites if option in site["named_arguments"]]
                missing = [site for site in sites if option not in site["named_arguments"]]
                if (
                    len(present) < 3
                    or len(missing) != 1
                    or len(present) / max(len(sites), 1) < 0.75
                ):
                    continue
                values = [site["named_values"].get(option) for site in present]
                straggler = missing[0]
                if any(value is None for value in values) or len(set(values)) != 1:
                    gated_out.append(
                        {
                            "callee": function["name"],
                            "kwarg": option,
                            "straggler": f"{straggler['file']}:{straggler['line']}",
                            "gated_in": False,
                            "reason": "present argument values are not one comparable value",
                        }
                    )
                    continue
                old_time, old_status = _blame(root, straggler)
                present_times = [_blame(root, site) for site in present]
                states = [old_status, *[status for _, status in present_times]]
                if old_time is None or any(status != "available" for status in states):
                    git_state = "failed" if "failed" in states else "insufficient"
                    git_states.add(git_state)
                    deferred.append(
                        {
                            "file": straggler["file"],
                            "line": straggler["line"],
                            "reason": f"{git_state}_git_evidence",
                        }
                    )
                    continue
                git_states.add("available")
                newer = all(
                    timestamp is not None and timestamp > old_time for timestamp, _ in present_times
                )
                row = {
                    "callee": function["name"],
                    "callee_semantic_id": symbol["semantic_id"],
                    "kwarg": option,
                    "group_size": len(sites),
                    "present_count": len(present),
                    "majority_frac": len(present) / len(sites),
                    "straggler": f"{straggler['file']}:{straggler['line']}",
                    "straggler_site": straggler,
                    "present_sites": present,
                    "gated_in": newer,
                    "value": values[0],
                    "default_value": default,
                    "trajectory": (
                        f"{len(present)}/{len(present)} option-present sites touched AFTER the straggler — consistent with a sweep that missed it"
                        if newer
                        else "not every option-present site is newer than the straggler — likely deliberate divergence"
                    ),
                    "identity_evidence": (
                        "each call occurrence resolves through textDocument/definition to "
                        "the selected SourceKit declaration"
                    ),
                }
                (findings if newer else gated_out).append(row)
    else:
        deferred.append({"reason": facts.get("failure_kind") or "semantic fact pack incomplete"})
    if "failed" in git_states:
        git_state = "failed"
    elif "insufficient" in git_states:
        git_state = "insufficient"
    elif "available" in git_states:
        git_state = "available"
    else:
        git_state = "not-required"
    status = (
        "complete"
        if facts.get("status") == "complete"
        and git_state
        in {
            "available",
            "not-required",
        }
        else "partial"
    )
    payload = {
        "schema_version": "swift-incomplete-sweep-v1",
        "language": "swift",
        "band": "swift-defaulted-argument-omission",
        "analyzer": "swiftpm-fresh-index+sourcekit-lsp-direct-calls",
        "status": status,
        "failure_kind": None
        if status == "complete"
        else facts.get("failure_kind") or f"{git_state}_git_evidence",
        "read_only": True,
        "project_root": str(root),
        "target": {"name": args.target_name, "path": target.relative_to(root).as_posix()},
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
        "limits": [
            *facts.get("limits", []),
            "one direct top-level defaulted labeled-argument omission shape only",
            "every promoted straggler requires newer uniform Git trajectory and a separate hash-bound human verdict",
        ],
    }
    _write(output, payload)
    print(f"wrote Swift incomplete-sweep evidence: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
