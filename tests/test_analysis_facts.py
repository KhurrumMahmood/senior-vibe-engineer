"""Contract tests for the versioned portable analysis fact interface."""
from __future__ import annotations

import json
import hashlib
import threading
from pathlib import Path

import pytest

import analysis_fact_benchmark as benchmark
from analysis_fact_benchmark import build_report

from _lib.lang_adapter import (
    ANALYSIS_INTERFACE_VERSION,
    CAP_CALLS,
    CAP_DEFINITIONS,
    CAP_IMPORTS,
    CAP_REFERENCES,
    CAP_SYMBOLS,
    CAP_WRITES,
    AnalysisFailure,
    GoAdapter,
    PythonAdapter,
    RustAdapter,
    TypeScriptAdapter,
    get_adapter,
)


FIXTURES = Path(__file__).parent / "fixtures" / "analysis_facts"
FACT_CAPABILITIES = frozenset(
    {CAP_SYMBOLS, CAP_IMPORTS, CAP_DEFINITIONS, CAP_REFERENCES, CAP_CALLS, CAP_WRITES}
)


def _names(result, capability: str) -> list[str]:
    return [fact.name for fact in result.for_capability(capability)]


def test_interface_uses_canonical_versioned_capabilities():
    assert ANALYSIS_INTERFACE_VERSION == 1
    assert FACT_CAPABILITIES == {
        "analysis.symbols",
        "analysis.imports",
        "analysis.definitions",
        "analysis.references",
        "analysis.calls",
        "analysis.writes",
    }
    for adapter in (PythonAdapter(), TypeScriptAdapter(), RustAdapter(), GoAdapter()):
        assert adapter.interface_version == ANALYSIS_INTERFACE_VERSION
        assert adapter.provider_version
        assert FACT_CAPABILITIES <= adapter.capabilities


def test_typescript_real_parser_handles_required_declarations_and_locations():
    source = (FIXTURES / "typescript-small.tsx").read_text(encoding="utf-8")
    adapter = TypeScriptAdapter()
    result = adapter.analyze(source, path="src/typescript-small.tsx", capabilities=FACT_CAPABILITIES)

    definitions = set(_names(result, CAP_DEFINITIONS))
    assert {"exported", "load", "Widget", "nested", "local", "render"} <= definitions
    assert set(_names(result, CAP_IMPORTS)) == {"./dep"}
    assert {"fetchValue", "local"} <= set(_names(result, CAP_CALLS))
    assert "state.value" in _names(result, CAP_WRITES)
    assert {"input", "state", "value"} <= set(_names(result, CAP_REFERENCES))

    symbols = result.for_capability(CAP_SYMBOLS)
    assert {fact.name for fact in symbols} >= {"exported", "load", "Widget", "nested", "local"}
    assert all(fact.path == "src/typescript-small.tsx" for fact in result.facts)
    assert all(fact.line >= 1 and fact.column >= 1 for fact in result.facts)
    assert tuple(result.facts) == tuple(sorted(result.facts, key=lambda fact: fact.sort_key()))


@pytest.mark.parametrize("suffix", [".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts"])
def test_javascript_typescript_extensions_use_real_parser(suffix: str):
    adapter = get_adapter(f"src/module{suffix}")
    source = "export const visible = () => {\n  function nested() { return 1; }\n  return nested();\n};\n"
    result = adapter.analyze(source, path=f"src/module{suffix}", capabilities={CAP_SYMBOLS})
    assert {fact.name for fact in result.facts} >= {"visible", "nested"}
    assert "heuristic" not in adapter.name


def test_tsx_jsx_syntax_is_parsed():
    source = "export const Widget = () => <section>ready</section>;\n"
    result = TypeScriptAdapter().analyze(
        source,
        path="src/widget.tsx",
        capabilities={CAP_SYMBOLS},
    )
    assert {fact.name for fact in result.facts} == {"Widget"}


def test_python_facts_preserve_legacy_symbols_and_add_named_fact_families():
    source = (FIXTURES / "python-small.py").read_text(encoding="utf-8")
    adapter = PythonAdapter()
    legacy = adapter.extract_symbols(source, path="src/python-small.py")
    result = adapter.analyze(source, path="src/python-small.py", capabilities=FACT_CAPABILITIES)

    assert {fact.name for fact in result.for_capability(CAP_SYMBOLS)} == {
        symbol.name for symbol in legacy
    }
    assert set(_names(result, CAP_IMPORTS)) == {"pathlib"}
    assert {"convert", "Runner", "value"} <= set(_names(result, CAP_DEFINITIONS))
    assert "helper" in _names(result, CAP_CALLS)
    assert "value" in _names(result, CAP_WRITES)


@pytest.mark.parametrize(
    ("adapter", "fixture", "expected"),
    [
        (RustAdapter(), "rust-small.rs", {"convert", "Runner"}),
        (GoAdapter(), "go-small.go", {"convert", "Runner"}),
    ],
)
def test_rust_and_go_publish_the_accepted_fact_subset(adapter, fixture: str, expected: set[str]):
    source = (FIXTURES / fixture).read_text(encoding="utf-8")
    result = adapter.analyze(source, path=f"src/{fixture}", capabilities=FACT_CAPABILITIES)
    assert expected <= set(_names(result, CAP_DEFINITIONS))
    assert result.for_capability(CAP_IMPORTS)
    assert result.for_capability(CAP_CALLS)


def test_unsupported_capability_is_typed_and_contextual():
    with pytest.raises(AnalysisFailure) as raised:
        PythonAdapter().analyze(
            "x = 1\n",
            path="src/broken.py",
            capabilities={"analysis.type-facts"},
        )
    failure = raised.value
    assert failure.code == "unsupported_capability"
    assert failure.adapter == "python-ast"
    assert failure.path == "src/broken.py"
    assert failure.capability == "analysis.type-facts"


def test_malformed_input_is_not_a_clean_zero_result():
    with pytest.raises(AnalysisFailure) as raised:
        TypeScriptAdapter().analyze(
            "export function broken( {\n",
            path="src/broken.ts",
            capabilities={CAP_SYMBOLS},
        )
    assert raised.value.code == "parse_error"
    assert raised.value.path == "src/broken.ts"
    assert raised.value.capability == CAP_SYMBOLS


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("missing", "missing_tool"),
        ("broken", "tool_failure"),
        ("timeout", "tool_timeout"),
        ("corrupt", "corrupt_output"),
    ],
)
def test_parser_faults_are_typed_and_never_clean(monkeypatch, mode: str, code: str):
    adapter = TypeScriptAdapter()

    if mode == "missing":
        monkeypatch.setattr(adapter, "_load_parser", lambda: (_ for _ in ()).throw(ImportError("gone")))
    elif mode == "broken":
        class BrokenParser:
            def parse(self, source):
                raise RuntimeError("boom")

        monkeypatch.setattr(adapter, "_load_parser", lambda: BrokenParser())
    elif mode == "timeout":
        class TimedOutParser:
            def parse(self, source):
                raise TimeoutError("deadline exceeded")

        monkeypatch.setattr(adapter, "_load_parser", lambda: TimedOutParser())
    else:
        class CorruptParser:
            def parse(self, source):
                return object()

        monkeypatch.setattr(adapter, "_load_parser", lambda: CorruptParser())

    with pytest.raises(AnalysisFailure) as raised:
        adapter.analyze("const ok = 1;\n", path="src/fault.ts", capabilities={CAP_SYMBOLS})
    assert raised.value.code == code
    assert raised.value.adapter == "typescript-syntax"
    assert raised.value.path == "src/fault.ts"
    assert raised.value.capability == CAP_SYMBOLS


@pytest.mark.parametrize("mode", ["missing_named_children", "raising_children"])
def test_malformed_root_variants_are_typed(monkeypatch, mode: str):
    adapter = TypeScriptAdapter()

    if mode == "missing_named_children":
        class Root:
            children = ()
            has_error = False

    else:
        class Root:
            has_error = False

            @property
            def children(self):
                raise RuntimeError("corrupt children")

    class Tree:
        root_node = Root()

    class Parser:
        def parse(self, source):
            return Tree()

    monkeypatch.setattr(adapter, "_load_parser", lambda: Parser())
    with pytest.raises(AnalysisFailure) as raised:
        adapter.analyze("const ok = 1;\n", path="src/corrupt.ts", capabilities={CAP_SYMBOLS})
    assert raised.value.code == "corrupt_output"
    assert raised.value.path == "src/corrupt.ts"
    assert raised.value.capability == CAP_SYMBOLS


def test_blocking_parser_has_substrate_enforced_deadline(monkeypatch):
    adapter = TypeScriptAdapter()
    adapter.parse_timeout_seconds = 0.02
    release = threading.Event()

    class BlockingParser:
        def parse(self, source):
            release.wait(5)

    monkeypatch.setattr(adapter, "_load_parser", lambda: BlockingParser())
    try:
        with pytest.raises(AnalysisFailure) as raised:
            adapter.analyze("const ok = 1;\n", path="src/blocked.ts", capabilities={CAP_SYMBOLS})
        assert raised.value.code == "tool_timeout"
        assert raised.value.path == "src/blocked.ts"
        assert raised.value.capability == CAP_SYMBOLS
    finally:
        release.set()


def test_golden_fact_files_match_deterministic_adapter_output():
    cases = {
        "typescript": (TypeScriptAdapter(), FIXTURES / "typescript-small.tsx"),
        "python": (PythonAdapter(), FIXTURES / "python-small.py"),
        "rust": (RustAdapter(), FIXTURES / "rust-small.rs"),
        "go": (GoAdapter(), FIXTURES / "go-small.go"),
    }
    for name, (adapter, fixture) in cases.items():
        result = adapter.analyze(
            fixture.read_text(encoding="utf-8"),
            path=fixture.name,
            capabilities=FACT_CAPABILITIES,
        )
        facts = [fact.to_dict() for fact in result.facts]
        encoded = json.dumps(
            facts,
            separators=(",", ":"),
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
        actual = {
            "schema_version": 1,
            "interface_version": result.interface_version,
            "adapter": result.adapter,
            "fact_count": len(facts),
            "fact_shape": "full-location-v1",
            "facts_sha256": hashlib.sha256(encoded).hexdigest(),
        }
        expected = json.loads((FIXTURES / "golden" / f"{name}.json").read_text(encoding="utf-8"))
        assert actual == expected


def test_productized_provider_meets_pinned_d3_and_small_large_budgets():
    report = build_report()
    assert report["corpus_sha256"] == "da03a77d5818deb2c2acd531e3875ad4053ff278d8cc11f17784d57f38d2cf4f"
    assert report["passed"], report["violations"]
    assert not report["violations"]
    assert all(
        score["precision"] == score["recall"] == 1.0
        for score in report["metrics"].values()
    )
    assert report["variance_method"].startswith("fresh subprocess cold")


def test_benchmark_platform_record_is_execution_derived(monkeypatch):
    monkeypatch.setattr(benchmark.platform, "system", lambda: "Linux")
    monkeypatch.setattr(benchmark.platform, "machine", lambda: "x86_64")

    execution = benchmark._platform_execution()

    assert execution["platform_key"] == "Linux-x86_64"
    assert execution["system"] == "Linux"
    assert execution["machine"] == "x86_64"
    assert "Darwin" not in json.dumps(execution)


def test_external_large_fixture_has_pinned_provenance_and_real_shape():
    provenance = benchmark._load_external_corpus()
    fixture = benchmark.FACT_FIXTURES / provenance["local_path"]

    assert provenance["upstream_revision"] == "c63de15a992d37f0d6cec03ac7631872838602cb"
    assert provenance["upstream_path"] == "src/compiler/symbolWalker.ts"
    assert provenance["local_path"] == "external/typescript-symbol-walker-v5.9.3.ts"
    assert provenance["license"] == "Apache-2.0"
    assert provenance["source_sha256"] == hashlib.sha256(fixture.read_bytes()).hexdigest()
    assert provenance["input_bytes"] == fixture.stat().st_size >= 7_000
    assert provenance["input_lines"] == len(fixture.read_text(encoding="utf-8").splitlines()) >= 180
    assert provenance["selection_rationale"]


def test_platform_comparison_requires_all_contract_platforms_and_stable_results():
    base = build_report(source_revision="a" * 40)
    base["platform_execution"] = {
        "platform_key": "Darwin-arm64",
        "system": "Darwin",
        "machine": "arm64",
        "python": "3.11.10",
        "python_series": "3.11",
        "tree_sitter": "0.26.0",
        "tree_sitter_language_pack": "1.12.5",
    }
    linux = json.loads(json.dumps(base))
    linux["platform_execution"] = {
        "platform_key": "Linux-x86_64",
        "system": "Linux",
        "machine": "x86_64",
        "python": "3.11.10",
        "python_series": "3.11",
        "tree_sitter": "0.26.0",
        "tree_sitter_language_pack": "1.12.5",
    }

    with pytest.raises(ValueError, match="missing required platform"):
        benchmark.compare_platform_reports([base])

    matrix = benchmark.compare_platform_reports([base, linux])
    assert matrix["passed"] is True
    assert matrix["cross_platform_deterministic"] is True
    assert sorted(matrix["executions"]) == ["Darwin-arm64", "Linux-x86_64"]

    linux["stable_result_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="stable result"):
        benchmark.compare_platform_reports([base, linux])


def test_python_symbol_facts_publish_precise_full_spans():
    source = (FIXTURES / "python-small.py").read_text(encoding="utf-8")
    result = PythonAdapter().analyze(
        source,
        path="src/python-small.py",
        capabilities={CAP_SYMBOLS},
    )
    by_name = {fact.name: fact for fact in result.facts}

    convert = by_name["convert"]
    assert (convert.line, convert.column, convert.end_line, convert.end_column) == (8, 1, 10, 17)
    runner = by_name["Runner"]
    assert (runner.line, runner.column, runner.end_line, runner.end_column) == (13, 1, 15, 29)
