#!/usr/bin/env python3
"""Synthesize one accepted PHP folder plan without detecting a cluster."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


def _library() -> Any:
    local = Path(__file__).with_name("php_proposal_evidence.py")
    canonical = Path(__file__).resolve().parents[2] / "_php-proposal/php_proposal_evidence.py"
    path = local if local.is_file() else canonical
    spec = importlib.util.spec_from_file_location("php_proposal_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("php_proposal_evidence.py is missing from the copied closure")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


E = _library()
NONCLAIMS = [
    "Composer direct-symbol facts establish every import or runtime consumer",
    "framework, reflection, generated, inherited, trait, or external edges are complete",
    "the proposed namespace change is backward compatible without reviewed shims",
    "this read-only plan authorizes file moves",
]


def _data(root: Path, evidence: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    decision = acceptance.get("decision")
    if decision == "defer_no_convention":
        return {
            "schema_version": "php-folder-proposal-v1", "language": "php",
            "status": "deferred", "outcome": "defer_no_convention", "read_only": True,
            "source_preserved": True, "nonclaims": NONCLAIMS,
        }
    if decision != "propose":
        raise E.EvidenceError("acceptance_invalid", "folder decision is unsupported")
    selection = acceptance.get("selection")
    moves = selection.get("moves") if isinstance(selection, dict) else None
    if not isinstance(moves, dict) or len(moves) < 3:
        raise E.EvidenceError("selection_invalid", "accepted folder plan needs at least three moves")
    inventory = {
        row.get("file"): row
        for row in evidence.get("source_inventory", {}).get("inventory", [])
        if isinstance(row, dict) and row.get("role") == "eligible" and row.get("selected") is True
    }
    parent = selection.get("parent")
    if not isinstance(parent, str) or not parent:
        raise E.EvidenceError("selection_invalid", "accepted folder parent is missing")
    normalized: list[dict[str, str]] = []
    for source, destination in moves.items():
        if not isinstance(source, str) or source not in inventory:
            raise E.EvidenceError("selection_invalid", f"move lacks accepted inventory authority: {source}")
        if Path(source).parent.as_posix() != parent:
            raise E.EvidenceError("selection_invalid", "every source must be a direct selected sibling")
        target = E.safe_path(root, destination, "proposed destination", exists=False)
        if target.exists() or Path(destination).suffix != ".php" or Path(destination).parent == Path(parent):
            raise E.EvidenceError("selection_invalid", "destination must be a new PHP subdirectory path")
        normalized.append({"from": source, "to": destination, "source_sha256": inventory[source]["source_sha256"]})
    for key in ("cluster", "proposed_namespace", "compatibility", "convention"):
        if not isinstance(selection.get(key), str) or not selection[key]:
            raise E.EvidenceError("selection_invalid", f"accepted folder selection lacks {key}")
    return {
        "schema_version": "php-folder-proposal-v1", "language": "php",
        "status": "ready_for_human_review", "outcome": "folder_plan_ready",
        "read_only": True, "source_preserved": True, "selection": selection,
        "moves": normalized,
        "import_impact": "Re-resolve every accepted direct type/new relationship and all project-aware references before approval.",
        "characterization": [f"pin behavior for {row['from']} before and after the move" for row in normalized],
        "project_identity": evidence.get("project_identity"),
        "source_manifest_sha256": evidence.get("source_manifest_sha256"),
        "nonclaims": NONCLAIMS,
    }


def _markdown(data: dict[str, Any]) -> str:
    selection = data["selection"]
    moves = "\n".join(f"- `{row['from']}` → `{row['to']}`" for row in data["moves"])
    tests = "\n".join(f"- {item}" for item in data["characterization"])
    limits = "\n".join(f"- {item}" for item in NONCLAIMS)
    return f"""# PHP folder reorganization proposal — {selection['cluster']}

Status: `ready_for_human_review`. No file is moved.

## Accepted convention

{selection['convention']}

## Current → proposed tree

{moves}

Proposed namespace: `{selection['proposed_namespace']}`.

## Compatibility and import impact

{selection['compatibility']}. {data['import_impact']}

## Characterization matrix

{tests}

## Explicit non-claims

{limits}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project-root", "evidence", "acceptance", "output-dir", "php", "composer"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    destination: Path | None = None
    try:
        destination = E.output_dir(root, args.output_dir, "propose-folder-reorganization")
        E.begin(destination)
        _, evidence, acceptance, native = E.validate(
            root=root, consumer="propose-folder-reorganization", evidence_arg=args.evidence,
            acceptance_arg=args.acceptance, php=args.php, composer=args.composer,
        )
        data = _data(root, evidence, acceptance)
        files = {"inspection.json": E.json_text({**data, "native": native})}
        if data["status"] != "deferred":
            files["proposal.md"] = _markdown(data)
        E.replace_bundle(destination, files)
    except (AttributeError, OSError, UnicodeError, KeyError, TypeError, ValueError) as error:
        if destination is not None:
            E.refuse(destination, "propose-folder-reorganization", error)
        print(f"[propose_php_folder] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
