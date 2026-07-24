"""Accepted, refused, copied, and native C# structure proposals."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
DOTNET = Path(shutil.which("dotnet") or "/nonexistent/dotnet").resolve()
BASE = ROOT / "tests/fixtures/csharp-lexical-syntax/host"
OVERLAY = ROOT / "tests/fixtures/csharp-structure-proposals/overlay"
SKILLS = ROOT / ".claude/skills"
MAP = SKILLS / "map-subsystem/scripts/map_csharp.py"
OMNIBUS = SKILLS / "find-omnibus/scripts/run_csharp.py"
TOPOLOGY = SKILLS / "find-folder-topology-drift/scripts/detect_csharp.py"
BOUNDARY = SKILLS / "propose-boundary/scripts/propose_csharp.py"
FOLDER = SKILLS / "propose-folder-reorganization/scripts/propose_csharp.py"
HELPER = SKILLS / "_csharp-semantic/csharp_structure_proposals.py"
PROJECTS = ("CSharpCohort.App.csproj", "CSharpCohort.Tests.csproj")
BOUNDARY_GATES = {
    "namespace_identity": "same_namespace",
    "assembly_identity": "same_app_and_test_assemblies",
    "public_api": "compatibility_shims_retained_new_type_reviewed",
    "abi": "not_claimed_separate_release_approval",
    "runtime_behavior": "native_test_and_smoke_only",
    "framework_registration": "none",
    "reflection_runtime_names": "none_selected",
    "delegates_method_groups": "none_selected",
    "override_interface_dispatch": "none_selected",
    "generated_vendor_inputs": "no_selected_dependency",
    "external_callers": "none",
    "conditional_build_variants": "none",
    "project_graph": "exact_two_dependency_free_projects",
}
FOLDER_GATES = {
    "project_convention": "group-four-same-prefix-csharp-siblings",
    "namespace_identity": "unchanged",
    "type_identity": "unchanged",
    "assembly_identity": "unchanged",
    "public_api": "unchanged_by_source_location",
    "abi": "not_claimed_separate_release_approval",
    "runtime_behavior": "native_test_and_smoke_only",
    "framework_registration": "none",
    "reflection_path_resource": "none_selected",
    "delegates_method_groups": "none_selected",
    "override_interface_dispatch": "none_selected",
    "generated_vendor_inputs": "no_selected_dependency",
    "external_callers": "none",
    "conditional_build_variants": "none",
    "project_graph": "exact_two_dependency_free_projects",
}

pytestmark = pytest.mark.skipif(
    not (PYTHON.is_file() and DOTNET.is_file()),
    reason="the frozen product Python and pinned .NET 10 SDK are required",
)


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int = 0,
    timeout: int = 300,
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


def _object_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _state(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): _sha(path)
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and not any(
            part in {"reports", ".native-build", ".engineering"}
            for part in path.relative_to(host).parts
        )
    }


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(BASE, host)
    shutil.copytree(OVERLAY, host, dirs_exist_ok=True)
    return host


def _producers(host: Path) -> tuple[Path, Path, Path, Path]:
    map_path = host / "reports/map/cohort/csharp-map.json"
    _run(
        PYTHON, "-I", "-S", MAP,
        "--name", "cohort", "--target", "src/CSharpCohort",
        "--project-root", ".",
        "--output", ".engineering/docs/subsystems/cohort.md",
        "--evidence", "reports/map/cohort/csharp-map.json",
        "--semantic-manifest", "csharp-semantic-project.json",
        "--dotnet", DOTNET, cwd=host,
    )
    assert _json(map_path)["status"] == "complete"
    facts = host / "reports/csharp-semantic/map-subsystem/cohort-facts.json"

    omnibus = host / "reports/omnibus/csharp/findings.json"
    _run(
        PYTHON, "-I", "-S", OMNIBUS, "--project-root", ".",
        "--dotnet", DOTNET, "--target", "src", "--output-dir",
        "reports/omnibus/csharp", "--scout-dir", "csharp-scouts", cwd=host,
    )
    assert _json(omnibus)["summary"] == {"confirmed_omnibus": 1}

    topology = host / "reports/folder/findings.json"
    _run(
        PYTHON, "-I", "-S", TOPOLOGY, "--project-root", ".",
        "--dotnet", DOTNET, "--csharp-root", "src/CSharpCohort",
        "--min-cluster-size", "3", "--output",
        "reports/folder/detections.jsonl", cwd=host,
    )
    assert _json(topology)["outcome"] == "drift-found"
    return omnibus, topology, map_path, facts


def _compile_paths(host: Path, project: str) -> list[str]:
    return [
        node.attrib["Include"]
        for node in ET.parse(host / project).getroot().findall(".//Compile")
    ]


def _manifests_after(
    host: Path, replacements: dict[str, str], additions: list[str] | None = None,
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for name in ("csharp-project.json", "csharp-semantic-project.json"):
        sources = [replacements.get(path, path) for path in _json(host / name)["sources"]]
        sources.extend(additions or [])
        result[name] = sources
    return result


def _projects_after(
    host: Path, replacements: dict[str, str], additions: list[str] | None = None,
) -> dict[str, list[str]]:
    result = {}
    for project in PROJECTS:
        paths = [replacements.get(path, path) for path in _compile_paths(host, project)]
        insertion = len(paths) - (1 if project.endswith("Tests.csproj") else 0)
        for path in additions or []:
            paths.insert(insertion, path)
            insertion += 1
        result[project] = paths
    return result


def _source_hashes(host: Path, facts: dict[str, Any]) -> list[dict[str, str]]:
    paths = {
        "csharp-project.json", "csharp-semantic-project.json", "global.json",
        "NuGet.Config", *PROJECTS,
        *(row["path"] for row in facts["source_inventory"]),
    }
    return [{"path": path, "sha256": _sha(host / path)} for path in sorted(paths)]


def _authority(script: Path, map_payload: dict[str, Any]) -> dict[str, Any]:
    semantic = map_payload["semantic_authority"]
    return {
        "selected_skill_sha256": _sha(script),
        "structure_helper_sha256": _sha(HELPER),
        "map_consumer_sha256": _sha(MAP),
        "lexical_helper_sha256": _sha(SKILLS / "_csharp/CSharpSyntaxFacts.cs"),
        "lexical_provider_sha256": _sha(SKILLS / "_csharp/csharp_facts.py"),
        "semantic_helper_sha256": _sha(SKILLS / "_csharp-semantic/CSharpSemanticFacts.cs"),
        "semantic_provider_sha256": _sha(SKILLS / "_csharp-semantic/csharp_semantic_facts.py"),
        "dotnet_sha256": semantic["dotnet_sha256"],
        "csc_sha256": semantic["csc_sha256"],
        "code_analysis_sha256": semantic["code_analysis_sha256"],
        "csharp_analysis_sha256": semantic["csharp_analysis_sha256"],
        "reference_pack_sha256": semantic["reference_pack_sha256"],
        "reference_count": semantic["reference_count"],
        "sdk_version": semantic["sdk_version"],
        "runtime_version": semantic["runtime_version"],
    }


def _acceptance(
    host: Path,
    *,
    consumer: str,
    script: Path,
    producer_kind: str,
    producer: Path,
    map_path: Path,
    facts_path: Path,
    selection: dict[str, Any],
    gates: dict[str, str],
) -> Path:
    map_payload = _json(map_path)
    facts = _json(facts_path)
    payload: dict[str, Any] = {
        "schema_version": "csharp-structure-acceptance-v1",
        "language": "csharp",
        "consumer": consumer,
        "artifacts": [
            {"kind": producer_kind, "path": producer.relative_to(host).as_posix(), "sha256": _sha(producer)},
            {"kind": "csharp-map", "path": map_path.relative_to(host).as_posix(), "sha256": _sha(map_path)},
            {"kind": "csharp-facts", "path": facts_path.relative_to(host).as_posix(), "sha256": _sha(facts_path)},
        ],
        "source_hashes": _source_hashes(host, facts),
        "authority": _authority(script, map_payload),
        "selection": selection,
        "candidate_verdict": {
            "status": "accepted",
            "reviewer": "csharp-structure-fixture-owner",
            "notes": "The exact current producer candidate and integrated semantic map were reviewed.",
        },
        "proposal_verdict": {
            "status": "accepted",
            "reviewer": "csharp-structure-fixture-owner",
            "notes": "The exact read-only proposal shape and all named boundaries were reviewed.",
            "boundary_verdicts": gates,
        },
    }
    payload["acceptance_sha256"] = _object_hash(payload)
    return _write(host / f"reports/accepted/{consumer}/acceptance.json", payload)


def _boundary_acceptance(host: Path, omnibus: Path, map_path: Path, facts: Path) -> Path:
    candidate = _json(omnibus)["findings"][0]
    mapped = _json(map_path)
    names = set(candidate["clusters"]["exports"])
    declarations = [
        row for row in mapped["qualified_declarations"]
        if f'{row["containing_type"]}.{row["name"]}' in names
    ]
    assert len(declarations) == 3
    symbol_ids = {row["symbol_id"] for row in declarations}
    source = host / candidate["file"]
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    source_blocks = [
        {"path": candidate["file"], "line": row["line"], "text": lines[row["line"] - 1]}
        for row in declarations
    ]
    exact_edits = [
        {
            "path": candidate["file"],
            "before": block["text"],
            "after": (
                f'    public static int {row["name"]}() => '
                f'ExportOperations.{row["name"]}();\n'
            ),
            "expected_occurrences": 1,
        }
        for row, block in zip(declarations, source_blocks, strict=True)
    ]
    new_path = "src/CSharpCohort/ExportOperations.cs"
    contents = (
        "namespace CSharpCohort;\n\npublic static class ExportOperations\n{\n"
        + "".join(block["text"] for block in source_blocks)
        + "}\n"
    )
    selection = {
        "candidate_id": candidate["candidate_id"],
        "target": candidate["file"],
        "domain": "exports",
        "declarations": declarations,
        "source_blocks": source_blocks,
        "caller_impact": [
            row for row in mapped["direct_resolved_calls"]
            if row["target_symbol_id"] in symbol_ids
        ],
        "namespace_impact": {"before": "CSharpCohort", "after": "CSharpCohort", "changed": False},
        "assembly_impact": {"projects": list(PROJECTS), "changed": False},
        "api_impact": {"compatibility_shims": True, "existing_public_signatures_changed": False, "new_public_type": "CSharpCohort.ExportOperations"},
        "abi_impact": {"claimed_compatible": False, "separate_release_approval_required": True},
        "runtime_impact": {"claimed_equivalent": False, "native_test_and_smoke_required": True},
        "exact_edits": exact_edits,
        "create_files": [{"path": new_path, "contents": contents}],
        "manifest_sources_after": _manifests_after(host, {}, [new_path]),
        "project_compile_after": _projects_after(host, {}, [new_path]),
        "test_surface": ["tests/CSharpCohortTests.cs", "src/CSharpCohort/Program.cs"],
    }
    return _acceptance(
        host, consumer="propose-boundary", script=BOUNDARY,
        producer_kind="confirmed-omnibus", producer=omnibus,
        map_path=map_path, facts_path=facts, selection=selection,
        gates=BOUNDARY_GATES,
    )


def _folder_acceptance(host: Path, topology: Path, map_path: Path, facts: Path) -> Path:
    finding = next(row for row in _json(topology)["findings"] if row["prefix"] == "Billing")
    mapped = _json(map_path)
    selected = set(finding["files"])
    replacements = {
        path: path.replace("/CSharpCohort/", "/CSharpCohort/Billing/")
        for path in finding["files"]
    }
    declarations = [row for row in mapped["qualified_declarations"] if row["path"] in selected]
    symbols = {row["symbol_id"] for row in declarations}
    selection = {
        "finding_evidence_sha256": finding["evidence_sha256"],
        "parent": finding["file"],
        "prefix": "Billing",
        "files": finding["files"],
        "project_convention": "group-four-same-prefix-csharp-siblings",
        "exact_moves": [{"from": source, "to": destination} for source, destination in replacements.items()],
        "declarations": declarations,
        "caller_impact": [
            row for row in mapped["direct_resolved_calls"]
            if row["target_symbol_id"] in symbols
        ],
        "reference_impact": [
            row for row in mapped["direct_resolved_references"]
            if row["target_symbol_id"] in symbols
        ],
        "namespace_impact": {"before": ["CSharpCohort"], "after": ["CSharpCohort"], "changed": False},
        "type_identity_impact": {
            "symbol_ids": sorted(row["symbol_id"] for row in declarations if row["kind"] in {"class", "record", "record-class", "struct", "interface", "enum"}),
            "changed": False,
        },
        "assembly_impact": {"projects": list(PROJECTS), "changed": False},
        "api_impact": {"public_signatures_changed": False, "source_location_only": True},
        "manifest_sources_after": _manifests_after(host, replacements),
        "project_compile_after": _projects_after(host, replacements),
        "test_surface": ["tests/CSharpCohortTests.cs", "src/CSharpCohort/Program.cs"],
    }
    return _acceptance(
        host, consumer="propose-folder-reorganization", script=FOLDER,
        producer_kind="lexical-topology", producer=topology,
        map_path=map_path, facts_path=facts, selection=selection,
        gates=FOLDER_GATES,
    )


def _invoke(
    script: Path, host: Path, producer: Path, map_path: Path, facts: Path,
    acceptance: Path, name: str, *, expected: int = 0,
) -> Path:
    skill = script.parents[1].name
    producer_flag = "--omnibus" if skill == "propose-boundary" else "--topology"
    output = host / f"reports/{skill}/csharp/{name}"
    _run(
        PYTHON, "-I", "-S", script, "--project-root", ".",
        producer_flag, producer.relative_to(host), "--map-evidence",
        map_path.relative_to(host), "--facts", facts.relative_to(host),
        "--acceptance", acceptance.relative_to(host), "--output-dir",
        output.relative_to(host), "--dotnet", DOTNET, cwd=host, expected=expected,
    )
    return output


def _apply_scope(root: Path, scope: dict[str, Any]) -> None:
    for row in scope.get("exact_moves", []):
        destination = root / row["to"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        (root / row["from"]).replace(destination)
    for row in scope.get("exact_edits", []):
        path = root / row["path"]
        text = path.read_text(encoding="utf-8")
        assert text.count(row["before"]) == row["expected_occurrences"]
        path.write_text(text.replace(row["before"], row["after"]), encoding="utf-8")
    for row in scope.get("create_files", []):
        path = root / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row["contents"], encoding="utf-8")
    for name, sources in scope["manifest_sources_after"].items():
        payload = _json(root / name)
        payload["sources"] = sources
        _write(root / name, payload)
    for name, compile_paths in scope["project_compile_after"].items():
        project = root / name
        tree = ET.parse(project)
        item_group = tree.getroot().find("ItemGroup")
        assert item_group is not None
        for node in list(item_group):
            if node.tag == "Compile":
                item_group.remove(node)
        for path in compile_paths:
            ET.SubElement(item_group, "Compile", {"Include": path})
        ET.indent(tree, space="  ")
        tree.write(project, encoding="unicode", xml_declaration=False)


def _native(host: Path) -> None:
    environment = {
        **os.environ,
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_NOLOGO": "1",
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "NUGET_XMLDOC_MODE": "skip",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
    }
    for project in PROJECTS:
        restore = subprocess.run(
            [str(DOTNET), "restore", project, "--configfile", "NuGet.Config", "--packages", ".native-build/packages"],
            cwd=host, capture_output=True, text=True, check=False, timeout=180, env=environment,
        )
        assert restore.returncode == 0, restore.stdout + restore.stderr
        build = subprocess.run(
            [str(DOTNET), "build", project, "--no-restore"], cwd=host,
            capture_output=True, text=True, check=False, timeout=180, env=environment,
        )
        assert build.returncode == 0, build.stdout + build.stderr
    test = subprocess.run(
        [str(DOTNET), "run", "--project", PROJECTS[1], "--no-build", "--no-restore"],
        cwd=host, capture_output=True, text=True, check=False, timeout=180, env=environment,
    )
    assert (test.returncode, test.stdout) == (0, "csharp-lexical-tests:ok\n"), test.stderr
    smoke = subprocess.run(
        [str(DOTNET), "run", "--project", PROJECTS[0], "--no-build", "--no-restore"],
        cwd=host, capture_output=True, text=True, check=False, timeout=180, env=environment,
    )
    assert (smoke.returncode, smoke.stdout) == (0, "csharp-lexical:12:queued\n"), smoke.stderr


def _rehash(path: Path, mutate) -> None:
    payload = _json(path)
    mutate(payload)
    payload.pop("acceptance_sha256", None)
    payload["acceptance_sha256"] = _object_hash(payload)
    _write(path, payload)


def test_csharp_structure_proposals_reach_native_copied_and_refused_outcomes(tmp_path: Path) -> None:
    host = _host(tmp_path)
    omnibus, topology, map_path, facts = _producers(host)
    boundary_acceptance = _boundary_acceptance(host, omnibus, map_path, facts)
    folder_acceptance = _folder_acceptance(host, topology, map_path, facts)
    before = _state(host)

    cases = (
        (BOUNDARY, omnibus, boundary_acceptance, "boundary"),
        (FOLDER, topology, folder_acceptance, "folder"),
    )
    for script, producer, acceptance, name in cases:
        output = _invoke(script, host, producer, map_path, facts, acceptance, "accepted")
        assert {path.name for path in output.iterdir()} == {"proposal.md", "evidence.json", "scope.json"}
        evidence = _json(output / "evidence.json")
        scope = _json(output / "scope.json")
        assert evidence["status"] == "ready_for_human_review"
        assert evidence["native_verification"]["current_tree"]["status"] == "passed"
        assert evidence["native_verification"]["disposable_after_tree"]["status"] == "passed"
        assert evidence["source_preservation"] == {"verified": True}
        assert evidence["evidence_binding"]["fact_pack_sha256"] == _json(facts)["fact_pack_sha256"]
        assert scope["read_only"] is True and scope["mutation_authorized"] is False
        assert scope["declarations"] and scope["caller_impact"]
        assert scope["manifest_sources_after"] and scope["project_compile_after"]
        assert _state(host) == before

        independent = _host(tmp_path, f"independent-{name}")
        _apply_scope(independent, scope)
        _native(independent)

        installed = tmp_path / f"installed-{name}/.claude/skills"
        copied_skill = installed / script.parents[1].name
        copied_semantic = installed / "_csharp-semantic"
        copied_lexical = installed / "_csharp"
        copied_map = installed / "map-subsystem"
        shutil.copytree(script.parents[1], copied_skill)
        shutil.copytree(SKILLS / "_csharp-semantic", copied_semantic)
        shutil.copytree(SKILLS / "_csharp", copied_lexical)
        shutil.copytree(SKILLS / "map-subsystem", copied_map)
        copied = copied_skill / "scripts" / script.name
        copied_output = _invoke(copied, host, producer, map_path, facts, acceptance, "copied")
        assert _json(copied_output / "evidence.json")["status"] == "ready_for_human_review"
        copied_text = copied.read_text(encoding="utf-8")
        assert str(ROOT) not in copied_text
        assert "run_csharp.py" not in copied_text
        assert "detect_csharp.py" not in copied_text
        assert "map_csharp.py" not in copied_text

    original = _json(boundary_acceptance)
    for gate in BOUNDARY_GATES:
        _rehash(
            boundary_acceptance,
            lambda payload, key=gate: payload["proposal_verdict"]["boundary_verdicts"].update({key: "unknown"}),
        )
        refused = _invoke(
            BOUNDARY, host, omnibus, map_path, facts, boundary_acceptance,
            f"refused-{gate}", expected=2,
        )
        refused_evidence = _json(refused / "evidence.json")
        refused_scope = _json(refused / "scope.json")
        assert refused_evidence["failure_kind"] == "csharp_boundary_unresolved"
        assert refused_scope["declarations"] == []
        _write(boundary_acceptance, original)

    _rehash(
        folder_acceptance,
        lambda payload: payload["selection"].update(project_convention=""),
    )
    refused = _invoke(
        FOLDER, host, topology, map_path, facts, folder_acceptance,
        "refused-convention", expected=2,
    )
    assert _json(refused / "evidence.json")["failure_kind"] == "project_convention_required"
    assert _json(refused / "scope.json")["declarations"] == []

    _write(folder_acceptance, _folder_acceptance(host, topology, map_path, facts) and _json(folder_acceptance))
    recovered = _invoke(FOLDER, host, topology, map_path, facts, folder_acceptance, "refused-convention")
    assert _json(recovered / "evidence.json")["status"] == "ready_for_human_review"
    assert _state(host) == before


def test_csharp_structure_proposals_refuse_stale_evidence_and_source(tmp_path: Path) -> None:
    host = _host(tmp_path)
    omnibus, topology, map_path, facts = _producers(host)
    acceptance = _boundary_acceptance(host, omnibus, map_path, facts)

    map_payload = _json(map_path)
    map_payload["name"] = "tampered"
    _write(map_path, map_payload)
    refused = _invoke(BOUNDARY, host, omnibus, map_path, facts, acceptance, "stale-map", expected=2)
    assert _json(refused / "evidence.json")["failure_kind"] == "artifact_hash_mismatch"

    omnibus, topology, map_path, facts = _producers(host)
    acceptance = _boundary_acceptance(host, omnibus, map_path, facts)
    source = host / "src/CSharpCohort/Omnibus.cs"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    refused = _invoke(BOUNDARY, host, omnibus, map_path, facts, acceptance, "stale-source", expected=2)
    assert _json(refused / "evidence.json")["failure_kind"] == "source_hash_mismatch"
