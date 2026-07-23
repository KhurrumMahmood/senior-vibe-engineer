"""Final-artifact contracts for the bounded Dart D7 proposal consumers."""

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
FIXTURE = ROOT / "tests/fixtures/dart-d7"
PROVIDER = ROOT / ".claude/skills/map-subsystem/scripts/dart_lsp_facts.py"
DETECTOR = ROOT / ".claude/skills/find-folder-topology-drift/scripts/detect_dart.py"
VALIDATOR = ROOT / ".claude/skills/_dart/dart_accepted_evidence.py"
BOUNDARY = ROOT / ".claude/skills/propose-boundary/scripts/propose_dart.py"
FOLDER = ROOT / ".claude/skills/propose-folder-reorganization/scripts/propose_dart.py"
DUPLICATION = ROOT / ".claude/skills/find-semantic-duplication/scripts/detect_dart_semantic.py"
DART = Path("/opt/homebrew/bin/dart")  # host-ref-allow: required frozen P7 runtime
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: required frozen P7 runtime
)
POSITIVE_QUERIES = [
    "InvoiceCalculator",
    "InvoicePolicy",
    "buildInvoice",
    "calculateTax",
    "collectPayment",
    "formatInvoice",
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


def _canonical_hash(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / name, host, ignore=shutil.ignore_patterns("reports"))
    return host


def _snapshot(host: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(part in {".git", "reports"} for part in relative.parts):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = _sha256(path)
    return rows


def _provider():
    spec = importlib.util.spec_from_file_location("test_dart_d7_lsp", PROVIDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _facts(host: Path, queries: list[str]) -> dict:
    facts = _provider().collect(host, "lib", queries, dart=str(DART), timeout=30)
    assert facts["status"] == "complete", facts
    return facts


def _d1_findings(host: Path, scan_name: str = "source") -> dict:
    _run(
        PYTHON,
        "-I",
        "-S",
        DETECTOR,
        "--project-root",
        host,
        "--dart-root",
        "lib/src",
        "--output",
        f"reports/d1/{scan_name}/detections.jsonl",
        "--dart",
        DART,
        "--direct-test",
        "test/native_test.dart",
        "--smoke-entrypoint",
        "bin/smoke.dart",
        "--expected-smoke",
        "invoice:116" if host.name == "positive" else "core:42",
        cwd=host,
    )
    return json.loads((host / f"reports/d1/{scan_name}/findings.json").read_text())


def _span(host: Path, path: str, line: int, column: int, token: str) -> dict:
    text = (host / path).read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    assert lines[line - 1][column - 1 :].startswith(token), (path, line, column, token)
    return {
        "path": path,
        "start_line": line,
        "start_column": column,
        "end_line": line,
        "end_column": column + len(token),
        "sha256": hashlib.sha256(token.encode()).hexdigest(),
    }


def _edge_span(host: Path, edge: dict) -> dict:
    line = (host / edge["source"]).read_text(encoding="utf-8").splitlines()[edge["line"] - 1]
    token = edge["specifier"]
    column = line.index(token) + 1
    return _span(host, edge["source"], edge["line"], column, token)


def _source_hashes(facts: dict) -> list[dict]:
    return [
        {"path": row["path"], "sha256": row["sha256"], "role": row["role"]}
        for row in facts["source_hashes"]
    ]


def _native_obligations(smoke: str) -> list[dict]:
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
            "expected_stdout": smoke,
        },
    ]


def _acceptance(
    host: Path,
    evidence: Path,
    *,
    producer: dict,
    selection: dict,
    artifacts: list[Path],
    facts: dict,
    cited_spans: list[dict],
    reviewed_boundaries: dict,
    smoke: str,
) -> Path:
    envelope = {
        "schema_version": "dart-accepted-evidence-v1",
        "producer": producer,
        "selection": selection,
        "artifacts": [
            {"path": path.relative_to(evidence).as_posix(), "sha256": _sha256(path)}
            for path in sorted(artifacts)
        ],
        "source_hashes": _source_hashes(facts),
        "configuration_hashes": [
            {"path": "pubspec.yaml", "sha256": _sha256(host / "pubspec.yaml")},
            {
                "path": ".dart_tool/package_config.json",
                "sha256": _sha256(host / ".dart_tool/package_config.json"),
                "kind": "dart_package_config",
            },
        ],
        "cited_spans": cited_spans,
        "human_verdict": {
            "status": "accepted",
            "reviewer": "dart-d7-fixture-owner",
            "notes": "The exact bounded proposal input and named limitations were reviewed.",
        },
        "reviewed_boundaries": reviewed_boundaries,
        "native_obligations": _native_obligations(smoke),
    }
    envelope["acceptance_hash"] = _canonical_hash(envelope)
    return _write_json(evidence / "acceptance.json", envelope)


def _boundary_evidence(
    host: Path,
    facts: dict,
    *,
    decision: str = "extract",
    target: str = "lib/src/invoicing",
    boundary_name: str = "invoicing",
) -> tuple[Path, Path]:
    evidence = host / f"reports/d7-evidence/boundary-{decision}"
    query_pack = _write_json(evidence / "query-pack.json", facts)
    selection_row = {
        "id": f"boundary-{boundary_name}",
        "target": target,
        "boundary_name": boundary_name,
        "decision": decision,
        "rationale": (
            "Keep the cohesive target in place."
            if decision == "defer_cohesive"
            else "Expose the reviewed child domain through one stable library seam."
        ),
    }
    selected = _write_json(
        evidence / "selection.json",
        {
            "schema_version": "dart-boundary-selection-v1",
            "language": "dart",
            "status": "complete",
            "selection": selection_row,
        },
    )
    selected_symbols = [
        row
        for row in facts["document_symbols"]
        if row.get("top_level")
        and row["source"].startswith(f"{target}/")
        and not row["name"].startswith("_")
    ]
    spans = [
        _span(host, row["source"], row["line"], row["column"], row["name"])
        for row in selected_symbols
    ]
    related_edges = [
        row
        for row in facts["module_edges"]
        if any(target_row["path"].startswith(target) for target_row in row["targets"])
        or row["source"].startswith(target)
    ]
    spans.extend(_edge_span(host, row) for row in related_edges)
    spans.extend(
        _span(host, ref["path"], ref["line"], ref["column"], row["name"])
        for row in facts["reference_queries"]
        for ref in row["references"]
        if ref["path"].startswith("lib/")
    )
    producer = {
        "skill": "map-subsystem",
        "version": "dart-d4-v1",
        "schema_version": "dart-lsp-facts-v1",
        "terminal_status": "complete",
        "artifact": "query-pack.json",
    }
    selection = {
        "kind": "dart_boundary_proposal",
        "id": selection_row["id"],
        "artifact": "selection.json",
        "json_pointer": "/selection",
        "sha256": _canonical_hash(selection_row),
    }
    acceptance = _acceptance(
        host,
        evidence,
        producer=producer,
        selection=selection,
        artifacts=[query_pack, selected],
        facts=facts,
        cited_spans=spans,
        reviewed_boundaries={
            "selected_configuration_only": True,
            "external_consumers_resolved": False,
            "runtime_graph_resolved": False,
        },
        smoke="invoice:116" if host.name == "positive" else "core:42",
    )
    return evidence, acceptance


def _folder_evidence(
    host: Path,
    facts: dict,
    d1: dict,
    *,
    decision: str = "split",
    convention: str | None = "folder_for_three_prefix_siblings",
) -> tuple[Path, Path]:
    finding = d1["findings"][0]
    evidence = host / f"reports/d7-evidence/folder-{decision}"
    query_pack = _write_json(evidence / "query-pack.json", facts)
    d1_artifact = _write_json(evidence / "d1-findings.json", d1)
    cluster = {
        "id": "dart-folder-billing",
        "parent": finding["file"],
        "prefix": finding["prefix"],
        "files": finding["files"],
        "d1_evidence_sha256": finding["evidence_sha256"],
        "d1_finding_sha256": _canonical_hash(finding),
        "d4_fact_pack_sha256": facts["fact_pack_sha256"],
        "decision": decision,
        "convention": convention,
        "rationale": (
            "The three accepted prefix siblings form one navigable billing domain."
            if decision == "split"
            else "The reviewer judged the direct siblings cohesive in the flat parent."
        ),
    }
    accepted_cluster = _write_json(
        evidence / "accepted-cluster.json",
        {
            "schema_version": "dart-folder-cluster-v1",
            "language": "dart",
            "status": "complete",
            "d1_artifact": "d1-findings.json",
            "d4_artifact": "query-pack.json",
            "cluster": cluster,
        },
    )
    symbols = {
        row["source"]: row
        for row in facts["document_symbols"]
        if row.get("top_level") and row["source"] in cluster["files"]
    }
    spans = [
        _span(host, path, symbols[path]["line"], symbols[path]["column"], symbols[path]["name"])
        for path in cluster["files"]
    ]
    cluster_set = set(cluster["files"])
    impacts = [
        row
        for row in facts["module_edges"]
        if any(target["path"] in cluster_set for target in row["targets"])
    ]
    spans.extend(_edge_span(host, row) for row in impacts)
    cluster_barrels = {row["source"] for row in impacts if row["kind"] == "export"}
    root_barrel_edges = [
        row
        for row in facts["module_edges"]
        if row["kind"] == "export"
        and any(target["path"] in cluster_barrels for target in row["targets"])
    ]
    spans.extend(_edge_span(host, row) for row in root_barrel_edges)
    producer = {
        "skill": "find-folder-topology-drift",
        "version": "dart-d1-v1",
        "schema_version": "dart-folder-cluster-v1",
        "terminal_status": "complete",
        "artifact": "accepted-cluster.json",
    }
    selection = {
        "kind": "dart_folder_reorganization_cluster",
        "id": cluster["id"],
        "artifact": "accepted-cluster.json",
        "json_pointer": "/cluster",
        "sha256": _canonical_hash(cluster),
    }
    acceptance = _acceptance(
        host,
        evidence,
        producer=producer,
        selection=selection,
        artifacts=[query_pack, d1_artifact, accepted_cluster],
        facts=facts,
        cited_spans=spans,
        reviewed_boundaries={
            "cluster_judgment": decision,
            "project_convention": convention or "absent",
            "cross_package_move": False,
            "public_package_uri_compatibility": "private-lib-src-only",
        },
        smoke="invoice:116",
    )
    return evidence, acceptance


def _invoke(
    script: Path,
    host: Path,
    evidence: Path,
    acceptance: Path,
    name: str,
    *,
    expected: int = 0,
    dart: Path = DART,
) -> subprocess.CompletedProcess[str]:
    family = (
        "propose-boundary"
        if "propose-boundary" in script.parts
        else "propose-folder-reorganization"
    )
    return _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--evidence-dir",
        evidence.relative_to(host),
        "--acceptance",
        acceptance.relative_to(evidence),
        "--inspection",
        f"reports/{family}/{name}/inspection.json",
        "--proposal",
        f"reports/{family}/{name}/proposal.md",
        "--dart",
        dart,
        cwd=host,
        expected=expected,
    )


def _inspection(host: Path, family: str, name: str) -> dict:
    return json.loads((host / f"reports/{family}/{name}/inspection.json").read_text())


def _apply_plan(root: Path, payload: dict) -> None:
    for move in payload.get("exact_moves", []):
        source = root / move["from"]
        destination = root / move["to"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
    for edit in payload.get("exact_edits", []):
        path = root / edit["path"]
        text = path.read_text(encoding="utf-8")
        assert text.count(edit["before"]) == 1
        path.write_text(text.replace(edit["before"], edit["after"], 1), encoding="utf-8")
    for create in payload.get("create_files", []):
        path = root / create["path"]
        assert not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(create["contents"], encoding="utf-8")


def _native_matrix(host: Path, smoke: str) -> None:
    commands = [
        [DART, "analyze", "--fatal-infos", "--fatal-warnings", "."],
        [DART, "format", "--output=none", "--set-exit-if-changed", "lib", "bin", "test"],
        [DART, "test/native_test.dart"],
        [DART, "bin/smoke.dart"],
    ]
    results = [_run(*command, cwd=host) for command in commands]
    assert results[-1].stdout.strip() == smoke


def test_positive_proposals_have_exact_citations_and_verified_after_trees(
    tmp_path: Path,
) -> None:
    host = _copy_fixture(tmp_path, "positive")
    before = _snapshot(host)
    facts = _facts(host, POSITIVE_QUERIES)
    d1 = _d1_findings(host)
    boundary_evidence, boundary_acceptance = _boundary_evidence(host, facts)
    folder_evidence, folder_acceptance = _folder_evidence(host, facts, d1)

    _invoke(BOUNDARY, host, boundary_evidence, boundary_acceptance, "ready")
    _invoke(FOLDER, host, folder_evidence, folder_acceptance, "ready")

    boundary = _inspection(host, "propose-boundary", "ready")
    assert boundary["status"] == "ready_for_human_review"
    assert boundary["recommendation"] == "review_boundary"
    assert [row["name"] for row in boundary["public_api"]] == [
        "InvoiceCalculator",
        "formatInvoice",
        "InvoicePolicy",
    ]
    assert {row["path"] for row in boundary["caller_impact"]} == {"lib/src/checkout.dart"}
    assert len(boundary["caller_impact"][0]["citations"]) == 3
    assert boundary["public_compatibility"]["root_barrel_preserved"] is True
    assert [row["path"] for row in boundary["test_surface"]] == ["test/native_test.dart"]
    assert boundary["test_surface"][0]["citation"].startswith("test/native_test.dart:sha256:")
    assert boundary["native_verification"]["current_tree"]["status"] == "passed"
    assert boundary["native_verification"]["disposable_after_tree"]["status"] == "passed"
    assert boundary["source_preservation"]["verified"] is True
    assert all(row["citation"].count(":") >= 2 for row in boundary["public_api"])
    assert boundary["create_files"] == [
        {"path": "lib/invoicing.dart", "contents": "export 'src/invoicing/invoicing.dart';\n"}
    ]

    folder = _inspection(host, "propose-folder-reorganization", "ready")
    assert folder["status"] == "ready_for_human_review"
    assert folder["recommendation"] == "review_folder_plan"
    assert folder["current_tree"] == [
        "lib/src/billing_invoice.dart",
        "lib/src/billing_payment.dart",
        "lib/src/billing_tax.dart",
    ]
    assert folder["proposed_tree"] == [
        "lib/src/billing/invoice.dart",
        "lib/src/billing/payment.dart",
        "lib/src/billing/tax.dart",
    ]
    assert len(folder["exact_moves"]) == 3
    assert len(folder["import_impact"]) == 6
    assert folder["accounting"] == {
        "cluster_members": 3,
        "planned_members": 3,
        "resolved_edges": 6,
        "planned_edges": 6,
    }
    assert folder["public_compatibility"]["barrel_path"] == "lib/src/billing.dart"
    assert folder["public_compatibility"]["root_barrels"] == [
        {
            "path": "lib/dart_d7_positive.dart",
            "citation": "lib/dart_d7_positive.dart:1:9",
        }
    ]
    assert [row["path"] for row in folder["test_surface"]] == ["test/native_test.dart"]
    assert folder["native_verification"]["disposable_after_tree"]["status"] == "passed"
    assert folder["source_preservation"]["verified"] is True
    assert _snapshot(host) == before

    for payload, name in ((boundary, "boundary"), (folder, "folder")):
        disposable = tmp_path / f"independent-{name}"
        shutil.copytree(host, disposable, ignore=shutil.ignore_patterns("reports"))
        _apply_plan(disposable, payload)
        _native_matrix(disposable, "invoice:116")


def test_cohesive_and_clean_inputs_defer_without_forcing_plans(tmp_path: Path) -> None:
    clean = _copy_fixture(tmp_path, "clean")
    clean_facts = _facts(clean, ["cleanInvoice", "cleanPayment", "describeCore"])
    clean_d1 = _d1_findings(clean)
    assert clean_d1["status"] == "complete"
    assert clean_d1["outcome"] == "clean" and clean_d1["findings"] == []
    boundary_evidence, boundary_acceptance = _boundary_evidence(
        clean,
        clean_facts,
        decision="defer_cohesive",
        target="lib/src/core",
        boundary_name="core",
    )
    _invoke(BOUNDARY, clean, boundary_evidence, boundary_acceptance, "defer")
    boundary = _inspection(clean, "propose-boundary", "defer")
    assert boundary["status"] == "deferred"
    assert boundary["recommendation"] == "defer_cohesive_target"
    assert boundary["exact_edits"] == [] and boundary["create_files"] == []
    assert boundary["native_verification"]["current_tree"]["status"] == "passed"

    positive = _copy_fixture(tmp_path, "positive")
    positive_facts = _facts(positive, POSITIVE_QUERIES)
    d1 = _d1_findings(positive)
    folder_evidence, folder_acceptance = _folder_evidence(
        positive, positive_facts, d1, decision="cohesive"
    )
    _invoke(FOLDER, positive, folder_evidence, folder_acceptance, "defer")
    folder = _inspection(positive, "propose-folder-reorganization", "defer")
    assert folder["status"] == "deferred"
    assert folder["recommendation"] == "defer_cohesive_cluster"
    assert folder["exact_moves"] == [] and folder["exact_edits"] == []
    assert folder["native_verification"]["current_tree"]["status"] == "passed"

    absent_evidence, absent_acceptance = _folder_evidence(
        positive,
        positive_facts,
        d1,
        decision="split",
        convention=None,
    )
    _invoke(FOLDER, positive, absent_evidence, absent_acceptance, "absent-convention")
    absent = _inspection(positive, "propose-folder-reorganization", "absent-convention")
    assert absent["status"] == "deferred"
    assert absent["recommendation"] == "defer_project_convention_required"
    assert absent["exact_moves"] == []


@pytest.mark.parametrize(
    ("script", "family"),
    [(BOUNDARY, "propose-boundary"), (FOLDER, "propose-folder-reorganization")],
)
def test_stale_refusal_replaces_ready_and_recovers_at_same_destination(
    script: Path, family: str, tmp_path: Path
) -> None:
    host = _copy_fixture(tmp_path, "positive")
    facts = _facts(host, POSITIVE_QUERIES)
    if script == BOUNDARY:
        evidence, acceptance = _boundary_evidence(host, facts)
    else:
        evidence, acceptance = _folder_evidence(host, facts, _d1_findings(host))
    _invoke(script, host, evidence, acceptance, "reuse")
    assert _inspection(host, family, "reuse")["status"] == "ready_for_human_review"
    (host / f"reports/{family}/reuse/stale.json").write_text("{}\n", encoding="utf-8")

    changed = host / "lib/src/checkout.dart"
    original = changed.read_text(encoding="utf-8")
    changed.write_text(f"{original}\n", encoding="utf-8")
    _invoke(script, host, evidence, acceptance, "reuse", expected=2)
    refused = _inspection(host, family, "reuse")
    assert refused["status"] == "failed"
    assert refused["failure_kind"] == "stale_accepted_evidence"
    assert refused.get("exact_moves", []) == []
    assert refused.get("exact_edits", []) == []
    assert not (host / f"reports/{family}/reuse/stale.json").exists()
    proposal = (host / f"reports/{family}/reuse/proposal.md").read_text()
    assert "Refusal" in proposal and "ready_for_human_review" not in proposal

    changed.write_text(original, encoding="utf-8")
    _invoke(script, host, evidence, acceptance, "reuse")
    assert _inspection(host, family, "reuse")["status"] == "ready_for_human_review"


def test_unaccepted_and_unresolved_evidence_never_yield_ready(tmp_path: Path) -> None:
    host = _copy_fixture(tmp_path, "positive")
    facts = _facts(host, POSITIVE_QUERIES)
    evidence, acceptance = _boundary_evidence(host, facts)
    envelope = json.loads(acceptance.read_text())
    envelope["human_verdict"]["status"] = "pending"
    envelope.pop("acceptance_hash")
    envelope["acceptance_hash"] = _canonical_hash(envelope)
    _write_json(acceptance, envelope)
    _invoke(BOUNDARY, host, evidence, acceptance, "unaccepted", expected=2)
    unaccepted = _inspection(host, "propose-boundary", "unaccepted")
    assert unaccepted["status"] == "partial"
    assert unaccepted["failure_kind"] == "human_acceptance_required"

    facts["status"] = "partial"
    facts["failure_kind"] = "semantic_boundary"
    facts.pop("fact_pack_sha256")
    facts["fact_pack_sha256"] = _canonical_hash(facts)
    evidence, acceptance = _boundary_evidence(host, facts)
    envelope = json.loads(acceptance.read_text())
    envelope["producer"]["terminal_status"] = "partial"
    envelope.pop("acceptance_hash")
    envelope["acceptance_hash"] = _canonical_hash(envelope)
    _write_json(acceptance, envelope)
    _invoke(BOUNDARY, host, evidence, acceptance, "partial", expected=2)
    partial = _inspection(host, "propose-boundary", "partial")
    assert partial["status"] == "partial"
    assert partial["failure_kind"] == "upstream_not_complete"


@pytest.mark.parametrize(
    ("script", "family"),
    [(BOUNDARY, "propose-boundary"), (FOLDER, "propose-folder-reorganization")],
)
def test_missing_native_tool_is_terminal_and_recoverable(
    script: Path, family: str, tmp_path: Path
) -> None:
    host = _copy_fixture(tmp_path, "positive")
    facts = _facts(host, POSITIVE_QUERIES)
    if script == BOUNDARY:
        evidence, acceptance = _boundary_evidence(host, facts)
    else:
        evidence, acceptance = _folder_evidence(host, facts, _d1_findings(host))
    _invoke(
        script,
        host,
        evidence,
        acceptance,
        "tool-reuse",
        expected=2,
        dart=tmp_path / "missing-dart",
    )
    failed = _inspection(host, family, "tool-reuse")
    assert failed["status"] == "failed"
    assert failed["failure_kind"] == "native_verification_failed"
    _invoke(script, host, evidence, acceptance, "tool-reuse")
    assert _inspection(host, family, "tool-reuse")["status"] == "ready_for_human_review"


def test_package_uri_cluster_impact_refuses_a_ready_move(tmp_path: Path) -> None:
    host = _copy_fixture(tmp_path, "positive")
    checkout = host / "lib/src/checkout.dart"
    text = checkout.read_text(encoding="utf-8")
    checkout.write_text(
        text.replace(
            "import 'billing_invoice.dart';",
            "import 'package:dart_d7_positive/src/billing_invoice.dart';",
        ),
        encoding="utf-8",
    )
    facts = _facts(host, POSITIVE_QUERIES)
    evidence, acceptance = _folder_evidence(host, facts, _d1_findings(host))
    _invoke(FOLDER, host, evidence, acceptance, "package-uri", expected=2)
    refused = _inspection(host, "propose-folder-reorganization", "package-uri")
    assert refused["status"] == "partial"
    assert refused["failure_kind"] == "public_package_uri_uncertainty"
    assert refused["exact_moves"] == []


def test_copied_on_demand_closures_run_without_repository_imports(tmp_path: Path) -> None:
    host = _copy_fixture(tmp_path, "positive")
    facts = _facts(host, POSITIVE_QUERIES)
    d1 = _d1_findings(host)
    inputs = {
        "propose-boundary": _boundary_evidence(host, facts),
        "propose-folder-reorganization": _folder_evidence(host, facts, d1),
    }
    scripts = {"propose-boundary": BOUNDARY, "propose-folder-reorganization": FOLDER}
    install = tmp_path / "installed/.agents/skills"
    for skill, source in scripts.items():
        destination = install / skill / "scripts" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        shutil.copy2(VALIDATOR, destination.with_name("dart_accepted_evidence.py"))
        evidence, acceptance = inputs[skill]
        _invoke(destination, host, evidence, acceptance, f"copied-{skill}")
        assert _inspection(host, skill, f"copied-{skill}")["status"] == "ready_for_human_review"
        assert str(ROOT) not in destination.read_text(encoding="utf-8")


def test_unify_shadows_remains_stopped_without_accepted_d5_finding() -> None:
    text = DUPLICATION.read_text(encoding="utf-8")
    assert "accepted_provider_fact_gap" in text
    assert "callHierarchy/outgoingCalls" in text
    assert not (ROOT / ".claude/skills/unify-shadows/scripts/propose_dart.py").exists()
