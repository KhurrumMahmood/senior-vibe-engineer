#!/usr/bin/env python3
"""Stage and execute an exact-field Ruby RBS guard from an approved enum proposal."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _helper() -> Any:
    candidates = [Path(__file__).with_name("ruby_proposal_evidence.py")]
    candidates.extend(parent / "_ruby-semantic" / "ruby_proposal_evidence.py" for parent in Path(__file__).resolve().parents)
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise RuntimeError("copied Ruby proposal-evidence helper is missing")
    spec = importlib.util.spec_from_file_location("ruby_guard_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied Ruby proposal-evidence helper cannot load")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _helper()


def _guard(owner: str, field: str, alias_name: str) -> str:
    return f'''#!/usr/bin/env ruby
# Exact reviewed authority only; not a general Ruby/Rails enum lint.
path = ARGV.fetch(0)
text = File.read(path, encoding: "UTF-8")
owner = {json.dumps(owner)}
field = {json.dumps(field)}
type_name = {json.dumps(alias_name.split("::")[-1])}
owner_name = owner.split("::").last
owner_pattern = /(?:class|module)\\s+\\b#{{Regexp.escape(owner_name)}}\\b/
field_pattern = /attr_accessor\\s+#{{Regexp.escape(field)}}:\\s*(?:[A-Za-z_][A-Za-z0-9_]*::)*#{{Regexp.escape(type_name)}}\\b/
unless text.match?(owner_pattern) && text.match?(field_pattern)
  warn "ruby-state-guard: #{{owner}}##{{field}} must retain reviewed RBS type #{{type_name}}"
  exit 1
end
puts "ruby-state-guard:ok"
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--accepted-review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ruby", default="ruby")
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        output = EVIDENCE.safe_output(root, args.output_dir, "prevent-regression")
        targets_path = EVIDENCE.safe_project_path(root, args.targets, "enum targets")
        review_path = EVIDENCE.safe_project_path(root, args.accepted_review, "enum proposal review")
        targets = EVIDENCE.read_json(targets_path, "enum targets")
        review = EVIDENCE.read_json(review_path, "enum proposal review")
        if targets.get("schema_version") != "ruby-enum-proposal-v1" or targets.get("outcome") != "proposal_ready":
            raise EVIDENCE.EvidenceError("unaccepted_evidence", "a ready Ruby enum proposal is required")
        EVIDENCE.validate_source_rows(root, targets.get("source_hashes"))
        if (
            review.get("schema_version") != "ruby-enum-proposal-review-v1"
            or review.get("decision") != "approve-exact-rbs-guard"
            or review.get("targets_sha256") != EVIDENCE.file_hash(targets_path)
            or not isinstance(review.get("reviewer"), str)
            or not review.get("reviewed_boundaries")
        ):
            raise EVIDENCE.EvidenceError("invalid_accepted_evidence", "enum proposal review does not verify")
        target = targets.get("target") or {}
        owner, field = target.get("owner"), target.get("name")
        alias_name = target.get("rbs_literal_alias", {}).get("name")
        if not all(isinstance(value, str) and value for value in (owner, field, alias_name)):
            raise EVIDENCE.EvidenceError("incomplete_evidence", "enum target lacks exact RBS authority")
        guard = _guard(owner, field, alias_name)
        owner_name = owner.split("::")[-1]
        type_name = alias_name.split("::")[-1]
        good = f"module GuardFixture\n  type {type_name} = \"queued\" | \"done\"\n  class {owner_name}\n    attr_accessor {field}: {type_name}\n  end\nend\n"
        bad = good.replace(f"attr_accessor {field}: {type_name}", f"attr_accessor {field}: String")
        artifacts: dict[str, str | dict[str, Any]] = {
            "ruby_state_guard.rb": guard,
            "good.rbs": good,
            "bad.rbs": bad,
            "guard.json": {
                "schema_version": "ruby-exact-rbs-state-guard-v1",
                "language": "ruby",
                "status": "complete",
                "outcome": "guard_staged",
                "installed": False,
                "source_mutations": 0,
                "owner": owner,
                "field": field,
                "rbs_type": alias_name,
                "targets_sha256": EVIDENCE.file_hash(targets_path),
                "review_sha256": EVIDENCE.file_hash(review_path),
                "human_authority": review,
                "limits": [
                    "Exact reviewed RBS declaration only; runtime assignments are not proved.",
                    "Rails enum/ActiveRecord, Zeitwerk, metaprogramming, reopening, and dynamic dispatch remain outside the guard.",
                ],
            },
        }
        EVIDENCE.replace_artifacts(output, artifacts)
        syntax = subprocess.run([args.ruby, "--disable-gems", "-c", str(output / "ruby_state_guard.rb")], text=True, capture_output=True, check=False)
        good_run = subprocess.run([args.ruby, "--disable-gems", str(output / "ruby_state_guard.rb"), str(output / "good.rbs")], text=True, capture_output=True, check=False)
        bad_run = subprocess.run([args.ruby, "--disable-gems", str(output / "ruby_state_guard.rb"), str(output / "bad.rbs")], text=True, capture_output=True, check=False)
        verification = {
            "schema_version": "ruby-exact-rbs-state-guard-verification-v1",
            "status": "complete" if syntax.returncode == 0 and good_run.returncode == 0 and bad_run.returncode == 1 else "failed",
            "syntax_rc": syntax.returncode,
            "good_rc": good_run.returncode,
            "bad_rc": bad_run.returncode,
            "good_stdout": good_run.stdout,
            "bad_stderr": bad_run.stderr,
        }
        EVIDENCE.atomic_json(output / "verification.json", verification)
        return 0 if verification["status"] == "complete" else 1
    except (EVIDENCE.EvidenceError, OSError) as exc:
        error = exc if isinstance(exc, EVIDENCE.EvidenceError) else EVIDENCE.EvidenceError("tool_unavailable", str(exc))
        try:
            output = EVIDENCE.safe_output(root, args.output_dir, "prevent-regression")
            payload, report = EVIDENCE.refusal("prevent-regression", error)
            EVIDENCE.replace_artifacts(output, {"guard.json": payload, "proposal.md": report})
        except EVIDENCE.EvidenceError:
            pass
        print(f"prevent-regression: {error.failure_kind}: {error.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
