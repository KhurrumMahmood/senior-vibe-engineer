#!/usr/bin/env python3
"""Find one LSP-resolved Dart named-argument sweep omission shape."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


def _provider():
    candidates = [Path(__file__).with_name("dart_lsp_facts.py")]
    candidates.extend(
        parent / "map-subsystem" / "scripts" / "dart_lsp_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Dart LSP fact provider is missing")
    spec = importlib.util.spec_from_file_location("dart_sweep_lsp_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _safe_output(root: Path, supplied: Path) -> Path:
    output = supplied if supplied.is_absolute() else root / supplied
    output = Path(os.path.abspath(output))
    allowed = root / "reports" / "find-incomplete-sweep"
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


def _replace_directory(staged: Path, destination: Path) -> None:
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
    paths = [target] if target.is_file() else sorted(target.rglob("*.dart"))
    pattern = re.compile(
        r"^\s*(?:(?:external|static)\s+)?(?:[A-Za-z_]\w*(?:<[^;{}=]+>)?\??\s+)?"
        r"(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^()]*)\)\s*(?:=>|\{)"
    )
    for path in paths:
        if path.is_symlink() or not path.is_file():
            continue
        depth = 0
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            code = re.sub(r"//.*$", "", line)
            if depth == 0:
                match = pattern.match(code)
                if match and "{" in match.group("params") and "}" in match.group("params"):
                    named = match.group("params").split("{", 1)[1].rsplit("}", 1)[0]
                    names = sorted(
                        {
                            item.group(1)
                            for item in re.finditer(
                                r"(?:required\s+)?(?:[A-Za-z_]\w*(?:<[^,=]+>)?\??\s+)?"
                                r"([A-Za-z_]\w*)\s*(?:=|,|$)",
                                named,
                            )
                        }
                    )
                    if names:
                        rows.append(
                            {
                                "name": match.group("name"),
                                "file": path.relative_to(root).as_posix(),
                                "line": line_no,
                                "column": match.start("name") + 1,
                                "named_options": names,
                            }
                        )
            depth += code.count("{") - code.count("}")
            depth = max(depth, 0)
    return rows


def _call_arguments(line: str, name: str, column: int) -> str | None:
    offset = column - 1
    if line[offset : offset + len(name)] != name:
        return None
    tail = line[offset + len(name) :]
    opening = re.match(r"\s*\(", tail)
    if opening is None:
        return None
    prefix = line[:offset]
    if "=>" in prefix and re.match(r"^\s*(?:[A-Za-z_]\w*\??\s+)?[A-Za-z_]\w*\s*\(", prefix):
        return None
    start = offset + len(name) + opening.end() - 1
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(start, len(line)):
        character = line[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return line[start + 1 : index]
    return None


def _git_timestamp(root: Path, site: dict[str, Any]) -> tuple[int | None, str]:
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
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, "failed"
    match = re.search(r"^committer-time (\d+)$", result.stdout, re.MULTILINE)
    if result.returncode or match is None:
        return None, "failed" if result.returncode else "insufficient"
    if result.stdout.startswith("0000000000000000000000000000000000000000"):
        return None, "insufficient"
    return int(match.group(1)), "available"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--dart", default="dart")
    parser.add_argument("--packages", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    target = Path(os.path.realpath((root / args.target).resolve(strict=True)))
    try:
        target.relative_to(root)
        report = _safe_output(root, args.report_dir)
    except ValueError as exc:
        parser.error(str(exc))
    functions = _functions(root, target)
    provider = _provider()
    try:
        facts = provider.load_or_collect(
            facts=args.facts,
            project_root=root,
            target=args.target,
            queries=[row["name"] for row in functions],
            dart=args.dart,
            packages=args.packages,
            cache_dir=args.cache_dir,
            timeout=args.timeout,
        )
    except (provider.DartFactError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    definitions = facts.get("definition_queries", [])
    findings: list[dict[str, Any]] = []
    gated_out: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    git_state = "not-required"
    if facts.get("status") == "complete":
        for function in functions:
            if roles.get(function["file"]) != "production":
                continue
            sites: list[dict[str, Any]] = []
            declaration_target = (function["file"], function["line"])
            for edge in definitions:
                if edge.get("name") != function["name"]:
                    continue
                if (edge.get("source"), edge.get("line"), edge.get("column")) == (
                    function["file"],
                    function["line"],
                    function["column"],
                ):
                    continue
                if roles.get(edge.get("source")) != "production":
                    continue
                targets = edge.get("targets", [])
                if not any(
                    (target_row.get("path"), target_row.get("line")) == declaration_target
                    for target_row in targets
                ):
                    continue
                lines = (root / edge["source"]).read_text(encoding="utf-8").splitlines()
                if not (1 <= edge["line"] <= len(lines)):
                    continue
                arguments = _call_arguments(
                    lines[edge["line"] - 1], function["name"], edge["column"]
                )
                if arguments is None:
                    continue
                named_values = {
                    match.group("name"): match.group("value")
                    for match in re.finditer(
                        r"\b(?P<name>[A-Za-z_]\w*)\s*:\s*"
                        r"(?P<value>true|false|null|-?\d+(?:\.\d+)?|['\"][^'\"]*['\"])",
                        arguments,
                    )
                }
                sites.append(
                    {
                        "file": edge["source"],
                        "line": edge["line"],
                        "column": edge["column"],
                        "named_arguments": sorted(
                            set(re.findall(r"\b([A-Za-z_]\w*)\s*:", arguments))
                        ),
                        "named_values": named_values,
                        "snippet": lines[edge["line"] - 1].strip()[:200],
                        "definition_targets": targets,
                    }
                )
            for option in function["named_options"]:
                present = [site for site in sites if option in site["named_arguments"]]
                missing = [site for site in sites if option not in site["named_arguments"]]
                if len(present) < 3 or len(missing) != 1 or len(present) / len(sites) < 0.75:
                    continue
                straggler = missing[0]
                values = [site["named_values"].get(option) for site in present]
                if any(value is None for value in values) or len(set(values)) != 1:
                    gated_out.append(
                        {
                            "callee": function["name"],
                            "kwarg": option,
                            "group_size": len(sites),
                            "present_count": len(present),
                            "majority_frac": len(present) / len(sites),
                            "straggler": f"{straggler['file']}:{straggler['line']}",
                            "present_sites": present,
                            "gated_in": False,
                            "trajectory": "present named-argument values are not one comparable value",
                            "reason": "inconsistent_or_noncomparable_present_values",
                        }
                    )
                    continue
                old_time, old_state = _git_timestamp(root, straggler)
                present_times = [_git_timestamp(root, site) for site in present]
                states = [old_state, *[state for _, state in present_times]]
                if any(state != "available" for state in states) or old_time is None:
                    git_state = "failed" if "failed" in states else "insufficient"
                    deferred.append(
                        {
                            "file": straggler["file"],
                            "line": straggler["line"],
                            "reason": f"{git_state}_git_evidence",
                            "detail": f"{function['name']}:{option}",
                        }
                    )
                    continue
                git_state = "available"
                newer = all(
                    timestamp is not None and timestamp > old_time
                    for timestamp, _ in present_times
                )
                row = {
                    "callee": function["name"],
                    "kwarg": option,
                    "group_size": len(sites),
                    "present_count": len(present),
                    "majority_frac": len(present) / len(sites),
                    "straggler": f"{straggler['file']}:{straggler['line']}",
                    "straggler_site": straggler,
                    "present_sites": present,
                    "gated_in": newer,
                    "value": values[0],
                    "default_value": "omitted/defaulted",
                    "trajectory": (
                        f"{len(present)}/{len(present)} option-present sites touched AFTER the straggler — consistent with a sweep that missed it"
                        if newer
                        else "not every option-present site is newer than the straggler — likely deliberate divergence"
                    ),
                    "identity_evidence": "textDocument/definition target matches the selected top-level callee",
                }
                (findings if newer else gated_out).append(row)
    else:
        deferred.append(
            {
                "file": args.target,
                "line": 0,
                "reason": facts.get("failure_kind") or "semantic_evidence_incomplete",
                "detail": "no LSP-resolved named-argument sweep claim",
            }
        )
    status = (
        "failed"
        if facts.get("status") == "failed"
        else (
            "complete"
            if facts.get("status") == "complete" and git_state in {"available", "not-required"}
            else "partial"
        )
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "read_only": True,
        "band": "dart-named-argument-omission",
        "language": "dart",
        "analyzer": "dart-sdk-lsp-direct-named-argument-sites",
        "status": status,
        "failure_kind": facts.get("failure_kind")
        if facts.get("status") != "complete"
        else (None if git_state in {"available", "not-required"} else f"{git_state}_git_evidence"),
        "project_root": str(root),
        "target": {"path": target.relative_to(root).as_posix()},
        "project_resolution": {"state": status, "git_evidence": git_state},
        "source_inventory": facts.get("source_inventory", []),
        "source_hashes": facts.get("source_hashes", []),
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "query_plan_sha256": facts.get("query_plan_sha256"),
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
            "one direct top-level named-argument omission shape only",
            "wrappers, aliases, dynamic/cascade/extension dispatch, runtime behavior, and automatic fixes are excluded",
            "an explicit fixed-vocabulary human verdict is required before a completion handoff",
        ],
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    staged = report.with_name(f".{report.name}.staged-{uuid.uuid4().hex}")
    staged.mkdir()
    _atomic(staged / "manifest.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    lines = [
        "# find-incomplete-sweep — Dart",
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
    _atomic(staged / "findings.md", "\n".join(lines) + "\n")
    _replace_directory(staged, report)
    print(f"wrote Dart incomplete-sweep evidence: {report}")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
