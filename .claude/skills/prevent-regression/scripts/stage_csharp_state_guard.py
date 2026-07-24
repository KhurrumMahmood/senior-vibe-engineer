#!/usr/bin/env python3
"""Stage and prove one exact C# enum-property compile-time guard."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


def _helper() -> Any:
    sys.dont_write_bytecode = True
    candidates = [Path(__file__).with_name("csharp_accepted_evidence.py")]
    candidates.extend(
        parent / "_csharp-semantic" / "csharp_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied C# accepted-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("csharp_guard_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied C# accepted-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _targets(root: Path, supplied: Path) -> tuple[Path, dict[str, Any]]:
    path = EVIDENCE.safe_project_path(root, supplied, "C# enum proposal")
    payload = EVIDENCE.read_json(path, "C# enum proposal")
    human = payload.get("human_authority")
    upstream = payload.get("upstream")
    if (
        payload.get("schema_version") != "csharp-enum-proposal-v1"
        or payload.get("language") != "csharp"
        or payload.get("status") != "review_required"
        or payload.get("outcome") != "proposal_ready"
        or payload.get("read_only") is not True
        or payload.get("source_mutations") != 0
        or payload.get("boundary_verdicts") != EVIDENCE.STATE_GATES
        or not EVIDENCE.valid_hashed_object(payload, "artifact_sha256")
        or not isinstance(human, dict)
        or human.get("schema_version") != "csharp-state-acceptance-v1"
        or human.get("status") != "accepted"
        or human.get("decision") != "accept-enum"
        or human.get("selection_symbol_id")
        != payload.get("target", {}).get("authority", {}).get("symbol_id")
        or human.get("enum") != payload.get("proposed_enum")
        or human.get("boundary_verdicts") != EVIDENCE.STATE_GATES
        or not isinstance(human.get("reviewer"), str)
        or not human["reviewer"].strip()
        or not isinstance(human.get("notes"), str)
        or not human["notes"].strip()
        or not EVIDENCE.valid_hashed_object(human, "acceptance_sha256")
        or not isinstance(upstream, dict)
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "proposal_invalid", "one content-addressed accepted C# enum proposal is required"
        )
    acceptance = EVIDENCE.safe_project_path(
        root, upstream.get("acceptance_path", ""), "upstream C# state acceptance"
    )
    if EVIDENCE.file_hash(acceptance) != upstream.get("acceptance_sha256"):
        raise EVIDENCE.EvidenceError(
            "partial", "proposal_invalid", "upstream C# state acceptance changed"
        )
    return path, payload


def _acceptance(
    root: Path,
    supplied: Path,
    proposal_path: Path,
    proposal: dict[str, Any],
    facts_path: Path,
    facts: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    path = EVIDENCE.safe_project_path(root, supplied, "accepted C# enum migration")
    payload = EVIDENCE.read_json(path, "accepted C# enum migration")
    authority = proposal.get("target", {}).get("authority")
    if (
        payload.get("schema_version") != "csharp-enum-migration-acceptance-v1"
        or payload.get("language") != "csharp"
        or payload.get("status") != "accepted"
        or payload.get("decision") != "approve-exact-property-type-guard"
        or payload.get("targets") != proposal_path.relative_to(root).as_posix()
        or payload.get("targets_sha256") != EVIDENCE.file_hash(proposal_path)
        or payload.get("migrated_facts") != facts_path.relative_to(root).as_posix()
        or payload.get("migrated_facts_sha256") != EVIDENCE.file_hash(facts_path)
        or payload.get("migrated_fact_pack_sha256") != facts.get("fact_pack_sha256")
        or payload.get("migrated_source_manifest_sha256")
        != facts.get("source_manifest_sha256")
        or payload.get("migrated_source_inventory") != facts.get("source_inventory")
        or payload.get("authority") != authority
        or payload.get("enum") != proposal.get("proposed_enum")
        or payload.get("migrated_signature")
        != "CSharpSemantic.JobStatus CSharpSemantic.Job.Status"
        or payload.get("boundary_verdicts") != EVIDENCE.STATE_GATES
        or not isinstance(payload.get("reviewer"), str)
        or not payload["reviewer"].strip()
        or not isinstance(payload.get("notes"), str)
        or not payload["notes"].strip()
        or not EVIDENCE.valid_hashed_object(payload, "acceptance_sha256")
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "migration_acceptance_invalid", "fresh exact migrated-tree acceptance is required"
        )
    edits = payload.get("reversion_edits")
    manifest_paths = set(facts.get("manifest", {}).get("sources", [])) | set(
        facts.get("manifest", {}).get("tests", [])
    )
    if not isinstance(edits, list) or not edits:
        raise EVIDENCE.EvidenceError(
            "partial", "reversion_invalid", "an exact accepted String-reversion tree is required"
        )
    for edit in edits:
        if (
            not isinstance(edit, dict)
            or set(edit) != {"path", "migrated", "reverted"}
            or edit.get("path") not in manifest_paths
            or not isinstance(edit.get("migrated"), str)
            or not isinstance(edit.get("reverted"), str)
            or edit["migrated"] == edit["reverted"]
        ):
            raise EVIDENCE.EvidenceError("failed", "reversion_invalid", "accepted reversion edit is malformed")
        source = EVIDENCE.safe_project_path(root, edit["path"], "accepted reversion source")
        if source.read_text(encoding="utf-8") != edit["migrated"]:
            raise EVIDENCE.EvidenceError(
                "partial", "reversion_stale", f"accepted migrated source changed: {edit['path']}"
            )
    return path, payload


def _migrated_authority(facts: dict[str, Any], proposal: dict[str, Any]) -> None:
    symbol = proposal["target"]["authority"]["symbol_id"]
    declarations = [
        row
        for row in facts.get("declarations", [])
        if row.get("role") == "source"
        and row.get("kind") == "property"
        and row.get("symbol_id") == symbol
    ]
    if (
        len(declarations) != 1
        or declarations[0].get("type") != "CSharpSemantic.JobStatus"
        or declarations[0].get("signature")
        != "CSharpSemantic.JobStatus CSharpSemantic.Job.Status"
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "migrated_authority_invalid", "accepted property is not exactly JobStatus"
        )


def _guard(proposal: dict[str, Any]) -> str:
    enum = proposal["proposed_enum"]
    return f"""using {enum['namespace']};

namespace EngineeringSkills.CSharpStateGuard;

internal static class ExactAcceptedStateGuard
{{
    private static {enum['type_name']} Exact({enum['type_name']} value) => value;

    internal static {enum['type_name']} Verify(Job job) => Exact(job.Status);
}}
"""


def _toolchain(facts: dict[str, Any]) -> tuple[str, str, list[str]]:
    tools = facts["tools"]
    dotnet = tools["dotnet"]["path"]
    csc = tools["csc"]["path"]
    references = [str(path) for path in sorted(Path(tools["reference_pack"]["path"]).glob("*.dll"))]
    return dotnet, csc, references


def _compile(
    root: Path,
    facts: dict[str, Any],
    sources: list[Path],
    output: Path,
    main: str,
) -> dict[str, Any]:
    dotnet, csc, references = _toolchain(facts)
    return EVIDENCE.run(
        [
            dotnet,
            csc,
            "-nologo",
            "-noconfig",
            "-nostdlib+",
            "-deterministic+",
            "-debug-",
            "-nullable:enable",
            "-warnaserror+",
            "-langversion:14",
            "-target:exe",
            f"-main:{main}",
            f"-out:{output}",
            *(f"-r:{path}" for path in references),
            *(str(path) for path in sources),
        ],
        root,
    )


def _runtime_config(output: Path) -> None:
    payload = {
        "runtimeOptions": {
            "tfm": "net10.0",
            "framework": {"name": "Microsoft.NETCore.App", "version": "10.0.10"},
            "rollForward": "Disable",
        }
    }
    output.with_suffix(".runtimeconfig.json").write_text(
        json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
    )


def _native(root: Path, facts: dict[str, Any], build: Path) -> dict[str, Any]:
    manifest = facts["manifest"]
    sources = [root / relative for relative in manifest["sources"]]
    tests = [root / relative for relative in manifest["tests"]]
    app, test = build / "app.dll", build / "tests.dll"
    compile_app = _compile(root, facts, sources, app, manifest["smoke_main"])
    compile_tests = _compile(root, facts, [*sources, *tests], test, manifest["test_main"])
    _runtime_config(app)
    _runtime_config(test)
    dotnet = facts["tools"]["dotnet"]["path"]
    test_run = EVIDENCE.run([dotnet, str(test)], root)
    smoke = EVIDENCE.run([dotnet, str(app)], root)
    passed = (
        compile_app["returncode"] == 0
        and compile_tests["returncode"] == 0
        and test_run["returncode"] == 0
        and test_run["stdout"] == manifest["test_output"]
        and smoke["returncode"] == 0
        and smoke["stdout"] == manifest["smoke_output"]
    )
    return {
        "compile": compile_app,
        "compile_tests": compile_tests,
        "test": test_run,
        "smoke": smoke,
        "passed": passed,
    }


def _compile_guard(
    root: Path, facts: dict[str, Any], guard: Path, output: Path
) -> dict[str, Any]:
    sources = [root / relative for relative in facts["manifest"]["sources"]]
    return _compile(
        root,
        facts,
        [*sources, guard],
        output,
        facts["manifest"]["smoke_main"],
    )


def _apply_reversion(root: Path, edits: list[dict[str, str]]) -> None:
    for edit in edits:
        path = EVIDENCE.safe_project_path(root, edit["path"], "String-reversion source")
        if path.read_text(encoding="utf-8") != edit["migrated"]:
            raise EVIDENCE.EvidenceError(
                "partial", "reversion_stale", f"accepted migrated source changed: {edit['path']}"
            )
        path.write_text(edit["reverted"], encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--accepted-migration", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, "prevent-regression")
        facts_path, facts = EVIDENCE.validate_fact_pack(root, args.facts)
        targets_path, targets = _targets(root, args.targets)
        acceptance_path, acceptance = _acceptance(
            root,
            args.accepted_migration,
            targets_path,
            targets,
            facts_path,
            facts,
        )
        _migrated_authority(facts, targets)
        guard_text = _guard(targets)
        before = {
            row["path"]: EVIDENCE.file_hash(root / row["path"])
            for row in facts["source_inventory"]
        }
        with tempfile.TemporaryDirectory(prefix="csharp-state-guard-") as raw:
            temporary = Path(raw)
            current_build = temporary / "current-build"
            current_build.mkdir()
            current_native = _native(root, facts, current_build)
            guard_path = temporary / "ExactAcceptedStateGuard.cs"
            guard_path.write_text(guard_text, encoding="utf-8")
            current_guard = _compile_guard(
                root, facts, guard_path, temporary / "current-guard.dll"
            )
            reverted = temporary / "reverted"
            shutil.copytree(
                root,
                reverted,
                ignore=shutil.ignore_patterns(".git", ".native-build", "reports"),
            )
            _apply_reversion(reverted, acceptance["reversion_edits"])
            reverted_build = temporary / "reverted-build"
            reverted_build.mkdir()
            reverted_native = _native(reverted, facts, reverted_build)
            reverted_guard = _compile_guard(
                reverted, facts, guard_path, temporary / "reverted-guard.dll"
            )
        if not current_native["passed"] or current_guard["returncode"] != 0:
            raise EVIDENCE.EvidenceError(
                "failed", "migrated_proof_failed", "accepted migrated native tree or exact guard failed"
            )
        if not reverted_native["passed"] or reverted_guard["returncode"] == 0:
            raise EVIDENCE.EvidenceError(
                "failed",
                "regression_proof_failed",
                "accepted String reversion must pass without the guard and fail with it",
            )
        after = {
            row["path"]: EVIDENCE.file_hash(root / row["path"])
            for row in facts["source_inventory"]
        }
        if after != before:
            raise EVIDENCE.EvidenceError(
                "failed", "source_mutated", "guard staging changed host C# sources"
            )
        evidence = {
            "schema_version": "csharp-exact-state-guard-v1",
            "language": "csharp",
            "status": "verified",
            "outcome": "guard_staged",
            "staged_only": True,
            "installed": False,
            "source_mutations": 0,
            "authority": targets["target"]["authority"],
            "enum": targets["proposed_enum"],
            "guard_sha256": hashlib.sha256(guard_text.encode()).hexdigest(),
            "targets_sha256": EVIDENCE.file_hash(targets_path),
            "acceptance_sha256": EVIDENCE.file_hash(acceptance_path),
            "migrated_fact_pack_sha256": facts["fact_pack_sha256"],
            "migrated_source_inventory": facts["source_inventory"],
            "human_authority": acceptance,
            "verification": {
                "migrated_native": current_native,
                "migrated_guard": current_guard,
                "reverted_native_without_guard": reverted_native,
                "reverted_guard": reverted_guard,
                "buildable_string_reversion": True,
                "regression_rejected": True,
            },
            "limits": [
                "one exact accepted Job.Status property type only",
                "enum member values, aliases, converters, serializers, reflection, generated/vendor inputs, framework/external callers, conditional variants, and binary compatibility remain outside this guard",
            ],
        }
        evidence["artifact_sha256"] = EVIDENCE.canonical_hash(evidence)
        report = (
            "# Staged C# exact-state guard\n\n"
            "The compile-time guard is verified but not installed. The separately accepted "
            "migrated tree passes native compile/test/smoke and the guard; the exact accepted "
            "String reversion passes the same native checks without the guard but fails compilation "
            "with it. Installation requires separate human action.\n"
        )
        EVIDENCE.replace_bundle(
            output,
            {
                "ExactAcceptedStateGuard.cs": guard_text,
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
        print(f"stage_csharp_state_guard.py: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
