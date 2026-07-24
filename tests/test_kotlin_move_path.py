"""Transactional proof for one manifest-owned Kotlin/JVM source-file move."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/move-path/scripts/kotlin_source_move.py"
FIXTURE = ROOT / "tests/fixtures/kotlin-pilot/host"
KOTLINC = Path("/opt/homebrew/bin/kotlinc")
JAVA = Path("/usr/bin/java")

pytestmark = pytest.mark.skipif(
    not KOTLINC.is_file() or not JAVA.is_file(),
    reason="Kotlin/JVM 2.4.10 and JDK 17 are required",
)


def _run(*argv: str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


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


def _plan(
    host: Path,
    *,
    source: str = "src/main/kotlin/kotlinpilot/Invoice.kt",
    destination: str = "src/main/kotlin/kotlinpilot/billing/Invoice.kt",
    kotlinc: Path = KOTLINC,
) -> Path:
    plan = host / "kotlin-move.json"
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "moves": [{"from": source, "to": destination, "mode": "file"}],
                "rewrite": {"code_imports": "update-kotlin-jvm"},
                "kotlin": {
                    "manifest": "kotlin-project.json",
                    "kotlinc": str(kotlinc),
                    "java": str(JAVA),
                    "kotlin_version": "2.4.10",
                    "jvm_target": "17",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return plan


def _invoke(
    host: Path,
    plan: Path,
    mode: str,
    *,
    script: Path = SCRIPT,
    evidence: Path | None = None,
    approval: str | None = None,
    cwd: Path | None = None,
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
    result = _run(*argv, cwd=cwd or host)
    report_path = report_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    return result, report, report_dir


def _preview(
    host: Path, plan: Path, *, script: Path = SCRIPT
) -> tuple[dict, Path, dict]:
    result, report, report_dir = _invoke(host, plan, "dry-run", script=script)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence_path = report_dir / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert report["kotlin"]["evidence_sha256"] == evidence["evidence_sha256"]
    return report, evidence_path, evidence


def test_kotlin_preview_approve_apply_check_preserves_package_jvm_identity_and_smoke(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    before = _tree(host)
    protected = {
        path: hashlib.sha256((host / path).read_bytes()).hexdigest()
        for path in (
            "src/main/kotlin/kotlinpilot/Main.kt",
            "tests/kotlinpilot/InvoiceTest.kt",
            "generated/GeneratedInvoice.kt",
            "vendor/VendorInvoice.kt",
            "scripts/Tooling.kt",
            "scripts/Seed.kts",
            "build.gradle.kts",
        )
    }

    preview, evidence_path, evidence = _preview(host, plan)
    kotlin = preview["kotlin"]
    assert kotlin["status"] == "complete"
    assert _tree(host) == before
    assert kotlin["exact_changes"] == [
        {
            "kind": "kotlin_source_path",
            "old": "src/main/kotlin/kotlinpilot/Invoice.kt",
            "new": "src/main/kotlin/kotlinpilot/billing/Invoice.kt",
        },
        {
            "file": "kotlin-project.json",
            "kind": "kotlin_manifest_source",
            "old": "src/main/kotlin/kotlinpilot/Invoice.kt",
            "new": "src/main/kotlin/kotlinpilot/billing/Invoice.kt",
        },
    ]
    assert kotlin["native_preflight"]["test"]["stdout"] == "kotlin-pilot-tests:ok\n"
    assert kotlin["native_preflight"]["smoke"]["stdout"] == (
        "invoice:INV-42:pending:kotlin\n"
    )
    assert kotlin["identity_proof"]["passed"] is True
    assert "kotlinpilot/InvoiceKt.class" in kotlin["identity_proof"]["classes_before"]
    assert evidence["expected_after_tree_sha256"]

    result, applied, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert applied["kotlin"]["status"] == "complete"
    assert applied["kotlin"]["exact_after_tree"]["passed"] is True
    assert applied["kotlin"]["rolled_back"] is False
    assert not (host / "src/main/kotlin/kotlinpilot/Invoice.kt").exists()
    moved = host / "src/main/kotlin/kotlinpilot/billing/Invoice.kt"
    assert moved.is_file()
    assert moved.read_bytes() == before["src/main/kotlin/kotlinpilot/Invoice.kt"][1]
    assert moved.read_text(encoding="utf-8").startswith("package kotlinpilot\n")
    manifest = json.loads((host / "kotlin-project.json").read_text(encoding="utf-8"))
    assert manifest["sources"] == [
        "src/main/kotlin/kotlinpilot/billing/Invoice.kt",
        "src/main/kotlin/kotlinpilot/Main.kt",
    ]
    assert all(
        hashlib.sha256((host / path).read_bytes()).hexdigest() == digest
        for path, digest in protected.items()
    )

    checked, report, _ = _invoke(host, plan, "check", evidence=evidence_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert report["kotlin"]["status"] == "complete"
    assert report["kotlin"]["old_identity_remaining"] == []


@pytest.mark.parametrize(
    ("mutation", "kind"),
    [
        ("rename", "kotlin_jvm_identity_change_refused"),
        ("file-annotation", "kotlin_file_annotation_refused"),
        ("reflection", "kotlin_dynamic_runtime_uncertain"),
        ("resource", "kotlin_resource_boundary_uncertain"),
        ("gradle", "kotlin_gradle_variant_uncertain"),
        ("generated", "kotlin_requires_manifested_authored_source"),
        ("script", "kotlin_requires_kt_source"),
        ("symlink", "kotlin_symlink_boundary"),
    ],
)
def test_kotlin_identity_annotation_dynamic_resource_gradle_and_path_uncertainty_refuse(
    tmp_path: Path, mutation: str, kind: str
) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    if mutation == "rename":
        plan = _plan(
            host,
            destination="src/main/kotlin/kotlinpilot/billing/RenamedInvoice.kt",
        )
    elif mutation == "file-annotation":
        source = host / "src/main/kotlin/kotlinpilot/Invoice.kt"
        source.write_text('@file:JvmName("Billing")\n' + source.read_text(), encoding="utf-8")
    elif mutation == "reflection":
        consumer = host / "src/main/kotlin/kotlinpilot/Main.kt"
        consumer.write_text(consumer.read_text() + '\nval dynamic = Class.forName("kotlinpilot.Invoice")\n', encoding="utf-8")
    elif mutation == "resource":
        resource = host / "src/main/resources/META-INF/services/invoice"
        resource.parent.mkdir(parents=True)
        resource.write_text("kotlinpilot.InvoiceKt\n", encoding="utf-8")
    elif mutation == "gradle":
        (host / "build.gradle.kts").write_text("plugins { kotlin(\"jvm\") version \"2.4.10\" }\n", encoding="utf-8")
    elif mutation == "generated":
        plan = _plan(
            host,
            source="generated/GeneratedInvoice.kt",
            destination="src/main/kotlin/kotlinpilot/GeneratedInvoice.kt",
        )
    elif mutation == "script":
        plan = _plan(
            host,
            source="scripts/Seed.kts",
            destination="scripts/moved/Seed.kts",
        )
    else:
        source = host / "src/main/kotlin/kotlinpilot/Invoice.kt"
        contents = source.read_bytes()
        source.unlink()
        outside = host / "Invoice.kt"
        outside.write_bytes(contents)
        source.symlink_to("../../../../Invoice.kt")
    before = _tree(host)

    result, report, report_dir = _invoke(host, plan, "dry-run")

    assert result.returncode == 2
    assert report["kotlin"]["status"] in {"failed", "partial", "unsupported"}
    assert kind in {row["kind"] for row in report["kotlin"]["blocked"]}
    assert _tree(host) == before
    assert not (report_dir / "evidence.json").exists()


def test_kotlin_stale_or_missing_approval_refuses_without_writes(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    _, evidence_path, evidence = _preview(host, plan)
    before = _tree(host)

    missing, _, _ = _invoke(host, plan, "apply")
    assert missing.returncode == 2
    assert _tree(host) == before

    source = host / "src/main/kotlin/kotlinpilot/Main.kt"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    changed = _tree(host)
    stale, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )
    assert stale.returncode == 2
    assert "kotlin_stale_evidence" in {
        row["kind"] for row in report["kotlin"]["blocked"]
    }
    assert _tree(host) == changed


def test_kotlin_postflight_failure_rolls_back_exact_tree(tmp_path: Path) -> None:
    host = _host(tmp_path)
    wrapper = tmp_path / "kotlinc"
    wrapper.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        f"case \"$*\" in *{host}/src/main/kotlin/kotlinpilot/billing/Invoice.kt*) exit 19;; esac\n"
        f'exec "{KOTLINC}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    plan = _plan(host, kotlinc=wrapper)
    before = _tree(host)
    _, evidence_path, evidence = _preview(host, plan)

    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 2
    assert report["kotlin"]["rolled_back"] is True
    assert report["kotlin"]["status"] == "failed"
    assert report["kotlin"]["rollback_exact"]["passed"] is True
    assert _tree(host) == before


def test_kotlin_copied_stock_selected_adapter_runs_outside_repository(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "installed/move-path/scripts/kotlin_source_move.py"
    copied.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, copied)
    host = _host(tmp_path, "external-host")
    plan = _plan(host)

    preview, evidence_path, evidence = _preview(host, plan, script=copied)
    assert preview["kotlin"]["status"] == "complete"
    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        script=copied,
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["kotlin"]["status"] == "complete"
    assert report["kotlin"]["exact_after_tree"]["passed"] is True
