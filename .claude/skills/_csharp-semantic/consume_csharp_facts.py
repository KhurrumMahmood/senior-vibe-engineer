#!/usr/bin/env python3
"""Render five conservative C# outcomes from one validated Roslyn fact pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


OUTPUTS = {
    "dormant": ("reports/find-dormant/csharp", "findings.json"),
    "state": ("reports/find-implicit-state/csharp", "findings.json"),
    "sweep": ("reports/find-incomplete-sweep/csharp", "manifest.json"),
    "duplication": ("reports/semantic-duplication/csharp", "analysis.json"),
    "rename": ("reports/rename-concept/csharp", "assessment.json"),
}


def _object_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _safe_destination(root: Path, skill: str, supplied: Path | None) -> Path:
    relative_root, filename = OUTPUTS[skill]
    allowed = root / relative_root
    requested = supplied if supplied is not None else Path(filename)
    destination = Path(
        os.path.abspath(requested if requested.is_absolute() else allowed / requested)
    )
    try:
        relative = destination.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"output must stay beneath {relative_root}") from exc
    if not relative.parts:
        raise ValueError("output must name an artifact file")
    current = root
    for part in destination.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output cannot traverse a symbolic link")
    return destination


def _load(root: Path, supplied: Path) -> tuple[dict[str, Any], str | None]:
    path = supplied if supplied.is_absolute() else root / supplied
    try:
        facts = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"status": "partial", "limits": []}, f"fact-pack-unavailable: {exc}"
    if (
        facts.get("schema_version") != "csharp-roslyn-semantic-facts-v1"
        or facts.get("language") != "csharp"
        or facts.get("status") != "complete"
    ):
        return facts, facts.get("failure_kind", "fact-pack-partial")
    if facts.get("project_root") != str(root):
        return facts, "fact-pack-root-mismatch"
    expected_hash = facts.get("fact_pack_sha256")
    unsigned = dict(facts)
    unsigned.pop("fact_pack_sha256", None)
    if expected_hash != _object_hash(unsigned):
        return facts, "fact-pack-hash-mismatch"
    try:
        declared_manifest = Path(facts["manifest_path"])
        if declared_manifest.is_symlink():
            return facts, "fact-pack-manifest-stale"
        manifest = declared_manifest.resolve(strict=True)
        manifest.relative_to(root)
    except (KeyError, OSError, TypeError, ValueError):
        return facts, "fact-pack-manifest-stale"
    if _sha256(manifest) != facts.get("manifest_sha256"):
        return facts, "fact-pack-manifest-stale"
    for row in facts.get("source_inventory", []):
        candidate = root / row.get("path", "")
        if (
            not candidate.is_file()
            or candidate.is_symlink()
            or _sha256(candidate) != row.get("sha256")
        ):
            return facts, "fact-pack-stale"
    return facts, None


def _dormant(facts: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    calls = facts.get("calls", [])
    references = facts.get("references", [])
    boundary_targets = {
        row.get("target_symbol_id", row.get("symbol_id"))
        for row in facts.get("boundaries", [])
        if row.get("kind")
        in {
            "delegate_or_method_group",
            "override_dispatch",
            "explicit_interface_dispatch",
        }
    }
    for declaration in facts.get("declarations", []):
        if (
            declaration.get("role") != "source"
            or declaration.get("kind") != "method"
            or declaration.get("accessibility") != "Private"
            or declaration.get("name") == "Main"
        ):
            continue
        symbol_id = declaration.get("symbol_id")
        direct_calls = [row for row in calls if row.get("target_symbol_id") == symbol_id]
        direct_references = [
            row for row in references if row.get("target_symbol_id") == symbol_id
        ]
        unresolved = [
            row
            for row in references
            if not row.get("resolved") and row.get("source") == declaration.get("name")
        ]
        if (
            declaration.get("override")
            or declaration.get("partial")
            or symbol_id in boundary_targets
            or unresolved
        ):
            deferred.append(
                {
                    "symbol_id": symbol_id,
                    "signature": declaration.get("signature"),
                    "reason": "dispatch, delegate/method-group, partial, or unresolved evidence prevents a dormant lead",
                }
            )
        elif not direct_calls and not direct_references:
            candidates.append(
                {
                    "classification": "review_required_private_no_resolved_reference",
                    "symbol_id": symbol_id,
                    "signature": declaration.get("signature"),
                    "path": declaration["path"],
                    "line": declaration["line"],
                    "certain_delete": False,
                    "human_verdict": "required",
                    "boundary": "not a runtime reachability, reflection, external-caller, or safe-delete claim",
                }
            )
    return {
        "candidates": candidates,
        "deferred": deferred,
        "candidate_sha256": _object_hash(candidates),
    }


def _state(facts: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for declaration in facts.get("declarations", []):
        if (
            declaration.get("role") != "source"
            or declaration.get("kind") != "property"
            or str(declaration.get("name", "")).casefold()
            not in {"state", "status", "phase"}
            or declaration.get("type") != "string"
        ):
            continue
        operations = [
            row
            for row in facts.get("writes", [])
            if row.get("target_symbol_id") == declaration.get("symbol_id")
            and row.get("role") == "source"
        ]
        literals = {declaration.get("initializer_string_literal")}
        literals.update(row.get("string_literal") for row in operations)
        values = sorted(value for value in literals if isinstance(value, str))
        if len(values) >= 2:
            candidates.append(
                {
                    "classification": "review_required_string_state_candidate",
                    "symbol_id": declaration.get("symbol_id"),
                    "signature": declaration.get("signature"),
                    "path": declaration["path"],
                    "line": declaration["line"],
                    "literals": values,
                    "operations": operations,
                    "automatic_migration": False,
                    "human_verdict": "required",
                    "boundary": "selected direct writes do not prove a closed serialized or runtime state domain",
                }
            )
        else:
            deferred.append(
                {
                    "symbol_id": declaration.get("symbol_id"),
                    "reason": "fewer than two selected direct string literals",
                }
            )
    return {
        "candidates": candidates,
        "deferred": deferred,
        "candidate_sha256": _object_hash(candidates),
    }


def _explicit_argument(call: dict[str, Any], parameter: str) -> bool:
    return any(
        row.get("parameter_name") == parameter
        and row.get("argument_kind") == "Explicit"
        for row in call.get("arguments", [])
    )


def _sweep(facts: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for call in facts.get("calls", []):
        if (
            call.get("role") == "source"
            and call.get("resolved")
            and call.get("target_kind") == "constructor"
        ):
            groups[str(call.get("target_symbol_id"))].append(call)
    for symbol_id, calls in sorted(groups.items()):
        if len(calls) < 3:
            continue
        for parameter in calls[0].get("target_parameters", []):
            if not parameter.get("has_explicit_default"):
                continue
            present = [
                call for call in calls if _explicit_argument(call, parameter["name"])
            ]
            missing = [
                call for call in calls if not _explicit_argument(call, parameter["name"])
            ]
            if len(present) >= 2 and len(missing) == 1:
                straggler = missing[0]
                findings.append(
                    {
                        "classification": "review_required_optional_constructor_argument_sweep_gap",
                        "constructor_symbol_id": symbol_id,
                        "constructor_signature": calls[0]["target_signature"],
                        "parameter": parameter["name"],
                        "group_size": len(calls),
                        "with_parameter_count": len(present),
                        "straggler": {
                            "path": straggler["path"],
                            "line": straggler["line"],
                            "source": straggler["source"],
                        },
                        "direct_calls": [
                            {
                                "path": row["path"],
                                "line": row["line"],
                                "source": row["source"],
                            }
                            for row in calls
                        ],
                        "human_verdict": "required",
                        "boundary": "selected direct constructor calls do not prove migration chronology or behavior",
                    }
                )
            else:
                deferred.append(
                    {
                        "constructor_symbol_id": symbol_id,
                        "parameter": parameter["name"],
                        "reason": "selected call group does not contain exactly one omission",
                    }
                )
    return {
        "findings": findings,
        "deferred": deferred,
        "finding_sha256": _object_hash(findings),
    }


def _normalized_body(source: str | None) -> str:
    return re.sub(r"\s+", " ", source or "").strip()


def _duplication(facts: dict[str, Any]) -> dict[str, Any]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    rejected: list[dict[str, Any]] = []
    for declaration in facts.get("declarations", []):
        if (
            declaration.get("role") != "source"
            or declaration.get("kind") != "method"
            or declaration.get("override")
            or declaration.get("partial")
        ):
            continue
        body = _normalized_body(declaration.get("body_source"))
        if not body:
            continue
        shape = (
            tuple(
                row.get("type") for row in declaration.get("parameters", [])
            ),
            declaration.get("return_type"),
            body,
        )
        groups[shape].append(declaration)
    leads: list[dict[str, Any]] = []
    for (_parameters, _return_type, body), declarations in groups.items():
        if len(declarations) != 2 or len(
            {row.get("symbol_id") for row in declarations}
        ) != 2:
            continue
        functions = []
        for declaration in declarations:
            contexts = [
                {
                    "path": row["path"],
                    "line": row["line"],
                    "caller": row.get("caller"),
                }
                for row in facts.get("calls", [])
                if row.get("target_symbol_id") == declaration.get("symbol_id")
                and row.get("role") == "source"
            ]
            if not contexts:
                rejected.append(
                    {
                        "symbol_id": declaration.get("symbol_id"),
                        "reason": "no distinct direct selected-source caller context",
                    }
                )
                break
            functions.append(
                {
                    "symbol_id": declaration.get("symbol_id"),
                    "signature": declaration.get("signature"),
                    "path": declaration["path"],
                    "line": declaration["line"],
                    "direct_caller_contexts": contexts,
                }
            )
        if len(functions) == 2:
            leads.append(
                {
                    "id": f"CSD-{len(leads) + 1:02d}",
                    "classification": "review_required_resolved_contract_and_body_shape_lead",
                    "functions": functions,
                    "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "human_verdict": "required",
                    "boundary": "matching selected static signatures, bodies, and callers do not prove behavioral equivalence",
                }
            )
    return {
        "leads": leads,
        "rejected": rejected,
        "candidate_sha256": _object_hash(leads),
    }


def _type_matches(row: dict[str, Any], concept: str) -> bool:
    return row.get("name") == concept or str(row.get("signature", "")).rsplit(
        ".", 1
    )[-1] == concept


def _rename(facts: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    declarations = [
        row
        for row in facts.get("declarations", [])
        if row.get("role") == "source"
        and row.get("kind") in {"class", "interface", "enum", "record", "struct"}
    ]
    old_declarations = [row for row in declarations if _type_matches(row, old)]
    new_declarations = [row for row in declarations if _type_matches(row, new)]
    old_ids = {row.get("symbol_id") for row in old_declarations}
    new_ids = {row.get("symbol_id") for row in new_declarations}
    old_references = [
        row
        for row in facts.get("references", [])
        if row.get("target_symbol_id") in old_ids
    ]
    new_references = [
        row
        for row in facts.get("references", [])
        if row.get("target_symbol_id") in new_ids
    ]
    unresolved = [
        row
        for row in facts.get("references", [])
        if not row.get("resolved") and row.get("source") in {old, new}
    ]
    boundaries = [
        row
        for row in facts.get("boundaries", [])
        if row.get("kind")
        in {
            "reflection_or_runtime_name_lookup",
            "dynamic_dispatch",
            "excluded_generated_input",
            "excluded_vendor_input",
            "partial_declaration",
            "override_dispatch",
            "delegate_or_method_group",
        }
    ]
    reasons: list[str] = []
    if len(new_declarations) != 1:
        reasons.append("exactly one selected-source declaration for the new concept is required")
    if old_declarations or old_references:
        reasons.append("resolved old declaration or reference remains")
    if unresolved:
        reasons.append("unresolved old/new spelling requires manual classification")
    if boundaries:
        reasons.append(
            "runtime-name, generated/vendor, partial, dispatch, or delegate boundaries require external review"
        )
    verdict = (
        "CANDIDATE COMPLETE — EXTERNAL/DYNAMIC API REVIEW REQUIRED"
        if not reasons
        else ("HALF-APPLIED / INCOMPLETE" if new_declarations or new_references else "INCOMPLETE")
    )
    return {
        "old_concept": old,
        "new_concept": new,
        "verdict": verdict,
        "assess_only": True,
        "source_mutated": False,
        "old_source_declarations": old_declarations,
        "new_source_declarations": new_declarations,
        "old_resolved_references": old_references,
        "new_resolved_references": new_references,
        "unresolved_spellings": unresolved,
        "boundary_evidence": boundaries,
        "reasons": reasons,
    }


def _report(skill: str, payload: dict[str, Any]) -> str:
    count = len(
        payload.get("candidates", payload.get("findings", payload.get("leads", [])))
    )
    lines = [
        f"# {skill} — C#",
        "",
        "> Read-only, exact SDK/Roslyn evidence. Every lead remains review-required.",
        "",
        f"Status: `{payload['status']}`",
        f"Review leads: `{count}`",
    ]
    if "verdict" in payload:
        lines.append(f"Verdict: `{payload['verdict']}`")
    lines.extend(
        ["", "## Boundary", "", *[f"- {item}" for item in payload.get("limits", [])], ""]
    )
    return "\n".join(lines)


def main(skill: str) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    if skill == "rename":
        parser.add_argument("old")
        parser.add_argument("new")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        destination = _safe_destination(root, skill, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    facts, failure = _load(root, args.facts)
    status = "complete" if failure is None else "partial"
    base = {
        "schema_version": f"csharp-roslyn-{skill}-v1",
        "language": "csharp",
        "status": status,
        "read_only": True,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_manifest_sha256": facts.get("source_manifest_sha256"),
        "limits": facts.get("limits", []),
    }
    if failure is not None:
        result: dict[str, Any] = {"deferred": [{"reason": failure}]}
        if skill in {"dormant", "state"}:
            result.update({"candidates": [], "candidate_sha256": _object_hash([])})
        elif skill == "sweep":
            result.update({"findings": [], "finding_sha256": _object_hash([])})
        elif skill == "duplication":
            result.update(
                {
                    "leads": [],
                    "rejected": [{"reason": failure}],
                    "candidate_sha256": _object_hash([]),
                }
            )
        else:
            result.update(_rename({"declarations": [], "references": []}, args.old, args.new))
    elif skill == "dormant":
        result = _dormant(facts)
    elif skill == "state":
        result = _state(facts)
    elif skill == "sweep":
        result = _sweep(facts)
    elif skill == "duplication":
        result = _duplication(facts)
    else:
        result = _rename(facts, args.old, args.new)
    payload = {**base, **result}
    _atomic(destination, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic(destination.with_suffix(".md"), _report(skill, payload))
    return 0 if status == "complete" else 2
