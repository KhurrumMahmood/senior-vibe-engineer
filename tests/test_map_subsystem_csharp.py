"""Final-artifact and copied-closure proof for the bounded C# subsystem map."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen product runtime
)
DOTNET = shutil.which("dotnet")
FIXTURE = ROOT / "tests/fixtures/csharp-map-subsystem/host"
SKILLS = ROOT / ".claude/skills"
MAP_SKILL = SKILLS / "map-subsystem"
MAP = MAP_SKILL / "scripts/map_csharp.py"
LEXICAL = SKILLS / "_csharp"
SEMANTIC = SKILLS / "_csharp-semantic"
HELPER_HASH = "0475a903da8973491775d627da2ca48c274e0c0684063ec229a26e439f5ed980"


pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or DOTNET is None,
    reason="the pinned product Python and .NET 10 SDK are required",
)


def _run(*argv: str | Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=240,
    )


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _state(host: Path) -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if relative.parts and relative.parts[0] in {
            "reports",
            ".native-build",
            ".engineering",
        }:
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = ("symlink", os.readlink(path))
        elif path.is_file():
            rows[relative.as_posix()] = (
                "file",
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return rows


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _map(
    host: Path,
    *,
    script: Path = MAP,
    name: str = "orders",
    dotnet: str | Path = str(DOTNET),
    cwd: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = host / ".engineering/docs/subsystems" / f"{name}.md"
    evidence = host / "reports/map" / name / "csharp-map.json"
    result = _run(
        PYTHON,
        "-I",
        "-S",
        script,
        "--name",
        name,
        "--target",
        "src/Orders",
        "--project-root",
        host,
        "--output",
        output,
        "--evidence",
        evidence,
        "--semantic-manifest",
        "csharp-semantic-project.json",
        "--dotnet",
        dotnet,
        cwd=cwd or host,
    )
    return result, output, evidence


def _assert_claim_free(payload: dict) -> None:
    assert payload["status"] != "complete"
    for key in (
        "namespaces",
        "files",
        "qualified_declarations",
        "types",
        "methods",
        "properties",
        "public_surface",
        "private_surface",
        "other_visibility",
        "direct_resolved_calls",
        "direct_resolved_references",
        "namespace_edges",
        "observed_boundary_evidence",
    ):
        assert payload[key] == []


def test_csharp_map_exact_manifest_symbols_edges_and_native_evidence(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    before = _state(host)

    result, markdown_path, evidence_path = _map(host)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(evidence_path)
    assert payload["status"] == "complete"
    assert payload["manifest_state"] == "current-complete-and-coherent"
    assert payload["manifest_evidence"]["state"] == (
        "current-complete-and-coherent"
    )
    assert len(payload["manifest_evidence"]["selected_paths_sha256"]) == 64
    assert [row["path"] for row in payload["source_inventory"]] == [
        "src/Orders/OrderService.cs",
        "src/Program.cs",
    ]
    assert [row["selected"] for row in payload["source_inventory"]] == [
        True,
        False,
    ]
    assert [row["path"] for row in payload["test_inventory"]] == [
        "tests/OrderTests.cs"
    ]
    assert all(len(row["sha256"]) == 64 for row in payload["source_inventory"])
    assert all(len(row["sha256"]) == 64 for row in payload["test_inventory"])
    assert {(row["path"], row["role"]) for row in payload["excluded_inventory"]} == {
        ("generated/GeneratedOrder.g.cs", "generated"),
        ("vendor/VendorOrder.cs", "vendor"),
    }
    assert payload["namespaces"] == [
        {
            "files": ["src/Orders/OrderService.cs"],
            "name": "CSharpMap.Orders",
        }
    ]
    assert [row["path"] for row in payload["files"]] == [
        "src/Orders/OrderService.cs"
    ]

    type_names = {row["name"] for row in payload["types"]}
    assert type_names == {
        "IOrderFormatter",
        "OrderService",
        "BaseOrderService",
        "SpecialOrderService",
        "OrderCallbacks",
        "RuntimeLookup",
    }
    assert {row["name"] for row in payload["properties"]} == {"Status"}
    assert {row["visibility"] for row in payload["types"]} == {"Public"}
    assert {
        (row["name"], row["visibility"])
        for row in payload["methods"]
        if row["name"] in {"Normalize", "Create"}
    } == {("Normalize", "Private"), ("Create", "Public")}
    override = next(row for row in payload["methods"] if row["override"])
    assert override["symbol_id"] == (
        "M:CSharpMap.Orders.SpecialOrderService.Describe(System.Int32)"
    )
    assert override["overridden_symbol_id"] == (
        "M:CSharpMap.Orders.BaseOrderService.Describe(System.Int32)"
    )
    explicit = next(
        row
        for row in payload["methods"]
        if row["explicit_interface_implementations"]
    )
    assert explicit["explicit_interface_implementations"] == [
        "M:CSharpMap.Orders.IOrderFormatter.Format(System.Int32)"
    ]

    calls = {
        (row["target_symbol_id"], row["direction"])
        for row in payload["direct_resolved_calls"]
    }
    assert (
        "M:CSharpMap.Orders.OrderService.Normalize(System.String)",
        "internal",
    ) in calls
    assert ("M:System.String.Trim", "outbound") in calls
    assert (
        "M:CSharpMap.Orders.OrderService.Create(System.Int32)",
        "inbound",
    ) in calls
    assert any(
        row["target_symbol_id"]
        == "P:CSharpMap.Orders.OrderService.Status"
        and row["direction"] == "inbound"
        for row in payload["direct_resolved_references"]
    )
    assert payload["direct_resolved_references"]
    assert all(row["target_symbol_id"] for row in payload["direct_resolved_calls"])

    authority = payload["semantic_authority"]
    assert authority["sdk_version"] == "10.0.302"
    assert authority["runtime_version"] == "10.0.10"
    assert authority["helper_sha256"] == HELPER_HASH
    assert authority["lexical_helper_sha256"] == (
        "65474b5a3e53cee8bfe035f925ad14d97f291f21baac1c4de5c12ae2f6ffdd16"
    )
    assert authority["csc_sha256"] == (
        "c5a2ff87882ad0c1b2e8d554ddf8d9eae1aa5d4d9b659f43a7c28d336ca2ba81"
    )
    assert authority["reference_count"] == 167
    assert payload["native_checks"]["semantic_test_stdout"] == (
        "csharp-map-native-test:ok\n"
    )
    assert payload["native_checks"]["semantic_smoke_stdout"] == "order:7\n"
    assert payload["native_checks"]["roslyn_diagnostics"] == []
    assert payload["source_preservation"]["verified"] is True

    observed = {row["kind"] for row in payload["observed_boundary_evidence"]}
    assert observed >= {
        "reflection_or_runtime_name_lookup",
        "delegate_or_method_group",
        "override_dispatch",
        "explicit_interface_dispatch",
        "excluded_generated_input",
        "excluded_vendor_input",
    }
    unresolved = {row["kind"] for row in payload["unresolved_boundaries"]}
    assert unresolved == {
        "runtime_dispatch_and_reachability",
        "reflection_and_runtime_names",
        "delegates_and_method_groups",
        "override_dispatch",
        "interface_dispatch",
        "generated_and_source_generator_inputs",
        "project_and_solution_graph",
        "framework_registration",
    }
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Status: **complete**" in markdown
    assert "Exact direct Roslyn edges" in markdown
    assert "CSharpMap.Orders.OrderService.Create" in markdown
    assert payload["artifacts"]["markdown_sha256"] == hashlib.sha256(
        markdown.encode()
    ).hexdigest()
    assert _state(host) == before


def test_copied_csharp_map_terminal_replacement_and_recovery(tmp_path: Path) -> None:
    host = _host(tmp_path, "copied-host")
    before = _state(host)
    installed = tmp_path / "installed/.agents/skills"
    shutil.copytree(MAP_SKILL, installed / "map-subsystem")
    shutil.copytree(LEXICAL, installed / "_csharp")
    shutil.copytree(SEMANTIC, installed / "_csharp-semantic")
    copied = installed / "map-subsystem/scripts/map_csharp.py"
    helper = installed / "_csharp-semantic/CSharpSemanticFacts.cs"
    outside = tmp_path / "outside"
    outside.mkdir()

    valid, markdown_path, evidence_path = _map(
        host, script=copied, name="lifecycle", cwd=outside
    )
    assert valid.returncode == 0, valid.stdout + valid.stderr
    complete = _payload(evidence_path)
    complete_markdown_hash = complete["artifacts"]["markdown_sha256"]
    assert complete["status"] == "complete"
    assert str(ROOT) not in copied.read_text(encoding="utf-8")

    semantic_manifest = host / "csharp-semantic-project.json"
    semantic_bytes = semantic_manifest.read_bytes()
    semantic_data = json.loads(semantic_bytes)
    semantic_data["sources"] = list(reversed(semantic_data["sources"]))
    semantic_manifest.write_text(
        json.dumps(semantic_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    stale, _, _ = _map(host, script=copied, name="lifecycle", cwd=outside)
    stale_payload = _payload(evidence_path)
    assert stale.returncode == 2, stale.stdout + stale.stderr
    assert stale_payload["status"] == "partial"
    assert stale_payload["failure_kind"] == "csharp_manifest_universe_mismatch"
    _assert_claim_free(stale_payload)
    stale_markdown = markdown_path.read_text(encoding="utf-8")
    assert "No structural map is available" in stale_markdown
    assert "CSharpMap.Orders.OrderService.Create" not in stale_markdown
    assert stale_payload["artifacts"]["markdown_sha256"] != complete_markdown_hash

    semantic_manifest.write_text("{}\n", encoding="utf-8")
    malformed, _, _ = _map(host, script=copied, name="lifecycle", cwd=outside)
    malformed_payload = _payload(evidence_path)
    assert malformed.returncode == 1
    assert malformed_payload["status"] == "failed"
    assert malformed_payload["failure_kind"] == "manifest_malformed"
    _assert_claim_free(malformed_payload)

    semantic_manifest.write_bytes(semantic_bytes)
    missing, _, _ = _map(
        host,
        script=copied,
        name="lifecycle",
        dotnet=host / "missing-dotnet",
        cwd=outside,
    )
    missing_payload = _payload(evidence_path)
    assert missing.returncode == 0
    assert missing_payload["status"] == "unsupported"
    assert missing_payload["failure_kind"] == "dotnet_tool_missing"
    _assert_claim_free(missing_payload)

    helper_bytes = helper.read_bytes()
    helper.write_bytes(helper_bytes + b"\n")
    hash_failed, _, _ = _map(host, script=copied, name="lifecycle", cwd=outside)
    hash_payload = _payload(evidence_path)
    assert hash_failed.returncode == 1
    assert hash_payload["status"] == "failed"
    assert hash_payload["failure_kind"] == "helper_source_hash_mismatch"
    _assert_claim_free(hash_payload)

    helper.write_bytes(helper_bytes)
    recovered, _, _ = _map(host, script=copied, name="lifecycle", cwd=outside)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    recovered_payload = _payload(evidence_path)
    assert recovered_payload["status"] == "complete"
    recovered_markdown = markdown_path.read_text(encoding="utf-8")
    assert "CSharpMap.Orders.OrderService.Create" in recovered_markdown
    assert recovered_payload["artifacts"]["markdown_sha256"] == hashlib.sha256(
        recovered_markdown.encode()
    ).hexdigest()
    assert recovered_payload["source_preservation"]["verified"] is True
    assert _state(host) == before


def test_csharp_map_requires_both_copied_providers(tmp_path: Path) -> None:
    host = _host(tmp_path, "missing-provider-host")
    installed = tmp_path / "partial-install/.agents/skills"
    shutil.copytree(MAP_SKILL, installed / "map-subsystem")
    shutil.copytree(LEXICAL, installed / "_csharp")
    copied = installed / "map-subsystem/scripts/map_csharp.py"

    result, markdown_path, evidence_path = _map(
        host, script=copied, name="missing-provider"
    )

    assert result.returncode == 2
    payload = _payload(evidence_path)
    assert payload["status"] == "partial"
    assert payload["failure_kind"] == "csharp_semantic_provider_missing"
    _assert_claim_free(payload)
    assert "No structural map is available" in markdown_path.read_text(
        encoding="utf-8"
    )
