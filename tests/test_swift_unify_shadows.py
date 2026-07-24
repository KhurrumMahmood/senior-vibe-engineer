"""Accepted, refused, copied, and source-preserving Swift shadow proposals."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
SWIFT = Path("/usr/bin/swift")
SWIFTC = Path("/usr/bin/swiftc")
SWIFT_FORMAT = Path("/Library/Developer/CommandLineTools/usr/bin/swift-format")
FIXTURE = ROOT / "tests/fixtures/swift-semantic-a3/host"
PROVIDER = ROOT / ".claude/skills/_swift-semantic-readonly/swift_semantic_facts.py"
DETECTOR = ROOT / ".claude/skills/find-semantic-duplication/scripts/detect_swift_semantic.py"
PROPOSER = ROOT / ".claude/skills/unify-shadows/scripts/propose_swift.py"
QUERIES = sorted(
    {
        "Statement", "billingSurface", "buildStatement", "cloneOne", "cloneTwo",
        "invoiceSurface", "normalize", "policyDecoy", "policyFee",
        "Receipt", "receiptFactoryReference", "roundCents", "statementFactoryReference",
        "summarizeInvoice", "summarizeReceipt", "makeReceipt", "wrapperDecoy",
    }
)
GATES = {
    "resolved_members_and_callers": "accepted_exact_selected_target",
    "static_capability_overlap": "accepted_not_equivalence",
    "behavioral_runtime_equivalence": "not_established_no_mutation_authority",
    "overload_default_argument_selection": "accepted_exact",
    "protocol_existential_override_dispatch": "none_selected",
    "closures_dynamic_reflection_objc": "none_selected",
    "actor_global_actor_concurrency": "none_selected",
    "conditional_macros_plugins_generated": "no_selected_dependency",
    "external_callers_package_variants": "none_after_human_review",
    "errors_side_effects_resources_frameworks": "not_established",
    "abi_binary_compatibility": "separate_approval_required",
}

pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (PYTHON, SWIFT, SWIFTC, SWIFT_FORMAT)),
    reason="frozen product Python and Apple Swift 6.3.3 are required",
)


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 360,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in argv], cwd=cwd, capture_output=True, text=True,
        check=False, shell=False, timeout=timeout,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _signed(payload: dict[str, Any]) -> dict[str, Any]:
    payload["acceptance_sha256"] = _canonical(payload)
    return payload


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host, ignore=shutil.ignore_patterns("reports", ".build"))
    return host


def _state(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): _sha(path)
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not any(
            part in {"reports", ".build", ".swiftpm", ".agents"}
            for part in path.relative_to(host).parts
        )
    }


def _facts(host: Path, provider: Path = PROVIDER) -> Path:
    output = host / "reports/swift-semantic-facts/unify.json"
    argv: list[str | Path] = [
        PYTHON, "-I", "-S", provider, "--project-root", host,
        "--target-name", "SwiftA3Core", "--configuration", "debug",
        "--output", output, "--swift", SWIFT, "--swiftc", SWIFTC,
        "--swift-format", SWIFT_FORMAT, "--check-product", "swift-a3-check",
        "--expected-check", "swift-a3-checks-ok", "--smoke-product",
        "swift-a3-smoke", "--expected-smoke", "swift-a3:42",
    ]
    for query in QUERIES:
        argv.extend(["--query", query])
    _run(*argv, cwd=host)
    assert _json(output)["status"] == "complete"
    return output


def _analysis(
    host: Path,
    facts: Path,
    verdict: str,
    detector: Path = DETECTOR,
    pair: tuple[str, str] = ("buildStatement", "summarizeInvoice"),
) -> tuple[Path, dict[str, Any]]:
    output = host / "reports/semantic-duplication/swift"
    reviews = host / "reports/semantic-duplication/reviews"
    _run(
        PYTHON, "-I", "-S", detector, "--project-root", host,
        "--target-name", "SwiftA3Core", "--target", "Sources/SwiftA3Core",
        "--facts", facts, "--output-dir", output, cwd=host.parent,
    )
    candidates = [
        json.loads(line)
        for line in (output / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [[row["name"] for row in candidate["functions"]] for candidate in candidates] == [
        ["buildStatement", "summarizeInvoice"],
        ["makeReceipt", "summarizeReceipt"],
    ]
    for candidate in candidates:
        _write(
            reviews / f'{candidate["candidate_id"]}.json',
            {
                "schema_version": "swift-semantic-duplication-review-v1",
                "candidate_id": candidate["candidate_id"],
                "candidate_sha256": candidate["candidate_sha256"],
                "human_verdict": "accepted",
                "verdict": verdict,
                "notes": "Reviewed the exact static pair, caller split, and non-equivalence limits.",
            },
        )
    _run(
        PYTHON, "-I", "-S", detector, "--project-root", host,
        "--target-name", "SwiftA3Core", "--target", "Sources/SwiftA3Core",
        "--facts", facts, "--output-dir", output, "--reviews-dir", reviews,
        cwd=host.parent,
    )
    analysis = output / "analysis.json"
    finding = next(
        row
        for row in _json(analysis)["findings"]
        if tuple(function["name"] for function in row["functions"]) == pair
    )
    assert finding["verdict"] == verdict
    return analysis, finding


def _acceptance(
    host: Path,
    facts: Path,
    analysis: Path,
    finding: dict[str, Any],
    decision: str,
    proposer: Path = PROPOSER,
) -> Path:
    fact_payload = _json(facts)
    payload = {
        "schema_version": "swift-unify-shadows-acceptance-v1",
        "language": "swift",
        "status": "accepted",
        "consumer": "unify-shadows",
        "target_name": "SwiftA3Core",
        "facts": facts.relative_to(host).as_posix(),
        "facts_sha256": _sha(facts),
        "fact_pack_sha256": fact_payload["fact_pack_sha256"],
        "source_manifest_sha256": fact_payload["source_manifest_sha256"],
        "analysis": analysis.relative_to(host).as_posix(),
        "analysis_sha256": _sha(analysis),
        "candidate_id": finding["candidate_id"],
        "candidate_sha256": finding["candidate_sha256"],
        "upstream_verdict": finding["verdict"],
        "decision": decision,
        "boundary_verdicts": GATES,
        "authority": {
            "provider_sha256": _sha(PROVIDER),
            "proposer_sha256": _sha(proposer),
        },
        "reviewer": "swift-unify-fixture-owner",
        "notes": "Accepted the exact disposition without granting source mutation authority.",
    }
    return _write(
        host / "reports/semantic-duplication/swift/accepted-unify.json",
        _signed(payload),
    )


def _propose(
    host: Path,
    facts: Path,
    analysis: Path,
    acceptance: Path,
    proposer: Path = PROPOSER,
    *,
    name: str = "SWIFT-SD-0001",
    expected: int = 0,
    output: Path | None = None,
) -> Path:
    destination = output or host / f"reports/unify-shadows/swift/{name}"
    _run(
        PYTHON, "-I", "-S", proposer, "--project-root", host,
        "--facts", facts, "--analysis", analysis, "--acceptance", acceptance,
        "--output-dir", destination, cwd=host.parent, expected=expected,
    )
    return destination


def _resign(path: Path, mutate) -> None:
    payload = _json(path)
    mutate(payload)
    payload.pop("acceptance_sha256", None)
    _write(path, _signed(payload))


def test_swift_unify_shadows_copied_value_refusal_and_recovery(tmp_path: Path) -> None:
    host = _host(tmp_path)
    before = _state(host)
    facts = _facts(host)
    analysis, finding = _analysis(host, facts, "consolidate_candidate")
    acceptance = _acceptance(host, facts, analysis, finding, "share_utilities")

    installed = tmp_path / "outside/.agents/skills"
    copied_provider = installed / "_swift-semantic-readonly/swift_semantic_facts.py"
    copied_proposer = installed / "unify-shadows/scripts/propose_swift.py"
    copied_provider.parent.mkdir(parents=True)
    copied_proposer.parent.mkdir(parents=True)
    shutil.copy2(PROVIDER, copied_provider)
    shutil.copy2(PROPOSER, copied_proposer)
    output = _propose(host, facts, analysis, acceptance, copied_proposer)

    assert {path.name for path in output.iterdir()} == {
        "proposal.md", "evidence.json", "scope.json"
    }
    evidence = _json(output / "evidence.json")
    scope = _json(output / "scope.json")
    assert evidence["status"] == "complete"
    assert evidence["outcome"] == "proposal_ready"
    assert evidence["consolidation_shape"] == "share_utilities"
    assert [row["id"] for row in evidence["native_checks"]] == [
        "swiftpm-dump-package", "swiftpm-describe", "swiftpm-build",
        "compiler-parse", "swift-format-lint", "direct-check",
        "executable-smoke", "compiler-ast",
    ]
    assert all(row["returncode"] == 0 for row in evidence["native_checks"])
    assert scope["read_only"] is True and scope["mutation_authorized"] is False
    assert [row["definition"]["name"] for row in scope["members"]] == [
        "buildStatement", "summarizeInvoice"
    ]
    callers = [
        {row["caller"]["name"] for row in member["resolved_callers"]}
        for member in scope["members"]
    ]
    assert callers == [
        {"billingSurface", "recordStatement", "statementTotal", "wrapperDecoy"},
        {"invoiceSurface"},
    ]
    assert "statementFactoryReference" not in callers[0]
    assert callers[0].isdisjoint(callers[1])
    assert scope["static_shape"]["shared_resolved_callees"] == ["normalize"]
    assert scope["static_shape"]["return_shape"] == {
        "fields": ["label", "total"], "type": "Statement"
    }
    assert scope["static_shape"]["selected_initializer_overload"]["line"] == 5

    receipt_acceptance = _acceptance(
        host,
        facts,
        analysis,
        next(
            row
            for row in _json(analysis)["findings"]
            if [function["name"] for function in row["functions"]]
            == ["makeReceipt", "summarizeReceipt"]
        ),
        "share_utilities",
        copied_proposer,
    )
    receipt_output = _propose(
        host,
        facts,
        analysis,
        receipt_acceptance,
        copied_proposer,
        name="SWIFT-SD-0002",
    )
    receipt_scope = _json(receipt_output / "scope.json")
    assert receipt_scope["static_shape"]["return_shape"] == {
        "fields": ["cents", "code"],
        "type": "Receipt",
    }
    assert receipt_scope["static_shape"]["shared_resolved_callees"] == ["roundCents"]
    assert receipt_scope["static_shape"]["selected_initializer_overload"]["parent"] == (
        "Receipt"
    )
    assert [
        {row["caller"]["name"] for row in member["resolved_callers"]}
        for member in receipt_scope["members"]
    ] == [{"checkoutReceipt"}, {"receiptTotal"}]
    assert "receiptFactoryReference" not in {
        row["caller"]["name"]
        for member in receipt_scope["members"]
        for row in member["resolved_callers"]
    }
    assert _state(host) == before
    copied_text = copied_proposer.read_text(encoding="utf-8")
    assert str(ROOT) not in copied_text
    assert "detect_swift_semantic" not in copied_text
    assert "rglob" not in copied_text and "read_text" not in copied_text

    original = _json(acceptance)
    for gate in GATES:
        _resign(
            acceptance,
            lambda payload, key=gate: payload["boundary_verdicts"].update({key: "unknown"}),
        )
        refused = _propose(host, facts, analysis, acceptance, copied_proposer, expected=2)
        refusal_evidence = _json(refused / "evidence.json")
        refusal_scope = _json(refused / "scope.json")
        assert refusal_evidence["failure_kind"] == "acceptance_invalid"
        assert refusal_scope["members"] == []
        assert refusal_scope["caller_impact"] == []
        assert refusal_scope["static_shape"] == {}
        _write(acceptance, original)
    _propose(host, facts, analysis, acceptance, copied_proposer)
    assert _json(output / "evidence.json")["outcome"] == "proposal_ready"
    assert _state(host) == before


def test_swift_unify_shadows_dispositions_stale_tamper_and_unsafe(tmp_path: Path) -> None:
    host = _host(tmp_path)
    facts = _facts(host)

    analysis, finding = _analysis(host, facts, "keep_separate_document_why")
    acceptance = _acceptance(
        host, facts, analysis, finding, "keep_separate_document_why"
    )
    output = _propose(host, facts, analysis, acceptance)
    assert _json(output / "evidence.json")["outcome"] == "keep_separate_documented"

    incompatible = _json(acceptance)
    incompatible["decision"] = "share_utilities"
    incompatible.pop("acceptance_sha256")
    _write(acceptance, _signed(incompatible))
    _propose(host, facts, analysis, acceptance, expected=2)
    assert _json(output / "evidence.json")["failure_kind"] == "verdict_incompatible"

    acceptance = _acceptance(
        host, facts, analysis, finding, "keep_separate_document_why"
    )
    tampered = _json(analysis)
    tampered["summary"]["reviewed"] = 99
    _write(analysis, tampered)
    _propose(host, facts, analysis, acceptance, expected=2)
    assert _json(output / "evidence.json")["failure_kind"] == "artifact_hash_mismatch"

    analysis, finding = _analysis(host, facts, "not_equivalent")
    acceptance = _acceptance(host, facts, analysis, finding, "not_equivalent_documented")
    _propose(host, facts, analysis, acceptance)
    assert _json(output / "evidence.json")["outcome"] == "not_equivalent_documented"

    source = host / "Sources/SwiftA3Core/Duplication.swift"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    _propose(host, facts, analysis, acceptance, expected=2)
    assert _json(output / "evidence.json")["failure_kind"] == "fact_pack_stale"

    outside = tmp_path / "outside-output"
    _propose(
        host, facts, analysis, acceptance, expected=2, output=outside,
    )
    assert not outside.exists()
