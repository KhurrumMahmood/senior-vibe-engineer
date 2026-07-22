"""Swift compiler final-outcome and copied-closure proof for find-omnibus."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "find-omnibus"
FIXTURE = ROOT / "tests" / "fixtures" / "swift-pilot"
OMNIBUS_MEMBERS = """

public struct OmnibusService {
    public init() {}
    public func saveInvoiceRecord() {}
    public func loadInvoiceRecord() {}
    public func createShipmentLabel() {}
    public func cancelShipmentLabel() {}
    public func getCustomerProfile() {}
    public func listCustomerProfile() {}
    public func getInventoryItem() {}
    public func listInventoryItem() {}
}
"""


def _swiftc() -> str:
    executable = shutil.which("swiftc")
    if executable is None:
        pytest.skip("Swift compiler unavailable; the provider reports this as unsupported")
    return executable


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _host(tmp_path: Path) -> Path:
    pilot = tmp_path / "swift-pilot"
    shutil.copytree(FIXTURE, pilot)
    host = pilot / "host"
    (host / "LinkedExternal").symlink_to(
        pilot / "symlink-target", target_is_directory=True
    )
    return host


def _source_state(host: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host).as_posix()
        if relative.startswith("reports/"):
            continue
        if path.is_symlink():
            state[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            state[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return state


def _records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _detect(
    skill: Path,
    host: Path,
    report_dir: Path,
    target: Path,
    *,
    env: dict[str, str] | None = None,
    isolated: bool = False,
) -> subprocess.CompletedProcess[str]:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    return _run(
        *prefix,
        str(skill / "scripts" / "detect.py"),
        "--target",
        str(target),
        "--project-root",
        str(host),
        "--output",
        str(report_dir / "omnibus.jsonl"),
        "--language",
        "swift",
        cwd=host,
        env=env,
    )


def _finish_report(
    skill: Path,
    host: Path,
    report_dir: Path,
    *,
    isolated: bool = False,
    scout: bool = False,
) -> dict:
    prefix = (sys.executable, "-I", "-S") if isolated else (sys.executable,)
    collapsed = _run(
        *prefix,
        str(skill / "scripts" / "collapse.py"),
        "--detections",
        str(report_dir / "omnibus.jsonl"),
        "--output",
        str(report_dir / "candidates.jsonl"),
        cwd=host,
    )
    assert collapsed.returncode == 0, collapsed.stdout + collapsed.stderr
    candidates = _records(report_dir / "candidates.jsonl")
    scout_dir = report_dir / "scout"
    if scout:
        candidate = candidates[0]
        scout_dir.mkdir()
        (scout_dir / f"{candidate['candidate_id']}.json").write_text(
            json.dumps(
                {
                    "candidate_id": candidate["candidate_id"],
                    "file": candidate["file"],
                    "bucket": "confirmed_omnibus",
                    "domains_confirmed": ["invoice", "shipment", "customer", "inventory"],
                    "srp_rewrite": "This Swift type handles four independent record domains.",
                    "decomposition_sketch": [],
                    "decomposition_depth_note": "Each domain has a separate callable surface.",
                    "false_positive_reason": None,
                    "notes": "Disposable Swift compiler outcome fixture.",
                    "recommendation": "decompose",
                }
            ),
            encoding="utf-8",
        )
    reported = _run(
        *prefix,
        str(skill / "scripts" / "report.py"),
        "--candidates",
        str(report_dir / "candidates.jsonl"),
        "--scout-dir",
        str(scout_dir),
        "--output-md",
        str(report_dir / "report.md"),
        "--output-json",
        str(report_dir / "findings.json"),
        "--scan-id",
        "p7-swift-compiler",
        "--target",
        ".",
        cwd=host,
    )
    assert reported.returncode == 0, reported.stdout + reported.stderr
    return json.loads((report_dir / "findings.json").read_text(encoding="utf-8"))


def _pipeline(
    skill: Path,
    host: Path,
    report_dir: Path,
    target: Path,
    *,
    expected_returncode: int,
    env: dict[str, str] | None = None,
    isolated: bool = False,
    scout: bool = False,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    detected = _detect(
        skill, host, report_dir, target, env=env, isolated=isolated
    )
    assert detected.returncode == expected_returncode, detected.stdout + detected.stderr
    return detected, _finish_report(
        skill, host, report_dir, isolated=isolated, scout=scout
    )


def _add_omnibus(host: Path) -> Path:
    source = host / "Sources" / "BillingCore" / "BillingCore.swift"
    source.write_text(source.read_text(encoding="utf-8") + OMNIBUS_MEMBERS, encoding="utf-8")
    return source


def test_swift_positive_and_clean_reach_final_reports_without_source_mutation(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    source = _add_omnibus(host)
    native = _run(_swiftc(), "-typecheck", str(source), cwd=host)
    assert native.returncode == 0, native.stdout + native.stderr
    before = _source_state(host)

    _, findings = _pipeline(
        SKILL,
        host,
        host / "reports" / "positive",
        source.parent,
        expected_returncode=0,
        scout=True,
    )

    records = _records(host / "reports" / "positive" / "omnibus.jsonl")
    assert [record["file"] for record in records] == [
        "Sources/BillingCore/BillingCore.swift"
    ]
    record = records[0]
    assert record["language"] == "swift"
    assert record["analyzer"] == "swiftc-typecheck-dump-ast"
    assert record["and_count"] == 3
    clusters = {cluster["name"]: cluster["symbols"] for cluster in record["clusters"]}
    assert set(clusters) == {"invoice", "shipment", "customer", "inventory"}
    assert "OmnibusService.saveInvoiceRecord" in clusters["invoice"]
    swift = findings["analysis"]["swift"]
    assert findings["status"] == "complete"
    assert findings["outcome"] == "findings-within-complete"
    assert swift["claim_boundary"] == {
        "swift_syntax": False,
        "resolved_references": False,
        "complete_project_semantics": False,
    }
    assert {row["name"] for row in swift["declarations"]} >= {
        "Clock",
        "FixedClock",
        "Invoice",
        "InvoiceFormatter",
        "InvoiceService",
        "OmnibusService",
    }
    assert swift["source_fingerprints"]["Sources/BillingCore/BillingCore.swift"] == (
        hashlib.sha256(source.read_bytes()).hexdigest()
    )
    assert _source_state(host) == before

    clean_host = _host(tmp_path / "clean")
    clean_before = _source_state(clean_host)
    _, clean = _pipeline(
        SKILL,
        clean_host,
        clean_host / "reports" / "clean",
        clean_host / "Sources" / "BillingCore",
        expected_returncode=0,
    )
    assert clean["status"] == "complete"
    assert clean["outcome"] == "clean-within-complete"
    assert clean["summary"]["findings_total"] == 0
    assert "**Outcome:** `clean-within-complete`" in (
        clean_host / "reports" / "clean" / "report.md"
    ).read_text(encoding="utf-8")
    assert _source_state(clean_host) == clean_before


def test_swift_partial_and_role_exclusions_are_explicit(tmp_path: Path) -> None:
    host = _host(tmp_path)
    linked = host / "Sources" / "BillingCore" / "LinkedExternal.swift"
    linked.symlink_to(FIXTURE / "symlink-target" / "LinkedExternal.swift")
    before = _source_state(host)

    _, findings = _pipeline(
        SKILL,
        host,
        host / "reports" / "partial",
        host,
        expected_returncode=0,
    )

    swift = findings["analysis"]["swift"]
    assert findings["status"] == "partial"
    assert findings["outcome"] == "incomplete"
    assert swift["failure_kind"] == "standalone-typecheck-incomplete"
    inventory = {row["file"]: row for row in swift["inventory"]}
    assert inventory["Sources/BillingCore/BillingCore.swift"]["role"] == "eligible"
    assert inventory["Sources/SwiftPilotSmoke/main.swift"]["role"] == "eligible"
    assert inventory["Tests/BillingCoreTests/InvoiceServiceTests.swift"]["role"] == "excluded"
    assert inventory["generated/GeneratedInvoice.swift"]["role"] == "excluded"
    assert inventory["vendor/Example/Vendor.swift"]["role"] == "excluded"
    assert inventory[".build/Sentinel.swift"]["role"] == "excluded"
    assert inventory["Sources/BillingCore/LinkedExternal.swift"] == {
        "file": "Sources/BillingCore/LinkedExternal.swift",
        "role": "excluded",
        "reason": "symlink",
    }
    assert not any(row["file"].startswith("LinkedExternal/") for row in swift["inventory"])
    assert "not a clean omnibus result" in (
        host / "reports" / "partial" / "report.md"
    ).read_text(encoding="utf-8")
    assert _source_state(host) == before


def test_swift_malformed_and_same_destination_transitions_are_terminal(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    source = _add_omnibus(host)
    report_dir = host / "reports" / "lifecycle"
    _, complete = _pipeline(
        SKILL,
        host,
        report_dir,
        source.parent,
        expected_returncode=0,
        scout=True,
    )
    assert complete["status"] == "complete"
    stale = (
        report_dir / "candidates.jsonl",
        report_dir / "report.md",
        report_dir / "findings.json",
        report_dir / "scout",
    )
    assert all(path.exists() for path in stale)

    source.write_text("public struct Broken {\n", encoding="utf-8")
    failed_detect = _detect(SKILL, host, report_dir, source.parent)
    assert failed_detect.returncode == 2
    assert "expected '}' in struct" in failed_detect.stderr
    assert all(not path.exists() for path in stale)
    failed = _finish_report(SKILL, host, report_dir)
    assert failed["status"] == "failed"
    assert failed["outcome"] == "failed"
    assert failed["analysis"]["swift"]["failure_kind"] == "swift-syntax-error"

    fixture_source = FIXTURE / "host" / "Sources" / "BillingCore" / "BillingCore.swift"
    source.write_text(fixture_source.read_text(encoding="utf-8") + OMNIBUS_MEMBERS, encoding="utf-8")
    recovered_detect = _detect(SKILL, host, report_dir, source.parent)
    assert recovered_detect.returncode == 0, recovered_detect.stdout + recovered_detect.stderr
    assert all(not path.exists() for path in stale)
    recovered = _finish_report(SKILL, host, report_dir, scout=True)
    assert recovered["status"] == "complete"
    assert recovered["outcome"] == "findings-within-complete"


@pytest.mark.parametrize(
    ("tool_setup", "failure_kind"),
    (("missing", "swiftc-tool-missing"), ("old", "swiftc-version-too-old")),
)
def test_swift_missing_and_old_tools_reach_unsupported_final_artifacts(
    tmp_path: Path,
    tool_setup: str,
    failure_kind: str,
) -> None:
    host = _host(tmp_path)
    env = {**os.environ, "PATH": ""}
    if tool_setup == "old":
        fake_bin = tmp_path / "fake-bin"
        fake_bin.mkdir()
        tool = fake_bin / "swiftc"
        tool.write_text(
            "#!/bin/sh\necho 'Apple Swift version 5.9.2 (swiftlang-5.9.2)'\n",
            encoding="utf-8",
        )
        tool.chmod(0o755)
        env["PATH"] = str(fake_bin)

    _, findings = _pipeline(
        SKILL,
        host,
        host / "reports" / tool_setup,
        host / "Sources" / "BillingCore",
        expected_returncode=2,
        env=env,
    )

    assert findings["status"] == "unsupported"
    assert findings["outcome"] == "unsupported"
    assert findings["analysis"]["swift"]["failure_kind"] == failure_kind
    assert findings["summary"]["findings_total"] == 0


def test_swift_no_eligible_target_and_exact_copied_closure_are_honest(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    _, unsupported = _pipeline(
        SKILL,
        host,
        host / "reports" / "excluded",
        host / "vendor",
        expected_returncode=2,
    )
    assert unsupported["status"] == "unsupported"
    assert unsupported["analysis"]["swift"]["failure_kind"] == "no-eligible-swift-source"

    source = _add_omnibus(host)
    copied = tmp_path / "on-demand" / "find-omnibus"
    shutil.copytree(SKILL, copied)
    assert {
        path.relative_to(copied).as_posix()
        for path in copied.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(SKILL).as_posix()
        for path in SKILL.rglob("*")
        if path.is_file()
    }
    assert {
        path.relative_to(copied).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in copied.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(SKILL).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in SKILL.rglob("*")
        if path.is_file()
    }
    before = _source_state(host)
    _, findings = _pipeline(
        copied,
        host,
        host / "reports" / "copied",
        source.parent,
        expected_returncode=0,
        isolated=True,
        scout=True,
    )
    assert findings["status"] == "complete"
    assert findings["analysis"]["swift"]["analyzer"] == "swiftc-typecheck-dump-ast"
    assert (copied / "scripts" / "detect_swift_symbols.py").is_file()
    assert _source_state(host) == before
