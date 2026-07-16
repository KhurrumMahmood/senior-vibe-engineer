"""Versioned portable analysis facts and language providers (ADRs 0032/0039).

Generalizes the single ``_ANALYZERS`` seam embedded in
``.claude/skills/find-omnibus/scripts/detect.py`` into a shared,
importable foundation. The clustering / scoring / reporting that consumes
:class:`Symbol` records remains compatible, while new consumers request named
normalized facts and receive typed failures.

Five subject providers ship and self-register at import time:

* :class:`PythonAdapter` (``python-ast``) — exact ``ast`` walk with
  god-class method expansion; also exposes the raw ``ast.Module`` tree
  for deep consumers (capability :data:`CAP_PYTHON_AST`).
* Tree-sitter-backed JavaScript, TypeScript/TSX, Rust, and Go providers expose
  deterministic syntax facts through pinned grammars.

Usage::

    from _lib.lang_adapter import get_adapter, Symbol, CAP_SYMBOLS

    adapter = get_adapter("core/views.py")
    if adapter and CAP_SYMBOLS in adapter.capabilities:
        symbols = adapter.extract_symbols(source)
"""
from __future__ import annotations

from .base import (
    ANALYSIS_INTERFACE_VERSION,
    CAP_CALLS,
    CAP_DEFINITIONS,
    CAP_IMPORTS,
    CAP_PYTHON_AST,
    CAP_REFERENCES,
    CAP_SYMBOLS,
    CAP_SYNTAX_TREE,
    CAP_WRITES,
    FACT_CAPABILITIES,
    AnalysisFailure,
    AnalysisResult,
    Fact,
    LanguageAdapter,
    Symbol,
    adapter_for_suffix,
    get_adapter,
    iter_adapters,
    register,
    supported_extensions,
)
from .javascript_adapter import JavaScriptAdapter, TypeScriptAdapter
from .python_adapter import PythonAdapter
from .systems_adapter import GoAdapter, RustAdapter

# Pre-register the shipped adapters at import time. A future real-parser
# adapter can ``register`` itself afterwards to override the .ts/.js
# mapping (last-writer-wins per extension).
register(PythonAdapter())
register(JavaScriptAdapter())
register(TypeScriptAdapter())
register(RustAdapter())
register(GoAdapter())

__all__ = [
    "Symbol",
    "Fact",
    "AnalysisResult",
    "AnalysisFailure",
    "LanguageAdapter",
    "PythonAdapter",
    "JavaScriptAdapter",
    "TypeScriptAdapter",
    "RustAdapter",
    "GoAdapter",
    "ANALYSIS_INTERFACE_VERSION",
    "CAP_SYMBOLS",
    "CAP_IMPORTS",
    "CAP_DEFINITIONS",
    "CAP_REFERENCES",
    "CAP_CALLS",
    "CAP_WRITES",
    "CAP_SYNTAX_TREE",
    "CAP_PYTHON_AST",
    "FACT_CAPABILITIES",
    "register",
    "get_adapter",
    "adapter_for_suffix",
    "supported_extensions",
    "iter_adapters",
]
