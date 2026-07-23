"""Swift A1 project/lexical consumers over one copied SwiftPM snapshot."""

from __future__ import annotations

import hashlib
import json
import runpy
import shutil
import statistics
import subprocess
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "swift-project-lexical"
PYTHON = Path(
    "/Users/khurrummahmood/Projects/engineering-skills-product/.venv/bin/python"  # host-ref-allow: frozen F2 runtime
)
SWIFT = Path("/usr/bin/swift")
SWIFTC = Path("/usr/bin/swiftc")
SWIFT_FORMAT = Path("/Library/Developer/CommandLineTools/usr/bin/swift-format")
COMMON = (
    ROOT
    / ".claude"
    / "skills"
    / "_swift-project-lexical"
    / "swift_project_facts.py"
)
SCRIPTS = {
    "adapt-project": ROOT
    / ".claude"
    / "skills"
    / "adapt-project"
    / "scripts"
    / "discover_swift.py",
    "explain-code": ROOT
    / ".claude"
    / "skills"
    / "explain-code"
    / "scripts"
    / "explain_swift.py",
    "find-comment-drift": ROOT
    / ".claude"
    / "skills"
    / "find-comment-drift"
    / "scripts"
    / "analyze_comments_swift.py",
    "find-concept-divergence": ROOT
    / ".claude"
    / "skills"
    / "find-concept-divergence"
    / "scripts"
    / "scan_swift.py",
    "find-duplication": ROOT
    / ".claude"
    / "skills"
    / "find-duplication"
    / "scripts"
    / "run_swift.py",
    "find-folder-topology-drift": ROOT
    / ".claude"
    / "skills"
    / "find-folder-topology-drift"
    / "scripts"
    / "detect_swift.py",
}
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (SWIFT, SWIFTC, SWIFT_FORMAT)),
    reason="Swift 6.3.3 Command Line Tools are required",
)


def _run(*args: str, cwd: Path, timeout: int = 180) -> subprocess.CompletedProcess[str]:
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


def _host_hashes(host: Path) -> dict[str, str]:
    return {
        path.relative_to(host).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(host.rglob("*"))
        if path.is_file()
        and not path.is_symlink()
        and "reports" not in path.relative_to(host).parts
    }


def _install_closures(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    install = tmp_path / "installed" / ".agents" / "skills"
    helper = install / "_swift-project-lexical" / COMMON.name
    helper.parent.mkdir(parents=True)
    shutil.copy2(COMMON, helper)
    copied: dict[str, Path] = {}
    for skill, source in SCRIPTS.items():
        destination = install / skill / "scripts" / source.name
        destination.parent.mkdir(parents=True)
        shutil.copy2(source, destination)
        copied[skill] = destination
    return helper, copied


def _install_literal_closures(tmp_path: Path) -> dict[str, Path]:
    install = tmp_path / "literal" / ".agents" / "skills"
    copied: dict[str, Path] = {}
    for skill, source in SCRIPTS.items():
        destination = install / skill / "scripts" / source.name
        destination.parent.mkdir(parents=True)
        text = source.read_text(encoding="utf-8").replace(
            'Path(__file__).resolve().parents[2] / "_swift-project-lexical"',
            "Path(__file__).resolve().parent",
        )
        destination.write_text(text, encoding="utf-8")
        shutil.copy2(COMMON, destination.parent / COMMON.name)
        copied[skill] = destination
    return copied


def _tool_args(swift: Path = SWIFT) -> tuple[str, ...]:
    return (
        "--swift",
        str(swift),
        "--swiftc",
        str(SWIFTC),
        "--swift-format",
        str(SWIFT_FORMAT),
        "--check-product",
        "swift-lexical-check",
        "--expected-check",
        "swift-lexical-checks-ok",
        "--smoke-product",
        "swift-lexical-smoke",
        "--expected-smoke",
        "swift-lexical:42",
    )


def _invoke(
    skill: str,
    script: Path,
    host: Path,
    *,
    swift: Path = SWIFT,
    clean: bool = False,
) -> subprocess.CompletedProcess[str]:
    base = (
        str(PYTHON),
        "-I",
        "-S",
        str(script),
        "--project-root",
        str(host),
        *_tool_args(swift),
    )
    if skill == "adapt-project":
        args = (*base, "--output-dir", str(host / "reports" / "adapt"), ".")
    elif skill == "explain-code":
        args = (
            *base,
            "--target",
            "Sources/SwiftLexicalSmoke" if clean else "Sources/BillingCore",
            "--output",
            str(host / "reports" / "explain" / "swift.md"),
        )
    elif skill == "find-comment-drift":
        args = (
            *base,
            "--target",
            "Sources/BillingCore",
            "--output-dir",
            str(host / "reports" / "comment"),
        )
    elif skill == "find-concept-divergence":
        args = (
            *base,
            "--glossary",
            str(host / ".claude" / "contracts" / "concepts.yaml"),
            "--output",
            str(host / "reports" / "concept" / "detections.jsonl"),
            "--report",
            str(host / "reports" / "concept" / "report.md"),
            "Sources/BillingCore",
        )
    elif skill == "find-duplication":
        args = (
            *base,
            "--target",
            "Sources/BillingCore",
            "--output-dir",
            str(host / "reports" / "duplication"),
        )
    else:
        args = (
            *base,
            "--swift-root",
            "Sources/BillingCore",
            "--output",
            str(host / "reports" / "folder" / "detections.jsonl"),
            *(("--allow-folder", "Sources/BillingCore") if clean else ()),
        )
    return _run(*args, cwd=host)


def _artifact(skill: str, host: Path) -> dict:
    paths = {
        "adapt-project": host / "reports" / "adapt" / "adapter.json",
        "explain-code": host / "reports" / "explain" / "swift" / "targets.json",
        "find-comment-drift": host / "reports" / "comment" / "findings.json",
        "find-concept-divergence": host / "reports" / "concept" / "findings.json",
        "find-duplication": host / "reports" / "duplication" / "findings.json",
        "find-folder-topology-drift": host / "reports" / "folder" / "findings.json",
    }
    return json.loads(paths[skill].read_text(encoding="utf-8"))


def _analysis(skill: str, payload: dict) -> dict:
    if skill == "find-duplication":
        return payload["scan_meta"]["analysis"]
    if skill == "explain-code":
        return payload["analysis"]["swift"]
    return payload["analysis"]["swift"]


def _fake_swift(
    path: Path,
    *,
    version: str = "6.3.3",
    version_exit: int = 0,
    command_exit: int = 9,
) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' 'Apple Swift version {version} (fixture)'\n"
        f"  exit {version_exit}\n"
        "fi\n"
        f"exit {command_exit}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_six_copied_value_outcomes_roles_native_and_source_preservation(
    tmp_path: Path,
) -> None:
    host = _copy_host(tmp_path)
    before = _host_hashes(host)
    helper, copied = _install_closures(tmp_path)

    results = {skill: _invoke(skill, script, host) for skill, script in copied.items()}
    assert all(result.returncode == 0 for result in results.values()), {
        skill: result.stdout + result.stderr for skill, result in results.items()
    }

    adapter = _artifact("adapt-project", host)
    assert adapter["status"] == "complete"
    assert adapter["stack"] == {
        "frameworks": [],
        "languages": ["swift"],
        "package_managers": ["swiftpm"],
    }
    assert adapter["source_roots"] == [
        {"path": "Sources", "source_languages": ["swift"], "swift_files": 9}
    ]
    assert adapter["commands"]["formal_test"] == []
    assert adapter["native_test_boundary"] == "unavailable-under-active-clt"
    assert (host / "reports" / "adapt" / "adapter.yml").is_file()
    assert json.loads((host / "reports" / "adapt" / "evidence.json").read_text())[
        "evidence"
    ] == {"adapter": "adapter.yml", "report": "report.md"}

    targets = _artifact("explain-code", host)
    assert targets["status"] == "complete"
    symbols = {row["symbol"] for row in targets["selected"]}
    assert {"Invoice", "InvoiceState", "parseBillingStatus", "serviceFee"} <= symbols
    assert "InternalSequence" not in symbols
    assert len(list((host / "reports" / "explain" / "swift" / "annotations").glob("*.md"))) == len(
        targets["selected"]
    )
    assert "compiler-validated lexical declaration" in (
        host / "reports" / "explain" / "swift.md"
    ).read_text()

    comments = _artifact("find-comment-drift", host)
    assert comments["status"] == "complete"
    assert comments["outcome"] == "advisory-findings"
    assert len(comments["findings"]) == 1
    comment = comments["findings"][0]
    assert comment["band"] == "adjacent_percentage_mismatch"
    assert comment["symbol"] == "serviceFee"
    assert comment["documented_percent"] == 10
    assert comment["fixed_multiplier"] == 0.2
    assert "lexical contradiction" in comment["claim_boundary"]

    concept = _artifact("find-concept-divergence", host)
    assert concept["status"] == "complete"
    assert concept["outcome"] == "drift-found"
    assert [(row["term"], row["file"]) for row in concept["findings"]] == [
        ("cancelled_order", "Sources/BillingCore/BillingParser.swift")
    ]

    duplication = _artifact("find-duplication", host)
    assert duplication["scan_meta"]["status"] == "complete"
    assert len(duplication["findings"]) == 1
    assert {site["symbol"] for site in duplication["findings"][0]["sites"]} == {
        "pendingInvoiceTotal",
        "queuedInvoiceTotal",
    }
    assert duplication["findings"][0]["semantic_identity_claimed"] is False

    folder = _artifact("find-folder-topology-drift", host)
    assert folder["status"] == "complete"
    assert folder["outcome"] == "drift-found"
    assert folder["findings"][0]["prefix"] == "Billing"
    assert set(folder["findings"][0]["files"]) == {
        "Sources/BillingCore/BillingModels.swift",
        "Sources/BillingCore/BillingParser.swift",
        "Sources/BillingCore/BillingTypes.swift",
        "Sources/BillingCore/BillingValidator.swift",
    }

    payloads = {
        "adapt-project": adapter,
        "explain-code": targets,
        "find-comment-drift": comments,
        "find-concept-divergence": concept,
        "find-duplication": duplication,
        "find-folder-topology-drift": folder,
    }
    analyses = [_analysis(skill, payload) for skill, payload in payloads.items()]
    assert len({analysis["source_manifest_sha256"] for analysis in analyses}) == 1
    for analysis in analyses:
        assert analysis["source_preserved"]
        assert analysis["host_state_preserved"]
        assert [row["id"] for row in analysis["native_checks"]] == [
            "swiftpm-dump-package",
            "swiftpm-describe",
            "swiftpm-build",
            "compiler-parse",
            "swift-format-lint",
            "direct-check",
            "executable-smoke",
        ]
        assert all(row["returncode"] == 0 for row in analysis["native_checks"])
        assert analysis["native_checks"][-2]["stdout"].strip() == "swift-lexical-checks-ok"
        assert analysis["native_checks"][-1]["stdout"].strip() == "swift-lexical:42"
        roles = {row["file"]: row.get("reason", row["role"]) for row in analysis["inventory"]}
        assert roles["Tests/BillingCoreTests/Excluded.swift"] == "test"
        assert roles["generated/GeneratedInvoice.swift"] == "generated-tree"
        assert roles["vendor/Example/Vendor.swift"] == "vendor"
        assert roles[".build/BuildSentinel.swift"] == "build"
        assert roles["build/BuildSentinel.swift"] == "build"
        assert roles["reports/decoys/BillingReport.swift"] == "report"
        assert roles["linked-external"] == "symlink"
    assert _host_hashes(host) == before
    assert helper.is_file()
    for script in copied.values():
        text = script.read_text(encoding="utf-8")
        assert "swift_project_facts" in text
        assert str(ROOT) not in text


def test_clean_and_below_threshold_outcomes(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    fee = host / "Sources" / "BillingCore" / "ServiceFee.swift"
    fee.write_text(fee.read_text().replace("10 percent", "20 percent"), encoding="utf-8")
    parser = host / "Sources" / "BillingCore" / "BillingParser.swift"
    parser.write_text(
        parser.read_text().replace("cancelled_order", "canceled_order"), encoding="utf-8"
    )
    check = host / "Sources" / "SwiftLexicalCheck" / "main.swift"
    check.write_text(
        check.read_text().replace("cancelled_order", "canceled_order"), encoding="utf-8"
    )
    queued = host / "Sources" / "BillingCore" / "QueuedInvoiceTotal.swift"
    queued.write_text(
        "public func queuedInvoiceTotal(_ amounts: [Int]) -> Int {\n"
        "  amounts.reduce(0, +)\n"
        "}\n",
        encoding="utf-8",
    )

    for skill in SCRIPTS:
        result = _invoke(skill, copied[skill], host, clean=True)
        assert result.returncode == 0, result.stdout + result.stderr

    assert _artifact("adapt-project", host)["standardization"]["cautions"] == [
        "Observed SwiftPM layout is objective evidence, not proof of a healthy standard."
    ]
    assert _artifact("explain-code", host)["public_symbol_count"] == 0
    assert _artifact("find-comment-drift", host)["outcome"] == "clean-within-complete"
    assert _artifact("find-concept-divergence", host)["outcome"] == "clean-within-complete"
    assert _artifact("find-duplication", host)["findings"] == []
    assert _artifact("find-folder-topology-drift", host)["outcome"] == "clean"


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_valid_failed_valid_same_destination_clears_stale(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    valid = _invoke(skill, copied[skill], host)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    assert (_artifact(skill, host).get("status") or _artifact(skill, host)["scan_meta"]["status"]) == "complete"

    failing = _fake_swift(tmp_path / "failing-swift")
    failed = _invoke(skill, copied[skill], host, swift=failing)
    assert failed.returncode == 1
    failed_payload = _artifact(skill, host)
    assert (failed_payload.get("status") or failed_payload["scan_meta"]["status"]) == "failed"
    assert failed_payload.get("findings", []) == []

    recovered = _invoke(skill, copied[skill], host)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert (_artifact(skill, host).get("status") or _artifact(skill, host)["scan_meta"]["status"]) == "complete"


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
@pytest.mark.parametrize("tool_state", ["missing", "old", "version-failed", "command-failed"])
def test_missing_old_and_failing_tools_are_visible(
    skill: str, tool_state: str, tmp_path: Path
) -> None:
    host = _copy_host(tmp_path)
    _, copied = _install_closures(tmp_path)
    tools = {
        "missing": tmp_path / "missing-swift",
        "old": _fake_swift(tmp_path / "old-swift", version="5.10.0"),
        "version-failed": _fake_swift(tmp_path / "version-failed", version_exit=7),
        "command-failed": _fake_swift(tmp_path / "command-failed"),
    }
    result = _invoke(skill, copied[skill], host, swift=tools[tool_state])
    payload = _artifact(skill, host)
    status = payload.get("status") or payload["scan_meta"]["status"]
    expected = (2, "partial") if tool_state in {"missing", "old"} else (1, "failed")
    assert (result.returncode, status) == expected
    assert payload.get("findings", []) == []


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_malformed_source_fails_and_preserves_source(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    shutil.copy2(FIXTURE / "malformed" / "Broken.swift", host / "Sources" / "BillingCore")
    before = _host_hashes(host)
    _, copied = _install_closures(tmp_path)

    result = _invoke(skill, copied[skill], host)

    assert result.returncode == 1
    payload = _artifact(skill, host)
    assert (payload.get("status") or payload["scan_meta"]["status"]) == "failed"
    assert _analysis(skill, payload)["failure_kind"] in {
        "swiftpm-build-failed",
        "compiler-parse-failed",
    }
    assert payload.get("findings", []) == []
    assert _host_hashes(host) == before


@pytest.mark.parametrize("skill", sorted(SCRIPTS))
def test_missing_swiftpm_manifest_is_partial_not_clean(skill: str, tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    (host / "Package.swift").unlink()
    _, copied = _install_closures(tmp_path)

    result = _invoke(skill, copied[skill], host)

    assert result.returncode == 2
    payload = _artifact(skill, host)
    assert (payload.get("status") or payload["scan_meta"]["status"]) == "partial"
    assert _analysis(skill, payload)["failure_kind"] == "swiftpm-project-incomplete"
    assert payload.get("findings", []) == []


def test_shared_snapshot_owns_policy_and_copied_closure_is_explicit() -> None:
    helper = COMMON.read_text(encoding="utf-8")
    for policy in (
        "swiftpm-dump-package",
        "swift-format-lint",
        "source_manifest_sha256",
        "generated-tree",
        "unexpected-source-mutation",
        "symlink",
        "no SwiftSyntax",
    ):
        assert policy in helper
    for script in SCRIPTS.values():
        text = script.read_text(encoding="utf-8")
        assert "collect_snapshot" in text
        assert "subprocess" not in text
        assert "--disable-automatic-resolution" not in text
        assert "generated-tree" not in text

    shared_loc = len(COMMON.read_text(encoding="utf-8").splitlines()) + sum(
        len(path.read_text(encoding="utf-8").splitlines()) for path in SCRIPTS.values()
    ) + len(Path(__file__).read_text(encoding="utf-8").splitlines())
    duplicated_loc = shared_loc + (len(SCRIPTS) - 1) * len(
        COMMON.read_text(encoding="utf-8").splitlines()
    )
    reduction = 1 - shared_loc / duplicated_loc
    assert reduction >= 0.25

    shared_selected_bytes = sum(
        COMMON.stat().st_size + path.stat().st_size for path in SCRIPTS.values()
    )
    literal_selected_bytes = sum(
        COMMON.stat().st_size + path.stat().st_size for path in SCRIPTS.values()
    )
    assert shared_selected_bytes <= literal_selected_bytes * 1.10


def test_swift_lexer_distinguishes_raw_strings_and_nested_comments() -> None:
    module = runpy.run_path(str(COMMON))
    source = (
        b'let raw = #"// Applies a 90 percent service fee."#\n'
        b"/* outer note /* nested note */ remains one comment */\n"
        b"/// Applies a 10 percent service fee.\n"
        b"public func fee(_ value: Double) -> Double { value * 0.20 }\n"
    )

    code_mask, comment_mask, comments, errors = module["lexical_facts"](source)

    assert errors == []
    assert [comment["kind"] for comment in comments] == ["block", "doc-line"]
    assert b"90 percent" not in code_mask
    assert b"nested note" not in comment_mask


def test_bodyless_protocol_requirement_does_not_absorb_later_declaration() -> None:
    module = runpy.run_path(str(COMMON))
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
    code_mask, comment_mask, _, errors = module["lexical_facts"](source)
    row = {
        "_source": source,
        "_mask": code_mask,
        "_comment_mask": comment_mask,
        "file": "Sources/Pricing.swift",
        "source_sha256": hashlib.sha256(source).hexdigest(),
    }

    facts = module["function_facts"](row)

    assert errors == []
    assert [fact["symbol"] for fact in facts] == ["charge"]


def test_ml025_literal_and_shared_aggregate_warm_latency(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    _, shared = _install_closures(tmp_path)
    literal = _install_literal_closures(tmp_path)
    _run(str(SWIFT), "--version", cwd=host)
    timings: dict[str, list[float]] = {"shared": [], "literal": []}

    for index, skill in enumerate(SCRIPTS):
        order = ("shared", "literal") if index % 2 == 0 else ("literal", "shared")
        for design in order:
            started = time.perf_counter()
            result = _invoke(skill, {"shared": shared, "literal": literal}[design][skill], host)
            timings[design].append(time.perf_counter() - started)
            assert result.returncode == 0, result.stdout + result.stderr

    medians = {design: statistics.median(values) for design, values in timings.items()}
    totals = {design: sum(values) for design, values in timings.items()}
    median_growth = medians["shared"] / medians["literal"] - 1
    aggregate_growth = totals["shared"] / totals["literal"] - 1
    evidence = {
        "aggregate_seconds": totals,
        "median_consumer_seconds": medians,
        "aggregate_growth": aggregate_growth,
        "median_growth": median_growth,
        "order": "alternating shared/literal across six consumers",
    }
    print("ML025=" + json.dumps(evidence, sort_keys=True))
    assert aggregate_growth <= 0.10
    assert median_growth <= 0.10
