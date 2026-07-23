"""Final-outcome contract for the four PHP A2 syntax-family consumers."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/php-syntax-family"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen F2 runtime
)
PHP = Path("/opt/homebrew/bin/php")
COMPOSER = Path("/usr/local/bin/composer")
PROVIDER = ROOT / ".claude/skills/_php-syntax/php_syntax_facts.php"
ADAPTERS = {
    "audit": ROOT / ".claude/skills/audit-decisions/scripts/audit_php.py",
    "complexity": ROOT / ".claude/skills/find-complexity-hotspots/scripts/run_php.py",
    "omnibus": ROOT / ".claude/skills/find-omnibus/scripts/run_php.py",
    "standards": ROOT / ".claude/skills/find-standard-gaps/scripts/scan_coverage_php.py",
}

pytestmark = pytest.mark.skipif(
    not PYTHON.is_file() or not PHP.is_file() or not COMPOSER.is_file(),
    reason="the frozen product Python, PHP 8.4.2, and Composer 2.4.0 are required",
)


def _run(*argv: str | Path, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(item) for item in argv], cwd=cwd, capture_output=True, text=True,
        check=False, timeout=timeout,
    )


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE / "host", host)
    (host / "linked-external").symlink_to(
        FIXTURE / "symlink-target", target_is_directory=True,
    )
    return host


def _state(root: Path) -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in {"reports", "scouts"}:
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = ("symlink", os.readlink(path))
        elif path.is_file():
            rows[relative.as_posix()] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return rows


def _install_closures(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    installed = tmp_path / "installed/.agents/skills"
    copied: dict[str, Path] = {}
    for kind, source in ADAPTERS.items():
        skill = source.parents[1]
        destination = installed / skill.name
        if not destination.exists():
            shutil.copytree(skill, destination)
        copied[kind] = destination / "scripts" / source.name
    provider = installed / "_php-syntax"
    shutil.copytree(PROVIDER.parent, provider)
    return provider / PROVIDER.name, copied


def _output(host: Path, kind: str) -> Path:
    return {
        "audit": host / "reports/audit-decisions/php-scan",
        "complexity": host / "reports/find-complexity-hotspots/php-scan",
        "omnibus": host / "reports/omnibus/php-scan",
        "standards": host / "reports/standard-gaps/php-scan",
    }[kind]


def _invoke(
    host: Path,
    kind: str,
    *,
    adapter: Path | None = None,
    target: str = "src",
    php: Path = PHP,
    composer: Path = COMPOSER,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command: list[str | Path] = [
        PYTHON, "-I", "-S", adapter or ADAPTERS[kind],
        "--project-root", host, "--target", target, "--output-dir", _output(host, kind),
        "--php", php, "--composer", composer, "--php-runner", PHP,
    ]
    if kind == "omnibus":
        command.extend(["--scout-dir", host / "scouts"])
    if kind == "standards":
        command.extend(["--ideas", host / "standards-php.json"])
    return _run(*command, cwd=cwd or host)


def _final(host: Path, kind: str) -> dict:
    names = {
        "audit": "raw-drift.json", "complexity": "findings.json",
        "omnibus": "findings.json", "standards": "coverage.json",
    }
    return json.loads((_output(host, kind) / names[kind]).read_text(encoding="utf-8"))


def _status(host: Path, kind: str) -> str:
    return _final(host, kind)["status"]


def _finding_count(host: Path, kind: str) -> int:
    final = _final(host, kind)
    if kind == "audit":
        return len(final["references"])
    if kind == "standards":
        return sum(row["gap_count"] for row in final["standards"])
    return len(final["findings"])


def _provider(host: Path, *, target: str = "src", php: Path = PHP, composer: Path = COMPOSER) -> tuple[subprocess.CompletedProcess[str], dict]:
    completed = _run(
        PHP, PROVIDER, "--project-root", host, "--target", target,
        "--php", php, "--composer", composer,
        cwd=host,
    )
    return completed, json.loads(completed.stdout)


def _write_scouts(host: Path) -> None:
    candidates = [
        json.loads(line)
        for line in (_output(host, "omnibus") / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    scouts = host / "scouts"
    scouts.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        assert candidate["file"] == "src/OmnibusService.php"
        payload = {
            "schema_version": "php-omnibus-scout-v1",
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate["candidate_sha256"],
            "human_verdict": "accepted",
            "bucket": "confirmed_omnibus",
            "rationale": "Invoice, payment, shipment, and audit are independently understandable domains.",
        }
        (scouts / f"{candidate['candidate_id']}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )


def _complete_omnibus(host: Path, *, adapter: Path | None = None, cwd: Path | None = None) -> None:
    first = _invoke(host, "omnibus", adapter=adapter, cwd=cwd)
    assert first.returncode == 2, first.stdout + first.stderr
    _write_scouts(host)
    completed = _invoke(host, "omnibus", adapter=adapter, cwd=cwd)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _native(host: Path) -> None:
    for command in (
        (COMPOSER, "validate", "--no-check-publish", "--no-interaction"),
        (PHP, "tests/lint.php"),
        (PHP, "tests/smoke.php"),
    ):
        completed = _run(*command, cwd=host)
        assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _run(PHP, "tests/smoke.php", cwd=host).stdout == "php-syntax-ok\n"


def test_php_syntax_provider_has_native_role_aware_facts_and_preserves_source(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)
    completed, facts = _provider(host)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (facts["status"], facts["failure_kind"]) == ("complete", "none")
    assert facts["analyzer"] == "php-token-syntax-facts-v1"
    assert facts["source_manifest"]["before_sha256"] == facts["source_manifest"]["after_sha256"]
    assert facts["source_manifest"]["preserved"] is True
    assert facts["composer_validate"]["state"] == "passed"
    roles = {row["file"]: row["role"] for row in facts["inventory"]}
    assert roles["tests/ExcludedSyntaxTest.php"] == "test"
    assert roles["generated/GeneratedSyntax.php"] == "generated"
    assert roles["vendor/example/package/VendorSyntax.php"] == "vendor"
    assert roles["build/CompiledSyntax.php"] == "build"
    assert roles["reports/decoy/ReportedSyntax.php"] == "report"
    assert roles["linked-external"] == "symlink"
    functions = {
        row["qualified_name"]: row
        for file in facts["files"] for row in file["functions"]
    }
    assert functions["routeInvoice"]["branch_score"] == 9
    assert functions["closureDecoy"]["branch_score"] == 0
    comments = [row["text"] for file in facts["files"] for row in file["comments"]]
    assert any("decision:0001" in row for row in comments)
    assert not any("decision:7777" in row for row in comments)
    calls = [row for file in facts["files"] for row in file["calls"] if row["spelling"] == "parseInvoice"]
    assert [(row["function"], row["enclosures"]) for row in calls] == [
        ("handledParse", ["try"]), ("unhandledParse", []),
    ]
    assert _state(host) == before


def test_php_a2_final_artifacts_reach_four_distinct_useful_outcomes(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _native(host)
    before = _state(host)
    copied_provider, copied = _install_closures(tmp_path)

    audit = _invoke(host, "audit", adapter=copied["audit"])
    complexity = _invoke(host, "complexity", adapter=copied["complexity"])
    standards = _invoke(host, "standards", adapter=copied["standards"])
    assert audit.returncode == 1, audit.stdout + audit.stderr
    assert complexity.returncode == 0, complexity.stdout + complexity.stderr
    assert standards.returncode == 1, standards.stdout + standards.stderr
    _complete_omnibus(host, adapter=copied["omnibus"])

    audit_final = _final(host, "audit")
    assert audit_final["status"] == "complete"
    assert {(row["id"], row["resolved"], row["language"]) for row in audit_final["references"]} == {
        ("0001", True, "php"), ("9999", False, "php"),
    }
    assert {row["symptom"] for row in audit_final["drift"]} == {"code-ref-orphan"}
    assert {path.name for path in _output(host, "audit").iterdir()} == {
        "drift.md", "raw-drift.json", "registry-audit.json", "link-check.txt",
    }

    complexity_final = _final(host, "complexity")
    assert (complexity_final["status"], complexity_final["verdict"]) == ("complete", "measure-first")
    assert [(row["function"], row["branch_score"]) for row in complexity_final["findings"]] == [
        ("routeInvoice", 9),
    ]
    assert "closureDecoy" not in json.dumps(complexity_final["findings"])
    assert {path.name for path in _output(host, "complexity").iterdir()} == {
        "detections.jsonl", "findings.json", "report.md",
    }
    assert (_output(host, "complexity").parent / "latest").resolve() == _output(host, "complexity").resolve()

    omnibus_final = _final(host, "omnibus")
    assert omnibus_final["status"] == "complete"
    assert omnibus_final["summary"] == {"confirmed_omnibus": 1}
    assert omnibus_final["human_scout_accounting"] == {"candidates_total": 1, "graded": 1, "ungraded": 0}
    assert omnibus_final["findings"][0]["file"] == "src/OmnibusService.php"
    assert omnibus_final["findings"][0]["recommendation"].startswith("/refactor-subsystem")
    assert "CohesiveControl" not in json.dumps(omnibus_final["findings"])
    assert {path.name for path in _output(host, "omnibus").iterdir()} == {
        "omnibus.jsonl", "candidates.jsonl", "scan.json", "findings.json", "report.md",
    }

    standards_final = _final(host, "standards")
    assert standards_final["status"] == "complete"
    standard = standards_final["standards"][0]
    assert (standard["id"], standard["status"], standard["situation_sites"], standard["gap_count"], standard["coverage_percent"]) == (
        "php-parse-try", "scanned", 2, 1, 50.0,
    )
    assert [(row["file"], row["function"]) for row in standard["gaps"]] == [
        ("src/Standards.php", "unhandledParse"),
    ]
    assert {path.name for path in _output(host, "standards").iterdir()} == {"coverage.json", "coverage.md"}
    assert copied_provider.is_file()
    assert _state(host) == before
    for adapter in copied.values():
        assert str(ROOT) not in adapter.read_text(encoding="utf-8")


def test_php_a2_clean_and_safe_defer_outputs_are_explicit(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    for kind in ("audit", "complexity", "standards"):
        completed = _invoke(host, kind, target="src/Clean")
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert _status(host, kind) == "complete"
    omnibus = _invoke(host, "omnibus", target="src/Clean")
    assert omnibus.returncode == 0, omnibus.stdout + omnibus.stderr
    assert _final(host, "audit")["references"] == []
    assert _final(host, "complexity")["findings"] == []
    assert _final(host, "omnibus")["findings"] == []
    assert _final(host, "omnibus")["human_scout_accounting"] == {
        "candidates_total": 0, "graded": 0, "ungraded": 0,
    }
    standard = _final(host, "standards")["standards"][0]
    assert (standard["status"], standard["gap_count"], standard["coverage_percent"]) == ("scanned", 0, 100.0)


def _fake_php(path: Path, *, version: str = "8.4.2", lint_exit: int = 0, probe_exit: int = 0) -> Path:
    path.write_text(
        "#!/bin/sh\nset -eu\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' 'PHP {version} (cli) (built: fixture)'\n"
        f"  exit {probe_exit}\n"
        "fi\n"
        f"exit {lint_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _fake_composer(path: Path, *, version: str = "2.4.0", validate_exit: int = 0, probe_exit: int = 0) -> Path:
    path.write_text(
        "#!/bin/sh\nset -eu\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' 'Composer version {version} fixture'\n"
        f"  exit {probe_exit}\n"
        "fi\n"
        f"exit {validate_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
@pytest.mark.parametrize(
    ("case", "expected_status", "expected_failure", "expected_code"),
    (
        ("missing-php", "partial", "php_tool_missing", 2),
        ("old-php", "partial", "php_tool_too_old", 2),
        ("missing-composer", "partial", "composer_tool_missing", 2),
        ("old-composer", "partial", "composer_tool_too_old", 2),
        ("failing-php", "failed", "php_lint_failed", 1),
        ("failing-composer", "failed", "composer_validation_failed", 1),
        ("probe-failing", "failed", "php_tool_probe_failed", 1),
    ),
)
def test_php_a2_tool_states_are_honest_and_never_clean(
    kind: str, case: str, expected_status: str, expected_failure: str, expected_code: int, tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path, f"{kind}-{case}")
    php = PHP
    composer = COMPOSER
    if case == "missing-php":
        php = tmp_path / "missing-php"
    elif case == "old-php":
        php = _fake_php(tmp_path / "old-php", version="8.0.29")
    elif case == "missing-composer":
        composer = tmp_path / "missing-composer"
    elif case == "old-composer":
        composer = _fake_composer(tmp_path / "old-composer", version="2.1.9")
    elif case == "failing-php":
        php = _fake_php(tmp_path / "failing-php", lint_exit=9)
    elif case == "failing-composer":
        composer = _fake_composer(tmp_path / "failing-composer", validate_exit=9)
    else:
        php = _fake_php(tmp_path / "probe-failing", probe_exit=9)
    completed = _invoke(host, kind, php=php, composer=composer)
    assert completed.returncode == expected_code, completed.stdout + completed.stderr
    final = _final(host, kind)
    assert (final["status"], final["failure_kind"]) == (expected_status, expected_failure)
    assert _finding_count(host, kind) == 0
    report = (_output(host, kind) / ({"audit": "drift.md", "complexity": "report.md", "omnibus": "report.md", "standards": "coverage.md"}[kind])).read_text(encoding="utf-8").casefold()
    assert "status: `complete`" not in report


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_php_a2_malformed_source_is_partial_empty_and_preserved(kind: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path, kind)
    shutil.copy2(FIXTURE / "malformed/Broken.php", host / "src/Broken.php")
    before = _state(host)
    completed = _invoke(host, kind)
    assert completed.returncode == 2, completed.stdout + completed.stderr
    final = _final(host, kind)
    assert (final["status"], final["failure_kind"]) == ("partial", "php_parse_diagnostics")
    assert _finding_count(host, kind) == 0
    assert _state(host) == before


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_php_a2_valid_failed_valid_lifecycle_replaces_stale_artifacts(kind: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path, kind)
    if kind == "omnibus":
        _complete_omnibus(host)
    else:
        initial = _invoke(host, kind)
        assert initial.returncode in {0, 1}, initial.stdout + initial.stderr
    initial_count = _finding_count(host, kind)
    assert initial_count > 0
    failed_composer = _fake_composer(tmp_path / f"failing-{kind}", validate_exit=9)
    failed = _invoke(host, kind, composer=failed_composer)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert (_status(host, kind), _finding_count(host, kind)) == ("failed", 0)
    if kind == "omnibus":
        shutil.rmtree(host / "scouts")
        _complete_omnibus(host)
    else:
        recovered = _invoke(host, kind)
        assert recovered.returncode in {0, 1}, recovered.stdout + recovered.stderr
    assert (_status(host, kind), _finding_count(host, kind)) == ("complete", initial_count)


def test_php_a2_copied_provider_deletion_fails_closed_and_recovers(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)
    copied_provider, copied = _install_closures(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    for kind in ("audit", "complexity", "standards"):
        assert _invoke(host, kind, adapter=copied[kind], cwd=outside).returncode in {0, 1}
    _complete_omnibus(host, adapter=copied["omnibus"], cwd=outside)
    original = copied_provider.read_bytes()
    copied_provider.unlink()
    for kind, adapter in copied.items():
        completed = _invoke(host, kind, adapter=adapter, cwd=outside)
        assert completed.returncode == 2, completed.stdout + completed.stderr
        final = _final(host, kind)
        assert (final["status"], final["failure_kind"]) == ("partial", "php_syntax_provider_missing")
        assert _finding_count(host, kind) == 0
    copied_provider.write_bytes(original)
    for kind in ("audit", "complexity", "standards"):
        assert _invoke(host, kind, adapter=copied[kind], cwd=outside).returncode in {0, 1}
    shutil.rmtree(host / "scouts")
    _complete_omnibus(host, adapter=copied["omnibus"], cwd=outside)
    assert _final(host, "omnibus")["findings"]
    assert _state(host) == before


def _physical_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_php_a2_local_provider_clears_ml025_literal_ownership_gates() -> None:
    provider_text = PROVIDER.read_text(encoding="utf-8")
    for policy in ("TOKEN_PARSE", "composer_validation_failed", "generated-tree", "source_mutation_detected"):
        assert policy in provider_text
    forbidden_caller_policy = ("TOKEN_PARSE", "proc_open", "RecursiveDirectoryIterator", "composer_validation_failed")
    for adapter in ADAPTERS.values():
        text = adapter.read_text(encoding="utf-8")
        assert "php_syntax_facts.php" in text
        assert all(policy not in text for policy in forbidden_caller_policy)

    provider_lines = _physical_lines(PROVIDER)
    adapter_lines = sum(_physical_lines(path) for path in ADAPTERS.values())
    test_lines = _physical_lines(Path(__file__))
    shared = provider_lines + adapter_lines + test_lines
    literal = provider_lines * len(ADAPTERS) + adapter_lines + test_lines
    assert (literal - shared) / literal * 100 >= 25
    closure_growth = []
    for adapter in ADAPTERS.values():
        shared_bytes = PROVIDER.stat().st_size + adapter.stat().st_size
        literal_adapter = adapter.read_text(encoding="utf-8").replace(
            'Path(__file__).resolve().parents[2] / "_php-syntax/php_syntax_facts.php"',
            'Path(__file__).resolve().parents[1] / "_php-syntax/php_syntax_facts.php"',
        )
        literal_bytes = PROVIDER.stat().st_size + len(literal_adapter.encode())
        closure_growth.append((shared_bytes - literal_bytes) / literal_bytes * 100)
    assert max(closure_growth) <= 10


def test_php_a2_required_frozen_runtime_paths_exist() -> None:
    assert PYTHON.is_file()
    assert PHP.is_file()
    assert COMPOSER.is_file()
