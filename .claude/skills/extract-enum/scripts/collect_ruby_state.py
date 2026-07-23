#!/usr/bin/env python3
"""Render one Ruby enum/value-object proposal from accepted A3 state evidence."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


def _helper() -> Any:
    candidates = [Path(__file__).with_name("ruby_proposal_evidence.py")]
    candidates.extend(parent / "_ruby-semantic" / "ruby_proposal_evidence.py" for parent in Path(__file__).resolve().parents)
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise RuntimeError("copied Ruby proposal-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("ruby_extract_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Ruby proposal-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _proposal(payload: dict[str, Any]) -> str:
    if payload["outcome"] == "safely_deferred":
        return "# Ruby enum proposal\n\nHuman review deferred this exact candidate. No source change is proposed.\n"
    candidate = payload["target"]
    constants = "\n".join(f'  {value.upper()} = "{value}"' for value in candidate["literals"])
    return f"""# Ruby enum/value-object proposal

Status: `review_required`; source remains unchanged.

## Exact authority

`{candidate['owner']}#{candidate['name']}` is backed by project-owned RBS alias
`{candidate['rbs_literal_alias']['name']}` with wire values `{', '.join(candidate['literals'])}`.

```ruby
module {candidate['name'].title()}Value
{constants}
  VALUES = [{', '.join(value.upper() for value in candidate['literals'])}].freeze
end
```

Preserve the exact strings as wire/persistence values. Update the RBS attribute
to the existing literal alias; do not infer symbol or integer serialization.

## Caller impact

""" + "\n".join(f"- `{row['path']}:{row['line']}` writes `{row['value']}`" for row in candidate["operations"]) + """

## Stop conditions and authority

- Stop for Rails enum/ActiveRecord persistence, Zeitwerk naming, external API,
  dynamic dispatch, reopening, metaprogramming, or an open runtime domain.
- Run the recorded Ruby syntax, frozen Bundler, RBS validation, native test,
  and smoke checks after an approved implementation.
- A human must approve this proposal before source mutation.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, "extract-enum")
        validated = EVIDENCE.validate(
            project_root=root,
            producer="find-implicit-state",
            evidence_path=args.evidence,
            facts_path=args.facts,
            acceptance_path=args.acceptance,
            allowed_decisions={"accept-enum", "defer"},
        )
        candidates = validated["artifact"].get("candidates", [])
        decision = validated["acceptance"]["decision"]
        if decision == "accept-enum" and len(candidates) != 1:
            raise EVIDENCE.EvidenceError("incomplete_evidence", "exactly one accepted Ruby state candidate is required")
        payload = {
            "schema_version": "ruby-enum-proposal-v1",
            "language": "ruby",
            "status": "complete",
            "outcome": "proposal_ready" if decision == "accept-enum" else "safely_deferred",
            "read_only": True,
            "source_mutations": 0,
            "upstream_artifact_sha256": validated["artifact_sha256"],
            "acceptance_sha256": validated["acceptance_sha256"],
            "human_authority": validated["acceptance"],
            "target": candidates[0] if candidates else None,
            "fact_pack_sha256": validated["facts"].get("fact_pack_sha256"),
            "source_manifest_sha256": validated["facts"].get("source_manifest_sha256"),
            "source_hashes": validated["facts"].get("source_hashes", []),
            "dynamic_boundaries": validated["facts"].get("source", {}).get("dynamic", []),
            "limits": validated["facts"].get("limits", []),
            "native_checks": validated["facts"].get("tools", {}).get("native", {}),
        }
        EVIDENCE.replace_artifacts(output, {"targets.json": payload, "proposal.md": _proposal(payload)})
        return 0
    except EVIDENCE.EvidenceError as exc:
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "extract-enum")
            payload, report = EVIDENCE.refusal("extract-enum", exc)
            EVIDENCE.replace_artifacts(output, {"targets.json": payload, "proposal.md": report})
        except EVIDENCE.EvidenceError:
            pass
        print(f"extract-enum: {exc.failure_kind}: {exc.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
