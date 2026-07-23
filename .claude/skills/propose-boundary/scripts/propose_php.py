#!/usr/bin/env python3
"""Synthesize one accepted PHP boundary selection without detecting a seam."""
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
    "Composer direct-symbol facts establish complete runtime reachability",
    "framework containers, reflection, traits, inheritance, or external consumers are covered",
    "public or semver compatibility is proved",
    "this read-only proposal authorizes an extraction",
]


def _data(evidence: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    decision = acceptance.get("decision")
    if decision == "defer_cohesive_target":
        return {
            "schema_version": "php-boundary-proposal-v1",
            "language": "php",
            "status": "deferred",
            "outcome": "defer_cohesive_target",
            "read_only": True,
            "source_preserved": True,
            "nonclaims": NONCLAIMS,
        }
    if decision != "propose":
        raise E.EvidenceError("acceptance_invalid", "boundary decision is unsupported")
    selection = acceptance.get("selection")
    if not isinstance(selection, dict):
        raise E.EvidenceError("selection_invalid", "accepted boundary selection is missing")
    classes = {row.get("fqcn"): row for row in evidence.get("classes", []) if isinstance(row, dict)}
    members = selection.get("members")
    public_api = selection.get("public_api")
    if (
        not isinstance(members, list)
        or len(members) < 2
        or len(set(members)) != len(members)
        or not all(isinstance(item, str) and item in classes for item in members)
        or not isinstance(public_api, list)
        or not public_api
    ):
        raise E.EvidenceError("selection_invalid", "accepted boundary members/API lack A3 authority")
    methods = {
        method.get("fqmn")
        for member in members
        for method in classes[member].get("methods", [])
        if isinstance(method, dict)
    }
    if not all(isinstance(item, str) and item in methods for item in public_api):
        raise E.EvidenceError("selection_invalid", "public API is not present in accepted A3 facts")
    if any(classes[item].get("boundaries") for item in members):
        raise E.EvidenceError("selection_incomplete", "selected members carry unresolved A3 boundaries")
    for key in ("boundary_name", "target_namespace", "proposed_namespace", "compatibility"):
        if not isinstance(selection.get(key), str) or not selection[key]:
            raise E.EvidenceError("selection_invalid", f"accepted boundary selection lacks {key}")
    return {
        "schema_version": "php-boundary-proposal-v1",
        "language": "php",
        "status": "ready_for_human_review",
        "outcome": "boundary_plan_ready",
        "read_only": True,
        "source_preserved": True,
        "selection": selection,
        "member_evidence": [
            {"fqcn": item, "file": classes[item]["file"], "source_sha256": classes[item]["source_sha256"]}
            for item in members
        ],
        "caller_impact_boundary": "Only accepted Composer direct relationships are known; run project-aware reference review before approval.",
        "characterization": [f"pin {item} before and after extraction" for item in public_api],
        "project_identity": evidence.get("project_identity"),
        "source_manifest_sha256": evidence.get("source_manifest_sha256"),
        "nonclaims": NONCLAIMS,
    }


def _markdown(data: dict[str, Any]) -> str:
    selection = data["selection"]
    members = "\n".join(f"- `{item}`" for item in selection["members"])
    api = "\n".join(f"- `{item}`" for item in selection["public_api"])
    tests = "\n".join(f"- {item}" for item in data["characterization"])
    limits = "\n".join(f"- {item}" for item in NONCLAIMS)
    return f"""# PHP boundary proposal — {selection['boundary_name']}

Status: `ready_for_human_review`. No source is edited.

## Accepted seam

Move the selected concern from `{selection['target_namespace']}` toward
`{selection['proposed_namespace']}` while preserving old entry points.

{members}

## Proposed public API

{api}

## Compatibility and caller impact

{selection['compatibility']}. {data['caller_impact_boundary']}

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
        destination = E.output_dir(root, args.output_dir, "propose-boundary")
        E.begin(destination)
        _, evidence, acceptance, native = E.validate(
            root=root, consumer="propose-boundary", evidence_arg=args.evidence,
            acceptance_arg=args.acceptance, php=args.php, composer=args.composer,
        )
        data = _data(evidence, acceptance)
        files = {"inspection.json": E.json_text({**data, "native": native})}
        if data["status"] != "deferred":
            files["proposal.md"] = _markdown(data)
        E.replace_bundle(destination, files)
    except (AttributeError, OSError, UnicodeError, KeyError, TypeError, ValueError) as error:
        if destination is not None:
            E.refuse(destination, "propose-boundary", error)
        print(f"[propose_php_boundary] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
