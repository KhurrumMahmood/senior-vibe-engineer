"""Five PHP project/lexical consumers over one copied PHP fact producer."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "php-project-lexical-family"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen F2 runtime
)
PHP = Path("/opt/homebrew/bin/php")
COMPOSER = Path("/usr/local/bin/composer")
COMMON = (
    ROOT
    / ".claude"
    / "skills"
    / "_php-project-lexical"
    / "php_project_lexical.php"
)
SCRIPTS = {
    "adapt-project": ROOT
    / ".claude"
    / "skills"
    / "adapt-project"
    / "scripts"
    / "discover_php.php",
    "explain-code": ROOT
    / ".claude"
    / "skills"
    / "explain-code"
    / "scripts"
    / "explain_php.php",
    "find-concept-divergence": ROOT
    / ".claude"
    / "skills"
    / "find-concept-divergence"
    / "scripts"
    / "scan_php.php",
    "find-duplication": ROOT
    / ".claude"
    / "skills"
    / "find-duplication"
    / "scripts"
    / "run_php.php",
    "find-folder-topology-drift": ROOT
    / ".claude"
    / "skills"
    / "find-folder-topology-drift"
    / "scripts"
    / "detect_php.php",
}

pytestmark = pytest.mark.skipif(
    not PHP.is_file() or not COMPOSER.is_file(),
    reason="PHP 8.4.2 and Composer 2.4.0 are required",
)


def _run(*args: str, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _copy_host(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", host)
    (host / "linked-external").symlink_to(
        FIXTURE / "symlink-target", target_is_directory=True
    )
    return host


def _install_closures(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    install = tmp_path / "installed" / ".agents" / "skills"
    common = install / "_php-project-lexical" / COMMON.name
    common.parent.mkdir(parents=True)
    shutil.copy2(COMMON, common)
    copied: dict[str, Path] = {}
    for skill, source in SCRIPTS.items():
        destination = install / skill
        shutil.copytree(ROOT / ".claude" / "skills" / skill, destination)
        copied[skill] = destination / "scripts" / source.name
    return common, copied


def _hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and (path.suffix == ".php" or path.name == "composer.json")
    }


def _invoke(
    skill: str,
    script: Path,
    host: Path,
    *,
    target: str = "src/Billing",
    php: Path = PHP,
    composer: Path = COMPOSER,
    minimum_php: str = "8.1.0",
    minimum_composer: str = "2.2.0",
) -> subprocess.CompletedProcess[str]:
    base = (
        str(PHP),
        str(script),
        "--project-root",
        str(host),
        "--target",
        target,
        "--php",
        str(php),
        "--composer",
        str(composer),
        "--minimum-php",
        minimum_php,
        "--minimum-composer",
        minimum_composer,
    )
    if skill == "adapt-project":
        args = (*base, "--output-dir", str(host / "reports" / "adapt"))
    elif skill == "explain-code":
        args = (*base, "--output", str(host / "reports" / "explain" / "php.md"))
    elif skill == "find-concept-divergence":
        args = (
            *base,
            "--glossary",
            str(host / ".claude" / "contracts" / "concepts.yaml"),
            "--output",
            str(host / "reports" / "concept" / "findings.jsonl"),
            "--report",
            str(host / "reports" / "concept" / "report.md"),
        )
    elif skill == "find-duplication":
        args = (*base, "--output-dir", str(host / "reports" / "duplication"))
    else:
        args = (
            *base,
            "--output",
            str(host / "reports" / "folder" / "detections.jsonl"),
            "--min-cluster-size",
            "3",
        )
    return _run(*args, cwd=host)


def _payload(skill: str, host: Path) -> dict:
    paths = {
        "adapt-project": host / "reports" / "adapt" / "adapter.json",
        "explain-code": host / "reports" / "explain" / "php" / "targets.json",
        "find-concept-divergence": host / "reports" / "concept" / "findings.json",
        "find-duplication": host / "reports" / "duplication" / "findings.json",
        "find-folder-topology-drift": host / "reports" / "folder" / "findings.json",
    }
    return json.loads(paths[skill].read_text(encoding="utf-8"))


def _status(skill: str, host: Path) -> str:
    payload = _payload(skill, host)
    return payload.get("status") or payload.get("scan_meta", {}).get("status")


def _finding_count(skill: str, host: Path) -> int:
    payload = _payload(skill, host)
    if skill == "adapt-project":
        return payload["source_roots"][0]["php_files"]
    if skill == "explain-code":
        return len(payload["selected"])
    return len(payload["findings"])


def _native(host: Path) -> None:
    commands = (
        (
            str(COMPOSER),
            "validate",
            "--no-check-publish",
            "--no-interaction",
        ),
        (str(PHP), "tests/lint.php"),
        (str(PHP), "tests/smoke.php"),
    )
    for command in commands:
        result = _run(*command, cwd=host)
        assert result.returncode == 0, result.stdout + result.stderr
    smoke = _run(str(PHP), "tests/smoke.php", cwd=host)
    assert smoke.stdout == "php-project-lexical-ok\n"


def test_php_five_value_outcomes_copied_closures_roles_and_native(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    _native(host)
    before = _hashes(host)
    copied_common, copied = _install_closures(tmp_path)

    results = {skill: _invoke(skill, script, host) for skill, script in copied.items()}
    assert all(result.returncode == 0 for result in results.values()), {
        skill: result.stdout + result.stderr for skill, result in results.items()
    }

    adapter = _payload("adapt-project", host)
    assert adapter["status"] == "complete"
    assert adapter["stack"] == {
        "frameworks": [],
        "languages": ["php"],
        "package_managers": ["composer"],
    }
    assert adapter["source_roots"][0]["php_files"] == 6
    assert adapter["composer"]["psr4"] == {"Acme\\": "src/"}
    assert adapter["commands"]["test"] == ["php tests/smoke.php"]
    assert (host / "reports" / "adapt" / "adapter.yml").is_file()
    evidence = json.loads((host / "reports" / "adapt" / "evidence.json").read_text())
    assert evidence["evidence"] == {"adapter": "adapter.yml", "report": "report.md"}

    targets = _payload("explain-code", host)
    assert targets["status"] == "complete"
    symbols = {row["symbol"] for row in targets["selected"]}
    assert {"BillingParser", "BillingTypes", "parse", "pendingTotal"} <= symbols
    assert "excluded_test_clone" not in symbols
    assert targets["unexplained"] == [
        {
            "file": "src/Billing/DynamicAlias.php",
            "reason": "dynamic class_alias identity requires runtime/project resolution",
            "symbol": "class_alias",
        }
    ]
    annotations = host / "reports" / "explain" / "php" / "annotations"
    assert len(list(annotations.glob("*.md"))) == len(targets["selected"])
    explanation = (host / "reports" / "explain" / "php.md").read_text()
    assert "## Public contracts" in explanation
    assert "lexical declaration; behavior remains unexplained" in explanation
    parsed = next(row for row in targets["selected"] if row["symbol"] == "parse")
    source = (host / parsed["file"]).read_bytes()
    spelling = source[parsed["span"]["start_byte"] : parsed["span"]["end_byte"]]
    assert hashlib.sha256(spelling).hexdigest() == parsed["spelling_sha256"]

    concept = _payload("find-concept-divergence", host)
    assert concept["status"] == "complete"
    assert concept["outcome"] == "drift-found"
    assert len(concept["findings"]) == 1
    assert concept["findings"][0]["term"] == "cancelled_order"
    assert concept["findings"][0]["file"] == "src/Billing/BillingParser.php"
    hit = concept["findings"][0]
    source = (host / hit["file"]).read_bytes()
    assert source[hit["span"]["start_byte"] : hit["span"]["end_byte"]] == b"cancelled_order"

    duplication = _payload("find-duplication", host)
    assert duplication["scan_meta"]["status"] == "complete"
    assert len(duplication["findings"]) == 1
    sites = {site["symbol"] for site in duplication["findings"][0]["sites"]}
    assert sites == {"BillingTotalsA::pendingTotal", "BillingTotalsB::queuedTotal"}
    assert "Do not consolidate automatically" in (
        host / "reports" / "duplication" / "triage.md"
    ).read_text()

    folder = _payload("find-folder-topology-drift", host)
    assert folder["status"] == "complete"
    assert folder["outcome"] == "drift-found"
    assert len(folder["findings"]) == 1
    assert folder["findings"][0]["prefix"] == "Billing"
    assert set(folder["findings"][0]["files"]) == {
        "src/Billing/BillingParser.php",
        "src/Billing/BillingTotalsA.php",
        "src/Billing/BillingTotalsB.php",
        "src/Billing/BillingTypes.php",
        "src/Billing/BillingValidator.php",
    }

    analyses = [
        adapter["analysis"]["php"],
        targets["analysis"]["php"],
        concept["analysis"]["php"],
        duplication["scan_meta"]["analysis"],
        folder["analysis"]["php"],
    ]
    assert len({analysis["source_manifest_sha256"] for analysis in analyses}) == 1
    assert all(analysis["composer_validate"]["returncode"] == 0 for analysis in analyses)
    for analysis in analyses:
        roles = {row["file"]: row.get("reason", row["role"]) for row in analysis["inventory"]}
        assert roles["tests/Billing/BillingParserTest.php"] == "test"
        assert roles["generated/BillingGenerated.php"] == "generated-tree"
        assert roles["vendor/example/package/BillingVendor.php"] == "vendor"
        assert roles["build/BillingCompiled.php"] == "build-tree"
        assert roles["reports/decoy/BillingReported.php"] == "report-tree"
        assert roles["linked-external"] == "symlink"
    assert _hashes(host) == before
    assert copied_common.is_file()
    for script in copied.values():
        text = script.read_text(encoding="utf-8")
        assert "php_project_lexical.php" in text
        assert str(ROOT) not in text


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_php_consumer_clean_or_below_threshold(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)

    result = _invoke(skill, copied[skill], host, target="src/Clean")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _status(skill, host) == "complete"
    if skill in {"adapt-project", "explain-code"}:
        assert _finding_count(skill, host) >= 1
    else:
        assert _finding_count(skill, host) == 0


def _fake_php(path: Path, *, version: str = "8.4.2", lint_exit: int = 0) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' 'PHP {version} (cli) (built: fixture)'\n"
        "  exit 0\n"
        "fi\n"
        f"exit {lint_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _fake_composer(path: Path, *, version: str = "2.4.0", validate_exit: int = 0) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' 'Composer version {version} 2022-08-16'\n"
        "  exit 0\n"
        "fi\n"
        f"exit {validate_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
@pytest.mark.parametrize(
    ("state", "expected"),
    (
        ("missing-php", "partial"),
        ("old-php", "partial"),
        ("missing-composer", "partial"),
        ("old-composer", "partial"),
        ("failing-php", "failed"),
        ("failing-composer", "failed"),
    ),
)
def test_each_php_consumer_tool_states_are_honest(
    skill: str, state: str, expected: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    php = PHP
    composer = COMPOSER
    if state == "missing-php":
        php = tmp_path / "missing-php"
    elif state == "old-php":
        php = _fake_php(tmp_path / "old-php", version="8.0.29")
    elif state == "missing-composer":
        composer = tmp_path / "missing-composer"
    elif state == "old-composer":
        composer = _fake_composer(tmp_path / "old-composer", version="2.1.9")
    elif state == "failing-php":
        php = _fake_php(tmp_path / "failing-php", lint_exit=9)
    else:
        composer = _fake_composer(tmp_path / "failing-composer", validate_exit=9)

    result = _invoke(skill, copied[skill], host, php=php, composer=composer)

    assert result.returncode == (2 if expected == "partial" else 1)
    assert _status(skill, host) == expected
    if expected == "failed":
        assert _finding_count(skill, host) == 0


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_php_consumer_malformed_source_is_partial_and_preserved(
    skill: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    shutil.copy2(FIXTURE / "malformed" / "Broken.php", host / "src" / "Billing" / "Broken.php")
    before = _hashes(host)
    _, copied = _install_closures(tmp_path)

    result = _invoke(skill, copied[skill], host)

    assert result.returncode == 2, result.stdout + result.stderr
    assert _status(skill, host) == "partial"
    assert _hashes(host) == before
    report_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (host / "reports").rglob("*.md")
    )
    assert "complete clean conclusion" not in report_text.casefold()


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_each_php_consumer_valid_failed_valid_destination_reuse(
    skill: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    failing = _fake_composer(tmp_path / "failing-composer", validate_exit=7)

    valid = _invoke(skill, copied[skill], host)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    positive_count = _finding_count(skill, host)
    assert positive_count > 0

    failed = _invoke(skill, copied[skill], host, composer=failing)
    assert failed.returncode == 1
    assert _status(skill, host) == "failed"
    assert _finding_count(skill, host) == 0

    recovered = _invoke(skill, copied[skill], host)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert _status(skill, host) == "complete"
    assert _finding_count(skill, host) == positive_count


def _physical_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _inline_bytes(helper: Path, consumer: Path) -> int:
    helper_text = helper.read_text(encoding="utf-8")
    helper_body = helper_text.removeprefix("<?php\n\ndeclare(strict_types=1);\n")
    consumer_text = consumer.read_text(encoding="utf-8")
    lines = [
        line
        for line in consumer_text.splitlines(keepends=True)
        if "php_project_lexical.php" not in line and "require_once" not in line
    ]
    return len(("".join(lines) + helper_body).encode())


def test_php_shared_fact_producer_clears_interface_and_economics_gates() -> None:
    helper = COMMON.read_text(encoding="utf-8")
    for policy in (
        "--no-check-publish",
        "--no-interaction",
        "TOKEN_PARSE",
        "source_manifest_sha256",
        "generated-tree",
        "report-tree",
        "symlink",
    ):
        assert policy in helper
    forbidden_caller_policy = ("generated-tree", "report-tree", "TOKEN_PARSE", "proc_open")
    for script in SCRIPTS.values():
        text = script.read_text(encoding="utf-8")
        assert "ppl_collect_snapshot" in text
        assert all(policy not in text for policy in forbidden_caller_policy)

    helper_lines = _physical_lines(COMMON)
    consumer_lines = sum(_physical_lines(path) for path in SCRIPTS.values())
    test_lines = _physical_lines(Path(__file__))
    shared = helper_lines + consumer_lines + test_lines
    duplicated = helper_lines * len(SCRIPTS) + consumer_lines + test_lines
    reduction = (duplicated - shared) / duplicated * 100
    assert reduction >= 25

    closure_growth = []
    for consumer in SCRIPTS.values():
        shared_bytes = COMMON.stat().st_size + consumer.stat().st_size
        inline_bytes = _inline_bytes(COMMON, consumer)
        closure_growth.append((shared_bytes - inline_bytes) / inline_bytes * 100)
    assert max(closure_growth) <= 10


def test_required_frozen_runtime_paths_exist() -> None:
    assert PYTHON.is_file()
    assert PHP.is_file()
    assert COMPOSER.is_file()
