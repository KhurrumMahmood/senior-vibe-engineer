#!/usr/bin/env python3
"""Produce conservative Java static record-construction review leads."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


MINIMUM_JDK = (17, 0, 0)
SKIP_DIRS = frozenset({
    ".git", ".gradle", ".idea", ".venv", "build", "dist", "generated",
    "node_modules", "out", "reports", "target", "test", "tests", "testdata",
    "testfixtures", "integrationtest", "vendor", "third-party", "third_party",
})
SKIP_FILES = ("*Test.java", "*Tests.java", "*IT.java", "*Generated.java", "*.generated.java")
GENERATED_RE = re.compile(r"^// (?:Code )?[Gg]enerated .* DO NOT EDIT\.$")
CAPABILITIES = {
    "function_level_static_candidates": "available_for_direct_static_methods",
    "record_return_construction": "available_for_one_direct_canonical_return",
    "resolved_direct_callers": "available_within_eligible_production_source",
    "behavioral_equivalence": "unavailable",
    "workflow_or_framework_analysis": "unavailable",
    "methods_dynamic_dispatch_and_reflection": "unavailable",
}


class SemanticJavaError(ValueError):
    """Known invalid analyzer condition."""


class UnsupportedJavaError(SemanticJavaError):
    """The host cannot supply the JDK 17 compiler-tree contract."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _reject_symlinks(root: Path, candidate: Path, label: str) -> None:
    current = root
    for part in candidate.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise SemanticJavaError(f"{label} must not traverse a symbolic link: {candidate}")


def _resolve_inside(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = Path(os.path.abspath(raw if raw.is_absolute() else root / raw))
    if not _inside(root, candidate):
        raise SemanticJavaError(f"{label} must stay inside project root: {supplied}")
    _reject_symlinks(root, candidate, label)
    resolved = candidate.resolve()
    if not _inside(root, resolved):
        raise SemanticJavaError(f"{label} must stay inside project root: {supplied}")
    return resolved


def _generated(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8") as source:
            return any(GENERATED_RE.fullmatch(line.strip()) for _, line in zip(range(40), source, strict=False))
    except (OSError, UnicodeDecodeError):
        return False


def _role(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if any(part.casefold() in SKIP_DIRS for part in relative.parts[:-1]):
        return "excluded_directory"
    if any(fnmatch.fnmatchcase(path.name, pattern) for pattern in SKIP_FILES):
        return "excluded_test_or_generated_name"
    if _generated(path):
        return "excluded_generated_marker"
    return "selected"


def _inventory(target: Path, root: Path) -> tuple[list[Path], list[dict[str, str]]]:
    if target.is_file():
        if target.suffix.casefold() != ".java":
            raise SemanticJavaError("target must be a .java file or directory")
        candidates = [target]
    else:
        candidates = sorted(path for path in target.rglob("*.java") if path.is_file() and not path.is_symlink())
    records = [{"file": path.relative_to(root).as_posix(), "role": _role(path, root)} for path in candidates]
    return [path for path, record in zip(candidates, records, strict=False) if record["role"] == "selected"], records


def _parse_version(rendered: str, tool: str) -> tuple[int, int, int]:
    prefix = r"^javac\s+" if tool == "javac" else r"^(?:openjdk|java)\s+"
    match = re.search(prefix + r'(?:version\s+\")?(\d+)(?:\.(\d+))?(?:\.(\d+))?', rendered, re.MULTILINE)
    if match is None:
        raise UnsupportedJavaError(f"cannot determine {tool} version: {rendered.strip()}")
    return tuple(int(part or 0) for part in match.groups())


def _jdk(java_raw: str | None, javac_raw: str | None) -> tuple[Path, str, str]:
    java = java_raw or shutil.which("java")
    javac = javac_raw or shutil.which("javac")
    if not java or not javac or not Path(java).is_file() or not Path(javac).is_file():
        raise UnsupportedJavaError("JDK toolchain is unavailable on PATH")
    versions: dict[str, str] = {}
    for tool, command in (("java", [java, "--version"]), ("javac", [javac, "-version"])):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as error:
            raise UnsupportedJavaError(f"cannot run {tool}: {error}") from error
        rendered = (result.stdout + result.stderr).strip()
        if result.returncode or _parse_version(rendered, tool) < MINIMUM_JDK:
            raise UnsupportedJavaError(f"Java analyzer requires JDK >= 17; found {rendered}")
        versions[tool] = rendered.splitlines()[0]
    return Path(java), versions["java"], versions["javac"]


def _fingerprint(scripts: Path) -> str:
    digest = hashlib.sha256()
    for name in ("detect_java_semantic.py", "detect_java_semantic.java"):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((scripts / name).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _helper(java: Path, files: list[Path], root: Path) -> dict[str, Any]:
    if not files:
        return {"schema_version": 1, "analyzer": "jdk-compiler-tree-static-record-returns", "eligible_method_count": 0, "leads": [], "deferred": []}
    command = [str(java), str(Path(__file__).with_name("detect_java_semantic.java")), "--project-root", str(root)]
    for file in files:
        command.extend(("--file", str(file)))
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, env=os.environ.copy())
    if result.returncode:
        raise SemanticJavaError(result.stderr.strip() or result.stdout.strip() or f"Java helper exited {result.returncode}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SemanticJavaError("Java helper emitted invalid JSON") from error
    if payload.get("schema_version") != 1 or payload.get("analyzer") != "jdk-compiler-tree-static-record-returns":
        raise SemanticJavaError("Java helper emitted invalid evidence")
    return payload


def _finding(lead: dict[str, Any], index: int) -> dict[str, Any]:
    finding_id = f"JAVA-SD-{index:04d}"
    members = []
    for member in lead["members"]:
        members.append({**member, "size": member["end_line"] - member["line"] + 1})
    return {
        "finding_id": finding_id,
        "id": finding_id,
        "level": "function",
        "members": members,
        "static_return_type": lead["static_return_type"],
        "return_fields": lead["return_fields"],
        "investigation_status": "confirmed",
        "shared_core_description": "Both direct static methods construct the same record return type and populate the same declared components.",
        "divergence": {"accidental": [], "load_bearing": []},
        "consolidation_shape": "share_utilities",
        "maintenance_risk_domain": "unknown",
        "matrix_path": f"capability_matrices/{finding_id}.md",
        "tests_that_guard_this_area": [],
        "notes": "Conservative function-level static lead only; matching record construction and resolved callers are not behavioral equivalence or authorization to refactor.",
    }


def _matrix(finding: dict[str, Any]) -> str:
    left, right = finding["members"]
    callers_left = ", ".join(f"{item['file']}:{item['line']}" for item in left["direct_callers"])
    callers_right = ", ".join(f"{item['file']}:{item['line']}" for item in right["direct_callers"])
    return "\n".join([
        f"## {finding['finding_id']}: {left['qualified_name']} and {right['qualified_name']}", "",
        "### Implementations", "",
        f"- **A:** `{left['file']}:{left['line']}-{left['end_line']}` — `{left['qualified_name']}`",
        f"- **B:** `{right['file']}:{right['line']}-{right['end_line']}` — `{right['qualified_name']}`", "",
        "### Capability comparison", "",
        "| Capability | A | B | Notes |", "|---|---|---|---|",
        f"| Static record return type | `{finding['static_return_type']}` | `{finding['static_return_type']}` | JDK Types resolved one identical project record. |",
        f"| Returned record components | `{', '.join(finding['return_fields'])}` | `{', '.join(finding['return_fields'])}` | Each method directly returns one canonical record construction. |",
        "| Resolved direct call relationship | None | None | Neither method directly calls the other in eligible production source. |",
        f"| Resolved direct callers | `{callers_left}` | `{callers_right}` | Compiler-resolved caller evidence; not a whole-repository runtime inventory. |", "",
        "### Recommendation", "",
        "Treat this as a static lead for human review. Never claim behavioral equivalence or refactor safety from this matrix.", "",
    ])


def _triage(findings: list[dict[str, Any]], deferred: list[dict[str, Any]]) -> str:
    lines = [
        "# Java semantic-duplication triage", "",
        "These are conservative static review leads, never behavioral equivalence or automatic refactor authority.", "",
        "## Conservative static review leads", "",
    ]
    if not findings:
        lines.append("(none)")
    for finding in findings:
        left, right = finding["members"]
        lines.extend([
            f"### {finding['finding_id']}: {left['qualified_name']} / {right['qualified_name']}", "",
            f"- **Evidence:** same compiler-resolved record `{finding['static_return_type']}` and components `{', '.join(finding['return_fields'])}`",
            f"- **Direct callers:** {left['caller_count']} / {right['caller_count']} within eligible production source",
            f"- **Capability matrix:** `{finding['matrix_path']}`",
            "- **Next boundary:** human review through `/unify-shadows`; do not invoke a mutation workflow directly.", "",
        ])
    lines.extend(["## Deferred static boundaries", ""])
    lines.extend([f"- `{item['file']}:{item['line']}` `{item['symbol']}` — {item['reason']}" for item in deferred] or ["(none)"])
    return "\n".join(lines) + "\n"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--java-executable")
    parser.add_argument("--javac-executable")
    args = parser.parse_args(argv)
    staged: Path | None = None
    try:
        logical_root = Path(os.path.abspath(args.project_root))
        if not logical_root.is_dir() or logical_root.is_symlink():
            raise SemanticJavaError(f"project root is not a directory: {args.project_root}")
        root = logical_root.resolve()
        target = _resolve_inside(root, args.target, "target")
        if not target.exists() or target.is_symlink():
            raise SemanticJavaError(f"target must be an existing non-symlink path: {args.target}")
        report = _resolve_inside(root, args.report_dir, "report directory")
        allowed = root / "reports/semantic-duplication"
        if report == allowed or not _inside(allowed, report):
            raise SemanticJavaError("report directory must stay beneath reports/semantic-duplication/")
        java, java_version, javac_version = _jdk(args.java_executable, args.javac_executable)
        files, inventory = _inventory(target, root)
        raw = _helper(java, files, root)
        findings = [_finding(lead, index) for index, lead in enumerate(raw["leads"], 1)]
        fingerprint = _fingerprint(Path(__file__).parent)
        payload = {
            "skill": "find-semantic-duplication", "language": "java",
            "analyzer": "jdk-compiler-tree-static-record-returns", "status": "complete",
            "source_fingerprint": fingerprint, "capability_matrix": CAPABILITIES,
            "counts": {"confirmed": len(findings), "uncertain": 0, "rejected": 0, "deferred": len(raw["deferred"])},
            "findings": findings, "confirmed": findings, "uncertain": [], "rejected": [],
            "deferred": raw["deferred"],
        }
        analysis = {
            "language": "java", "analyzer": "jdk-compiler-tree-static-record-returns",
            "status": "complete", "source_inventory": inventory,
            "eligible_method_count": raw["eligible_method_count"], "deferred": raw["deferred"],
            "capability_matrix": CAPABILITIES, "java_version": java_version,
            "javac_version": javac_version, "source_fingerprint": fingerprint,
        }
        report.parent.mkdir(parents=True, exist_ok=True)
        staged = report.with_name(f".{report.name}.staged-{uuid.uuid4().hex}")
        (staged / "capability_matrices").mkdir(parents=True)
        for finding in findings:
            (staged / finding["matrix_path"]).write_text(_matrix(finding), encoding="utf-8")
        (staged / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
        (staged / "findings.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (staged / "triage.md").write_text(_triage(findings, raw["deferred"]), encoding="utf-8")
        _replace(staged, report)
        staged = None
    except UnsupportedJavaError as error:
        if staged is not None:
            shutil.rmtree(staged, ignore_errors=True)
        print(f"[detect_java_semantic] unsupported: {error}", file=sys.stderr)
        return 2
    except (SemanticJavaError, OSError, KeyError, TypeError) as error:
        if staged is not None:
            shutil.rmtree(staged, ignore_errors=True)
        print(f"[detect_java_semantic] failed: {error}", file=sys.stderr)
        return 2
    print(f"[detect_java_semantic] wrote {report} (confirmed={len(findings)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
