"""Final-outcome checks for the bounded dependency-free SwiftPM subsystem map."""
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
SCRIPT = ROOT / ".claude" / "skills" / "map-subsystem" / "scripts" / "map_swift.py"
FIXTURE = ROOT / "tests" / "fixtures" / "swift-pilot" / "host"
SWIFT = shutil.which("swift")
SOURCEKIT = shutil.which("sourcekit-lsp")
pytestmark = pytest.mark.skipif(
    SWIFT is None or SOURCEKIT is None,
    reason="Swift 6+ and SourceKit-LSP are required for the Swift pilot",
)


def _run(*argv: str, cwd: Path, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _fingerprints(host: Path) -> dict[str, str]:
    rows = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(
            part in {"reports", ".claude", ".engineering", ".agents", "index-build"}
            for part in relative.parts
        ):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _map(
    script: Path,
    host: Path,
    *,
    name: str = "billing",
    target: str = "Sources/BillingCore",
    swift: str | None = None,
    sourcekit: str | None = None,
    minimum: str | None = None,
    output: Path | None = None,
    evidence: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = output or host / ".engineering" / "docs" / "subsystems" / f"{name}.md"
    evidence = evidence or host / "reports" / "map" / name / "swift-map.json"
    argv = [
        sys.executable,
        str(script),
        "--name", name,
        "--target", target,
        "--project-root", str(host),
        "--output", str(output),
        "--evidence", str(evidence),
        "--swift", swift or str(SWIFT),
        "--sourcekit-lsp", sourcekit or str(SOURCEKIT),
    ]
    if minimum:
        argv.extend(["--minimum-swift", minimum])
    return _run(*argv, cwd=host), output, evidence


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_swift_map_reaches_public_surface_target_edge_and_native_smoke(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _fingerprints(host)

    result, output, evidence = _map(SCRIPT, host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    payload = _payload(evidence)
    rendered = output.read_text(encoding="utf-8")
    assert payload["status"] == "complete"
    assert payload["analyzer"] == "swiftpm+swift-build+sourcekit-lsp+symbolgraph"
    assert payload["package"] == {"dependencies": [], "name": "SwiftPilot", "tools_version": "6.0"}
    assert payload["selected_target"] == {
        "name": "BillingCore",
        "path": "Sources/BillingCore",
        "sources": ["Sources/BillingCore/BillingCore.swift"],
        "type": "library",
    }
    public_paths = {row["path"] for row in payload["public_surface"]}
    assert {"Clock", "FixedClock", "Invoice", "InvoiceFormatter", "InvoiceService"} <= public_paths
    assert all(row["access"] == "public" for row in payload["public_surface"])
    assert payload["target_edges"] == [{
        "consumer": "SwiftPilotSmoke",
        "dependency": "BillingCore",
        "file": "Sources/SwiftPilotSmoke/main.swift",
        "import": "BillingCore",
        "line": 1,
        "resolution": "swiftpm_target_dependency+successful_build_index",
    }]
    assert set(payload["native_evidence"]["index"]["targets"]) == {"BillingCore", "SwiftPilotSmoke"}
    assert all(
        row["status"] == "complete"
        for row in payload["native_evidence"]["index"]["targets"].values()
    )
    roles = {(row["path"], row["role"], row["included"]) for row in payload["source_inventory"]}
    assert ("Sources/BillingCore/BillingCore.swift", "source", True) in roles
    assert ("Tests/BillingCoreTests/InvoiceServiceTests.swift", "test", False) in roles
    assert ("generated/GeneratedInvoice.swift", "generated", False) in roles
    assert ("vendor/Example/Vendor.swift", "vendor", False) in roles
    assert (".build/Sentinel.swift", "build", False) in roles
    assert ("Package.swift", "configuration", False) in roles
    assert "`BillingCore` → `SwiftPilotSmoke`" in rendered
    assert "conditional compilation" in rendered
    scratch = Path(payload["native_evidence"]["build"]["scratch_path"])
    smoke = _run(str(scratch / "debug" / "swift-pilot-smoke"), cwd=host)
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    assert smoke.stdout.strip() == "invoice:INV-42:fixed-2026"


def test_swift_map_replaces_stale_success_after_malformed_and_clean_reruns(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    source = host / "Sources" / "BillingCore" / "BillingCore.swift"
    consumer = host / "Sources" / "SwiftPilotSmoke" / "main.swift"
    original_source = source.read_text(encoding="utf-8")
    original_consumer = consumer.read_text(encoding="utf-8")

    valid, output, evidence = _map(SCRIPT, host, name="transition")
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert _payload(evidence)["status"] == "complete"
    valid_doc = output.read_text(encoding="utf-8")

    source.write_text(original_source + "\nlet malformed: = 1\n", encoding="utf-8")
    malformed, _, malformed_evidence = _map(SCRIPT, host, name="transition")
    assert malformed.returncode == 2
    malformed_payload = _payload(malformed_evidence)
    assert malformed_payload["status"] == "failed"
    assert malformed_payload["failure_kind"] == "native_build_failed"
    assert "Status: **failed**" in output.read_text(encoding="utf-8")
    assert output.read_text(encoding="utf-8") != valid_doc

    source.write_text("struct InternalOnly {}\n", encoding="utf-8")
    consumer.write_text('print("clean")\n', encoding="utf-8")
    clean, _, clean_evidence = _map(SCRIPT, host, name="transition")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    clean_payload = _payload(clean_evidence)
    assert clean_payload["status"] == "complete"
    assert clean_payload["public_surface"] == []
    assert clean_payload["target_edges"] == []
    assert "No public declarations" in output.read_text(encoding="utf-8")
    source.write_text(original_source, encoding="utf-8")
    consumer.write_text(original_consumer, encoding="utf-8")


def test_swift_map_rejects_missing_old_limited_and_zero_exit_target_failure(tmp_path: Path) -> None:
    missing_host = _copy_host(tmp_path, "missing")
    missing, _, missing_evidence = _map(
        SCRIPT,
        missing_host,
        name="missing",
        sourcekit=str(missing_host / "no-sourcekit"),
    )
    assert missing.returncode == 0
    assert _payload(missing_evidence)["failure_kind"] == "sourcekit_lsp_missing"

    old_host = _copy_host(tmp_path, "old")
    old, _, old_evidence = _map(SCRIPT, old_host, name="old", minimum="99.0")
    assert old.returncode == 0
    assert _payload(old_evidence)["failure_kind"] == "swift_version_too_old"

    limited_host = _copy_host(tmp_path, "limited")
    limited_tool = _fake_tool(limited_host / "limited-sourcekit", "exit 0\n")
    limited, _, limited_evidence = _map(
        SCRIPT, limited_host, name="limited", sourcekit=str(limited_tool)
    )
    assert limited.returncode == 0, limited.stdout + limited.stderr
    limited_payload = _payload(limited_evidence)
    assert limited_payload["status"] == "partial"
    assert limited_payload["failure_kind"] == "sourcekit_index_incomplete"

    mixed_host = _copy_host(tmp_path, "mixed-target")
    mixed_tool = _fake_tool(
        mixed_host / "mixed-sourcekit",
        f"""cat <<'EOF'
Preparing BillingCore
Build of target: 'BillingCore' complete!
Finished with exit code 0
Indexing {mixed_host}/Sources/BillingCore/BillingCore.swift
Preparing SwiftPilotSmoke
error: emit-module command failed with exit code 1
Finished with exit code 1
Indexing {mixed_host}/Sources/SwiftPilotSmoke/main.swift
Indexing finished
EOF
exit 0
""",
    )
    mixed, mixed_output, mixed_evidence = _map(
        SCRIPT, mixed_host, name="mixed-target", sourcekit=str(mixed_tool)
    )
    assert mixed.returncode == 2
    mixed_payload = _payload(mixed_evidence)
    assert mixed_payload["status"] == "failed"
    assert mixed_payload["failure_kind"] == "sourcekit_target_failure"
    assert mixed_payload["native_evidence"]["index"]["process_exit"] == 0
    assert mixed_payload["native_evidence"]["index"]["targets"]["SwiftPilotSmoke"]["status"] == "failed"
    assert "Status: **failed**" in mixed_output.read_text(encoding="utf-8")


def test_swift_map_refuses_excluded_symlinked_malformed_and_unsupported_shapes(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    for index, target in enumerate(("Tests/BillingCoreTests", "generated", "vendor/Example", ".build")):
        result, _, evidence = _map(SCRIPT, host, name=f"excluded-{index}", target=target)
        assert result.returncode == 0, result.stdout + result.stderr
        assert _payload(evidence)["failure_kind"] == "excluded_or_missing_target"

    malformed_host = _copy_host(tmp_path, "malformed-manifest")
    (malformed_host / "Package.swift").write_text("not a manifest\n", encoding="utf-8")
    malformed, _, malformed_evidence = _map(SCRIPT, malformed_host, name="malformed-manifest")
    assert malformed.returncode == 2
    assert _payload(malformed_evidence)["failure_kind"] == "swiftpm_manifest_invalid"

    dependency_host = _copy_host(tmp_path, "dependency")
    manifest = dependency_host / "Package.swift"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "products: [",
            'dependencies: [.package(url: "https://example.invalid/pkg", from: "1.0.0")],\n    products: [',
        ),
        encoding="utf-8",
    )
    dependency, _, dependency_evidence = _map(SCRIPT, dependency_host, name="dependency")
    assert dependency.returncode in {0, 2}
    if dependency_evidence.is_file():
        assert _payload(dependency_evidence)["status"] in {"unsupported", "failed"}

    linked_host = _copy_host(tmp_path, "linked")
    external = tmp_path / "External.swift"
    external.write_text("public struct External {}\n", encoding="utf-8")
    os.symlink(external, linked_host / "Sources" / "BillingCore" / "Linked.swift")
    linked, _, linked_evidence = _map(SCRIPT, linked_host, name="linked")
    assert linked.returncode == 0, linked.stdout + linked.stderr
    assert _payload(linked_evidence)["failure_kind"] == "unsafe_source"

    victim = host / "Sources" / "BillingCore" / "BillingCore.swift"
    unsafe, _, _ = _map(SCRIPT, host, name="unsafe", output=victim)
    assert unsafe.returncode == 2
    assert "output must stay" in unsafe.stderr


def test_swift_map_copied_single_file_closure_has_no_checkout_dependency(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    installed = host / ".agents" / "skills" / "map-subsystem" / "scripts" / "map_swift.py"
    installed.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, installed)
    before = _fingerprints(host)

    result, _, evidence = _map(installed, host, name="copied")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _payload(evidence)["status"] == "complete"
    assert _fingerprints(host) == before
    closure = installed.read_text(encoding="utf-8")
    assert str(ROOT) not in closure
    assert "tree_sitter" not in closure
    assert "SwiftSyntax" not in closure
