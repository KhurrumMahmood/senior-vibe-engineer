#!/usr/bin/env python3
"""Stage one Clang/C17 exact-field-type guard from an accepted C migration."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import shutil
import sys
from pathlib import Path
from typing import Any


def _evidence() -> Any:
    path = Path(__file__).with_name("c_state_guard_evidence.py")
    spec = importlib.util.spec_from_file_location("c_state_guard_generate_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("copied C guard evidence helper is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


E = _evidence()
REQUIRED_APPROVALS = {
    "abi": "approved",
    "external": "approved",
    "storage": "approved",
    "wire": "approved",
}
NONCLAIMS = [
    "this exact field-type assertion is a general C state lint",
    "enumerators, values, aliases, callbacks, macros, or inactive variants are protected",
    "ABI, wire, storage, serialization, or external compatibility remains correct after approval",
    "staging authorizes installation into the host project",
]


def _targets(root: Path, supplied: str) -> tuple[Path, dict[str, Any]]:
    path = E.artifact(root, supplied, "enum targets", "extract-enum")
    payload = E.load_json(path, "C enum targets")
    authority = payload.get("authority")
    enum = payload.get("proposed_enum")
    if (
        payload.get("schema_version") != "c-enum-proposal-v1"
        or payload.get("language") != "c"
        or payload.get("status") != "review_required"
        or payload.get("outcome") != "proposal_ready"
        or payload.get("read_only") is not True
        or payload.get("source_mutations") != 0
        or not isinstance(authority, dict)
        or authority.get("type") != "const char *"
        or not all(
            isinstance(authority.get(key), str) and authority[key]
            for key in ("owner", "field", "declaration_file")
        )
        or not isinstance(enum, dict)
        or not isinstance(enum.get("name"), str)
        or not enum["name"]
    ):
        raise E.EvidenceError(
            "evidence_invalid", "one review-required exact C string-field proposal is required"
        )
    return path, payload


def _safe_relative(value: Any, label: str, suffix: str | None = None) -> str:
    if (
        not isinstance(value, str)
        or not value
        or Path(value).is_absolute()
        or ".." in Path(value).parts
        or (suffix is not None and Path(value).suffix != suffix)
    ):
        raise E.EvidenceError("migration_invalid", f"{label} is unsafe")
    return value


def _native(migration: dict[str, Any]) -> dict[str, Any]:
    native = migration.get("native")
    if not isinstance(native, dict):
        raise E.EvidenceError("migration_invalid", "accepted native obligations are missing")
    compile_target = native.get("compile_database_target")
    make_target = native.get("make_target")
    if not all(
        isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", value)
        for value in (compile_target, make_target)
    ):
        raise E.EvidenceError("migration_invalid", "accepted Make targets are malformed")
    smoke_path = _safe_relative(native.get("smoke_path"), "smoke path")
    smoke_stdout = native.get("smoke_stdout")
    flags = native.get("guard_cflags")
    if (
        not isinstance(smoke_stdout, str)
        or not isinstance(flags, list)
        or "-std=c17" not in flags
        or not all(isinstance(flag, str) and flag and "\x00" not in flag for flag in flags)
    ):
        raise E.EvidenceError("migration_invalid", "accepted C17 guard flags or smoke are invalid")
    return {
        "compile_database_target": compile_target,
        "make_target": make_target,
        "smoke_path": smoke_path,
        "smoke_stdout": smoke_stdout,
        "guard_cflags": flags,
    }


def _replacement(value: Any, label: str, sources: dict[str, str]) -> dict[str, str]:
    if not isinstance(value, dict):
        raise E.EvidenceError("migration_invalid", f"{label} is missing")
    relative = _safe_relative(value.get("path"), f"{label} path")
    before, after = value.get("before"), value.get("after")
    if (
        relative not in sources
        or not isinstance(before, str)
        or not before
        or not isinstance(after, str)
        or before == after
    ):
        raise E.EvidenceError("migration_invalid", f"{label} is malformed")
    return {"path": relative, "before": before, "after": after}


def _migration(root: Path, proposal: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    if review.get("approvals") != REQUIRED_APPROVALS:
        raise E.EvidenceError(
            "approval_required", "ABI, wire, storage, and external approvals are all required"
        )
    migration = review.get("migration")
    if not isinstance(migration, dict):
        raise E.EvidenceError("migration_invalid", "accepted migration authority is missing")
    enum_type = migration.get("enum_type")
    if enum_type != proposal["proposed_enum"]["name"]:
        raise E.EvidenceError("migration_invalid", "accepted enum type differs from the proposal")
    header_include = _safe_relative(migration.get("header_include"), "header include", ".h")
    authority = proposal["authority"]
    if (Path("include") / header_include).as_posix() != authority["declaration_file"]:
        raise E.EvidenceError("migration_invalid", "header include differs from exact field authority")
    sources = E.validate_sources(
        root,
        migration.get("migrated_sources"),
        kind="migration_stale",
    )
    if authority["declaration_file"] not in sources:
        raise E.EvidenceError("migration_invalid", "migrated field source lacks a current hash")
    destination = _safe_relative(
        migration.get("guard_destination"), "guard destination", ".c"
    )
    regression = migration.get("seeded_regression")
    if not isinstance(regression, dict):
        raise E.EvidenceError("migration_invalid", "buildable seeded regression plan is missing")
    field_replacement = _replacement(
        regression.get("field_replacement"), "field replacement", sources
    )
    expected_before = f"{enum_type} {authority['field']};"
    expected_after = f"const char *{authority['field']};"
    if (
        field_replacement["path"] != authority["declaration_file"]
        or field_replacement["before"].strip() != expected_before
        or field_replacement["after"].strip() != expected_after
    ):
        raise E.EvidenceError(
            "migration_invalid", "seeded regression must revert the exact field to const char *"
        )
    caller_values = regression.get("caller_replacements")
    if not isinstance(caller_values, list) or not caller_values:
        raise E.EvidenceError("migration_invalid", "buildable caller regression plan is missing")
    callers = [
        _replacement(value, "caller replacement", sources) for value in caller_values
    ]
    for replacement in [field_replacement, *callers]:
        text = (root / replacement["path"]).read_text(encoding="utf-8")
        if text.count(replacement["before"]) != 1:
            raise E.EvidenceError(
                "migration_stale", f"accepted regression anchor is stale: {replacement['path']}"
            )
    return {
        "enum_type": enum_type,
        "header_include": header_include,
        "migrated_sources": migration["migrated_sources"],
        "guard_destination": destination,
        "native": _native(migration),
        "seeded_regression": {
            "field_replacement": field_replacement,
            "caller_replacements": callers,
        },
    }


def _guard(authority: dict[str, Any], migration: dict[str, Any]) -> str:
    owner, field = authority["owner"], authority["field"]
    enum_type = migration["enum_type"]
    return f'''/* Staged exact-field C17 guard; human-reviewed installation only. */
#include "{migration['header_include']}"

_Static_assert(
    _Generic((({owner} *)0)->{field}, {enum_type}: 1, default: 0),
    "{owner}.{field} must remain {enum_type}"
);
'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--accepted-review", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or Path(args.project_root).is_symlink():
            raise E.EvidenceError("unsafe_path", "project root must be a non-symlink directory")
        output = E.artifact(root, args.output_dir, "output directory", "prevent-regression")
        shutil.rmtree(output, ignore_errors=True)
        targets_path, proposal = _targets(root, args.targets)
        review_path = E.safe_path(root, args.accepted_review, "accepted review")
        review = E.load_json(review_path, "accepted C enum review")
        if (
            review.get("schema_version") != "c-enum-proposal-review-v1"
            or review.get("language") != "c"
            or review.get("status") != "accepted"
            or review.get("decision") != "approve_exact_field_guard"
            or review.get("targets_sha256") != E.sha256(targets_path)
            or review.get("authority") != proposal["authority"]
        ):
            raise E.EvidenceError(
                "accepted_review_invalid", "fresh explicit acceptance of the exact C proposal is required"
            )
        migration = _migration(root, proposal, review)
        guard = _guard(proposal["authority"], migration)
        metadata = {
            "schema_version": "c-state-guard-v1",
            "language": "c",
            "status": "staged",
            "outcome": "exact_field_type_guard",
            "installed": False,
            "source_mutations": 0,
            "targets_sha256": E.sha256(targets_path),
            "review_sha256": E.sha256(review_path),
            "guard_sha256": hashlib.sha256(guard.encode()).hexdigest(),
            "authority": proposal["authority"],
            "proposed_enum": proposal["proposed_enum"],
            "approvals": review["approvals"],
            "migration": migration,
            "nonclaims": NONCLAIMS,
        }
        E.replace_bundle(
            output,
            {
                "authority.json": E.json_text(metadata),
                "guard/exact_field_type_guard.c": guard,
                "host-wiring.diff": (
                    "# Staged only; review and copy explicitly. No host file was changed.\n"
                    f"+ copy guard/exact_field_type_guard.c to {migration['guard_destination']}\n"
                    "+ compile it with the accepted Clang/C17 host flags\n"
                    "+ run the accepted Make target and exact native smoke\n"
                ),
            },
        )
    except (E.EvidenceError, OSError, UnicodeError, KeyError, TypeError) as error:
        kind = error.kind if isinstance(error, E.EvidenceError) else "guard_stage_failed"
        if output is not None:
            E.replace_bundle(
                output,
                {
                    "refusal.json": E.json_text(
                        {
                            "schema_version": "c-state-guard-refusal-v1",
                            "language": "c",
                            "status": "refused",
                            "outcome": "no_guard",
                            "failure_kind": kind,
                            "message": str(error),
                        }
                    )
                },
            )
        print(f"[generate_c_state_guard] ERROR: {kind}: {error}", file=sys.stderr)
        return 2
    print(
        f"[generate_c_state_guard] staged {proposal['authority']['owner']}."
        f"{proposal['authority']['field']} at {output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
