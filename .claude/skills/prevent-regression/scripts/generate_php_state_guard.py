#!/usr/bin/env python3
"""Stage an exact PHP enum-property guard from one accepted enum proposal."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


def _library() -> Any:
    local = Path(__file__).with_name("php_proposal_evidence.py")
    canonical = Path(__file__).resolve().parents[2] / "_php-proposal/php_proposal_evidence.py"
    path = local if local.is_file() else canonical
    spec = importlib.util.spec_from_file_location("php_proposal_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("php_proposal_evidence.py is missing from the copied closure")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


E = _library()
NONCLAIMS = [
    "this exact type assertion is a general PHP state lint",
    "enum cases, serialization, storage, wire, or framework behavior are protected",
    "dynamic, inherited, trait, reflected, or external state authorities are covered",
    "staging authorizes installation into the host project",
]


def _stage(root: Path, proposal: dict[str, Any], acceptance: dict[str, Any]) -> tuple[dict[str, Any], str]:
    decision = acceptance.get("decision")
    if decision == "defer_no_guard_policy":
        return ({
            "schema_version": "php-state-guard-v1", "language": "php",
            "status": "deferred", "outcome": "defer_no_guard_policy",
            "read_only": True, "nonclaims": NONCLAIMS,
        }, "")
    if decision != "stage_guard":
        raise E.EvidenceError("acceptance_invalid", "guard decision is unsupported")
    if (
        proposal.get("schema_version") != "php-enum-proposal-v1"
        or proposal.get("status") != "review_required"
        or proposal.get("outcome") != "proposal_ready"
    ):
        raise E.EvidenceError("evidence_invalid", "one review-required PHP enum proposal is required")
    selection = acceptance.get("selection")
    authority = proposal.get("authority")
    if not isinstance(selection, dict) or not isinstance(authority, dict):
        raise E.EvidenceError("selection_invalid", "guard authority is missing")
    for file_key, hash_key in (("enum_file", "enum_sha256"), ("authority_file", "authority_sha256")):
        relative, digest = selection.get(file_key), selection.get(hash_key)
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise E.EvidenceError("selection_invalid", f"guard selection lacks {file_key}")
        path = E.safe_path(root, relative, file_key)
        if not path.is_file() or E.sha256(path) != digest:
            raise E.EvidenceError("evidence_stale", f"accepted migrated source is stale: {relative}")
    if authority.get("file") != selection.get("authority_file"):
        raise E.EvidenceError("selection_invalid", "migrated field must retain the accepted authority file")
    fqcn, field, enum_type = authority.get("fqcn"), authority.get("field"), selection.get("enum_type")
    destination = selection.get("guard_destination")
    if not all(isinstance(item, str) and item for item in (fqcn, field, enum_type, destination)):
        raise E.EvidenceError("selection_invalid", "exact guard identity/destination is incomplete")
    destination_path = Path(destination)
    if destination_path.is_absolute() or ".." in destination_path.parts or destination_path.suffix != ".php":
        raise E.EvidenceError("selection_invalid", "guard destination must be a safe PHP path")
    guard = f"""<?php

declare(strict_types=1);

// Project-owned exact-field type guard; invoke with the project root.
$root = $argv[1] ?? '';
if ($root === '' || !is_dir($root)) {{
    fwrite(STDERR, "project root required\\n");
    exit(2);
}}
require $root . '/{selection['enum_file']}';
require $root . '/{selection['authority_file']}';
$property = new ReflectionProperty('{fqcn}', '{field}');
$type = $property->getType();
if (!$type instanceof ReflectionNamedType || $type->getName() !== '{enum_type}') {{
    fwrite(STDERR, "{fqcn}::{field} must remain {enum_type}\\n");
    exit(1);
}}
echo "php-state-guard-ok\\n";
"""
    metadata = {
        "schema_version": "php-state-guard-v1", "language": "php", "status": "staged",
        "outcome": "exact_native_guard", "read_only": True,
        "authority": authority, "selection": selection,
        "guard_sha256": __import__("hashlib").sha256(guard.encode()).hexdigest(),
        "project_identity": proposal.get("project_identity"),
        "native": acceptance.get("native"), "nonclaims": NONCLAIMS,
    }
    return metadata, guard


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project-root", "evidence", "acceptance", "output-dir", "php", "composer"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    destination: Path | None = None
    try:
        destination = E.output_dir(root, args.output_dir, "prevent-regression")
        E.begin(destination)
        _, proposal, acceptance, native = E.validate(
            root=root, consumer="prevent-regression", evidence_arg=args.evidence,
            acceptance_arg=args.acceptance, php=args.php, composer=args.composer,
            allowed_evidence_statuses={"review_required"}, verify_evidence_sources=False,
        )
        metadata, guard = _stage(root, proposal, acceptance)
        metadata["native_evidence"] = native
        files = {"authority.json": E.json_text(metadata)}
        if metadata["status"] == "staged":
            files["guard/exact_field_type_guard.php"] = guard
            files["host-wiring.diff"] = (
                "# Human-reviewed installation only; generator edits no host source.\n"
                f"+ copy guard/exact_field_type_guard.php to {metadata['selection']['guard_destination']}\n"
                "+ run accepted Composer/PHP native checks\n"
            )
        E.replace_bundle(destination, files)
    except (AttributeError, OSError, UnicodeError, KeyError, TypeError, ValueError) as error:
        if destination is not None:
            E.refuse(destination, "prevent-regression", error)
        print(f"[generate_php_state_guard] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
