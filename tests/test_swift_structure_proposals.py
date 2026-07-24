"""Accepted, refused, copied, and independently replayed Swift structure proposals."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python")  # host-ref-allow: task-pinned product runtime
SWIFT = Path("/usr/bin/swift")
SWIFTC = Path("/usr/bin/swiftc")
SWIFT_FORMAT = Path("/Library/Developer/CommandLineTools/usr/bin/swift-format")
BASE = ROOT / "tests/fixtures/swift-semantic-a3/host"
OVERLAY = ROOT / "tests/fixtures/swift-structure-proposals/overlay"
SKILLS = ROOT / ".claude/skills"
PROVIDER = SKILLS / "_swift-semantic-readonly/swift_semantic_facts.py"
HELPER = SKILLS / "_swift-semantic-readonly/swift_structure_proposals.py"
BOUNDARY = SKILLS / "propose-boundary/scripts/propose_swift.py"
FOLDER = SKILLS / "propose-folder-reorganization/scripts/propose_swift.py"
OMNIBUS_SKILL = SKILLS / "find-omnibus"
TOPOLOGY = SKILLS / "find-folder-topology-drift/scripts/detect_swift.py"
TARGET = "SwiftA3Core"
TARGET_ROOT = "Sources/SwiftA3Core"
CHECK_PRODUCT = "swift-a3-check"
CHECK_OUTPUT = "swift-a3-checks-ok"
SMOKE_PRODUCT = "swift-a3-smoke"
SMOKE_OUTPUT = "swift-a3:42"
QUERIES = [
    "BillingKind",
    "BillingModel",
    "BillingParser",
    "BillingValidator",
    "DomainOperations",
    "accepts",
    "exportSurface",
    "loadExports",
    "parse",
    "renderExports",
    "saveExports",
    "total",
]
BOUNDARY_GATES = {
    "abi": "not_claimed_separate_release_approval",
    "compatibility": "three_original_public_static_signatures_retained_as_shims",
    "dynamic_reflection": "none_selected",
    "external_callers": "none",
    "macro_conditional_compilation": "none_selected",
    "module_identity": "SwiftA3Core_unchanged",
    "new_boundary": "internal_ExportOperations",
    "protocol_actor_dispatch": "none_selected",
    "resolved_callers": "accepted_exact_and_unchanged",
    "runtime_behavior": "native_check_and_smoke_only",
    "xcode_mixed_language": "none",
}
FOLDER_GATES = {
    "abi": "not_claimed_separate_release_approval",
    "api_identity": "unchanged",
    "dynamic_reflection": "none_selected",
    "external_callers": "none",
    "macro_conditional_compilation": "none_selected",
    "module_identity": "SwiftA3Core_unchanged",
    "package_manifest": "unchanged",
    "project_convention": "swiftpm_recursive_target_subfolders",
    "protocol_actor_dispatch": "none_selected",
    "resolved_callers_references": "accepted_exact_logical_edges_unchanged",
    "runtime_behavior": "native_check_and_smoke_only",
    "target_identity": "name_type_path_dependencies_unchanged",
    "type_identity": "module_qualified_names_unchanged",
    "xcode_mixed_language": "none",
}

pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (PYTHON, SWIFT, SWIFTC, SWIFT_FORMAT)),
    reason="the frozen Python and Apple Swift 6.3.3 toolchain are required",
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


def _write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(BASE, host)
    shutil.copytree(OVERLAY, host, dirs_exist_ok=True)
    return host


def _state(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): _sha(path)
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not any(
            part in {".build", ".git", ".swiftpm", "reports"}
            for part in path.relative_to(host).parts
        )
    }


def _facts(host: Path, label: str, *, swift: Path = SWIFT) -> Path:
    output = host / f"reports/swift-semantic-facts/{label}.json"
    argv: list[str | Path] = [
        PYTHON,
        "-I",
        "-S",
        PROVIDER,
        "--project-root",
        host,
        "--target-name",
        TARGET,
        "--configuration",
        "debug",
        "--output",
        output,
        "--swift",
        swift,
        "--swiftc",
        SWIFTC,
        "--swift-format",
        SWIFT_FORMAT,
        "--check-product",
        CHECK_PRODUCT,
        "--expected-check",
        CHECK_OUTPUT,
        "--smoke-product",
        SMOKE_PRODUCT,
        "--expected-smoke",
        SMOKE_OUTPUT,
    ]
    for query in QUERIES:
        argv.extend(("--query", query))
    _run(*argv, cwd=host)
    assert _json(output)["status"] == "complete"
    return output


def _omnibus(host: Path) -> Path:
    report = host / "reports/omnibus/swift"
    detected = report / "omnibus.jsonl"
    _run(
        PYTHON,
        "-I",
        "-S",
        OMNIBUS_SKILL / "scripts/detect.py",
        "--target",
        host / TARGET_ROOT / "StructureEvidence",
        "--project-root",
        host,
        "--output",
        detected,
        "--language",
        "swift",
        cwd=host,
    )
    candidates = report / "candidates.jsonl"
    _run(
        PYTHON,
        "-I",
        "-S",
        OMNIBUS_SKILL / "scripts/collapse.py",
        "--detections",
        detected,
        "--output",
        candidates,
        cwd=host,
    )
    candidate = json.loads(candidates.read_text(encoding="utf-8").splitlines()[0])
    scout = report / "scout" / f"{candidate['candidate_id']}.json"
    _write(
        scout,
        {
            "bucket": "confirmed_omnibus",
            "candidate_id": candidate["candidate_id"],
            "decomposition_depth_note": "Each domain has a separate public static surface.",
            "decomposition_sketch": [],
            "domains_confirmed": ["customers", "exports", "notifications", "payments"],
            "false_positive_reason": None,
            "file": candidate["file"],
            "notes": "The exact Swift structure fixture was reviewed.",
            "recommendation": "decompose",
            "srp_rewrite": "DomainOperations owns four independent static operation domains.",
        },
    )
    output = report / "findings.json"
    _run(
        PYTHON,
        "-I",
        "-S",
        OMNIBUS_SKILL / "scripts/report.py",
        "--candidates",
        candidates,
        "--scout-dir",
        scout.parent,
        "--output-md",
        report / "report.md",
        "--output-json",
        output,
        "--scan-id",
        "swift-structure-proposals",
        "--target",
        TARGET_ROOT,
        cwd=host,
    )
    assert _json(output)["status"] == "complete"
    return output


def _topology(host: Path) -> Path:
    report = host / "reports/topology/swift"
    _run(
        PYTHON,
        "-I",
        "-S",
        TOPOLOGY,
        "--project-root",
        host,
        "--swift-root",
        TARGET_ROOT,
        "--min-cluster-size",
        "4",
        "--output",
        report / "detections.jsonl",
        "--swift",
        SWIFT,
        "--swiftc",
        SWIFTC,
        "--swift-format",
        SWIFT_FORMAT,
        "--check-product",
        CHECK_PRODUCT,
        "--expected-check",
        CHECK_OUTPUT,
        "--smoke-product",
        SMOKE_PRODUCT,
        "--expected-smoke",
        SMOKE_OUTPUT,
        cwd=host,
    )
    output = report / "findings.json"
    assert _json(output)["outcome"] == "drift-found"
    return output


def _target_row(facts: dict[str, Any]) -> dict[str, Any]:
    return next(row for row in facts["target_graph"] if row["name"] == TARGET)


def _logical(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_name": row["display_name"],
        "interface_type": row["interface_type"],
        "kind": row["kind"],
        "name": row["name"],
        "parent": row["parent"],
        "top_level": row["top_level"],
    }


def _boundary_selection(host: Path, omnibus: Path, facts_path: Path) -> dict[str, Any]:
    producer = _json(omnibus)
    facts = _json(facts_path)
    finding = producer["findings"][0]
    candidate = finding["candidate"]
    cluster = next(row for row in candidate["clusters"] if row["name"] == "exports")
    names = {name.split(".")[-1] for name in cluster["symbols"]}
    declarations = [
        row
        for row in facts["compiler_details"]["all_declarations"]
        if row["file"] == candidate["file"]
        and row["parent"] == "DomainOperations"
        and row["name"] in names
    ]
    assert len(declarations) == 3
    source = host / candidate["file"]
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    blocks = [
        {"line": row["line"], "path": row["file"], "text": lines[row["line"] - 1]}
        for row in declarations
    ]
    edits = [
        {
            "after": (
                f"  public static func {row['name']}() -> Int "
                f"{{ ExportOperations.{row['name']}() }}\n"
            ),
            "before": block["text"],
            "expected_occurrences": 1,
            "path": row["file"],
        }
        for row, block in zip(declarations, blocks, strict=True)
    ]
    bodies = [block["text"].split("{", 1)[1].rsplit("}", 1)[0].strip() for block in blocks]
    new_path = f"{TARGET_ROOT}/StructureEvidence/ExportOperations.swift"
    contents = "internal enum ExportOperations {\n" + "".join(
        f"  internal static func {row['name']}() -> Int {{ {body} }}\n"
        for row, body in zip(declarations, bodies, strict=True)
    ) + "}\n"
    symbol_ids = {row["semantic_id"] for row in declarations}
    callers = [
        row
        for row in facts["compiler_details"]["resolved_calls"]
        if row["target_semantic_id"] in symbol_ids
    ]
    assert len(callers) == 3
    target_sources = sorted([*_target_row(facts)["sources"], "StructureEvidence/ExportOperations.swift"])
    return {
        "api_impact": {
            "compatibility_shims": True,
            "existing_public_signatures_changed": False,
            "new_type": "SwiftA3Core.ExportOperations",
            "new_type_access": "internal",
        },
        "caller_impact": callers,
        "candidate_id": candidate["candidate_id"],
        "create_files": [{"contents": contents, "path": new_path}],
        "declarations": declarations,
        "domain": "exports",
        "exact_edits": edits,
        "exact_moves": [],
        "module_impact": {"after": TARGET, "before": TARGET, "changed": False},
        "package_impact": {
            "manifest_changed": False,
            "package_sha256": _sha(host / "Package.swift"),
        },
        "source_blocks": blocks,
        "target": candidate["file"],
        "target_sources_after": target_sources,
        "test_surface": [
            "Sources/SwiftA3Check/main.swift",
            "Sources/SwiftA3Smoke/main.swift",
        ],
    }


def _folder_selection(host: Path, topology: Path, facts_path: Path) -> dict[str, Any]:
    facts = _json(facts_path)
    finding = next(row for row in _json(topology)["findings"] if row["prefix"] == "Billing")
    files = finding["files"]
    replacements = {
        path: f"{TARGET_ROOT}/Billing/{Path(path).name}"
        for path in files
    }
    declarations = [
        row
        for row in facts["compiler_details"]["all_declarations"]
        if row["file"] in set(files)
    ]
    symbol_ids = {row["semantic_id"] for row in declarations}
    callers = [
        row
        for row in facts["compiler_details"]["resolved_calls"]
        if row["target_semantic_id"] in symbol_ids
    ]
    references = [
        row
        for row in facts["compiler_details"]["resolved_references"]
        if row["target_semantic_id"] in symbol_ids
    ]
    target_sources = sorted(
        f"Billing/{Path(path).name}" if f"{TARGET_ROOT}/{path}" in replacements else path
        for path in _target_row(facts)["sources"]
    )
    return {
        "api_impact": {
            "logical_declarations": sorted(
                (_logical(row) for row in declarations), key=lambda row: _canonical(row)
            ),
            "public_signatures_changed": False,
            "source_location_only": True,
        },
        "caller_impact": callers,
        "create_files": [],
        "declarations": declarations,
        "exact_edits": [],
        "exact_moves": [
            {"from": source, "to": destination}
            for source, destination in replacements.items()
        ],
        "files": files,
        "finding_evidence_sha256": finding["evidence_sha256"],
        "module_impact": {"after": TARGET, "before": TARGET, "changed": False},
        "package_impact": {
            "manifest_changed": False,
            "package_sha256": _sha(host / "Package.swift"),
        },
        "parent": finding["file"],
        "prefix": "Billing",
        "project_convention": "swiftpm-recursive-target-subfolders",
        "reference_impact": references,
        "target_identity_impact": {
            "dependencies": _target_row(facts)["target_dependencies"],
            "name": TARGET,
            "path": TARGET_ROOT,
            "type": "library",
            "changed": False,
        },
        "target_sources_after": target_sources,
        "test_surface": [
            "Sources/SwiftA3Check/main.swift",
            "Sources/SwiftA3Smoke/main.swift",
        ],
        "type_identity_impact": {
            "module": TARGET,
            "qualified_types": sorted(
                row["name"] for row in declarations if row["kind"] in {5, 10, 11, 23}
            ),
            "changed": False,
        },
    }


def _producer_candidate(consumer: str, producer: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    if consumer == "propose-boundary":
        return next(
            row for row in producer["findings"]
            if row["candidate"]["candidate_id"] == selection["candidate_id"]
        )
    return next(
        row for row in producer["findings"]
        if row["evidence_sha256"] == selection["finding_evidence_sha256"]
    )


def _acceptance(
    host: Path,
    *,
    consumer: str,
    script: Path,
    producer: Path,
    facts_path: Path,
    selection: dict[str, Any],
    gates: dict[str, str],
    swift: Path = SWIFT,
) -> Path:
    producer_payload = _json(producer)
    facts = _json(facts_path)
    candidate_material = {
        "consumer": consumer,
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "producer_candidate": _producer_candidate(consumer, producer_payload, selection),
    }
    candidate_verdict: dict[str, Any] = {
        "candidate_sha256": _canonical(candidate_material),
        "notes": "The exact upstream candidate and current compiler fact closure were reviewed.",
        "reviewer": "swift-structure-fixture-owner",
        "schema_version": "swift-structure-candidate-verdict-v1",
        "status": "accepted",
    }
    candidate_verdict["candidate_verdict_sha256"] = _canonical(candidate_verdict)
    proposal_verdict: dict[str, Any] = {
        "boundary_verdicts": gates,
        "candidate_verdict_sha256": candidate_verdict["candidate_verdict_sha256"],
        "notes": "The exact read-only proposal and every named nonclaim were reviewed.",
        "proposal_sha256": _canonical(selection),
        "reviewer": "swift-structure-fixture-owner",
        "schema_version": "swift-structure-proposal-verdict-v1",
        "status": "accepted",
    }
    proposal_verdict["proposal_verdict_sha256"] = _canonical(proposal_verdict)
    payload: dict[str, Any] = {
        "artifacts": [
            {
                "kind": "confirmed-omnibus"
                if consumer == "propose-boundary"
                else "lexical-topology",
                "path": producer.relative_to(host).as_posix(),
                "sha256": _sha(producer),
            },
            {
                "kind": "swift-semantic-facts-v2",
                "path": facts_path.relative_to(host).as_posix(),
                "sha256": _sha(facts_path),
            },
        ],
        "authority": {
            "selected_skill_sha256": _sha(script),
            "semantic_provider_sha256": _sha(PROVIDER),
            "structure_helper_sha256": _sha(HELPER),
            "swift_format_sha256": _sha(SWIFT_FORMAT.resolve()),
            "swift_sha256": _sha(swift.resolve()),
            "swiftc_sha256": _sha(SWIFTC.resolve()),
            "toolchain_sha256": facts["identity"]["toolchain_sha256"],
        },
        "candidate_verdict": candidate_verdict,
        "consumer": consumer,
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "language": "swift",
        "proposal_verdict": proposal_verdict,
        "schema_version": "swift-structure-acceptance-v1",
        "selection": selection,
        "source_manifest_sha256": facts["source_manifest_sha256"],
        "target_name": TARGET,
    }
    payload["acceptance_sha256"] = _canonical(payload)
    return _write(host / f"reports/accepted/{consumer}/acceptance.json", payload)


def _invoke(
    script: Path,
    host: Path,
    producer: Path,
    facts: Path,
    acceptance: Path,
    name: str,
    *,
    expected: int = 0,
    swift: Path = SWIFT,
    output: Path | None = None,
) -> Path:
    consumer = script.parents[1].name
    producer_flag = "--omnibus" if consumer == "propose-boundary" else "--topology"
    destination = output or host / f"reports/{consumer}/swift/{name}"
    _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        producer_flag,
        producer.relative_to(host),
        "--facts",
        facts.relative_to(host),
        "--acceptance",
        acceptance.relative_to(host),
        "--output-dir",
        destination if destination.is_absolute() else destination.relative_to(host),
        "--target-name",
        TARGET,
        "--configuration",
        "debug",
        "--swift",
        swift,
        "--swiftc",
        SWIFTC,
        "--swift-format",
        SWIFT_FORMAT,
        "--check-product",
        CHECK_PRODUCT,
        "--expected-check",
        CHECK_OUTPUT,
        "--smoke-product",
        SMOKE_PRODUCT,
        "--expected-smoke",
        SMOKE_OUTPUT,
        cwd=host,
        expected=expected,
    )
    return destination


def _apply_scope(root: Path, scope: dict[str, Any]) -> None:
    for row in scope["exact_moves"]:
        destination = root / row["to"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        (root / row["from"]).replace(destination)
    for row in scope["exact_edits"]:
        path = root / row["path"]
        text = path.read_text(encoding="utf-8")
        assert text.count(row["before"]) == row["expected_occurrences"]
        path.write_text(text.replace(row["before"], row["after"]), encoding="utf-8")
    for row in scope["create_files"]:
        path = root / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["contents"], encoding="utf-8")


def _rehash_verdict(path: Path, verdict: str, mutate: Callable[[dict[str, Any]], None]) -> None:
    payload = _json(path)
    mutate(payload[verdict])
    hash_field = f"{verdict}_sha256"
    payload[verdict].pop(hash_field, None)
    payload[verdict][hash_field] = _canonical(payload[verdict])
    payload.pop("acceptance_sha256")
    payload["acceptance_sha256"] = _canonical(payload)
    _write(path, payload)


def _native_outputs(facts: dict[str, Any]) -> tuple[str, str]:
    checks = {row["id"]: row for row in facts["native_checks"]}
    return checks["direct-check"]["stdout"].strip(), checks["executable-smoke"]["stdout"].strip()


def test_swift_structure_proposals_reach_accepted_copied_and_independent_outcomes(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    omnibus = _omnibus(host)
    topology = _topology(host)
    facts = _facts(host, "structure")
    boundary_acceptance = _acceptance(
        host,
        consumer="propose-boundary",
        script=BOUNDARY,
        producer=omnibus,
        facts_path=facts,
        selection=_boundary_selection(host, omnibus, facts),
        gates=BOUNDARY_GATES,
    )
    folder_acceptance = _acceptance(
        host,
        consumer="propose-folder-reorganization",
        script=FOLDER,
        producer=topology,
        facts_path=facts,
        selection=_folder_selection(host, topology, facts),
        gates=FOLDER_GATES,
    )
    before = _state(host)

    cases = (
        (BOUNDARY, omnibus, boundary_acceptance, "boundary"),
        (FOLDER, topology, folder_acceptance, "folder"),
    )
    for script, producer, acceptance, label in cases:
        output = _invoke(script, host, producer, facts, acceptance, "accepted")
        assert {path.name for path in output.iterdir()} == {
            "evidence.json",
            "proposal.md",
            "scope.json",
        }
        evidence = _json(output / "evidence.json")
        scope = _json(output / "scope.json")
        assert evidence["status"] == "ready_for_human_review"
        assert evidence["native_verification"]["current_tree"]["status"] == "complete"
        assert evidence["native_verification"]["disposable_after_tree"]["status"] == (
            "complete"
        )
        assert evidence["source_preservation"] == {"verified": True}
        assert evidence["evidence_binding"]["fact_pack_sha256"] == _json(facts)[
            "fact_pack_sha256"
        ]
        assert scope["read_only"] is True and scope["mutation_authorized"] is False
        assert _state(host) == before

        if label == "boundary":
            assert len(scope["declarations"]) == len(scope["caller_impact"]) == 3
            assert len(scope["exact_edits"]) == 3
            assert scope["create_files"][0]["contents"].startswith(
                "internal enum ExportOperations"
            )
        else:
            assert len(scope["exact_moves"]) == 4
            assert all("/Billing/Billing" in row["to"] for row in scope["exact_moves"])
            assert scope["package_impact"]["manifest_changed"] is False

        independent = _host(tmp_path, f"independent-{label}")
        _apply_scope(independent, scope)
        independent_facts = _facts(independent, f"after-{label}")
        assert _native_outputs(_json(independent_facts)) == (CHECK_OUTPUT, SMOKE_OUTPUT)

        installed = tmp_path / f"installed-{label}/.claude/skills"
        copied_skill = installed / script.parents[1].name
        copied_helper = installed / "_swift-semantic-readonly"
        shutil.copytree(script.parents[1], copied_skill)
        shutil.copytree(SKILLS / "_swift-semantic-readonly", copied_helper)
        copied = copied_skill / "scripts/propose_swift.py"
        copied_output = _invoke(copied, host, producer, facts, acceptance, "copied")
        assert _json(copied_output / "evidence.json")["status"] == (
            "ready_for_human_review"
        )
        combined = copied.read_text(encoding="utf-8") + (
            copied_helper / "swift_structure_proposals.py"
        ).read_text(encoding="utf-8")
        assert "SourceKit" not in combined
        assert "map-subsystem" not in combined
        assert "detect_swift" not in combined
        assert str(ROOT) not in combined


def test_swift_structure_proposals_refuse_claim_free_and_recover_same_destination(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    omnibus = _omnibus(host)
    facts = _facts(host, "structure")
    acceptance = _acceptance(
        host,
        consumer="propose-boundary",
        script=BOUNDARY,
        producer=omnibus,
        facts_path=facts,
        selection=_boundary_selection(host, omnibus, facts),
        gates=BOUNDARY_GATES,
    )
    original = acceptance.read_bytes()
    original_producer = omnibus.read_bytes()
    destination = _invoke(BOUNDARY, host, omnibus, facts, acceptance, "lifecycle")
    assert _json(destination / "evidence.json")["status"] == "ready_for_human_review"

    _rehash_verdict(
        acceptance,
        "proposal_verdict",
        lambda row: row["boundary_verdicts"].update(abi="unknown"),
    )
    refused = _invoke(
        BOUNDARY,
        host,
        omnibus,
        facts,
        acceptance,
        "lifecycle",
        expected=2,
    )
    assert {path.name for path in refused.iterdir()} == {
        "evidence.json",
        "proposal.md",
        "scope.json",
    }
    evidence = _json(refused / "evidence.json")
    scope = _json(refused / "scope.json")
    assert evidence["failure_kind"] == "swift_boundary_unresolved"
    assert "native_verification" not in evidence
    assert scope["declarations"] == scope["caller_impact"] == scope["reference_impact"] == []
    assert scope["exact_moves"] == scope["exact_edits"] == scope["create_files"] == []

    acceptance.write_bytes(original)
    recovered = _invoke(BOUNDARY, host, omnibus, facts, acceptance, "lifecycle")
    assert _json(recovered / "evidence.json")["status"] == "ready_for_human_review"

    producer = _json(omnibus)
    producer["scan_id"] = "tampered"
    _write(omnibus, producer)
    stale = _invoke(
        BOUNDARY,
        host,
        omnibus,
        facts,
        acceptance,
        "stale",
        expected=2,
    )
    assert _json(stale / "evidence.json")["failure_kind"] == "artifact_hash_mismatch"
    assert _json(stale / "scope.json")["declarations"] == []

    omnibus.write_bytes(original_producer)
    producer = _json(omnibus)
    producer.update(status="partial", outcome="incomplete")
    _write(omnibus, producer)
    accepted = _json(acceptance)
    next(row for row in accepted["artifacts"] if row["kind"] == "confirmed-omnibus")[
        "sha256"
    ] = _sha(omnibus)
    accepted.pop("acceptance_sha256")
    accepted["acceptance_sha256"] = _canonical(accepted)
    _write(acceptance, accepted)
    incomplete = _invoke(
        BOUNDARY,
        host,
        omnibus,
        facts,
        acceptance,
        "incomplete",
        expected=2,
    )
    assert _json(incomplete / "evidence.json")["failure_kind"] == (
        "upstream_not_complete"
    )
    assert _json(incomplete / "scope.json")["declarations"] == []


def test_swift_structure_proposals_refuse_unsupported_and_unsafe_conditions(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    source = host / TARGET_ROOT / "StructureEvidence/Omnibus.swift"
    source.write_text(
        source.read_text(encoding="utf-8")
        + "\npublic protocol UnsupportedBoundaryProtocol {}\n",
        encoding="utf-8",
    )
    omnibus = _omnibus(host)
    facts = _facts(host, "unsupported")
    acceptance = _acceptance(
        host,
        consumer="propose-boundary",
        script=BOUNDARY,
        producer=omnibus,
        facts_path=facts,
        selection=_boundary_selection(host, omnibus, facts),
        gates=BOUNDARY_GATES,
    )
    refused = _invoke(
        BOUNDARY,
        host,
        omnibus,
        facts,
        acceptance,
        "unsupported",
        expected=2,
    )
    assert _json(refused / "evidence.json")["failure_kind"] == (
        "unsupported_swift_condition"
    )
    assert _json(refused / "scope.json")["declarations"] == []

    outside = tmp_path / "outside"
    _invoke(
        BOUNDARY,
        host,
        omnibus,
        facts,
        acceptance,
        "unsafe",
        expected=2,
        output=outside,
    )
    assert not outside.exists()


def test_swift_structure_proposals_refuse_after_tree_native_failure(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    swift = tmp_path / "swift-after-fails"
    swift.write_text(
        "#!/bin/sh\n"
        "case \"$PWD\" in\n"
        "  */after) exit 9 ;;\n"
        "esac\n"
        "exec /usr/bin/swift \"$@\"\n",
        encoding="utf-8",
    )
    swift.chmod(0o755)
    omnibus = _omnibus(host)
    facts = _facts(host, "native-failure", swift=swift)
    acceptance = _acceptance(
        host,
        consumer="propose-boundary",
        script=BOUNDARY,
        producer=omnibus,
        facts_path=facts,
        selection=_boundary_selection(host, omnibus, facts),
        gates=BOUNDARY_GATES,
        swift=swift,
    )
    refused = _invoke(
        BOUNDARY,
        host,
        omnibus,
        facts,
        acceptance,
        "native-failure",
        expected=2,
        swift=swift,
    )
    evidence = _json(refused / "evidence.json")
    scope = _json(refused / "scope.json")
    assert evidence["failure_kind"] == "native_verification_failed"
    assert "native_verification" not in evidence
    assert scope["declarations"] == scope["caller_impact"] == []
    assert scope["exact_moves"] == scope["exact_edits"] == scope["create_files"] == []
