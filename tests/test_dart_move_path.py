"""Final-outcome contract for one evidence-authorized Dart library move."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude/skills/move-path/scripts/dart_library_move.py"
GENERIC_MOVE = ROOT / ".claude/skills/move-path/scripts/move_path.py"
PYTHON = Path("/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python")  # host-ref-allow: required frozen P7 runtime
DART = Path("/opt/homebrew/bin/dart")

pytestmark = pytest.mark.skipif(
    not (PYTHON.is_file() and DART.is_file()),
    reason="the frozen product Python and Dart 3.12 SDK are required",
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    _write(
        host / "pubspec.yaml",
        """name: dart_move_host
environment:
  sdk: '>=3.12.0 <3.13.0'
""",
    )
    _write(
        host / ".dart_tool/package_config.json",
        json.dumps(
            {
                "configVersion": 2,
                "packages": [
                    {
                        "name": "dart_move_host",
                        "rootUri": "../",
                        "packageUri": "lib/",
                        "languageVersion": "3.12",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
    )
    _write(
        host / "lib/dart_move_host.dart",
        "export 'src/legacy/invoice_service.dart';\n",
    )
    _write(
        host / "lib/src/legacy/invoice_service.dart",
        """import '../model/invoice.dart';

class InvoiceService {
  String render(Invoice invoice) => '${invoice.id}:${invoice.cents}';
}
""",
    )
    _write(
        host / "lib/src/model/invoice.dart",
        """class Invoice {
  const Invoice(this.id, this.cents);

  final String id;
  final int cents;
}
""",
    )
    _write(
        host / "lib/src/relative_consumer.dart",
        """import 'legacy/invoice_service.dart';
import 'model/invoice.dart';

String renderRelative() => InvoiceService().render(const Invoice('REL', 10));
""",
    )
    _write(
        host / "lib/src/package_consumer.dart",
        """import 'package:dart_move_host/src/legacy/invoice_service.dart';
import 'package:dart_move_host/src/model/invoice.dart';

String renderPackage() => InvoiceService().render(const Invoice('PKG', 20));
""",
    )
    _write(
        host / "lib/src/internal_exports.dart",
        "export 'legacy/invoice_service.dart' show InvoiceService;\n",
    )
    _write(
        host / "bin/smoke.dart",
        """import 'package:dart_move_host/dart_move_host.dart';
import 'package:dart_move_host/src/model/invoice.dart';

void main() {
  print(InvoiceService().render(const Invoice('INV-42', 125)));
}
""",
    )
    _write(
        host / "test/native_test.dart",
        """import 'package:dart_move_host/dart_move_host.dart';
import 'package:dart_move_host/src/model/invoice.dart';

void main() {
  final actual = InvoiceService().render(const Invoice('INV-42', 125));
  if (actual != 'INV-42:125') {
    throw StateError(actual);
  }
}
""",
    )
    return host


def _plan(
    host: Path,
    *,
    dart: Path = DART,
    source: str = "lib/src/legacy/invoice_service.dart",
    destination: str = "lib/src/billing/internal/invoice_service.dart",
    mode: str = "file",
) -> Path:
    path = host / "move-plan.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "moves": [
                    {
                        "from": source,
                        "to": destination,
                        "mode": mode,
                    }
                ],
                "rewrite": {"code_imports": "update-dart"},
                "dart": {
                    "binary": str(dart),
                    "host_scope": "disposable",
                    "package_config": ".dart_tool/package_config.json",
                    "native_test": "test/native_test.dart",
                    "smoke": "bin/smoke.dart",
                    "smoke_expected_stdout": "INV-42:125\n",
                    "public_barrels": ["lib/dart_move_host.dart"],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


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
        str(PYTHON),
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
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    report_path = report_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    return result, report, report_dir


def _preview(host: Path, plan: Path, *, script: Path = SCRIPT, cwd: Path | None = None):
    result, report, report_dir = _invoke(host, plan, "dry-run", script=script, cwd=cwd)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence_path = report_dir / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["evidence_sha256"] == report["dart"]["evidence_sha256"]
    return report, evidence_path, evidence


def test_dart_nontrivial_move_rewrites_all_resolved_edges_and_preserves_barrel(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    before = _tree(host)

    preview, evidence_path, evidence = _preview(host, plan)

    assert preview["dart"]["status"] == "complete"
    assert preview["dart"]["mode"] == "dry-run"
    assert preview["dart"]["rolled_back"] is False
    assert _tree(host) == before
    kinds = {row["kind"] for row in preview["dart"]["exact_changes"]}
    assert kinds == {"import", "export"}
    assert len(preview["dart"]["exact_changes"]) == 5
    assert preview["dart"]["public_barrels_preserved"] == ["lib/dart_move_host.dart"]
    assert evidence["source_tree_sha256"] == preview["dart"]["source_tree_sha256"]

    result, applied, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert applied["dart"]["status"] == "complete"
    assert applied["dart"]["rolled_back"] is False
    assert applied["dart"]["native_postflight"]["status"] == "complete"
    assert applied["dart"]["exact_after_tree"]["passed"] is True
    destination = host / "lib/src/billing/internal/invoice_service.dart"
    assert destination.is_file()
    assert not (host / "lib/src/legacy/invoice_service.dart").exists()
    assert "../../model/invoice.dart" in destination.read_text(encoding="utf-8")
    assert "billing/internal/invoice_service.dart" in (
        host / "lib/src/package_consumer.dart"
    ).read_text(encoding="utf-8")
    assert "billing/internal/invoice_service.dart" in (
        host / "lib/dart_move_host.dart"
    ).read_text(encoding="utf-8")
    assert "package:dart_move_host/dart_move_host.dart" in (
        host / "test/native_test.dart"
    ).read_text(encoding="utf-8")

    checked, check_report, _ = _invoke(host, plan, "check", evidence=evidence_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert check_report["dart"]["status"] == "complete"
    assert check_report["dart"]["old_identity_remaining"] == []
    assert check_report["dart"]["further_edits"] == []


def test_dart_leaf_directory_move_uses_the_same_resolved_transaction(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(
        host,
        source="lib/src/legacy",
        destination="lib/src/billing/internal",
        mode="directory",
    )

    preview, evidence_path, evidence = _preview(host, plan)
    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert preview["dart"]["move"]["mode"] == "directory"
    assert report["dart"]["exact_after_tree"]["passed"] is True
    assert (host / "lib/src/billing/internal/invoice_service.dart").is_file()
    assert not (host / "lib/src/legacy").exists()


def test_dart_stale_evidence_refuses_without_touching_current_source(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    _, evidence_path, evidence = _preview(host, plan)
    consumer = host / "lib/src/relative_consumer.dart"
    consumer.write_text(consumer.read_text(encoding="utf-8") + "\n// reviewed change\n")
    before_apply = _tree(host)

    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 2
    assert report["dart"]["status"] == "failed"
    assert report["dart"]["failure_kind"] == "stale_move_evidence"
    assert _tree(host) == before_apply


def test_dart_partial_rerun_removes_prior_mutation_authority(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    _, evidence_path, _ = _preview(host, plan)
    _write(
        host / "lib/src/dynamic_loader.dart",
        """String deferredLibraryIdentity() =>
    'package:dart_move_host/src/legacy/invoice_service.dart';
""",
    )
    before_rerun = _tree(host)

    result, report, _ = _invoke(host, plan, "dry-run")

    assert result.returncode == 0
    assert report["dart"]["status"] == "partial"
    assert not evidence_path.exists()
    assert _tree(host) == before_rerun


@pytest.mark.parametrize("uncertainty", ["dynamic", "unresolved"])
def test_dart_unresolved_or_dynamic_uncertainty_refuses_and_preserves_bytes(
    tmp_path: Path, uncertainty: str
) -> None:
    host = _host(tmp_path, uncertainty)
    if uncertainty == "dynamic":
        _write(
            host / "lib/src/dynamic_loader.dart",
            """String deferredLibraryIdentity() =>
    'package:dart_move_host/src/legacy/invoice_service.dart';
""",
        )
    else:
        _write(
            host / "lib/src/platform.dart",
            "export 'platform_stub.dart' if (dart.library.io) 'platform_io.dart';\n",
        )
        _write(host / "lib/src/platform_stub.dart", "String platform() => 'stub';\n")
        _write(host / "lib/src/platform_io.dart", "String platform() => 'io';\n")
    plan = _plan(host)
    before = _tree(host)

    result, report, _ = _invoke(host, plan, "dry-run")

    assert result.returncode == 0
    assert report["dart"]["status"] == "partial"
    assert any(
        row["kind"] in {"dart_unproved_dynamic_identity", "conditional_configuration"}
        for row in report["dart"]["blocked"]
    )
    assert _tree(host) == before
    apply, _, _ = _invoke(host, plan, "apply")
    assert apply.returncode == 2
    assert _tree(host) == before


@pytest.mark.parametrize("boundary", ["generated", "symlink", "part", "public-package"])
def test_dart_generated_symlink_part_and_public_package_moves_refuse_before_analysis(
    tmp_path: Path, boundary: str
) -> None:
    host = _host(tmp_path, boundary)
    plan_kwargs: dict[str, str] = {}
    if boundary == "generated":
        generated = host / "lib/src/generated/invoice_service.g.dart"
        generated.parent.mkdir(parents=True)
        (host / "lib/src/legacy/invoice_service.dart").rename(generated)
        plan_kwargs.update(
            source="lib/src/generated/invoice_service.g.dart",
            destination="lib/src/billing/invoice_service.g.dart",
        )
    elif boundary == "symlink":
        source = host / "lib/src/legacy/invoice_service.dart"
        external = tmp_path / "External.dart"
        external.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(external)
    elif boundary == "part":
        (host / "lib/src/legacy/invoice_service.dart").write_text(
            "part of dart_move_host;\n",
            encoding="utf-8",
        )
    else:
        plan_kwargs.update(
            source="lib/dart_move_host.dart",
            destination="lib/renamed_host.dart",
        )
    plan = _plan(host, **plan_kwargs)
    before = _tree(host)

    result, report, _ = _invoke(host, plan, "dry-run")

    assert result.returncode == 0
    assert report["dart"]["status"] == "partial"
    assert report["dart"]["blocked"]
    assert _tree(host) == before
    apply, _, _ = _invoke(host, plan, "apply")
    assert apply.returncode == 2
    assert _tree(host) == before


def test_dart_native_test_failure_rolls_back_exact_source_tree(tmp_path: Path) -> None:
    host = _host(tmp_path)
    wrapper = host / "fake-dart"
    wrapper.write_text(
        "#!/bin/sh\n"
        "case \"${1:-}\" in\n"
        "*test/native_test.dart) if [ -f lib/src/billing/internal/invoice_service.dart ]; then\n"
        "  echo forced-native-test-failure >&2\n"
        "  exit 9\n"
        "fi ;;\n"
        "esac\n"
        f"exec {json.dumps(str(DART))} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    plan = _plan(host, dart=wrapper)
    _, evidence_path, evidence = _preview(host, plan)
    before_apply = _tree(host)

    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 2
    assert report["dart"]["status"] == "failed"
    assert report["dart"]["failure_kind"] == "direct_test_failed"
    assert report["dart"]["rolled_back"] is True
    assert _tree(host) == before_apply
    assert (host / "lib/src/legacy/invoice_service.dart").is_file()
    assert not (host / "lib/src/billing/internal/invoice_service.dart").exists()


def test_dart_external_library_closure_runs_from_outside_repo(tmp_path: Path) -> None:
    host = _host(tmp_path)
    plan = _plan(host)
    library = tmp_path / "installed/on-demand"
    copied_move = library / "move-path/scripts/dart_library_move.py"
    copied_move.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, copied_move)
    for relative in (
        "dart_project_snapshot.py",
        "scripts/dart_syntax_facts.py",
        "tool/bin/dart_syntax_facts.dart",
        "tool/pubspec.yaml",
        "tool/pubspec.lock",
    ):
        destination = library / "_dart" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ".claude/skills/_dart" / relative, destination)
    copied_provider = library / "map-subsystem/scripts/dart_lsp_facts.py"
    copied_provider.parent.mkdir(parents=True)
    shutil.copy2(
        ROOT / ".claude/skills/map-subsystem/scripts/dart_lsp_facts.py",
        copied_provider,
    )
    outside = tmp_path / "outside"
    outside.mkdir()

    _, evidence_path, evidence = _preview(host, plan, script=copied_move, cwd=outside)
    result, report, _ = _invoke(
        host,
        plan,
        "apply",
        script=copied_move,
        cwd=outside,
        evidence=evidence_path,
        approval=evidence["evidence_sha256"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert report["dart"]["status"] == "complete"
    assert (host / "lib/src/billing/internal/invoice_service.dart").is_file()
    source = copied_move.read_text(encoding="utf-8")
    assert str(ROOT) not in source
    assert "package:analyzer/src/" not in source


def test_non_dart_move_path_behavior_is_preserved(tmp_path: Path) -> None:
    host = tmp_path / "generic"
    _write(host / "docs/old.md", "# Old\n")
    _write(host / "README.md", "See [the guide](docs/old.md).\n")
    plan = host / "moves.json"
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "moves": [{"from": "docs/old.md", "to": "docs/new.md"}],
                "reference_scope": {"include": ["**/*.md"], "exclude": []},
                "rewrite": {
                    "markdown_links": "update",
                    "markdown_images": "update",
                    "html_href_src": "update",
                    "backtick_paths": "update",
                    "exact_text_paths": "suggest",
                    "code_imports": "ignore",
                },
                "safety": {
                    "require_clean_touched_files": False,
                    "fail_on_broken_links": True,
                    "fail_on_blocked": True,
                },
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            str(PYTHON),
            str(GENERIC_MOVE),
            "--plan",
            str(plan),
            "--project-root",
            str(host),
            "--report-dir",
            str(host / "reports/generic"),
            "--dry-run",
            "--json",
        ],
        cwd=host,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["auto_rewrites"] == 1
    assert (host / "docs/old.md").is_file()


def test_dart_fixture_and_adapter_closure_manifests_are_content_addressed(
    tmp_path: Path,
) -> None:
    host = _host(tmp_path)
    fixture_rows = _tree(host)
    fixture_digest = hashlib.sha256()
    for path, (_, content, _) in sorted(fixture_rows.items()):
        assert isinstance(content, bytes)
        fixture_digest.update(path.encode() + b"\0" + hashlib.sha256(content).hexdigest().encode() + b"\n")

    closure = [
        SCRIPT,
        ROOT / ".claude/skills/_dart/dart_project_snapshot.py",
        ROOT / ".claude/skills/_dart/scripts/dart_syntax_facts.py",
        ROOT / ".claude/skills/_dart/tool/bin/dart_syntax_facts.dart",
        ROOT / ".claude/skills/_dart/tool/pubspec.yaml",
        ROOT / ".claude/skills/_dart/tool/pubspec.lock",
        ROOT / ".claude/skills/map-subsystem/scripts/dart_lsp_facts.py",
    ]
    closure_digest = hashlib.sha256()
    for path in sorted(closure, key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix()
        closure_digest.update(
            relative.encode()
            + b"\0"
            + hashlib.sha256(path.read_bytes()).hexdigest().encode()
            + b"\n"
        )

    assert fixture_digest.hexdigest() == (
        "315f6217ccc049fbe3fc7d43f8376cabc317729f80d706e416ae7cfaf68f3f3d"
    )
    assert closure_digest.hexdigest() == (
        "74b1ec0903b4ff7d3524850301017e81ab4fe8673d616ec8e4d3f72c61d2d120"
    )
