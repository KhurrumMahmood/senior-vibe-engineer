#!/usr/bin/env python3
"""Stage a dependency-free exact-field Dart guard from accepted evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import sys
import tempfile
from typing import Any
import uuid


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DartGuardError(ValueError):
    """Rejected accepted review, stale authority, or unsupported guard shape."""

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
        raise DartGuardError(
            "partial", "evidence_validator_unavailable", "Dart accepted-evidence validator is missing"
        )
    spec = importlib.util.spec_from_file_location("dart_guard_accepted_evidence", path)
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


def _bounded(root: Path, supplied: Path, boundary: Path, label: str) -> Path:
    raw = supplied if supplied.is_absolute() else root / supplied
    if raw.is_symlink():
        raise DartGuardError("failed", "unsafe_path", f"{label} must not be a symlink")
    path = Path(os.path.realpath(raw.resolve(strict=False)))
    if not _inside(boundary, path):
        raise DartGuardError("failed", "unsafe_path", f"{label} escapes its allowed boundary")
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise DartGuardError("failed", "unsafe_path", f"{label} traverses a symlink")
    return path


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DartGuardError("partial", "accepted_input_unavailable", f"{label} is unavailable") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DartGuardError("failed", "invalid_accepted_input", f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DartGuardError("failed", "invalid_accepted_input", f"{label} must be an object")
    return payload


def _review(
    targets_path: Path,
    review_path: Path,
    validated: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    targets = _json(targets_path, "Dart enum targets")
    review = _json(review_path, "accepted Dart enum proposal")
    if (
        targets.get("schema_version") != "dart-enum-proposal-v1"
        or targets.get("language") != "dart"
        or targets.get("status") != "complete"
        or targets.get("outcome") != "proposal_ready"
        or targets.get("read_only") is not True
    ):
        raise DartGuardError("partial", "proposal_not_ready", "Dart enum proposal is not ready")
    if review.get("schema_version") != "dart-enum-proposal-review-v1":
        raise DartGuardError("failed", "invalid_proposal_review", "proposal review schema is incompatible")
    supplied_hash = review.get("acceptance_hash")
    unhashed = dict(review)
    unhashed.pop("acceptance_hash", None)
    if supplied_hash != _canonical_hash(unhashed):
        raise DartGuardError("failed", "invalid_proposal_review", "proposal acceptance hash does not verify")
    if review.get("status") != "accepted":
        raise DartGuardError("partial", "proposal_acceptance_required", "accepted proposal review is absent")
    if (
        review.get("targets_sha256") != _sha256(targets_path)
        or review.get("accepted_evidence_hash") != targets.get("accepted_evidence_hash")
        or targets.get("accepted_evidence_hash")
        != validated["envelope"].get("acceptance_hash")
        or review.get("candidate_id") != targets.get("candidate_id")
        or review.get("enum") != targets.get("proposed_enum")
        or review.get("native_obligations") != targets.get("native_obligations")
        or review.get("accepted_nonclaims") != targets.get("nonclaims")
    ):
        raise DartGuardError("failed", "stale_proposal_review", "proposal review is stale or unrelated")
    verdict = review.get("human_verdict")
    if not isinstance(verdict, dict) or any(
        not isinstance(verdict.get(key), str) or not verdict[key].strip()
        for key in ("reviewer", "notes")
    ):
        raise DartGuardError("failed", "invalid_proposal_review", "proposal reviewer authority is missing")
    return targets, review


def _relative(value: Any, label: str, first: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise DartGuardError("failed", "invalid_proposal_review", f"{label} is missing")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != first:
        raise DartGuardError("failed", "unsafe_path", f"{label} is outside {first}/")
    return path


def _authority(
    root: Path,
    targets: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    before, after = targets.get("authority"), review.get("authority")
    enum, guard = review.get("enum"), review.get("guard")
    if not all(isinstance(row, dict) for row in (before, after, enum, guard)):
        raise DartGuardError("failed", "invalid_proposal_review", "accepted exact authority is malformed")
    owner, field, expected_type = after.get("owner"), after.get("field"), after.get("expected_type")
    if (
        owner != before.get("owner")
        or field != before.get("field")
        or not isinstance(owner, str)
        or not isinstance(field, str)
        or not isinstance(expected_type, str)
        or not all(IDENTIFIER.fullmatch(value) for value in (owner, field, expected_type))
        or owner.startswith("_")
        or field.startswith("_")
        or after.get("visibility") != "public"
        or after.get("generated") is not False
        or after.get("external_owner") is not False
    ):
        raise DartGuardError(
            "partial", "unsupported_guard_authority", "guard requires one public authored project-owned field"
        )
    relative = _relative(after.get("declaration_file"), "authority source", "lib")
    if relative.name.endswith((".g.dart", ".freezed.dart", ".mocks.dart")):
        raise DartGuardError("partial", "unsupported_guard_authority", "generated authority is unsupported")
    source = root / Path(relative.as_posix())
    if (
        not source.is_file()
        or source.is_symlink()
        or after.get("source_sha256") != _sha256(source)
    ):
        raise DartGuardError("failed", "stale_proposal_review", "accepted migrated source is stale")
    lines = source.read_text(encoding="utf-8").splitlines()
    line = after.get("declaration_line")
    if (
        not isinstance(line, int)
        or not 1 <= line <= len(lines)
        or re.fullmatch(
            rf"\s*(?:late\s+)?{re.escape(expected_type)}\s+{re.escape(field)}\s*;",
            lines[line - 1],
        )
        is None
        or not re.search(rf"\benum\s+{re.escape(expected_type)}\b", source.read_text())
        or not re.search(rf"\bclass\s+{re.escape(owner)}\b", source.read_text())
    ):
        raise DartGuardError("failed", "stale_proposal_review", "accepted migrated field is stale")
    if guard.get("kind") != "dependency_free_direct_type_guard":
        raise DartGuardError("partial", "direct_guard_unavailable", "accepted direct type guard is unavailable")
    tool = _relative(guard.get("tool_destination"), "guard tool destination", "tool")
    test = _relative(guard.get("test_destination"), "guard test destination", "test")
    expected_import = posixpath.relpath(relative.as_posix(), tool.parent.as_posix())
    if guard.get("import_uri") != expected_import or not isinstance(guard.get("expected_stdout"), str):
        raise DartGuardError("failed", "invalid_proposal_review", "guard import/stdout authority is malformed")
    variants = enum.get("variants")
    if (
        enum.get("type_name") != expected_type
        or not isinstance(variants, list)
        or not variants
        or not all(
            isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and IDENTIFIER.fullmatch(row["name"])
            and isinstance(row.get("wire_value"), str)
            for row in variants
        )
    ):
        raise DartGuardError("failed", "invalid_proposal_review", "accepted enum values are malformed")
    for destination in (root / Path(tool.as_posix()), root / Path(test.as_posix())):
        if destination.is_symlink():
            raise DartGuardError("failed", "unsafe_path", "guard destination must not be a symlink")
    return {
        "owner": owner,
        "field": field,
        "declaration_file": relative.as_posix(),
        "declaration_line": line,
        "source_sha256": after["source_sha256"],
        "expected_type": expected_type,
        "visibility": "public",
        "enum": enum,
        "guard": guard,
        "tool_destination": tool.as_posix(),
        "test_destination": test.as_posix(),
    }


def _guard_text(data: dict[str, Any]) -> str:
    enum, guard = data["enum"], data["guard"]
    checks = "\n".join(
        f"  if ({enum['type_name']}.{row['name']}.wireValue != {json.dumps(row['wire_value'])}) {{\n"
        f"    throw StateError('wire value changed: {row['name']}');\n"
        "  }"
        for row in enum["variants"]
    )
    return f"""import '{guard['import_uri']}';

{enum['type_name']} readAcceptedField({data['owner']} value) => value.{data['field']};

void verifyAcceptedNativeValues() {{
  final {enum['type_name']} Function({data['owner']}) exactFieldReader = readAcceptedField;
  if (exactFieldReader != readAcceptedField) {{
    throw StateError('field reader changed');
  }}
{checks}
}}

void main() {{
  verifyAcceptedNativeValues();
  print({json.dumps(guard['expected_stdout'])});
}}
"""


def _test_text(data: dict[str, Any]) -> str:
    relative = posixpath.relpath(data["tool_destination"], PurePosixPath(data["test_destination"]).parent.as_posix())
    return f"""import '{relative}' as guard;

void main() {{
  guard.verifyAcceptedNativeValues();
}}
"""


def _metadata(
    targets_path: Path,
    review_path: Path,
    validated: dict[str, Any],
    targets: dict[str, Any],
    data: dict[str, Any],
    guard_text: str,
    test_text: str,
) -> dict[str, Any]:
    return {
        "schema_version": "dart-state-guard-v1",
        "language": "dart",
        "status": "staged",
        "outcome": "exact_native_guard",
        "accepted_evidence_hash": validated["envelope"]["acceptance_hash"],
        "targets_sha256": _sha256(targets_path),
        "accepted_review_sha256": _sha256(review_path),
        "authority": {key: data[key] for key in (
            "owner", "field", "declaration_file", "declaration_line", "source_sha256", "expected_type", "visibility"
        )},
        "enum": data["enum"],
        "guard": data["guard"],
        "tool_destination": data["tool_destination"],
        "test_destination": data["test_destination"],
        "tool_sha256": hashlib.sha256(guard_text.encode()).hexdigest(),
        "test_sha256": hashlib.sha256(test_text.encode()).hexdigest(),
        "native_obligations": validated["envelope"]["native_obligations"],
        "native_values": {
            row["name"]: row["wire_value"] for row in data["enum"]["variants"]
        },
        "regression_revert_edits": [
            {
                "file": row["file"],
                "old": row["new"],
                "new": row["old"],
                "purpose": row["purpose"],
            }
            for row in targets["rewrite_plan"]["edits"]
            if row["purpose"] != "declare the reviewed wire-preserving enum"
        ],
    }


def _pattern(metadata: dict[str, Any]) -> str:
    authority = metadata["authority"]
    return f"""# Dart exact-field regression pattern

Protect only `{authority['owner']}.{authority['field']}` in
`{authority['declaration_file']}`. The dependency-free direct script gives the
field reader the accepted `{authority['expected_type']}` return type, so a
reversion to `String` fails compilation. It also checks every accepted native
wire value. It is not a universal Dart lint or runtime/serialization proof.
"""


def _proposal(metadata: dict[str, Any]) -> str:
    return f"""# Staged Dart regression guard

Status: `staged`; native verification required.

This stage never installs or mutates the audited host. Review and copy
`staged/{metadata['tool_destination']}` and
`staged/{metadata['test_destination']}` only after approval, then apply the
commands in `host-wiring.diff`. The guard protects the exact accepted field and
native enum values only.
"""


def _wiring(metadata: dict[str, Any]) -> str:
    return f"""# Review-only host wiring; no command below was applied.
+ copy staged/{metadata['tool_destination']} to {metadata['tool_destination']}
+ copy staged/{metadata['test_destination']} to {metadata['test_destination']}
+ dart analyze --fatal-infos --fatal-warnings .
+ dart format --output=none --set-exit-if-changed lib bin tool test
+ dart {metadata['tool_destination']}
+ dart {metadata['test_destination']}
"""


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


def _terminal(status: str, kind: str, detail: str) -> dict[str, Any]:
    return {
        "schema_version": "dart-state-guard-verification-v1",
        "language": "dart",
        "status": status,
        "outcome": "refused",
        "failure_kind": kind,
        "failure_detail": detail,
        "audited_host_mutated": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--accepted-review", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
        if not root.is_dir() or args.project_root.is_symlink():
            raise DartGuardError("partial", "project_unavailable", "project root is unavailable")
        output = _bounded(
            root,
            args.output_root,
            root / "reports" / "prevent-regression",
            "output root",
        )
        if output == root / "reports" / "prevent-regression":
            raise DartGuardError("failed", "unsafe_path", "output root must name one guard")
        targets_path = _bounded(
            root, args.targets, root / "reports" / "extract-enum", "targets"
        )
        review_path = _bounded(
            root,
            args.accepted_review,
            root / "reports" / "extract-enum",
            "accepted proposal review",
        )
        validator = _validator()
        try:
            validated = validator.validate_accepted_evidence(
                root,
                args.evidence_dir,
                args.acceptance,
                expected_producer="find-implicit-state",
                expected_kind="extract_enum_candidate",
                verify_current_sources=False,
            )
        except validator.AcceptedEvidenceError as exc:
            raise DartGuardError(exc.status, exc.failure_kind, exc.detail) from exc
        targets, review = _review(targets_path, review_path, validated)
        data = _authority(root, targets, review)
        guard_text, test_text = _guard_text(data), _test_text(data)
        metadata = _metadata(
            targets_path, review_path, validated, targets, data, guard_text, test_text
        )
        installed_tool = root / data["tool_destination"]
        installed_test = root / data["test_destination"]
        existing = installed_tool.exists() or installed_test.exists()
        if existing:
            if (
                installed_tool.is_file()
                and not installed_tool.is_symlink()
                and installed_test.is_file()
                and not installed_test.is_symlink()
                and installed_tool.read_text(encoding="utf-8") == guard_text
                and installed_test.read_text(encoding="utf-8") == test_text
            ):
                metadata.update(status="complete", outcome="equivalent_guard_exists")
                verification = {
                    "schema_version": "dart-state-guard-verification-v1",
                    "language": "dart",
                    "status": "complete",
                    "outcome": "equivalent_guard_exists",
                    "source_preserved": True,
                }
                files = {
                    "authority.json": json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                    "pattern.md": _pattern(metadata),
                    "proposal.md": "# Dart regression guard\n\nAn equivalent exact guard already exists; no duplicate was staged.\n",
                    "verification.json": json.dumps(verification, indent=2, sort_keys=True) + "\n",
                }
            else:
                raise DartGuardError(
                    "partial", "existing_guard_conflict", "existing guard paths are not equivalent"
                )
        else:
            verification = {
                "schema_version": "dart-state-guard-verification-v1",
                "language": "dart",
                "status": "partial",
                "outcome": "staged_unverified",
                "failure_kind": "native_verification_required",
                "source_preserved": True,
            }
            files = {
                "authority.json": json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                "pattern.md": _pattern(metadata),
                "proposal.md": _proposal(metadata),
                "host-wiring.diff": _wiring(metadata),
                f"staged/{data['tool_destination']}": guard_text,
                f"staged/{data['test_destination']}": test_text,
                "verification.json": json.dumps(verification, indent=2, sort_keys=True) + "\n",
            }
        _replace(output, files)
    except (
        DartGuardError,
        FileNotFoundError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        if isinstance(exc, DartGuardError):
            status, kind, detail = exc.status, exc.failure_kind, exc.detail
        else:
            status, kind, detail = "failed", "invalid_accepted_input", str(exc)
        terminal = _terminal(status, kind, detail)
        if output is not None:
            _replace(
                output,
                {
                    "pattern.md": f"# Dart regression guard\n\nGuard staging refused: {detail}\n",
                    "verification.json": json.dumps(terminal, indent=2, sort_keys=True) + "\n",
                },
            )
        print(f"[generate_dart_state_guard] {status}/{kind}: {detail}", file=sys.stderr)
        return 2
    print(f"[generate_dart_state_guard] {metadata['outcome']}: {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
