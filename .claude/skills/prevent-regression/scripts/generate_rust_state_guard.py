#!/usr/bin/env python3
"""Stage a narrow Cargo compile-time guard from an accepted Rust enum review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any


NONCLAIMS = [
    "macro expansions",
    "build-script or include! output",
    "unselected cfg or target variants",
    "trait dispatch or generic owners",
    "unsafe or FFI behavior",
    "serialization or wire compatibility",
    "public API compatibility",
]
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RustGuardError(ValueError):
    """Rejected review, stale evidence, or unsupported exact guard shape."""


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve(root: Path, supplied: str, label: str) -> Path:
    raw = Path(supplied)
    candidate = raw if raw.is_absolute() else root / raw
    if candidate.is_symlink():
        raise RustGuardError(f"{label} must not be a symbolic link: {supplied}")
    resolved = candidate.resolve(strict=False)
    if not _inside(root, resolved):
        raise RustGuardError(f"{label} must stay inside project root: {supplied}")
    return resolved


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RustGuardError(f"cannot read {label}: {error}") from error
    if not isinstance(payload, dict):
        raise RustGuardError(f"{label} must be a JSON object")
    return payload


def _load(
    root: Path, targets_arg: str, review_arg: str
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    targets = _resolve(root, targets_arg, "targets")
    review = _resolve(root, review_arg, "accepted review")
    allowed = root / "reports" / "extract-enum"
    if not _inside(allowed, targets) or not _inside(allowed, review):
        raise RustGuardError("targets and accepted review must stay beneath reports/extract-enum/")
    data = _json(targets, "Rust enum targets")
    accepted = _json(review, "Rust accepted review")
    if (
        data.get("schema_version") != "rust-enum-proposal-v1"
        or data.get("language") != "rust"
        or data.get("status") != "review_required"
        or data.get("outcome") != "proposal_ready"
        or data.get("read_only") is not True
    ):
        raise RustGuardError("targets are not one review-required Rust enum proposal")
    if (
        accepted.get("schema_version") != "rust-enum-review-v1"
        or accepted.get("status") != "accepted"
    ):
        raise RustGuardError("a separately accepted rust-enum-review-v1 artifact is required")
    digest = hashlib.sha256(targets.read_bytes()).hexdigest()
    if accepted.get("targets_sha256") != digest:
        raise RustGuardError("accepted review is stale for the supplied targets")
    if accepted.get("authority") != data.get("authority"):
        raise RustGuardError("accepted review exact authority differs from the proposal")
    if accepted.get("accepted_nonclaims") != NONCLAIMS or data.get("nonclaims") != NONCLAIMS:
        raise RustGuardError("accepted review must preserve every bounded Rust non-claim")
    return targets, data, accepted


def _validate(root: Path, data: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    authority = data.get("authority")
    enum = review.get("enum")
    guard = review.get("guard")
    if not all(isinstance(item, dict) for item in (authority, enum, guard)):
        raise RustGuardError("accepted review authority, enum, and guard sections are required")
    required_authority = (
        "target",
        "owner",
        "field",
        "declaration_file",
        "source_sha256",
        "owner_visibility",
        "visibility",
    )
    if any(
        not isinstance(authority.get(key), str) or not authority[key] for key in required_authority
    ):
        raise RustGuardError("proposal exact field authority is malformed")
    if authority["visibility"] != "public" or authority["owner_visibility"] != "public":
        raise RustGuardError(
            "partial: the staged integration-test guard supports only a public owner and field"
        )
    source = _resolve(root, authority["declaration_file"], "authority source")
    if (
        not source.is_file()
        or hashlib.sha256(source.read_bytes()).hexdigest() != authority["source_sha256"]
    ):
        raise RustGuardError("proposal exact field authority is stale")
    lines = source.read_text(encoding="utf-8").splitlines()
    declaration_line = authority.get("declaration_line")
    if not isinstance(declaration_line, int) or not 1 <= declaration_line <= len(lines):
        raise RustGuardError("proposal exact field line is invalid")
    if (
        re.fullmatch(
            rf"\s*pub\s+{re.escape(authority['field'])}\s*:\s*(?:String|std::string::String)\s*,?\s*",
            lines[declaration_line - 1],
        )
        is None
    ):
        raise RustGuardError("proposal exact public String field authority is stale")
    proposed = data.get("proposed_enum")
    if (
        not isinstance(proposed, dict)
        or enum.get("type_name") != proposed.get("type_name")
        or enum.get("variants") != proposed.get("variants")
    ):
        raise RustGuardError("accepted enum differs from the proposal; collect a new exact review")
    for key in ("type_name", "crate_import", "module_path"):
        if not isinstance(enum.get(key), str) or not enum[key]:
            raise RustGuardError(f"accepted enum lacks {key}")
    if not IDENTIFIER.fullmatch(enum["type_name"]) or not IDENTIFIER.fullmatch(
        enum["crate_import"]
    ):
        raise RustGuardError("accepted enum type/crate import is not a Rust identifier")
    module_parts = enum["module_path"].split("::")
    if not module_parts or any(IDENTIFIER.fullmatch(part) is None for part in module_parts):
        raise RustGuardError("accepted enum module path is invalid")
    package, destination = guard.get("package"), guard.get("test_destination")
    if not isinstance(package, str) or not package or not isinstance(destination, str):
        raise RustGuardError("accepted guard package and destination are required")
    relative = Path(destination)
    if (
        relative.is_absolute()
        or relative.suffix != ".rs"
        or ".." in relative.parts
        or len(relative.parts) < 3
        or relative.parts[0] != package
        or relative.parts[1] != "tests"
    ):
        raise RustGuardError("guard destination must be <package>/tests/<name>.rs")
    return {"authority": authority, "enum": enum, "guard": guard}


def _guard_text(data: dict[str, Any]) -> str:
    authority, enum = data["authority"], data["enum"]
    module = f"::{enum['module_path']}" if enum["module_path"] else ""
    return f"""//! Project-owned exact-field regression guard.
//!
//! This compile-time assertion protects only `{authority["owner"]}.{authority["field"]}`.

use {enum["crate_import"]}{module}::{{{authority["owner"]}, {enum["type_name"]}}};

fn assert_exact_field_type(value: &{authority["owner"]}) {{
    let _: &{enum["type_name"]} = &value.{authority["field"]};
}}

#[test]
fn {authority["owner"].lower()}_{authority["field"]}_remains_typed() {{
    let _: fn(&{authority["owner"]}) = assert_exact_field_type;
}}
"""


def _atomic_stage(output: Path, files: dict[str, str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        for relative, text in files.items():
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")
        temporary.replace(output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--accepted-review", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        root = Path(args.project_root).resolve()
        if not root.is_dir() or root.is_symlink():
            raise RustGuardError("project root must be a non-symlink directory")
        output = _resolve(root, args.output_root, "output root")
        allowed = root / "reports" / "prevent-regression"
        if output == allowed or not _inside(allowed, output):
            raise RustGuardError("output root must stay beneath reports/prevent-regression/")
        shutil.rmtree(output, ignore_errors=True)
        targets, proposal, review = _load(root, args.targets, args.accepted_review)
        data = _validate(root, proposal, review)
        guard_text = _guard_text(data)
        metadata = {
            "schema_version": "rust-state-guard-v1",
            "language": "rust",
            "status": "staged",
            "outcome": "exact_native_guard",
            "targets_sha256": hashlib.sha256(targets.read_bytes()).hexdigest(),
            "guard_sha256": hashlib.sha256(guard_text.encode()).hexdigest(),
            **data,
            "nonclaims": NONCLAIMS,
        }
        destination = data["guard"]["test_destination"]
        files = {
            "guard/exact_field_type_guard.rs": guard_text,
            "authority.json": json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            "host-wiring.diff": (
                "# Review and copy; this stage does not mutate the host source tree.\n"
                f"+ copy guard/exact_field_type_guard.rs to {destination}\n"
                "+ cargo test --locked --offline --workspace --all-targets --all-features\n"
                "+ cargo clippy --locked --offline --workspace --all-targets --all-features -- -D warnings\n"
                "+ cargo fmt --all -- --check\n"
            ),
        }
        _atomic_stage(output, files)
    except (RustGuardError, OSError, UnicodeError, KeyError, TypeError) as error:
        if output is not None:
            shutil.rmtree(output, ignore_errors=True)
        print(f"[generate_rust_state_guard] ERROR: {error}", file=sys.stderr)
        return 2
    print(
        f"[generate_rust_state_guard] staged {data['authority']['owner']}.{data['authority']['field']} at {output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
