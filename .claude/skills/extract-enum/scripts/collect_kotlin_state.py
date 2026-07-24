#!/usr/bin/env python3
"""Render one read-only Kotlin enum proposal from accepted state evidence."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any


def _helper() -> Any:
    candidates = [Path(__file__).with_name("kotlin_accepted_evidence.py")]
    candidates.extend(
        parent / "_kotlin-semantic" / "kotlin_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied Kotlin accepted-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("kotlin_extract_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Kotlin accepted-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _variant(value: str) -> str:
    rendered = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    if not rendered or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", rendered):
        raise EVIDENCE.EvidenceError(
            "partial", "unsupported_literal", f"literal cannot become an exact enum variant: {value!r}"
        )
    return rendered


def _target(validated: dict[str, Any]) -> dict[str, Any]:
    facts, candidate = validated["facts"], validated["candidate"]
    fq_name = candidate.get("fq_name")
    declarations = [
        row
        for row in facts.get("declarations", [])
        if row.get("fq_name") == fq_name
        and row.get("kind") == "property"
        and row.get("role") == "source"
    ]
    if len(declarations) != 1:
        raise EVIDENCE.EvidenceError(
            "partial", "authority_ambiguous", "one exact direct Kotlin property declaration is required"
        )
    declaration = declarations[0]
    if (
        candidate.get("classification") != "review_required_string_state_candidate"
        or candidate.get("human_verdict") != "required"
        or declaration.get("type_text") != "String"
        or declaration.get("override")
        or declaration.get("extension_receiver") is not None
        or not isinstance(declaration.get("initializer"), str)
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "unsupported_authority", "selected property is not a direct String-state authority"
        )
    signature = declaration.get("signature")
    writes = [
        row
        for row in facts.get("writes", [])
        if row.get("target_signature") == signature and row.get("resolved")
    ]
    if writes != candidate.get("operations") or any(
        row.get("operator") != "=" or not isinstance(row.get("string_literal"), str)
        for row in writes
    ):
        raise EVIDENCE.EvidenceError(
            "partial", "write_evidence_ambiguous", "accepted candidate must match exact direct literal writes"
        )
    references = [
        row
        for row in facts.get("references", [])
        if row.get("target_signature") == signature and row.get("resolved")
    ]
    owner_fq_name, separator, property_name = str(fq_name).rpartition(".")
    package_name, owner_separator, owner_name = owner_fq_name.rpartition(".")
    if not separator or not owner_separator or not package_name or not owner_name:
        raise EVIDENCE.EvidenceError(
            "partial", "unsupported_authority", "property must have a package-qualified class owner"
        )
    enum_name = f"{owner_name}{property_name.title()}"
    literals = candidate.get("literals")
    if not isinstance(literals, list) or len(literals) < 2 or len(set(literals)) != len(literals):
        raise EVIDENCE.EvidenceError(
            "partial", "domain_ambiguous", "accepted property must have a unique multi-value domain"
        )
    variants = [{"name": _variant(value), "wire_value": value} for value in literals]
    if len({row["name"] for row in variants}) != len(variants):
        raise EVIDENCE.EvidenceError(
            "partial", "domain_ambiguous", "enum variant normalization is not one-to-one"
        )
    return {
        "authority": {
            "fq_name": fq_name,
            "owner_fq_name": owner_fq_name,
            "property": property_name,
            "declaration_path": declaration["path"],
            "declaration_line": declaration["line"],
            "original_type": "String",
            "visibility": declaration.get("visibility"),
        },
        "declaration": declaration,
        "writes": writes,
        "references": references,
        "callers": sorted(
            {
                (row["caller"]["fq_name"], row["caller"]["signature"])
                for row in [*writes, *references]
                if isinstance(row.get("caller"), dict)
                and row["caller"].get("fq_name")
                and row["caller"].get("signature")
            }
        ),
        "enum": {
            "fq_name": f"{package_name}.{enum_name}",
            "type_name": enum_name,
            "variants": variants,
            "serialization_shape": "enum constructor wireValue: String",
        },
    }


def _proposal(payload: dict[str, Any]) -> str:
    target, enum = payload["target"], payload["proposed_enum"]
    authority = target["authority"]
    variants = "\n".join(
        f'    {row["name"]}("{row["wire_value"]}")' for row in enum["variants"]
    )
    callers = "\n".join(f"- `{row['fq_name']}`" for row in target["caller_contexts"])
    return f"""# Kotlin enum proposal

Status: `review_required`; no source was changed.

## Exact accepted authority

`{authority['fq_name']}` is declared as direct `String` state at
`{authority['declaration_path']}:{authority['declaration_line']}`. The proposal
preserves the accepted strings as explicit wire values:

```kotlin
enum class {enum['type_name']}(val wireValue: String) {{
{variants}
}}
```

Exact resolved caller contexts:

{callers}

## Human gates and stop conditions

- Closed domain and exact serialization strings were explicitly reviewed.
- Java callers, framework registration, external callers, reflection,
  delegated properties, generated/KAPT/KSP sources, Gradle variants, and
  overload ambiguity were explicitly attested absent for this authority.
- JVM ABI change was explicitly accepted for proposal drafting only.
- This is not mutation authority and does not claim runtime or behavioral
  equivalence. Re-review all gates before implementing the proposal.
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
        selected = _target(validated)
        payload = {
            "schema_version": "kotlin-enum-proposal-v1",
            "language": "kotlin",
            "status": "review_required",
            "outcome": "proposal_ready",
            "read_only": True,
            "source_mutations": 0,
            "target": {
                "authority": selected["authority"],
                "declaration": selected["declaration"],
                "writes": selected["writes"],
                "references": selected["references"],
                "caller_contexts": [
                    {"fq_name": fq_name, "signature": signature}
                    for fq_name, signature in selected["callers"]
                ],
            },
            "proposed_enum": selected["enum"],
            "human_gates": validated["acceptance"]["boundary_verdicts"],
            "fact_pack_sha256": validated["facts"]["fact_pack_sha256"],
            "source_manifest_sha256": validated["facts"]["source_manifest_sha256"],
            "source_inventory": validated["facts"]["source_inventory"],
            "native_checks": {
                name: validated["facts"]["commands"][name]
                for name in ("compile", "compile_tests", "test", "smoke")
            },
            "upstream": {
                "facts_path": validated["facts_path"].relative_to(root).as_posix(),
                "facts_sha256": EVIDENCE.file_hash(validated["facts_path"]),
                "findings_path": validated["findings_path"].relative_to(root).as_posix(),
                "findings_sha256": EVIDENCE.file_hash(validated["findings_path"]),
                "acceptance_path": validated["acceptance_path"].relative_to(root).as_posix(),
                "acceptance_sha256": EVIDENCE.file_hash(validated["acceptance_path"]),
            },
            "nonclaims": [
                "direct resolved writes and references do not prove runtime closure",
                "wire-value spelling does not prove serializer or framework compatibility",
                "the proposal grants no source mutation authority",
            ],
        }
        EVIDENCE.replace_bundle(
            output, {"targets.json": payload, "proposal.md": _proposal(payload)}
        )
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "extract-enum")
            payload, report = EVIDENCE.refusal("extract-enum", exc)
            EVIDENCE.replace_bundle(output, {"targets.json": payload, "proposal.md": report})
        except EVIDENCE.EvidenceError:
            pass
        print(f"collect_kotlin_state.py: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
