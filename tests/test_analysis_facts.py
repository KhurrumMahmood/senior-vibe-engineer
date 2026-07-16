"""Contract tests for the versioned portable analysis fact interface."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("suffix", [".js", ".mjs", ".cjs", ".ts", ".tsx"])
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
        facts = [
            [fact.capability, fact.name, fact.line, fact.column, fact.kind]
            for fact in result.facts
        ]
        encoded = json.dumps(facts, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        actual = {
            "schema_version": 1,
            "interface_version": result.interface_version,
            "adapter": result.adapter,
            "fact_count": len(facts),
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
