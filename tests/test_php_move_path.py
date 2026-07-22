"""Final-outcome evidence for the bounded PHP namespace move-path cohort."""
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
MOVE = ROOT / ".claude" / "skills" / "move-path" / "scripts" / "move_path.py"
FIXTURE = ROOT / "tests" / "fixtures" / "php-pilot" / "host"
MALFORMED = ROOT / "tests" / "fixtures" / "php-pilot" / "malformed" / "Broken.php"
PHP = Path("/opt/homebrew/bin/php")
pytestmark = pytest.mark.skipif(not PHP.is_file(), reason="PHP 8.1 or newer is required")


def _module():
    spec = importlib.util.spec_from_file_location("php_move_path_under_test", MOVE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE, host)
    return host


def _plan(host: Path) -> Path:
    plan = host / "move.json"
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "moves": [
                    {
                        "from": "src/Legacy/",
                        "to": "src/Archive/",
                        "mode": "directory",
                    }
                ],
                "reference_scope": {"include": ["**/*.md"]},
                "rewrite": {"code_imports": "update-php"},
                "php": {
                    "binary": str(PHP),
                    "verification_scripts": ["tests/lint.php", "tests/smoke.php"],
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
        report_dir=host / ".engineering" / "local" / "move-path",
    )


def _native(host: Path, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PHP), script], cwd=host, text=True, capture_output=True, check=False
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_php_plan_and_apply_move_namespace_require_and_use_with_native_proof(
    tmp_path: Path,
) -> None:
    module = _module()
    host = _host(tmp_path)
    plan = _plan(host)
    excluded = [
        host / "generated/GeneratedProxy.php",
        host / "build/CompiledContainer.php",
        host / "vendor/example/package/VendorService.php",
        host / "tests/Billing/InvoiceServiceTest.php",
    ]
    excluded_before = {path: _sha256(path) for path in excluded}

    dry = _run(module, host, plan, "dry-run")

    assert dry["mode"] == "dry-run"
    assert dry["php"]["status"] == "complete"
    assert dry["php"]["tooling"]["php"]["path"] == str(PHP)
    assert {item["kind"] for item in dry["php"]["exact_changes"]} == {
        "php_namespace",
        "php_require_path",
        "php_name",
    }
    assert {item["file_before"] for item in dry["php"]["exact_changes"]} == {
        "src/Legacy/LegacyInvoiceFormatter.php",
        "tests/smoke.php",
    }
    assert "tests/Billing/InvoiceServiceTest.php" in dry["php"]["excluded_files"]
    assert "tests/smoke.php" in dry["php"]["verification_files"]
    assert (host / "src/Legacy/LegacyInvoiceFormatter.php").is_file()
    assert not (host / "src/Archive").exists()

    applied = _run(module, host, plan, "apply")

    assert applied["php"]["status"] == "complete"
    native = applied["php"]["native"]
    assert all(native[key]["passed"] for key in ("lint_preflight", "smoke_preflight", "lint", "smoke"))
    assert native["exact_diff"]["passed"] is True
    assert native["exact_diff"]["before_fingerprint"]
    assert native["exact_diff"]["actual_fingerprint"] == native["exact_diff"]["expected_fingerprint"]
    moved = host / "src/Archive/LegacyInvoiceFormatter.php"
    assert moved.is_file()
    assert "namespace Acme\\Archive;" in moved.read_text(encoding="utf-8")
    smoke = (host / "tests/smoke.php").read_text(encoding="utf-8")
    assert "/src/Archive/LegacyInvoiceFormatter.php" in smoke
    assert "use Acme\\Archive\\LegacyInvoiceFormatter;" in smoke
    assert not (host / "src/Legacy").exists()
    for path in excluded:
        assert _sha256(path) == excluded_before[path]
    stale_files = []
    for path in host.rglob("*.php"):
        if path.is_file() and not path.is_symlink():
            text = path.read_text(encoding="utf-8")
            if "Acme\\Legacy" in text or "/src/Legacy/" in text:
                stale_files.append(path.relative_to(host).as_posix())
    assert stale_files == []
    assert _native(host, "tests/lint.php").returncode == 0
    assert _native(host, "tests/smoke.php").returncode == 0
    artifact = host / ".engineering/local/move-path/report.json"
    assert artifact.is_file()
    assert json.loads(artifact.read_text(encoding="utf-8"))["php"]["status"] == "complete"

    checked = _run(module, host, plan, "check")
    assert checked["mode"] == "check"
    assert checked["php"]["status"] == "complete"
    assert checked["php"]["native"]["lint"]["passed"] is True
    assert checked["php"]["native"]["smoke"]["passed"] is True


@pytest.mark.parametrize(
    "relative",
    [
        "generated/OldReference.php",
        "build/OldReference.php",
        "vendor/example/package/OldReference.php",
        "tests/Billing/OldReferenceTest.php",
    ],
)
def test_php_excluded_roles_are_never_rewritten_and_block_stale_identity(
    tmp_path: Path, relative: str
) -> None:
    module = _module()
    host = _host(tmp_path)
    plan = _plan(host)
    excluded = host / relative
    excluded.parent.mkdir(parents=True, exist_ok=True)
    excluded.write_text(
        "<?php\nnamespace Excluded;\nuse Acme\\Legacy\\LegacyInvoiceFormatter;\n",
        encoding="utf-8",
    )
    before = excluded.read_bytes()

    report = _run(module, host, plan, "dry-run")

    assert report["php"]["status"] == "unsupported"
    assert any(
        item["kind"] == "php_excluded_old_identity" and item["path"] == relative
        for item in report["php"]["blocked"]
    )
    assert excluded.read_bytes() == before
    with pytest.raises(SystemExit, match="blocked findings prevent apply"):
        _run(module, host, plan, "apply")
    assert excluded.read_bytes() == before
    assert (host / "src/Legacy").is_dir()


def test_php_refuses_malformed_generated_and_symlinked_move_inputs_and_refreshes_lifecycle(
    tmp_path: Path,
) -> None:
    module = _module()

    lifecycle = _host(tmp_path / "lifecycle")
    lifecycle_plan = _plan(lifecycle)
    clean = _run(module, lifecycle, lifecycle_plan, "dry-run")
    assert clean["php"]["status"] == "complete"
    moved_source = lifecycle / "src/Legacy/LegacyInvoiceFormatter.php"
    original = moved_source.read_bytes()
    shutil.copyfile(MALFORMED, moved_source)
    failed = _run(module, lifecycle, lifecycle_plan, "dry-run")
    assert failed["php"]["status"] == "failed"
    assert "src/Legacy/LegacyInvoiceFormatter.php" in failed["php"]["error"]
    report_path = lifecycle / ".engineering/local/move-path/report.json"
    assert json.loads(report_path.read_text(encoding="utf-8"))["php"]["status"] == "failed"
    moved_source.write_bytes(original)
    recovered = _run(module, lifecycle, lifecycle_plan, "dry-run")
    assert recovered["php"]["status"] == "complete"
    assert json.loads(report_path.read_text(encoding="utf-8"))["php"]["status"] == "complete"

    dynamic = _host(tmp_path / "dynamic")
    dynamic_plan = _plan(dynamic)
    consumer = dynamic / "src/Consumer/CheckoutService.php"
    consumer.write_text(
        consumer.read_text(encoding="utf-8").replace(
            "final class CheckoutService",
            "// Reflection identity: Acme\\Legacy\\LegacyInvoiceFormatter\nfinal class CheckoutService",
        ),
        encoding="utf-8",
    )
    dynamic_report = _run(module, dynamic, dynamic_plan, "dry-run")
    assert dynamic_report["php"]["status"] == "partial"
    assert any(
        item["kind"] == "php_dynamic_old_identity"
        for item in dynamic_report["php"]["blocked"]
    )

    generated = _host(tmp_path / "generated")
    generated_plan = _plan(generated)
    generated_source = generated / "src/Legacy/Generated.php"
    generated_source.write_text(
        "<?php\n// Code generated by fixture. DO NOT EDIT.\nnamespace Acme\\Legacy;\n",
        encoding="utf-8",
    )
    generated_report = _run(module, generated, generated_plan, "dry-run")
    assert generated_report["php"]["status"] == "unsupported"
    assert any(item["kind"] == "php_generated_source" for item in generated_report["php"]["blocked"])

    linked = _host(tmp_path / "linked")
    linked_plan = _plan(linked)
    (linked / "src/Legacy/linked.php").symlink_to(linked / "src/Billing/InvoiceService.php")
    linked_report = _run(module, linked, linked_plan, "dry-run")
    assert linked_report["php"]["status"] == "unsupported"
    assert any(item["kind"] == "php_symlink_in_namespace" for item in linked_report["php"]["blocked"])


def test_php_native_failure_and_outside_diff_are_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    host = _host(tmp_path / "native")
    plan = _plan(host)
    moved_before = (host / "src/Legacy/LegacyInvoiceFormatter.php").read_bytes()
    smoke_before = (host / "tests/smoke.php").read_bytes()
    original_runner = module.run_php_script
    calls = 0

    def fail_post_apply(root, php, script):
        nonlocal calls
        calls += 1
        if calls == 3:
            return {
                "argv": [php, script],
                "passed": False,
                "returncode": 1,
                "stdout": "",
                "stderr": "forced",
            }
        return original_runner(root, php, script)

    monkeypatch.setattr(module, "run_php_script", fail_post_apply)
    with pytest.raises(SystemExit, match="rolled back"):
        _run(module, host, plan, "apply")
    assert (host / "src/Legacy/LegacyInvoiceFormatter.php").read_bytes() == moved_before
    assert not (host / "src/Archive").exists()
    assert (host / "tests/smoke.php").read_bytes() == smoke_before
    rolled_back = json.loads(
        (host / ".engineering/local/move-path/report.json").read_text(encoding="utf-8")
    )
    assert rolled_back["php"]["status"] == "failed"
    assert rolled_back["php"]["rolled_back"] is True

    monkeypatch.setattr(module, "run_php_script", original_runner)
    outside = _host(tmp_path / "outside-diff")
    outside_plan = _plan(outside)
    unrelated = outside / "src/Billing/InvoiceService.php"
    unrelated_before = unrelated.read_bytes()
    calls = 0

    def mutate_outside_diff(root, php, script):
        nonlocal calls
        calls += 1
        result = original_runner(root, php, script)
        if calls == 3:
            unrelated.write_bytes(unrelated.read_bytes() + b"\n// native side effect\n")
        return result

    monkeypatch.setattr(module, "run_php_script", mutate_outside_diff)
    with pytest.raises(SystemExit, match="rolled back"):
        _run(module, outside, outside_plan, "apply")
    assert unrelated.read_bytes() == unrelated_before
    assert (outside / "src/Legacy/LegacyInvoiceFormatter.php").is_file()
    exact = json.loads(
        (outside / ".engineering/local/move-path/report.json").read_text(encoding="utf-8")
    )["php"]["native"]["exact_diff"]
    assert exact["passed"] is False
    assert "src/Billing/InvoiceService.php" in exact["changed"]


def test_php_copied_on_demand_closure_runs_without_repository_helpers(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    installed = tmp_path / "installed/move-path"
    outside = tmp_path / "outside"
    outside.mkdir()
    shutil.copytree(MOVE.parents[1], installed)

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(installed / "scripts/move_path.py"),
            "--plan",
            str(plan),
            "--project-root",
            str(host),
            "--report-dir",
            str(host / ".engineering/local/move-path"),
            "--apply",
            "--json",
        ],
        cwd=outside,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["php"]["status"] == "complete"
    assert report["php"]["native"]["lint"]["passed"] is True
    assert report["php"]["native"]["smoke"]["passed"] is True
