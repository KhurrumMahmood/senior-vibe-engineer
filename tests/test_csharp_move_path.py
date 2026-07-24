"""Transactional proof for the bounded C# source-location move."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/move-path/scripts/csharp_source_move.py"
FIXTURE = ROOT / "tests/fixtures/csharp-move-path/host"
DOTNET_RAW = shutil.which("dotnet")
DOTNET = Path(DOTNET_RAW).resolve() if DOTNET_RAW else Path("/missing/dotnet")


def _documented_csharp_command() -> str:
    text = (ROOT / ".claude/skills/move-path/SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- installed-command:csharp-move:start -->\n```bash\n(.*?)\n```\n"
        r"<!-- installed-command:csharp-move:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def _dotnet_10() -> bool:
    if not DOTNET.is_file():
        return False
    result = subprocess.run(
        [str(DOTNET), "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "10.0.302"


pytestmark = pytest.mark.skipif(
    not _dotnet_10(), reason="the fixture requires the pinned .NET SDK 10.0.302"
)


def test_csharp_documented_branch_matches_standalone_cli() -> None:
    command = _documented_csharp_command()
    assert "scripts/csharp_source_move.py" in command
    assert "--approve-evidence-sha256" in command
    assert "--evidence" in command
    result = subprocess.run(
        [str(Path(sys.executable).resolve()), "-I", "-S", str(SCRIPT), "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    for flag in (
        "--dry-run",
        "--apply",
        "--check",
        "--evidence",
        "--approve-evidence-sha256",
    ):
        assert flag in result.stdout


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _plan_payload(
    *,
    dotnet: Path = DOTNET,
    source: str = "src/Invoice.cs",
    destination: str = "src/billing/Invoice.cs",
) -> dict:
    return {
        "version": 1,
        "moves": [{"from": source, "to": destination, "mode": "file"}],
        "rewrite": {"code_imports": "update-csharp-project"},
        "csharp": {
            "dotnet": str(dotnet),
            "project": "CSharpMovePilot.csproj",
            "sdk_version": "10.0.302",
            "assembly_name": "CSharpMovePilot",
            "namespace": "CSharpMovePilot",
            "type_identity": "CSharpMovePilot.Invoice",
            "artifact_scope": "closed-executable",
            "external_consumers": "none",
            "native_test_expected_stdout": "csharp-move-tests:ok\n",
            "smoke_expected_stdout": "invoice:INV-42:125:csharp-move\n",
        },
    }


def _plan(host: Path, **kwargs: object) -> Path:
    plan = host / "csharp-move.json"
    plan.write_text(
        json.dumps(_plan_payload(**kwargs), indent=2) + "\n",
        encoding="utf-8",
    )
    return plan


def _tree(host: Path) -> dict[str, tuple[str, bytes | str, int]]:
    rows: dict[str, tuple[str, bytes | str, int]] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if relative.parts[:2] == ("reports", "move-path"):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = ("link", os.readlink(path), 0)
        elif path.is_file():
            rows[relative.as_posix()] = (
                "file",
                path.read_bytes(),
                stat.S_IMODE(path.stat().st_mode),
            )
    return rows


def _invoke(
    host: Path,
    plan: Path,
    mode: str,
    *,
    script: Path = SCRIPT,
    cwd: Path | None = None,
    evidence: Path | None = None,
    approval: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict, Path]:
    report_dir = host / "reports/move-path"
    argv = [
        str(Path(sys.executable).resolve()),
        "-I",
        "-S",
        str(script),
        "--plan",
        str(plan),
        "--project-root",
        str(host),
        "--report-dir",
        str(report_dir),
        f"--{mode}",
        "--json",
    ]
    if evidence is not None:
        argv.extend(["--evidence", str(evidence)])
    if approval is not None:
        argv.extend(["--approve-evidence-sha256", approval])
    result = subprocess.run(
        argv,
        cwd=cwd or host,
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )
    report_path = report_dir / "report.json"
    report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else {}
    )
    return result, report, report_dir


def _preview(
    host: Path,
    plan: Path,
    *,
    script: Path = SCRIPT,
    cwd: Path | None = None,
) -> tuple[dict, Path, dict]:
    result, report, report_dir = _invoke(
        host, plan, "dry-run", script=script, cwd=cwd
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence_path = report_dir / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert report["csharp"]["evidence_sha256"] == evidence["evidence_sha256"]
    return report, evidence_path, evidence


def test_csharp_preview_authorized_apply_check_preserves_identity_and_output(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    before = _tree(host)
    source_bytes = (host / "src/Invoice.cs").read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    protected = {
        path: hashlib.sha256((host / path).read_bytes()).hexdigest()
        for path in (
            "src/Program.cs",
            "tests/MoveTests.cs",
            "generated/GeneratedInvoice.cs",
            "vendor/VendorInvoice.cs",
            "build/BuildSentinel.cs",
            "tools/Tooling.cs",
            "global.json",
            "NuGet.Config",
        )
    }

    preview, evidence_path, evidence = _preview(host, plan)

    csharp = preview["csharp"]
    assert csharp["status"] == "complete"
    assert csharp["mode"] == "dry-run"
    assert _tree(host) == before
    assert csharp["identity"] == {
        "assembly_name": "CSharpMovePilot",
        "namespace": "CSharpMovePilot",
        "type_identity": "CSharpMovePilot.Invoice",
        "source_sha256": source_sha,
    }
    assert {
        (row["path"], row["kind"], row["old"], row["new"])
        for row in csharp["exact_changes"]
    } == {
        (
            "CSharpMovePilot.csproj",
            "csharp_compile_include",
            "src/Invoice.cs",
            "src/billing/Invoice.cs",
        ),
        (
            "src/Invoice.cs",
            "csharp_source_location",
            "src/Invoice.cs",
            "src/billing/Invoice.cs",
        ),
    }
    assert csharp["native_preflight"]["test"]["stdout"] == "csharp-move-tests:ok\n"
    assert csharp["native_after_preview"]["smoke"]["stdout"] == (
        "invoice:INV-42:125:csharp-move\n"
    )

    applied, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert report["csharp"]["status"] == "complete"
    assert report["csharp"]["rolled_back"] is False
    assert report["csharp"]["exact_after_tree"]["passed"] is True
    assert not (host / "src/Invoice.cs").exists()
    destination = host / "src/billing/Invoice.cs"
    assert destination.read_bytes() == source_bytes
    assert 'Compile Include="src/billing/Invoice.cs"' in (
        host / "CSharpMovePilot.csproj"
    ).read_text(encoding="utf-8")
    assert all(
        hashlib.sha256((host / path).read_bytes()).hexdigest() == digest
        for path, digest in protected.items()
    )

    checked, checked_report, _ = _invoke(
        host, plan, "check", evidence=evidence_path
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert checked_report["csharp"]["status"] == "complete"
    assert checked_report["csharp"]["old_path_residue"] == []
    assert checked_report["csharp"]["native_postflight"]["smoke"]["stdout"] == (
        "invoice:INV-42:125:csharp-move\n"
    )


def test_csharp_complete_failed_complete_lifecycle_clears_authority(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    first, evidence_path, _ = _preview(host, plan)
    assert first["csharp"]["status"] == "complete"

    program = host / "src/Program.cs"
    original = program.read_bytes()
    program.write_text(
        program.read_text(encoding="utf-8")
        + '\ninternal static class DynamicInvoice { internal static object? Value => Type.GetType("CSharpMovePilot.Invoice"); }\n',
        encoding="utf-8",
    )
    failed, report, _ = _invoke(host, plan, "dry-run")
    assert failed.returncode == 2
    assert report["csharp"]["status"] == "partial"
    assert report["csharp"]["failure_kind"] == "csharp_reflection_identity_uncertain"
    assert not evidence_path.exists()

    program.write_bytes(original)
    recovered, recovered_evidence, _ = _preview(host, plan)
    assert recovered["csharp"]["status"] == "complete"
    assert recovered_evidence.is_file()


@pytest.mark.parametrize(
    ("boundary", "expected_kind"),
    [
        ("namespace", "csharp_namespace_identity_change"),
        ("type", "csharp_type_identity_change"),
        ("public", "csharp_public_identity_unsupported"),
        ("assembly", "csharp_assembly_identity_change"),
        ("package", "csharp_project_dependency_unsupported"),
        ("solution", "csharp_project_graph_ambiguous"),
        ("reflection", "csharp_reflection_identity_uncertain"),
        ("path", "csharp_path_identity_uncertain"),
        ("resource", "csharp_resource_identity_uncertain"),
        ("unowned-source", "csharp_project_source_closure_mismatch"),
        ("generated-source", "csharp_source_role_unsupported"),
        ("symlink-source", "csharp_symlink_source_unsupported"),
        ("multiple", "csharp_move_scope_unsupported"),
        ("directory", "csharp_move_scope_unsupported"),
        ("rename", "csharp_filename_identity_change"),
        ("api-claim", "csharp_plan_invalid"),
    ],
)
def test_csharp_identity_graph_dynamic_role_and_scope_uncertainty_refuse(
    tmp_path: Path, boundary: str, expected_kind: str
) -> None:
    host = _host(tmp_path, boundary)
    payload = _plan_payload()
    source = host / "src/Invoice.cs"
    project = host / "CSharpMovePilot.csproj"
    program = host / "src/Program.cs"
    if boundary == "namespace":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "namespace CSharpMovePilot;", "namespace Changed;"
            ),
            encoding="utf-8",
        )
    elif boundary == "type":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "record Invoice", "record RenamedInvoice"
            ),
            encoding="utf-8",
        )
    elif boundary == "public":
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "internal sealed record", "public sealed record"
            ),
            encoding="utf-8",
        )
    elif boundary == "assembly":
        project.write_text(
            project.read_text(encoding="utf-8").replace(
                "<AssemblyName>CSharpMovePilot</AssemblyName>",
                "<AssemblyName>Changed</AssemblyName>",
            ),
            encoding="utf-8",
        )
    elif boundary == "package":
        project.write_text(
            project.read_text(encoding="utf-8").replace(
                "  </ItemGroup>",
                '    <PackageReference Include="Example" Version="1.0.0" />\n  </ItemGroup>',
            ),
            encoding="utf-8",
        )
    elif boundary == "solution":
        (host / "CSharpMovePilot.sln").write_text("Microsoft Visual Studio Solution File\n")
    elif boundary == "reflection":
        program.write_text(
            program.read_text(encoding="utf-8")
            + '\ninternal static class DynamicInvoice { internal static object? Value => Type.GetType("CSharpMovePilot.Invoice"); }\n',
            encoding="utf-8",
        )
    elif boundary == "path":
        program.write_text(
            program.read_text(encoding="utf-8")
            + '\ninternal static class InvoicePath { internal static string Value => System.IO.Path.Combine("src", "Invoice.cs"); }\n',
            encoding="utf-8",
        )
    elif boundary == "resource":
        program.write_text(
            program.read_text(encoding="utf-8")
            + '\ninternal static class InvoiceResource { internal static object? Value => typeof(Program).Assembly.GetManifestResourceStream("CSharpMovePilot.Invoice"); }\n',
            encoding="utf-8",
        )
    elif boundary == "unowned-source":
        (host / "src/Unowned.cs").write_text(
            "namespace CSharpMovePilot;\ninternal sealed class Unowned;\n",
            encoding="utf-8",
        )
    elif boundary == "generated-source":
        payload = _plan_payload(
            source="generated/GeneratedInvoice.cs",
            destination="generated/archive/GeneratedInvoice.cs",
        )
        payload["csharp"]["namespace"] = "CSharpMovePilot.Generated"
        payload["csharp"]["type_identity"] = "CSharpMovePilot.Generated.GeneratedInvoice"
    elif boundary == "symlink-source":
        external = tmp_path / "ExternalInvoice.cs"
        external.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(external)
    elif boundary == "multiple":
        payload["moves"].append(
            {"from": "src/Program.cs", "to": "src/app/Program.cs", "mode": "file"}
        )
    elif boundary == "directory":
        payload["moves"] = [
            {"from": "src/", "to": "source/", "mode": "directory"}
        ]
    elif boundary == "rename":
        payload["moves"][0]["to"] = "src/billing/RenamedInvoice.cs"
    else:
        payload["csharp"]["public_api_compatible"] = True
    plan = host / "csharp-move.json"
    plan.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    before = _tree(host)

    result, report, report_dir = _invoke(host, plan, "dry-run")

    assert result.returncode == 2
    assert report["csharp"]["status"] in {"partial", "failed", "unsupported"}
    assert report["csharp"]["failure_kind"] == expected_kind
    assert not (report_dir / "evidence.json").exists()
    assert _tree(host) == before


def test_csharp_missing_wrong_and_stale_authority_refuse_without_writes(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    before = _tree(host)

    missing, _, _ = _invoke(host, plan, "apply")
    assert missing.returncode == 2
    assert _tree(host) == before

    _, evidence_path, evidence = _preview(host, plan)
    wrong, _, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval="0" * 64,
    )
    assert wrong.returncode == 2
    assert _tree(host) == before

    consumer = host / "src/Program.cs"
    consumer.chmod(0o600)
    stale_before = _tree(host)
    stale, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )
    assert stale.returncode == 2
    assert report["csharp"]["failure_kind"] == "stale_move_evidence"
    assert report["csharp"]["rolled_back"] is False
    assert _tree(host) == stale_before


def test_csharp_post_mutation_native_failure_rolls_back_exact_tree(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    state = host / "reports/move-path/destination-build-count"
    wrapper = host / "dotnet-wrapper"
    wrapper.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "if [ \"${1:-}\" = build ] && grep -q 'src/billing/Invoice.cs' CSharpMovePilot.csproj; then\n"
        f"  state={json.dumps(str(state))}\n"
        "  mkdir -p \"$(dirname \"$state\")\"\n"
        "  count=0\n"
        "  if [ -f \"$state\" ]; then count=$(cat \"$state\"); fi\n"
        "  count=$((count + 1))\n"
        "  printf '%s' \"$count\" > \"$state\"\n"
        "  if [ \"$count\" -ge 3 ]; then echo forced-postflight-failure >&2; exit 9; fi\n"
        "fi\n"
        f"exec {json.dumps(str(DOTNET))} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    plan = _plan(host, dotnet=wrapper)
    _, evidence_path, evidence = _preview(host, plan)
    before = _tree(host)

    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 2
    assert report["csharp"]["status"] == "failed"
    assert report["csharp"]["failure_kind"] == "dotnet_build_failed"
    assert report["csharp"]["rolled_back"] is True
    assert report["csharp"]["rollback_exact"]["passed"] is True
    assert _tree(host) == before
    assert (host / "src/Invoice.cs").is_file()
    assert not (host / "src/billing/Invoice.cs").exists()


def test_csharp_copied_stock_closure_runs_outside_repository(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    copied = tmp_path / "installed/move-path/scripts/csharp_source_move.py"
    copied.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, copied)
    outside = tmp_path / "outside"
    outside.mkdir()

    _, evidence_path, evidence = _preview(host, plan, script=copied, cwd=outside)
    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        script=copied,
        cwd=outside,
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert report["csharp"]["status"] == "complete"
    assert report["csharp"]["exact_after_tree"]["passed"] is True
    source = copied.read_text(encoding="utf-8")
    assert str(ROOT) not in source
    assert "csharp_language_provider" not in source
    assert "source_inventory" not in source
