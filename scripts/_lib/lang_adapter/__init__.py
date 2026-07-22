"""Shared per-language symbol-extraction adapters (ADR 0032).

Generalizes the single ``_ANALYZERS`` seam embedded in
``.claude/skills/find-omnibus/scripts/detect.py`` into a shared,
importable foundation. The clustering / scoring / reporting that consumes
:class:`Symbol` records stays language-neutral; adapters keyed by file
extension are the only per-language seam.

Two adapters ship and self-register at import time:

* :class:`PythonAdapter` (``python-ast``) — exact ``ast`` walk with
  god-class method expansion; also exposes the raw ``ast.Module`` tree
  for deep consumers (capability :data:`CAP_PYTHON_AST`).
* :class:`JavaScriptAdapter` (``js-heuristic``) — column-0 declaration
  heuristic for ``.js/.mjs/.cjs/.ts/.tsx`` (no external parser).

Usage::

    from _lib.lang_adapter import get_adapter, Symbol, CAP_SYMBOLS

    adapter = get_adapter("core/views.py")
    if adapter and CAP_SYMBOLS in adapter.capabilities:
        symbols = adapter.extract_symbols(source)
"""
from __future__ import annotations

from .base import (
    CAP_PYTHON_AST,
    CAP_SYMBOLS,
    LanguageAdapter,
    Symbol,
    adapter_for_suffix,
    get_adapter,
    iter_adapters,
    register,
    supported_extensions,
)
from .javascript_adapter import JavaScriptAdapter
from .python_adapter import PythonAdapter

# Pre-register the shipped adapters at import time. A future real-parser
# adapter can ``register`` itself afterwards to override the .ts/.js
# mapping (last-writer-wins per extension).
register(PythonAdapter())
register(JavaScriptAdapter())

__all__ = [
    "Symbol",
    "LanguageAdapter",
    "PythonAdapter",
    "JavaScriptAdapter",
    "CAP_SYMBOLS",
    "CAP_PYTHON_AST",
    "register",
    "get_adapter",
    "adapter_for_suffix",
    "supported_extensions",
    "iter_adapters",
]
