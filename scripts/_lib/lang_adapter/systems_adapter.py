"""Tree-sitter fact providers for the accepted Rust and Go subset."""
from __future__ import annotations

from typing import Any

from .javascript_adapter import TreeSitterAdapter, _field_text, _node_text


# spec:portable-analysis-substrate::IM-6
class RustAdapter(TreeSitterAdapter):
    name = "rust-syntax"
    language = "rust"
    grammar = "rust"
    extensions = (".rs",)
    import_node_types = {"use_declaration"}
    definition_types = {
        "function_item": "function",
        "struct_item": "class",
        "enum_item": "enum",
        "trait_item": "interface",
        "type_item": "type",
        "const_item": "constant",
        "static_item": "variable",
        "let_declaration": "variable",
    }

    def _definition_name(self, node: Any, source: bytes) -> str:
        if node.type == "let_declaration":
            return _field_text(node, "pattern", source)
        return _field_text(node, "name", source)

    def _definition_node(self, node: Any) -> Any | None:
        if node.type == "let_declaration":
            return node.child_by_field_name("pattern")
        return super()._definition_node(node)

    def _import_name(self, node: Any, source: bytes) -> str:
        if node.type != "use_declaration":
            return ""
        value = _field_text(node, "argument", source)
        if value:
            return value
        return _node_text(node, source).removeprefix("use ").removesuffix(";").strip()

    def _write_name(self, node: Any, source: bytes) -> str:
        if node.type == "assignment_expression":
            return _field_text(node, "left", source)
        if node.type == "let_declaration":
            return _field_text(node, "pattern", source)
        return ""

    def analyze(self, source: str, *, path: str, capabilities):
        return super().analyze(source, path=path, capabilities=capabilities)


class GoAdapter(TreeSitterAdapter):
    name = "go-syntax"
    language = "go"
    grammar = "go"
    extensions = (".go",)
    import_node_types = {"import_spec"}
    definition_types = {
        "function_declaration": "function",
        "method_declaration": "method",
        "type_spec": "type",
        "var_spec": "variable",
        "const_spec": "constant",
        "short_var_declaration": "variable",
    }

    def _definition_name(self, node: Any, source: bytes) -> str:
        if node.type == "short_var_declaration":
            left = node.child_by_field_name("left")
            return _node_text(left, source) if left is not None else ""
        return _field_text(node, "name", source)

    def _definition_node(self, node: Any) -> Any | None:
        if node.type == "short_var_declaration":
            return node.child_by_field_name("left")
        return super()._definition_node(node)

    def _import_name(self, node: Any, source: bytes) -> str:
        if node.type != "import_spec":
            return ""
        for child in node.named_children:
            if "string" in child.type:
                return _node_text(child, source).strip('"`')
        return ""

    def _write_name(self, node: Any, source: bytes) -> str:
        if node.type in {"assignment_statement", "short_var_declaration"}:
            left = node.child_by_field_name("left")
            return _node_text(left, source) if left is not None else ""
        return ""

    def analyze(self, source: str, *, path: str, capabilities):
        return super().analyze(source, path=path, capabilities=capabilities)
