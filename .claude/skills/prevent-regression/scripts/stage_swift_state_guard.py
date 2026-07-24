#!/usr/bin/env python3
"""Stage and prove one exact Swift enum-property compile-time guard."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _helper() -> Any:
    candidates = [Path(__file__).with_name("swift_accepted_evidence.py")]
    candidates.extend(
        parent / "_swift-semantic-readonly" / "swift_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied Swift accepted-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("swift_guard_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Swift accepted-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()
PINNED_SWIFT = (6, 3, 3)


def _run(argv: list[str], root: Path, *, timeout: int = 180) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout,
            env={
                **os.environ,
                "http_proxy": "http://127.0.0.1:9",
                "https_proxy": "http://127.0.0.1:9",
                "ALL_PROXY": "http://127.0.0.1:9",
            },
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"argv": argv, "returncode": 124, "stdout": "", "stderr": str(exc)}
    return {
        "argv": argv,
        "returncode": result.returncode,
        "stdout": result.stdout[-6000:],
        "stderr": result.stderr[-6000:],
    }


def _version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"Apple Swift version\s+(\d+)\.(\d+)(?:\.(\d+))?", text)
    return tuple(int(value or 0) for value in match.groups()) if match else None


def _toolchain(
    swift: Path, swiftc: Path, swift_format: Path, root: Path
) -> tuple[Path, Path, Path, dict[str, Any]]:
    try:
        tools = [path.resolve(strict=True) for path in (swift, swiftc, swift_format)]
    except OSError as exc:
        raise EVIDENCE.EvidenceError("partial", "toolchain_unavailable", str(exc)) from exc
    if not all(path.is_file() and os.access(path, os.X_OK) for path in tools):
        raise EVIDENCE.EvidenceError(
            "partial", "toolchain_unavailable", "Swift tools must be executable files"
        )
    swift_path, swiftc_path, format_path = tools
    swift_version = _run([str(swift_path), "--version"], root, timeout=20)
    swiftc_version = _run([str(swiftc_path), "--version"], root, timeout=20)
    if (
        swift_version["returncode"]
        or swiftc_version["returncode"]
        or _version(swift_version["stdout"] + swift_version["stderr"]) != PINNED_SWIFT
        or _version(swiftc_version["stdout"] + swiftc_version["stderr"]) != PINNED_SWIFT
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "compiler_version_unsupported", "Apple Swift 6.3.3 is required"
        )
    format_version = _run([str(format_path), "--version"], root, timeout=20)
    if format_version["returncode"]:
        raise EVIDENCE.EvidenceError(
            "partial", "swift_format_unavailable", "swift-format version probe failed"
        )
    return (
        swift_path,
        swiftc_path,
        format_path,
        {
            "swift": swift_version,
            "swiftc": swiftc_version,
            "swift_format": format_version,
        },
    )


def _proposal(root: Path, supplied: Path) -> tuple[Path, dict[str, Any]]:
    path = EVIDENCE.safe_project_path(root, supplied, "Swift enum proposal")
    payload = EVIDENCE.read_json(path, "Swift enum proposal")
    native = payload.get("native")
    selected_sources = payload.get("selected_sources")
    if (
        payload.get("schema_version") != "swift-enum-proposal-v1"
        or payload.get("language") != "swift"
        or payload.get("status") != "review_required"
        or payload.get("outcome") != "proposal_ready"
        or payload.get("read_only") is not True
        or payload.get("source_mutations") != 0
        or payload.get("boundary_verdicts") != EVIDENCE.STATE_GATES
        or not isinstance(native, dict)
        or not isinstance(selected_sources, list)
        or not selected_sources
        or not all(isinstance(row, str) and row.endswith(".swift") for row in selected_sources)
        or not isinstance(payload.get("target", {}).get("authority"), dict)
        or not isinstance(payload.get("proposed_enum"), dict)
        or not EVIDENCE.valid_hashed_object(payload, "artifact_sha256")
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "proposal_invalid", "fresh exact Swift enum proposal is required"
        )
    return path, payload


def _acceptance(
    root: Path, supplied: Path, proposal_path: Path, proposal: dict[str, Any]
) -> tuple[Path, dict[str, Any], list[dict[str, str]]]:
    path = EVIDENCE.safe_project_path(root, supplied, "accepted Swift migration")
    payload = EVIDENCE.read_json(path, "accepted Swift migration")
    current = EVIDENCE.source_hashes(root)
    if (
        payload.get("schema_version") != "swift-enum-migration-acceptance-v1"
        or payload.get("language") != "swift"
        or payload.get("status") != "accepted"
        or payload.get("decision") != "approve-exact-property-type-guard"
        or payload.get("targets_sha256") != EVIDENCE.file_hash(proposal_path)
        or payload.get("authority") != proposal.get("target", {}).get("authority")
        or payload.get("enum") != proposal.get("proposed_enum")
        or payload.get("boundary_verdicts") != EVIDENCE.STATE_GATES
        or payload.get("package_sha256") != proposal.get("package_sha256")
        or payload.get("migrated_source_hashes") != current
        or not isinstance(payload.get("reviewer"), str)
        or not payload["reviewer"].strip()
        or not isinstance(payload.get("notes"), str)
        or not payload["notes"].strip()
        or not EVIDENCE.valid_hashed_object(payload, "acceptance_sha256")
    ):
        raise EVIDENCE.EvidenceError(
            "partial",
            "migration_acceptance_invalid",
            "fresh exact migrated-tree authority is required",
        )
    package = root / "Package.swift"
    if not package.is_file() or EVIDENCE.file_hash(package) != payload["package_sha256"]:
        raise EVIDENCE.EvidenceError(
            "partial", "package_stale", "accepted package identity changed"
        )
    edits = payload.get("reversion_edits")
    if not isinstance(edits, list) or not edits:
        raise EVIDENCE.EvidenceError(
            "partial", "reversion_invalid", "accepted exact String reversion is required"
        )
    for edit in edits:
        if (
            not isinstance(edit, dict)
            or set(edit) != {"path", "migrated", "reverted"}
            or not all(isinstance(edit.get(key), str) and edit[key] for key in edit)
            or edit["migrated"] == edit["reverted"]
        ):
            raise EVIDENCE.EvidenceError(
                "failed", "reversion_invalid", "reversion edit is malformed"
            )
        EVIDENCE.safe_project_path(root, edit["path"], "reversion path")
    return path, payload, current


def _swiftpm_build(swift: Path, root: Path, state: Path, configuration: str) -> dict[str, Any]:
    for name in ("cache", "config", "security", "build"):
        (state / name).mkdir(parents=True, exist_ok=True)
    argv = [
        str(swift),
        "build",
        "--package-path",
        str(root),
        "--cache-path",
        str(state / "cache"),
        "--config-path",
        str(state / "config"),
        "--security-path",
        str(state / "security"),
        "--scratch-path",
        str(state / "build"),
        "--disable-dependency-cache",
        "--manifest-cache",
        "local",
        "--disable-netrc",
        "--disable-keychain",
        "--disable-prefetching",
        "--disable-automatic-resolution",
        "--configuration",
        configuration,
    ]
    return _run(argv, root)


def _native(
    root: Path,
    state: Path,
    swift: Path,
    swift_format: Path,
    contract: dict[str, str],
) -> dict[str, Any]:
    build = _swiftpm_build(swift, root, state, contract["configuration"])
    formatted = _run([str(swift_format), "lint", "--strict", "--recursive", "Sources"], root)
    checks: dict[str, Any] = {"build": build, "format": formatted}
    passed = build["returncode"] == 0 and formatted["returncode"] == 0
    for name, product, expected in (
        ("check", contract["check_product"], contract["expected_check"]),
        ("smoke", contract["smoke_product"], contract["expected_smoke"]),
    ):
        executable = state / "build" / contract["configuration"] / product
        result = _run([str(executable)], root, timeout=30)
        checks[name] = result
        passed = passed and result["returncode"] == 0 and result["stdout"].strip() == expected
    checks["passed"] = passed
    return checks


def _guard_text(proposal: dict[str, Any]) -> str:
    authority = proposal["target"]["authority"]
    enum = proposal["proposed_enum"]
    return f"""private func exactAcceptedState(_ value: {authority['owner']}) -> {enum['type_name']} {{
  value.{authority['field']}
}}
"""


def _compile_guard(
    root: Path,
    swiftc: Path,
    proposal: dict[str, Any],
    guard: Path,
) -> dict[str, Any]:
    sources = [
        str(EVIDENCE.safe_project_path(root, row, "selected Swift source"))
        for row in proposal["selected_sources"]
    ]
    argv = [
        str(swiftc),
        "-typecheck",
        "-parse-as-library",
        "-swift-version",
        "6",
        "-module-name",
        proposal["proposed_enum"]["module"],
        *sources,
        str(guard),
    ]
    return _run(argv, root)


def _apply_reversion(root: Path, edits: list[dict[str, str]]) -> None:
    for edit in edits:
        path = EVIDENCE.safe_project_path(root, edit["path"], "reversion path")
        text = path.read_text(encoding="utf-8")
        if text.count(edit["migrated"]) != 1:
            raise EVIDENCE.EvidenceError(
                "partial", "reversion_stale", f"accepted reversion anchor changed: {edit['path']}"
            )
        path.write_text(text.replace(edit["migrated"], edit["reverted"], 1), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--accepted-migration", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--swift", type=Path, default=Path("/usr/bin/swift"))
    parser.add_argument("--swiftc", type=Path, default=Path("/usr/bin/swiftc"))
    parser.add_argument(
        "--swift-format",
        type=Path,
        default=Path("/Library/Developer/CommandLineTools/usr/bin/swift-format"),
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, "prevent-regression")
        targets_path, proposal = _proposal(root, args.targets)
        acceptance_path, acceptance, before = _acceptance(
            root, args.accepted_migration, targets_path, proposal
        )
        swift, swiftc, swift_format, tools = _toolchain(
            args.swift, args.swiftc, args.swift_format, root
        )
        guard_text = _guard_text(proposal)
        with tempfile.TemporaryDirectory(prefix="swift-state-guard-") as raw:
            temporary = Path(raw)
            guard = temporary / "ExactAcceptedStateGuard.swift"
            guard.write_text(guard_text, encoding="utf-8")
            guard_format = _run([str(swift_format), "lint", "--strict", str(guard)], root)
            migrated_native = _native(
                root, temporary / "migrated-native", swift, swift_format, proposal["native"]
            )
            migrated_guard = _compile_guard(root, swiftc, proposal, guard)
            reverted = temporary / "reverted"
            shutil.copytree(
                root,
                reverted,
                symlinks=True,
                ignore=shutil.ignore_patterns(".agents", ".build", ".git", ".swiftpm", "reports"),
            )
            _apply_reversion(reverted, acceptance["reversion_edits"])
            reverted_native = _native(
                reverted,
                temporary / "reverted-native",
                swift,
                swift_format,
                proposal["native"],
            )
            reverted_guard = _compile_guard(reverted, swiftc, proposal, guard)
        if guard_format["returncode"]:
            raise EVIDENCE.EvidenceError("failed", "guard_format_failed", guard_format["stderr"])
        if not migrated_native["passed"] or migrated_guard["returncode"] != 0:
            raise EVIDENCE.EvidenceError(
                "failed",
                "migrated_proof_failed",
                "accepted migrated tree or exact guard failed native proof",
            )
        diagnostics = reverted_guard["stdout"] + reverted_guard["stderr"]
        if (
            not reverted_native["passed"]
            or reverted_guard["returncode"] == 0
            or "String" not in diagnostics
            or proposal["proposed_enum"]["type_name"] not in diagnostics
        ):
            raise EVIDENCE.EvidenceError(
                "failed",
                "regression_proof_failed",
                "buildable String reversion must fail only with the exact-type guard",
            )
        if EVIDENCE.source_hashes(root) != before:
            raise EVIDENCE.EvidenceError(
                "failed", "source_mutated", "guard staging changed host source"
            )
        evidence = {
            "schema_version": "swift-exact-state-guard-v1",
            "language": "swift",
            "status": "verified",
            "outcome": "guard_staged",
            "staged_only": True,
            "installed": False,
            "source_mutations": 0,
            "authority": proposal["target"]["authority"],
            "enum": proposal["proposed_enum"],
            "guard_sha256": hashlib.sha256(guard_text.encode()).hexdigest(),
            "targets_sha256": EVIDENCE.file_hash(targets_path),
            "acceptance_sha256": EVIDENCE.file_hash(acceptance_path),
            "migrated_source_hashes": before,
            "human_authority": acceptance,
            "verification": {
                "toolchain": tools,
                "guard_format": guard_format,
                "migrated_native": migrated_native,
                "migrated_guard": migrated_guard,
                "reverted_native_without_guard": reverted_native,
                "reverted_guard": reverted_guard,
                "buildable_string_reversion": True,
                "regression_rejected": True,
            },
            "limits": [
                "one exact accepted Job.state property type only",
                "raw values, Codable behavior, reflection, dynamic dispatch, generated/macros/plugins, frameworks, external callers, conditional variants, ABI, and runtime behavior remain outside the guard",
            ],
        }
        evidence["artifact_sha256"] = EVIDENCE.canonical_hash(evidence)
        report = (
            "# Staged Swift exact-state guard\n\n"
            "The compile-time guard is verified but not installed. The accepted migrated tree "
            "passes build/check/smoke and guard typecheck; the accepted buildable String "
            "reversion passes native gates without the guard and fails with it. Installation "
            "requires separate human action.\n"
        )
        EVIDENCE.replace_bundle(
            output,
            {
                "ExactAcceptedStateGuard.swift": guard_text,
                "evidence.json": evidence,
                "proposal.md": report,
            },
        )
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "prevent-regression")
            payload, report = EVIDENCE.refusal("prevent-regression", exc)
            EVIDENCE.replace_bundle(output, {"evidence.json": payload, "proposal.md": report})
        except EVIDENCE.EvidenceError:
            pass
        print(f"stage_swift_state_guard.py: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
