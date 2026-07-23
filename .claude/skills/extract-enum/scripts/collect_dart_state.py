#!/usr/bin/env python3
"""Build one read-only Dart enum proposal from accepted D5 state evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any
import uuid


NONCLAIMS = [
    "the accepted literals prove an exhaustive runtime domain",
    "wire, persistence, reflection, or external API compatibility is automatic",
    "generated or Flutter state-management code is covered",
    "source mutation is authorized by this proposal",
]
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DartProposalError(ValueError):
    """Consumer-local refusal after the shared acceptance boundary."""

    def __init__(self, status: str, failure_kind: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.failure_kind = failure_kind
        self.detail = detail


def _validator():
    candidates = [Path(__file__).with_name("dart_accepted_evidence.py")]
    candidates.extend(
        parent / "_dart" / "dart_accepted_evidence.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise DartProposalError(
            "partial", "evidence_validator_unavailable", "Dart accepted-evidence validator is missing"
        )
    spec = importlib.util.spec_from_file_location("dart_extract_accepted_evidence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_output(root: Path, supplied: Path) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    if raw.is_symlink():
        raise DartProposalError("failed", "unsafe_output", "output directory must not be a symlink")
    output = Path(os.path.realpath(raw.resolve(strict=False)))
    allowed = root / "reports" / "extract-enum"
    if output == allowed or not _inside(allowed, output):
        raise DartProposalError(
            "failed", "unsafe_output", "output directory must stay beneath reports/extract-enum/"
        )
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise DartProposalError(
                "failed", "unsafe_output", "output directory must not traverse a symlink"
            )
    return output


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DartProposalError("failed", "invalid_d5_evidence", f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DartProposalError("failed", "invalid_d5_evidence", f"{label} must be an object")
    return payload


def _d5_consistency(
    root: Path, evidence: Path, validated: dict[str, Any]
) -> dict[str, Any]:
    required = {
        "candidates.jsonl",
        "facts.json",
        "findings.json",
        "scan.json",
    }
    verified = set(validated["verified_artifacts"])
    if not required <= verified:
        raise DartProposalError(
            "partial", "d5_evidence_incomplete", "accepted D5 evidence closure is incomplete"
        )
    facts = _json(evidence / "facts.json", "D5 facts")
    findings = _json(evidence / "findings.json", "D5 findings")
    scan = _json(evidence / "scan.json", "D5 scan")
    supplied_pack = facts.get("fact_pack_sha256")
    canonical_facts = dict(facts)
    canonical_facts.pop("fact_pack_sha256", None)
    if supplied_pack != _canonical_hash(canonical_facts):
        raise DartProposalError("failed", "invalid_d5_evidence", "D5 fact-pack hash does not verify")
    candidates_text = (evidence / "candidates.jsonl").read_text(encoding="utf-8")
    if (
        scan.get("schema_version") != "dart-implicit-state-scan-v1"
        or scan.get("status") != "complete"
        or scan.get("fact_pack_sha256") != supplied_pack
        or scan.get("candidates_sha256")
        != hashlib.sha256(candidates_text.encode()).hexdigest()
        or scan.get("findings_sha256") != _sha256(evidence / "findings.json")
        or findings.get("fact_pack_sha256") != supplied_pack
        or findings.get("source_hashes") != facts.get("source_hashes")
        or findings.get("source_hashes") != validated["envelope"].get("source_hashes")
    ):
        raise DartProposalError("failed", "invalid_d5_evidence", "D5 artifact lineage does not verify")
    query_plan = facts.get("query_plan")
    if not isinstance(query_plan, dict) or facts.get("query_plan_sha256") != _canonical_hash(
        query_plan
    ):
        raise DartProposalError("failed", "invalid_d5_evidence", "D5 query-plan hash does not verify")
    fact_config = facts.get("package_config")
    config_rows = validated["envelope"].get("configuration_hashes", [])
    if not isinstance(fact_config, dict) or not isinstance(fact_config.get("path"), str):
        raise DartProposalError("failed", "invalid_d5_evidence", "D5 package configuration is missing")
    config_path = Path(fact_config["path"])
    try:
        config_relative = config_path.resolve().relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise DartProposalError(
            "failed", "invalid_d5_evidence", "D5 package configuration escapes the project"
        ) from exc
    if not any(
        row.get("path") == config_relative and row.get("sha256") == fact_config.get("sha256")
        for row in config_rows
        if isinstance(row, dict)
    ):
        raise DartProposalError(
            "failed", "invalid_d5_evidence", "accepted package configuration differs from D5 facts"
        )
    return {"facts": facts, "findings": findings, "scan": scan, "candidates": candidates_text}


def _candidate_consistency(
    evidence: Path,
    selected: dict[str, Any],
    d5: dict[str, Any],
) -> None:
    try:
        candidates = [json.loads(line) for line in d5["candidates"].splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise DartProposalError("failed", "invalid_d5_evidence", "D5 candidates are malformed") from exc
    matches = [row for row in candidates if row.get("candidate_id") == selected.get("candidate_id")]
    if len(matches) != 1:
        raise DartProposalError("failed", "invalid_d5_evidence", "accepted D5 candidate is ambiguous")
    candidate = matches[0]
    unhashed = dict(candidate)
    supplied = unhashed.pop("candidate_sha256", None)
    review_path = evidence / "scout" / f"{selected.get('candidate_id')}.json"
    review = _json(review_path, "D5 human review")
    if (
        supplied != _canonical_hash(unhashed)
        or selected.get("candidate_sha256") != supplied
        or selected.get("bucket") != "extract_enum_candidate"
        or selected.get("human_verdict") != "accepted"
        or review.get("candidate_sha256") != supplied
        or review.get("candidate_id") != selected.get("candidate_id")
        or review.get("bucket") != "extract_enum_candidate"
        or review.get("human_verdict") != "accepted"
    ):
        raise DartProposalError("failed", "invalid_d5_evidence", "D5 candidate acceptance does not verify")


def _source_manifest(validated: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = validated["envelope"]["source_hashes"]
    return {row["path"]: row for row in rows}


def _exact_candidate(root: Path, selected: dict[str, Any], validated: dict[str, Any]) -> dict[str, Any]:
    required = ("owner", "field", "type", "file", "line", "column", "operations", "literals")
    if any(key not in selected for key in required):
        raise DartProposalError("failed", "invalid_d5_evidence", "selected D5 candidate is malformed")
    owner, field, relative = selected["owner"], selected["field"], selected["file"]
    if (
        not isinstance(owner, str)
        or not isinstance(field, str)
        or not isinstance(relative, str)
        or not IDENTIFIER.fullmatch(owner)
        or not IDENTIFIER.fullmatch(field)
        or owner.startswith("_")
        or field.startswith("_")
        or selected["type"] != "String"
    ):
        raise DartProposalError(
            "partial", "unsupported_exact_authority", "only one public direct String field is supported"
        )
    manifest = _source_manifest(validated)
    record = manifest.get(relative)
    if (
        not record
        or record.get("role") != "production"
        or Path(relative).suffix != ".dart"
        or relative.endswith((".g.dart", ".freezed.dart", ".mocks.dart"))
    ):
        raise DartProposalError(
            "partial", "unsupported_exact_authority", "accepted owner is not authored production Dart"
        )
    source = root / relative
    lines = source.read_text(encoding="utf-8").splitlines()
    line = selected["line"]
    if not isinstance(line, int) or not 1 <= line <= len(lines):
        raise DartProposalError("failed", "stale_d5_evidence", "accepted field line is stale")
    declaration = lines[line - 1]
    match = re.fullmatch(rf"(?P<indent>\s*)(?:late\s+)?String\s+{re.escape(field)}\s*;", declaration)
    if match is None:
        raise DartProposalError("failed", "stale_d5_evidence", "accepted exact String field is stale")
    if declaration.index(field) + 1 != selected["column"]:
        raise DartProposalError("failed", "stale_d5_evidence", "accepted exact field column is stale")
    before = "\n".join(lines[: line - 1])
    classes = list(re.finditer(r"(?:^|\n)\s*class\s+([A-Za-z_]\w*)\b", before))
    if not classes or classes[-1].group(1) != owner:
        raise DartProposalError("failed", "stale_d5_evidence", "accepted field owner is stale")
    operations = selected["operations"]
    literals = selected["literals"]
    if (
        not isinstance(operations, list)
        or len(operations) < 3
        or not isinstance(literals, list)
        or len(set(literals)) < 3
        or not all(isinstance(value, str) and value for value in literals)
    ):
        raise DartProposalError(
            "partial", "open_or_sparse_domain", "accepted candidate lacks three bounded literal operations"
        )
    for operation in operations:
        if (
            not isinstance(operation, dict)
            or operation.get("file") != relative
            or operation.get("kind") not in {"assignment", "comparison"}
        ):
            raise DartProposalError("partial", "ambiguous_authority", "operation authority is ambiguous")
        operation_line = operation.get("line")
        syntax = operation.get("syntax")
        if (
            not isinstance(operation_line, int)
            or not 1 <= operation_line <= len(lines)
            or not isinstance(syntax, str)
            or syntax not in lines[operation_line - 1]
            or not any(
                target.get("path") == relative and target.get("line") == line
                for target in operation.get("definition_targets", [])
                if isinstance(target, dict)
            )
        ):
            raise DartProposalError("failed", "stale_d5_evidence", "operation lineage is stale")
    return {
        "owner": owner,
        "field": field,
        "current_type": "String",
        "declaration_file": relative,
        "declaration_line": line,
        "source_sha256": record["sha256"],
        "visibility": "public",
        "operations": operations,
        "literals": literals,
        "indent": match.group("indent"),
    }


def _boundaries(validated: dict[str, Any], literals: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    boundaries = validated["envelope"]["reviewed_boundaries"]
    domain = boundaries.get("domain", {})
    serialization = boundaries.get("serialization", {})
    compatibility = boundaries.get("public_compatibility", {})
    reflection = boundaries.get("reflection", {})
    external = boundaries.get("external_api", {})
    enum = boundaries.get("enum", {})
    if (
        domain.get("closed_for_proposal") is not True
        or serialization.get("reviewed") is not True
        or serialization.get("strategy") != "preserve_wire_values"
        or compatibility.get("reviewed") is not True
        or reflection.get("reviewed") is not True
        or reflection.get("uncertain") is not False
        or external.get("owned_elsewhere") is not False
        or boundaries.get("generated_owner") is not False
        or boundaries.get("ambiguous_authority") is not False
    ):
        raise DartProposalError(
            "partial",
            "proposal_boundary_unresolved",
            "domain, serialization, compatibility, reflection, or ownership review is unresolved",
        )
    type_name, variants = enum.get("type_name"), enum.get("variants")
    if (
        not isinstance(type_name, str)
        or not IDENTIFIER.fullmatch(type_name)
        or type_name.startswith("_")
        or not type_name[:1].isupper()
        or not isinstance(variants, list)
        or not all(
            isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and IDENTIFIER.fullmatch(row["name"])
            and isinstance(row.get("wire_value"), str)
            for row in variants
        )
        or {row["wire_value"] for row in variants} != set(literals)
        or len({row["name"] for row in variants}) != len(variants)
    ):
        raise DartProposalError(
            "partial", "proposal_boundary_unresolved", "accepted Dart enum names are incomplete"
        )
    return boundaries, {"type_name": type_name, "variants": variants}


def _enum_text(proposed: dict[str, Any]) -> str:
    rows = ",\n".join(
        f"  {row['name']}({json.dumps(row['wire_value'])})" for row in proposed["variants"]
    )
    return f"""enum {proposed['type_name']} {{
{rows};

  const {proposed['type_name']}(this.wireValue);

  final String wireValue;

  static {proposed['type_name']} fromWire(String value) {{
    return values.firstWhere((candidate) => candidate.wireValue == value);
  }}
}}
"""


def _proposal(
    root: Path,
    selected: dict[str, Any],
    validated: dict[str, Any],
    d5: dict[str, Any],
) -> dict[str, Any]:
    _candidate_consistency(Path(validated["evidence_dir"]), selected, d5)
    authority = _exact_candidate(root, selected, validated)
    boundaries, proposed = _boundaries(validated, authority["literals"])
    source_text = (root / authority["declaration_file"]).read_text(encoding="utf-8")
    cited = {
        (row.get("path"), row.get("start_line"))
        for row in validated["envelope"].get("cited_spans", [])
        if isinstance(row, dict)
    }
    required_citations = {
        (authority["declaration_file"], authority["declaration_line"]),
        *((row["file"], row["line"]) for row in authority["operations"]),
    }
    serialization_line = source_text[: source_text.index(boundaries["serialization"]["syntax"])].count(
        "\n"
    ) + 1
    required_citations.add((authority["declaration_file"], serialization_line))
    if not required_citations <= cited:
        raise DartProposalError(
            "failed", "invalid_d5_evidence", "accepted field/operation/boundary citations are incomplete"
        )
    if re.search(rf"\benum\s+{re.escape(proposed['type_name'])}\b", source_text):
        raise DartProposalError(
            "partial", "proposal_boundary_unresolved", "proposed enum type already exists"
        )
    variant_by_wire = {row["wire_value"]: row["name"] for row in proposed["variants"]}
    edits: list[dict[str, str]] = [
        {
            "file": authority["declaration_file"],
            "old": f"class {authority['owner']} {{",
            "new": f"{_enum_text(proposed)}\nclass {authority['owner']} {{",
            "purpose": "declare the reviewed wire-preserving enum",
        },
        {
            "file": authority["declaration_file"],
            "old": (
                f"class {authority['owner']} {{\n"
                f"{authority['indent']}late String {authority['field']};"
            ),
            "new": (
                f"class {authority['owner']} {{\n"
                f"{authority['indent']}late {proposed['type_name']} {authority['field']};"
            ),
            "purpose": "replace the exact accepted field type",
        },
    ]
    for operation in authority["operations"]:
        old = operation["syntax"]
        member = variant_by_wire[operation["literal"]]
        if operation["kind"] == "assignment":
            new = re.sub(
                r"(['\"]).*\1",
                f"{proposed['type_name']}.{member}",
                old,
                count=1,
            )
        else:
            new = re.sub(
                r"(['\"])(.*?)\1",
                f"{proposed['type_name']}.{member}",
                old,
                count=1,
            )
        edits.append(
            {
                "file": operation["file"],
                "old": old,
                "new": new,
                "purpose": f"replace accepted {operation['kind']} literal",
            }
        )
    serialization = boundaries["serialization"]
    edits.append(
        {
            "file": authority["declaration_file"],
            "old": serialization["syntax"],
            "new": serialization["replacement"],
            "purpose": "preserve reviewed JSON/wire values",
        }
    )
    if any(
        (root / row["file"]).read_text(encoding="utf-8").count(row["old"]) != 1
        for row in edits
    ):
        raise DartProposalError(
            "failed", "stale_d5_evidence", "exact rewrite plan is ambiguous or stale"
        )
    variants = proposed["variants"]
    assertions = "\n".join(
        f"  if ({proposed['type_name']}.{row['name']}.wireValue != {json.dumps(row['wire_value'])}) {{\n"
        f"    throw StateError('wire value changed: {row['name']}');\n"
        "  }"
        for row in variants
    )
    validation_test = f"""import '../lib/state.dart';

void main() {{
{assertions}
  for (final value in {proposed['type_name']}.values) {{
    if ({proposed['type_name']}.fromWire(value.wireValue) != value) {{
      throw StateError('wire round trip changed');
    }}
  }}
}}
"""
    return {
        "schema_version": "dart-enum-proposal-v1",
        "language": "dart",
        "status": "complete",
        "outcome": "proposal_ready",
        "read_only": True,
        "source_preserved": True,
        "accepted_evidence_hash": validated["envelope"]["acceptance_hash"],
        "fact_pack_sha256": d5["facts"]["fact_pack_sha256"],
        "candidate_id": selected["candidate_id"],
        "authority": {key: authority[key] for key in (
            "owner", "field", "current_type", "declaration_file", "declaration_line", "source_sha256", "visibility"
        )},
        "operations": authority["operations"],
        "proposed_enum": proposed,
        "boundaries": boundaries,
        "rewrite_plan": {"edits": edits, "apply_authorized": False},
        "disposable_validation_test": {
            "path": "test/dart_d6_enum_values.dart",
            "content": validation_test,
            "expected_returncode": 0,
        },
        "native_obligations": validated["envelope"]["native_obligations"],
        "nonclaims": NONCLAIMS,
        "next_step": "A human must SHA-bind and accept this exact proposal before guard staging.",
    }


def _clean(selected: dict[str, Any], validated: dict[str, Any]) -> dict[str, Any]:
    if (
        selected.get("classification") != "typed_state_authority"
        or not isinstance(selected.get("type"), str)
        or selected["type"].rstrip("?") == "String"
    ):
        raise DartProposalError("failed", "invalid_d5_evidence", "clean selection is not typed state")
    return {
        "schema_version": "dart-enum-proposal-v1",
        "language": "dart",
        "status": "complete",
        "outcome": "no_proposal_already_typed",
        "read_only": True,
        "source_preserved": True,
        "accepted_evidence_hash": validated["envelope"]["acceptance_hash"],
        "authority": {
            "owner": selected.get("owner"),
            "field": selected.get("field"),
            "current_type": selected.get("type"),
            "declaration_file": selected.get("file"),
            "declaration_line": selected.get("line"),
        },
        "rewrite_plan": {"edits": [], "apply_authorized": False},
        "nonclaims": NONCLAIMS,
    }


def _profile(data: dict[str, Any]) -> str:
    if data["outcome"] == "no_proposal_already_typed":
        return f"""# Dart state profile

Status: `complete`

`{data['authority']['owner']}.{data['authority']['field']}` already has typed
authority `{data['authority']['current_type']}`. No enum proposal is needed.
This result is read-only.
"""
    authority = data["authority"]
    return f"""# Dart state profile — {authority['owner']}.{authority['field']}

Status: `complete`; outcome: `proposal_ready`

This proposal does not edit source. It consumes accepted evidence hash
`{data['accepted_evidence_hash']}` for the exact public field at
`{authority['declaration_file']}:{authority['declaration_line']}`.

The accepted review treats the three named literals as the bounded proposal
domain, preserves their JSON/wire strings, and records the public field-type
change as breaking. Reflection and external ownership were reviewed explicitly.
"""


def _proposal_markdown(data: dict[str, Any]) -> str:
    if data["outcome"] == "no_proposal_already_typed":
        return "# Dart enum proposal\n\nNo enum proposal is needed; accepted evidence already names typed state.\n"
    enum_text = _enum_text(data["proposed_enum"])
    edits = "\n".join(
        f"{index}. `{row['file']}`: {row['purpose']}."
        for index, row in enumerate(data["rewrite_plan"]["edits"], 1)
    )
    nonclaims = "\n".join(f"- {item}" for item in NONCLAIMS)
    return f"""# Proposal — Dart enum for {data['authority']['owner']}.{data['authority']['field']}

Status: `complete`; human proposal review still required.

```dart
{enum_text}```

## Exact migration plan

{edits}

The public field type is a breaking field-type change. Coordinate callers,
retain the reviewed wire strings through `wireValue` / `fromWire`, apply these
exact edits only in a separately authorized change, then run every recorded
native obligation and the disposable native value test.

## Non-claims

{nonclaims}
"""


def _terminal(status: str, kind: str, detail: str) -> dict[str, Any]:
    return {
        "schema_version": "dart-enum-proposal-v1",
        "language": "dart",
        "status": status,
        "outcome": "refused",
        "failure_kind": kind,
        "failure_detail": detail,
        "read_only": True,
        "rewrite_plan": {"edits": [], "apply_authorized": False},
        "nonclaims": NONCLAIMS,
    }


def _replace(output: Path, files: dict[str, str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{output.name}.staged-", dir=output.parent))
    backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
    try:
        for relative, text in files.items():
            destination = staged / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")
        if output.exists():
            output.replace(backup)
        staged.replace(output)
        shutil.rmtree(backup, ignore_errors=True)
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        if backup.exists() and not output.exists():
            backup.replace(output)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
        if not root.is_dir() or args.project_root.is_symlink():
            raise DartProposalError("partial", "project_unavailable", "project root is unavailable")
        output = _safe_output(root, args.output_dir)
        validator = _validator()
        try:
            validated = validator.validate_accepted_evidence(
                root,
                args.evidence_dir,
                args.acceptance,
                expected_producer="find-implicit-state",
                verify_current_sources=True,
            )
        except validator.AcceptedEvidenceError as exc:
            raise DartProposalError(exc.status, exc.failure_kind, exc.detail) from exc
        evidence = Path(os.path.realpath(args.evidence_dir.resolve(strict=True)))
        validated["evidence_dir"] = str(evidence)
        d5 = _d5_consistency(root, evidence, validated)
        selection_kind = validated["envelope"]["selection"]["kind"]
        selected = validated["selected_evidence"]
        if not isinstance(selected, dict):
            raise DartProposalError("failed", "invalid_d5_evidence", "accepted selection is malformed")
        if selection_kind == "extract_enum_candidate":
            data = _proposal(root, selected, validated, d5)
        elif selection_kind == "enum_already_owned":
            data = _clean(selected, validated)
        else:
            raise DartProposalError("partial", "unsupported_selection", "accepted state selection is unsupported")
        files = {
            "targets.json": json.dumps(data, indent=2, sort_keys=True) + "\n",
            "profile.md": _profile(data),
            "proposal.md": _proposal_markdown(data),
        }
        _replace(output, files)
    except (
        DartProposalError,
        FileNotFoundError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        if isinstance(exc, DartProposalError):
            status, kind, detail = exc.status, exc.failure_kind, exc.detail
        else:
            status, kind, detail = "failed", "invalid_d5_evidence", str(exc)
        terminal = _terminal(status, kind, detail)
        if output is not None:
            _replace(
                output,
                {
                    "targets.json": json.dumps(terminal, indent=2, sort_keys=True) + "\n",
                    "profile.md": f"# Dart state profile\n\nStatus: `{status}`; proposal refused.\n\n{detail}\n",
                },
            )
        print(f"[collect_dart_state] {status}/{kind}: {detail}", file=sys.stderr)
        return 2
    print(f"[collect_dart_state] {data['outcome']}: {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
