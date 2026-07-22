"""Final-outcome evidence for the bounded SwiftPM move-path cohort."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MOVE = ROOT / ".claude/skills/move-path/scripts/move_path.py"
SKILL = MOVE.parents[1]
FIXTURE = ROOT / "tests/fixtures/swift-pilot/host"
SWIFT = shutil.which("swift")
SWIFTC = shutil.which("swiftc")
pytestmark = pytest.mark.skipif(not SWIFT or not SWIFTC, reason="Swift 6 toolchain required")


def _module():
    spec = importlib.util.spec_from_file_location("swift_move_path_under_test", MOVE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    return host


def _plan(host: Path, source: str = "Sources/BillingCore/", destination: str = "Sources/InvoicingCore/") -> Path:
    plan = host / "move.json"
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "moves": [{"from": source, "to": destination, "mode": "directory"}],
                "rewrite": {"code_imports": "update-swift"},
                "swift": {
                    "binary": SWIFT,
                    "swiftc_binary": SWIFTC,
                    "smoke_product": "swift-pilot-smoke",
                    "smoke_expected_stdout": "invoice:INV-42:fixed-2026\n",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return plan


def _run(module, host: Path, plan: Path, mode: str):
    return module.run_plan(
        plan_path=plan,
        project_root=host,
        mode=mode,
        report_dir=host / ".engineering/local/move-path",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_swiftpm_preview_apply_check_and_exact_native_outcome(tmp_path: Path) -> None:
    module = _module()
    host = _host(tmp_path)
    plan = _plan(host)
    excluded = [
        host / ".build/Sentinel.swift",
        host / "Tests/BillingCoreTests/InvoiceServiceTests.swift",
        host / "generated/GeneratedInvoice.swift",
        host / "vendor/Example/Vendor.swift",
    ]
    excluded_before = {path: _sha(path) for path in excluded}

    preview = _run(module, host, plan, "dry-run")

    assert preview["swift"]["status"] == "complete"
    assert preview["swift"]["target"] == "BillingCore"
    assert preview["swift"]["source_manifest"]["before_fingerprint"]
    assert preview["swift"]["source_manifest"]["expected_fingerprint"]
    assert preview["swift"]["source_manifest"]["actual_fingerprint"] is None
    assert preview["swift"]["native"]["dump_package"]["passed"] is True
    assert preview["swift"]["native"]["typecheck_preflight"]["passed"] is True
    assert preview["swift"]["exact_changes"] == [
        {
            "file_before": "Package.swift",
            "file_after": "Package.swift",
            "kind": "swiftpm_target_path",
            "old": '.target(name: "BillingCore")',
            "new": '.target(name: "BillingCore", path: "Sources/InvoicingCore")',
            "target_before": "Sources/BillingCore",
            "target_after": "Sources/InvoicingCore",
        }
    ]
    assert "rename Sources/BillingCore/BillingCore.swift" in preview["swift"]["review_diff"]
    assert (host / "Sources/BillingCore/BillingCore.swift").is_file()
    assert not (host / "Sources/InvoicingCore").exists()

    applied = _run(module, host, plan, "apply")

    assert applied["swift"]["status"] == "complete"
    assert applied["swift"]["rolled_back"] is False
    assert applied["swift"]["native"]["build"]["passed"] is True
    assert applied["swift"]["native"]["smoke"]["passed"] is True
    assert applied["swift"]["native"]["smoke"]["stdout"] == "invoice:INV-42:fixed-2026\n"
    exact = applied["swift"]["native"]["exact_diff"]
    assert exact["passed"] is True
    assert exact["actual_fingerprint"] == exact["expected_fingerprint"]
    assert applied["swift"]["source_manifest"]["actual_fingerprint"] == exact["actual_fingerprint"]
    assert (host / "Sources/InvoicingCore/BillingCore.swift").is_file()
    assert not (host / "Sources/BillingCore").exists()
    assert '.target(name: "BillingCore", path: "Sources/InvoicingCore")' in (host / "Package.swift").read_text(encoding="utf-8")
    assert "import BillingCore" in (host / "Sources/SwiftPilotSmoke/main.swift").read_text(encoding="utf-8")
    for path in excluded:
        assert _sha(path) == excluded_before[path]

    checked = _run(module, host, plan, "check")
    assert checked["swift"]["status"] == "complete"
    assert checked["swift"]["native"]["build"]["passed"] is True
    assert checked["swift"]["native"]["smoke"]["passed"] is True


def test_swiftpm_lifecycle_and_dynamic_or_reflective_shapes(tmp_path: Path) -> None:
    module = _module()
    host = _host(tmp_path / "lifecycle")
    plan = _plan(host)
    source = host / "Sources/BillingCore/BillingCore.swift"
    original = source.read_bytes()

    assert _run(module, host, plan, "dry-run")["swift"]["status"] == "complete"
    source.write_text("struct Broken {\n", encoding="utf-8")
    failed = _run(module, host, plan, "dry-run")
    assert failed["swift"]["status"] == "failed"
    assert any(item["kind"] == "swift_typecheck_failed" for item in failed["swift"]["blocked"])
    report = host / ".engineering/local/move-path/report.json"
    assert json.loads(report.read_text(encoding="utf-8"))["swift"]["status"] == "failed"
    source.write_bytes(original)
    assert _run(module, host, plan, "dry-run")["swift"]["status"] == "complete"
    assert json.loads(report.read_text(encoding="utf-8"))["swift"]["status"] == "complete"

    dynamic = _host(tmp_path / "dynamic")
    dynamic_plan = _plan(dynamic)
    manifest = dynamic / "Package.swift"
    dynamic_text = manifest.read_text(encoding="utf-8")
    dynamic_text = dynamic_text.replace(
        "let package = Package(", 'let coreTarget = "BillingCore"\n\nlet package = Package('
    ).replace('.target(name: "BillingCore")', ".target(name: coreTarget)")
    manifest.write_text(dynamic_text, encoding="utf-8")
    dynamic_result = _run(module, dynamic, dynamic_plan, "dry-run")
    assert dynamic_result["swift"]["status"] == "unsupported"
    assert any(item["kind"] == "swift_manifest_dynamic_or_unsupported_target" for item in dynamic_result["swift"]["blocked"])

    reflective = _host(tmp_path / "reflective")
    reflective_plan = _plan(reflective)
    reflective_source = reflective / "Sources/BillingCore/BillingCore.swift"
    reflective_source.write_text(
        reflective_source.read_text(encoding="utf-8")
        + '\nlet reflectiveSourcePath = "Sources/BillingCore"\n',
        encoding="utf-8",
    )
    partial = _run(module, reflective, reflective_plan, "dry-run")
    assert partial["swift"]["status"] == "partial"
    assert any(item["kind"] == "swift_unproved_reflective_path_identity" for item in partial["swift"]["blocked"])


@pytest.mark.parametrize(
    ("case", "expected_kind"),
    [
        ("symlink", "swift_symlink_boundary"),
        ("generated", "swift_generated_source"),
        ("mixed", "swift_mixed_language_unsupported"),
        ("framework", "swift_framework_or_external_import_unsupported"),
        ("dependency", "swift_dependency_resolution_unsupported"),
        ("xcode", "swift_xcode_project_unsupported"),
        ("resource", "swift_manifest_feature_unsupported"),
        ("plugin", "swift_manifest_feature_unsupported"),
    ],
)
def test_swiftpm_refuses_unproved_boundaries(tmp_path: Path, case: str, expected_kind: str) -> None:
    module = _module()
    host = _host(tmp_path)
    plan = _plan(host)
    source = host / "Sources/BillingCore/BillingCore.swift"
    manifest = host / "Package.swift"
    if case == "symlink":
        (host / "Sources/BillingCore/Linked.swift").symlink_to(source)
    elif case == "generated":
        (host / "Sources/BillingCore/Generated.swift").write_text(
            "// Code generated by fixture. DO NOT EDIT.\nstruct Generated {}\n", encoding="utf-8"
        )
    elif case == "mixed":
        (host / "Sources/BillingCore/Bridge.m").write_text("void bridge(void) {}\n", encoding="utf-8")
    elif case == "framework":
        source.write_text("import Foundation\n" + source.read_text(encoding="utf-8"), encoding="utf-8")
    elif case == "dependency":
        (host / "Package.resolved").write_text("{}\n", encoding="utf-8")
    elif case == "xcode":
        (host / "SwiftPilot.xcodeproj").mkdir()
    elif case == "resource":
        (host / "Sources/BillingCore/Resources").mkdir()
        (host / "Sources/BillingCore/Resources/fixture.txt").write_text("fixture\n", encoding="utf-8")
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                '.target(name: "BillingCore")',
                '.target(name: "BillingCore", resources: [.process("Resources")])',
            ),
            encoding="utf-8",
        )
    elif case == "plugin":
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                '.target(name: "BillingCore"),',
                '.target(name: "BillingCore"),\n        .plugin(name: "FixturePlugin", capability: .buildTool()),',
            ),
            encoding="utf-8",
        )

    result = _run(module, host, plan, "dry-run")

    assert result["swift"]["status"] != "complete"
    assert any(item["kind"] == expected_kind for item in result["swift"]["blocked"])
    with pytest.raises(SystemExit, match="blocked findings prevent apply"):
        _run(module, host, plan, "apply")


def test_swiftpm_refuses_test_tree_move(tmp_path: Path) -> None:
    module = _module()
    host = _host(tmp_path)
    plan = _plan(host, "Tests/BillingCoreTests/", "Tests/InvoicingCoreTests/")

    result = _run(module, host, plan, "dry-run")

    assert result["swift"]["status"] == "unsupported"
    assert any(item["kind"] == "swift_sources_root_target_directory_required" for item in result["swift"]["blocked"])


def test_swiftpm_native_failure_and_unexpected_mutation_roll_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    original_run = subprocess.run
    native = _host(tmp_path / "native")
    native_plan = _plan(native)
    before = {path.relative_to(native).as_posix(): path.read_bytes() for path in native.rglob("*") if path.is_file()}

    def fail_build(argv, *args, **kwargs):
        if len(argv) > 1 and argv[1] == "build":
            return subprocess.CompletedProcess(argv, 1, "", "forced build failure")
        return original_run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fail_build)
    with pytest.raises(SystemExit, match="rolled back"):
        _run(module, native, native_plan, "apply")
    for relative, contents in before.items():
        assert (native / relative).read_bytes() == contents
    assert not (native / "Sources/InvoicingCore").exists()
    rolled = json.loads((native / ".engineering/local/move-path/report.json").read_text(encoding="utf-8"))
    assert rolled["swift"]["rolled_back"] is True

    monkeypatch.setattr(subprocess, "run", original_run)
    outside = _host(tmp_path / "outside")
    outside_plan = _plan(outside)
    unrelated = outside / "generated/GeneratedInvoice.swift"
    unrelated_before = unrelated.read_bytes()

    def mutate_after_smoke(argv, *args, **kwargs):
        result = original_run(argv, *args, **kwargs)
        if Path(str(argv[0])).name == "swift-pilot-smoke":
            unrelated.write_bytes(unrelated.read_bytes() + b"// unexpected\n")
        return result

    monkeypatch.setattr(subprocess, "run", mutate_after_smoke)
    with pytest.raises(SystemExit, match="rolled back"):
        _run(module, outside, outside_plan, "apply")
    assert unrelated.read_bytes() == unrelated_before
    assert (outside / "Sources/BillingCore/BillingCore.swift").is_file()
    exact = json.loads((outside / ".engineering/local/move-path/report.json").read_text(encoding="utf-8"))["swift"]["native"]["exact_diff"]
    assert exact["passed"] is False
    assert "generated/GeneratedInvoice.swift" in exact["changed"]


def test_swiftpm_copied_exact_closure_runs_without_repository_helpers(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    installed = tmp_path / "installed/move-path"
    outside = tmp_path / "outside"
    outside.mkdir()
    shutil.copytree(SKILL, installed)

    result = subprocess.run(
        [
            sys.executable, "-I", "-S", str(installed / "scripts/move_path.py"),
            "--plan", str(plan), "--project-root", str(host),
            "--report-dir", str(host / ".engineering/local/move-path"),
            "--apply", "--json",
        ],
        cwd=outside,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["swift"]["status"] == "complete"
    assert report["swift"]["native"]["build"]["passed"] is True
    assert report["swift"]["native"]["smoke"]["passed"] is True
    assert report["swift"]["native"]["exact_diff"]["passed"] is True
