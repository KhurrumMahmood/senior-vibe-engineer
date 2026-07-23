"""Accepted-artifact contracts for Dart semantic leads and shadow proposals."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/dart-d5/positive"
PROVIDER = ROOT / ".claude/skills/map-subsystem/scripts/dart_lsp_facts.py"
DETECTOR = (
    ROOT / ".claude/skills/find-semantic-duplication/scripts/detect_dart_semantic.py"
)
PROPOSER = ROOT / ".claude/skills/unify-shadows/scripts/propose_dart.py"
VALIDATOR = ROOT / ".claude/skills/_dart/dart_accepted_evidence.py"
DART = Path("/opt/homebrew/bin/dart")  # host-ref-allow: required frozen P7 runtime
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
QUERIES = [
    "buildStatement",
    "cloneOne",
    "cloneOnePreview",
    "cloneTwo",
    "cloneTwoPreview",
    "invoicePreview",
    "protocolDecoy",
    "protocolPreview",
    "statementPreview",
    "summarizeInvoice",
    "wrapperDuplicationDecoy",
]

pytestmark = pytest.mark.skipif(
    not DART.is_file() or not PYTHON.is_file(),
    reason="the frozen product Python and Dart 3.12 SDK are required",
)


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 120,
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


def _provider():
    spec = importlib.util.spec_from_file_location("test_dart_semantic_provider", PROVIDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical_hash(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _snapshot(host: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(part in {".git", "reports"} for part in relative.parts):
            continue
        if path.is_symlink():
            result[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            result[relative.as_posix()] = _sha256(path)
    return result


def _run_detector(
    host: Path,
    facts: Path,
    name: str,
    *,
    reviews: Path | None = None,
    script: Path = DETECTOR,
    expected: int = 0,
) -> Path:
    argv: list[str | Path] = [
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--target",
        "lib",
        "--facts",
        facts,
        "--output-dir",
        f"reports/semantic-duplication/{name}",
    ]
    if reviews is not None:
        argv.extend(["--reviews-dir", reviews])
    _run(*argv, cwd=host, expected=expected)
    return host / f"reports/semantic-duplication/{name}"


def _review(candidate: dict, directory: Path) -> Path:
    return _write_json(
        directory / f"{candidate['candidate_id']}.json",
        {
            "schema_version": "dart-semantic-duplication-review-v1",
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate["candidate_sha256"],
            "human_verdict": "accepted",
            "consolidation_shape": "keep_separate_document_why",
            "reviewer": "fixture-reviewer",
            "notes": "Keep the separately named public intents and document why they remain distinct.",
        },
    )


def _native_obligations() -> list[dict]:
    return [
        {
            "name": "analyze",
            "argv": ["dart", "analyze", "--fatal-infos", "--fatal-warnings", "."],
            "expected_returncode": 0,
        },
        {
            "name": "format",
            "argv": [
                "dart",
                "format",
                "--output=none",
                "--set-exit-if-changed",
                "lib",
                "bin",
                "test",
            ],
            "expected_returncode": 0,
        },
        {
            "name": "direct-test",
            "argv": ["dart", "test/native_test.dart"],
            "expected_returncode": 0,
        },
        {
            "name": "smoke",
            "argv": ["dart", "bin/smoke.dart"],
            "expected_returncode": 0,
            "expected_stdout": "42",
        },
    ]


def _acceptance(report: Path) -> Path:
    findings = json.loads((report / "findings.json").read_text())
    finding = findings["findings"][0]
    relative_artifacts = [
        "findings.json",
        "scan.json",
        "facts.json",
        finding["capability_matrix_path"],
        f"scout/{finding['candidate_id']}.json",
    ]
    spans: list[dict] = []
    seen: set[tuple] = set()
    for member in finding["members"]:
        for row in [member["source_span"], *[caller["source_span"] for caller in member["direct_callers"]]]:
            key = tuple(row[item] for item in ("path", "start_line", "start_column", "end_line", "end_column", "sha256"))
            if key not in seen:
                spans.append(row)
                seen.add(key)
    envelope = {
        "schema_version": "dart-accepted-evidence-v1",
        "producer": {
            "skill": "find-semantic-duplication",
            "version": "dart-d5-v1",
            "schema_version": "dart-semantic-duplication-v1",
            "terminal_status": "complete",
            "artifact": "findings.json",
        },
        "artifacts": [
            {"path": relative, "sha256": _sha256(report / relative)}
            for relative in relative_artifacts
        ],
        "selection": {
            "kind": "dart_semantic_duplication_finding",
            "id": finding["candidate_id"],
            "artifact": "findings.json",
            "json_pointer": "/findings/0",
            "sha256": _canonical_hash(finding),
        },
        "source_hashes": findings["source_hashes"],
        "configuration_hashes": findings["configuration_hashes"],
        "cited_spans": spans,
        "human_verdict": {
            "status": "accepted",
            "reviewer": "fixture-acceptor",
            "notes": "Accept the hash-bound static lead and its keep-separate shape for proposal drafting.",
        },
        "reviewed_boundaries": {
            "consolidation_shape": "keep_separate_document_why",
            "static_lead_only": True,
            "source_mutation_authorized": False,
            "runtime_equivalence_resolved": False,
        },
        "native_obligations": _native_obligations(),
    }
    envelope["acceptance_hash"] = _canonical_hash(envelope)
    return _write_json(report / "acceptance.json", envelope)


def _run_proposer(
    host: Path,
    report: Path,
    acceptance: Path,
    name: str,
    *,
    script: Path = PROPOSER,
    expected: int = 0,
) -> Path:
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--evidence-dir",
        report,
        "--acceptance",
        acceptance,
        "--output-dir",
        f"reports/unify-shadows/{name}",
        cwd=host,
        expected=expected,
    )
    return host / f"reports/unify-shadows/{name}"


@pytest.fixture(scope="module")
def accepted_host(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict, dict]:
    root = tmp_path_factory.mktemp("dart-d5-d7-accepted")
    host = root / "host"
    shutil.copytree(FIXTURE, host, ignore=shutil.ignore_patterns("reports"))
    before = _snapshot(host)
    facts = _provider().collect(host, ".", QUERIES, dart=str(DART), timeout=30)
    assert facts["status"] == "complete"
    facts_path = _write_json(host / "reports/dart-lsp-facts/facts.json", facts)
    pending_report = _run_detector(host, facts_path, "accepted")
    pending = json.loads((pending_report / "analysis.json").read_text())
    assert pending["status"] == "partial"
    assert pending["failure_kind"] == "human_review_required"
    assert len(pending["machine_candidates"]) == 1
    reviews = root / "reviews"
    _review(pending["machine_candidates"][0], reviews)
    report = _run_detector(host, facts_path, "accepted", reviews=reviews)
    accepted = json.loads((report / "analysis.json").read_text())
    assert accepted["status"] == "complete" and len(accepted["confirmed"]) == 1
    _acceptance(report)
    assert _snapshot(host) == before
    return host, pending, accepted


def _copy_accepted(
    accepted_host: tuple[Path, dict, dict], tmp_path: Path
) -> tuple[Path, Path, Path]:
    source, _, _ = accepted_host
    host = tmp_path / "host"
    shutil.copytree(source, host)
    report = host / "reports/semantic-duplication/accepted"
    return host, report, report / "acceptance.json"


def test_d5_static_lead_is_conservative_and_human_shape_is_hash_bound(
    accepted_host: tuple[Path, dict, dict], tmp_path: Path
) -> None:
    source, pending, accepted = accepted_host
    candidate = pending["machine_candidates"][0]
    assert candidate["machine_consolidation_shape"] is None
    assert candidate["human_verdict"] == "required"
    assert [row["name"] for row in candidate["members"]] == [
        "buildStatement",
        "summarizeInvoice",
    ]
    assert {row["reason"] for row in pending["rejected"]} >= {
        "lexical_clone",
        "first_party_policy_callee_mismatch",
    }
    assert {row["reason"] for row in pending["ineligible"]} >= {
        "dynamic_syntax",
        "generic_function",
        "not_top_level_free_function",
        "wrapper_without_direct_constructor_return",
    }
    finding = accepted["confirmed"][0]
    assert finding["human_verdict"] == "accepted"
    assert finding["consolidation_shape"] == "keep_separate_document_why"
    assert finding["review"]["candidate_sha256"] == candidate["candidate_sha256"]
    assert all(member["fact_status"] == "complete" for member in finding["members"])
    assert all(member["direct_callers"] for member in finding["members"])

    host = tmp_path / "bad-review-host"
    shutil.copytree(source, host)
    facts = host / "reports/dart-lsp-facts/facts.json"
    bad_reviews = tmp_path / "bad-reviews"
    review = _review(candidate, bad_reviews)
    payload = json.loads(review.read_text())
    payload["candidate_sha256"] = "0" * 64
    _write_json(review, payload)
    report = _run_detector(
        host, facts, "bad-review", reviews=bad_reviews, expected=2
    )
    refusal = json.loads((report / "analysis.json").read_text())
    assert refusal["status"] == "failed"
    assert refusal["failure_kind"] == "invalid_human_review"
    assert refusal["confirmed"] == []


def test_d7_consumes_only_accepted_d5_and_emits_exact_three_artifacts(
    accepted_host: tuple[Path, dict, dict], tmp_path: Path
) -> None:
    host, report, acceptance = _copy_accepted(accepted_host, tmp_path)
    before = _snapshot(host)
    output = _run_proposer(host, report, acceptance, "ready")
    assert sorted(path.name for path in output.iterdir()) == [
        "evidence.json",
        "proposal.md",
        "scope.json",
    ]
    evidence = json.loads((output / "evidence.json").read_text())
    scope = json.loads((output / "scope.json").read_text())
    proposal = (output / "proposal.md").read_text()
    assert evidence["status"] == "ready_for_human_review"
    assert evidence["shape"] == "keep_separate_document_why"
    assert scope["mutation_authorized"] is False
    assert "Document the load-bearing reason" in proposal
    assert "no shared implementation or caller-move plan" in proposal
    assert "selected by the accepted human D5 review" in proposal
    assert _snapshot(host) == before
    script_text = PROPOSER.read_text()
    assert "subprocess" not in script_text
    assert "language-server" not in script_text
    assert "dart_lsp_facts" not in script_text


def test_d7_ready_failure_ready_replacement_and_refusal_matrix(
    accepted_host: tuple[Path, dict, dict], tmp_path: Path
) -> None:
    host, report, acceptance = _copy_accepted(accepted_host, tmp_path)
    before = _snapshot(host)
    output = _run_proposer(host, report, acceptance, "reuse")
    (output / "stale-ready.json").write_text("{}\n", encoding="utf-8")

    envelope = json.loads(acceptance.read_text())
    pending = dict(envelope)
    pending["human_verdict"] = {
        **pending["human_verdict"],
        "status": "pending",
    }
    pending.pop("acceptance_hash")
    pending["acceptance_hash"] = _canonical_hash(pending)
    pending_path = _write_json(report / "pending-acceptance.json", pending)
    _run_proposer(host, report, pending_path, "reuse", expected=2)
    refused = json.loads((output / "evidence.json").read_text())
    assert refused["status"] == "partial"
    assert refused["failure_kind"] == "human_acceptance_required"
    assert not (output / "stale-ready.json").exists()
    assert "refusal" in (output / "proposal.md").read_text().lower()

    matrix = report / "capability_matrices/DART-SD-0001.json"
    matrix_bytes = matrix.read_bytes()
    matrix.write_bytes(matrix_bytes + b" ")
    _run_proposer(host, report, acceptance, "reuse", expected=2)
    tampered = json.loads((output / "evidence.json").read_text())
    assert tampered["status"] == "failed"
    assert tampered["failure_kind"] == "invalid_accepted_evidence"
    matrix.write_bytes(matrix_bytes)

    source = host / "lib/duplication.dart"
    source_bytes = source.read_bytes()
    source.write_bytes(source_bytes + b"\n")
    _run_proposer(host, report, acceptance, "reuse", expected=2)
    stale = json.loads((output / "evidence.json").read_text())
    assert stale["status"] == "failed"
    assert stale["failure_kind"] == "stale_accepted_evidence"
    source.write_bytes(source_bytes)

    partial = dict(envelope)
    partial["producer"] = {**partial["producer"], "terminal_status": "partial"}
    partial.pop("acceptance_hash")
    partial["acceptance_hash"] = _canonical_hash(partial)
    partial_path = _write_json(report / "partial-acceptance.json", partial)
    _run_proposer(host, report, partial_path, "reuse", expected=2)
    partial_result = json.loads((output / "evidence.json").read_text())
    assert partial_result["status"] == "partial"
    assert partial_result["failure_kind"] == "upstream_not_complete"

    _run_proposer(host, report, acceptance, "reuse")
    restored = json.loads((output / "evidence.json").read_text())
    assert restored["status"] == "ready_for_human_review"
    assert sorted(path.name for path in output.iterdir()) == [
        "evidence.json",
        "proposal.md",
        "scope.json",
    ]
    assert _snapshot(host) == before

    missing = _run_proposer(
        host,
        host / "reports/missing-d5",
        Path("acceptance.json"),
        "missing",
        expected=2,
    )
    missing_result = json.loads((missing / "evidence.json").read_text())
    assert missing_result["status"] == "partial"
    assert missing_result["failure_kind"] == "evidence_unavailable"


def test_exact_copied_closures_run_without_repository_imports(
    accepted_host: tuple[Path, dict, dict], tmp_path: Path
) -> None:
    host, report, acceptance = _copy_accepted(accepted_host, tmp_path / "copy")
    install = tmp_path / "installed/.agents/skills/on-demand"
    copied_provider = install / "map-subsystem/scripts/dart_lsp_facts.py"
    copied_detector = install / "find-semantic-duplication/scripts/detect_dart_semantic.py"
    copied_proposer = install / "unify-shadows/scripts/propose_dart.py"
    copied_validator = install / "_dart/dart_accepted_evidence.py"
    for source, destination in (
        (PROVIDER, copied_provider),
        (DETECTOR, copied_detector),
        (PROPOSER, copied_proposer),
        (VALIDATOR, copied_validator),
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    copied_facts = host / "reports/dart-lsp-facts/copied.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        copied_provider,
        "--project-root",
        host,
        "--target",
        ".",
        *sum((["--query", query] for query in QUERIES), []),
        "--dart",
        DART,
        "--output",
        "reports/dart-lsp-facts/copied.json",
        cwd=tmp_path,
    )
    pending = _run_detector(host, copied_facts, "copied", script=copied_detector)
    candidate = json.loads((pending / "candidates.jsonl").read_text())
    reviews = tmp_path / "copied-reviews"
    _review(candidate, reviews)
    copied_report = _run_detector(
        host,
        copied_facts,
        "copied",
        reviews=reviews,
        script=copied_detector,
    )
    copied_acceptance = _acceptance(copied_report)
    output = _run_proposer(
        host,
        copied_report,
        copied_acceptance,
        "copied",
        script=copied_proposer,
    )
    assert json.loads((output / "evidence.json").read_text())["status"] == (
        "ready_for_human_review"
    )
    assert str(ROOT) not in copied_detector.read_text()
    assert str(ROOT) not in copied_proposer.read_text()
    assert "language-server" not in copied_detector.read_text()
    assert "dart_lsp_facts" not in copied_proposer.read_text()
