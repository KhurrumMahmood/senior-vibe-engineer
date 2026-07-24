#!/usr/bin/env python3
"""Move one C source file under reviewed, content-addressed authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "c-source-move-evidence-v1"
REPORT_SCHEMA = "c-source-move-report-v1"
EXCLUDED_PARTS = frozenset({"build", "generated", "vendor", "dist", "out"})
INCLUDE_RE = re.compile(
    rb"(?m)^(?P<prefix>[ \t]*#[ \t]*include[ \t]*)\"(?P<path>[^\"\r\n]+)\""
)
ANY_INCLUDE_RE = re.compile(rb"(?m)^[ \t]*#[ \t]*include[ \t]+(?P<value>[^\r\n]+)")


class UserError(RuntimeError):
    """Unsafe or invalid input that must not mutate source."""


@dataclass(frozen=True)
class FileState:
    content: bytes
    mode: int


@dataclass(frozen=True)
class TreeState:
    files: dict[str, FileState]
    symlinks: dict[str, str]


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return _sha(rendered.encode("utf-8"))


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _relative(raw: Any, *, field: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise UserError(f"{field} must be a non-empty relative path")
    value = PurePosixPath(raw)
    if value.is_absolute() or ".." in value.parts or "." in value.parts:
        raise UserError(f"{field} must be a normalized relative path")
    return value.as_posix()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _excluded(path: Path, root: Path, report_dir: Path) -> bool:
    relative = path.relative_to(root)
    if relative.parts and relative.parts[0] == ".git":
        return True
    try:
        path.resolve().relative_to(report_dir.resolve())
    except ValueError:
        return False
    return True


def _snapshot(root: Path, report_dir: Path) -> TreeState:
    files: dict[str, FileState] = {}
    symlinks: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if _excluded(path, root, report_dir):
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            symlinks[relative] = os.readlink(path)
        elif path.is_file():
            files[relative] = FileState(
                path.read_bytes(), stat.S_IMODE(path.stat().st_mode)
            )
    return TreeState(files, symlinks)


def _source_state(state: TreeState) -> TreeState:
    files = {
        path: value
        for path, value in state.files.items()
        if path != "compile_commands.json" and not path.startswith(".native-build/")
    }
    symlinks = {
        path: value
        for path, value in state.symlinks.items()
        if not path.startswith(".native-build/")
    }
    return TreeState(files, symlinks)


def _tree_payload(state: TreeState) -> dict[str, Any]:
    return {
        "files": [
            {"path": path, "sha256": _sha(value.content), "mode": value.mode}
            for path, value in sorted(state.files.items())
        ],
        "symlinks": [
            {"path": path, "target": target}
            for path, target in sorted(state.symlinks.items())
        ],
    }


def _tree_hash(state: TreeState) -> str:
    return _canonical_hash(_tree_payload(state))


def _restore(root: Path, report_dir: Path, state: TreeState) -> None:
    current = _snapshot(root, report_dir)
    for relative in sorted(current.symlinks, reverse=True):
        (root / relative).unlink(missing_ok=True)
    for relative in sorted(current.files, reverse=True):
        (root / relative).unlink(missing_ok=True)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and not path.is_symlink() and not _excluded(path, root, report_dir):
            try:
                path.rmdir()
            except OSError:
                pass
    for relative, value in state.files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.content)
        path.chmod(value.mode)
    for relative, target in state.symlinks.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)


def _run(argv: list[str], root: Path, *, timeout: int = 120) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env={
                **os.environ,
                "ALL_PROXY": "http://127.0.0.1:9",
                "http_proxy": "http://127.0.0.1:9",
                "https_proxy": "http://127.0.0.1:9",
            },
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "argv": argv,
            "passed": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "argv": argv,
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _binary(raw: Any, *, name: str, version_args: list[str], minimum: tuple[int, ...]) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        raise UserError(f"c.{name} must name an executable")
    candidate = Path(raw)
    if candidate.parent == Path("."):
        found = shutil.which(raw)
        if found is None:
            raise UserError(f"configured {name} is unavailable")
        candidate = Path(found)
    path = candidate.resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise UserError(f"configured {name} is not executable")
    version = _run([str(path), *version_args], Path.cwd(), timeout=30)
    if not version["passed"]:
        raise UserError(f"configured {name} version probe failed")
    match = re.search(r"(\d+(?:\.\d+)+)", version["stdout"] + version["stderr"])
    if match is None:
        raise UserError(f"configured {name} emitted an unrecognized version")
    parts = tuple(int(item) for item in match.group(1).split("."))
    if parts < minimum:
        raise UserError(f"configured {name} is too old: {match.group(1)}")
    return {
        "path": str(path),
        "version": match.group(1),
        "sha256": _sha(path.read_bytes()),
    }


def _load_plan(path: Path, root: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UserError(f"cannot read JSON plan: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise UserError("plan must be a version 1 JSON object")
    moves = payload.get("moves")
    if not isinstance(moves, list) or len(moves) != 1:
        raise UserError("c_requires_exactly_one_move")
    move = moves[0]
    if not isinstance(move, dict) or move.get("mode") != "file":
        raise UserError("c_requires_one_file_move")
    source = _relative(move.get("from"), field="moves[0].from")
    destination = _relative(move.get("to"), field="moves[0].to")
    if not source.endswith(".c") or not destination.endswith(".c"):
        raise UserError("c move requires .c source and destination")
    if source == destination:
        raise UserError("source and destination must differ")
    if (payload.get("rewrite") or {}).get("code_imports") != "update-c":
        raise UserError('rewrite.code_imports must be "update-c"')
    config = payload.get("c")
    if not isinstance(config, dict):
        raise UserError("plan.c must be an object")
    compile_database = _relative(
        config.get("compile_database", "compile_commands.json"),
        field="c.compile_database",
    )
    native_target = config.get("native_target")
    smoke = _relative(config.get("smoke"), field="c.smoke")
    expected = config.get("smoke_expected_stdout")
    if not isinstance(native_target, str) or not native_target:
        raise UserError("c.native_target must be a non-empty string")
    if not isinstance(expected, str):
        raise UserError("c.smoke_expected_stdout must be a string")
    plan_resolved = path.resolve()
    if not _inside(plan_resolved, root) or plan_resolved.is_symlink():
        raise UserError("plan must be a regular file inside the project root")
    return {
        "raw": payload,
        "plan_relative": plan_resolved.relative_to(root).as_posix(),
        "source": source,
        "destination": destination,
        "compile_database": compile_database,
        "native_target": native_target,
        "smoke": smoke,
        "smoke_expected_stdout": expected,
        "clang": _binary(config.get("clang"), name="clang", version_args=["--version"], minimum=(21, 0)),
        "make": _binary(config.get("make"), name="make", version_args=["--version"], minimum=(3, 81)),
    }


def _role_refused(path: str) -> bool:
    return bool(EXCLUDED_PARTS.intersection(PurePosixPath(path).parts))


def _has_symlink(path: Path, root: Path) -> bool:
    current = path
    while current != root:
        if current.is_symlink():
            return True
        current = current.parent
    return root.is_symlink()


def _database(root: Path, relative: str, source: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blocked: list[dict[str, Any]] = []
    path = root / relative
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [], [{"kind": "c_compile_database_invalid", "path": relative}]
    if not isinstance(payload, list):
        return [], [{"kind": "c_compile_database_invalid", "path": relative}]
    normalized: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict) or not isinstance(row.get("file"), str):
            blocked.append({"kind": "c_compile_database_invalid", "path": relative})
            continue
        try:
            file_path = Path(row["file"]).resolve().relative_to(root).as_posix()
        except ValueError:
            blocked.append({"kind": "c_compile_database_outside_root", "file": row["file"]})
            continue
        arguments = row.get("arguments")
        if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
            blocked.append({"kind": "c_compile_database_arguments_invalid", "file": file_path})
            continue
        if "-std=c17" not in arguments or "-c" not in arguments:
            blocked.append({"kind": "c_compile_database_wrong_mode", "file": file_path})
        normalized.append({"file": file_path, "arguments": arguments})
    if sum(row["file"] == source for row in normalized) != 1:
        blocked.append({"kind": "c_compile_database_source_incomplete", "source": source})
    return normalized, blocked


def _change(
    file_before: str,
    file_after: str,
    kind: str,
    old: str,
    new: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    return {
        "file_before": file_before,
        "file_after": file_after,
        "kind": kind,
        "old": old,
        "new": new,
        "start": start,
        "end": end,
    }


def _plan_changes(
    root: Path, report_dir: Path, plan_path: Path, plan: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source = plan["source"]
    destination = plan["destination"]
    blocked: list[dict[str, Any]] = []
    source_path = root / source
    destination_path = root / destination
    if _role_refused(source):
        blocked.append({"kind": "c_source_role_refused", "path": source})
    if _role_refused(destination):
        blocked.append({"kind": "c_destination_role_refused", "path": destination})
    if not source_path.is_file() or source_path.is_symlink():
        blocked.append({"kind": "c_symlink_boundary" if source_path.is_symlink() else "c_source_missing", "path": source})
    if destination_path.exists() or destination_path.is_symlink():
        blocked.append({"kind": "c_destination_exists", "path": destination})
    if _has_symlink(source_path, root) or _has_symlink(destination_path.parent, root):
        blocked.append({"kind": "c_symlink_boundary", "path": source})
    if blocked:
        return [], blocked
    content = source_path.read_bytes()
    literal_spans = {(match.start(), match.end()) for match in INCLUDE_RE.finditer(content)}
    for match in ANY_INCLUDE_RE.finditer(content):
        if (match.start(), match.end()) not in literal_spans and not match.group("value").lstrip().startswith(b"<"):
            blocked.append({"kind": "c_dynamic_include_refused", "path": source})
    changes: list[dict[str, Any]] = []
    for match in INCLUDE_RE.finditer(content):
        old = match.group("path").decode("utf-8")
        resolved = (source_path.parent / old).resolve()
        if not _inside(resolved, root) or not resolved.is_file():
            continue
        new = os.path.relpath(resolved, (root / destination).parent).replace(os.sep, "/")
        if new != old:
            changes.append(
                _change(
                    source,
                    destination,
                    "c_relative_include",
                    old,
                    new,
                    match.start("path"),
                    match.end("path"),
                )
            )
    makefile = root / "Makefile"
    if not makefile.is_file() or makefile.is_symlink():
        blocked.append({"kind": "c_makefile_missing"})
    else:
        make_content = makefile.read_bytes()
        old = source.encode("utf-8")
        start = 0
        found = 0
        while True:
            index = make_content.find(old, start)
            if index < 0:
                break
            changes.append(
                _change(
                    "Makefile",
                    "Makefile",
                    "make_path",
                    source,
                    destination,
                    index,
                    index + len(old),
                )
            )
            found += 1
            start = index + len(old)
        if not found:
            blocked.append({"kind": "c_make_source_path_missing", "path": source})
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or _excluded(path, root, report_dir):
            continue
        relative = path.relative_to(root).as_posix()
        if relative in {
            source,
            "Makefile",
            plan["compile_database"],
            plan_path.relative_to(root).as_posix(),
        }:
            continue
        if source.encode("utf-8") in path.read_bytes():
            kind = "c_excluded_old_identity" if _role_refused(relative) else "c_unresolved_old_identity"
            blocked.append({"kind": kind, "path": relative})
    return sorted(changes, key=lambda row: (row["file_before"], row["start"])), blocked


def _apply_changes(content: bytes, changes: list[dict[str, Any]]) -> bytes:
    result = content
    for row in sorted(changes, key=lambda item: item["start"], reverse=True):
        old = row["old"].encode("utf-8")
        if result[row["start"] : row["end"]] != old:
            raise UserError(f"planned edit span is stale in {row['file_before']}")
        result = result[: row["start"]] + row["new"].encode("utf-8") + result[row["end"] :]
    return result


def _expected(before: TreeState, plan: dict[str, Any], changes: list[dict[str, Any]]) -> TreeState:
    files = dict(before.files)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in changes:
        grouped.setdefault(row["file_before"], []).append(row)
    for relative, rows in grouped.items():
        value = files[relative]
        updated = _apply_changes(value.content, rows)
        if relative == plan["source"]:
            files.pop(relative)
            files[plan["destination"]] = FileState(updated, value.mode)
        else:
            files[relative] = FileState(updated, value.mode)
    return TreeState(files, dict(before.symlinks))


def _native(root: Path, plan: dict[str, Any], *, refresh: bool) -> dict[str, Any]:
    make = plan["make"]["path"]
    clang = plan["clang"]["path"]
    targets = (["clean", "compile-db"] if refresh else []) + [plan["native_target"]]
    make_result = _run([make, *targets, f"CC={clang}"], root)
    smoke = _run([str(root / plan["smoke"])], root) if make_result["passed"] else {
        "argv": [str(root / plan["smoke"])],
        "passed": False,
        "returncode": None,
        "stdout": "",
        "stderr": "native target failed",
    }
    if smoke["passed"] and smoke["stdout"] != plan["smoke_expected_stdout"]:
        smoke["passed"] = False
        smoke["stderr"] = "unexpected smoke stdout"
    return {"make": make_result, "smoke": smoke}


def _analysis(
    root: Path, report_dir: Path, plan_path: Path, plan: dict[str, Any]
) -> tuple[TreeState, TreeState, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    full = _snapshot(root, report_dir)
    before = _source_state(full)
    changes, blocked = _plan_changes(root, report_dir, plan_path, plan)
    _, database_blocked = _database(root, plan["compile_database"], plan["source"])
    blocked.extend(database_blocked)
    native = _native(root, plan, refresh=False) if not blocked else {}
    if native and not all(row["passed"] for row in native.values()):
        blocked.append({"kind": "c_native_preflight_failed"})
    expected = _expected(before, plan, changes) if not blocked else before
    return full, before, changes, blocked, {"native": native, "expected": expected}


def _evidence(
    plan_path: Path,
    plan: dict[str, Any],
    before: TreeState,
    expected: TreeState,
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "plan_sha256": _sha(plan_path.read_bytes()),
        "plan": plan["raw"],
        "source": plan["source"],
        "destination": plan["destination"],
        "source_tree_sha256": _tree_hash(before),
        "expected_after_tree_sha256": _tree_hash(expected),
        "tooling": {"clang": plan["clang"], "make": plan["make"]},
        "exact_changes": changes,
    }
    payload["evidence_sha256"] = _canonical_hash(payload)
    return payload


def _load_evidence(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UserError(f"cannot read evidence: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise UserError("evidence schema is invalid")
    claimed = payload.get("evidence_sha256")
    raw = dict(payload)
    raw.pop("evidence_sha256", None)
    if claimed != _canonical_hash(raw):
        raise UserError("evidence hash is invalid")
    return payload


def _old_identity(root: Path, report_dir: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    old = plan["source"].encode("utf-8")
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or _excluded(path, root, report_dir):
            continue
        relative = path.relative_to(root).as_posix()
        if relative in {plan["compile_database"], plan["plan_relative"]}:
            continue
        if old in path.read_bytes():
            rows.append({"path": relative})
    return rows


def _report(
    *,
    mode: str,
    status: str,
    plan: dict[str, Any] | None,
    blocked: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    native: dict[str, Any] | None = None,
    evidence_sha: str | None = None,
    exact: dict[str, Any] | None = None,
    rolled_back: bool = False,
    old_identity: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema": REPORT_SCHEMA,
        "c": {
            "mode": mode,
            "status": status,
            "source": plan["source"] if plan else None,
            "destination": plan["destination"] if plan else None,
            "blocked": blocked,
            "exact_changes": changes,
            "native_preflight" if mode == "dry-run" else "native": native or {},
            "evidence_sha256": evidence_sha,
            "exact_after_tree": exact or {},
            "old_identity_remaining": old_identity or [],
            "rolled_back": rolled_back,
        },
    }


def _write_report(report_dir: Path, payload: dict[str, Any]) -> None:
    _atomic_json(report_dir / "report.json", payload)


def run(
    *,
    root: Path,
    plan_path: Path,
    report_dir: Path,
    mode: str,
    evidence_path: Path | None,
    approval: str | None,
) -> tuple[int, dict[str, Any]]:
    report_dir.mkdir(parents=True, exist_ok=True)
    evidence_output = report_dir / "evidence.json"
    try:
        plan = _load_plan(plan_path, root)
    except UserError as exc:
        evidence_output.unlink(missing_ok=True)
        payload = _report(
            mode=mode,
            status="failed",
            plan=None,
            blocked=[{"kind": str(exc)}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload

    if mode == "dry-run":
        _, before, changes, blocked, facts = _analysis(root, report_dir, plan_path, plan)
        if blocked:
            evidence_output.unlink(missing_ok=True)
            status = "unsupported" if any("role_refused" in row["kind"] for row in blocked) else "partial"
            payload = _report(
                mode=mode,
                status=status,
                plan=plan,
                blocked=blocked,
                changes=changes,
                native=facts["native"],
            )
            _write_report(report_dir, payload)
            return 2, payload
        evidence = _evidence(plan_path, plan, before, facts["expected"], changes)
        _atomic_json(evidence_output, evidence)
        payload = _report(
            mode=mode,
            status="complete",
            plan=plan,
            blocked=[],
            changes=changes,
            native=facts["native"],
            evidence_sha=evidence["evidence_sha256"],
        )
        _write_report(report_dir, payload)
        return 0, payload

    if evidence_path is None:
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": "c_evidence_required"}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload
    try:
        evidence = _load_evidence(evidence_path)
    except UserError as exc:
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": str(exc)}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload

    if mode == "check":
        current = _source_state(_snapshot(root, report_dir))
        old_identity = _old_identity(root, report_dir, plan)
        database, database_blocked = _database(
            root, plan["compile_database"], plan["destination"]
        )
        native = _native(root, plan, refresh=False) if not database_blocked else {}
        blocked = list(database_blocked)
        if _tree_hash(current) != evidence.get("expected_after_tree_sha256"):
            blocked.append({"kind": "c_after_tree_mismatch"})
        if old_identity:
            blocked.append({"kind": "c_old_identity_remaining"})
        if native and not all(row["passed"] for row in native.values()):
            blocked.append({"kind": "c_native_check_failed"})
        payload = _report(
            mode=mode,
            status="complete" if not blocked else "failed",
            plan=plan,
            blocked=blocked,
            changes=[],
            native=native,
            evidence_sha=evidence.get("evidence_sha256"),
            exact={"passed": not any(row["kind"] == "c_after_tree_mismatch" for row in blocked)},
            old_identity=old_identity,
        )
        _write_report(report_dir, payload)
        return (0 if not blocked else 2), payload

    if approval != evidence.get("evidence_sha256"):
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": "c_evidence_approval_mismatch"}],
            changes=[],
        )
        _write_report(report_dir, payload)
        return 2, payload
    full, before, changes, blocked, facts = _analysis(root, report_dir, plan_path, plan)
    current_evidence = _evidence(plan_path, plan, before, facts["expected"], changes)
    if blocked or current_evidence != evidence:
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[*blocked, {"kind": "c_stale_evidence"}],
            changes=changes,
        )
        _write_report(report_dir, payload)
        return 2, payload

    try:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in changes:
            grouped.setdefault(row["file_before"], []).append(row)
        for relative, rows in grouped.items():
            path = root / relative
            updated = _apply_changes(path.read_bytes(), rows)
            if relative == plan["source"]:
                destination = root / plan["destination"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                mode_bits = stat.S_IMODE(path.stat().st_mode)
                destination.write_bytes(updated)
                destination.chmod(mode_bits)
                path.unlink()
            else:
                path.write_bytes(updated)
        native = _native(root, plan, refresh=True)
        current = _source_state(_snapshot(root, report_dir))
        exact_passed = _tree_hash(current) == evidence["expected_after_tree_sha256"]
        old_identity = _old_identity(root, report_dir, plan)
        _, database_blocked = _database(
            root, plan["compile_database"], plan["destination"]
        )
        if (
            not all(row["passed"] for row in native.values())
            or not exact_passed
            or old_identity
            or database_blocked
        ):
            raise UserError("c_postflight_failed")
    except (OSError, UserError) as exc:
        _restore(root, report_dir, full)
        payload = _report(
            mode=mode,
            status="failed",
            plan=plan,
            blocked=[{"kind": str(exc)}],
            changes=changes,
            native=locals().get("native", {}),
            rolled_back=True,
        )
        _write_report(report_dir, payload)
        return 2, payload
    payload = _report(
        mode=mode,
        status="complete",
        plan=plan,
        blocked=[],
        changes=changes,
        native=native,
        evidence_sha=evidence["evidence_sha256"],
        exact={"passed": True, "actual_fingerprint": _tree_hash(current)},
        old_identity=[],
    )
    _write_report(report_dir, payload)
    return 0, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--check", action="store_true")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--approve-evidence-sha256")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    if not root.is_dir() or root.is_symlink():
        print("project root must be a non-symlink directory", file=sys.stderr)
        return 2
    mode = "dry-run" if args.dry_run else "apply" if args.apply else "check"
    code, payload = run(
        root=root,
        plan_path=args.plan.resolve(),
        report_dir=args.report_dir.resolve(),
        mode=mode,
        evidence_path=args.evidence.resolve() if args.evidence else None,
        approval=args.approve_evidence_sha256,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
