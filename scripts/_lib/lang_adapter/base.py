"""Core types and registry for per-language symbol-extraction adapters.

This module defines the language-neutral seam described in ADR 0032:
a small ``Symbol`` record, a ``LanguageAdapter`` contract, capability
constants, and an extension-keyed registry. Concrete adapters live in
sibling modules (``python_adapter``, ``javascript_adapter``) and register
themselves at import time via ``register``.

The extraction behavior reproduced by the concrete adapters is the
pattern originally embedded in
``.claude/skills/find-omnibus/scripts/detect.py`` (the ``_python_symbols``
/ ``_javascript_symbols`` extractors and the ``_ANALYZERS`` table). This
package generalizes that single in-script seam into a shared, importable
foundation many consumers can target — without migrating any consumer.

Public surface::

    from _lib.lang_adapter import (
        Symbol, LanguageAdapter, CAP_SYMBOLS, CAP_PYTHON_AST,
        register, get_adapter, adapter_for_suffix,
        supported_extensions, iter_adapters,
    )
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

# --- Capability constants -------------------------------------------------
#
# Capabilities let a consumer declare what it needs from an adapter and
# gracefully skip files whose adapter cannot provide it. ``CAP_SYMBOLS`` is
# the baseline both adapters offer (top-level symbol extraction).
# ``CAP_PYTHON_AST`` advertises raw ``ast.Module`` access for deep Python
# analysis — only the Python adapter has it.
CAP_SYMBOLS: str = "symbols"
CAP_PYTHON_AST: str = "python_ast"


@dataclass(frozen=True)
class Symbol:
    """One top-level (or expanded god-class method) symbol in a source file.

    Fields mirror the triples produced by the original find-omnibus
    extractors, enriched with structural metadata for downstream
    consumers:

    * ``name`` — fully-qualified symbol name. For an expanded god-class
      method this is ``ClassName.method``; otherwise the bare symbol name.
    * ``cluster_name`` — the name fed to head-noun / cluster extraction.
      For expanded god-class methods this is the *method* name (so
      ``Service.parse_html`` clusters as ``html``, not ``Service``);
      otherwise it equals ``name``.
    * ``kind`` — one of ``"function"``, ``"async_function"``,
      ``"method"``, ``"async_method"``, ``"class"``.
    * ``lineno`` / ``end_lineno`` — 1-based source span. For the JS
      heuristic ``end_lineno`` is the line before the next top-level
      declaration (or end of file).
    * ``loc`` — line count of the symbol's span (``>= 1``).
    * ``parent`` — owning class name for expanded methods, else ``None``.
    * ``is_dunder`` — whether the bare symbol name is a ``__dunder__``.
      Always ``False`` for JavaScript symbols.
    * ``decorators`` — decorator names (Python only); empty tuple for JS.
    """

    name: str
    cluster_name: str
    kind: str
    lineno: int
    end_lineno: int
    loc: int
    parent: str | None = None
    is_dunder: bool = False
    decorators: tuple[str, ...] = field(default_factory=tuple)


class LanguageAdapter(ABC):
    """Contract for a per-language symbol-extraction adapter.

    Subclasses declare the language they cover, the file extensions they
    claim, and the capabilities they offer, then implement
    ``extract_symbols``. Adapters are pluggable: a future real-parser
    adapter can ``register`` itself and override the ``.ts`` / ``.js``
    mapping without touching this module.
    """

    #: Stable adapter identifier (e.g. ``"python-ast"``, ``"js-heuristic"``).
    name: str
    #: Language label (e.g. ``"python"``, ``"javascript"``).
    language: str
    #: File extensions claimed, lowercase, dot-prefixed (e.g. ``(".py",)``).
    extensions: tuple[str, ...]
    #: Capabilities offered (subset of the ``CAP_*`` constants).
    capabilities: frozenset[str]

    @abstractmethod
    def extract_symbols(
        self, source: str, *, path: str | None = None
    ) -> list[Symbol] | None:
        """Extract top-level symbols from ``source``.

        Returns a list of :class:`Symbol` (possibly empty), or ``None``
        when the source is unparseable for this adapter (e.g. a Python
        ``SyntaxError``). ``path`` is advisory context only.
        """
        raise NotImplementedError


# --- Registry -------------------------------------------------------------
#
# Extension -> adapter. The mapping is the only per-language seam; the
# clustering / scoring / reporting that consumes Symbols stays
# language-neutral. ``register`` is last-writer-wins per extension so a
# future real-parser adapter can override the heuristic mapping.
_REGISTRY: dict[str, LanguageAdapter] = {}


def register(adapter: LanguageAdapter) -> LanguageAdapter:
    """Register ``adapter`` for each of its extensions (case-insensitive).

    Later registrations override earlier ones for a shared extension —
    this is how a real-parser adapter graduates over the heuristic
    (ADR 0032). Returns the adapter for convenient inline use.
    """
    for ext in adapter.extensions:
        _REGISTRY[ext.lower()] = adapter
    return adapter


def adapter_for_suffix(suffix: str) -> LanguageAdapter | None:
    """Return the adapter claiming ``suffix`` (e.g. ``".py"``), or ``None``.

    Matching is case-insensitive. ``suffix`` should include the leading
    dot, as produced by ``pathlib.Path.suffix``.
    """
    return _REGISTRY.get(suffix.lower())


def get_adapter(path: str | Path) -> LanguageAdapter | None:
    """Return the adapter for ``path`` by its file suffix, or ``None``."""
    return adapter_for_suffix(Path(path).suffix)


def supported_extensions() -> frozenset[str]:
    """Return every registered file extension (lowercase, dot-prefixed)."""
    return frozenset(_REGISTRY)


def iter_adapters() -> list[LanguageAdapter]:
    """Return the distinct registered adapters (deduplicated, stable order)."""
    seen: dict[int, LanguageAdapter] = {}
    for adapter in _REGISTRY.values():
        seen.setdefault(id(adapter), adapter)
    return list(seen.values())
