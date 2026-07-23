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
FIXTURE = ROOT / "tests/fixtures/dart-d4-calls"
PROVIDER = ROOT / ".claude/skills/map-subsystem/scripts/dart_lsp_facts.py"
DART = Path("/opt/homebrew/bin/dart")
CALL_QUERIES = [
    "compute",
    "dynamicDispatch",
    "externalCall",
    "finalize",
    "normalize",
    "orchestrate",
]


def _load_provider(path: Path = PROVIDER):
    spec = importlib.util.spec_from_file_location("test_dart_call_hierarchy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(
    argv: list[str], cwd: Path, *, expected: int = 0
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, timeout=120, check=False
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return result


def _copy_host(tmp_path: Path) -> Path:
    destination = tmp_path / "host"
    shutil.copytree(FIXTURE / "host", destination, ignore=shutil.ignore_patterns("reports"))
    return destination


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink() and "reports" not in path.parts
    }


def _query(
    facts: dict[str, object], name: str, path: str, detail: str
) -> dict[str, object]:
    matches = [
        row
        for row in facts["call_hierarchy_queries"]
        if row["caller"]["name"] == name
        and row["caller"]["path"] == path
        and row["caller"]["detail"] == detail
    ]
    assert len(matches) == 1
    return matches[0]


def _site_text(root: Path, site: dict[str, object]) -> str:
    line = (root / site["path"]).read_text().splitlines()[site["line"] - 1]
    return line[site["column"] - 1 : site["end_column"] - 1]


@pytest.fixture()
def call_pack(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    if not DART.is_file():
        pytest.skip("Dart 3.12 SDK is unavailable")
    host = _copy_host(tmp_path)
    before = _snapshot(host)
    output = host / "reports/dart-lsp-facts/calls.json"
    _run(
        [
            sys.executable,
            str(PROVIDER),
            "--project-root",
            str(host),
            "--target",
            ".",
            *sum((["--query", name] for name in CALL_QUERIES), []),
            "--dart",
            str(DART),
            "--output",
            "reports/dart-lsp-facts/calls.json",
        ],
        ROOT,
    )
    assert _snapshot(host) == before
    return host, json.loads(output.read_text())


def test_exact_resolved_outgoing_identity_aliases_collisions_and_uncertainty(
    call_pack: tuple[Path, dict[str, object]],
) -> None:
    host, facts = call_pack
    provider = _load_provider()
    assert facts["status"] == "partial"
    assert facts["failure_kind"] == "call_hierarchy_uncertainty"
    assert facts["missing_capabilities"] == []
    assert facts["call_hierarchy_summary"] == {
        "callers": 9,
        "complete": 7,
        "partial": 2,
        "resolved_edges": 11,
        "unresolved": 2,
    }
    assert {
        "textDocument/prepareCallHierarchy",
        "callHierarchy/outgoingCalls",
    }.issubset(facts["query_plan"]["requests"])
    assert facts["server"]["info"] == {
        "name": "Dart SDK LSP Analysis Server",
        "version": "3.12.2",
    }

    orchestrate = _query(facts, "orchestrate", "lib/orchestrator.dart", "orchestrator.dart")
    expected = {
        ("Alpha", "lib/owners/alpha.dart", "Alpha"),
        ("Beta", "lib/owners/beta.dart", "Beta"),
        ("compute", "lib/owners/alpha.dart", "alpha.dart"),
        ("compute", "lib/owners/beta.dart", "beta.dart"),
        ("compute", "lib/owners/alpha.dart", "Alpha"),
        ("compute", "lib/owners/beta.dart", "Beta"),
    }
    resolved = {
        (edge["callee"]["name"], edge["callee"]["path"], edge["callee"]["detail"])
        for edge in orchestrate["outgoing_calls"]
    }
    assert resolved == expected
    assert len({edge["callee"]["symbol_id"] for edge in orchestrate["outgoing_calls"]}) == 6
    assert orchestrate["status"] == "complete"
    assert orchestrate["prepare"] == {
        "method": "textDocument/prepareCallHierarchy",
        "result_count": 1,
        "status": "resolved",
    }
    assert orchestrate["outgoing_status"] == "resolved"
    assert orchestrate["uncertainties"] == []
    assert all(edge["resolution"] == "resolved-first-party" for edge in orchestrate["outgoing_calls"])
    assert all(
        _site_text(host, site).endswith(edge["callee"]["name"])
        for edge in orchestrate["outgoing_calls"]
        for site in edge["call_sites"]
    )
    identities = [orchestrate["caller"], *[row["callee"] for row in orchestrate["outgoing_calls"]]]
    for identity in identities:
        unhashed = dict(identity)
        symbol_id = unhashed.pop("symbol_id")
        assert symbol_id == f"dart:{provider._canonical_hash(unhashed)}"
        assert identity["declaration_range"]["end_line"] >= identity["declaration_range"]["line"]
        assert identity["selection_range"]["end_column"] > identity["selection_range"]["column"]
    assert orchestrate["source_sha256"] == hashlib.sha256(
        (host / "lib/orchestrator.dart").read_bytes()
    ).hexdigest()

    alpha_method = _query(facts, "compute", "lib/owners/alpha.dart", "Alpha")
    beta_method = _query(facts, "compute", "lib/owners/beta.dart", "Beta")
    assert [(row["callee"]["name"], row["callee"]["path"]) for row in alpha_method["outgoing_calls"]] == [
        ("normalize", "lib/shared.dart")
    ]
    assert [(row["callee"]["name"], row["callee"]["path"]) for row in beta_method["outgoing_calls"]] == [
        ("finalize", "lib/shared.dart")
    ]

    dynamic = _query(
        facts, "dynamicDispatch", "lib/orchestrator.dart", "orchestrator.dart"
    )
    assert dynamic["status"] == "partial"
    assert dynamic["outgoing_calls"] == []
    assert dynamic["uncertainties"] == [
        {
            "column": 21,
            "kind": "dynamic-type-syntax",
            "line": 13,
            "path": "lib/orchestrator.dart",
            "reason": "runtime dispatch target is not closed by static call hierarchy",
        }
    ]

    external = _query(
        facts, "externalCall", "lib/orchestrator.dart", "orchestrator.dart"
    )
    assert external["status"] == "partial"
    assert len(external["outgoing_calls"]) == 1
    assert external["outgoing_calls"][0]["resolution"] == "resolved-external"
    assert external["outgoing_calls"][0]["callee"]["path"] is None
    assert external["outgoing_calls"][0]["callee"]["uri_sha256"]
    assert external["uncertainties"][0]["kind"] == "callee-outside-production-scope"
    assert not any(
        row["caller"]["path"].startswith("generated/")
        or row["caller"]["path"].startswith("lib/generated/")
        for row in facts["call_hierarchy_queries"]
    )
    assert all(row["source_sha256"] for row in facts["call_hierarchy_queries"])
    assert all(row["method"] == "callHierarchy/outgoingCalls" for row in facts["call_hierarchy_queries"])
    assert facts["fact_pack_sha256"]
    assert facts["query_plan_sha256"]


def test_failing_analyzer_cannot_emit_complete_call_facts(tmp_path: Path) -> None:
    provider = _load_provider()
    host = _copy_host(tmp_path)
    fake = tmp_path / "failing-dart"
    # Reuse the established fake server helper shape without adding an alternate parser.
    fake.write_text("#!/bin/sh\nexit 7\n")
    fake.chmod(0o755)
    try:
        facts = provider.collect(host, ".", [], dart=str(fake), timeout=0.2)
    finally:
        fake.unlink(missing_ok=True)
    assert facts["status"] == "failed"
    assert facts["failure_kind"] == "dart_missing_or_broken"
    assert facts["call_hierarchy_queries"] == []


def test_outgoing_request_failure_and_malformed_result_are_explicit(tmp_path: Path) -> None:
    provider = _load_provider()
    host = _copy_host(tmp_path)
    root = host.resolve()
    inventory_rows = provider._inventory(root, root)
    inventory = {row["path"]: row for row in inventory_rows}
    source = "lib/orchestrator.dart"
    candidate = {
        "source": source,
        "parent": None,
        "item": {
            "name": "orchestrate",
            "kind": 12,
            "detail": "(int value)",
            "range": {
                "start": {"line": 3, "character": 0},
                "end": {"line": 10, "character": 1},
            },
            "selectionRange": {
                "start": {"line": 3, "character": 4},
                "end": {"line": 3, "character": 15},
            },
        },
    }
    origin = {
        **candidate["item"],
        "detail": "orchestrator.dart",
        "uri": (root / source).as_uri(),
    }

    class FakeClient:
        def __init__(self, outgoing: object):
            self.outgoing = outgoing

        def request(self, method: str, params: object, timeout: float) -> object:
            del params, timeout
            if method == "textDocument/prepareCallHierarchy":
                return [origin]
            if isinstance(self.outgoing, Exception):
                raise self.outgoing
            return self.outgoing

    unsupported, unsupported_requests = provider._collect_call_hierarchy(
        FakeClient([]),
        root,
        inventory,
        [candidate],
        available=False,
        timeout=1,
    )
    assert unsupported[0]["status"] == "partial"
    assert unsupported[0]["prepare"]["status"] == "unsupported"
    assert unsupported[0]["outgoing_status"] == "not-run"
    assert unsupported[0]["outgoing_calls"] == []
    assert unsupported_requests[0]["method"] == "textDocument/prepareCallHierarchy"

    failed, unresolved = provider._collect_call_hierarchy(
        FakeClient(provider.DartFactError("outgoing request failed")),
        root,
        inventory,
        [candidate],
        available=True,
        timeout=1,
    )
    assert failed[0]["status"] == "partial"
    assert failed[0]["prepare"]["status"] == "resolved"
    assert failed[0]["outgoing_status"] == "unresolved"
    assert failed[0]["outgoing_calls"] == []
    assert failed[0]["uncertainties"] == [
        {"kind": "call-hierarchy-unresolved", "reason": "outgoing request failed"}
    ]
    assert unresolved[0]["method"] == "callHierarchy/outgoingCalls"

    malformed, _ = provider._collect_call_hierarchy(
        FakeClient([{"to": {"name": "missing-lineage"}, "fromRanges": []}]),
        root,
        inventory,
        [candidate],
        available=True,
        timeout=1,
    )
    assert malformed[0]["status"] == "partial"
    assert malformed[0]["outgoing_calls"] == []
    assert malformed[0]["uncertainties"][0]["kind"] == "call-hierarchy-malformed"


def test_copied_external_library_provider_closure(call_pack: tuple[Path, dict[str, object]], tmp_path: Path) -> None:
    host, _ = call_pack
    copied = tmp_path / "installed/.agents/skills/map-subsystem/scripts/dart_lsp_facts.py"
    copied.parent.mkdir(parents=True)
    shutil.copy2(PROVIDER, copied)
    output = host / "reports/dart-lsp-facts/copied-calls.json"
    _run(
        [
            sys.executable,
            "-I",
            "-S",
            str(copied),
            "--project-root",
            str(host),
            "--target",
            ".",
            *sum((["--query", name] for name in CALL_QUERIES), []),
            "--dart",
            str(DART),
            "--output",
            "reports/dart-lsp-facts/copied-calls.json",
        ],
        tmp_path,
    )
    payload = json.loads(output.read_text())
    assert payload["call_hierarchy_summary"]["resolved_edges"] == 11
    assert payload["status"] == "partial"


def test_native_analyze_format_test_smoke_and_failing_test_variant(tmp_path: Path) -> None:
    if not DART.is_file():
        pytest.skip("Dart 3.12 SDK is unavailable")
    host = _copy_host(tmp_path)
    before = _snapshot(host)
    _run([str(DART), "analyze", "--fatal-infos", "--fatal-warnings", "."], host)
    _run(
        [str(DART), "format", "--output=none", "--set-exit-if-changed", "lib", "bin", "test"],
        host,
    )
    _run([str(DART), "test/native_test.dart"], host)
    smoke = _run([str(DART), "bin/smoke.dart"], host)
    assert smoke.stdout == "36\n"
    assert _snapshot(host) == before

    failing = tmp_path / "failing"
    shutil.copytree(host, failing)
    shutil.copy2(FIXTURE / "variants/failing_native_test.dart", failing / "test/native_test.dart")
    failed = subprocess.run(
        [str(DART), "test/native_test.dart"],
        cwd=failing,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert failed.returncode != 0
    assert "deliberate native-test failure" in failed.stderr
