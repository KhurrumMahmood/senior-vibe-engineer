"""Versioned normalized facts and registry for portable language adapters.

This module defines the language-neutral seam described in ADRs 0032 and 0039:
immutable facts/results/failures, a compatibility ``Symbol`` record, a
``LanguageAdapter`` contract, canonical capability constants, and an
extension-keyed registry.

The extraction behavior reproduced by the concrete adapters is the
pattern originally embedded in
``.claude/skills/find-omnibus/scripts/detect.py``. The Python compatibility
surface preserves that behavior while normalized facts and real parsers give
new consumers an explicit, failure-visible contract.

Public surface::

    from _lib.lang_adapter import (
        Fact, AnalysisResult, AnalysisFailure, LanguageAdapter,
        CAP_SYMBOLS, CAP_IMPORTS, CAP_PYTHON_AST,
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
# reject requests an adapter cannot provide. ``CAP_SYMBOLS`` is the
# compatibility baseline for top-level symbol extraction.
# ``CAP_PYTHON_AST`` advertises raw ``ast.Module`` access for deep Python
# analysis — only the Python adapter has it.
# spec:portable-analysis-substrate::IM-1
ANALYSIS_INTERFACE_VERSION = 1
CAP_SYMBOLS: str = "analysis.symbols"
CAP_IMPORTS: str = "analysis.imports"
CAP_DEFINITIONS: str = "analysis.definitions"
CAP_REFERENCES: str = "analysis.references"
CAP_CALLS: str = "analysis.calls"
CAP_WRITES: str = "analysis.writes"
CAP_SYNTAX_TREE: str = "analysis.syntax-tree"
# Compatibility name for existing Python consumers. The value is the canonical
# registry capability; consumers may keep the old constant name while moving
# away from direct ``ast.Module`` access.
CAP_PYTHON_AST: str = CAP_SYNTAX_TREE
FACT_CAPABILITIES = frozenset(
    {CAP_SYMBOLS, CAP_IMPORTS, CAP_DEFINITIONS, CAP_REFERENCES, CAP_CALLS, CAP_WRITES}
)


# spec:portable-analysis-substrate::IM-7
class AnalysisFailure(RuntimeError):
    """Typed failure that can never be confused with a clean fact result."""

    def __init__(
        self,
        code: str,
        *,
        adapter: str,
        path: str,
        capability: str,
        detail: str,
    ) -> None:
        self.code = code
        self.adapter = adapter
        self.path = path
        self.capability = capability
        self.detail = detail
        super().__init__(
            f"{code}: adapter={adapter} path={path} capability={capability}: {detail}"
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "adapter": self.adapter,
            "path": self.path,
            "capability": self.capability,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Fact:
    """One deterministic normalized fact with a source location."""

    capability: str
    name: str
    path: str
    line: int
    column: int
    end_line: int
    end_column: int
    kind: str
    parent: str | None = None

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.path,
            self.line,
            self.column,
            self.end_line,
            self.end_column,
            self.capability,
            self.name,
            self.kind,
            self.parent or "",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "name": self.name,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "kind": self.kind,
            "parent": self.parent,
        }


# spec:portable-analysis-substrate::IM-8
@dataclass(frozen=True)
class AnalysisResult:
    """Successful result for an explicit set of requested capabilities."""

    interface_version: int
    adapter: str
    provider_version: str
    language: str
    path: str
    requested_capabilities: tuple[str, ...]
    facts: tuple[Fact, ...]

    def for_capability(self, capability: str) -> tuple[Fact, ...]:
        return tuple(fact for fact in self.facts if fact.capability == capability)

    def to_dict(self) -> dict[str, object]:
        return {
            "interface_version": self.interface_version,
            "adapter": self.adapter,
            "provider_version": self.provider_version,
            "language": self.language,
            "path": self.path,
            "requested_capabilities": list(self.requested_capabilities),
            "facts": [fact.to_dict() for fact in self.facts],
        }


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
    * ``lineno`` / ``end_lineno`` — 1-based source span.
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
    """Contract for a versioned per-language fact provider.

    Subclasses declare the language they cover, the file extensions they
    claim, their provider version, and the capabilities they offer. The
    normalized ``analyze`` method is authoritative; ``extract_symbols`` remains
    for legacy consumers.
    """

    #: Stable adapter identifier (e.g. ``"python-ast"``, ``"typescript-syntax"``).
    name: str
    #: Language label (e.g. ``"python"``, ``"javascript"``).
    language: str
    #: File extensions claimed, lowercase, dot-prefixed (e.g. ``(".py",)``).
    extensions: tuple[str, ...]
    #: Capabilities offered (subset of the ``CAP_*`` constants).
    capabilities: frozenset[str]
    interface_version = ANALYSIS_INTERFACE_VERSION
    provider_version: str

    def require_capabilities(
        self,
        capabilities: set[str] | frozenset[str],
        *,
        path: str,
    ) -> tuple[str, ...]:
        requested = tuple(sorted(set(capabilities)))
        missing = sorted(set(requested) - set(self.capabilities))
        if missing:
            raise AnalysisFailure(
                "unsupported_capability",
                adapter=self.name,
                path=path,
                capability=missing[0],
                detail=f"supported capabilities: {', '.join(sorted(self.capabilities))}",
            )
        return requested

    @abstractmethod
    def analyze(
        self,
        source: str,
        *,
        path: str,
        capabilities: set[str] | frozenset[str],
    ) -> AnalysisResult:
        """Return requested normalized facts or raise :class:`AnalysisFailure`."""
        raise NotImplementedError

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
# version-specific provider can replace a mapping without changing callers.
_REGISTRY: dict[str, LanguageAdapter] = {}


def register(adapter: LanguageAdapter) -> LanguageAdapter:
    """Register ``adapter`` for each of its extensions (case-insensitive).

    Later registrations override earlier ones for a shared extension. Returns
    the adapter for convenient inline use.
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


def get_adapter(
    path: str | Path,
    *,
    capability: str = CAP_SYMBOLS,
) -> LanguageAdapter:
    """Return the adapter for ``path`` or raise a contextual typed failure.

    ``adapter_for_suffix`` remains the explicit optional registry probe. This
    higher-level selection boundary is strict so an analysis request cannot
    silently turn an unsupported file type into a clean zero-result.
    """
    rendered = str(path)
    suffix = Path(path).suffix
    adapter = adapter_for_suffix(suffix)
    if adapter is None:
        raise AnalysisFailure(
            "unsupported_language",
            adapter="registry",
            path=rendered,
            capability=capability,
            detail=f"no adapter registered for suffix {suffix or '<none>'}",
        )
    return adapter


def supported_extensions() -> frozenset[str]:
    """Return every registered file extension (lowercase, dot-prefixed)."""
    return frozenset(_REGISTRY)


def iter_adapters() -> list[LanguageAdapter]:
    """Return the distinct registered adapters (deduplicated, stable order)."""
    seen: dict[int, LanguageAdapter] = {}
    for adapter in _REGISTRY.values():
        seen.setdefault(id(adapter), adapter)
    return list(seen.values())
