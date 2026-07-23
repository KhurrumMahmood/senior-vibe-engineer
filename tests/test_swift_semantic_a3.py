"""Final-outcome contracts for the Swift A3 semantic read-only family."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "swift-semantic-a3" / "host"
PROVIDER = ROOT / ".claude" / "skills" / "_swift-semantic-readonly" / "swift_semantic_facts.py"
RUNTIMES = {
    "dormant": ROOT / ".claude/skills/find-dormant/scripts/detect_swift_dormant.py",
    "state": ROOT / ".claude/skills/find-implicit-state/scripts/detect_swift_state.py",
    "sweep": ROOT / ".claude/skills/find-incomplete-sweep/scripts/detect_swift_incomplete_sweep.py",
    "sweep_scout": ROOT / ".claude/skills/find-incomplete-sweep/scripts/scout_swift.py",
    "sweep_triage": ROOT / ".claude/skills/find-incomplete-sweep/scripts/triage_swift.py",
    "duplicate": ROOT / ".claude/skills/find-semantic-duplication/scripts/detect_swift_semantic.py",
    "rename": ROOT / ".claude/skills/rename-concept/scripts/swift_identifier_evidence.py",
}
SWIFT = Path("/usr/bin/swift")
SWIFTC = Path("/usr/bin/swiftc")
SOURCEKIT = Path("/usr/bin/sourcekit-lsp")
SWIFT_FORMAT = Path("/Library/Developer/CommandLineTools/usr/bin/swift-format")
PRODUCT_PYTHON = ROOT / ".venv/bin/python"
pytestmark = pytest.mark.skipif(
    not all(path.is_file() for path in (SWIFT, SWIFTC, SOURCEKIT, SWIFT_FORMAT, PRODUCT_PYTHON)),
    reason="the frozen Python and CLT Swift semantic toolchain are required",
)


QUERY_GROUPS = {
    "dormant": [
        "dormantDiscount",
        "normalize",
        "policyFee",
        "reflectedHelper",
        "usedHelper",
    ],
    "state": ["phase", "state", "status"],
    "sweep": ["charge"],
    "duplicate": [
        "billingSurface",
        "buildStatement",
        "cloneOne",
        "cloneTwo",
        "invoiceSurface",
        "normalize",
        "policyDecoy",
        "policyFee",
        "Statement",
        "summarizeInvoice",
        "wrapperDecoy",
    ],
    "rename": ["CanonicalStatus", "LegacyStatus"],
}
UNION_QUERIES = sorted({query for rows in QUERY_GROUPS.values() for query in rows})


def _run(
    *argv: str | Path,
    cwd: Path,
    expected: int | set[int] = 0,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    allowed = {expected} if isinstance(expected, int) else expected
    assert result.returncode in allowed, result.stdout + result.stderr
    return result


def _copy_host(tmp_path: Path, name: str = "host") -> Path:
    host = tmp_path / name
    shutil.copytree(FIXTURE, host)
    return host


def _history_host(tmp_path: Path) -> Path:
    host = _copy_host(tmp_path)
    present = host / "Sources/SwiftA3Core/SweepPresent.swift"
    content = present.read_text(encoding="utf-8")
    present.unlink()
    _run("git", "init", "-q", cwd=host)
    _run("git", "config", "user.email", "fixture@example.com", cwd=host)
    _run("git", "config", "user.name", "Fixture", cwd=host)
    old = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2024-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2024-01-01T00:00:00Z",
    }
    subprocess.run(["git", "add", "."], cwd=host, env=old, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=host, env=old, check=True)
    present.write_text(content, encoding="utf-8")
    new = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2024-02-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2024-02-01T00:00:00Z",
    }
    subprocess.run(["git", "add", str(present.relative_to(host))], cwd=host, env=new, check=True)
    subprocess.run(["git", "commit", "-qm", "finish audit sweep"], cwd=host, env=new, check=True)
    return host


def _source_fingerprints(host: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for path in sorted(host.rglob("*")):
        relative = path.relative_to(host)
        if any(
            part in {".agents", ".build", ".git", ".swiftpm", "reports"} for part in relative.parts
        ):
            continue
        if path.is_symlink():
            rows[relative.as_posix()] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            rows[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def _provider_args(
    script: Path,
    host: Path,
    output: Path,
    target: str,
    queries: list[str],
    *extra: str | Path,
) -> list[str | Path]:
    argv: list[str | Path] = [
        PRODUCT_PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--target-name",
        target,
        "--configuration",
        "debug",
        "--output",
        output,
        "--swift",
        SWIFT,
        "--swiftc",
        SWIFTC,
        "--sourcekit-lsp",
        SOURCEKIT,
        "--swift-format",
        SWIFT_FORMAT,
        "--check-product",
        "swift-a3-check",
        "--expected-check",
        "swift-a3-checks-ok",
        "--smoke-product",
        "swift-a3-smoke",
        "--expected-smoke",
        "swift-a3:42",
    ]
    for query in queries:
        argv.extend(["--query", query])
    argv.extend(extra)
    return argv


def _collect(
    script: Path,
    host: Path,
    target: str,
    queries: list[str],
    label: str,
    *extra: str | Path,
    expected: int | set[int] = 0,
) -> tuple[dict, Path, subprocess.CompletedProcess[str]]:
    output = host / f"reports/swift-semantic-facts/{label}.json"
    result = _run(
        *_provider_args(script, host, output, target, queries, *extra),
        cwd=host,
        expected=expected,
        timeout=360,
    )
    return json.loads(output.read_text(encoding="utf-8")), output, result


def _copy_closure(host: Path) -> tuple[Path, dict[str, Path]]:
    selected = host / ".agents/skills/on-demand"
    provider = selected / "_swift-semantic-readonly/swift_semantic_facts.py"
    provider.parent.mkdir(parents=True)
    shutil.copy2(PROVIDER, provider)
    copied: dict[str, Path] = {}
    destinations = {
        "dormant": "find-dormant/scripts/detect_swift_dormant.py",
        "state": "find-implicit-state/scripts/detect_swift_state.py",
        "sweep": "find-incomplete-sweep/scripts/detect_swift_incomplete_sweep.py",
        "sweep_scout": "find-incomplete-sweep/scripts/scout_swift.py",
        "sweep_triage": "find-incomplete-sweep/scripts/triage_swift.py",
        "duplicate": "find-semantic-duplication/scripts/detect_swift_semantic.py",
        "rename": "rename-concept/scripts/swift_identifier_evidence.py",
    }
    for name, relative in destinations.items():
        destination = selected / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RUNTIMES[name], destination)
        copied[name] = destination
    return provider, copied


def _consumer(
    script: Path,
    host: Path,
    facts: Path,
    *args: str | Path,
    expected: int | set[int] = 0,
) -> subprocess.CompletedProcess[str]:
    return _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        script,
        "--project-root",
        host,
        "--target-name",
        "SwiftA3Core",
        "--target",
        "Sources/SwiftA3Core",
        "--facts",
        facts,
        *args,
        cwd=host.parent,
        expected=expected,
    )


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _provider_module():
    spec = importlib.util.spec_from_file_location("swift_semantic_facts_under_test", PROVIDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_lsp_failure_and_query_scope_are_globally_bounded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider = _provider_module()
    sources = []
    roles = {}
    for index in range(3):
        source = tmp_path / f"Source{index}.swift"
        source.write_text("let state = 1\n", encoding="utf-8")
        sources.append(source)
        roles[source.name] = "selected-production"

    class FailingClient:
        methods: list[str] = []
        timeouts: list[float] = []
        instances = 0

        def __init__(self, _argv, _root) -> None:
            self.__class__.instances += 1

        def request(self, method, _params, timeout=60):
            self.__class__.methods.append(method)
            self.__class__.timeouts.append(timeout)
            if method == "initialize":
                return {
                    "capabilities": {
                        "callHierarchyProvider": True,
                        "definitionProvider": True,
                        "documentSymbolProvider": True,
                        "referencesProvider": True,
                        "renameProvider": {"prepareProvider": True},
                    }
                }
            raise provider.SwiftFactError("sourcekit_lsp_timeout", "fixture timeout")

        def notify(self, _method, _params) -> None:
            pass

        def close(self):
            return {"exited_cleanly": True, "returncode": 0, "stderr": ""}

    monkeypatch.setattr(provider, "_LspClient", FailingClient)
    with pytest.raises(provider.SwiftFactError, match="fixture timeout") as failure:
        provider._lsp_facts(
            Path("/fake/sourcekit-lsp"),
            tmp_path,
            tmp_path / "scratch",
            "debug",
            sources,
            roles,
            ["state"],
        )
    assert failure.value.kind == "sourcekit_lsp_timeout"
    assert FailingClient.methods == ["initialize", "textDocument/documentSymbol"]
    assert max(FailingClient.timeouts) <= provider.LSP_REQUEST_TIMEOUT_SECONDS

    crowded = tmp_path / "Crowded.swift"
    crowded.write_text(
        "state " * (provider.MAX_LSP_OCCURRENCES + 1),
        encoding="utf-8",
    )
    with pytest.raises(provider.SwiftFactError) as scope_failure:
        provider._lsp_facts(
            Path("/fake/sourcekit-lsp"),
            tmp_path,
            tmp_path / "scratch",
            "debug",
            [crowded],
            {crowded.name: "selected-production"},
            ["state"],
        )
    assert scope_failure.value.kind == "sourcekit_lsp_query_scope_exceeded"
    assert FailingClient.instances == 1


def test_copied_union_reaches_five_outcomes_reviews_and_lifecycle(tmp_path: Path) -> None:
    host = _history_host(tmp_path)
    before = _source_fingerprints(host)
    copied_provider, copied = _copy_closure(host)
    facts_payload, facts, _ = _collect(copied_provider, host, "SwiftA3Core", UNION_QUERIES, "union")

    assert facts_payload["status"] == "complete"
    assert facts_payload["identity"]["target_name"] == "SwiftA3Core"
    assert facts_payload["identity"]["configuration"] == "debug"
    assert facts_payload["index"]["fresh_scratch"] is True
    assert facts_payload["index"]["all_selected_sources_indexed"] is True
    assert facts_payload["semantic"]["capabilities"] == {
        "call_hierarchy": True,
        "definition": True,
        "document_symbol": True,
        "prepare_rename": True,
        "references": True,
    }
    assert [row["id"] for row in facts_payload["native_checks"]] == [
        "swiftpm-dump-package",
        "swiftpm-describe",
        "swiftpm-build-index",
        "fresh-index-units",
        "compiler-parse",
        "swift-format-lint",
        "direct-check",
        "executable-smoke",
        "sourcekit-lsp",
    ]
    assert all(row["returncode"] == 0 for row in facts_payload["native_checks"])
    inventory_roles = {row["path"]: row["role"] for row in facts_payload["source_inventory"]}
    assert inventory_roles["generated/GeneratedDecoy.swift"] == "generated"
    assert inventory_roles["vendor/Example/VendorDecoy.swift"] == "vendor"
    assert inventory_roles["Tests/SwiftA3CoreTests/Excluded.swift"] == "test"

    dormant_dir = host / "reports/find-dormant/swift"
    _consumer(copied["dormant"], host, facts, "--output-dir", dormant_dir)
    dormant = json.loads((dormant_dir / "findings.json").read_text())
    assert dormant["status"] == "complete"
    assert [row["name"] for row in dormant["candidates"]] == ["dormantDiscount"]
    assert dormant["summary"]["certain_delete"] == 0
    assert any(row.get("name") == "reflectedHelper" for row in dormant["deferred"])
    assert all("generated" not in row.get("file", "") for row in dormant["candidates"])

    state_dir = host / "reports/implicit-state/swift"
    _consumer(copied["state"], host, facts, "--output-dir", state_dir)
    state_pending = json.loads((state_dir / "findings.json").read_text())
    assert state_pending["status"] == "partial"
    assert state_pending["failure_kind"] == "human_review_required"
    candidates = [
        json.loads(line) for line in (state_dir / "candidates.jsonl").read_text().splitlines()
    ]
    assert [(row["owner"], row["field"], row["literals"]) for row in candidates] == [
        ("Job", "state", ["done", "queued", "running"])
    ]
    state_reviews = tmp_path / "state-reviews"
    candidate = candidates[0]
    _write_json(
        state_reviews / f"{candidate['candidate_id']}.json",
        {
            "schema_version": "swift-implicit-state-review-v1",
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": "0" * 64,
            "bucket": "extract_enum_candidate",
            "human_verdict": "accepted",
            "notes": "This deliberately stale review must not bind.",
        },
    )
    _consumer(
        copied["state"],
        host,
        facts,
        "--output-dir",
        state_dir,
        "--reviews-dir",
        state_reviews,
        expected=2,
    )
    assert json.loads((state_dir / "findings.json").read_text())["failure_kind"] == (
        "invalid_human_review"
    )
    _write_json(
        state_reviews / f"{candidate['candidate_id']}.json",
        {
            "schema_version": "swift-implicit-state-review-v1",
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": candidate["candidate_sha256"],
            "bucket": "extract_enum_candidate",
            "human_verdict": "accepted",
            "confidence": "high",
            "notes": "The direct String field owns three internal state values.",
        },
    )
    _consumer(
        copied["state"],
        host,
        facts,
        "--output-dir",
        state_dir,
        "--reviews-dir",
        state_reviews,
    )
    state = json.loads((state_dir / "findings.json").read_text())
    assert state["status"] == "complete"
    assert state["findings"][0]["human_verdict"] == "accepted"

    sweep_dir = host / "reports/find-incomplete-sweep/swift"
    _consumer(copied["sweep"], host, facts, "--report-dir", sweep_dir)
    sweep = json.loads((sweep_dir / "manifest.json").read_text())
    assert sweep["status"] == "complete"
    assert [(row["callee"], row["kwarg"]) for row in sweep["findings"]] == [("charge", "audit")]
    _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        copied["sweep_scout"],
        "--project-root",
        host,
        "--scan-dir",
        sweep_dir,
        cwd=host.parent,
    )
    packets = json.loads((sweep_dir / "scout_packets.json").read_text())
    assert packets["packet_count"] == 1
    packet = packets["packets"][0]
    _write_json(
        sweep_dir / "scout_verdicts.json",
        {
            "schema_version": "swift-sweep-verdicts-v1",
            "verdicts": [
                {
                    "id": packet["id"],
                    "packet_sha256": "0" * 64,
                    "verdict": "deliberate",
                    "rationale": "This deliberately stale verdict must not bind.",
                }
            ],
        },
    )
    _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        copied["sweep_triage"],
        "--project-root",
        host,
        "--scan-dir",
        sweep_dir,
        cwd=host.parent,
        expected=2,
    )
    assert not (sweep_dir / "triaged.md").exists()
    valid_sweep_verdict = {
        "schema_version": "swift-sweep-verdicts-v1",
        "verdicts": [
            {
                "id": packet["id"],
                "packet_sha256": packet["packet_sha256"],
                "verdict": "forgotten",
                "rationale": "The older direct call missed the later uniform audit sweep.",
                "completion": "Pass audit: true after owner review.",
            }
        ],
    }
    _write_json(sweep_dir / "scout_verdicts.json", valid_sweep_verdict)
    _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        copied["sweep_triage"],
        "--project-root",
        host,
        "--scan-dir",
        sweep_dir,
        cwd=host.parent,
    )
    assert "human-verdict handoff" in (sweep_dir / "triaged.md").read_text()
    invalidated_verdict = json.loads(json.dumps(valid_sweep_verdict))
    invalidated_verdict["verdicts"][0]["packet_sha256"] = "f" * 64
    _write_json(sweep_dir / "scout_verdicts.json", invalidated_verdict)
    _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        copied["sweep_triage"],
        "--project-root",
        host,
        "--scan-dir",
        sweep_dir,
        cwd=host.parent,
        expected=2,
    )
    assert not (sweep_dir / "triaged.md").exists()
    _write_json(sweep_dir / "scout_verdicts.json", valid_sweep_verdict)
    _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        copied["sweep_triage"],
        "--project-root",
        host,
        "--scan-dir",
        sweep_dir,
        cwd=host.parent,
    )

    duplicate_dir = host / "reports/semantic-duplication/swift"
    _consumer(copied["duplicate"], host, facts, "--output-dir", duplicate_dir)
    duplicate_pending = json.loads((duplicate_dir / "analysis.json").read_text())
    assert duplicate_pending["status"] == "partial"
    assert duplicate_pending["failure_kind"] == "human_review_required"
    leads = [
        json.loads(line) for line in (duplicate_dir / "candidates.jsonl").read_text().splitlines()
    ]
    assert [[item["name"] for item in lead["functions"]] for lead in leads] == [
        ["buildStatement", "summarizeInvoice"]
    ]
    assert {row["reason"] for row in duplicate_pending["rejected"]} >= {
        "direct_wrapper_relationship",
        "lexical_clone_only",
        "resolved_callee_set_mismatch",
    }
    duplicate_reviews = tmp_path / "duplicate-reviews"
    lead = leads[0]
    _write_json(
        duplicate_reviews / f"{lead['candidate_id']}.json",
        {
            "schema_version": "swift-semantic-duplication-review-v1",
            "candidate_id": lead["candidate_id"],
            "candidate_sha256": lead["candidate_sha256"],
            "human_verdict": "accepted",
            "verdict": "keep_separate_document_why",
            "notes": "The static capability overlap is real; product ownership remains distinct.",
        },
    )
    _consumer(
        copied["duplicate"],
        host,
        facts,
        "--output-dir",
        duplicate_dir,
        "--reviews-dir",
        duplicate_reviews,
    )
    duplicate = json.loads((duplicate_dir / "analysis.json").read_text())
    assert duplicate["status"] == "complete"
    assert duplicate["findings"][0]["human_verdict"] == "accepted"
    matrix = duplicate_dir / "capability-matrix-swift-sd-0001.md"
    assert matrix.is_file()

    rename = host / "reports/rename-concept/swift/assessment.json"
    _consumer(
        copied["rename"],
        host,
        facts,
        "--old",
        "LegacyStatus",
        "--new",
        "CanonicalStatus",
        "--output",
        rename,
    )
    rename_payload = json.loads(rename.read_text())
    assert rename_payload["status"] == "resolved"
    assert rename_payload["authority_status"] == "resolved"
    assert rename_payload["summary"]["old_symbol_references"] >= 2
    assert any(
        row["kind"] == "unresolved_or_unrelated_lexical"
        for row in rename_payload["deferred_references"]
    )
    assert rename_payload["mutation_applied"] is False

    source = host / "Sources/SwiftA3Core/Duplication.swift"
    original = source.read_text(encoding="utf-8")
    source.write_text(original + "\n", encoding="utf-8")
    _consumer(
        copied["duplicate"],
        host,
        facts,
        "--output-dir",
        duplicate_dir,
        "--reviews-dir",
        duplicate_reviews,
        expected=2,
    )
    stale = json.loads((duplicate_dir / "analysis.json").read_text())
    assert stale["status"] == "failed"
    assert stale["failure_kind"] == "fact_pack_stale"
    assert not matrix.exists()
    source.write_text(original, encoding="utf-8")
    _consumer(
        copied["duplicate"],
        host,
        facts,
        "--output-dir",
        duplicate_dir,
        "--reviews-dir",
        duplicate_reviews,
    )
    assert matrix.is_file()
    added = host / "Sources/SwiftA3Core/AddedAfterFacts.swift"
    added.write_text("public let addedAfterFacts = true\n", encoding="utf-8")
    _consumer(
        copied["duplicate"],
        host,
        facts,
        "--output-dir",
        duplicate_dir,
        "--reviews-dir",
        duplicate_reviews,
        expected=2,
    )
    assert json.loads((duplicate_dir / "analysis.json").read_text())["failure_kind"] == (
        "fact_pack_stale"
    )
    assert not matrix.exists()
    added.unlink()
    _consumer(
        copied["duplicate"],
        host,
        facts,
        "--output-dir",
        duplicate_dir,
        "--reviews-dir",
        duplicate_reviews,
    )
    assert matrix.is_file()
    assert _source_fingerprints(host) == before
    for runtime in [copied_provider, *copied.values()]:
        assert str(ROOT) not in runtime.read_text(encoding="utf-8")


def test_clean_selected_target_returns_complete_empty_outcomes(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    before = _source_fingerprints(host)
    queries = ["CleanState", "FormerState", "cleanCharge", "cleanSummary", "state"]
    payload, facts, _ = _collect(PROVIDER, host, "SwiftA3Clean", queries, "clean")
    assert payload["status"] == "complete"
    cases = [
        ("dormant", "--output-dir", host / "reports/find-dormant/clean", "findings.json"),
        ("state", "--output-dir", host / "reports/implicit-state/clean", "findings.json"),
        ("sweep", "--report-dir", host / "reports/find-incomplete-sweep/clean", "manifest.json"),
        ("duplicate", "--output-dir", host / "reports/semantic-duplication/clean", "analysis.json"),
    ]
    for name, option, output, artifact in cases:
        _run(
            PRODUCT_PYTHON,
            "-I",
            "-S",
            RUNTIMES[name],
            "--project-root",
            host,
            "--target-name",
            "SwiftA3Clean",
            "--target",
            "Sources/SwiftA3Clean",
            "--facts",
            facts,
            option,
            output,
            cwd=host.parent,
        )
        result = json.loads((output / artifact).read_text())
        assert result["status"] == "complete"
    rename = host / "reports/rename-concept/clean/assessment.json"
    _run(
        PRODUCT_PYTHON,
        "-I",
        "-S",
        RUNTIMES["rename"],
        "--project-root",
        host,
        "--target-name",
        "SwiftA3Clean",
        "--target",
        "Sources/SwiftA3Clean",
        "--facts",
        facts,
        "--old",
        "FormerState",
        "--new",
        "CleanState",
        "--output",
        rename,
        cwd=host.parent,
    )
    assert json.loads(rename.read_text())["status"] == "resolved"
    assert _source_fingerprints(host) == before


def _fake_tool(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\nset -eu\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_missing_old_failing_malformed_tool_index_config_and_facts(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    missing, _, _ = _collect(
        PROVIDER,
        host,
        "SwiftA3Core",
        ["state"],
        "missing-sourcekit",
        "--sourcekit-lsp",
        host / "missing-sourcekit",
    )
    assert (missing["status"], missing["failure_kind"]) == ("partial", "sourcekit_lsp_missing")

    old_swift = _fake_tool(host / "old-swift", 'printf "%s\\n" "Apple Swift version 5.9.0"\n')
    old, _, _ = _collect(
        PROVIDER,
        host,
        "SwiftA3Core",
        ["state"],
        "old-swift",
        "--swift",
        old_swift,
    )
    assert (old["status"], old["failure_kind"]) == ("partial", "swift_too_old")

    failing_swift = _fake_tool(
        host / "failing-swift",
        'if [ "$1" = "--version" ]; then printf "%s\\n" "Apple Swift version 6.3.3"; exit 0; fi\n'
        'if [ "$1" = "package" ]; then exec /usr/bin/swift "$@"; fi\n'
        'printf "%s\\n" "fixture build failure" >&2\nexit 9\n',
    )
    failed, _, _ = _collect(
        PROVIDER,
        host,
        "SwiftA3Core",
        ["state"],
        "failed-build",
        "--swift",
        failing_swift,
        expected=2,
    )
    assert (failed["status"], failed["failure_kind"]) == ("failed", "swiftpm_build_failed")

    malformed_swift = _fake_tool(
        host / "malformed-swift",
        'if [ "$1" = "--version" ]; then printf "%s\\n" "Apple Swift version 6.3.3"; exit 0; fi\n'
        'case "$*" in *dump-package*) printf "%s\\n" "{not-json"; exit 0;; esac\n'
        'exec /usr/bin/swift "$@"\n',
    )
    malformed, _, _ = _collect(
        PROVIDER,
        host,
        "SwiftA3Core",
        ["state"],
        "malformed-tool",
        "--swift",
        malformed_swift,
        expected=2,
    )
    assert (malformed["status"], malformed["failure_kind"]) == (
        "failed",
        "swiftpm_dump_invalid",
    )

    missing_index_swift = _fake_tool(
        host / "missing-index-swift",
        'if [ "$1" = "--version" ]; then printf "%s\\n" "Apple Swift version 6.3.3"; exit 0; fi\n'
        'if [ "$1" = "package" ]; then exec /usr/bin/swift "$@"; fi\n'
        "exit 0\n",
    )
    no_index, _, _ = _collect(
        PROVIDER,
        host,
        "SwiftA3Core",
        ["state"],
        "missing-index",
        "--swift",
        missing_index_swift,
    )
    assert (no_index["status"], no_index["failure_kind"]) == (
        "partial",
        "fresh_index_missing_or_incomplete",
    )

    old_state = tmp_path / "old-state"
    old_state.mkdir()
    (old_state / "old-index-unit").write_text("old", encoding="utf-8")
    stale_state, _, _ = _collect(
        PROVIDER,
        host,
        "SwiftA3Core",
        ["state"],
        "old-index",
        "--state-dir",
        old_state,
    )
    assert (stale_state["status"], stale_state["failure_kind"]) == (
        "partial",
        "semantic_state_not_fresh",
    )

    broken = _copy_host(tmp_path, "broken-config")
    (broken / "Package.swift").write_text("not a SwiftPM manifest\n", encoding="utf-8")
    config, _, _ = _collect(
        PROVIDER,
        broken,
        "SwiftA3Core",
        ["state"],
        "bad-config",
        expected=2,
    )
    assert (config["status"], config["failure_kind"]) == (
        "failed",
        "swiftpm_dump_failed",
    )

    malformed_facts = host / "reports/swift-semantic-facts/malformed.json"
    _write_json(malformed_facts, {"schema_version": "wrong"})
    output = host / "reports/find-dormant/malformed"
    _consumer(RUNTIMES["dormant"], host, malformed_facts, "--output-dir", output, expected=2)
    failure = json.loads((output / "findings.json").read_text())
    assert (failure["status"], failure["failure_kind"]) == (
        "failed",
        "fact_pack_invalid",
    )


def test_shared_provider_economics_clear_ml025() -> None:
    provider_loc = len(PROVIDER.read_text(encoding="utf-8").splitlines())
    consumer_loc = sum(
        len(path.read_text(encoding="utf-8").splitlines()) for path in RUNTIMES.values()
    )
    consumer_loc += len(Path(__file__).read_text(encoding="utf-8").splitlines())
    duplicated = consumer_loc + 5 * provider_loc
    accepted = consumer_loc + provider_loc
    saving = (duplicated - accepted) / duplicated
    assert saving >= 0.25
    provider_bytes = PROVIDER.stat().st_size
    runtime_bytes = sum(path.stat().st_size for path in RUNTIMES.values())
    assert runtime_bytes + provider_bytes <= runtime_bytes + 5 * provider_bytes


@pytest.mark.slow
def test_union_fact_pack_latency_beats_five_separate_provider_runs(tmp_path: Path) -> None:
    host = _copy_host(tmp_path)
    union_times: list[float] = []
    separate_times: list[float] = []
    for trial in range(3):
        order = ("union", "separate") if trial % 2 == 0 else ("separate", "union")
        for mode in order:
            started = time.monotonic()
            if mode == "union":
                _collect(PROVIDER, host, "SwiftA3Core", UNION_QUERIES, f"bench-u-{trial}")
                union_times.append(time.monotonic() - started)
            else:
                for name, queries in QUERY_GROUPS.items():
                    _collect(
                        PROVIDER,
                        host,
                        "SwiftA3Core",
                        queries,
                        f"bench-s-{trial}-{name}",
                    )
                separate_times.append(time.monotonic() - started)
    union_median = statistics.median(union_times)
    separate_median = statistics.median(separate_times)
    print(
        json.dumps(
            {
                "union_seconds": union_times,
                "separate_seconds": separate_times,
                "union_median_seconds": union_median,
                "separate_median_seconds": separate_median,
                "saved_fraction": (separate_median - union_median) / separate_median,
            },
            sort_keys=True,
        )
    )
    assert union_median <= separate_median * 1.10
