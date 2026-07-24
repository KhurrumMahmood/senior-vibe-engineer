"""Final-outcome proof for five bounded SDK/Roslyn C# semantic consumers."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python")  # host-ref-allow: frozen product runtime
DOTNET = shutil.which("dotnet")
FIXTURE = ROOT / "tests/fixtures/csharp-semantic-family/host"
SKILLS = ROOT / ".claude/skills"
COMMON = SKILLS / "_csharp-semantic"
PROVIDER = COMMON / "csharp_semantic_facts.py"
HELPER = COMMON / "CSharpSemanticFacts.cs"
SCRIPTS = {
    "dormant": SKILLS / "find-dormant/scripts/detect_csharp_dormant.py",
    "state": SKILLS / "find-implicit-state/scripts/detect_csharp_state.py",
    "sweep": SKILLS
    / "find-incomplete-sweep/scripts/detect_csharp_incomplete_sweep.py",
    "duplication": SKILLS
    / "find-semantic-duplication/scripts/detect_csharp_semantic.py",
    "rename": SKILLS / "rename-concept/scripts/assess_csharp_rename.py",
}
SKILL_NAMES = {
    "dormant": "find-dormant",
    "state": "find-implicit-state",
    "sweep": "find-incomplete-sweep",
    "duplication": "find-semantic-duplication",
    "rename": "rename-concept",
}
OUTPUTS = {
    "dormant": "reports/find-dormant/csharp/findings.json",
    "state": "reports/find-implicit-state/csharp/findings.json",
    "sweep": "reports/find-incomplete-sweep/csharp/manifest.json",
    "duplication": "reports/semantic-duplication/csharp/analysis.json",
    "rename": "reports/rename-concept/csharp/assessment.json",
}

pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or DOTNET is None,
    reason="product Python and the pinned .NET SDK are required",
)


def _run(*argv: str | Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "csharp-semantic-host"
    shutil.copytree(FIXTURE, host, ignore=shutil.ignore_patterns("reports"))
    return host


def _snapshot(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file() and "reports" not in path.relative_to(host).parts
    }


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _provider(
    host: Path,
    *,
    provider: Path = PROVIDER,
    dotnet: str | Path = str(DOTNET),
) -> subprocess.CompletedProcess[str]:
    return _run(
        PYTHON,
        "-I",
        "-S",
        provider,
        "--project-root",
        host,
        "--manifest",
        "csharp-semantic-project.json",
        "--output",
        "reports/csharp-semantic/facts.json",
        "--dotnet",
        dotnet,
        cwd=host,
    )


def _consumer(
    host: Path, kind: str, *, script: Path | None = None
) -> subprocess.CompletedProcess[str]:
    argv: list[str | Path] = [PYTHON, "-I", "-S", script or SCRIPTS[kind]]
    if kind == "rename":
        argv.extend(["LegacyStatus", "CanonicalStatus"])
    argv.extend(
        [
            "--project-root",
            host,
            "--facts",
            "reports/csharp-semantic/facts.json",
        ]
    )
    return _run(*argv, cwd=host)


def _outcome(host: Path, kind: str) -> dict:
    return _payload(host / OUTPUTS[kind])


def _assert_expected_outcome(host: Path, kind: str) -> None:
    payload = _outcome(host, kind)
    assert payload["status"] == "complete"
    assert payload["language"] == "csharp"
    assert payload["read_only"] is True
    assert Path(host / OUTPUTS[kind]).with_suffix(".md").is_file()
    if kind == "dormant":
        assert [row["symbol_id"] for row in payload["candidates"]] == [
            "M:CSharpSemantic.SemanticCases.DormantAdjustment(System.Int32)"
        ]
        assert payload["candidates"][0]["certain_delete"] is False
    elif kind == "state":
        assert [row["symbol_id"] for row in payload["candidates"]] == [
            "P:CSharpSemantic.Job.Status"
        ]
        assert payload["candidates"][0]["literals"] == [
            "done",
            "queued",
            "running",
        ]
        assert payload["candidates"][0]["automatic_migration"] is False
    elif kind == "sweep":
        assert [
            (row["parameter"], row["group_size"], row["with_parameter_count"])
            for row in payload["findings"]
        ] == [("Audit", 3, 2)]
        assert payload["findings"][0]["straggler"]["source"] == "new()"
    elif kind == "duplication":
        assert len(payload["leads"]) == 1
        assert [
            row["symbol_id"] for row in payload["leads"][0]["functions"]
        ] == [
            "M:CSharpSemantic.SemanticCases.SummarizeAlpha(System.Int32)",
            "M:CSharpSemantic.SemanticCases.SummarizeBeta(System.Int32)",
        ]
        assert "do not prove behavioral equivalence" in payload["leads"][0][
            "boundary"
        ]
    else:
        assert payload["verdict"] == "HALF-APPLIED / INCOMPLETE"
        assert payload["assess_only"] is True
        assert payload["source_mutated"] is False
        assert [row["symbol_id"] for row in payload["old_source_declarations"]] == [
            "T:CSharpSemantic.LegacyStatus"
        ]
        assert [row["symbol_id"] for row in payload["new_source_declarations"]] == [
            "T:CSharpSemantic.CanonicalStatus"
        ]
        assert payload["old_resolved_references"]
        assert payload["new_resolved_references"]
        assert {row["kind"] for row in payload["boundary_evidence"]} >= {
            "reflection_or_runtime_name_lookup",
            "excluded_generated_input",
            "excluded_vendor_input",
            "partial_declaration",
            "override_dispatch",
            "delegate_or_method_group",
        }


def test_csharp_semantic_pack_reaches_five_read_only_final_outcomes(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    before = _snapshot(host)
    collected = _provider(host)
    assert collected.returncode == 0, collected.stdout + collected.stderr
    facts = _payload(host / "reports/csharp-semantic/facts.json")
    assert facts["status"] == "complete"
    assert facts["semantic_authority"] == {
        "code_analysis_assembly": (
            "Microsoft.CodeAnalysis, Version=5.6.0.0, Culture=neutral, "
            "PublicKeyToken=31bf3856ad364e35"
        ),
        "helper_sha256": hashlib.sha256(HELPER.read_bytes()).hexdigest(),
        "kind": "sdk-bundled-roslyn-after-direct-csc-native-gates",
        "provider_sha256": hashlib.sha256(PROVIDER.read_bytes()).hexdigest(),
        "roslyn_assembly": (
            "Microsoft.CodeAnalysis.CSharp, Version=5.6.0.0, Culture=neutral, "
            "PublicKeyToken=31bf3856ad364e35"
        ),
        "runtime_version": "10.0.10",
        "sdk_version": "10.0.302",
    }
    assert facts["tools"]["csc"]["sha256"] == (
        "c5a2ff87882ad0c1b2e8d554ddf8d9eae1aa5d4d9b659f43a7c28d336ca2ba81"
    )
    assert [row["sha256"] for row in facts["tools"]["assemblies"]] == [
        "eabc44a97ca36c415af0d7a4db353c170fad26da897b11862927bdb3402f3786",
        "daff05fe558690b194b93e99d1299f2a85afba55c41fba5718dba6bdfd36bfe9",
    ]
    assert facts["tools"]["reference_pack"] == {
        "assembly_count": 167,
        "manifest_sha256": (
            "9719ee9a053103d3de4b3bfb91f230d9a58325f47e7ac90a2147649d288f2fdd"
        ),
        "path": facts["tools"]["reference_pack"]["path"],
    }
    assert len(facts["manifest_sha256"]) == 64
    assert len(facts["project_contract_sha256"]) == 64
    assert len(facts["source_manifest_sha256"]) == 64
    assert facts["commands"]["compile"]["returncode"] == 0
    assert facts["commands"]["compile_tests"]["returncode"] == 0
    assert facts["commands"]["test"]["stdout"] == "csharp-semantic-native-test:ok\n"
    assert facts["commands"]["smoke"]["stdout"] == "receipt:7:receipt:8:queued\n"
    assert facts["diagnostics"] == []
    assert facts["source_preservation"] == {"unchanged": True}

    roles = {row["path"]: row["role"] for row in facts["source_inventory"]}
    assert roles == {
        "generated/Generated.g.cs": "generated",
        "src/Semantics.cs": "source",
        "src/Smoke.cs": "source",
        "tests/SemanticTests.cs": "test",
        "vendor/Vendor.cs": "vendor",
    }
    boundary_kinds = {row["kind"] for row in facts["boundaries"]}
    assert boundary_kinds >= {
        "overload_set",
        "override_dispatch",
        "partial_declaration",
        "excluded_generated_input",
        "reflection_or_runtime_name_lookup",
        "delegate_or_method_group",
    }
    overload_targets = {
        row["target_signature"]
        for row in facts["calls"]
        if row["resolved"] and row["source"].startswith("processor.Process")
    }
    assert overload_targets == {
        "string CSharpSemantic.Processor.Process(int value)",
        "string CSharpSemantic.Processor.Process(string value)",
    }
    override = next(
        row
        for row in facts["declarations"]
        if row.get("symbol_id")
        == "M:CSharpSemantic.OverrideFormatter.Format(System.Int32)"
    )
    assert override["override"] is True
    assert override["overridden_symbol_id"] == (
        "M:CSharpSemantic.BaseFormatter.Format(System.Int32)"
    )
    assert any(
        row.get("signature") == "CSharpSemantic.PartialFeature" and row["partial"]
        for row in facts["declarations"]
    )

    for kind in SCRIPTS:
        result = _consumer(host, kind)
        assert result.returncode == 0, kind + result.stdout + result.stderr
        _assert_expected_outcome(host, kind)
    assert _snapshot(host) == before


def test_csharp_semantic_provider_and_consumers_replace_terminal_states(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    assert _provider(host).returncode == 0
    assert _payload(host / "reports/csharp-semantic/facts.json")["status"] == "complete"

    unavailable = _provider(host, dotnet=tmp_path / "missing-dotnet")
    assert unavailable.returncode == 2
    failed_facts = _payload(host / "reports/csharp-semantic/facts.json")
    assert failed_facts["status"] == "partial"
    assert failed_facts["failure_kind"] == "dotnet_unavailable"
    assert failed_facts["declarations"] == []

    assert _provider(host).returncode == 0
    source = host / "src/Semantics.cs"
    original = source.read_bytes()
    source.write_bytes(original + b"\nthis is not valid C#;\n")
    malformed = _provider(host)
    assert malformed.returncode == 1
    failed_facts = _payload(host / "reports/csharp-semantic/facts.json")
    assert failed_facts["status"] == "failed"
    assert failed_facts["failure_kind"] == "native_diagnostics_failed"
    assert failed_facts["declarations"] == []
    source.write_bytes(original)
    assert _provider(host).returncode == 0

    manifest = host / "csharp-semantic-project.json"
    manifest_bytes = manifest.read_bytes()
    manifest.write_bytes(manifest_bytes + b"\n")
    contract_stale = _consumer(host, "dormant")
    assert contract_stale.returncode == 2
    assert _outcome(host, "dormant")["deferred"] == [
        {"reason": "fact-pack-manifest-stale"}
    ]
    manifest.write_bytes(manifest_bytes)
    assert _consumer(host, "dormant").returncode == 0
    for kind in SCRIPTS:
        valid = _consumer(host, kind)
        assert valid.returncode == 0
        _assert_expected_outcome(host, kind)

        source.write_bytes(original + b"\n")
        stale = _consumer(host, kind)
        assert stale.returncode == 2
        partial = _outcome(host, kind)
        assert partial["status"] == "partial"
        assert partial["deferred"] == [{"reason": "fact-pack-stale"}]
        if kind in {"dormant", "state"}:
            assert partial["candidates"] == []
        elif kind == "sweep":
            assert partial["findings"] == []
        elif kind == "duplication":
            assert partial["leads"] == []
        else:
            assert partial["old_source_declarations"] == []
            assert partial["new_source_declarations"] == []
            assert partial["old_resolved_references"] == []
            assert partial["new_resolved_references"] == []

        source.write_bytes(original)
        restored = _consumer(host, kind)
        assert restored.returncode == 0
        _assert_expected_outcome(host, kind)


def test_csharp_semantic_family_runs_from_each_copied_external_library_closure(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path / "project")
    before = _snapshot(host)
    installed = tmp_path / "installed/.agents/skills"
    shutil.copytree(COMMON, installed / "_csharp-semantic")
    copied_scripts: dict[str, Path] = {}
    for kind, source in SCRIPTS.items():
        skill = installed / SKILL_NAMES[kind]
        script = skill / "scripts" / source.name
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, script)
        knowledge = SKILLS / SKILL_NAMES[kind] / "knowledge/csharp-v1.md"
        copied_knowledge = skill / "knowledge/csharp-v1.md"
        copied_knowledge.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(knowledge, copied_knowledge)
        copied_scripts[kind] = script

    collected = _provider(
        host, provider=installed / "_csharp-semantic/csharp_semantic_facts.py"
    )
    assert collected.returncode == 0, collected.stdout + collected.stderr
    for kind, script in copied_scripts.items():
        result = _consumer(host, kind, script=script)
        assert result.returncode == 0, kind + result.stdout + result.stderr
        _assert_expected_outcome(host, kind)
    assert _snapshot(host) == before
