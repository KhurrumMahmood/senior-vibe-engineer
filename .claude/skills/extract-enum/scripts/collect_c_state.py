#!/usr/bin/env python3
"""Render one review-required C enum proposal from accepted state evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "c-enum-proposal-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
APPROVAL_GATES = {
    "abi": "human_approval_required",
    "external": "human_approval_required",
    "storage": "human_approval_required",
    "wire": "human_approval_required",
}
NONCLAIMS = [
    "three direct literal assignments prove a closed state domain",
    "pointer aliases, callbacks, macros, inactive variants, or external consumers are complete",
    "the proposed enum preserves ABI or record layout",
    "wire, storage, serialization, or public API compatibility is established",
    "this proposal authorizes source mutation",
]


class CProposalError(ValueError):
    """Invalid, incomplete, stale, or ambiguous accepted C evidence."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind


def _hash_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_path(root: Path, supplied: str | Path, label: str) -> Path:
    raw = Path(supplied)
    candidate = raw if raw.is_absolute() else root / raw
    absolute = Path(os.path.abspath(candidate))
    if not _inside(root, absolute):
        raise CProposalError("unsafe_path", f"{label} must stay inside project root")
    current = root
    for part in absolute.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise CProposalError("unsafe_path", f"{label} must not traverse a symbolic link")
    return absolute


def _artifact(root: Path, supplied: str | Path, label: str, family: str) -> Path:
    path = _safe_path(root, supplied, label)
    allowed = root / "reports" / family
    if path == allowed or not _inside(allowed, path):
        raise CProposalError("unsafe_path", f"{label} must stay beneath reports/{family}/")
    return path


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CProposalError("evidence_invalid", f"cannot read {label}: {error}") from error
    if not isinstance(payload, dict):
        raise CProposalError("evidence_invalid", f"{label} must be a JSON object")
    return payload


def _source_rows(root: Path, facts: dict[str, Any]) -> dict[str, str]:
    rows = facts.get("source_files")
    if not isinstance(rows, list) or not rows:
        raise CProposalError("evidence_invalid", "C fact pack source manifest is missing")
    manifest: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise CProposalError("evidence_invalid", "C fact pack source manifest is malformed")
        relative, digest = row.get("path"), row.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(digest, str)
            or relative in manifest
        ):
            raise CProposalError("evidence_invalid", "C fact pack source manifest is malformed")
        path = root / relative
        if digest.startswith("symlink:"):
            current = f"symlink:{os.readlink(path)}" if path.is_symlink() else None
        else:
            if SHA256_RE.fullmatch(digest) is None:
                raise CProposalError("evidence_invalid", "C fact pack source hash is malformed")
            current = _sha256(path) if path.is_file() and not path.is_symlink() else None
        if current != digest:
            raise CProposalError(
                "evidence_stale",
                f"accepted C fact pack is stale at {relative}; re-run /find-implicit-state",
            )
        manifest[relative] = digest
    if facts.get("source_manifest_sha256") != _hash_json(rows):
        raise CProposalError("evidence_tampered", "C fact pack source manifest hash does not verify")
    return manifest


def _facts(root: Path, path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    payload = _load_json(path, "C semantic fact pack")
    database = payload.get("compile_database")
    preservation = payload.get("source_preservation")
    if (
        payload.get("schema_version") != "c-semantic-facts-v1"
        or payload.get("language") != "c"
        or payload.get("read_only") is not True
        or payload.get("status") != "complete"
        or not isinstance(database, dict)
        or database.get("state") != "valid-current-complete-c17"
        or not isinstance(preservation, dict)
        or preservation.get("unchanged") is not True
    ):
        raise CProposalError(
            "evidence_incomplete", "complete source-preserving C17 semantic facts are required"
        )
    claimed = payload.get("fact_pack_sha256")
    unhashed = dict(payload)
    unhashed.pop("fact_pack_sha256", None)
    if not isinstance(claimed, str) or claimed != _hash_json(unhashed):
        raise CProposalError("evidence_tampered", "C semantic fact-pack hash does not verify")
    manifest = _source_rows(root, payload)
    database_path = _safe_path(root, database.get("path", ""), "compile database")
    if (
        database_path.name != "compile_commands.json"
        or not database_path.is_file()
        or database_path.is_symlink()
        or _sha256(database_path) != database.get("sha256")
    ):
        raise CProposalError("evidence_stale", "accepted C compile database is stale")
    current_inputs = [root / "Makefile"]
    current_inputs.extend(root / item for item in database.get("translation_units", []))
    closure = payload.get("dependency_closure")
    if not isinstance(closure, dict):
        raise CProposalError("evidence_invalid", "C dependency closure is malformed")
    for dependencies in closure.values():
        if isinstance(dependencies, list):
            current_inputs.extend(root / item for item in dependencies)
    newest_input = max(
        (item.stat().st_mtime_ns for item in current_inputs if item.is_file()), default=0
    )
    if database_path.stat().st_mtime_ns < newest_input:
        raise CProposalError("evidence_stale", "accepted C compile database predates its inputs")
    return payload, manifest


def _findings(path: Path, facts: dict[str, Any]) -> dict[str, Any]:
    payload = _load_json(path, "C implicit-state findings")
    if (
        payload.get("schema_version") != "c-implicit-state-v1"
        or payload.get("language") != "c"
        or payload.get("read_only") is not True
        or payload.get("status") != "complete"
    ):
        raise CProposalError(
            "evidence_incomplete", "complete read-only C implicit-state findings are required"
        )
    if payload.get("fact_pack_sha256") != facts.get("fact_pack_sha256"):
        raise CProposalError(
            "evidence_tampered", "C implicit-state findings do not bind to the supplied fact pack"
        )
    if not isinstance(payload.get("candidates"), list):
        raise CProposalError("evidence_invalid", "C implicit-state candidate list is malformed")
    return payload


def _candidate(payload: dict[str, Any], selector: str) -> dict[str, Any]:
    matches = [
        row
        for row in payload["candidates"]
        if isinstance(row, dict) and f"{row.get('owner')}.{row.get('field')}" == selector
    ]
    if len(matches) != 1:
        raise CProposalError(
            "selection_invalid", "select exactly one accepted C candidate as owner.field"
        )
    row = matches[0]
    literals = row.get("literals")
    operations = row.get("operations")
    if (
        row.get("classification") != "enum_review_only"
        or row.get("human_verdict") != "required"
        or row.get("automatic_migration") is not False
        or row.get("type") != "const char *"
        or not isinstance(literals, list)
        or len(literals) < 3
        or not all(isinstance(value, str) and value for value in literals)
        or len(literals) != len(set(literals))
        or not isinstance(operations, list)
        or len(operations) < 3
    ):
        raise CProposalError("selection_invalid", "selected C row is not a bounded enum review lead")
    if sorted(literals) != literals:
        raise CProposalError("selection_invalid", "accepted C literals must be deterministic")
    return row


def _fact_match(row: dict[str, Any], candidates: list[Any], keys: tuple[str, ...]) -> bool:
    return any(
        isinstance(candidate, dict)
        and all(candidate.get(key) == row.get(key) for key in keys)
        for candidate in candidates
    )


def _authority(
    row: dict[str, Any], facts: dict[str, Any], manifest: dict[str, str]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    owner, field = row.get("owner"), row.get("field")
    declaration_file, declaration_line = row.get("file"), row.get("line")
    if (
        not all(isinstance(value, str) and value for value in (owner, field, declaration_file))
        or not isinstance(declaration_line, int)
        or declaration_file not in manifest
    ):
        raise CProposalError("selection_invalid", "selected C field authority is malformed")
    declarations = facts.get("declarations")
    if not isinstance(declarations, list) or not any(
        isinstance(item, dict)
        and item.get("kind") == "field"
        and item.get("owner") == owner
        and item.get("name") == field
        and item.get("file") == declaration_file
        and item.get("line") == declaration_line
        and item.get("type") == "const char *"
        and item.get("macro_expansion") is False
        for item in declarations
    ):
        raise CProposalError("evidence_tampered", "selected field is absent from accepted Clang facts")
    fact_operations = facts.get("state_operations")
    if not isinstance(fact_operations, list):
        raise CProposalError("evidence_invalid", "accepted C state operations are malformed")
    callers = []
    cited = {declaration_file}
    literals = set()
    keys = ("file", "line", "function", "field", "literal", "operation", "macro_expansion")
    for operation in row["operations"]:
        if (
            not isinstance(operation, dict)
            or operation.get("field") != field
            or operation.get("operation") != "direct_assignment"
            or operation.get("macro_expansion") is not False
            or not isinstance(operation.get("file"), str)
            or operation["file"] not in manifest
            or not isinstance(operation.get("line"), int)
            or not isinstance(operation.get("function"), str)
            or not isinstance(operation.get("literal"), str)
            or not _fact_match(operation, fact_operations, keys)
        ):
            raise CProposalError(
                "evidence_tampered", "candidate caller is absent from accepted Clang facts"
            )
        cited.add(operation["file"])
        literals.add(operation["literal"])
        callers.append(
            {
                key: operation[key]
                for key in ("file", "line", "function", "operation", "literal")
            }
        )
    if literals != set(row["literals"]):
        raise CProposalError("evidence_tampered", "candidate literal and caller inventories differ")
    inventory = {
        item.get("path"): item
        for item in facts.get("source_inventory", [])
        if isinstance(item, dict)
    }
    if any(
        inventory.get(relative, {}).get("role") != "production"
        or inventory.get(relative, {}).get("included") is not True
        for relative in cited
    ):
        raise CProposalError("selection_invalid", "candidate cites non-production C evidence")
    authority = {
        "owner": owner,
        "field": field,
        "type": "const char *",
        "declaration_file": declaration_file,
        "declaration_line": declaration_line,
    }
    return authority, callers, {relative: manifest[relative] for relative in sorted(cited)}


def _identifier(value: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    if not identifier:
        raise CProposalError("selection_invalid", f"cannot derive a C identifier from {value!r}")
    if identifier[0].isdigit():
        identifier = "value_" + identifier
    return identifier


def _proposal_data(
    findings_path: Path,
    facts_path: Path,
    findings: dict[str, Any],
    facts: dict[str, Any],
    row: dict[str, Any],
    authority: dict[str, Any],
    callers: list[dict[str, Any]],
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    enum_name = _identifier(f"{authority['owner']}_{authority['field']}").lower()
    prefix = enum_name.upper()
    enumerators = [
        {
            "name": f"{prefix}_{_identifier(value).upper()}",
            "wire_value": value,
        }
        for value in row["literals"]
    ]
    if len({item["name"] for item in enumerators}) != len(enumerators):
        raise CProposalError("selection_invalid", "C literals collapse to duplicate enumerators")
    return {
        "schema_version": SCHEMA,
        "language": "c",
        "status": "review_required",
        "outcome": "proposal_ready",
        "read_only": True,
        "source_mutations": 0,
        "detector_artifact_sha256": _sha256(findings_path),
        "fact_artifact_sha256": _sha256(facts_path),
        "fact_pack_sha256": facts["fact_pack_sha256"],
        "source_manifest_sha256": facts["source_manifest_sha256"],
        "authority": authority,
        "current_source_hashes": source_hashes,
        "callers": callers,
        "proposed_enum": {
            "name": enum_name,
            "underlying_type": "implementation-defined C enum compatible type",
            "enumerators": enumerators,
        },
        "approval_gates": APPROVAL_GATES,
        "human_authority": (
            "A human must approve ABI/layout, wire, storage, and external-consumer impact "
            "before source mutation or guard staging."
        ),
        "nonclaims": NONCLAIMS,
    }


def _markdown(data: dict[str, Any]) -> str:
    authority = data["authority"]
    enum = data["proposed_enum"]
    members = ",\n".join(f"    {row['name']}" for row in enum["enumerators"])
    callers = "\n".join(
        f"| `{row['file']}:{row['line']}` | `{row['function']}` | "
        f"`{row['literal']}` | `{next(item['name'] for item in enum['enumerators'] if item['wire_value'] == row['literal'])}` |"
        for row in data["callers"]
    )
    hashes = "\n".join(
        f"- `{path}` — `{digest}`" for path, digest in data["current_source_hashes"].items()
    )
    nonclaims = "\n".join(f"- {item}" for item in NONCLAIMS)
    return f"""# C enum extraction proposal — {authority['owner']}.{authority['field']}

Status: `review_required`. This artifact consumes accepted Clang/C17 evidence
and edits no C source.

## Exact accepted authority

`{authority['owner']}.{authority['field']}` is currently
`{authority['type']}` at
`{authority['declaration_file']}:{authority['declaration_line']}`.

```c
typedef enum {enum['name']} {{
{members}
}} {enum['name']};
```

Observed strings remain explicit wire-value candidates; the C enum does not
itself preserve those strings.

## Exact caller migration inventory

| Source | Function | Current literal | Proposed enumerator |
|---|---|---|---|
{callers}

## Current evidence hashes

{hashes}

## Human approval gates

- **ABI:** approve record layout, compatible type, calling convention, and
  public-header impact.
- **wire:** approve explicit enum-to-string parsing and serialization.
- **storage:** approve persisted-value and migration compatibility.
- **external:** approve unobserved consumers, callbacks, aliases, and build
  variants.

All four gates remain `human_approval_required`. Stop rather than mutate if
any gate is unresolved or the domain is not intentionally finite. After a
separate approved migration, `/prevent-regression` may stage an exact-field
compile-time guard; this proposal neither applies nor installs one.

## Explicit non-claims

{nonclaims}
"""


def _replace_bundle(destination: Path, files: dict[str, str]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        for relative, text in files.items():
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        shutil.rmtree(destination, ignore_errors=True)
        temporary.replace(destination)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--facts", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or Path(args.project_root).is_symlink():
            raise CProposalError("unsafe_path", "project root must be a non-symlink directory")
        output = _artifact(root, args.output_dir, "output directory", "extract-enum")
        shutil.rmtree(output, ignore_errors=True)
        facts_path = _artifact(root, args.facts, "facts", "c-semantic")
        findings_path = _artifact(root, args.findings, "findings", "implicit-state")
        facts, manifest = _facts(root, facts_path)
        findings = _findings(findings_path, facts)
        row = _candidate(findings, args.candidate)
        authority, callers, current_hashes = _authority(row, facts, manifest)
        data = _proposal_data(
            findings_path,
            facts_path,
            findings,
            facts,
            row,
            authority,
            callers,
            current_hashes,
        )
        _replace_bundle(
            output,
            {
                "targets.json": json.dumps(data, indent=2, sort_keys=True) + "\n",
                "proposal.md": _markdown(data),
            },
        )
    except (CProposalError, OSError, UnicodeError, KeyError, TypeError) as error:
        kind = error.kind if isinstance(error, CProposalError) else "proposal_failed"
        if output is not None:
            _replace_bundle(
                output,
                {
                    "refusal.json": json.dumps(
                        {
                            "schema_version": "c-enum-proposal-refusal-v1",
                            "language": "c",
                            "status": "refused",
                            "outcome": "no_proposal",
                            "failure_kind": kind,
                            "message": str(error),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                },
            )
        print(f"[collect_c_state] ERROR: {kind}: {error}", file=sys.stderr)
        return 2
    print(
        f"[collect_c_state] review_required {authority['owner']}.{authority['field']} "
        f"callers={len(callers)} literals={len(row['literals'])}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
