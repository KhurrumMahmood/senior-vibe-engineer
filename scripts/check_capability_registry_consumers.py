#!/usr/bin/env python3
"""Guard canonical capability consumers against a second stack registry."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

from _lib.capability_registry import load_registry


REPO_ROOT = Path(__file__).resolve().parent.parent
CONSUMERS = (
    "scripts/skill_meta.py",
    "scripts/project_adapt.py",
    ".claude/skills/which-skill/scripts/match.py",
    ".claude/skills/find-perimeter-gaps/scripts/scan.py",
    "scripts/manifest.py",
    "scripts/installer_selection.py",
    "scripts/sweep_shims.py",
)
FORBIDDEN_ASSIGNMENTS = {
    "VALID_LANGUAGES",
    "VALID_FRAMEWORKS",
    "LANGUAGE_BY_EXTENSION",
    "SUPPORTED_LANGUAGES",
    "SUPPORTED_FRAMEWORKS",
}
FORBIDDEN_COMPOSITE_IDENTIFIERS = {"javascript/typescript", "vite/vitest"}


def _assigned_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return {name for child in node.elts for name in _assigned_names(child)}
    return set()


def check_consumers(root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    registry = load_registry()
    stack_ids = (
        set(registry.identifiers("languages"))
        | set(registry.identifiers("frameworks"))
    ) - {"any", "none"}
    for relative in CONSUMERS:
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except (OSError, SyntaxError) as exc:
            errors.append(f"{relative}: cannot inspect: {exc}")
            continue
        imported = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "_lib.capability_registry":
                imported = True
            if isinstance(node, ast.Assign):
                names = {name for target in node.targets for name in _assigned_names(target)}
                duplicates = sorted(names & FORBIDDEN_ASSIGNMENTS)
                if duplicates:
                    errors.append(f"{relative}: forbidden duplicate registry assignment {duplicates}")
            if isinstance(node, ast.AnnAssign):
                duplicates = sorted(_assigned_names(node.target) & FORBIDDEN_ASSIGNMENTS)
                if duplicates:
                    errors.append(f"{relative}: forbidden duplicate registry assignment {duplicates}")
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                values = {
                    child.value
                    for child in node.elts
                    if isinstance(child, ast.Constant) and isinstance(child.value, str)
                }
                duplicated_ids = sorted(values & stack_ids)
                if len(duplicated_ids) >= 2:
                    errors.append(
                        f"{relative}: hard-codes stack identifier collection {duplicated_ids}"
                    )
        if not imported:
            errors.append(f"{relative}: does not import the canonical capability registry")
        for identifier in sorted(FORBIDDEN_COMPOSITE_IDENTIFIERS):
            if identifier in text:
                errors.append(f"{relative}: contains forbidden composite stack identifier {identifier!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    errors = check_consumers(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"OK — {len(CONSUMERS)} consumers use the canonical capability registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
