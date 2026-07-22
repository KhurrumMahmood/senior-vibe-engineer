#!/usr/bin/env python3
"""Extract bounded Swift declaration facts with the host's Swift compiler.

This helper deliberately uses only successful ``swiftc -typecheck`` and
``swiftc -dump-ast`` output.  The textual compiler AST is validated narrowly;
it is not SwiftSyntax and does not establish resolved references or complete
project semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


ANALYZER = "swiftc-typecheck-dump-ast"
MINIMUM_VERSION = (6, 0, 0)
PROCESS_TIMEOUT_SECONDS = 30
_VERSION = re.compile(r"\bSwift version (\d+)\.(\d+)(?:\.(\d+))?\b", re.IGNORECASE)
_RANGE = re.compile(r"range=\[.*:(\d+):\d+ - line:(\d+):\d+\]")
_DECLARATION = re.compile(
    r'^\s*\((protocol|struct_decl|class_decl|enum_decl|actor_decl|func_decl|constructor_decl)\b.*?"([^"]+)"'
)
_NOMINAL_KINDS = {
    "protocol": "protocol",
    "struct_decl": "struct",
    "class_decl": "class",
    "enum_decl": "enum",
    "actor_decl": "actor",
}


def _payload(status: str, **extra: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "analyzer": ANALYZER,
        "status": status,
        "minimum_swift_version": ".".join(map(str, MINIMUM_VERSION)),
        "claim_boundary": {
            "swift_syntax": False,
            "resolved_references": False,
            "complete_project_semantics": False,
        },
        **extra,
    }


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )


def _diagnostic(completed: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())


def _toolchain() -> tuple[str | None, dict[str, object] | None]:
    swiftc = shutil.which("swiftc")
    if swiftc is None:
        return None, _payload(
            "unsupported",
            failure_kind="swiftc-tool-missing",
            message="Swift compiler is unavailable on PATH",
            files=[],
        )
    try:
        completed = _run([swiftc, "--version"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, _payload(
            "failed",
            failure_kind="swiftc-version-failed",
            message=f"cannot determine Swift compiler version: {exc}",
            files=[],
        )
    rendered = _diagnostic(completed)
    match = _VERSION.search(rendered)
    if completed.returncode != 0 or match is None:
        return None, _payload(
            "failed",
            failure_kind="swiftc-version-failed",
            message=f"cannot determine Swift compiler version: {rendered or 'unknown error'}",
            files=[],
        )
    version = tuple(int(part or 0) for part in match.groups())
    rendered_version = ".".join(map(str, version))
    if version < MINIMUM_VERSION:
        return None, _payload(
            "unsupported",
            failure_kind="swiftc-version-too-old",
            message=(
                "Swift compiler >= "
                + ".".join(map(str, MINIMUM_VERSION))
                + f" is required; found {rendered_version}"
            ),
            actual_swift_version=rendered_version,
            files=[],
        )
    return swiftc, {"actual_swift_version": rendered_version}


def _lines_for_declaration(match: re.Match[str], line: str) -> tuple[int, int] | None:
    span = _RANGE.search(line)
    if span is None:
        return None
    return int(span.group(1)), int(span.group(2))


def _base_name(name: str) -> str:
    return name.split("(", 1)[0]


def _parse_ast(source: Path, rendered: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    declarations: list[dict[str, Any]] = []
    members: dict[str, list[dict[str, Any]]] = {}
    current_nominal: str | None = None
    current_indent = -1
    for line in rendered.splitlines():
        match = _DECLARATION.match(line)
        if match is None:
            continue
        span = _lines_for_declaration(match, line)
        if span is None:
            continue
        node_kind, name = match.groups()
        indent = len(line) - len(line.lstrip())
        start, end = span
        if node_kind in _NOMINAL_KINDS and indent == 2:
            current_nominal = name
            current_indent = indent
            declarations.append(
                {
                    "name": name,
                    "kind": _NOMINAL_KINDS[node_kind],
                    "lineno": start,
                    "end_lineno": end,
                }
            )
            members.setdefault(name, [])
            continue
        if indent <= current_indent:
            current_nominal = None
        if current_nominal is None or indent != current_indent + 2:
            continue
        if node_kind not in {"func_decl", "constructor_decl"} or " implicit " in line:
            continue
        cluster_name = _base_name(name)
        members[current_nominal].append(
            {
                "name": f"{current_nominal}.{cluster_name}",
                "cluster_name": cluster_name,
                "kind": "initializer" if node_kind == "constructor_decl" else "method",
                "lineno": start,
                "end_lineno": end,
                "loc": max(1, end - start + 1),
            }
        )

    if not declarations:
        raise ValueError("compiler AST contained no validated top-level nominal declarations")
    symbols: list[dict[str, Any]] = []
    for declaration in declarations:
        direct_members = members[declaration["name"]]
        if len(direct_members) >= 3:
            symbols.extend(direct_members)
        else:
            symbols.append(
                {
                    "name": declaration["name"],
                    "cluster_name": declaration["name"],
                    "kind": declaration["kind"],
                    "lineno": declaration["lineno"],
                    "end_lineno": declaration["end_lineno"],
                    "loc": max(1, declaration["end_lineno"] - declaration["lineno"] + 1),
                }
            )
    return declarations, symbols


def _file_evidence(swiftc: str, source: Path) -> tuple[dict[str, object], str | None]:
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    try:
        typed = _run([swiftc, "-typecheck", str(source)])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "file": str(source),
            "status": "failed",
            "failure_kind": "swiftc-typecheck-failed",
            "diagnostic": str(exc),
            "source_sha256": fingerprint,
        }, "failed"
    if typed.returncode != 0:
        try:
            parsed = _run([swiftc, "-frontend", "-parse", str(source)])
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "file": str(source),
                "status": "failed",
                "failure_kind": "swiftc-parse-failed",
                "diagnostic": str(exc),
                "source_sha256": fingerprint,
            }, "failed"
        if parsed.returncode != 0:
            return {
                "file": str(source),
                "status": "failed",
                "failure_kind": "swift-syntax-error",
                "diagnostic": _diagnostic(parsed) or _diagnostic(typed),
                "source_sha256": fingerprint,
            }, "failed"
        return {
            "file": str(source),
            "status": "partial",
            "failure_kind": "standalone-typecheck-incomplete",
            "diagnostic": _diagnostic(typed),
            "source_sha256": fingerprint,
            "declarations": [],
            "symbols": [],
        }, "partial"
    try:
        dumped = _run([swiftc, "-dump-ast", str(source)])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "file": str(source),
            "status": "failed",
            "failure_kind": "swiftc-ast-failed",
            "diagnostic": str(exc),
            "source_sha256": fingerprint,
        }, "failed"
    if dumped.returncode != 0:
        return {
            "file": str(source),
            "status": "failed",
            "failure_kind": "swiftc-ast-failed",
            "diagnostic": _diagnostic(dumped),
            "source_sha256": fingerprint,
        }, "failed"
    try:
        declarations, symbols = _parse_ast(source, dumped.stdout)
    except ValueError as exc:
        return {
            "file": str(source),
            "status": "failed",
            "failure_kind": "swiftc-ast-unrecognized",
            "diagnostic": str(exc),
            "source_sha256": fingerprint,
        }, "failed"
    return {
        "file": str(source),
        "status": "complete",
        "source_sha256": fingerprint,
        "declarations": declarations,
        "symbols": symbols,
    }, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", action="append", required=True, type=Path)
    args = parser.parse_args(argv)
    swiftc, tool_evidence = _toolchain()
    if swiftc is None:
        assert tool_evidence is not None
        print(json.dumps(tool_evidence))
        return 2
    assert tool_evidence is not None
    files: list[dict[str, object]] = []
    terminal: str | None = None
    for source in args.file:
        try:
            evidence, outcome = _file_evidence(swiftc, source.resolve(strict=True))
        except (OSError, UnicodeError) as exc:
            evidence, outcome = ({
                "file": str(source),
                "status": "failed",
                "failure_kind": "swift-source-read-failed",
                "diagnostic": str(exc),
            }, "failed")
        files.append(evidence)
        if outcome == "failed":
            terminal = "failed"
        elif outcome == "partial" and terminal is None:
            terminal = "partial"
    status = terminal or "complete"
    failure_rows = [row for row in files if row["status"] != "complete"]
    payload = _payload(
        status,
        **tool_evidence,
        files=files,
        failure_kind=(failure_rows[0].get("failure_kind") if failure_rows else None),
        message=(failure_rows[0].get("diagnostic") if failure_rows else None),
    )
    print(json.dumps(payload))
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
