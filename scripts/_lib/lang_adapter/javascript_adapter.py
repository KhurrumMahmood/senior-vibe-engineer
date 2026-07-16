"""Real parser-backed JavaScript and TypeScript normalized fact adapters."""
from __future__ import annotations

from collections import Counter
import threading
from typing import Any

from .base import (
    ANALYSIS_INTERFACE_VERSION,
    CAP_CALLS,
    CAP_DEFINITIONS,
    CAP_IMPORTS,
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


DEFINITION_TYPES = {
    "function_declaration": "function",
    "generator_function_declaration": "function",
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "type_alias_declaration": "type",
    "variable_declarator": "variable",
    "method_definition": "method",
}
IDENTIFIER_TYPES = {
    "identifier",
    "type_identifier",
    "property_identifier",
    "shorthand_property_identifier_pattern",
}


def _node_text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _field_text(node: Any, field: str, source: bytes) -> str:
    child = node.child_by_field_name(field)
    return _node_text(child, source) if child is not None else ""


# spec:portable-analysis-substrate::IM-2
class TreeSitterAdapter(LanguageAdapter):
    """Shared deterministic syntax-fact provider backed by pinned grammars."""

    grammar: str
    provider_version = "tree-sitter-0.26.0+language-pack-1.12.5"
    definition_types = DEFINITION_TYPES
    import_node_types = {"import_statement"}
    capabilities = FACT_CAPABILITIES
    parse_timeout_seconds = 5.0

    def _load_parser(self):
        from tree_sitter_language_pack import get_parser

        return get_parser(self.grammar)

    def _parse(self, source: bytes, *, path: str, capability: str):
        try:
            parser = self._load_parser()
        except (ImportError, ModuleNotFoundError, OSError) as exc:
            raise AnalysisFailure(
                "missing_tool",
                adapter=self.name,
                path=path,
                capability=capability,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            raise AnalysisFailure(
                "tool_failure",
                adapter=self.name,
                path=path,
                capability=capability,
                detail=str(exc),
            ) from exc
        outcome: dict[str, Any] = {}
        completed = threading.Event()

        def run_parse() -> None:
            try:
                outcome["tree"] = parser.parse(source)
            except BaseException as exc:  # noqa: BLE001 - provider boundary
                outcome["error"] = exc
            finally:
                completed.set()

        worker = threading.Thread(
            target=run_parse,
            name=f"{self.name}-parse",
            daemon=True,
        )
        worker.start()
        if not completed.wait(self.parse_timeout_seconds):
            raise AnalysisFailure(
                "tool_timeout",
                adapter=self.name,
                path=path,
                capability=capability,
                detail=f"parser exceeded {self.parse_timeout_seconds:.3f}s deadline",
            )
        error = outcome.get("error")
        if isinstance(error, TimeoutError):
            raise AnalysisFailure(
                "tool_timeout",
                adapter=self.name,
                path=path,
                capability=capability,
                detail=str(error),
            ) from error
        if isinstance(error, Exception):
            raise AnalysisFailure(
                "tool_failure",
                adapter=self.name,
                path=path,
                capability=capability,
                detail=str(error),
            ) from error
        tree = outcome.get("tree")
        try:
            root = getattr(tree, "root_node", None)
            children = root.children
            named_children = root.named_children
            has_error = root.has_error
        except Exception as exc:
            raise AnalysisFailure(
                "corrupt_output",
                adapter=self.name,
                path=path,
                capability=capability,
                detail=f"parser result has no valid root node: {exc}",
            ) from exc
        if root is None or children is None or named_children is None:
            raise AnalysisFailure(
                "corrupt_output",
                adapter=self.name,
                path=path,
                capability=capability,
                detail="parser result has no valid root node",
            )
        if has_error:
            raise AnalysisFailure(
                "parse_error",
                adapter=self.name,
                path=path,
                capability=capability,
                detail="syntax tree contains an error node",
            )
        return root

    def _definition_name(self, node: Any, source: bytes) -> str:
        return _field_text(node, "name", source)

    def _definition_node(self, node: Any) -> Any | None:
        return node.child_by_field_name("name")

    def _definition_kind(self, node: Any) -> str:
        if node.type == "variable_declarator":
            value = node.child_by_field_name("value")
            if value is not None and value.type in {
                "arrow_function",
                "function_expression",
                "generator_function",
            }:
                return "function"
        return self.definition_types[node.type]

    def _import_name(self, node: Any, source: bytes) -> str:
        if node.type != "import_statement":
            return ""
        return _field_text(node, "source", source).strip("'\"")

    def _write_name(self, node: Any, source: bytes) -> str:
        return _field_text(node, "left", source) if node.type == "assignment_expression" else ""

    def _parent_name(self, node: Any, source: bytes) -> str | None:
        parent = node.parent
        while parent is not None:
            if parent.type in self.definition_types:
                name = self._definition_name(parent, source)
                if name:
                    return name
            parent = parent.parent
        return None

    def analyze(
        self,
        source: str,
        *,
        path: str,
        capabilities: set[str] | frozenset[str],
    ) -> AnalysisResult:
        primary = sorted(capabilities)[0] if capabilities else CAP_SYMBOLS
        try:
            return self._analyze(source, path=path, capabilities=capabilities)
        except AnalysisFailure:
            raise
        except Exception as exc:
            raise AnalysisFailure(
                "corrupt_output",
                adapter=self.name,
                path=path,
                capability=primary,
                detail=f"invalid parser output: {exc}",
            ) from exc

    def _analyze(
        self,
        source: str,
        *,
        path: str,
        capabilities: set[str] | frozenset[str],
    ) -> AnalysisResult:
        requested = self.require_capabilities(capabilities, path=path)
        source_bytes = source.encode("utf-8")
        primary = requested[0] if requested else CAP_SYMBOLS
        root = self._parse(source_bytes, path=path, capability=primary)
        facts: list[Fact] = []
        definition_positions: set[tuple[int, int]] = set()
        reference_candidates: list[tuple[Any, str]] = []

        def add(capability: str, name: str, node: Any, kind: str, parent: str | None = None) -> None:
            if capability not in requested or not name:
                return
            facts.append(
                Fact(
                    capability,
                    name,
                    path,
                    node.start_point.row + 1,
                    node.start_point.column + 1,
                    node.end_point.row + 1,
                    node.end_point.column + 1,
                    kind,
                    parent,
                )
            )

        stack = [root]
        while stack:
            node = stack.pop()
            stack.extend(reversed(node.named_children))
            if node.type in self.definition_types:
                name_node = self._definition_node(node)
                name = self._definition_name(node, source_bytes)
                if name_node is not None:
                    definition_positions.add((name_node.start_byte, name_node.end_byte))
                parent = self._parent_name(node, source_bytes)
                kind = self._definition_kind(node)
                add(CAP_DEFINITIONS, name, name_node or node, kind, parent)
                add(CAP_SYMBOLS, name, name_node or node, kind, parent)
            if node.type == "assignment_expression":
                right = node.child_by_field_name("right")
                left = node.child_by_field_name("left")
                if right is not None and right.type in {"arrow_function", "function_expression"} and left is not None:
                    assigned = _node_text(left, source_bytes).rsplit(".", 1)[-1]
                    definition_positions.add((left.start_byte, left.end_byte))
                    add(CAP_DEFINITIONS, assigned, left, "function", self._parent_name(node, source_bytes))
                    add(CAP_SYMBOLS, assigned, left, "function", self._parent_name(node, source_bytes))
            if node.type in self.import_node_types:
                add(CAP_IMPORTS, self._import_name(node, source_bytes), node, "import")
            if node.type == "call_expression":
                function = node.child_by_field_name("function")
                add(CAP_CALLS, _node_text(function, source_bytes) if function else "", function or node, "call", self._parent_name(node, source_bytes))
            write = self._write_name(node, source_bytes)
            if write:
                left = node.child_by_field_name("left")
                add(CAP_WRITES, write, left or node, "assignment", self._parent_name(node, source_bytes))
            if node.type in IDENTIFIER_TYPES:
                reference_candidates.append((node, _node_text(node, source_bytes)))

        # spec:portable-analysis-substrate::IM-4
        # These are deterministic syntax references. ADR 0039 reserves a
        # project-pinned compiler provider for a future named semantic
        # definition/reference/type consumer; none exists in the inventory.
        if CAP_REFERENCES in requested:
            counts = Counter(name for _, name in reference_candidates)
            definition_counts = Counter(
                name
                for node, name in reference_candidates
                if (node.start_byte, node.end_byte) in definition_positions
            )
            for node, name in reference_candidates:
                position = (node.start_byte, node.end_byte)
                has_non_definition_occurrence = counts[name] > definition_counts[name]
                if position not in definition_positions and (
                    has_non_definition_occurrence or definition_counts[name] == 0
                ):
                    add(CAP_REFERENCES, name, node, "reference", self._parent_name(node, source_bytes))

        return AnalysisResult(
            ANALYSIS_INTERFACE_VERSION,
            self.name,
            self.provider_version,
            self.language,
            path,
            requested,
            tuple(sorted(set(facts), key=Fact.sort_key)),
        )

    def extract_symbols(self, source: str, *, path: str | None = None) -> list[Symbol] | None:
        display_path = path or "<memory>"
        try:
            result = self.analyze(source, path=display_path, capabilities={CAP_SYMBOLS})
        except AnalysisFailure as failure:
            if failure.code == "parse_error":
                return None
            raise
        return [
            Symbol(
                name=fact.name,
                cluster_name=fact.name,
                kind=fact.kind,
                lineno=fact.line,
                end_lineno=fact.end_line,
                loc=max(1, fact.end_line - fact.line + 1),
                parent=fact.parent,
                decorators=(),
            )
            for fact in result.facts
        ]


class JavaScriptAdapter(TreeSitterAdapter):
    name = "javascript-syntax"
    language = "javascript"
    grammar = "javascript"
    extensions = (".js", ".mjs", ".cjs", ".jsx")


# spec:portable-analysis-substrate::IM-3
class TypeScriptAdapter(TreeSitterAdapter):
    name = "typescript-syntax"
    language = "typescript"
    # The TSX grammar accepts both TypeScript and JSX-bearing TSX, so one
    # deterministic provider covers both registered extensions.
    grammar = "tsx"
    extensions = (".ts", ".tsx", ".mts", ".cts")
