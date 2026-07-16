#!/usr/bin/env python3
"""Extract the pinned syntax facts with tree-sitter-language-pack."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from tree_sitter_language_pack import get_parser


DEFINITION_NODES = {
    "function_declaration",
    "enum_declaration",
    "interface_declaration",
    "variable_declarator",
}


def text(node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def child_text(node, field: str, source: bytes) -> str | None:
    child = node.child_by_field_name(field)
    return text(child, source) if child is not None else None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: tree_sitter_probe.py <corpus-root>", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    parser = get_parser("typescript")
    facts = {name: set() for name in ("definitions", "imports", "calls", "writes")}
    for path in sorted((root / "src").glob("*.ts")):
        source = path.read_bytes()
        tree = parser.parse(source)
        if tree.root_node.has_error:
            print(f"parse error: {path}", file=sys.stderr)
            return 1
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            stack.extend(reversed(node.children))
            if node.type in DEFINITION_NODES:
                name = child_text(node, "name", source)
                if name:
                    facts["definitions"].add(name)
            elif node.type == "import_statement":
                value = child_text(node, "source", source)
                if value:
                    facts["imports"].add(value.strip("'\""))
            elif node.type == "call_expression":
                value = child_text(node, "function", source)
                if value:
                    facts["calls"].add(value)
            elif node.type == "assignment_expression":
                value = child_text(node, "left", source)
                if value:
                    facts["writes"].add(value)
    print(json.dumps({key: sorted(value) for key, value in facts.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
