#!/usr/bin/env python3
"""Stage and prove one exact Kotlin enum-property compile-time guard."""

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
    candidates = [Path(__file__).with_name("kotlin_accepted_evidence.py")]
    candidates.extend(
        parent / "_kotlin-semantic" / "kotlin_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied Kotlin accepted-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("kotlin_guard_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Kotlin accepted-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()
KOTLIN_VERSION = "2.4.10"
COMPILER_SHA256 = "db12b1af0db0e10eeedfc15d5dac0316604e5c556321f60e3bcd73075a66f0a3"
STDLIB_SHA256 = "4ec0293bc3751423b203f1d8493251c57c42e73eb6377a6b8560d0974ff0a6df"


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


def _toolchain(kotlinc: Path, java: Path, root: Path) -> tuple[Path, Path, Path, dict[str, Any]]:
    try:
        compiler = kotlinc.resolve(strict=True)
        runtime = java.resolve(strict=True)
    except OSError as exc:
        raise EVIDENCE.EvidenceError("partial", "toolchain_unavailable", str(exc)) from exc
    version = _run([str(compiler), "-version"], root)
    java_version = _run([str(runtime), "-version"], root)
    if version["returncode"] or not re.search(
        rf"kotlinc-jvm {re.escape(KOTLIN_VERSION)}(?:\s|$)",
        version["stdout"] + version["stderr"],
    ):
        raise EVIDENCE.EvidenceError("partial", "compiler_version_mismatch", "Kotlin 2.4.10 is required")
    if java_version["returncode"] or not re.search(
        r'version "17\.', java_version["stdout"] + java_version["stderr"]
    ):
        raise EVIDENCE.EvidenceError("partial", "java_version_mismatch", "JDK 17 is required")
    library = compiler.parent.parent / "libexec" / "lib"
    compiler_jar = library / "kotlin-compiler.jar"
    stdlib = library / "kotlin-stdlib.jar"
    if not compiler_jar.is_file() or EVIDENCE.file_hash(compiler_jar) != COMPILER_SHA256:
        raise EVIDENCE.EvidenceError("partial", "compiler_hash_mismatch", "pinned compiler jar is required")
    if not stdlib.is_file() or EVIDENCE.file_hash(stdlib) != STDLIB_SHA256:
        raise EVIDENCE.EvidenceError("partial", "stdlib_hash_mismatch", "pinned stdlib jar is required")
    return compiler, runtime, stdlib, {"kotlinc_version": version, "java_version": java_version}


def _manifest(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    path = EVIDENCE.safe_project_path(root, "kotlin-semantic-project.json", "Kotlin manifest")
    payload = EVIDENCE.read_json(path, "Kotlin manifest")
    expected = {"schema_version", "sources", "tests", "test_main", "test_output", "smoke_main", "smoke_output"}
    if not isinstance(payload, dict) or set(payload) != expected or payload.get("schema_version") != 1:
        raise EVIDENCE.EvidenceError("failed", "manifest_invalid", "exact semantic manifest is required")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for role, key in (("source", "sources"), ("test", "tests")):
        values = payload.get(key)
        if not isinstance(values, list) or not values:
            raise EVIDENCE.EvidenceError("failed", "manifest_invalid", f"{key} must be non-empty")
        for relative in values:
            if not isinstance(relative, str) or relative in seen:
                raise EVIDENCE.EvidenceError("failed", "manifest_invalid", "manifest paths must be unique strings")
            seen.add(relative)
            source = EVIDENCE.safe_project_path(root, relative, "manifest Kotlin input")
            if source.suffix != ".kt" or not source.is_file() or source.is_symlink():
                raise EVIDENCE.EvidenceError("failed", "manifest_invalid", f"invalid Kotlin input: {relative}")
            rows.append({"path": relative, "role": role, "sha256": EVIDENCE.file_hash(source)})
    if not all(isinstance(payload.get(key), str) for key in expected - {"schema_version", "sources", "tests"}):
        raise EVIDENCE.EvidenceError("failed", "manifest_invalid", "manifest main/output fields must be strings")
    return payload, rows


def _native(
    root: Path,
    manifest: dict[str, Any],
    compiler: Path,
    runtime: Path,
    stdlib: Path,
    build: Path,
) -> dict[str, Any]:
    sources = [str(root / relative) for relative in manifest["sources"]]
    tests = [str(root / relative) for relative in manifest["tests"]]
    app = build / "app.jar"
    test_jar = build / "tests.jar"
    compile_app = _run(
        [str(compiler), "-jvm-target", "17", "-Werror", "-d", str(app), *sources], root
    )
    compile_tests = _run(
        [str(compiler), "-jvm-target", "17", "-Werror", "-d", str(test_jar), *sources, *tests], root
    )
    classpath = os.pathsep.join((str(test_jar), str(stdlib)))
    smoke_classpath = os.pathsep.join((str(app), str(stdlib)))
    test = _run([str(runtime), "-cp", classpath, manifest["test_main"]], root)
    smoke = _run([str(runtime), "-cp", smoke_classpath, manifest["smoke_main"]], root)
    passed = (
        compile_app["returncode"] == 0
        and compile_tests["returncode"] == 0
        and test["returncode"] == 0
        and test["stdout"] == manifest["test_output"]
        and smoke["returncode"] == 0
        and smoke["stdout"] == manifest["smoke_output"]
    )
    return {
        "compile": compile_app,
        "compile_tests": compile_tests,
        "test": test,
        "smoke": smoke,
        "passed": passed,
    }


def _compile_guard(
    root: Path,
    manifest: dict[str, Any],
    compiler: Path,
    guard: Path,
    output: Path,
) -> dict[str, Any]:
    sources = [str(root / relative) for relative in manifest["sources"]]
    return _run(
        [str(compiler), "-jvm-target", "17", "-Werror", "-d", str(output), *sources, str(guard)],
        root,
    )


def _proposal(root: Path, supplied: Path) -> tuple[Path, dict[str, Any]]:
    path = EVIDENCE.safe_project_path(root, supplied, "Kotlin enum proposal")
    payload = EVIDENCE.read_json(path, "Kotlin enum proposal")
    if (
        payload.get("schema_version") != "kotlin-enum-proposal-v1"
        or payload.get("language") != "kotlin"
        or payload.get("status") != "review_required"
        or payload.get("outcome") != "proposal_ready"
        or payload.get("read_only") is not True
        or payload.get("source_mutations") != 0
        or payload.get("human_gates") != EVIDENCE.STATE_GATES
    ):
        raise EVIDENCE.EvidenceError("partial", "proposal_invalid", "ready exact Kotlin enum proposal is required")
    return path, payload


def _acceptance(
    root: Path,
    supplied: Path,
    proposal_path: Path,
    proposal: dict[str, Any],
    rows: list[dict[str, str]],
) -> tuple[Path, dict[str, Any]]:
    path = EVIDENCE.safe_project_path(root, supplied, "accepted Kotlin migration")
    payload = EVIDENCE.read_json(path, "accepted Kotlin migration")
    if (
        payload.get("schema_version") != "kotlin-enum-migration-acceptance-v1"
        or payload.get("language") != "kotlin"
        or payload.get("status") != "accepted"
        or payload.get("decision") != "approve-exact-type-guard"
        or payload.get("targets_sha256") != EVIDENCE.file_hash(proposal_path)
        or payload.get("authority") != proposal.get("target", {}).get("authority")
        or payload.get("enum") != proposal.get("proposed_enum")
        or payload.get("boundary_verdicts") != EVIDENCE.STATE_GATES
        or payload.get("migrated_source_inventory") != rows
        or not isinstance(payload.get("reviewer"), str)
        or not payload["reviewer"].strip()
        or not isinstance(payload.get("notes"), str)
        or not payload["notes"].strip()
        or not EVIDENCE.valid_hashed_object(payload, "acceptance_sha256")
    ):
        raise EVIDENCE.EvidenceError("partial", "migration_acceptance_invalid", "fresh exact migration acceptance is required")
    edits = payload.get("reversion_edits")
    if not isinstance(edits, list) or not edits:
        raise EVIDENCE.EvidenceError("partial", "reversion_invalid", "accepted reversion edits are required")
    for edit in edits:
        if (
            not isinstance(edit, dict)
            or set(edit) != {"path", "migrated", "reverted"}
            or not all(isinstance(edit.get(key), str) and edit[key] for key in edit)
            or edit["migrated"] == edit["reverted"]
        ):
            raise EVIDENCE.EvidenceError("failed", "reversion_invalid", "accepted reversion edit is malformed")
        EVIDENCE.safe_project_path(root, edit["path"], "reversion path")
    return path, payload


def _guard_text(proposal: dict[str, Any]) -> str:
    authority = proposal["target"]["authority"]
    enum = proposal["proposed_enum"]
    return f"""package engineering.skills.kotlin.guard

private fun exactAcceptedState(value: {authority['owner_fq_name']}): {enum['fq_name']} =
    value.{authority['property']}
"""


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
    parser.add_argument("--kotlinc", type=Path, default=Path("/opt/homebrew/bin/kotlinc"))
    parser.add_argument("--java", type=Path, default=Path("/usr/bin/java"))
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, "prevent-regression")
        manifest, rows = _manifest(root)
        proposal_path, proposal = _proposal(root, args.targets)
        acceptance_path, acceptance = _acceptance(
            root, args.accepted_migration, proposal_path, proposal, rows
        )
        compiler, runtime, stdlib, tools = _toolchain(args.kotlinc, args.java, root)
        guard_text = _guard_text(proposal)
        with tempfile.TemporaryDirectory(prefix="kotlin-state-guard-") as raw:
            temporary = Path(raw)
            current_build = temporary / "current-build"
            current_build.mkdir()
            current_native = _native(
                root, manifest, compiler, runtime, stdlib, current_build
            )
            guard = temporary / "ExactStateGuard.kt"
            guard.write_text(guard_text, encoding="utf-8")
            current_guard = _compile_guard(
                root, manifest, compiler, guard, temporary / "current-guard.jar"
            )
            reverted = temporary / "reverted"
            shutil.copytree(
                root,
                reverted,
                ignore=shutil.ignore_patterns(".git", ".native-build", "reports"),
            )
            _apply_reversion(reverted, acceptance["reversion_edits"])
            reverted_manifest, _reverted_rows = _manifest(reverted)
            reverted_build = temporary / "reverted-build"
            reverted_build.mkdir()
            reverted_native = _native(
                reverted,
                reverted_manifest,
                compiler,
                runtime,
                stdlib,
                reverted_build,
            )
            reverted_guard = _compile_guard(
                reverted,
                reverted_manifest,
                compiler,
                guard,
                temporary / "reverted-guard.jar",
            )
        if not current_native["passed"] or current_guard["returncode"] != 0:
            raise EVIDENCE.EvidenceError(
                "failed", "migrated_proof_failed", "accepted migrated tree or exact guard does not compile/test/smoke"
            )
        if not reverted_native["passed"] or reverted_guard["returncode"] == 0:
            raise EVIDENCE.EvidenceError(
                "failed", "regression_proof_failed", "String reversion must build without the guard and fail with it"
            )
        _manifest_after, after_rows = _manifest(root)
        if after_rows != rows:
            raise EVIDENCE.EvidenceError("failed", "source_mutated", "guard staging changed host Kotlin sources")
        evidence = {
            "schema_version": "kotlin-exact-state-guard-v1",
            "language": "kotlin",
            "status": "verified",
            "outcome": "guard_staged",
            "staged_only": True,
            "installed": False,
            "source_mutations": 0,
            "authority": proposal["target"]["authority"],
            "enum": proposal["proposed_enum"],
            "guard_sha256": hashlib.sha256(guard_text.encode()).hexdigest(),
            "targets_sha256": EVIDENCE.file_hash(proposal_path),
            "acceptance_sha256": EVIDENCE.file_hash(acceptance_path),
            "migrated_source_inventory": rows,
            "human_authority": acceptance,
            "verification": {
                "toolchain": tools,
                "migrated_native": current_native,
                "migrated_guard": current_guard,
                "reverted_native_without_guard": reverted_native,
                "reverted_guard": reverted_guard,
                "buildable_reversion": True,
                "regression_rejected": True,
            },
            "limits": [
                "exact accepted property type only",
                "wire values, enum members, reflection, delegated properties, generated/KAPT/KSP sources, Gradle variants, Java/framework/external callers, JVM ABI, and runtime behavior remain outside this guard",
            ],
        }
        proposal_text = (
            "# Staged Kotlin exact-state guard\n\n"
            "The guard is verified but not installed. It accepts the human-reviewed migrated tree, "
            "while the accepted buildable String reversion passes native test/smoke without the guard "
            "and fails compilation with it. Copy/install only after separate human approval.\n"
        )
        EVIDENCE.replace_bundle(
            output,
            {"ExactStateGuard.kt": guard_text, "evidence.json": evidence, "proposal.md": proposal_text},
        )
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "prevent-regression")
            payload, report = EVIDENCE.refusal("prevent-regression", exc)
            EVIDENCE.replace_bundle(output, {"evidence.json": payload, "proposal.md": report})
        except EVIDENCE.EvidenceError:
            pass
        print(f"stage_kotlin_state_guard.py: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
