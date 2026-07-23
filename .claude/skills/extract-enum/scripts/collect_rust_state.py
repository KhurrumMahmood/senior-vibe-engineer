#!/usr/bin/env python3
"""Build a read-only Rust enum proposal from one complete detector candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any


NONCLAIMS = [
    "macro expansions",
    "build-script or include! output",
    "unselected cfg or target variants",
    "trait dispatch or generic owners",
    "unsafe or FFI behavior",
    "serialization or wire compatibility",
    "public API compatibility",
]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RustProposalError(ValueError):
    """Invalid, partial, stale, or ambiguous Rust proposal evidence."""


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
        raise RustProposalError(f"{label} must not be a symbolic link: {supplied}")
    resolved = candidate.resolve(strict=False)
    if not _inside(root, resolved):
        raise RustProposalError(f"{label} must stay inside project root: {supplied}")
    return resolved


def _artifact(root: Path, supplied: str, label: str, family: str) -> Path:
    path = _resolve(root, supplied, label)
    allowed = root / "reports" / family
    if path == allowed or not _inside(allowed, path):
        raise RustProposalError(f"{label} must stay beneath reports/{family}/")
    return path


def _load_findings(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RustProposalError(f"cannot read Rust detector findings: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != "rust-implicit-state-v1":
        raise RustProposalError("findings are not rust-implicit-state-v1 evidence")
    if payload.get("language") != "rust" or payload.get("read_only") is not True:
        raise RustProposalError("findings do not carry read-only Rust authority")
    status = payload.get("status")
    if status != "complete":
        raise RustProposalError(
            f"Rust detector evidence is {status or 'invalid'}; complete evidence is required"
        )
    if not isinstance(payload.get("candidates"), list):
        raise RustProposalError("Rust detector candidates are malformed")
    return payload


def _manifest(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    rows = payload.get("source_hashes")
    if not isinstance(rows, list):
        raise RustProposalError("Rust detector source manifest is missing")
    manifest: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RustProposalError("Rust detector source manifest is malformed")
        path, digest, role = row.get("path"), row.get("sha256"), row.get("role")
        if (
            not isinstance(path, str)
            or Path(path).is_absolute()
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
            or not isinstance(role, str)
            or path in manifest
        ):
            raise RustProposalError("Rust detector source manifest is malformed")
        manifest[path] = {"sha256": digest, "role": role}
    return manifest


def _fresh_source(root: Path, relative: str, manifest: dict[str, dict[str, str]]) -> Path:
    if Path(relative).is_absolute() or Path(relative).suffix != ".rs":
        raise RustProposalError("candidate must cite project-relative Rust source")
    record = manifest.get(relative)
    if record is None or record["role"] != "production-module":
        raise RustProposalError(f"candidate source lacks production-module authority: {relative}")
    source = _resolve(root, relative, "candidate source")
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]:
        raise RustProposalError(
            f"candidate source is stale; re-run /find-implicit-state: {relative}"
        )
    return source


def _candidate(payload: dict[str, Any], selector: str | None) -> dict[str, Any] | None:
    candidates = payload["candidates"]
    if not candidates:
        if selector is not None:
            raise RustProposalError(f"selected Rust candidate was not found: {selector}")
        return None
    matches = [
        row
        for row in candidates
        if isinstance(row, dict) and f"{row.get('owner')}.{row.get('name')}" == selector
    ]
    if selector is None and len(candidates) == 1 and isinstance(candidates[0], dict):
        matches = [candidates[0]]
    if len(matches) != 1:
        raise RustProposalError(
            "select exactly one Rust candidate as Owner.field; repeated literals do not prove a closed domain"
        )
    row = matches[0]
    if (
        row.get("classification") != "extract_enum_candidate"
        or row.get("human_verdict") != "required"
        or row.get("type") not in {"String", "std::string::String"}
        or row.get("generic_owner") is not False
        or row.get("boundary") != "candidate only; the domain is not proven closed"
    ):
        raise RustProposalError("selected Rust row is not a bounded review candidate")
    return row


def _pascal(value: str) -> str:
    pieces = re.findall(r"[A-Za-z0-9]+", value)
    if not pieces:
        raise RustProposalError(f"literal cannot become a Rust enum variant: {value!r}")
    result = "".join(piece[:1].upper() + piece[1:] for piece in pieces)
    if result[0].isdigit():
        result = "Value" + result
    return result


def _proposal_data(root: Path, payload: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    manifest = _manifest(payload)
    relative = row.get("file")
    if not isinstance(relative, str):
        raise RustProposalError("candidate declaration file is missing")
    source = _fresh_source(root, relative, manifest)
    lines = source.read_text(encoding="utf-8").splitlines()
    line_number = row.get("line")
    if not isinstance(line_number, int) or not 1 <= line_number <= len(lines):
        raise RustProposalError("candidate declaration line is invalid")
    field = row.get("name")
    owner = row.get("owner")
    if not isinstance(field, str) or not isinstance(owner, str):
        raise RustProposalError("candidate exact field authority is malformed")
    declaration = lines[line_number - 1]
    field_match = re.search(
        rf"^\s*(?P<visibility>pub(?:\([^)]*\))?\s+)?{re.escape(field)}\s*:\s*(?:String|std::string::String)\s*,?\s*$",
        declaration,
    )
    if field_match is None:
        raise RustProposalError("candidate declaration no longer matches the exact String field")
    owner_line = row.get("owner_line")
    if not isinstance(owner_line, int) or not 1 <= owner_line <= len(lines):
        raise RustProposalError("candidate owner line is invalid")
    owner_match = re.search(
        rf"^\s*(?P<visibility>pub(?:\([^)]*\))?\s+)?struct\s+{re.escape(owner)}\b",
        lines[owner_line - 1],
    )
    if owner_match is None:
        raise RustProposalError("candidate owner declaration is stale")
    operations = row.get("operations")
    literals = row.get("literals")
    if (
        not isinstance(operations, list)
        or len(operations) < 2
        or not isinstance(literals, list)
        or len(literals) < 2
        or not all(isinstance(value, str) and value for value in literals)
    ):
        raise RustProposalError("candidate lacks repeated literal operations")
    for operation in operations:
        if not isinstance(operation, dict) or not isinstance(operation.get("file"), str):
            raise RustProposalError("candidate caller evidence is malformed")
        operation_source = _fresh_source(root, operation["file"], manifest)
        operation_lines = operation_source.read_text(encoding="utf-8").splitlines()
        operation_line = operation.get("line")
        if not isinstance(operation_line, int) or not 1 <= operation_line <= len(operation_lines):
            raise RustProposalError("candidate caller line is invalid")
        if operation.get("syntax") != operation_lines[operation_line - 1].strip()[:180]:
            raise RustProposalError("candidate caller syntax is stale; re-run /find-implicit-state")
    variants = [{"name": _pascal(value), "wire_value": value} for value in sorted(set(literals))]
    if len({item["name"] for item in variants}) != len(variants):
        raise RustProposalError("proposed Rust enum variants collide after normalization")
    type_name = owner + field[:1].upper() + field[1:]
    authority = {
        "target": payload.get("target"),
        "owner": owner,
        "field": field,
        "field_type": row["type"],
        "declaration_file": relative,
        "declaration_line": line_number,
        "source_sha256": manifest[relative]["sha256"],
        "owner_visibility": "public"
        if owner_match.group("visibility") == "pub "
        else (owner_match.group("visibility") or "private").strip(),
        "visibility": "public"
        if field_match.group("visibility") == "pub "
        else (field_match.group("visibility") or "private").strip(),
    }
    return {
        "schema_version": "rust-enum-proposal-v1",
        "language": "rust",
        "status": "review_required",
        "outcome": "proposal_ready",
        "read_only": True,
        "source_preserved": True,
        "detector": payload.get("analyzer"),
        "fact_pack_sha256": payload.get("fact_pack_sha256"),
        "authority": authority,
        "operations": operations,
        "proposed_enum": {"type_name": type_name, "variants": variants},
        "nonclaims": NONCLAIMS,
        "next_step": "A human must accept a separate rust-enum-review-v1 artifact before guard staging.",
    }


def _proposal_markdown(data: dict[str, Any]) -> str:
    authority = data["authority"]
    proposed = data["proposed_enum"]
    match_arms = "\n".join(
        f'            Self::{row["name"]} => "{row["wire_value"]}",' for row in proposed["variants"]
    )
    variants = "\n".join(f'    {row["name"]},' for row in proposed["variants"])
    callers = "\n".join(
        f'- `{row["file"]}:{row["line"]}` — `{row["syntax"]}`' for row in data["operations"]
    )
    limits = "\n".join(f"- {item}" for item in NONCLAIMS)
    return f"""# Proposal — extract-enum: {authority['owner']}.{authority['field']}

Status: `review_required`

This proposal is read-only and does not edit Rust source. Repeated literals are
candidate evidence only; they do not establish that the domain is closed.

## Proposed bounded type

```rust
pub enum {proposed['type_name']} {{
{variants}
}}

impl {proposed['type_name']} {{
    pub const fn as_str(self) -> &'static str {{
        match self {{
{match_arms}
        }}
    }}
}}
```

## Exact caller inventory

{callers}

## Human review gate

Confirm domain closure, variant names, persisted/wire values, crate/module
placement, migration order, and every external boundary. Record acceptance in
a separate `rust-enum-review-v1` artifact; this collector never applies edits.

## Explicit non-claims

{limits}
"""


def _atomic_bundle(bundle: Path, files: dict[str, str]) -> None:
    bundle.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{bundle.name}.", dir=bundle.parent))
    try:
        for name, text in files.items():
            destination = temporary / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")
        temporary.replace(bundle)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--candidate")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--proposal", required=True)
    args = parser.parse_args(argv)
    bundle: Path | None = None
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or root.is_symlink():
            raise RustProposalError("project root must be a non-symlink directory")
        findings = _artifact(root, args.findings, "findings", "implicit-state")
        output = _artifact(root, args.output, "output", "extract-enum")
        proposal = _artifact(root, args.proposal, "proposal", "extract-enum")
        if (
            output.name != "targets.json"
            or proposal.name != "proposal.md"
            or output.parent != proposal.parent
        ):
            raise RustProposalError(
                "output and proposal must be sibling targets.json/proposal.md artifacts"
            )
        bundle = output.parent
        shutil.rmtree(bundle, ignore_errors=True)
        payload = _load_findings(findings)
        row = _candidate(payload, args.candidate)
        if row is None:
            clean = {
                "schema_version": "rust-enum-proposal-v1",
                "language": "rust",
                "status": "complete",
                "outcome": "clean",
                "read_only": True,
                "nonclaims": NONCLAIMS,
            }
            _atomic_bundle(
                bundle, {"targets.json": json.dumps(clean, indent=2, sort_keys=True) + "\n"}
            )
            print("[collect_rust_state] complete clean: no review candidate", file=sys.stderr)
            return 0
        data = _proposal_data(root, payload, row)
        relevant = {
            data["authority"]["declaration_file"],
            *(item["file"] for item in data["operations"]),
        }
        before = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in relevant}
        _atomic_bundle(
            bundle,
            {
                "targets.json": json.dumps(data, indent=2, sort_keys=True) + "\n",
                "proposal.md": _proposal_markdown(data),
            },
        )
        after = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in relevant}
        if before != after:
            shutil.rmtree(bundle, ignore_errors=True)
            raise RustProposalError("source changed while writing the read-only proposal")
    except (RustProposalError, OSError, UnicodeError, KeyError, TypeError) as error:
        if bundle is not None:
            shutil.rmtree(bundle, ignore_errors=True)
        print(f"[collect_rust_state] ERROR: {error}", file=sys.stderr)
        return 2
    print(
        f"[collect_rust_state] review required for {data['authority']['owner']}.{data['authority']['field']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
