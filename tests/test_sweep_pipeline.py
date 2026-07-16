from __future__ import annotations

import copy
import hashlib
import subprocess
from pathlib import Path

import pytest

from sweep.manifest import FindingInput, build_manifest
from sweep.pipeline import (
    HarnessScan,
    JudgmentGateError,
    VerificationGateError,
    build_judgment,
    build_judgment_input,
    build_packet,
    import_judgment_outcomes,
    read_changed_paths,
    render_judged_digest,
    validate_judged_digest,
    verify_packet,
)
from sweep.schemas import SchemaValidationError, packet_budget_ceiling, validate_packet
from sweep.serialization import canonical_json_bytes


EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
REVISION = "a" * 40


def _provider() -> dict[str, object]:
    return {
        "schema_version": 1,
        "provider": "ruff",
        "language": "python",
        "provider_kind": "native",
        "scope": {"paths": ["src"], "case_sensitive": True, "roots": ["src"], "exclusions": []},
        "command": {
            "executable": "/tool/ruff",
            "argv": ["check", "src"],
            "timeout_seconds": 30,
            "output_format": "json",
            "output_byte_limit": 1_048_576,
        },
        "tool_version": "ruff 0.9.9",
        "exit": {"code": 0, "classification": "diagnostics"},
        "raw": {
            "stdout_sha256": EMPTY_SHA256,
            "stderr_sha256": EMPTY_SHA256,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
        },
        "status": "completed",
        "failure": None,
    }


def _finding(index: int, *, count: int = 1, message_size: int = 20) -> FindingInput:
    return FindingInput(
        provider="ruff",
        language="python",
        native_rule_id=f"R{index:03d}",
        rule_semantic_key=f"R{index:03d}:v1",
        path=f"src/file_{index:03d}.py",
        semantic_anchor=f"symbol:item_{index:03d}",
        native_severity="warning",
        severity=2,
        message="m" * message_size,
        summary=f"summary {index} " + "x" * message_size,
        metrics={"count": count},
        observation_index=0,
        line=index + 1,
    )


def _manifest(findings: list[FindingInput], *, revision: str = REVISION) -> dict[str, object]:
    return build_manifest(
        capability_registry_version=1,
        paths=["src"],
        case_sensitive=True,
        roots=["src"],
        exclusions=[],
        source={"revision": revision, "dirty": False, "dirty_state_hash": EMPTY_SHA256},
        providers=[_provider()],
        findings=findings,
    )


def _outcomes(manifest, outcomes: dict[int, str] | None = None):
    outcomes = outcomes or {}
    return [
        {
            "finding_id": row["id"],
            "outcome": outcomes.get(index, "actionable"),
            "reason": f"reason {index}",
            "evidence": f"evidence:{index}",
        }
        for index, row in enumerate(manifest["findings"])
    ]


def _judgment(manifest, outcomes: dict[int, str] | None = None):
    return build_judgment(
        manifest,
        judge_identity="fixture-judge",
        judge_version="1.0",
        outcomes=_outcomes(manifest, outcomes),
    )


def _harness_scan(manifest) -> HarnessScan:
    content = canonical_json_bytes(manifest)
    return HarnessScan(
        manifest=manifest,
        evidence={"argv": ["fixture-scan"], "exit_code": 0,
                  "stdout_sha256": hashlib.sha256(content).hexdigest(),
                  "stderr_sha256": EMPTY_SHA256,
                  "stdout_bytes": len(content), "stderr_bytes": 0},
    )


def _verification(argv=None, exit_code: int = 0, *, fault: str | None = None) -> dict:
    return {
        "argv": list(argv or ["fixture-verify"]),
        "exit_code": exit_code,
        "fault": fault,
        "stdout_sha256": EMPTY_SHA256,
        "stderr_sha256": EMPTY_SHA256,
        "stdout_bytes": 0,
        "stderr_bytes": 0,
    }


def test_im_9_judgment_input_is_deterministic_id_addressable_and_bounded() -> None:
    manifest = _manifest([_finding(index, message_size=2_000) for index in range(80)])

    first = build_judgment_input(manifest)
    second = build_judgment_input(copy.deepcopy(manifest))

    assert first == second
    assert len(canonical_json_bytes(first)) <= 65_536
    assert len(first["findings"]) == 50
    assert first["omitted"] == 30
    assert first["offset"] == 0 and first["next_offset"] == 50 and first["total"] == 80
    assert all(set(row) == {"finding_id", "provider", "rule", "path", "severity", "summary", "metrics"} for row in first["findings"])
    assert first["manifest_hash"] == manifest["hashes"]["semantic"]

    second_page = build_judgment_input(manifest, offset=first["next_offset"])
    assert len(second_page["findings"]) == 30
    assert second_page["offset"] == 50
    assert second_page["next_offset"] is None and second_page["omitted"] == 0
    assert {row["finding_id"] for row in first["findings"]}.isdisjoint(
        row["finding_id"] for row in second_page["findings"]
    )
    assert {
        row["finding_id"] for page in (first, second_page) for row in page["findings"]
    } == {row["id"] for row in manifest["findings"]}


def test_im_9_import_rejects_unknown_duplicate_and_stale_outcomes() -> None:
    manifest = _manifest([_finding(1), _finding(2)])
    valid = _outcomes(manifest)

    imported = import_judgment_outcomes(manifest, valid)
    assert [row["finding_id"] for row in imported] == sorted(row["id"] for row in manifest["findings"])
    with pytest.raises(JudgmentGateError, match="unknown finding"):
        import_judgment_outcomes(
            manifest,
            [{**valid[0], "finding_id": "f2_" + "f" * 24}],
        )
    with pytest.raises(JudgmentGateError, match="duplicate"):
        import_judgment_outcomes(manifest, [valid[0], valid[0]])

    judgment = _judgment(manifest)
    tampered = copy.deepcopy(judgment)
    tampered["outcomes"][0]["reason"] = "changed after hashing"
    with pytest.raises(JudgmentGateError, match="hash"):
        render_judged_digest(manifest, tampered, purpose="dashboard")


@pytest.mark.parametrize("bad", ["uncertain", "failed"])
def test_im_9_uncertain_failed_and_missing_judgments_block_every_ordinary_consumer(bad: str) -> None:
    manifest = _manifest([_finding(1), _finding(2)])
    incomplete = build_judgment(
        manifest,
        judge_identity="fixture-judge",
        judge_version="1.0",
        outcomes=_outcomes(manifest)[:1],
    )
    blocked = _judgment(manifest, {0: bad})

    for judgment, message in ((incomplete, "missing"), (blocked, bad)):
        with pytest.raises(JudgmentGateError, match=message):
            render_judged_digest(manifest, judgment, purpose="dashboard")
        with pytest.raises(JudgmentGateError, match=message):
            build_packet(
                manifest,
                judgment,
                finding_ids=[manifest["findings"][0]["id"]],
                scope=[manifest["findings"][0]["location"]["path"]],
                recipe="fix the finding",
                verification="python -m pytest -q",
                expected_delta={"fixed": [manifest["findings"][0]["id"]], "allowed_new": [], "metrics": []},
                token_budget=8_000,
            )


def test_im_9_judged_digest_excludes_not_actionable_and_has_content_hash() -> None:
    manifest = _manifest([_finding(1), _finding(2), _finding(3)])
    judgment = _judgment(manifest, {1: "not_actionable"})

    digest = render_judged_digest(manifest, judgment, purpose="dashboard")

    assert digest["purpose"] == "dashboard"
    assert digest["total_actionable"] == 2
    assert digest["counts"] == {"ruff": 2}
    assert digest["outcomes"] == {"actionable": 2, "not_actionable": 1}
    assert digest["finding_ids"] == sorted(
        [manifest["findings"][0]["id"], manifest["findings"][2]["id"]]
    )
    assert "findings" not in digest
    assert len(canonical_json_bytes(digest)) <= 65_536
    assert len(digest["digest_hash"]) == 64

    tampered = copy.deepcopy(digest)
    tampered["total_actionable"] = 99
    with pytest.raises(JudgmentGateError):
        validate_judged_digest(tampered)
    malformed_id = copy.deepcopy(digest)
    malformed_id["finding_ids"] = ["f2_not-actually-a-v2-id"]
    malformed_id["omitted_actionable"] = 1
    with pytest.raises(JudgmentGateError, match="v2 IDs"):
        validate_judged_digest(malformed_id)


def test_im_10_packet_is_fresh_actionable_scoped_structured_and_budgeted() -> None:
    manifest = _manifest([_finding(1), _finding(2)])
    judgment = _judgment(manifest, {1: "not_actionable"})
    identifier = manifest["findings"][0]["id"]
    path = manifest["findings"][0]["location"]["path"]
    expected = {"fixed": [identifier], "allowed_new": [], "metrics": []}

    packet = build_packet(
        manifest,
        judgment,
        finding_ids=[identifier],
        scope=[path],
        recipe="replace the unsafe construct",
        verification="python -m pytest -q tests/test_example.py",
        expected_delta=expected,
        token_budget=packet_budget_ceiling([path]),
    )

    assert validate_packet(packet) == packet
    assert packet["manifest_hash"] == manifest["hashes"]["semantic"]
    assert packet["judgment_hash"] == judgment["judgment_hash"]
    with pytest.raises(JudgmentGateError, match="not actionable"):
        build_packet(
            manifest,
            judgment,
            finding_ids=[manifest["findings"][1]["id"]],
            scope=[manifest["findings"][1]["location"]["path"]],
            recipe="wrong",
            verification="python -m pytest -q",
            expected_delta={"fixed": [], "allowed_new": [], "metrics": []},
            token_budget=8_000,
        )
    with pytest.raises(SchemaValidationError, match="scope"):
        build_packet(
            manifest,
            judgment,
            finding_ids=[identifier],
            scope=["src/other.py"],
            recipe="wrong scope",
            verification="python -m pytest -q",
            expected_delta=expected,
            token_budget=8_000,
        )


def test_im_11_harness_runs_verification_then_rescans_and_emits_bound_evidence() -> None:
    before = _manifest([_finding(1), _finding(2)])
    after = _manifest([_finding(2)])
    judgment = _judgment(before, {1: "not_actionable"})
    identifier = before["findings"][0]["id"]
    path = before["findings"][0]["location"]["path"]
    packet = build_packet(
        before,
        judgment,
        finding_ids=[identifier],
        scope=[path],
        recipe="fix it",
        verification="python -m pytest -q tests/test_example.py",
        expected_delta={"fixed": [identifier], "allowed_new": [], "metrics": []},
        token_budget=8_000,
    )
    events: list[str] = []

    def run_verification(argv, root):
        events.append(f"verify:{argv[0]}:{root.name}")
        return {**_verification(), "argv": list(argv)}

    def rescan():
        events.append("rescan")
        return _harness_scan(after)

    evidence = verify_packet(
        packet,
        before,
        judgment,
        root=Path("/tmp/fixture-root"),
        changed_path_reader=lambda _: [path],
        verification_runner=run_verification,
        scanner=rescan,
    )

    assert events == ["verify:python:fixture-root", "rescan"]
    assert evidence["verdict"] == "verified"
    assert evidence["before_manifest_hash"] == before["hashes"]["semantic"]
    assert evidence["after_manifest_hash"] == after["hashes"]["semantic"]
    assert evidence["diff"]["fixed"] == [identifier]
    assert evidence["changed_paths"] == [path]
    assert evidence["evidence_hash"]


def test_im_11_harness_rejects_self_attestation_scope_staleness_and_delta_bypass() -> None:
    before = _manifest([_finding(1)])
    judgment = _judgment(before)
    identifier = before["findings"][0]["id"]
    path = before["findings"][0]["location"]["path"]
    packet = build_packet(
        before,
        judgment,
        finding_ids=[identifier],
        scope=[path],
        recipe="fix it",
        verification="python -m pytest -q",
        expected_delta={"fixed": [identifier], "allowed_new": [], "metrics": []},
        token_budget=8_000,
    )

    with pytest.raises(SchemaValidationError, match="unknown fields"):
        verify_packet(
            {**packet, "executor_report": "PASS"},
            before,
            judgment,
            root=Path("/tmp/root"),
            changed_path_reader=lambda _: [path],
            verification_runner=lambda argv, _: _verification(argv),
            scanner=lambda: _harness_scan(_manifest([])),
        )
    with pytest.raises(VerificationGateError, match="outside packet scope"):
        verify_packet(
            packet,
            before,
            judgment,
            root=Path("/tmp/root"),
            changed_path_reader=lambda _: ["src/other.py"],
            verification_runner=lambda argv, _: _verification(argv),
            scanner=lambda: _harness_scan(_manifest([])),
        )

    stale = copy.deepcopy(judgment)
    stale["manifest_hash"] = "b" * 64
    with pytest.raises(JudgmentGateError):
        verify_packet(
            packet,
            before,
            stale,
            root=Path("/tmp/root"),
            changed_path_reader=lambda _: [path],
            verification_runner=lambda argv, _: _verification(argv),
            scanner=lambda: _harness_scan(_manifest([])),
        )

    called = False

    def forbidden_scan():
        nonlocal called
        called = True
        return _harness_scan(_manifest([]))

    with pytest.raises(VerificationGateError, match="verification command failed"):
        verify_packet(
            packet,
            before,
            judgment,
            root=Path("/tmp/root"),
            changed_path_reader=lambda _: [path],
            verification_runner=lambda argv, _: _verification(argv, 1),
            scanner=forbidden_scan,
        )
    assert called is False

    with pytest.raises(VerificationGateError, match="expected fixed"):
        verify_packet(
            packet,
            before,
            judgment,
            root=Path("/tmp/root"),
            changed_path_reader=lambda _: [path],
            verification_runner=lambda argv, _: _verification(argv),
            scanner=lambda: _harness_scan(before),
        )


def test_im_11_new_findings_are_rejected_unless_structurally_allowed() -> None:
    before = _manifest([_finding(1)])
    after = _manifest([_finding(2)])
    judgment = _judgment(before)
    fixed_id = before["findings"][0]["id"]
    new_id = after["findings"][0]["id"]
    path = before["findings"][0]["location"]["path"]

    def packet(allowed_new):
        return build_packet(
            before,
            judgment,
            finding_ids=[fixed_id],
            scope=[path, after["findings"][0]["location"]["path"]],
            recipe="replace finding",
            verification="python -m pytest -q",
            expected_delta={"fixed": [fixed_id], "allowed_new": allowed_new, "metrics": []},
            token_budget=8_000,
        )

    with pytest.raises(VerificationGateError, match="unexpected new"):
        verify_packet(
            packet([]),
            before,
            judgment,
            root=Path("/tmp/root"),
            changed_path_reader=lambda _: [path],
            verification_runner=lambda argv, _: _verification(argv),
            scanner=lambda: _harness_scan(after),
        )

    evidence = verify_packet(
        packet([new_id]),
        before,
        judgment,
        root=Path("/tmp/root"),
        changed_path_reader=lambda _: [path],
        verification_runner=lambda argv, _: _verification(argv),
        scanner=lambda: _harness_scan(after),
    )
    assert evidence["diff"]["new"] == [new_id]


def test_im_11_changed_paths_are_harness_derived_from_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    tracked = tmp_path / "src" / "tracked.py"
    tracked.parent.mkdir()
    tracked.write_text("before\n")
    subprocess.run(["git", "add", "src/tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    tracked.write_text("after\n")
    (tmp_path / "src" / "new.py").write_text("new\n")

    assert read_changed_paths(tmp_path) == ["src/new.py", "src/tracked.py"]


def test_im_11_verification_command_is_not_shell_interpreted(tmp_path: Path) -> None:
    before = _manifest([_finding(1)])
    after = _manifest([])
    judgment = _judgment(before)
    identifier = before["findings"][0]["id"]
    path = before["findings"][0]["location"]["path"]
    marker = tmp_path / "shell-bypass"
    packet = build_packet(
        before,
        judgment,
        finding_ids=[identifier],
        scope=[path],
        recipe="fix it",
        verification=f"/usr/bin/true ; /usr/bin/touch {marker}",
        expected_delta={"fixed": [identifier], "allowed_new": [], "metrics": []},
        token_budget=8_000,
    )

    evidence = verify_packet(
        packet,
        before,
        judgment,
        root=tmp_path,
        changed_path_reader=lambda _: [path],
        scanner=lambda: _harness_scan(after),
    )

    assert evidence["verdict"] == "verified"
    assert evidence["verification"]["argv"][1] == ";"
    assert not marker.exists()
