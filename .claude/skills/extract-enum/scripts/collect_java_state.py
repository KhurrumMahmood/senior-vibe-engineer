#!/usr/bin/env python3
"""Build a review-only Java enum migration proposal from one accepted finding."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


class JavaEnumProposalError(ValueError):
    """Invalid, stale, or non-actionable Java detector evidence."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = raw if raw.is_absolute() else root / raw
    if candidate.is_symlink():
        raise JavaEnumProposalError(f"{label} must not be a symbolic link: {supplied}")
    candidate = candidate.resolve()
    if not _inside(root, candidate):
        raise JavaEnumProposalError(f"{label} must stay inside project root: {supplied}")
    return candidate


def _artifact(root: Path, supplied: str, label: str, directory: str) -> Path:
    path = _resolve(root, supplied, label)
    allowed = root / "reports" / directory
    if path == allowed or not _inside(allowed, path):
        raise JavaEnumProposalError(f"{label} must stay beneath reports/{directory}/")
    return path


def _read_findings(root: Path, supplied: str) -> tuple[Path, dict[str, Any]]:
    path = _artifact(root, supplied, "findings", "implicit-state")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise JavaEnumProposalError(f"cannot read Java detector findings: {error}") from error
    if not isinstance(payload, dict) or payload.get("language") != "java":
        raise JavaEnumProposalError("findings are not a Java implicit-state artifact")
    if payload.get("status") != "complete" or payload.get("analysis", {}).get("status") != "complete":
        raise JavaEnumProposalError("Java detector evidence is partial; resolve it before proposing an enum")
    if not isinstance(payload.get("findings"), list):
        raise JavaEnumProposalError("Java detector findings are malformed")
    return path, payload


def _accepted(payload: dict[str, Any], finding_id: str) -> dict[str, Any]:
    matches = [item for item in payload["findings"] if isinstance(item, dict) and item.get("finding_id") == finding_id]
    if len(matches) != 1:
        raise JavaEnumProposalError(f"accepted Java finding not found: {finding_id}")
    finding = matches[0]
    if finding.get("status") != "accepted" or finding.get("bucket") != "extract_enum_candidate":
        raise JavaEnumProposalError(
            f"finding {finding_id} is not an accepted enum candidate: "
            f"status={finding.get('status')!r} bucket={finding.get('bucket')!r}"
        )
    return finding


def _authority(root: Path, finding: dict[str, Any]) -> dict[str, Any]:
    authority = finding.get("authority")
    required = (
        "language", "kind", "qualified_owner", "package_name", "field", "field_type",
        "declaration_file", "declaration_line", "source_sha256",
    )
    if not isinstance(authority, dict) or any(not authority.get(key) for key in required):
        raise JavaEnumProposalError("accepted finding omits exact Java field authority")
    if authority["language"] != "java" or authority["kind"] != "direct_string_field" or authority["field_type"] != "java.lang.String":
        raise JavaEnumProposalError("accepted finding is not a direct java.lang.String field")
    source = _resolve(root, str(authority["declaration_file"]), "authority source")
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != authority["source_sha256"]:
        raise JavaEnumProposalError("accepted Java field authority is stale; re-run /find-implicit-state")
    return authority


def _member(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    if not name:
        name = "VALUE"
    if name[0].isdigit():
        name = "VALUE_" + name
    return name


def _literal_rows(finding: dict[str, Any]) -> list[dict[str, Any]]:
    callsites = finding.get("callsites")
    if not isinstance(callsites, list) or len(callsites) < 3:
        raise JavaEnumProposalError("accepted finding lacks repeated direct callsite evidence")
    values = [item.get("literal") for item in callsites if isinstance(item, dict)]
    if not all(isinstance(value, str) for value in values):
        raise JavaEnumProposalError("accepted finding has malformed literal evidence")
    counts = Counter(values)
    if len(counts) < 2:
        raise JavaEnumProposalError("accepted finding lacks distinct literal evidence")
    rows = [{"value": value, "count": counts[value], "enum_member": _member(value)} for value in sorted(counts)]
    names = [item["enum_member"] for item in rows]
    if len(names) != len(set(names)):
        raise JavaEnumProposalError("literals collapse to one Java enum member name; choose reviewed names manually")
    return rows


def _matching_unsafe(payload: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for finding in payload["findings"]:
        if not isinstance(finding, dict) or finding.get("bucket") != "unsafe_string_comparison":
            continue
        candidate = finding.get("authority")
        if isinstance(candidate, dict) and all(candidate.get(key) == authority.get(key) for key in ("qualified_owner", "field", "source_sha256")):
            output.append(finding)
    return output


def _vendor_boundaries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    operations = payload.get("boundaries", {}).get("operations", [])
    if not isinstance(operations, list):
        return []
    return [
        {key: item[key] for key in ("file", "line", "field_owner", "field", "literal")}
        for item in operations
        if isinstance(item, dict) and item.get("classification") == "vendor_wire_boundary"
    ]


def _render(data: dict[str, Any]) -> str:
    authority = data["accepted_authority"]
    enum_rows = ",\n".join(
        f'    {item["enum_member"]}({json.dumps(item["value"])})'
        for item in data["literals"]
    )
    callers = "\n".join(
        f'| `{item["file"]}:{item["line"]}` | `{item["operation"]}` | `{item["literal"]}` | `{data["proposed_enum"]}.{next(row["enum_member"] for row in data["literals"] if row["value"] == item["literal"])}` |'
        for item in data["callsites"]
    )
    unsafe = data["unsafe_string_comparisons"]
    unsafe_text = "\n".join(
        f'- `{item["finding_id"]}` has {item["hit_count"]} reference-equality call(s); repair it independently with value equality.'
        for item in unsafe
    ) or "- None on this exact authority. `==` elsewhere was not used as enum evidence."
    vendors = "\n".join(
        f'- `{item["field_owner"]}.{item["field"]}` at `{item["file"]}:{item["line"]}` keeps wire literal `{item["literal"]}` until ownership is reviewed.'
        for item in data["vendor_boundary_candidates"]
    ) or "- None observed by the bounded detector."
    return f'''# Proposal — Java enum migration: {authority['qualified_owner']}.{authority['field']}

## Accepted detector authority

This proposal consumes exactly `{data['detector_finding_id']}` from a complete
Java `find-implicit-state` artifact. The compiler resolved the direct
`java.lang.String` field `{authority['qualified_owner']}.{authority['field']}`
at `{authority['declaration_file']}:{authority['declaration_line']}`. Its
source fingerprint is `{authority['source_sha256']}`. This skill did not
re-detect or edit source.

## Proposed symbolic authority

```java
package {authority['package_name']};

public enum {data['proposed_enum']} {{
{enum_rows};

    private final String serializedValue;

    {data['proposed_enum']}(String serializedValue) {{
        this.serializedValue = serializedValue;
    }}

    public String serializedValue() {{
        return serializedValue;
    }}
}}
```

Keep the serialized strings unchanged unless a human explicitly approves an
API or persistence migration.

## Exact migration and impact plan

1. Change only `{authority['qualified_owner']}.{authority['field']}` from
   `String` to `{data['proposed_enum']}` after reviewing persistence,
   reflection, JSON, ORM, and public API conversion points.
2. Replace the listed direct bare-string callers with the named enum member.
   Java enum `==` is valid only after that field is actually an enum.
3. Add an explicit wire adapter at confirmed external boundaries; do not add a
   vendor literal as an enum member merely because its text happens to match.
4. After human approval and mutation, stage the exact-authority guard through
   `/prevent-regression`; it must consume this target artifact rather than
   matching every Java field called `status`.

| Caller | Operation | Current literal | Proposed member |
|---|---|---|---|
{callers}

## Unsafe String reference equality

{unsafe_text}

## Vendor-boundary review

{vendors}

## Native verification and stop condition

After a human applies the migration, compile the host with its native JDK 17
toolchain, for example:

```bash
javac --release 17 -proc:none -d out $(find src -name '*.java')
```

Stop and return to review if the field is not intentionally finite, literals
are computed dynamically, serialization must remain raw at a public boundary,
or an enum name/value collision needs a domain decision. This is a review-only
proposal: it creates no Java source, migration, guard installation, or host
configuration change.

## Authorization

Human approval is required before source mutation. Keep this `targets.json`
with the review record so `/prevent-regression` can copy the exact accepted
field authority into a staged guard.
'''


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}.") as stream:
        stream.write(text)
        temporary = Path(stream.name)
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finding", required=True)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--proposal", required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or root.is_symlink():
            raise JavaEnumProposalError(f"project root is not a directory: {args.project_root}")
        findings_path, payload = _read_findings(root, args.findings)
        finding = _accepted(payload, args.finding)
        authority = _authority(root, finding)
        literals = _literal_rows(finding)
        callsites = finding["callsites"]
        output = _artifact(root, args.output, "targets artifact", "extract-enum")
        proposal = _artifact(root, args.proposal, "proposal artifact", "extract-enum")
        if output == proposal:
            raise JavaEnumProposalError("targets and proposal paths must be distinct")
        owner = authority["qualified_owner"].rsplit(".", 1)[-1]
        proposed_enum = owner + authority["field"][:1].upper() + authority["field"][1:]
        data = {
            "schema_version": 1,
            "language": "java",
            "status": "review_required",
            "detector_finding_id": finding["finding_id"],
            "detector_findings_sha256": hashlib.sha256(findings_path.read_bytes()).hexdigest(),
            "evidence_provenance": "complete JDK compiler-tree/type accepted field authority",
            "accepted_authority": authority,
            "current_type": "java.lang.String",
            "proposed_enum": proposed_enum,
            "literals": literals,
            "callsites": [
                {key: item[key] for key in ("file", "line", "column", "operation", "literal", "evidence")}
                for item in callsites
            ],
            "unsafe_string_comparisons": _matching_unsafe(payload, authority),
            "vendor_boundary_candidates": _vendor_boundaries(payload),
            "stop_condition": "A human cannot establish an intentionally finite domain with explicit conversion boundaries.",
        }
        _atomic_write(output, json.dumps(data, indent=2, sort_keys=True) + "\n")
        _atomic_write(proposal, _render(data))
    except (JavaEnumProposalError, OSError, KeyError, TypeError) as error:
        print(f"[collect_java_state] ERROR: {error}", file=sys.stderr)
        return 2
    print(
        f"[collect_java_state] finding={data['detector_finding_id']} callers={len(data['callsites'])} "
        f"literals={len(data['literals'])} review_required",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
