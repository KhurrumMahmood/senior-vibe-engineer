#!/usr/bin/env python3
"""Synthesize one accepted PHP shadow disposition from confirmed A3 evidence."""
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
    "equal direct construction shape proves behavioral equivalence",
    "callers, exceptions, side effects, framework wiring, or external consumers are complete",
    "public or semver compatibility is established",
    "this read-only proposal authorizes consolidation",
]


def _data(evidence: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    selection = acceptance.get("selection")
    candidate_id = selection.get("candidate_id") if isinstance(selection, dict) else None
    decision = acceptance.get("decision")
    if decision == "keep_separate":
        matches = [
            row
            for row in evidence.get("uncertain", [])
            if isinstance(row, dict) and row.get("candidate_id") == candidate_id
        ]
        if len(matches) != 1 or matches[0].get("human_verdict") != "keep_separate":
            raise E.EvidenceError("selection_unaccepted", "keep-separate requires the exact A3 human verdict")
        return {
            "schema_version": "php-shadow-proposal-v1", "language": "php",
            "status": "complete", "outcome": "keep_separate", "read_only": True,
            "source_preserved": True, "candidate": matches[0], "nonclaims": NONCLAIMS,
        }
    if decision != "propose":
        raise E.EvidenceError("acceptance_invalid", "shadow decision is unsupported")
    matches = [
        row
        for row in evidence.get("confirmed", [])
        if isinstance(row, dict) and row.get("candidate_id") == candidate_id
    ]
    if len(matches) != 1 or matches[0].get("human_verdict") != "confirm_candidate":
        raise E.EvidenceError("selection_unaccepted", "one exact A3-confirmed shadow is required")
    finding = matches[0]
    members = [row.get("fqmn") for row in finding.get("members", []) if isinstance(row, dict)]
    canonical = selection.get("canonical")
    shape = selection.get("shape")
    if canonical not in members or shape not in {"delegate_to_canonical", "extract_shared_utility"}:
        raise E.EvidenceError("selection_invalid", "accepted canonical member/shape is invalid")
    return {
        "schema_version": "php-shadow-proposal-v1", "language": "php",
        "status": "ready_for_human_review", "outcome": "consolidation_plan_ready",
        "read_only": True, "source_preserved": True,
        "candidate_id": candidate_id, "finding": finding, "canonical": canonical,
        "consolidation_shape": shape,
        "other_members": [item for item in members if item != canonical],
        "caller_impact_boundary": "A project-aware complete reference inventory is required before approval.",
        "project_identity": evidence.get("project_identity"),
        "source_manifest_sha256": evidence.get("source_manifest_sha256"),
        "nonclaims": NONCLAIMS,
    }


def _markdown(data: dict[str, Any]) -> str:
    others = "\n".join(f"- `{item}`" for item in data["other_members"])
    limits = "\n".join(f"- {item}" for item in NONCLAIMS)
    return f"""# PHP shadow-unification proposal

Status: `ready_for_human_review`. No source is edited.

## Accepted shape

Keep `{data['canonical']}` canonical and `{data['consolidation_shape']}` for:

{others}

The A3 finding proves only one Composer-resolved direct return-construction
shape. {data['caller_impact_boundary']}

## Verification and stop condition

Characterize every member, preserve returned values and side effects, run the
accepted Composer/PHP matrix before and after, and stop on any behavior drift.

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
        destination = E.output_dir(root, args.output_dir, "unify-shadows")
        E.begin(destination)
        _, evidence, acceptance, native = E.validate(
            root=root, consumer="unify-shadows", evidence_arg=args.evidence,
            acceptance_arg=args.acceptance, php=args.php, composer=args.composer,
        )
        data = _data(evidence, acceptance)
        files = {"inspection.json": E.json_text({**data, "native": native})}
        if data["outcome"] != "keep_separate":
            files["proposal.md"] = _markdown(data)
        E.replace_bundle(destination, files)
    except (AttributeError, OSError, UnicodeError, KeyError, TypeError, ValueError) as error:
        if destination is not None:
            E.refuse(destination, "unify-shadows", error)
        print(f"[propose_php_shadows] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
