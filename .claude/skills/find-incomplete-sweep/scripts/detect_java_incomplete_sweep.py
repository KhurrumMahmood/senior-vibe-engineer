#!/usr/bin/env python3
"""Launch the family-local Java record-constructor sweep detector."""
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


class JavaSweepError(ValueError):
    """Known invalid detector condition."""


class UnsupportedJavaError(JavaSweepError):
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
            raise JavaSweepError(f"{label} must not traverse a symbolic link: {candidate}")


def _resolve_inside(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = Path(os.path.abspath(raw if raw.is_absolute() else root / raw))
    if not _inside(root, candidate):
        raise JavaSweepError(f"{label} must stay inside project root: {supplied}")
    _reject_symlinks(root, candidate, label)
    resolved = candidate.resolve()
    if not _inside(root, resolved):
        raise JavaSweepError(f"{label} must stay inside project root: {supplied}")
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
            raise JavaSweepError("target must be a .java file or directory")
        candidates = [target]
    else:
        candidates = sorted(path for path in target.rglob("*.java") if path.is_file() and not path.is_symlink())
    records = [{"file": path.relative_to(root).as_posix(), "role": _role(path, root)} for path in candidates]
    return [path for path, record in zip(candidates, records, strict=False) if record["role"] == "selected"], records


def _version(rendered: str, tool: str) -> tuple[int, int, int]:
    prefix = r"^javac\s+" if tool == "javac" else r"^(?:openjdk|java)\s+"
    match = re.search(prefix + r'(?:version\s+\")?(\d+)(?:\.(\d+))?(?:\.(\d+))?', rendered, re.MULTILINE)
    if match is None:
        raise UnsupportedJavaError(f"cannot determine {tool} version: {rendered.strip()}")
    return tuple(int(part or 0) for part in match.groups())


def _jdk(java_raw: str | None, javac_raw: str | None) -> tuple[Path, str, str]:
    found_java = java_raw or shutil.which("java")
    found_javac = javac_raw or shutil.which("javac")
    if not found_java or not found_javac or not Path(found_java).is_file() or not Path(found_javac).is_file():
        raise UnsupportedJavaError("JDK toolchain is unavailable on PATH")
    rendered_versions: dict[str, str] = {}
    for tool, command in (("java", [found_java, "--version"]), ("javac", [found_javac, "-version"])):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as error:
            raise UnsupportedJavaError(f"cannot run {tool}: {error}") from error
        rendered = (result.stdout + result.stderr).strip()
        if result.returncode or _version(rendered, tool) < MINIMUM_JDK:
            raise UnsupportedJavaError(f"Java analyzer requires JDK >= 17; found {rendered}")
        rendered_versions[tool] = rendered.splitlines()[0]
    return Path(found_java), rendered_versions["java"], rendered_versions["javac"]


def _fingerprint(scripts: Path) -> str:
    digest = hashlib.sha256()
    for name in ("detect_java_incomplete_sweep.py", "detect_java_incomplete_sweep.java"):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((scripts / name).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _helper(java: Path, files: list[Path], root: Path) -> dict[str, Any]:
    if not files:
        return {"schema_version": 1, "analyzer": "jdk-compiler-tree-direct-record-constructors", "candidates": [], "deferred": []}
    helper = Path(__file__).with_name("detect_java_incomplete_sweep.java")
    command = [str(java), str(helper), "--project-root", str(root)]
    for file in files:
        command.extend(("--file", str(file)))
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, env=os.environ.copy())
    if result.returncode:
        raise JavaSweepError(result.stderr.strip() or result.stdout.strip() or f"Java helper exited {result.returncode}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise JavaSweepError("Java helper emitted invalid JSON") from error
    if payload.get("schema_version") != 1 or payload.get("analyzer") != "jdk-compiler-tree-direct-record-constructors":
        raise JavaSweepError("Java helper emitted invalid evidence")
    return payload


def _blame(root: Path, file: str, line: int) -> tuple[int | None, str]:
    result = subprocess.run(
        ["git", "blame", "--line-porcelain", "-L", f"{line},{line}", "--", file],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return None, "failed"
    match = re.search(r"^committer-time (\d+)$", result.stdout, re.MULTILINE)
    if match is None or result.stdout.startswith("0000000000000000000000000000000000000000"):
        return None, "insufficient"
    return int(match.group(1)), "available"


def _gate(raw: dict[str, Any], root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str]:
    deferred = list(raw.get("deferred", []))
    findings: list[dict[str, Any]] = []
    gated_out: list[dict[str, Any]] = []
    repo = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, capture_output=True, text=True, check=False)
    if repo.returncode or repo.stdout.strip() != "true":
        for candidate in raw.get("candidates", []):
            site = candidate["straggler"]
            deferred.append({"file": site["file"], "line": site["line"], "reason": "insufficient_git_evidence", "detail": candidate["callee"]})
        return [], [], deferred, "insufficient"
    git_state = "available"
    for candidate in raw.get("candidates", []):
        straggler = candidate["straggler"]
        old_time, old_state = _blame(root, straggler["file"], straggler["line"])
        present_times: list[int] = []
        states = [old_state]
        for site in candidate["present"]:
            stamp, state = _blame(root, site["file"], site["line"])
            states.append(state)
            if stamp is not None:
                present_times.append(stamp)
        if any(state != "available" for state in states) or old_time is None or len(present_times) != len(candidate["present"]):
            reason = "failed_git_evidence" if "failed" in states else "insufficient_git_evidence"
            git_state = "failed" if reason == "failed_git_evidence" else ("insufficient" if git_state != "failed" else git_state)
            deferred.append({"file": straggler["file"], "line": straggler["line"], "reason": reason, "detail": candidate["callee"]})
            continue
        trajectory = (
            f"{len(present_times)}/{len(present_times)} option-present sites touched AFTER the straggler — consistent with a sweep that missed it"
            if all(stamp > old_time for stamp in present_times)
            else "not every option-present site is newer than the straggler — likely deliberate divergence"
        )
        present = [{"file": item["file"], "line": item["line"]} for item in candidate["present"]]
        finding = {
            "callee": candidate["callee"], "kwarg": candidate["option"],
            "option_position": candidate["option_position"],
            "group_size": len(present) + 1, "present_count": len(present),
            "majority_frac": len(present) / (len(present) + 1),
            "straggler": f"{straggler['file']}:{straggler['line']}",
            "present_sites": present, "gated_in": all(stamp > old_time for stamp in present_times),
            "value": candidate["present"][0]["value"], "default_value": candidate["default_value"],
            "trajectory": trajectory,
        }
        (findings if finding["gated_in"] else gated_out).append(finding)
    return findings, gated_out, deferred, git_state


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# find-incomplete-sweep — findings (Java 17)", "",
        f"Status: **{payload['status']}**. Compiler-resolved direct record constructions only.", "",
        "## Gated IN — likely forgotten sweeps", "",
    ]
    if not payload["findings"]:
        lines.append("_none_")
    for finding in payload["findings"]:
        lines.extend([
            f"### `{finding['callee']}` missing `{finding['kwarg']}`", "",
            f"- straggler: `{finding['straggler']}`",
            f"- majority: {finding['present_count']}/{finding['group_size']}",
            f"- comparable value/default: `{finding['value']}` / `{finding['default_value']}`",
            f"- trajectory: {finding['trajectory']}", "",
        ])
    lines.extend(["## Gated OUT — likely deliberate", ""])
    lines.extend([f"- `{item['straggler']}` — {item['trajectory']}" for item in payload["gated_out"]] or ["_none_"])
    lines.extend(["", "## Deferred boundaries", ""])
    lines.extend([f"- `{item['file']}:{item['line']}` — {item['reason']}" for item in payload["deferred"]] or ["_none_"])
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
            raise JavaSweepError(f"project root is not a directory: {args.project_root}")
        root = logical_root.resolve()
        target = _resolve_inside(root, args.target, "target")
        if not target.exists() or target.is_symlink():
            raise JavaSweepError(f"target must be an existing non-symlink path: {args.target}")
        report = _resolve_inside(root, args.report_dir, "report directory")
        allowed = root / "reports/find-incomplete-sweep"
        if report == allowed or not _inside(allowed, report):
            raise JavaSweepError("report directory must stay beneath reports/find-incomplete-sweep/")
        java, java_version, javac_version = _jdk(args.java_executable, args.javac_executable)
        files, inventory = _inventory(target, root)
        raw = _helper(java, files, root)
        findings, gated_out, deferred, git_state = _gate(raw, root)
        status = "partial" if git_state != "available" else "complete"
        payload = {
            "schema_version": 1, "band": "java-record-constructor-omission", "language": "java",
            "analyzer": "jdk-compiler-tree-direct-record-constructors", "status": status,
            "project_root": str(root), "target": {"path": target.relative_to(root).as_posix()},
            "project_resolution": {"state": status, "git_evidence": git_state},
            "source_inventory": inventory, "findings": findings, "gated_out": gated_out,
            "deferred": deferred,
            "summary": {"gated_in": len(findings), "gated_out": len(gated_out), "deferred": len(deferred)},
            "java_version": java_version, "javac_version": javac_version,
            "source_fingerprint": _fingerprint(Path(__file__).parent),
        }
        report.parent.mkdir(parents=True, exist_ok=True)
        staged = report.with_name(f".{report.name}.staged-{uuid.uuid4().hex}")
        staged.mkdir()
        (staged / "manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (staged / "findings.md").write_text(_render(payload), encoding="utf-8")
        _replace(staged, report)
        staged = None
    except UnsupportedJavaError as error:
        if staged is not None:
            shutil.rmtree(staged, ignore_errors=True)
        print(f"[find-incomplete-sweep-java] unsupported: {error}", file=sys.stderr)
        return 2
    except (JavaSweepError, OSError) as error:
        if staged is not None:
            shutil.rmtree(staged, ignore_errors=True)
        print(f"[find-incomplete-sweep-java] failed: {error}", file=sys.stderr)
        return 2
    print(f"[find-incomplete-sweep-java] wrote {report} (gated_in={len(findings)} status={status})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
