"""Tests for the shared per-language symbol-extraction adapters (ADR 0032).

Pins the extraction behavior generalized out of
``.claude/skills/find-omnibus/scripts/detect.py`` so downstream consumers
can target ``scripts/_lib/lang_adapter`` with a trusted contract.

Plain ``unittest`` so the same file runs under both pytest
(engineering-skills) and a host Django test runner unchanged. ``scripts/``
is placed on ``sys.path`` (matching conftest) so ``_lib.lang_adapter``
imports the same way the runtime does.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _lib.lang_adapter import (  # noqa: E402
    CAP_PYTHON_AST,
    CAP_SYMBOLS,
    JavaScriptAdapter,
    TypeScriptAdapter,
    PythonAdapter,
    Symbol,
    adapter_for_suffix,
    get_adapter,
    iter_adapters,
    supported_extensions,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "lang_adapter"


def _by_name(symbols: list[Symbol]) -> dict[str, Symbol]:
    return {s.name: s for s in symbols}


class PythonExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = (_FIXTURES / "sample.py").read_text(encoding="utf-8")
        self.symbols = PythonAdapter().extract_symbols(self.source)

    def test_expected_symbol_set(self) -> None:
        names = {s.name for s in self.symbols}
        self.assertEqual(
            names,
            {
                "load_invoice",
                "fetch_shipment",
                "SmallThing",
                "BigService.get_samples",
                "BigService.save_samples",
                "BigService.parse_html",
            },
        )

    def test_dunders_skipped(self) -> None:
        # top-level __ignored_dunder__ and BigService.__init__ never appear
        names = {s.name for s in self.symbols}
        self.assertNotIn("__ignored_dunder__", names)
        self.assertNotIn("BigService.__init__", names)
        self.assertFalse(any(s.is_dunder for s in self.symbols))

    def test_kinds(self) -> None:
        by = _by_name(self.symbols)
        self.assertEqual(by["load_invoice"].kind, "function")
        self.assertEqual(by["fetch_shipment"].kind, "async_function")
        self.assertEqual(by["SmallThing"].kind, "class")
        self.assertEqual(by["BigService.get_samples"].kind, "method")
        self.assertEqual(by["BigService.parse_html"].kind, "async_method")

    def test_god_class_expansion(self) -> None:
        # BigService has 3 non-dunder methods -> expanded per method.
        expanded = [s for s in self.symbols if s.parent == "BigService"]
        self.assertEqual(len(expanded), 3)
        for s in expanded:
            self.assertEqual(s.parent, "BigService")
            # cluster_name is the *method* name, not the class.
            self.assertEqual(s.name, f"BigService.{s.cluster_name}")
        # SmallThing stays a single class symbol (under threshold).
        by = _by_name(self.symbols)
        self.assertIsNone(by["SmallThing"].parent)

    def test_cluster_name_for_top_level(self) -> None:
        by = _by_name(self.symbols)
        self.assertEqual(by["load_invoice"].cluster_name, "load_invoice")
        self.assertEqual(by["SmallThing"].cluster_name, "SmallThing")

    def test_loc_positive(self) -> None:
        self.assertTrue(all(s.loc >= 1 for s in self.symbols))

    def test_decorators_default_empty(self) -> None:
        self.assertTrue(all(s.decorators == () for s in self.symbols))


class PythonParseTests(unittest.TestCase):
    def test_parse_returns_module(self) -> None:
        tree = PythonAdapter().parse("x = 1\n")
        self.assertIsInstance(tree, ast.Module)

    def test_parse_returns_none_on_syntax_error(self) -> None:
        self.assertIsNone(PythonAdapter().parse("def f(:\n"))

    def test_extract_returns_none_on_invalid_python(self) -> None:
        self.assertIsNone(PythonAdapter().extract_symbols("def f(:\n"))


class JavaScriptExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = (_FIXTURES / "sample.ts").read_text(encoding="utf-8")
        self.symbols = JavaScriptAdapter().extract_symbols(self.source)

    def test_expected_symbol_set(self) -> None:
        names = {s.name for s in self.symbols}
        self.assertEqual(
            names,
            {"loadInvoice", "fetchShipment", "CustomerWidget", "render", "bootInventory"},
        )

    def test_kinds(self) -> None:
        by = _by_name(self.symbols)
        self.assertEqual(by["loadInvoice"].kind, "function")  # function decl
        self.assertEqual(by["fetchShipment"].kind, "function")  # const-arrow
        self.assertEqual(by["CustomerWidget"].kind, "class")  # class decl
        self.assertEqual(by["render"].kind, "method")  # parsed class method
        self.assertEqual(by["bootInventory"].kind, "function")  # window.X =

    def test_js_symbol_shape(self) -> None:
        for s in self.symbols:
            self.assertEqual(s.decorators, ())
            self.assertFalse(s.is_dunder)
            self.assertEqual(s.cluster_name, s.name)
            self.assertGreaterEqual(s.loc, 1)

    def test_never_returns_none(self) -> None:
        # The real parser accepts empty input and nested declarations.
        self.assertEqual(JavaScriptAdapter().extract_symbols(""), [])
        indented = "(function () {\n  function hidden() {}\n})();\n"
        self.assertEqual(
            {symbol.name for symbol in JavaScriptAdapter().extract_symbols(indented)},
            {"hidden"},
        )
        self.assertIsNone(JavaScriptAdapter().extract_symbols("function broken( {\n"))


class RegistryTests(unittest.TestCase):
    def test_py_routes_to_python_adapter(self) -> None:
        self.assertIsInstance(get_adapter("a/b/c.py"), PythonAdapter)
        self.assertIsInstance(adapter_for_suffix(".py"), PythonAdapter)

    def test_js_family_routes_to_javascript_adapter(self) -> None:
        for path in ("x.js", "x.mjs", "x.cjs"):
            self.assertIsInstance(get_adapter(path), JavaScriptAdapter, path)
        for path in ("x.ts", "x.tsx"):
            self.assertIsInstance(get_adapter(path), TypeScriptAdapter, path)

    def test_case_insensitive_suffix(self) -> None:
        self.assertIsInstance(get_adapter("X.PY"), PythonAdapter)
        self.assertIsInstance(get_adapter("X.TSX"), TypeScriptAdapter)

    def test_unknown_suffix_returns_none(self) -> None:
        self.assertIsNone(get_adapter("README.md"))
        self.assertIsNone(get_adapter("noext"))
        self.assertIsNotNone(adapter_for_suffix(".rs"))

    def test_supported_extensions(self) -> None:
        exts = supported_extensions()
        self.assertIn(".py", exts)
        for ext in (".js", ".mjs", ".cjs", ".ts", ".tsx"):
            self.assertIn(ext, exts)

    def test_iter_adapters_deduplicated(self) -> None:
        adapters = iter_adapters()
        # JS adapter claims 5 extensions but appears once.
        self.assertEqual(len(adapters), len({id(a) for a in adapters}))
        languages = {a.language for a in adapters}
        self.assertEqual(languages, {"python", "javascript", "typescript", "rust", "go"})


class CapabilityTests(unittest.TestCase):
    def test_python_capabilities(self) -> None:
        caps = PythonAdapter().capabilities
        self.assertIn(CAP_SYMBOLS, caps)
        self.assertIn(CAP_PYTHON_AST, caps)

    def test_javascript_capabilities(self) -> None:
        caps = JavaScriptAdapter().capabilities
        self.assertIn(CAP_SYMBOLS, caps)
        self.assertNotIn(CAP_PYTHON_AST, caps)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
