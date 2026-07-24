#!/usr/bin/env python3
"""Audit decision propagation, subsystem coverage, and deferred obligations.

The audit is intentionally read-only.  It does not infer project topology from
framework names: hosts declare first-party surface roots and grouping in
``.engineering/project/surfaces.json``.  The audit then asks whether every
derived candidate is registered or explicitly exempted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import decisions as decision_registry  # noqa: E402
import precedents as precedent_registry  # noqa: E402


ROOT = SCRIPT_DIR.parent
SURFACES = (
    "code",
    "skill-prose",
    "durable-docs",
    "tests",
    "generated-projections",
    "host-configuration-state",
    "migration",
    "release",
)
TEXT_SUFFIXES = {".json", ".md", ".py", ".yaml", ".yml"}
ACTIVE_REFERENCE_ROOTS = (
    "README.md",
    "docs",
    ".augment/rules/imported",
    ".claude/skills",
    ".claude/docs",
    "scripts",
    "ai-docs/decisions",
    ".engineering",
)


class CoherenceError(ValueError):
    """A declared coherence artifact is invalid."""


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoherenceError(f"cannot read JSON: {path}") from exc


def _relative(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CoherenceError(f"{field} must be a non-empty project-relative path")
    path = PurePosixPath(value.strip())
    if path.is_absolute() or ".." in path.parts:
        raise CoherenceError(f"{field} must be a project-relative path")
    return path.as_posix()


def _strings(value: object, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise CoherenceError(f"{field} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise CoherenceError(f"{field} must not be empty")
    return [item.strip() for item in value]


def _idea_ids(root: Path) -> set[str]:
    path = root / ".claude" / "ideas" / "log.jsonl"
    if not path.is_file():
        return set()
    result: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            result.add(row["id"])
    return result


def validate_impact(payload: object, root: Path) -> dict[str, Any]:
    """Validate one complete decision-impact disposition set."""
    errors: list[str] = []
    deferred: list[str] = []
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return {"valid": False, "errors": ["unsupported decision-impact schema"]}
    decision = payload.get("decision")
    if not isinstance(decision, str) or not decision:
        errors.append("decision must be a non-empty string")
    obligations = payload.get("obligations")
    if not isinstance(obligations, list):
        return {"valid": False, "errors": [*errors, "obligations must be a list"]}
    seen: set[str] = set()
    ideas = _idea_ids(root)
    for index, row in enumerate(obligations):
        prefix = f"obligations[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        surface = row.get("surface")
        if surface not in SURFACES:
            errors.append(f"{prefix}.surface is invalid")
            continue
        if surface in seen:
            errors.append(f"duplicate obligation surface: {surface}")
        seen.add(surface)
        disposition = row.get("disposition")
        if disposition == "complete":
            try:
                evidence = _strings(row.get("evidence"), f"{prefix}.evidence")
                for raw in evidence:
                    relative = _relative(raw, f"{prefix}.evidence")
                    if not (root / relative).exists():
                        errors.append(f"{prefix}.evidence does not exist: {relative}")
            except CoherenceError as exc:
                errors.append(str(exc))
        elif isinstance(disposition, str) and disposition.startswith("deferred:"):
            work_item = disposition.partition(":")[2]
            if not work_item:
                errors.append(f"{prefix}.disposition has no work item")
            elif work_item not in ideas:
                errors.append(f"{prefix} references unknown deferred work item: {work_item}")
            else:
                deferred.append(work_item)
            if not isinstance(row.get("review_trigger"), str) or not row[
                "review_trigger"
            ].strip():
                errors.append(f"{prefix}.review_trigger is required when deferred")
            try:
                source_links = _strings(
                    row.get("source_links"), f"{prefix}.source_links"
                )
                for raw in source_links:
                    relative = _relative(raw, f"{prefix}.source_links")
                    if not (root / relative).exists():
                        errors.append(
                            f"{prefix}.source_links does not exist: {relative}"
                        )
            except CoherenceError as exc:
                errors.append(str(exc))
        elif isinstance(disposition, str) and disposition.startswith("not-applicable:"):
            if not disposition.partition(":")[2].strip():
                errors.append(f"{prefix}.disposition has no reason")
        else:
            errors.append(f"{prefix}.disposition is invalid")
    missing = sorted(set(SURFACES) - seen)
    if missing:
        errors.append(f"missing obligation surfaces: {', '.join(missing)}")

    fallbacks = payload.get("legacy_fallbacks")
    if not isinstance(fallbacks, list):
        errors.append("legacy_fallbacks must be a list")
        fallbacks = []
    legacy_seen: set[str] = set()
    for index, row in enumerate(fallbacks):
        prefix = f"legacy_fallbacks[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        try:
            legacy = _relative(row.get("legacy"), f"{prefix}.legacy")
            _relative(row.get("canonical"), f"{prefix}.canonical")
            _strings(
                row.get("allowed_reference_prefixes"),
                f"{prefix}.allowed_reference_prefixes",
            )
        except CoherenceError as exc:
            errors.append(str(exc))
            continue
        if legacy in legacy_seen:
            errors.append(f"duplicate legacy fallback: {legacy}")
        legacy_seen.add(legacy)
        for field in ("owner", "removal_condition", "review_trigger"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
    return {
        "valid": not errors,
        "decision": decision,
        "errors": errors,
        "deferred_work_items": sorted(set(deferred)),
        "legacy_fallbacks": fallbacks,
    }


def _load_registry(path: Path) -> dict[str, dict[str, Any]]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise CoherenceError(f"cannot read subsystem registry: {path}") from exc
    rows = payload.get("subsystems") if isinstance(payload, dict) else None
    if not isinstance(rows, dict) or not all(
        isinstance(name, str) and isinstance(body, dict) for name, body in rows.items()
    ):
        raise CoherenceError("subsystem registry must contain a subsystems mapping")
    return rows


def _matches(path: str, prefix: str) -> bool:
    path = path[2:] if path.startswith("./") else path
    prefix = prefix[2:] if prefix.startswith("./") else prefix
    return path == prefix.rstrip("/") or (
        prefix.endswith("/") and path.startswith(prefix)
    )


def _registry_owners(path: str, registry: dict[str, dict[str, Any]]) -> list[str]:
    matches: list[tuple[int, str]] = []
    for name, body in registry.items():
        for prefix in body.get("paths", []):
            if isinstance(prefix, str) and _matches(path, prefix):
                matches.append((len(prefix), name))
    if not matches:
        return []
    longest = max(length for length, _ in matches)
    return sorted({name for length, name in matches if length == longest})


def _entry_count(path: Path) -> int:
    if path.is_file():
        return 1
    return sum(1 for item in path.rglob("*") if item.is_file() and "__pycache__" not in item.parts)


def audit_registry(root: Path) -> dict[str, Any]:
    """Derive declared first-party candidates, then register or exempt each."""
    profile_path = root / ".engineering" / "project" / "surfaces.json"
    registry_path = root / ".engineering" / "subsystems.yaml"
    try:
        profile = _read_json(profile_path)
        if not isinstance(profile, dict) or profile.get("schema_version") != 1:
            raise CoherenceError("surface profile has an unsupported schema")
        root_rows = profile.get("first_party_surface_roots")
        exemptions = profile.get("exemptions", [])
        if not isinstance(root_rows, list) or not isinstance(exemptions, list):
            raise CoherenceError("surface roots and exemptions must be lists")
        registry = _load_registry(registry_path)
    except CoherenceError as exc:
        return {"status": "invalid", "errors": [str(exc)], "candidates": [], "integrity": []}

    candidates: dict[str, set[str]] = {}
    errors: list[str] = []
    for index, row in enumerate(root_rows):
        if not isinstance(row, dict):
            errors.append(f"surface root {index} must be an object")
            continue
        try:
            relative = _relative(row.get("path"), f"surface root {index}.path")
        except CoherenceError as exc:
            errors.append(str(exc))
            continue
        group = row.get("group")
        depth = row.get("candidate_depth")
        minimum = row.get("minimum_entries", 1)
        if not isinstance(group, str) or not group or depth not in {0, 1}:
            errors.append(f"surface root {index} has invalid group/candidate_depth")
            continue
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
            errors.append(f"surface root {index}.minimum_entries is invalid")
            continue
        absolute = root / relative
        if not absolute.exists():
            errors.append(f"declared surface root does not exist: {relative}")
            continue
        if depth == 0:
            rows = [(group, absolute, relative)]
        else:
            rows = [
                (f"{group}:{child.name}", child, child.relative_to(root).as_posix())
                for child in sorted(absolute.iterdir())
                if child.is_dir() and not child.is_symlink()
            ]
        for candidate_id, path, candidate_path in rows:
            if _entry_count(path) >= minimum:
                candidates.setdefault(candidate_id, set()).add(candidate_path)

    exemption_map: dict[str, dict[str, Any]] = {}
    for row in exemptions:
        if not isinstance(row, dict) or not isinstance(row.get("candidate"), str):
            errors.append("exemption must name a candidate")
            continue
        if not all(
            isinstance(row.get(field), str) and row[field].strip()
            for field in ("reason", "owner", "review_trigger")
        ):
            errors.append(f"exemption {row['candidate']} is missing review metadata")
            continue
        if row["candidate"] in exemption_map:
            errors.append(f"duplicate exemption: {row['candidate']}")
        exemption_map[row["candidate"]] = row

    candidate_rows = []
    for candidate_id, paths in sorted(candidates.items()):
        owners = {path: _registry_owners(path, registry) for path in sorted(paths)}
        ambiguous = {path: names for path, names in owners.items() if len(names) > 1}
        registered = all(len(names) == 1 for names in owners.values())
        exemption = exemption_map.get(candidate_id)
        if ambiguous:
            disposition = "ambiguous-registration"
            errors.extend(
                f"candidate path has multiple registry owners: {path}: "
                f"{', '.join(names)}"
                for path, names in ambiguous.items()
            )
        elif registered:
            disposition = "registered"
            if exemption:
                errors.append(f"stale exemption for registered candidate: {candidate_id}")
        elif exemption:
            disposition = "exempt"
        elif any(names for names in owners.values()):
            disposition = "partially-registered"
            errors.append(f"candidate is only partially registered: {candidate_id}")
        else:
            disposition = "uncovered"
            errors.append(f"candidate is neither registered nor exempt: {candidate_id}")
        candidate_rows.append(
            {
                "candidate": candidate_id,
                "paths": sorted(paths),
                "owners": owners,
                "disposition": disposition,
                **({"exemption": exemption} if exemption else {}),
            }
        )
    stale_exemptions = sorted(set(exemption_map) - set(candidates))
    errors.extend(f"exemption names no candidate: {item}" for item in stale_exemptions)

    integrity = []
    for name, body in sorted(registry.items()):
        raw_paths = body.get("paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            integrity.append({"subsystem": name, "status": "invalid-paths"})
            errors.append(f"subsystem has no paths: {name}")
            continue
        for raw in raw_paths:
            try:
                relative = _relative(raw, f"subsystem {name} path").rstrip("/")
            except CoherenceError as exc:
                errors.append(str(exc))
                continue
            exists = (root / relative).exists()
            integrity.append(
                {"subsystem": name, "path": raw, "status": "present" if exists else "missing"}
            )
            if not exists:
                errors.append(f"registered path does not exist: {raw}")
    return {
        "status": "pass" if not errors else "findings",
        "errors": errors,
        "candidates": candidate_rows,
        "integrity": integrity,
    }


def _text_files(root: Path) -> Iterable[Path]:
    for relative in ACTIVE_REFERENCE_ROOTS:
        base = root / relative
        if base.is_file():
            yield base
        elif base.is_dir():
            for path in base.rglob("*"):
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and path.suffix in TEXT_SUFFIXES
                    and "__pycache__" not in path.parts
                    and ".engineering/quality/decision-impacts/"
                    not in path.as_posix()
                ):
                    yield path


def _reference_audit(root: Path, fallbacks: list[dict[str, Any]]) -> dict[str, Any]:
    files = list(_text_files(root))
    rows = []
    errors = []
    for fallback in fallbacks:
        legacy = fallback["legacy"]
        allowed = tuple(fallback["allowed_reference_prefixes"])
        references = []
        unclassified = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if legacy not in text:
                continue
            relative = path.relative_to(root).as_posix()
            references.append(relative)
            if not any(relative == prefix or relative.startswith(prefix) for prefix in allowed):
                unclassified.append(relative)
        if unclassified:
            errors.extend(f"unclassified legacy reference {legacy}: {path}" for path in unclassified)
        legacy_present = (root / legacy.rstrip("/")).exists()
        canonical_present = (root / fallback["canonical"].rstrip("/")).exists()
        if legacy_present and canonical_present:
            errors.append(
                f"conflicting canonical and legacy homes are both present: "
                f"{fallback['canonical']} and {legacy}"
            )
        rows.append(
            {
                "legacy": legacy,
                "canonical": fallback["canonical"],
                "legacy_present": legacy_present,
                "canonical_present": canonical_present,
                "references": sorted(references),
                "unclassified_references": sorted(unclassified),
                "owner": fallback["owner"],
                "removal_condition": fallback["removal_condition"],
                "review_trigger": fallback["review_trigger"],
            }
        )
    return {"rows": rows, "errors": errors}


def _scope_contract_audit(root: Path) -> dict[str, Any]:
    contract_path = root / ".claude" / "skills" / "_common" / "scan_scope_contracts.json"
    try:
        payload = _read_json(contract_path)
        rows = payload["skills"] if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise CoherenceError("scope contracts have no skills list")
        declared = {row["skill"] for row in rows if isinstance(row, dict)}
        producers = {
            path.name
            for path in (root / ".claude" / "skills").glob("find-*")
            if path.is_dir()
        }
        rollout = payload.get("adapter_rollout")
        active = isinstance(rollout, dict) and rollout.get("status") == "active"
        missing = sorted(producers - declared)
        extra = sorted(declared - producers)
        paths_missing = []
        if active:
            for field in ("implementation", "conformance"):
                if not (root / rollout.get(field, "")).is_file():
                    paths_missing.append(field)
        errors = [
            *(f"producer missing scope contract: {item}" for item in missing),
            *(f"scope contract names missing producer: {item}" for item in extra),
            *(f"scope rollout path missing: {item}" for item in paths_missing),
        ]
        if not active:
            errors.append("scope adapter rollout is not active")
        return {"status": "pass" if not errors else "findings", "errors": errors}
    except (CoherenceError, KeyError, TypeError) as exc:
        return {"status": "invalid", "errors": [str(exc)]}


def _idea_portability_audit(root: Path) -> dict[str, Any]:
    path = root / ".claude" / "ideas" / "log.jsonl"
    events: dict[str, list[dict[str, Any]]] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                events.setdefault(row["id"], []).append(row)
    findings = []
    for idea_id, rows in events.items():
        host_adoptions = [
            row
            for row in rows
            if row.get("outcome") == "adopted" and "host-a" in str(row.get("summary", ""))
        ]
        clarified = any(row.get("event_kind") == "scope-clarification" for row in rows)
        if host_adoptions and not clarified:
            findings.append(idea_id)
    return {
        "status": "pass" if not findings else "findings",
        "unscoped_host_adoptions": sorted(findings),
    }


def _authority_audit(root: Path) -> dict[str, Any]:
    """Report ADR lifecycle drift and precedent-reference drift.

    Their existing dedicated hooks remain the enforcement owners.  This audit
    composes their structured logic so one coherence report cannot imply that
    authority references were checked when only legacy path strings were read.
    """
    decisions = decision_registry.load_decisions(root / "ai-docs" / "decisions")
    decision_drift = decision_registry._audit_drift(decisions)
    try:
        precedents = precedent_registry.load_precedents(
            root / ".claude" / "docs" / "precedents.yml"
        )
        precedent_drift = precedent_registry.check_precedents(precedents, root)
        precedent_status = "pass" if not precedent_drift else "findings"
    except precedent_registry.PrecedentError as exc:
        precedents = []
        precedent_drift = [str(exc)]
        precedent_status = "invalid"
    return {
        "status": "pass" if not decision_drift and not precedent_drift else "findings",
        "decisions": {
            "status": "pass" if not decision_drift else "findings",
            "count": len(decisions),
            "drift": decision_drift,
            "enforcement_owner": "scripts/decisions.py audit",
        },
        "precedents": {
            "status": precedent_status,
            "count": len(precedents),
            "drift": precedent_drift,
            "enforcement_owner": "scripts/precedents.py check",
        },
    }


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file() and not file.is_symlink() and "__pycache__" not in file.parts:
            digest.update(file.relative_to(path).as_posix().encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()


def _compare_skills(root: Path, compare_root: Path | None) -> dict[str, Any]:
    if compare_root is None:
        return {"status": "not-configured", "differences": []}
    left = root / ".claude" / "skills"
    right = compare_root / ".claude" / "skills"
    if not right.is_dir():
        return {"status": "invalid", "differences": ["comparison root has no skill tree"]}
    names = {path.name for path in left.iterdir() if path.is_dir()} | {
        path.name for path in right.iterdir() if path.is_dir()
    }
    differences = []
    for name in sorted(names):
        a, b = left / name, right / name
        if not a.is_dir() or not b.is_dir():
            differences.append({"skill": name, "reason": "missing-side"})
        elif _tree_digest(a) != _tree_digest(b):
            differences.append({"skill": name, "reason": "content-drift"})
    return {"status": "pass" if not differences else "drift", "differences": differences}


def audit(root: Path, compare_root: Path | None = None) -> dict[str, Any]:
    impact_dir = root / ".engineering" / "quality" / "decision-impacts"
    impacts = []
    impact_errors = []
    fallbacks: list[dict[str, Any]] = []
    for path in sorted(impact_dir.glob("*.json")) if impact_dir.is_dir() else []:
        result = validate_impact(_read_json(path), root)
        impacts.append({"path": path.relative_to(root).as_posix(), **result})
        impact_errors.extend(f"{path.name}: {error}" for error in result["errors"])
        if result["valid"]:
            fallbacks.extend(result["legacy_fallbacks"])
    if not impacts:
        impact_errors.append("no decision-impact artifacts found")
    references = _reference_audit(root, fallbacks)
    registry = audit_registry(root)
    scope = _scope_contract_audit(root)
    portability = _idea_portability_audit(root)
    authorities = _authority_audit(root)
    comparison = _compare_skills(root, compare_root)
    errors = [
        *impact_errors,
        *references["errors"],
        *registry["errors"],
        *scope["errors"],
        *(f"idea portability claim is unscoped: {item}" for item in portability["unscoped_host_adoptions"]),
    ]
    return {
        "schema_version": 1,
        "project_root": str(root),
        "status": "pass" if not errors else "findings",
        "errors": errors,
        "decision_impacts": impacts,
        "legacy_homes_and_references": references["rows"],
        "stale_authority_references": references["errors"],
        "subsystem_coverage": registry,
        "scope_contract_adoption": scope,
        "idea_portability": portability,
        "authority_registry_drift": authorities,
        "skill_tree_comparison": comparison,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--compare-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = audit(
        args.project_root.resolve(),
        args.compare_root.resolve() if args.compare_root else None,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"coherence-audit: {result['status']}")
        for error in result["errors"]:
            print(f"- {error}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
