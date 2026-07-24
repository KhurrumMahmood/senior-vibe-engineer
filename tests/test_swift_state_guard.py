"""Accepted Swift enum proposal and staged exact-property-type guard."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
SKILLS = ROOT / ".claude/skills"
PROVIDER = SKILLS / "_swift-semantic-readonly/swift_semantic_facts.py"
HELPER = SKILLS / "_swift-semantic-readonly/swift_accepted_evidence.py"
STATE = SKILLS / "find-implicit-state/scripts/detect_swift_state.py"
EXTRACT = SKILLS / "extract-enum/scripts/collect_swift_state.py"
GUARD = SKILLS / "prevent-regression/scripts/stage_swift_state_guard.py"
OVERLAY = ROOT / "tests/fixtures/swift-state-guard/migrated"
SWIFT = Path("/usr/bin/swift")
SWIFTC = Path("/usr/bin/swiftc")
SWIFT_FORMAT = Path("/Library/Developer/CommandLineTools/usr/bin/swift-format")

_A3_SPEC = importlib.util.spec_from_file_location(
    "swift_a3_state_guard_fixture", ROOT / "tests/test_swift_semantic_a3.py"
)
assert _A3_SPEC and _A3_SPEC.loader
A3 = importlib.util.module_from_spec(_A3_SPEC)
sys.modules[_A3_SPEC.name] = A3
_A3_SPEC.loader.exec_module(A3)

_HELPER_SPEC = importlib.util.spec_from_file_location("swift_a4_evidence_test", HELPER)
assert _HELPER_SPEC and _HELPER_SPEC.loader
EVIDENCE = importlib.util.module_from_spec(_HELPER_SPEC)
sys.modules[_HELPER_SPEC.name] = EVIDENCE
_HELPER_SPEC.loader.exec_module(EVIDENCE)

pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (PYTHON, SWIFT, SWIFTC, SWIFT_FORMAT)),
    reason="the product Python and pinned CLT Swift toolchain are required",
)


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 360,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any], hash_field: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hash_field:
        payload = dict(payload)
        payload[hash_field] = EVIDENCE.canonical_hash(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _install(tmp_path: Path) -> dict[str, Path]:
    selected = tmp_path / "outside-checkout/.agents/skills"
    common = selected / "_swift-semantic-readonly"
    common.mkdir(parents=True)
    shutil.copy2(PROVIDER, common / PROVIDER.name)
    shutil.copy2(HELPER, common / HELPER.name)
    copied: dict[str, Path] = {"provider": common / PROVIDER.name}
    for name, source in (("extract", EXTRACT), ("guard", GUARD)):
        destination = selected / source.parents[1].name / "scripts" / source.name
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)
        copied[name] = destination
    return copied


def _accepted_state(host: Path, tmp_path: Path) -> tuple[Path, Path, Path]:
    facts_payload, facts, _ = A3._collect(
        PROVIDER, host, "SwiftA3Core", A3.UNION_QUERIES, "state-guard"
    )
    state_dir = host / "reports/implicit-state/swift"
    A3._consumer(STATE, host, facts, "--output-dir", state_dir)
    candidate = _jsonl(state_dir / "candidates.jsonl")[0]
    reviews = tmp_path / "state-reviews"
    _write(
        reviews / f"{candidate['candidate_id']}.json",
        {
            "schema_version": "swift-implicit-state-review-v1",
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate["candidate_sha256"],
            "bucket": "extract_enum_candidate",
            "human_verdict": "accepted",
            "confidence": "high",
            "notes": "Accepted exact internal String state operations.",
        },
    )
    A3._consumer(
        STATE,
        host,
        facts,
        "--output-dir",
        state_dir,
        "--reviews-dir",
        reviews,
    )
    findings = state_dir / "findings.json"
    finding = _json(findings)["findings"][0]
    enum_source = host / "Sources/SwiftA3Core/State.swift"
    acceptance = _write(
        host / "reports/implicit-state/swift/accepted-enum.json",
        {
            "schema_version": "swift-state-acceptance-v1",
            "language": "swift",
            "status": "accepted",
            "producer": "find-implicit-state",
            "decision": "accept-enum",
            "artifact": findings.relative_to(host).as_posix(),
            "artifact_sha256": _hash(findings),
            "fact_pack_sha256": facts_payload["fact_pack_sha256"],
            "source_manifest_sha256": facts_payload["source_manifest_sha256"],
            "candidate_sha256": finding["candidate_sha256"],
            "selection_semantic_id": finding["semantic_id"],
            "enum": {
                "action": "reuse_existing",
                "module": "SwiftA3Core",
                "type_name": "JobState",
                "raw_type": "String",
                "source": enum_source.relative_to(host).as_posix(),
                "source_sha256": _hash(enum_source),
                "cases": [
                    {"name": "queued", "raw_value": "queued"},
                    {"name": "running", "raw_value": "running"},
                    {"name": "done", "raw_value": "done"},
                ],
            },
            "boundary_verdicts": EVIDENCE.STATE_GATES,
            "native": {
                "configuration": "debug",
                "check_product": "swift-a3-check",
                "expected_check": "swift-a3-checks-ok",
                "smoke_product": "swift-a3-smoke",
                "expected_smoke": "swift-a3:42",
            },
            "reviewer": "fixture-reviewer",
            "notes": "Accepted closed domain, existing enum, raw values, and bounded Swift surfaces.",
        },
        "acceptance_sha256",
    )
    return facts, findings, acceptance


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract(
    host: Path,
    script: Path,
    facts: Path,
    findings: Path,
    acceptance: Path,
    *,
    expected: int = 0,
) -> Path:
    output = host / "reports/extract-enum/swift/job-state"
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--target-name",
        "SwiftA3Core",
        "--facts",
        facts,
        "--findings",
        findings,
        "--acceptance",
        acceptance,
        "--output-dir",
        output,
        cwd=host,
        expected=expected,
    )
    return output


def _migrate(host: Path) -> list[dict[str, str]]:
    edits: list[dict[str, str]] = []
    for migrated in sorted(OVERLAY.rglob("*.swift")):
        relative = migrated.relative_to(OVERLAY)
        destination = host / relative
        original = destination.read_text(encoding="utf-8")
        replacement = migrated.read_text(encoding="utf-8")
        destination.write_text(replacement, encoding="utf-8")
        if relative.as_posix() == "Sources/SwiftA3Core/State.swift":
            edits.append(
                {"path": relative.as_posix(), "migrated": replacement, "reverted": original}
            )
    return edits


def _migration_acceptance(host: Path, targets: Path, edits: list[dict[str, str]]) -> Path:
    proposal = _json(targets)
    payload = {
        "schema_version": "swift-enum-migration-acceptance-v1",
        "language": "swift",
        "status": "accepted",
        "decision": "approve-exact-property-type-guard",
        "targets_sha256": _hash(targets),
        "authority": proposal["target"]["authority"],
        "enum": proposal["proposed_enum"],
        "boundary_verdicts": EVIDENCE.STATE_GATES,
        "package_sha256": proposal["package_sha256"],
        "migrated_source_hashes": EVIDENCE.source_hashes(host),
        "reversion_edits": edits,
        "reviewer": "fixture-migration-reviewer",
        "notes": "Accepted migrated tree, exact String reversion, and staged-only guard.",
    }
    return _write(
        host / "reports/extract-enum/swift/job-state/accepted-migration.json",
        payload,
        "acceptance_sha256",
    )


def _stage(
    host: Path,
    script: Path,
    targets: Path,
    acceptance: Path,
    *,
    expected: int = 0,
    swift: Path = SWIFT,
) -> Path:
    output = host / "reports/prevent-regression/swift/job-state"
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--targets",
        targets,
        "--accepted-migration",
        acceptance,
        "--output-dir",
        output,
        "--swift",
        swift,
        "--swiftc",
        SWIFTC,
        "--swift-format",
        SWIFT_FORMAT,
        cwd=host,
        expected=expected,
    )
    return output


def test_swift_accepted_proposal_guard_copied_and_lifecycle(tmp_path: Path) -> None:
    host = A3._copy_host(tmp_path)
    copied = _install(tmp_path)
    facts, findings, state_acceptance = _accepted_state(host, tmp_path)
    original = A3._source_fingerprints(host)

    proposal_dir = _extract(host, copied["extract"], facts, findings, state_acceptance)
    targets = proposal_dir / "targets.json"
    proposal = _json(targets)
    assert set(path.name for path in proposal_dir.iterdir()) == {"proposal.md", "targets.json"}
    assert proposal["outcome"] == "proposal_ready"
    assert proposal["source_mutations"] == 0
    assert proposal["target"]["authority"]["semantic_id"]
    assert proposal["proposed_enum"]["action"] == "reuse_existing"
    assert proposal["proposed_enum"]["type_name"] == "JobState"
    assert [row["raw_value"] for row in proposal["proposed_enum"]["cases"]] == [
        "queued",
        "running",
        "done",
    ]
    assert A3._source_fingerprints(host) == original

    accepted = _json(state_acceptance)
    invalid = {**accepted, "artifact_sha256": "0" * 64}
    invalid.pop("acceptance_sha256")
    _write(state_acceptance, invalid, "acceptance_sha256")
    _extract(
        host,
        copied["extract"],
        facts,
        findings,
        state_acceptance,
        expected=2,
    )
    assert _json(targets)["failure_kind"] == "acceptance_invalid"
    _write(state_acceptance, accepted)
    _extract(host, copied["extract"], facts, findings, state_acceptance)
    assert _json(targets)["outcome"] == "proposal_ready"

    edits = _migrate(host)
    migrated = A3._source_fingerprints(host)
    migration_acceptance = _migration_acceptance(host, targets, edits)
    guard_dir = _stage(host, copied["guard"], targets, migration_acceptance)
    assert set(path.name for path in guard_dir.iterdir()) == {
        "ExactAcceptedStateGuard.swift",
        "evidence.json",
        "proposal.md",
    }
    guard = _json(guard_dir / "evidence.json")
    assert guard["outcome"] == "guard_staged"
    assert guard["installed"] is False
    assert guard["verification"]["migrated_native"]["passed"] is True
    assert guard["verification"]["migrated_guard"]["returncode"] == 0
    assert guard["verification"]["reverted_native_without_guard"]["passed"] is True
    assert guard["verification"]["reverted_guard"]["returncode"] != 0
    diagnostics = (
        guard["verification"]["reverted_guard"]["stdout"]
        + guard["verification"]["reverted_guard"]["stderr"]
    )
    assert "String" in diagnostics and "JobState" in diagnostics
    assert A3._source_fingerprints(host) == migrated

    migration = _json(migration_acceptance)
    stale = {**migration, "targets_sha256": "0" * 64}
    stale.pop("acceptance_sha256")
    _write(migration_acceptance, stale, "acceptance_sha256")
    _stage(host, copied["guard"], targets, migration_acceptance, expected=2)
    assert _json(guard_dir / "evidence.json")["failure_kind"] == ("migration_acceptance_invalid")
    assert not (guard_dir / "ExactAcceptedStateGuard.swift").exists()
    _write(migration_acceptance, migration)
    _stage(
        host,
        copied["guard"],
        targets,
        migration_acceptance,
        expected=2,
        swift=host / "missing-swift",
    )
    assert _json(guard_dir / "evidence.json")["failure_kind"] == "toolchain_unavailable"
    _stage(host, copied["guard"], targets, migration_acceptance)
    assert (guard_dir / "ExactAcceptedStateGuard.swift").is_file()
    assert A3._source_fingerprints(host) == migrated
    for path in copied.values():
        assert str(ROOT) not in path.read_text(encoding="utf-8")


def test_swift_proposal_refuses_stale_a3_source_and_recovers(tmp_path: Path) -> None:
    host = A3._copy_host(tmp_path)
    copied = _install(tmp_path)
    facts, findings, acceptance = _accepted_state(host, tmp_path)
    output = _extract(host, copied["extract"], facts, findings, acceptance)
    state = host / "Sources/SwiftA3Core/State.swift"
    original = state.read_text(encoding="utf-8")
    state.write_text(original + "\n", encoding="utf-8")
    _extract(host, copied["extract"], facts, findings, acceptance, expected=2)
    assert _json(output / "targets.json")["failure_kind"] == "fact_pack_stale"
    state.write_text(original, encoding="utf-8")
    _extract(host, copied["extract"], facts, findings, acceptance)
    assert _json(output / "targets.json")["outcome"] == "proposal_ready"
