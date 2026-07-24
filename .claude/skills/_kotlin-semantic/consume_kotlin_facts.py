#!/usr/bin/env python3
"""Render five bounded read-only outcomes from a validated Kotlin fact pack."""

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
    "dormant": ("reports/find-dormant/kotlin", "findings.json"),
    "state": ("reports/find-implicit-state/kotlin", "findings.json"),
    "sweep": ("reports/find-incomplete-sweep/kotlin", "manifest.json"),
    "duplication": ("reports/semantic-duplication/kotlin", "analysis.json"),
    "rename": ("reports/rename-concept/kotlin", "assessment.json"),
}


def _object_hash(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode()).hexdigest()


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
    destination = supplied if supplied is not None else Path(filename)
    output = Path(
        os.path.abspath(destination if destination.is_absolute() else allowed / destination)
    )
    try:
        relative = output.relative_to(allowed)
    except ValueError as exc:
        raise ValueError(f"output must stay beneath {relative_root}") from exc
    current = allowed
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("output cannot traverse a symbolic link")
    return output


def _load(root: Path, supplied: Path) -> tuple[dict[str, Any], str | None]:
    path = supplied if supplied.is_absolute() else root / supplied
    try:
        facts = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"status": "partial", "limits": []}, f"fact-pack-unavailable: {exc}"
    if facts.get("status") != "complete":
        return facts, facts.get("failure_kind", "fact-pack-partial")
    if facts.get("project_root") != str(root):
        return facts, "fact-pack-root-mismatch"
    expected_hash = facts.get("fact_pack_sha256")
    unsigned = dict(facts)
    unsigned.pop("fact_pack_sha256", None)
    if expected_hash != _object_hash(unsigned):
        return facts, "fact-pack-hash-mismatch"
    for row in facts.get("source_inventory", []):
        candidate = root / row.get("path", "")
        if (
            not candidate.is_file()
            or candidate.is_symlink()
            or _sha256(candidate) != row.get("sha256")
        ):
            return facts, "fact-pack-stale"
    return facts, None


def _unresolved_for_name(facts: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return [
        {"path": row["path"], "line": row["line"], "source": row.get("source")}
        for row in facts.get("calls", [])
        if not row.get("resolved") and row.get("callee") == name
    ]


def _dormant(facts: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    calls = facts.get("calls", [])
    references = facts.get("references", [])
    for declaration in facts.get("declarations", []):
        if (
            declaration.get("role") != "source"
            or declaration.get("kind") != "function"
            or declaration.get("visibility") != "private"
            or declaration.get("name") == "main"
        ):
            continue
        signature = declaration.get("signature")
        direct = [row for row in calls if row.get("target_signature") == signature]
        callable_refs = [row for row in references if row.get("target_signature") == signature]
        unresolved = _unresolved_for_name(facts, declaration["name"])
        if declaration.get("override") or declaration.get("extension_receiver") or unresolved:
            deferred.append(
                {
                    "fq_name": declaration.get("fq_name"),
                    "reason": "override/extension or unresolved same-name call prevents a dormant lead",
                    "unresolved": unresolved,
                }
            )
        elif not direct and not callable_refs:
            candidates.append(
                {
                    "classification": "review_required_private_no_direct_reference",
                    "fq_name": declaration.get("fq_name"),
                    "signature": signature,
                    "path": declaration["path"],
                    "line": declaration["line"],
                    "human_verdict": "required",
                    "boundary": "not a runtime reachability or safe-delete claim",
                }
            )
    return {
        "candidates": candidates,
        "deferred": deferred,
        "candidate_sha256": _object_hash(candidates),
    }


def _literal(source: str | None) -> str | None:
    if source is None:
        return None
    match = re.fullmatch(r'"([^"$]*)"', source.strip())
    return match.group(1) if match else None


def _state(facts: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    writes = facts.get("writes", [])
    for declaration in facts.get("declarations", []):
        if (
            declaration.get("role") != "source"
            or declaration.get("kind") != "property"
            or declaration.get("name") not in {"state", "status", "phase"}
            or declaration.get("type_text") != "String"
        ):
            continue
        operations = [
            row for row in writes if row.get("target_fq_name") == declaration.get("fq_name")
        ]
        values = {_literal(declaration.get("initializer"))}
        values.update(row.get("string_literal") for row in operations)
        literals = sorted(value for value in values if value is not None)
        if len(literals) >= 2:
            candidates.append(
                {
                    "classification": "review_required_string_state_candidate",
                    "fq_name": declaration.get("fq_name"),
                    "path": declaration["path"],
                    "line": declaration["line"],
                    "literals": literals,
                    "operations": operations,
                    "human_verdict": "required",
                    "boundary": "observed direct writes do not prove a closed runtime state domain",
                }
            )
        else:
            deferred.append(
                {
                    "fq_name": declaration.get("fq_name"),
                    "reason": "fewer than two direct string literals",
                }
            )
    return {
        "candidates": candidates,
        "deferred": deferred,
        "candidate_sha256": _object_hash(candidates),
    }


def _argument_supplied(call: dict[str, Any], parameter: dict[str, Any], index: int) -> bool:
    arguments = call.get("arguments", [])
    if any(row.get("name") == parameter.get("name") for row in arguments):
        return True
    positional = [row for row in arguments if row.get("name") is None]
    return index < len(positional)


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
            groups[str(call.get("target_signature"))].append(call)
    for signature, calls in sorted(groups.items()):
        if len(calls) < 3:
            continue
        parameters = calls[0].get("target_parameters", [])
        for index, parameter in enumerate(parameters):
            if not parameter.get("declares_default"):
                continue
            present = [call for call in calls if _argument_supplied(call, parameter, index)]
            missing = [call for call in calls if not _argument_supplied(call, parameter, index)]
            if len(present) >= 2 and len(missing) == 1:
                straggler = missing[0]
                findings.append(
                    {
                        "classification": "review_required_optional_constructor_argument_sweep_gap",
                        "constructor_signature": signature,
                        "parameter": parameter["name"],
                        "group_size": len(calls),
                        "with_parameter_count": len(present),
                        "straggler": {
                            "path": straggler["path"],
                            "line": straggler["line"],
                            "source": straggler["source"],
                        },
                        "direct_calls": [
                            {"path": row["path"], "line": row["line"], "source": row["source"]}
                            for row in calls
                        ],
                        "human_verdict": "required",
                        "boundary": "direct constructor call-shape evidence, not migration trajectory or behavior",
                    }
                )
            else:
                deferred.append(
                    {
                        "constructor_signature": signature,
                        "parameter": parameter["name"],
                        "reason": "direct constructor group does not contain exactly one omission",
                    }
                )
    return {"findings": findings, "deferred": deferred, "finding_sha256": _object_hash(findings)}


def _normalized_body(source: str | None) -> str:
    return re.sub(r"\s+", " ", source or "").strip()


def _duplication(facts: dict[str, Any]) -> dict[str, Any]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    calls = facts.get("calls", [])
    rejected: list[dict[str, Any]] = []
    for declaration in facts.get("declarations", []):
        if (
            declaration.get("role") != "source"
            or declaration.get("kind") != "function"
            or declaration.get("override")
            or declaration.get("extension_receiver")
        ):
            continue
        body = _normalized_body(declaration.get("body"))
        if not body:
            continue
        shape = (
            tuple(row.get("type") for row in declaration.get("parameters", [])),
            declaration.get("return_type"),
            body,
        )
        groups[shape].append(declaration)
    leads: list[dict[str, Any]] = []
    for (_parameters, _return_type, body), declarations in groups.items():
        if len(declarations) != 2 or len({row.get("fq_name") for row in declarations}) != 2:
            continue
        functions = []
        for declaration in declarations:
            contexts = [
                {"path": row["path"], "line": row["line"], "caller": row.get("caller")}
                for row in calls
                if row.get("target_signature") == declaration.get("signature")
                and row.get("role") == "source"
            ]
            if not contexts:
                rejected.append(
                    {
                        "fq_name": declaration.get("fq_name"),
                        "reason": "no distinct direct production caller context",
                    }
                )
                break
            functions.append(
                {
                    "fq_name": declaration.get("fq_name"),
                    "signature": declaration.get("signature"),
                    "path": declaration["path"],
                    "line": declaration["line"],
                    "direct_caller_contexts": contexts,
                }
            )
        if len(functions) == 2:
            leads.append(
                {
                    "id": f"KSD-{len(leads) + 1:02d}",
                    "classification": "review_required_resolved_contract_and_body_shape_lead",
                    "functions": functions,
                    "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "human_verdict": "required",
                    "boundary": "matching static signature/body shape and direct callers do not prove behavioral equivalence",
                }
            )
    return {"leads": leads, "rejected": rejected, "candidate_sha256": _object_hash(leads)}


def _matches(row: dict[str, Any], concept: str) -> bool:
    return row.get("name") == concept or str(row.get("fq_name", "")).rsplit(".", 1)[-1] == concept


def _rename(facts: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    declarations = [
        row
        for row in facts.get("declarations", [])
        if row.get("role") == "source"
        and row.get("kind") in {"class", "interface", "enum", "object"}
    ]
    old_declarations = [row for row in declarations if _matches(row, old)]
    new_declarations = [row for row in declarations if _matches(row, new)]
    old_signatures = {row.get("signature") for row in old_declarations}
    new_signatures = {row.get("signature") for row in new_declarations}
    old_references = [
        row for row in facts.get("references", []) if row.get("target_signature") in old_signatures
    ]
    new_references = [
        row for row in facts.get("references", []) if row.get("target_signature") in new_signatures
    ]
    unresolved = [
        row
        for row in facts.get("references", [])
        if not row.get("resolved") and row.get("source") in {old, new}
    ]
    reasons: list[str] = []
    if len(new_declarations) != 1:
        reasons.append("exactly one selected-source declaration for the new concept is required")
    if old_declarations or old_references:
        reasons.append("resolved old declaration or reference remains")
    if unresolved:
        reasons.append("unresolved old/new spelling requires manual classification")
    verdict = (
        "CANDIDATE COMPLETE — EXTERNAL/DYNAMIC API REVIEW REQUIRED"
        if not reasons
        else ("HALF-APPLIED / INCOMPLETE" if new_declarations or new_references else "INCOMPLETE")
    )
    return {
        "old_concept": old,
        "new_concept": new,
        "verdict": verdict,
        "old_source_declarations": old_declarations,
        "new_source_declarations": new_declarations,
        "old_resolved_references": old_references,
        "new_resolved_references": new_references,
        "unresolved_spellings": unresolved,
        "reasons": reasons,
    }


def _report(skill: str, payload: dict[str, Any]) -> str:
    count = len(payload.get("candidates", payload.get("findings", payload.get("leads", []))))
    lines = [
        f"# {skill} — Kotlin/JVM",
        "",
        "> Read-only, pinned compiler evidence. Every candidate remains review-required.",
        "",
        f"Status: `{payload['status']}`",
        f"Review leads: `{count}`",
    ]
    if "verdict" in payload:
        lines.append(f"Verdict: `{payload['verdict']}`")
    lines.extend(["", "## Boundary", "", *[f"- {item}" for item in payload.get("limits", [])], ""])
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
        "schema_version": f"kotlin-jvm-{skill}-v1",
        "language": "kotlin",
        "status": status,
        "read_only": True,
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "source_manifest_sha256": facts.get("source_manifest_sha256"),
        "limits": facts.get("limits", []),
    }
    if failure is not None:
        result: dict[str, Any] = {"deferred": [{"reason": failure}]}
        if skill == "dormant" or skill == "state":
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
