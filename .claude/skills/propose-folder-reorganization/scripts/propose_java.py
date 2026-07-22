#!/usr/bin/env python3
"""Preflight and launch the family-local JDK Java subpackage proposer."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True


def artifact_path(root: pathlib.Path, supplied: pathlib.Path, label: str) -> pathlib.Path:
    report_root = root / "reports" / "propose-folder-reorganization"
    candidate = supplied if supplied.is_absolute() else root / supplied
    logical = pathlib.Path(os.path.abspath(candidate))
    try:
        relative = logical.relative_to(report_root)
    except ValueError as exc:
        raise ValueError(
            f"--{label} must stay below reports/propose-folder-reorganization/"
        ) from exc
    if not relative.parts:
        raise ValueError(f"--{label} must name a file below the report root")
    current = root
    for part in logical.relative_to(root).parts:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"--{label} component could not be inspected") from exc
        if stat.S_ISLNK(mode):
            raise ValueError(f"--{label} must not traverse a symlink")
    if logical.exists() and logical.is_dir():
        raise ValueError(f"--{label} must name a file")
    return logical


def write_atomic(path: pathlib.Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    temporary.write_text(contents, encoding="utf-8")
    os.replace(temporary, path)


def terminal_payload(
    args: argparse.Namespace,
    *,
    status: str,
    recommendation: str,
    failure_kind: str,
    message: str,
) -> dict:
    return {
        "schema_version": 1,
        "skill": "propose-folder-reorganization",
        "language": "java",
        "status": status,
        "recommendation": recommendation,
        "failure_kind": failure_kind,
        "message": message,
        "read_only": True,
        "analyzer": "jdk-compiler-tree-type-api",
        "judgment": {
            "cluster": args.cluster_judgment,
            "project_convention": args.convention_judgment,
            "framework_convention_inferred": False,
        },
        "moves": [],
        "impacts": [],
        "blockers": [{"kind": failure_kind, "reason": message}],
    }


def render_terminal(payload: dict) -> str:
    return (
        "# Java folder reorganization proposal\n\n"
        "> Read-only result; no source edits were applied.\n\n"
        f"**Status:** `{payload['status']}`  \n"
        f"**Recommendation:** `{payload['recommendation']}`\n\n"
        "## Stop condition\n\n"
        f"No move plan is authorized: {payload['message']}\n\n"
        "No Java framework convention was inferred. Resolve the stated "
        "constraint, obtain explicit human judgments, and rerun.\n"
    )


def write_terminal(
    args: argparse.Namespace,
    inspection: pathlib.Path,
    proposal: pathlib.Path,
    *,
    status: str,
    recommendation: str,
    failure_kind: str,
    message: str,
) -> None:
    payload = terminal_payload(
        args,
        status=status,
        recommendation=recommendation,
        failure_kind=failure_kind,
        message=message,
    )
    write_atomic(inspection, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_atomic(proposal, render_terminal(payload))


def jdk_feature(java: str, root: pathlib.Path) -> tuple[int | None, str]:
    try:
        result = subprocess.run(
            [java, "-version"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    rendered = (result.stdout + result.stderr).strip()
    match = re.search(r'(?:version\s+")?(\d+)(?:\.\d+)*', rendered)
    if result.returncode or match is None:
        return None, rendered or "cannot determine Java version"
    return int(match.group(1)), rendered


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--cluster-judgment", required=True, choices=("split", "cohesive"))
    parser.add_argument(
        "--convention-judgment",
        required=True,
        choices=("approve-subpackage", "deny-subpackage"),
    )
    parser.add_argument("--project-root", type=pathlib.Path, required=True)
    parser.add_argument("--minimum-jdk", type=int, default=17)
    parser.add_argument("--inspection", type=pathlib.Path, required=True)
    parser.add_argument("--proposal", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)
    if args.minimum_jdk < 17:
        parser.error("--minimum-jdk must be at least 17")
    args.project_root = args.project_root.resolve()
    if not args.project_root.is_dir() or args.project_root.is_symlink():
        parser.error("--project-root must be a non-symlink directory")
    try:
        args.inspection = artifact_path(args.project_root, args.inspection, "inspection")
        args.proposal = artifact_path(args.project_root, args.proposal, "proposal")
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    java = shutil.which("java")
    javac = shutil.which("javac")
    if not java or not javac:
        write_terminal(
            args,
            args.inspection,
            args.proposal,
            status="unsupported",
            recommendation="defer_tool_missing",
            failure_kind="jdk_tool_missing",
            message="JDK java and javac executables are required from PATH.",
        )
        return 0
    feature, rendered = jdk_feature(java, args.project_root)
    if feature is None:
        write_terminal(
            args,
            args.inspection,
            args.proposal,
            status="unsupported",
            recommendation="defer_tool_missing",
            failure_kind="jdk_version_unavailable",
            message=rendered,
        )
        return 0
    if feature < args.minimum_jdk:
        write_terminal(
            args,
            args.inspection,
            args.proposal,
            status="unsupported",
            recommendation="defer_jdk_version",
            failure_kind="jdk_version_too_old",
            message=f"JDK {feature} is below required JDK {args.minimum_jdk}.",
        )
        return 0

    helper = pathlib.Path(__file__).resolve().with_name("propose_java.java")
    if not helper.is_file():
        write_terminal(
            args,
            args.inspection,
            args.proposal,
            status="unsupported",
            recommendation="defer_tool_missing",
            failure_kind="java_helper_missing",
            message="The copied skill is missing scripts/propose_java.java.",
        )
        return 0
    command = [
        java,
        str(helper),
        "--parent", args.parent,
        "--prefix", args.prefix,
        "--cluster-judgment", args.cluster_judgment,
        "--convention-judgment", args.convention_judgment,
        "--project-root", str(args.project_root),
        "--minimum-jdk", str(args.minimum_jdk),
        "--inspection", str(args.inspection),
        "--proposal", str(args.proposal),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=args.project_root,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        write_terminal(
            args,
            args.inspection,
            args.proposal,
            status="failed",
            recommendation="defer_java_analysis",
            failure_kind="java_helper_failure",
            message=str(exc),
        )
        return 2
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if not args.inspection.is_file() or not args.proposal.is_file():
        write_terminal(
            args,
            args.inspection,
            args.proposal,
            status="failed",
            recommendation="defer_java_analysis",
            failure_kind="java_helper_no_artifact",
            message=f"Java helper exited {result.returncode} without both artifacts.",
        )
        return 2
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
