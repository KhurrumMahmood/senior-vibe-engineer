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


def _literal_strings(node: ast.AST) -> set[str]:
    return {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }


def _static_collection_strings(node: ast.AST) -> set[str]:
    """Recover strings from simple, side-effect-free computed collections."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return {value for child in node.elts for value in _static_collection_strings(child)}
    if isinstance(node, ast.Dict):
        return {
            value
            for child in [*node.keys, *node.values]
            if child is not None
            for value in _static_collection_strings(child)
        }
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _static_collection_strings(node.left) | _static_collection_strings(node.right)
    if not isinstance(node, ast.Call):
        return set()
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "split"
        and isinstance(node.func.value, ast.Constant)
        and isinstance(node.func.value.value, str)
        and not node.keywords
        and len(node.args) <= 1
        and (
            not node.args
            or (
                isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            )
        )
    ):
        separator = node.args[0].value if node.args else None
        return set(node.func.value.value.split(separator))
    if isinstance(node.func, ast.Name) and node.func.id in {
        "dict", "list", "set", "tuple", "zip"
    }:
        values = {
            value
            for argument in node.args
            for value in _static_collection_strings(argument)
        }
        values.update(keyword.arg for keyword in node.keywords if keyword.arg)
        values.update(
            value
            for keyword in node.keywords
            for value in _static_collection_strings(keyword.value)
        )
        return values
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
                computed_ids = sorted(_static_collection_strings(node.value) & stack_ids)
                if len(computed_ids) >= 2:
                    errors.append(
                        f"{relative}: hard-codes computed stack identifier collection {computed_ids}"
                    )
            if isinstance(node, ast.AnnAssign):
                duplicates = sorted(_assigned_names(node.target) & FORBIDDEN_ASSIGNMENTS)
                if duplicates:
                    errors.append(f"{relative}: forbidden duplicate registry assignment {duplicates}")
                if node.value is not None:
                    computed_ids = sorted(
                        _static_collection_strings(node.value) & stack_ids
                    )
                    if len(computed_ids) >= 2:
                        errors.append(
                            f"{relative}: hard-codes computed stack identifier collection {computed_ids}"
                        )
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                values = _literal_strings(node)
                duplicated_ids = sorted(values & stack_ids)
                if len(duplicated_ids) >= 2:
                    errors.append(
                        f"{relative}: hard-codes stack identifier collection {duplicated_ids}"
                    )
            if isinstance(node, ast.Dict):
                values = _literal_strings(node)
                duplicated_ids = sorted(values & stack_ids)
                if len(duplicated_ids) >= 2:
                    errors.append(
                        f"{relative}: hard-codes stack identifier dictionary {duplicated_ids}"
                    )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "dict"
            ):
                duplicated_ids = sorted(
                    {keyword.arg for keyword in node.keywords if keyword.arg} & stack_ids
                )
                if len(duplicated_ids) >= 2:
                    errors.append(
                        f"{relative}: hard-codes stack identifier dictionary {duplicated_ids}"
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
