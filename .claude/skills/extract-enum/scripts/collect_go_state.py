#!/usr/bin/env python3
"""Build a review-only Go typed-constant proposal from detector JSONL."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import sys
from pathlib import Path
from typing import Any


class ProposalError(ValueError):
    """Invalid or unsupported Go state evidence."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _artifact(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    path = (raw if raw.is_absolute() else root / raw).resolve()
    allowed = root / "reports" / "extract-enum"
    if path == allowed or not _inside(allowed, path):
        raise ProposalError(f"{label} must stay beneath reports/extract-enum/")
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ProposalError(f"cannot read detector findings: {error}") from error
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ProposalError(f"invalid detector JSON on line {number}: {error}") from error
        if not isinstance(record, dict):
            raise ProposalError(f"invalid detector record on line {number}")
        records.append(record)
    return records


def _exported_piece(value: str) -> str:
    pieces = [piece for piece in re.split(r"[^A-Za-z0-9]+", value) if piece]
    rendered = "".join(piece[:1].upper() + piece[1:] for piece in pieces)
    if not rendered:
        raise ProposalError(f"cannot derive a Go identifier from literal {value!r}")
    if rendered[0].isdigit():
        rendered = "Value" + rendered
    return rendered


def _render(data: dict[str, Any]) -> str:
    declarations = "\n".join(
        f'\t{data["proposed_type"]}{_exported_piece(item["value"])} '
        f'{data["proposed_type"]} = {json.dumps(item["value"])}'
        for item in data["literals"]
    )
    callers = "\n".join(
        f'| `{item["file"]}:{item["line"]}` | {item["operation"]} | `{item["literal"]}` |'
        for item in data["callsites"]
    )
    boundaries = "\n".join(
        f"- `{path}`" for path in data["vendor_boundary_candidates"]
    ) or "- None observed."
    return f"""# Proposal — Go typed state: {data['proposed_type']}

## Evidence boundary

This is a review candidate, not proof that the domain is closed. Go's type
system proves the receiver is `{data['carrier_type']}.{data['field']}` and the
field is currently `string`; repeated literals only suggest a finite domain.
Confirm the business invariant before applying this proposal.

## Proposed authority

```go
type {data['proposed_type']} string

const (
{declarations}
)
```

Change `{data['carrier_type']}.{data['field']}` to `{data['proposed_type']}` and
replace only the resolved callers below with constants. Keep serialization
values unchanged.

| Caller | Operation | Bare literal |
| --- | --- | --- |
{callers}

## Possible vendor boundaries

{boundaries}

These are candidates inferred from carrier naming only. Confirm actual
third-party/protocol ownership. Preserve confirmed wire-format literals; treat
first-party `Request`/`Response`/`Payload` names as ordinary code instead.

## Verification and stop condition

Run `gofmt` and the host's native `go test ./...`. Stop if additional valid
states are computed dynamically, external callers require raw strings, or the
review cannot establish that the domain is intentionally finite.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--proposal", required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or root.is_symlink():
            raise ProposalError(f"project root is not a directory: {args.project_root}")
        raw_findings = Path(args.findings)
        findings = (raw_findings if raw_findings.is_absolute() else root / raw_findings).resolve()
        if not _inside(root, findings):
            raise ProposalError("detector findings must stay inside project root")
        records = _read_jsonl(findings)
        statuses = [record for record in records if record.get("record_kind") == "analysis_status"]
        if len(statuses) != 1 or statuses[0].get("status") != "complete":
            state = statuses[0].get("status") if len(statuses) == 1 else "missing-or-ambiguous"
            raise ProposalError(f"Go detector evidence is {state}; resolve partial analysis before proposing")
        candidates = [
            record for record in records
            if record.get("record_kind") == "operation"
            and record.get("classification") == "first_party_state_operation"
        ]
        if not candidates:
            raise ProposalError("detector result contains no Go implicit-state review candidate")
        fields = {
            (item.get("package_path"), item.get("carrier_type"), item.get("field"), item.get("field_type"))
            for item in candidates
        }
        if len(fields) != 1:
            raise ProposalError(f"proposal requires exactly one resolved state field; found {sorted(fields)!r}")
        package_path, carrier, field, field_type = next(iter(fields))
        if not all(isinstance(value, str) for value in (package_path, carrier, field)) or field_type != "string":
            raise ProposalError("Go proposal requires one built-in string struct field")
        counts = Counter(str(item["literal"]) for item in candidates)
        member_names = [_exported_piece(value) for value in sorted(counts)]
        if len(member_names) != len(set(member_names)):
            raise ProposalError(
                "distinct state literals collapse to the same Go constant name; "
                "choose reviewed member names manually",
            )
        proposed_type = f"{carrier}{field}"
        data = {
            "schema_version": 1,
            "language": "go",
            "status": "review_required",
            "evidence_provenance": "go/types-resolved receiver plus repeated literal heuristic",
            "carrier_type": carrier,
            "package_path": package_path,
            "field": field,
            "current_type": "string",
            "proposed_type": proposed_type,
            "literals": [{"value": value, "count": counts[value]} for value in sorted(counts)],
            "callsites": [
                {key: item[key] for key in ("file", "line", "operation", "literal")}
                for item in candidates
            ],
            "vendor_boundary_candidates": sorted({
                str(item["file"]) for item in records
                if item.get("classification") == "possible_vendor_boundary"
            }),
            "stop_condition": "A reviewer cannot establish an intentionally finite domain.",
        }
        output = _artifact(root, args.output, "targets artifact")
        proposal = _artifact(root, args.proposal, "proposal artifact")
        output.parent.mkdir(parents=True, exist_ok=True)
        proposal.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{json.dumps(data, indent=2)}\n", encoding="utf-8")
        proposal.write_text(_render(data), encoding="utf-8")
    except (ProposalError, OSError) as error:
        print(f"[collect_go_state] ERROR: {error}", file=sys.stderr)
        return 2
    print(
        f"[collect_go_state] {len(candidates)} callers, {len(data['literals'])} literals, review_required",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
