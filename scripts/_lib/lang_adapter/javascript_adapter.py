"""JavaScript / TypeScript symbol-extraction adapter — column-0 heuristic.

Reproduces the find-omnibus ``_javascript_symbols`` extraction behavior
verbatim: a column-0 declaration scan (``function name(``,
``const name = (…) =>``, ``class Name``, ``window.X =``) where each
symbol's LOC is the span to the next top-level declaration. Deliberately
coarse — IIFE-wrapped or deeply indented module bodies under-detect and
yield an empty list rather than a wrong count. Per ADR 0032 the heuristic
graduates to a real parser later (registered to override the mapping)
rather than growing regex epicycles. Never raises.
"""
from __future__ import annotations

import re

from .base import CAP_SYMBOLS, LanguageAdapter, Symbol

# Column-0 declaration matcher — identical to find-omnibus ``_JS_DECL``.
_JS_DECL = re.compile(
    r"^(?:"
    r"(?:async\s+)?function\s+(?P<fn>[A-Za-z_$][\w$]*)\s*\("
    r"|(?:const|let|var)\s+(?P<assigned>[A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s*)?(?:function\b|\([^)\n]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"
    r"|class\s+(?P<cls>[A-Za-z_$][\w$]*)"
    r"|window\.(?P<ns>[A-Za-z_$][\w$]*)\s*="
    r")",
    re.MULTILINE,
)


def _kind_for(group: str) -> str:
    """Map the matched declaration group to a :class:`Symbol` kind.

    ``class`` declarations are ``"class"``; everything else the heuristic
    recognizes (``function``, const-arrow, ``window.X =``) is a callable
    surface reported as ``"function"``. The heuristic cannot distinguish
    async reliably at this granularity, so no ``async_*`` kinds are
    emitted here.
    """
    return "class" if group == "cls" else "function"


class JavaScriptAdapter(LanguageAdapter):
    """Column-0 declaration heuristic for JavaScript / TypeScript sources."""

    name = "js-heuristic"
    language = "javascript"
    extensions = (".js", ".mjs", ".cjs", ".ts", ".tsx")
    capabilities = frozenset({CAP_SYMBOLS})

    def extract_symbols(
        self, source: str, *, path: str | None = None
    ) -> list[Symbol] | None:
        """Top-level declarations via the column-0 heuristic.

        Returns a (possibly empty) list; never ``None`` and never raises.
        Symbol LOC is the span to the next top-level declaration, matching
        find-omnibus ``_javascript_symbols``. ``parent`` is always
        ``None``, ``decorators`` always empty, ``is_dunder`` always
        ``False``.
        """
        lines = source.splitlines()
        # (line_index, name, kind_group) — line_index is 0-based.
        matches: list[tuple[int, str, str]] = []
        for m in _JS_DECL.finditer(source):
            group = next(
                (g for g in ("fn", "assigned", "cls", "ns") if m.group(g)),
                None,
            )
            if group is None:
                continue
            name = m.group(group)
            line_index = source.count("\n", 0, m.start())
            matches.append((line_index, name, group))

        symbols: list[Symbol] = []
        for i, (line_index, name, group) in enumerate(matches):
            end = matches[i + 1][0] if i + 1 < len(matches) else len(lines)
            loc = max(1, end - line_index)
            symbols.append(
                Symbol(
                    name=name,
                    cluster_name=name,
                    kind=_kind_for(group),
                    lineno=line_index + 1,
                    end_lineno=line_index + loc,
                    loc=loc,
                    parent=None,
                    is_dunder=False,
                    decorators=(),
                )
            )
        return symbols
