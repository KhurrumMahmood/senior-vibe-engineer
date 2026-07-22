"""PHP 8.1+/Composer final-artifact proof for the bounded PSR-4 subsystem map."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "map-subsystem"
FIXTURE = ROOT / "tests" / "fixtures" / "php-pilot" / "host"
PHP_PATH = shutil.which("php")
COMPOSER_PATH = shutil.which("composer")
PHP = Path(PHP_PATH) if PHP_PATH else Path("php-unavailable")
COMPOSER = Path(COMPOSER_PATH) if COMPOSER_PATH else Path("composer-unavailable")
pytestmark = pytest.mark.skipif(
    PHP_PATH is None or COMPOSER_PATH is None,
    reason="PHP and Composer pilot tools are required",
)


def _run(
    *args: str,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _native_verify(host: Path) -> None:
    composer = _run(
        str(COMPOSER), "validate", "--no-check-publish", "--no-interaction", cwd=host
    )
    assert composer.returncode == 0, composer.stdout + composer.stderr
    for script in ("tests/lint.php", "tests/smoke.php"):
        completed = _run(str(PHP), script, cwd=host)
        assert completed.returncode == 0, completed.stdout + completed.stderr


def _fingerprints(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and ".claude" not in path.relative_to(host).parts
        and ".agents" not in path.relative_to(host).parts
        and "reports" not in path.relative_to(host).parts
    }


def _map(
    skill: Path,
    host: Path,
    *,
    name: str = "billing",
    target: str = "src/Billing",
    output: Path | None = None,
    evidence: Path | None = None,
    minimum_php: str | None = None,
    minimum_composer: str | None = None,
    composer: Path = COMPOSER,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    output = output or host / ".claude" / "docs" / "subsystems" / f"{name}.md"
    evidence = evidence or host / "reports" / "map" / name / "php-map.json"
    args = [
        str(PHP),
        str(skill / "scripts" / "map_php.php"),
        "--name",
        name,
        "--target",
        target,
        "--project-root",
        str(host),
        "--output",
        str(output),
        "--evidence",
        str(evidence),
        "--composer",
        str(composer),
    ]
    if minimum_php is not None:
        args.extend(["--minimum-php", minimum_php])
    if minimum_composer is not None:
        args.extend(["--minimum-composer", minimum_composer])
    return _run(*args, cwd=host), output, evidence


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _documented_command(skill: Path) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- installed-command:php-map:start -->\n```bash\n(.*?)\n```\n"
        r"<!-- installed-command:php-map:end -->",
        text,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_php_map_reaches_final_artifacts_with_composer_psr4_static_edges(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _native_verify(host)
    before = _fingerprints(host)

    result, output, evidence = _map(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(host) == before
    assert output.is_file()
    payload = _payload(evidence)
    rendered = output.read_text(encoding="utf-8")
    assert payload["status"] == "complete"
    assert payload["language"] == "php"
    assert payload["analyzer"] == "native-php-lint+composer-psr4-static"
    assert payload["target"] == {
        "path": "src/Billing",
        "kind": "psr4_directory",
        "source_files": 1,
        "eligible_files": ["src/Billing/InvoiceService.php"],
        "excluded_files": [],
    }
    assert payload["counts"] == {
        "source_files": 1,
        "declared_symbols": 1,
        "outbound_imports": 1,
        "inbound_imports": 1,
        "external_imports": 0,
        "unresolved_imports": 0,
    }
    assert payload["exported_surface"] == [{
        "name": "InvoiceService",
        "qualified_name": "Acme\\Billing\\InvoiceService",
        "kind": "class",
        "file": "src/Billing/InvoiceService.php",
        "line": 9,
        "resolution": "composer_psr4_declared",
    }]
    assert payload["outbound_imports"] == [{
        "from_symbol": "Acme\\Billing\\InvoiceService",
        "file": "src/Billing/InvoiceService.php",
        "line": 7,
        "import": "Acme\\Shared\\Clock",
        "alias": "Clock",
        "target_symbol": "Acme\\Shared\\Clock",
        "target_file": "src/Shared/Clock.php",
        "resolution": "composer_psr4_first_party",
    }]
    assert payload["inbound_imports"] == [{
        "from_symbol": "Acme\\Consumer\\CheckoutService",
        "file": "src/Consumer/CheckoutService.php",
        "line": 7,
        "import": "Acme\\Billing\\InvoiceService",
        "alias": "InvoiceService",
        "target_symbol": "Acme\\Billing\\InvoiceService",
        "target_file": "src/Billing/InvoiceService.php",
        "resolution": "composer_psr4_first_party",
    }]
    assert payload["completeness"] == {
        "source_inventory": "complete",
        "php_syntax": "complete",
        "composer_manifest": "complete",
        "composer_psr4_static_resolution": "complete",
        "dynamic_calls_and_types": "unavailable",
    }
    assert not any(
        any(part in item.split("/") for part in ("tests", "generated", "vendor", "build"))
        for item in payload["source_inventory"]["eligible_files"]
    )
    assert "Status: **complete**" in rendered
    assert "Composer PSR-4 static resolution" in rendered
    assert "does not resolve dynamic calls" in rendered
    _native_verify(host)


def test_php_map_keeps_unresolved_first_party_imports_partial(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "src" / "Billing" / "MissingClock.php").write_text(
        "<?php\n\ndeclare(strict_types=1);\n\nnamespace Acme\\Billing;\n\n"
        "use Acme\\Shared\\MissingClock;\n\nfinal class MissingClockConsumer {}\n",
        encoding="utf-8",
    )

    result, output, evidence = _map(SKILL, host)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = _payload(evidence)
    assert payload["status"] == "partial"
    assert payload["failure_kind"] == "psr4_resolution_incomplete"
    assert payload["unresolved_imports"] == [{
        "from_symbol": "Acme\\Billing\\MissingClockConsumer",
        "file": "src/Billing/MissingClock.php",
        "line": 7,
        "import": "Acme\\Shared\\MissingClock",
        "alias": "MissingClock",
        "resolution": "unresolved_first_party_psr4",
    }]
    assert payload["completeness"]["composer_psr4_static_resolution"] == "partial"
    rendered = output.read_text(encoding="utf-8")
    assert "Status: **partial**" in rendered
    assert "Acme\\Billing\\InvoiceService" in rendered
    assert "Acme\\Shared\\MissingClock" in rendered


def test_php_map_replaces_same_destination_after_failed_and_recovered_runs(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    valid, output, evidence = _map(SKILL, host, name="transition")
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert _payload(evidence)["status"] == "complete"
    valid_doc = output.read_text(encoding="utf-8")

    broken = host / "src" / "Billing" / "Broken.php"
    broken.write_text(
        "<?php\n\nnamespace Acme\\Billing;\n\nfinal class Broken { public function nope( { }\n",
        encoding="utf-8",
    )
    malformed, _, malformed_evidence = _map(SKILL, host, name="transition")
    assert malformed.returncode == 2
    malformed_payload = _payload(malformed_evidence)
    assert malformed_payload["status"] == "failed"
    assert malformed_payload["failure_kind"] == "syntax_error"
    assert "Broken.php" in malformed_payload["message"]
    assert "Status: **failed**" in output.read_text(encoding="utf-8")
    assert output.read_text(encoding="utf-8") != valid_doc

    broken.unlink()
    recovered, _, recovered_evidence = _map(SKILL, host, name="transition")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert _payload(recovered_evidence)["status"] == "complete"
    assert "Status: **complete**" in output.read_text(encoding="utf-8")
    _native_verify(host)


def test_php_map_reports_old_and_missing_composer_tools_without_stale_success(tmp_path: Path) -> None:
    old_host = _copy_host(tmp_path, "old")
    old, _, old_evidence = _map(SKILL, old_host, name="old", minimum_php="99.0")
    assert old.returncode == 0, old.stdout + old.stderr
    old_payload = _payload(old_evidence)
    assert old_payload["status"] == "unsupported"
    assert old_payload["failure_kind"] == "php_version_too_old"

    missing_host = _copy_host(tmp_path, "missing-composer")
    missing, _, missing_evidence = _map(
        SKILL,
        missing_host,
        name="missing-composer",
        composer=missing_host / "no-composer-here",
    )
    assert missing.returncode == 0, missing.stdout + missing.stderr
    missing_payload = _payload(missing_evidence)
    assert missing_payload["status"] == "unsupported"
    assert missing_payload["failure_kind"] == "composer_tool_missing"

    old_composer_host = _copy_host(tmp_path, "old-composer")
    old_composer, _, old_composer_evidence = _map(
        SKILL, old_composer_host, name="old-composer", minimum_composer="99.0"
    )
    assert old_composer.returncode == 0, old_composer.stdout + old_composer.stderr
    assert _payload(old_composer_evidence)["failure_kind"] == "composer_version_too_old"


def test_php_map_excludes_roles_and_refuses_symlinked_targets_or_sources(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    for index, target in enumerate(("tests/Billing", "generated", "vendor/example/package", "build")):
        excluded, _, evidence = _map(SKILL, host, name=f"excluded-{index}", target=target)
        assert excluded.returncode == 0, excluded.stdout + excluded.stderr
        payload = _payload(evidence)
        assert payload["status"] == "unsupported"
        assert payload["failure_kind"] == "excluded_target"

    role_host = _copy_host(tmp_path, "roles")
    (role_host / "src" / "Billing" / "GeneratedProxy.php").write_text(
        "<?php\n\n// Code generated. DO NOT EDIT.\n\nnamespace Acme\\Billing;\n\nfinal class GeneratedProxy {}\n",
        encoding="utf-8",
    )
    (role_host / "src" / "Billing" / "InvoiceServiceTest.php").write_text(
        "<?php\n\nnamespace Acme\\Billing;\n\nfinal class InvoiceServiceTest {}\n",
        encoding="utf-8",
    )
    roles, _, roles_evidence = _map(SKILL, role_host, name="roles")
    assert roles.returncode == 0, roles.stdout + roles.stderr
    roles_payload = _payload(roles_evidence)
    assert roles_payload["target"]["eligible_files"] == ["src/Billing/InvoiceService.php"]
    assert roles_payload["target"]["excluded_files"] == [
        "src/Billing/GeneratedProxy.php",
        "src/Billing/InvoiceServiceTest.php",
    ]

    external = tmp_path / "external"
    external.mkdir()
    (external / "Outside.php").write_text("<?php\nfinal class Outside {}\n", encoding="utf-8")
    os.symlink(external, host / "src" / "Linked")
    linked_target, _, linked_evidence = _map(SKILL, host, name="linked-target", target="src/Linked")
    assert linked_target.returncode == 0, linked_target.stdout + linked_target.stderr
    assert _payload(linked_evidence)["failure_kind"] == "unsafe_target"
    (host / "src" / "Linked").unlink()

    os.symlink(external / "Outside.php", host / "src" / "Billing" / "Outside.php")
    source_link, _, source_evidence = _map(SKILL, host, name="source-link")
    assert source_link.returncode == 0, source_link.stdout + source_link.stderr
    source_payload = _payload(source_evidence)
    assert source_payload["status"] == "unsupported"
    assert source_payload["failure_kind"] == "unsafe_source"
    assert "symbolic link" in source_payload["message"]


def test_php_map_refuses_unsafe_artifact_paths_and_copied_command_is_self_contained(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    victim = host / "src" / "Billing" / "InvoiceService.php"
    before = victim.read_bytes()
    unsafe, _, _ = _map(
        SKILL,
        host,
        name="unsafe",
        output=victim,
        evidence=host / "reports" / "map" / "unsafe" / "php-map.json",
    )
    assert unsafe.returncode == 2
    assert "output must stay" in unsafe.stderr
    assert victim.read_bytes() == before

    shutil.rmtree(host / "reports", ignore_errors=True)
    os.symlink(host / "src", host / "reports")
    unsafe_report, _, _ = _map(SKILL, host, name="unsafe-report")
    assert unsafe_report.returncode == 2
    assert "symbolic link" in unsafe_report.stderr
    assert victim.read_bytes() == before

    copied_host = _copy_host(tmp_path, "copied")
    copied_before = _fingerprints(copied_host)
    installed = copied_host / ".agents" / "skills" / "map-subsystem"
    shutil.copytree(SKILL, installed)
    result = _run(
        "/bin/bash",
        "-c",
        _documented_command(installed),
        cwd=copied_host,
        env={
            **os.environ,
            "MAP_NAME": "billing",
            "MAP_TARGET": "src/Billing",
            "PHP_BIN": str(PHP),
            "COMPOSER_BIN": str(COMPOSER),
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprints(copied_host) == copied_before
    assert _payload(copied_host / "reports" / "map" / "billing" / "php-map.json")["status"] == "complete"
    closure = (installed / "scripts" / "map_php.php").read_text(encoding="utf-8")
    assert "tree_sitter" not in closure
    assert "tree-sitter" not in closure
    assert str(ROOT) not in closure
    _native_verify(copied_host)

    missing_host = _copy_host(tmp_path, "missing-php")
    missing = _run(
        "/bin/bash",
        "-c",
        _documented_command(installed),
        cwd=missing_host,
        env={"MAP_NAME": "missing", "MAP_TARGET": "src/Billing", "PATH": ""},
    )
    assert missing.returncode == 2
    assert "PHP 8.1+" in missing.stderr
    assert not (missing_host / "reports" / "map" / "missing").exists()


def test_php_map_docs_state_the_family_local_psr4_boundary_and_tree_sitter_rejection() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    knowledge = (SKILL / "knowledge" / "php-v1.md").read_text(encoding="utf-8")
    assert "scans: [python, typescript, javascript, go, java, php, swift, c]" in text
    assert "PHP 8.1" in text
    assert "composer validate --no-check-publish --no-interaction" in text
    assert "Composer PSR-4" in text
    assert "tree-sitter" in knowledge
    assert "rejected" in knowledge
    assert "not semantic resolution" in knowledge
