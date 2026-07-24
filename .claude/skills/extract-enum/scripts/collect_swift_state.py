#!/usr/bin/env python3
"""Render one read-only Swift enum proposal from accepted A3 state evidence."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


def _helper() -> Any:
    candidates = [Path(__file__).with_name("swift_accepted_evidence.py")]
    candidates.extend(
        parent / "_swift-semantic-readonly" / "swift_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("copied Swift accepted-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("swift_extract_accepted_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Swift accepted-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _markdown(payload: dict[str, Any]) -> str:
    authority = payload["target"]["authority"]
    enum = payload["proposed_enum"]
    cases = "\n".join(f"  case {row['name']}" for row in enum["cases"])
    operations = "\n".join(
        f"- `{row['file']}:{row['line']}` — `{row['syntax']}`"
        for row in payload["target"]["operations"]
    )
    return f"""# Swift enum proposal

Status: `review_required`; no project source was changed.

## Exact accepted authority

`{authority['semantic_id']}` identifies `{authority['owner']}.{authority['field']}` at
`{authority['file']}:{authority['line']}`. Reuse the existing String-backed
`{enum['module']}.{enum['type_name']}` authority:

```swift
public enum {enum['type_name']}: String {{
{cases}
}}
```

The accepted raw values are `{', '.join(row['raw_value'] for row in enum['cases'])}`.

## Exact resolved operations

{operations}

## Human gates and stop conditions

- Closed-domain and exact raw-value decisions are human authority, not compiler inference.
- Codable/serialization, Objective-C and dynamic selectors, protocol/existential dispatch,
  frameworks/Xcode registration, external callers, generated/macros/plugins, conditional
  variants, and source/binary compatibility remain bounded by the acceptance artifact.
- This proposal grants no mutation or release authority. A second accepted migrated-tree
  artifact is required before staging the exact-type guard.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target-name", required=True)
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
            target_name=args.target_name,
            facts_path=args.facts,
            findings_path=args.findings,
            acceptance_path=args.acceptance,
        )
        candidate = validated["candidate"]
        facts = validated["facts"]
        enum = validated["enum"]
        target = {
            "authority": {
                "semantic_id": candidate["semantic_id"],
                "owner": candidate["owner"],
                "field": candidate["field"],
                "original_type": candidate["type"],
                "file": candidate["file"],
                "line": candidate["line"],
                "column": candidate["column"],
                "definition_identity": candidate["definition_identity"],
            },
            "operations": candidate["operations"],
            "literals": candidate["literals"],
        }
        payload = {
            "schema_version": "swift-enum-proposal-v1",
            "language": "swift",
            "status": "review_required",
            "outcome": "proposal_ready",
            "read_only": True,
            "source_mutations": 0,
            "target": target,
            "proposed_enum": enum,
            "boundary_verdicts": validated["acceptance"]["boundary_verdicts"],
            "native": validated["acceptance"]["native"],
            "fact_pack_sha256": facts["fact_pack_sha256"],
            "source_manifest_sha256": facts["source_manifest_sha256"],
            "source_hashes": facts["source_hashes"],
            "source_inventory": facts["source_inventory"],
            "package_sha256": facts["identity"]["package_sha256"],
            "selected_sources": sorted(
                row["path"]
                for row in facts["source_inventory"]
                if row.get("role") == "selected-production" and row.get("included")
            ),
            "native_checks": facts["native_checks"],
            "upstream": {
                "facts": validated["facts_path"].relative_to(root).as_posix(),
                "facts_sha256": EVIDENCE.file_hash(validated["facts_path"]),
                "findings": validated["findings_path"].relative_to(root).as_posix(),
                "findings_sha256": EVIDENCE.file_hash(validated["findings_path"]),
                "acceptance": validated["acceptance_path"].relative_to(root).as_posix(),
                "acceptance_sha256": EVIDENCE.file_hash(validated["acceptance_path"]),
                "candidate_sha256": candidate["candidate_sha256"],
            },
            "limits": [
                *facts.get("limits", []),
                "the existing enum and raw-value mapping are accepted human authority",
                "the proposal grants no source mutation or release authority",
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
        print(f"collect_swift_state.py: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
