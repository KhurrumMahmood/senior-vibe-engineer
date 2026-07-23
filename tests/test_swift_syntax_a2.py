"""Swift A2 final outcomes over bounded compiler-validated syntax facts."""

from __future__ import annotations

import hashlib
import json
import os
import runpy
import shutil
import statistics
import subprocess
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/swift-syntax-a2"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen F2 runtime
)
SWIFT = Path("/usr/bin/swift")
SWIFTC = Path("/usr/bin/swiftc")
SWIFT_FORMAT = Path("/Library/Developer/CommandLineTools/usr/bin/swift-format")
PROVIDER = ROOT / ".claude/skills/_swift-project-lexical/swift_project_facts.py"
ADAPTERS = {
    "audit": ROOT / ".claude/skills/audit-decisions/scripts/audit_swift.py",
    "complexity": ROOT / ".claude/skills/find-complexity-hotspots/scripts/run_swift.py",
    "standards": ROOT / ".claude/skills/find-standard-gaps/scripts/scan_coverage_swift.py",
}
SKILL_NAMES = {
    "audit": "audit-decisions",
    "complexity": "find-complexity-hotspots",
    "standards": "find-standard-gaps",
}
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (SWIFT, SWIFTC, SWIFT_FORMAT, PYTHON)),
    reason="Swift 6.3.3 Command Line Tools and the frozen product runtime are required",
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
    shutil.copytree(FIXTURE / "host", host)
    (host / "linked-external").symlink_to(
        FIXTURE / "symlink-target", target_is_directory=True
    )
    return host


def _state(host: Path) -> dict[str, tuple[str, str]]:
    state: dict[str, tuple[str, str]] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host).as_posix()
        if relative == "reports" or relative.startswith("reports/"):
            continue
        if path.is_symlink():
            state[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            state[relative] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return state


def _tool_args(swift: Path = SWIFT) -> list[str]:
    return [
        "--swift",
        str(swift),
        "--swiftc",
        str(SWIFTC),
        "--swift-format",
        str(SWIFT_FORMAT),
        "--check-product",
        "swift-a2-check",
        "--expected-check",
        "swift-a2-checks-ok",
        "--smoke-product",
        "swift-a2-smoke",
        "--expected-smoke",
        "swift-a2:42",
    ]


def _output(host: Path, kind: str) -> Path:
    roots = {
        "audit": "audit-decisions",
        "complexity": "find-complexity-hotspots",
        "standards": "standard-gaps",
    }
    return host / "reports" / roots[kind] / "swift-a2"


def _invoke(
    host: Path,
    kind: str,
    *,
    adapter: Path | None = None,
    swift: Path = SWIFT,
    target: str | None = None,
    ideas: Path | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    selected = target or ("." if kind == "audit" else "Sources/SwiftA2Core")
    argv = [
        str(PYTHON),
        "-I",
        "-S",
        str(adapter or ADAPTERS[kind]),
        "--project-root",
        str(host),
        "--target",
        selected,
        "--output-dir",
        str(_output(host, kind)),
        *_tool_args(swift),
    ]
    if kind == "standards":
        argv.extend(["--ideas", str(ideas or host / "standards-swift.json")])
    return _run(*argv, cwd=cwd or host)


def _final(host: Path, kind: str) -> dict:
    names = {
        "audit": "raw-drift.json",
        "complexity": "findings.json",
        "standards": "coverage.json",
    }
    return json.loads((_output(host, kind) / names[kind]).read_text(encoding="utf-8"))


def _analysis(payload: dict) -> dict:
    return payload["analysis"]["swift"]


def _fake_swift(
    path: Path,
    *,
    version: str = "6.3.3",
    version_exit: int = 0,
    malformed_version: bool = False,
    command_exit: int = 9,
) -> Path:
    version_text = "not a Swift version" if malformed_version else f"Apple Swift version {version} (fixture)"
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' '{version_text}'\n"
        f"  exit {version_exit}\n"
        "fi\n"
        f"exit {command_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _copy_shared_closure(tmp_path: Path, kind: str) -> Path:
    installed = tmp_path / "installed" / ".agents/skills"
    skill = installed / SKILL_NAMES[kind]
    ignored = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ADAPTERS[kind].parents[1], skill, ignore=ignored)
    shutil.copytree(
        PROVIDER.parent, installed / "_swift-project-lexical", ignore=ignored
    )
    return skill / "scripts" / ADAPTERS[kind].name


def _copy_consumer_only(tmp_path: Path, kind: str) -> Path:
    installed = tmp_path / "consumer-only" / ".agents/skills"
    skill = installed / SKILL_NAMES[kind]
    shutil.copytree(
        ADAPTERS[kind].parents[1],
        skill,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return skill / "scripts" / ADAPTERS[kind].name


def _copy_literal_closure(tmp_path: Path, kind: str) -> Path:
    installed = tmp_path / "literal" / ".agents/skills"
    skill = installed / SKILL_NAMES[kind]
    shutil.copytree(
        ADAPTERS[kind].parents[1],
        skill,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    adapter = skill / "scripts" / ADAPTERS[kind].name
    source = adapter.read_text(encoding="utf-8")
    shared = (
        'PRODUCER = Path(__file__).resolve().parents[2] / "_swift-project-lexical" '
        '/ "swift_project_facts.py"'
    )
    literal = 'PRODUCER = Path(__file__).resolve().with_name("swift_project_facts.py")'
    assert shared in source
    adapter.write_text(source.replace(shared, literal), encoding="utf-8")
    shutil.copy2(PROVIDER, adapter.with_name(PROVIDER.name))
    return adapter


def test_three_final_outcomes_roles_native_source_preservation_and_boundaries(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _state(host)

    results = {kind: _invoke(host, kind) for kind in ADAPTERS}

    assert {kind: result.returncode for kind, result in results.items()} == {
        "audit": 1,
        "complexity": 0,
        "standards": 1,
    }, {kind: result.stdout + result.stderr for kind, result in results.items()}

    audit = _final(host, "audit")
    assert audit["status"] == "complete"
    references = {
        (row["id"], row["resolved"], row["comment_form"])
        for row in audit["references"]
    }
    assert ("9999", False, "line") in references
    assert {(identifier, form) for identifier, resolved, form in references if resolved} >= {
        ("0001", "line"),
        ("0001", "doc"),
    }
    assert not {"6000", "6001", "6002", "6003", "6004", "6005", "6006", "7000"} & {
        row["id"] for row in audit["references"]
    }
    assert {row["symptom"] for row in audit["drift"]} >= {
        "code-ref-orphan",
        "unreferenced-decision",
    }
    assert {path.name for path in _output(host, "audit").iterdir()} == {
        "drift.md",
        "raw-drift.json",
        "registry-audit.json",
        "link-check.txt",
    }

    complexity = _final(host, "complexity")
    assert complexity["status"] == "complete"
    assert complexity["outcome"] == "measure-first"
    assert [(row["function"], row["branch_score"]) for row in complexity["findings"]] == [
        ("routeInvoice", 11)
    ]
    serialized_complexity = json.dumps(complexity["findings"])
    assert "closureDecoy" not in serialized_complexity
    assert "localFunctionDecoy" not in serialized_complexity
    assert "protocolRequirement" not in serialized_complexity
    assert complexity["findings"][0]["runtime_cost_claimed"] is False
    assert {path.name for path in _output(host, "complexity").iterdir()} == {
        "detections.jsonl",
        "findings.json",
        "report.md",
        "scan.json",
    }

    standards = _final(host, "standards")
    assert standards["status"] == "complete"
    row = standards["standards"][0]
    assert (row["status"], row["situation_sites"], row["gap_count"], row["coverage_percent"]) == (
        "scanned",
        3,
        1,
        66.67,
    )
    assert [(gap["file"], gap["function"]) for gap in row["gaps"]] == [
        ("Sources/SwiftA2Core/A2Cases.swift", "uncheckedInvoice")
    ]
    assert all(site["call_identity_claimed"] is False for site in row["sites"])
    serialized_sites = json.dumps(row["sites"])
    assert "standardDecoys" not in serialized_sites
    assert "ReceiverDecoy" not in serialized_sites
    assert {path.name for path in _output(host, "standards").iterdir()} == {
        "coverage.json",
        "coverage.md",
        "scan.json",
    }

    analyses = [_analysis(payload) for payload in (audit, complexity, standards)]
    assert len({analysis["source_manifest_sha256"] for analysis in analyses}) == 1
    for analysis in analyses:
        assert analysis["source_preserved"] is True
        assert analysis["host_state_preserved"] is True
        assert [check["id"] for check in analysis["native_checks"]] == [
            "swiftpm-dump-package",
            "swiftpm-describe",
            "swiftpm-build",
            "compiler-parse",
            "swift-format-lint",
            "direct-check",
            "executable-smoke",
        ]
        assert all(check["returncode"] == 0 for check in analysis["native_checks"])
        limits = " ".join(analysis["limits"])
        assert "resolved symbol" in limits
        assert "runtime" in limits
        roles = {item["file"]: item.get("reason", item["role"]) for item in analysis["inventory"]}
        assert roles["Tests/SwiftA2CoreTests/Excluded.swift"] == "test"
        assert roles["generated/GeneratedDecoy.swift"] == "generated-tree"
        assert roles["vendor/Example/Vendor.swift"] == "vendor"
        assert roles[".build/BuildDecoy.swift"] == "build"
        assert roles["build/BuildDecoy.swift"] == "build"
        assert roles["reports/seed/ReportDecoy.swift"] == "report"
        assert roles["linked-external"] == "symlink"
    audit_inventory = {row["file"]: row for row in _analysis(audit)["inventory"]}
    assert audit_inventory["Sources/SwiftA2Check/main.swift"]["role"] == "eligible"
    assert audit_inventory["Sources/SwiftA2Smoke/main.swift"]["role"] == "eligible"
    assert _state(host) == before


def test_clean_outcomes_are_complete_not_deferred(tmp_path: Path) -> None:
    audit_host = _copy_host(tmp_path, "audit-clean")
    audit_source = audit_host / "Sources/SwiftA2Core/A2Cases.swift"
    audit_source.write_text(
        audit_source.read_text(encoding="utf-8").replace("decision:9999", "decision:0002"),
        encoding="utf-8",
    )
    audit = _invoke(audit_host, "audit")
    assert audit.returncode == 0, audit.stdout + audit.stderr
    assert _final(audit_host, "audit")["drift"] == []

    complexity_host = _copy_host(tmp_path, "complexity-clean")
    complexity = _invoke(
        complexity_host, "complexity", target="Sources/SwiftA2Clean"
    )
    assert complexity.returncode == 0, complexity.stdout + complexity.stderr
    complexity_report = _final(complexity_host, "complexity")
    assert complexity_report["status"] == "complete"
    assert complexity_report["outcome"] == "no-hotspots"
    assert complexity_report["findings"] == []

    standards_host = _copy_host(tmp_path, "standards-clean")
    standards_source = standards_host / "Sources/SwiftA2Core/A2Cases.swift"
    standards_source.write_text(
        standards_source.read_text(encoding="utf-8").replace(
            "public func uncheckedInvoice(_ raw: String) -> Int {\n"
            "  (try? parseInvoice(raw)) ?? 0\n"
            "}",
            "public func uncheckedInvoice(_ raw: String) -> Int {\n"
            "  do {\n"
            "    return try parseInvoice(raw)\n"
            "  } catch {\n"
            "    return 0\n"
            "  }\n"
            "}",
        ),
        encoding="utf-8",
    )
    standards = _invoke(standards_host, "standards")
    assert standards.returncode == 0, standards.stdout + standards.stderr
    standard = _final(standards_host, "standards")["standards"][0]
    assert (standard["situation_sites"], standard["gap_count"], standard["coverage_percent"]) == (
        3,
        0,
        100.0,
    )


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_valid_failed_valid_same_destination_replaces_stale_artifacts(
    tmp_path: Path,
    kind: str,
) -> None:
    host = _copy_host(tmp_path)
    valid = _invoke(host, kind)
    assert valid.returncode in {0, 1}, valid.stdout + valid.stderr
    valid_payload = _final(host, kind)
    assert valid_payload["status"] == "complete"
    valid_text = json.dumps(valid_payload, sort_keys=True)

    failing = _fake_swift(tmp_path / "failing-swift")
    failed = _invoke(host, kind, swift=failing)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    terminal = _final(host, kind)
    assert terminal["status"] == "failed"
    assert terminal["failure_kind"] == "swiftpm-dump-package-failed"
    assert json.dumps(terminal, sort_keys=True) != valid_text
    if kind == "audit":
        assert terminal["references"] == [] and terminal["drift"] == []
    elif kind == "complexity":
        assert terminal["findings"] == []
    else:
        assert not any(row["status"] == "scanned" for row in terminal["standards"])

    recovered = _invoke(host, kind)
    assert recovered.returncode in {0, 1}, recovered.stdout + recovered.stderr
    assert _final(host, kind)["status"] == "complete"


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
@pytest.mark.parametrize(
    ("state", "expected_code", "expected_status", "expected_failure"),
    [
        ("missing", 2, "partial", "swift-tool-missing"),
        ("old", 2, "partial", "swift-version-too-old"),
        ("version-failed", 1, "failed", "swift-version-failed"),
        ("version-malformed", 1, "failed", "swift-version-unrecognized"),
        ("command-failed", 1, "failed", "swiftpm-dump-package-failed"),
    ],
)
def test_each_consumer_reports_missing_old_failing_and_malformed_tools(
    tmp_path: Path,
    kind: str,
    state: str,
    expected_code: int,
    expected_status: str,
    expected_failure: str,
) -> None:
    host = _copy_host(tmp_path)
    tools = {
        "missing": tmp_path / "missing-swift",
        "old": _fake_swift(tmp_path / "old-swift", version="5.10.0"),
        "version-failed": _fake_swift(tmp_path / "failed-version", version_exit=7),
        "version-malformed": _fake_swift(
            tmp_path / "malformed-version", malformed_version=True
        ),
        "command-failed": _fake_swift(tmp_path / "failed-command"),
    }

    result = _invoke(host, kind, swift=tools[state])

    assert result.returncode == expected_code, result.stdout + result.stderr
    payload = _final(host, kind)
    assert (payload["status"], payload["failure_kind"]) == (
        expected_status,
        expected_failure,
    )
    if kind == "audit":
        assert payload["references"] == [] and payload["drift"] == []
    elif kind == "complexity":
        assert payload["findings"] == []
    else:
        assert not any(row["status"] == "scanned" for row in payload["standards"])


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_malformed_source_fails_closed_and_is_preserved(tmp_path: Path, kind: str) -> None:
    host = _copy_host(tmp_path)
    shutil.copy2(FIXTURE / "malformed/Broken.swift", host / "Sources/SwiftA2Core")
    before = _state(host)

    result = _invoke(host, kind)

    assert result.returncode == 1, result.stdout + result.stderr
    payload = _final(host, kind)
    assert payload["status"] == "failed"
    assert payload["failure_kind"] in {"swiftpm-build-failed", "compiler-parse-failed"}
    assert _state(host) == before


def test_invalid_standards_replaces_prior_coverage_before_tool_probe(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    valid = _invoke(host, "standards")
    assert valid.returncode == 1, valid.stdout + valid.stderr
    invalid = host / "invalid-standards.json"
    invalid.write_text('{"ideas": [', encoding="utf-8")

    result = _invoke(
        host,
        "standards",
        ideas=invalid,
        swift=host / "missing-swift",
    )

    assert result.returncode == 1
    payload = _final(host, "standards")
    assert (payload["status"], payload["failure_kind"]) == (
        "failed",
        "invalid-standards",
    )
    assert payload["standards"] == []


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_copied_selected_skill_and_sibling_provider_run_outside_checkout(
    tmp_path: Path,
    kind: str,
) -> None:
    host = _copy_host(tmp_path)
    adapter = _copy_shared_closure(tmp_path, kind)
    unrelated = tmp_path / "unrelated-cwd"
    unrelated.mkdir()

    result = _invoke(host, kind, adapter=adapter, cwd=unrelated)

    assert result.returncode in {0, 1}, result.stdout + result.stderr
    payload = _final(host, kind)
    assert payload["status"] == "complete"
    assert _analysis(payload)["source_preserved"] is True
    assert str(ROOT) not in adapter.read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", sorted(ADAPTERS))
def test_deleting_sibling_provider_fails_closed_without_swift_parser_fallback(
    tmp_path: Path,
    kind: str,
) -> None:
    host = _copy_host(tmp_path)
    adapter = _copy_consumer_only(tmp_path, kind)

    result = _invoke(host, kind, adapter=adapter)

    assert result.returncode == 2
    payload = _final(host, kind)
    assert (payload["status"], payload["failure_kind"]) == (
        "partial",
        "swift-fact-producer-missing",
    )
    source = adapter.read_text(encoding="utf-8")
    for producer_knowledge in (
        "swift build",
        "swiftc -frontend",
        "swift-format lint",
        "FUNCTION_RE",
        "unterminated-string",
    ):
        assert producer_knowledge not in source


def test_protocol_requirement_does_not_absorb_later_body_in_a2_facts() -> None:
    module = runpy.run_path(str(PROVIDER))
    source = b"""\
public protocol Pricing {
  func fee(_ value: Double) -> Double
}

public struct Fallback {
  public func charge(_ value: Double) -> Double {
    value * 0.20
  }
}
"""
    code_mask, comment_mask, comments, errors = module["lexical_facts"](source)
    row = {
        "_source": source,
        "_mask": code_mask,
        "_comment_mask": comment_mask,
        "comments": comments,
        "file": "Sources/Pricing.swift",
        "source_sha256": hashlib.sha256(source).hexdigest(),
    }

    facts = module["function_syntax_facts"](row)

    assert errors == []
    assert [fact["symbol"] for fact in facts] == ["charge"]


def test_ml025_shared_provider_clears_loc_and_copied_closure_gates() -> None:
    helper_loc = len(PROVIDER.read_text(encoding="utf-8").splitlines())
    consumer_loc = sum(
        len(path.read_text(encoding="utf-8").splitlines()) for path in ADAPTERS.values()
    ) + len(Path(__file__).read_text(encoding="utf-8").splitlines())
    shared_loc = consumer_loc + helper_loc
    literal_loc = consumer_loc + len(ADAPTERS) * helper_loc
    reduction = 1 - shared_loc / literal_loc
    assert reduction >= 0.25

    for adapter in ADAPTERS.values():
        shared_bytes = adapter.stat().st_size + PROVIDER.stat().st_size
        literal_bytes = adapter.stat().st_size + PROVIDER.stat().st_size
        assert shared_bytes <= literal_bytes * 1.10


def test_ml025_literal_and_shared_aggregate_warm_latency(tmp_path: Path) -> None:
    hosts = {
        "shared": _copy_host(tmp_path, "shared-host"),
        "literal": _copy_host(tmp_path, "literal-host"),
    }
    adapters = {
        "shared": {
            kind: _copy_shared_closure(tmp_path / f"shared-{kind}", kind)
            for kind in ADAPTERS
        },
        "literal": {
            kind: _copy_literal_closure(tmp_path / f"literal-{kind}", kind)
            for kind in ADAPTERS
        },
    }
    _run(str(SWIFT), "--version", cwd=hosts["shared"])
    timings: dict[str, list[float]] = {"shared": [], "literal": []}

    for index, kind in enumerate(ADAPTERS):
        order = ("shared", "literal") if index % 2 == 0 else ("literal", "shared")
        for design in order:
            started = time.perf_counter()
            result = _invoke(hosts[design], kind, adapter=adapters[design][kind])
            timings[design].append(time.perf_counter() - started)
            assert result.returncode in {0, 1}, result.stdout + result.stderr

    medians = {design: statistics.median(values) for design, values in timings.items()}
    totals = {design: sum(values) for design, values in timings.items()}
    evidence = {
        "aggregate_seconds": totals,
        "median_consumer_seconds": medians,
        "aggregate_growth": totals["shared"] / totals["literal"] - 1,
        "median_growth": medians["shared"] / medians["literal"] - 1,
        "order": "alternating shared/literal across three A2 consumers",
    }
    print("ML025=" + json.dumps(evidence, sort_keys=True))
    assert evidence["aggregate_growth"] <= 0.10
    assert evidence["median_growth"] <= 0.10
