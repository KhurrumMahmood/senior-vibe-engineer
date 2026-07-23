#!/usr/bin/env python3
"""Turn one accepted PHP implicit-state finding into a read-only enum proposal."""
from __future__ import annotations

import argparse
import importlib.util
import re
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
    "the observed literals prove a closed domain",
    "dynamic, reflected, framework, inherited, trait, or external consumers are complete",
    "serialization, database, wire, or public API compatibility is established",
    "this proposal authorizes source edits",
]


def _pascal(value: str) -> str:
    pieces = re.findall(r"[A-Za-z0-9]+", value)
    if not pieces:
        raise E.EvidenceError("candidate_invalid", "a literal cannot become a PHP case name")
    result = "".join(piece[:1].upper() + piece[1:] for piece in pieces)
    return ("Value" + result) if result[0].isdigit() else result


def _proposal(evidence: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
    findings = evidence.get("findings")
    if not isinstance(findings, list):
        raise E.EvidenceError("evidence_invalid", "implicit-state findings are malformed")
    decision = acceptance.get("decision")
    if decision == "defer_no_candidate":
        if findings:
            raise E.EvidenceError("acceptance_invalid", "cannot accept clean while findings exist")
        return {
            "schema_version": "php-enum-proposal-v1",
            "language": "php",
            "status": "complete",
            "outcome": "clean",
            "read_only": True,
            "source_preserved": True,
            "nonclaims": NONCLAIMS,
        }
    if decision != "propose":
        raise E.EvidenceError("acceptance_invalid", "enum acceptance decision is unsupported")
    selection = acceptance.get("selection")
    candidate_id = selection.get("candidate_id") if isinstance(selection, dict) else None
    matches = [row for row in findings if isinstance(row, dict) and row.get("candidate_id") == candidate_id]
    if len(matches) != 1:
        raise E.EvidenceError("selection_invalid", "acceptance must select one accepted state finding")
    row = matches[0]
    if row.get("human_verdict") != "extract_enum_candidate":
        raise E.EvidenceError("selection_unaccepted", "A3 human enum-candidate authority is required")
    authority, literals, operations = row.get("authority"), row.get("literals"), row.get("operations")
    if (
        not isinstance(authority, dict)
        or authority.get("field_type") != "string"
        or not isinstance(literals, list)
        or len(literals) < 2
        or not all(isinstance(item, str) and item for item in literals)
        or not isinstance(operations, list)
        or len(operations) < 2
    ):
        raise E.EvidenceError("selection_invalid", "selected state finding lacks bounded authority")
    fqcn = authority.get("fqcn")
    field = authority.get("field")
    if not isinstance(fqcn, str) or not isinstance(field, str):
        raise E.EvidenceError("selection_invalid", "selected field identity is malformed")
    short_owner = fqcn.rsplit("\\", 1)[-1]
    enum_name = short_owner + field[:1].upper() + field[1:]
    variants = [{"case": _pascal(item), "value": item} for item in sorted(set(literals))]
    if len({row["case"] for row in variants}) != len(variants):
        raise E.EvidenceError("selection_invalid", "enum cases collide after normalization")
    return {
        "schema_version": "php-enum-proposal-v1",
        "language": "php",
        "status": "review_required",
        "outcome": "proposal_ready",
        "read_only": True,
        "source_preserved": True,
        "authority": authority,
        "candidate_id": candidate_id,
        "candidate_sha256": row.get("candidate_sha256"),
        "operations": operations,
        "proposed_enum": {"name": enum_name, "backing_type": "string", "cases": variants},
        "project_identity": evidence.get("project_identity"),
        "source_manifest_sha256": evidence.get("source_manifest_sha256"),
        "nonclaims": NONCLAIMS,
        "next_step": "Human approval is required before migration or guard staging.",
    }


def _markdown(data: dict[str, Any]) -> str:
    cases = "\n".join(f"    case {row['case']} = '{row['value']}';" for row in data["proposed_enum"]["cases"])
    callers = "\n".join(
        f"- `{row['file']}:{row['line']}` — {row['operation']} `{row['literal']}`"
        for row in data["operations"]
    )
    limits = "\n".join(f"- {item}" for item in NONCLAIMS)
    enum_name = data["proposed_enum"]["name"]
    return f"""# PHP enum extraction proposal

Status: `review_required`. This artifact consumes accepted A3 evidence and edits no source.

```php
enum {enum_name}: string
{{
{cases}
}}
```

## Exact accepted operations

{callers}

## Human authority

Confirm domain closure, case names, storage/wire compatibility, migration order, and guard policy.

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
        destination = E.output_dir(root, args.output_dir, "extract-enum")
        E.begin(destination)
        _, evidence, acceptance, native = E.validate(
            root=root,
            consumer="extract-enum",
            evidence_arg=args.evidence,
            acceptance_arg=args.acceptance,
            php=args.php,
            composer=args.composer,
        )
        data = _proposal(evidence, acceptance)
        inspection = {**data, "native": native}
        files = {"inspection.json": E.json_text(inspection)}
        if data["outcome"] == "proposal_ready":
            files.update({"targets.json": E.json_text(data), "proposal.md": _markdown(data)})
        E.replace_bundle(destination, files)
    except (AttributeError, OSError, UnicodeError, KeyError, TypeError, ValueError) as error:
        if destination is not None:
            E.refuse(destination, "extract-enum", error)
        print(f"[collect_php_state] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
