#!/usr/bin/env python3
"""Render one read-only C# enum proposal from accepted Roslyn state evidence."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


def _helper() -> Any:
    sys.dont_write_bytecode = True
    candidates = [Path(__file__).with_name("csharp_accepted_evidence.py")]
    candidates.extend(
        parent / "_csharp-semantic" / "csharp_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied C# accepted-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("csharp_extract_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied C# accepted-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _target(validated: dict[str, Any]) -> dict[str, Any]:
    facts, candidate = validated["facts"], validated["candidate"]
    declarations = [
        row
        for row in facts.get("declarations", [])
        if row.get("role") == "source"
        and row.get("kind") == "property"
        and row.get("symbol_id") == candidate.get("symbol_id")
        and row.get("signature") == candidate.get("signature")
        and row.get("path") == candidate.get("path")
        and row.get("line") == candidate.get("line")
    ]
    if len(declarations) != 1:
        raise EVIDENCE.EvidenceError(
            "partial", "authority_ambiguous", "one exact source property declaration is required"
        )
    declaration = declarations[0]
    operations = [
        row
        for row in facts.get("writes", [])
        if row.get("role") == "source"
        and row.get("resolved") is True
        and row.get("target_symbol_id") == candidate.get("symbol_id")
    ]
    if (
        candidate.get("classification") != "review_required_string_state_candidate"
        or candidate.get("human_verdict") != "required"
        or candidate.get("automatic_migration") is not False
        or declaration.get("type") != "string"
        or declaration.get("override") is not False
        or not isinstance(declaration.get("initializer_string_literal"), str)
        or operations != candidate.get("operations")
        or any(
            row.get("operator") != "=" or not isinstance(row.get("string_literal"), str)
            for row in operations
        )
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "unsupported_authority", "selected evidence is not one direct String-state authority"
        )
    literals = candidate.get("literals")
    if (
        not isinstance(literals, list)
        or len(literals) < 2
        or len(literals) != len(set(literals))
        or sorted(
            {
                declaration["initializer_string_literal"],
                *(row["string_literal"] for row in operations),
            }
        )
        != literals
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "domain_ambiguous", "accepted literals must match the exact direct property domain"
        )
    callers = sorted(
        {
            (row["caller"]["symbol_id"], row["caller"]["signature"])
            for row in operations
            if isinstance(row.get("caller"), dict)
            and row["caller"].get("symbol_id")
            and row["caller"].get("signature")
        }
    )
    if not callers:
        raise EVIDENCE.EvidenceError(
            "partial", "caller_evidence_ambiguous", "resolved direct write callers are required"
        )
    return {
        "authority": {
            "symbol_id": declaration["symbol_id"],
            "signature": declaration["signature"],
            "path": declaration["path"],
            "line": declaration["line"],
            "original_type": "string",
            "accessibility": declaration.get("accessibility"),
        },
        "declaration": declaration,
        "writes": operations,
        "resolved_write_callers": [
            {"symbol_id": symbol_id, "signature": signature}
            for symbol_id, signature in callers
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    authority = payload["target"]["authority"]
    enum = payload["proposed_enum"]
    members = "\n".join(
        f"    {row['name']}, // wire value: {row['wire_value']!r}"
        for row in enum["members"]
    )
    callers = "\n".join(
        f"- `{row['signature']}`" for row in payload["target"]["resolved_write_callers"]
    )
    return f"""# C# enum proposal

Status: `review_required`; no project source was changed.

## Exact accepted authority

`{authority['symbol_id']}` / `{authority['signature']}` at
`{authority['path']}:{authority['line']}` is the one reviewer-accepted direct
String-state authority.

```csharp
namespace {enum['namespace']};

public enum {enum['type_name']}
{{
{members}
}}
```

The comments record the accepted serialization strings; an implementation must
preserve them with an explicitly reviewed converter rather than relying on enum
names or numeric values.

Exact resolved direct-write caller contexts:

{callers}

## Stop conditions and non-claims

- The reviewer explicitly accepted the closed domain and exact wire strings.
- External callers, framework registration, reflection/runtime names,
  generated/vendor inputs, partial declarations, dispatch/delegates, conditional
  variants, and binary compatibility were resolved only as recorded in the
  acceptance artifact.
- This read-only proposal does not establish runtime behavior and grants no
  source-mutation authority.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--findings", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, "extract-enum")
        validated = EVIDENCE.validate_state_acceptance(
            root,
            facts_path=args.facts,
            findings_path=args.findings,
            acceptance_path=args.acceptance,
        )
        target = _target(validated)
        payload = {
            "schema_version": "csharp-enum-proposal-v1",
            "language": "csharp",
            "status": "review_required",
            "outcome": "proposal_ready",
            "read_only": True,
            "source_mutations": 0,
            "target": target,
            "proposed_enum": validated["acceptance"]["enum"],
            "boundary_verdicts": validated["acceptance"]["boundary_verdicts"],
            "fact_pack_sha256": validated["facts"]["fact_pack_sha256"],
            "source_manifest_sha256": validated["facts"]["source_manifest_sha256"],
            "source_inventory": validated["facts"]["source_inventory"],
            "native_checks": {
                name: validated["facts"]["commands"][name]
                for name in ("compile", "compile_tests", "test", "smoke")
            },
            "human_authority": validated["acceptance"],
            "upstream": {
                "facts_path": validated["facts_path"].relative_to(root).as_posix(),
                "facts_sha256": EVIDENCE.file_hash(validated["facts_path"]),
                "findings_path": validated["findings_path"].relative_to(root).as_posix(),
                "findings_sha256": EVIDENCE.file_hash(validated["findings_path"]),
                "acceptance_path": validated["acceptance_path"].relative_to(root).as_posix(),
                "acceptance_sha256": EVIDENCE.file_hash(validated["acceptance_path"]),
            },
            "nonclaims": [
                "selected Roslyn writes do not independently prove a closed runtime domain",
                "wire strings do not independently prove serializer or framework compatibility",
                "the proposal grants no source mutation authority",
            ],
        }
        payload["artifact_sha256"] = EVIDENCE.canonical_hash(payload)
        EVIDENCE.replace_bundle(
            output, {"targets.json": payload, "proposal.md": _markdown(payload)}
        )
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "extract-enum")
            payload, report = EVIDENCE.refusal("extract-enum", exc)
            EVIDENCE.replace_bundle(output, {"targets.json": payload, "proposal.md": report})
        except EVIDENCE.EvidenceError:
            pass
        print(f"collect_csharp_state.py: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
