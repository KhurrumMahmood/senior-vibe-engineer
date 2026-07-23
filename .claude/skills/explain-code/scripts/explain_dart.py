#!/usr/bin/env python3
"""Render bounded direct-public Dart declaration explanations from D3 facts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

sys.dont_write_bytecode = True


PUBLIC_KINDS = frozenset({"class", "enum", "extension", "mixin", "typedef", "top_level_function"})


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _module(path: Path) -> ModuleType | None:
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("dart_d3_snapshot", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dart_d3_snapshot"] = module
    spec.loader.exec_module(module)
    return module


def _support() -> ModuleType | None:
    path = Path(__file__).resolve().parents[2] / "_dart/scripts/dart_d3_snapshot.py"
    return _module(path)


def _local_terminal() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "analyzer": "dart-d3-union-syntax-snapshot-v1",
        "status": "partial",
        "failure_kind": "dart_d3_snapshot_companion_missing",
        "provider": {"inventory": [], "files": [], "source_manifest": {"preserved": True}},
    }


def _load(args: argparse.Namespace) -> dict[str, Any]:
    support = _support()
    if support is None:
        return _local_terminal()
    try:
        return support.load_for_consumer(
            args.facts,
            args.project_root,
            Path(args.target),
            consumer="explain-code",
            required_fact_groups=("directives", "declarations"),
        )
    except support.SnapshotError as exc:
        return support.terminal(exc.status, exc.failure_kind, str(exc))


def _safe_output(root: Path, requested: Path) -> Path:
    configured = root / "reports/explanations"
    output = requested if requested.is_absolute() else root / requested
    output = Path(os.path.abspath(output))
    if output.suffix.casefold() != ".md":
        raise ValueError("--output must be a Markdown artifact")
    try:
        relative = output.relative_to(configured)
    except ValueError as exc:
        raise ValueError("--output must be below reports/explanations") from exc
    if not relative.parts or relative == Path("."):
        raise ValueError("--output must name an explanation artifact")
    current = configured
    for path in (root / "reports", configured):
        if path.is_symlink():
            raise ValueError("report ancestors must not be symlinks")
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output must not resolve through a symlink")
    return output


def _selected_file(file: str, root: Path, target: str) -> bool:
    requested = (root / target).resolve()
    path = (root / file).resolve()
    return path == requested or requested in path.parents


def _facts(snapshot: dict[str, Any], root: Path, target: str) -> tuple[list[dict], list[dict]]:
    declarations: list[dict] = []
    unexplained: list[dict] = []
    if snapshot["status"] != "complete":
        return declarations, unexplained
    for file in snapshot["provider"]["files"]:
        if not _selected_file(file["file"], root, target):
            continue
        source = (root / file["file"]).read_bytes()
        for declaration in file["declarations"]:
            if not (
                declaration["top_level"]
                and not declaration["private"]
                and not declaration["anonymous"]
                and declaration["supported"]
                and declaration["kind"] in PUBLIC_KINDS
            ):
                continue
            offset, end = declaration["offset"], declaration["end"]
            name = declaration["name"]
            raw_key = f"{file['file']}\0{declaration['kind']}\0{name}\0{offset}".encode()
            declarations.append(
                {
                    "file": file["file"],
                    "name": name,
                    "kind": declaration["kind"],
                    "symbol_key": f"{name}-{_hash(raw_key)[:12]}",
                    "span": {
                        "offset": offset,
                        "end": end,
                        "line": declaration["line"],
                        "end_line": declaration["end_line"],
                    },
                    "source_sha256": file["source_sha256"],
                    "spelling_sha256": _hash(source[offset:end]),
                    "annotation_policy": "direct-syntax-contract-behavior-unresolved",
                }
            )
        for directive in file["directives"]:
            if directive["kind"] == "export":
                unexplained.append(
                    {
                        "file": file["file"],
                        "kind": "re_export",
                        "reason": (
                            "syntax-only export URI; alias and public binding resolution "
                            "remain unexplained"
                        ),
                        "uri": directive["uri"],
                    }
                )
    declarations.sort(key=lambda row: (row["file"], row["span"]["offset"], row["name"]))
    unexplained.sort(key=lambda row: (row["file"], row["uri"] or ""))
    return declarations, unexplained


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    try:
        output = _safe_output(root, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    sidecar = output.with_suffix("")
    annotations = sidecar / "annotations"
    output.unlink(missing_ok=True)
    for name in ("targets.json", "scan.json", "unexplained.txt", "surprises.txt"):
        (sidecar / name).unlink(missing_ok=True)
    shutil.rmtree(annotations, ignore_errors=True)

    snapshot = _load(args)
    declarations, unexplained = _facts(snapshot, root, args.target)
    selected, overflow = declarations[:15], declarations[15:]
    annotations.mkdir(parents=True, exist_ok=True)
    for row in selected:
        _atomic(
            annotations / f"{row['symbol_key']}.md",
            f"# `{row['name']}`\n\n"
            f"- Kind: `{row['kind']}`\n"
            f"- Source: `{row['file']}:{row['span']['line']}`\n"
            "- Contract: direct public Dart declaration with exact analyzer span.\n"
            "- Preconditions: unresolved without semantic, caller, or runtime evidence.\n"
            "- Postconditions: unresolved without semantic, caller, or runtime evidence.\n"
            "- Invariants: syntax surface only; behavior remains unexplained.\n"
            "- Unexplained regions: bodies, resolved types, aliases, callers, and runtime behavior.\n",
        )
    targets = {
        "schema_version": 1,
        "language": "dart",
        "target": args.target,
        "status": snapshot["status"],
        "failure_kind": snapshot["failure_kind"],
        "analyzer": snapshot["analyzer"],
        "public_symbol_count": len(declarations),
        "selected": selected,
        "overflow": overflow,
        "unexplained": unexplained,
        "snapshot_sha256": snapshot.get("snapshot_sha256"),
        "limitation": (
            "Direct syntax surface only; no callers, behavior, alias/re-export resolution, "
            "contracts, generated semantics, framework, or Flutter claim."
        ),
    }
    _atomic(sidecar / "targets.json", json.dumps(targets, indent=2, sort_keys=True) + "\n")
    _atomic(sidecar / "scan.json", json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    unresolved = [
        f"- `{row['file']}` — export `{row['uri']}`: {row['reason']}" for row in unexplained
    ]
    _atomic(sidecar / "unexplained.txt", "\n".join(unresolved) + ("\n" if unresolved else ""))
    _atomic(sidecar / "surprises.txt", "")
    contracts = [
        f"### `{row['name']}`\n\n"
        f"- Kind: `{row['kind']}`\n"
        f"- Source: `{row['file']}:{row['span']['line']}`\n"
        "- Invariant: direct syntax declaration; behavior remains unexplained.\n"
        "- Evidence: exact analyzer span and spelling hash in `targets.json`."
        for row in selected
    ]
    markdown = [
        f"# Explanation — {args.target}",
        "",
        f"Status: `{snapshot['status']}`",
        f"Failure: `{snapshot['failure_kind']}`",
        f"Public symbols: {len(declarations)}",
        "",
        "## Public contracts",
        "",
        "\n\n".join(contracts)
        if contracts
        else "No direct public declarations in the complete target.",
    ]
    if unresolved:
        markdown.extend(["", "## Unexplained regions", "", *unresolved])
    if snapshot["status"] != "complete":
        markdown.extend(["", "No explanation claim is available from incomplete evidence."])
    _atomic(output, "\n".join(markdown) + "\n")
    print(output)
    return 0 if snapshot["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
