"""Python symbol-extraction adapter — exact ``ast`` walk.

Reproduces the find-omnibus ``_python_symbols`` extraction behavior
verbatim (dunder skip at top level, god-class method expansion at the
``>= 3`` non-dunder-method threshold) and additionally exposes the raw
``ast.Module`` tree for deep consumers via :meth:`PythonAdapter.parse`
(capability :data:`CAP_PYTHON_AST`).
"""
from __future__ import annotations

import ast

from .base import (
    ANALYSIS_INTERFACE_VERSION,
    CAP_CALLS,
    CAP_DEFINITIONS,
    CAP_IMPORTS,
    CAP_PYTHON_AST,
    CAP_REFERENCES,
    CAP_SYMBOLS,
    CAP_WRITES,
    FACT_CAPABILITIES,
    AnalysisFailure,
    AnalysisResult,
    Fact,
    LanguageAdapter,
    Symbol,
)

# Threshold at which a class's methods drive the SRP signal individually
# rather than the class counting as a single symbol. Mirrors find-omnibus.
_GOD_CLASS_METHOD_THRESHOLD = 3


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _node_loc(node: ast.AST) -> int:
    """Line count of ``node``'s span (``>= 1``); 0 when positions absent."""
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None) or start
    if start is None or end is None:
        return 0
    return max(1, end - start + 1)


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> tuple[str, ...]:
    """Best-effort dotted/attribute decorator names, source order."""
    names: list[str] = []
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        rendered = _render_decorator(target)
        if rendered:
            names.append(rendered)
    return tuple(names)


def _render_decorator(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _render_decorator(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


# spec:portable-analysis-substrate::IM-5
class PythonAdapter(LanguageAdapter):
    """Exact ``ast``-based extractor for Python sources."""

    name = "python-ast"
    provider_version = "python-ast-v1"
    language = "python"
    extensions = (".py",)
    capabilities = FACT_CAPABILITIES | {CAP_PYTHON_AST}

    def parse(self, source: str) -> ast.Module | None:
        """Return the raw ``ast.Module`` tree, or ``None`` on ``SyntaxError``.

        Deep consumers that need the full tree (capability
        :data:`CAP_PYTHON_AST`) use this instead of re-parsing.
        """
        try:
            return ast.parse(source)
        except SyntaxError:
            return None

    def extract_symbols(
        self, source: str, *, path: str | None = None
    ) -> list[Symbol] | None:
        """Top-level symbols (with god-class expansion), or ``None`` if unparseable.

        Faithful to find-omnibus ``_python_symbols``:

        * top-level functions/classes whose bare name is a dunder are
          skipped;
        * a class with ``>= 3`` non-dunder methods is expanded — each
          method becomes a ``ClassName.method`` symbol (kind
          ``method`` / ``async_method``, ``cluster_name`` = method name,
          ``parent`` = class name);
        * a smaller class becomes one ``class`` symbol.
        """
        tree = self.parse(source)
        if tree is None:
            return None

        symbols: list[Symbol] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _is_dunder(node.name):
                    continue
                kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                symbols.append(
                    Symbol(
                        name=node.name,
                        cluster_name=node.name,
                        kind=kind,
                        lineno=node.lineno,
                        end_lineno=node.end_lineno or node.lineno,
                        loc=_node_loc(node),
                        parent=None,
                        is_dunder=False,
                        decorators=_decorator_names(node),
                    )
                )
            elif isinstance(node, ast.ClassDef):
                if _is_dunder(node.name):
                    continue
                method_nodes = [
                    m
                    for m in node.body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not _is_dunder(m.name)
                ]
                if len(method_nodes) >= _GOD_CLASS_METHOD_THRESHOLD:
                    for m in method_nodes:
                        kind = "async_method" if isinstance(m, ast.AsyncFunctionDef) else "method"
                        symbols.append(
                            Symbol(
                                name=f"{node.name}.{m.name}",
                                cluster_name=m.name,
                                kind=kind,
                                lineno=m.lineno,
                                end_lineno=m.end_lineno or m.lineno,
                                loc=_node_loc(m),
                                parent=node.name,
                                is_dunder=False,
                                decorators=_decorator_names(m),
                            )
                        )
                else:
                    symbols.append(
                        Symbol(
                            name=node.name,
                            cluster_name=node.name,
                            kind="class",
                            lineno=node.lineno,
                            end_lineno=node.end_lineno or node.lineno,
                            loc=_node_loc(node),
                            parent=None,
                            is_dunder=False,
                            decorators=_decorator_names(node),
                        )
                    )
        return symbols

    def analyze(
        self,
        source: str,
        *,
        path: str,
        capabilities: set[str] | frozenset[str],
    ) -> AnalysisResult:
        requested = self.require_capabilities(capabilities, path=path)
        tree = self.parse(source)
        if tree is None:
            raise AnalysisFailure(
                "parse_error",
                adapter=self.name,
                path=path,
                capability=requested[0] if requested else CAP_SYMBOLS,
                detail="Python syntax error",
            )

        facts: list[Fact] = []

        def add(capability: str, name: str, node: ast.AST, kind: str, parent: str | None = None) -> None:
            if capability not in requested or not name:
                return
            line = int(getattr(node, "lineno", 1) or 1)
            column = int(getattr(node, "col_offset", 0) or 0) + 1
            end_line = int(getattr(node, "end_lineno", line) or line)
            end_column = int(getattr(node, "end_col_offset", column) or column) + 1
            facts.append(Fact(capability, name, path, line, column, end_line, end_column, kind, parent))

        if CAP_SYMBOLS in requested:
            for symbol in self.extract_symbols(source, path=path) or []:
                facts.append(
                    Fact(
                        CAP_SYMBOLS,
                        symbol.name,
                        path,
                        symbol.lineno,
                        1,
                        symbol.end_lineno,
                        1,
                        symbol.kind,
                        symbol.parent,
                    )
                )

        parent_by_node: dict[ast.AST, str | None] = {}
        for parent in ast.walk(tree):
            owner = getattr(parent, "name", None) if isinstance(parent, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else None
            for child in ast.iter_child_nodes(parent):
                parent_by_node[child] = owner or parent_by_node.get(parent)

        for node in ast.walk(tree):
            parent = parent_by_node.get(node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                add(CAP_DEFINITIONS, node.name, node, type(node).__name__.lower(), parent)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                add(CAP_DEFINITIONS, node.id, node, "assignment", parent)
                add(CAP_WRITES, node.id, node, "assignment", parent)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                add(CAP_WRITES, _render_expression(node), node, "assignment", parent)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    add(CAP_IMPORTS, alias.name, node, "import", parent)
            elif isinstance(node, ast.ImportFrom):
                add(CAP_IMPORTS, node.module or "." * node.level, node, "import", parent)
            elif isinstance(node, ast.Call):
                add(CAP_CALLS, _render_expression(node.func), node.func, "call", parent)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                add(CAP_REFERENCES, node.id, node, "reference", parent)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                add(CAP_REFERENCES, _render_expression(node), node, "reference", parent)

        return AnalysisResult(
            ANALYSIS_INTERFACE_VERSION,
            self.name,
            self.provider_version,
            self.language,
            path,
            requested,
            tuple(sorted(set(facts), key=Fact.sort_key)),
        )


def _render_expression(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _render_expression(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""
