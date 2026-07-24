#!/usr/bin/env python3
"""Stage and prove one exact C++ enum-class field regression guard."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
import tempfile
from pathlib import Path


def _tools():
    candidates = [Path(__file__).with_name("cpp_proposal_tools.py")]
    candidates.extend(parent / "_cpp-semantic/cpp_proposal_tools.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C++ proposal helper is missing")
    spec = importlib.util.spec_from_file_location("cpp_state_guard_tools", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


T = _tools()
APPROVALS = {key: "approved" for key in ("abi", "external", "storage", "wire", "odr")}


def _proposal(root: Path, supplied: str) -> tuple[Path, dict]:
    path = T.safe_path(root, supplied, "enum proposal")
    payload = T.load_json(path, "enum proposal")
    claimed = payload.get("artifact_sha256")
    unhashed = dict(payload)
    unhashed.pop("artifact_sha256", None)
    if (
        payload.get("schema_version") != "cpp-enum-proposal-v1"
        or payload.get("language") != "cpp"
        or payload.get("status") != "review_required"
        or payload.get("outcome") != "proposal_ready"
        or payload.get("read_only") is not True
        or payload.get("source_mutations") != 0
        or claimed != T.canonical_hash(unhashed)
    ):
        raise T.ProposalError("proposal_invalid", "content-addressed C++ enum proposal required")
    return path, payload


def _acceptance(root: Path, supplied: str, proposal_path: Path, proposal: dict) -> dict:
    path = T.safe_path(root, supplied, "accepted migration")
    payload = T.load_json(path, "accepted migration")
    if (
        payload.get("schema_version") != "cpp-enum-migration-acceptance-v1"
        or payload.get("language") != "cpp"
        or payload.get("status") != "accepted"
        or payload.get("decision") != "approve_exact_field_guard"
        or payload.get("proposal_sha256") != T.sha256(proposal_path)
        or payload.get("authority") != proposal.get("authority")
        or payload.get("approvals") != APPROVALS
    ):
        raise T.ProposalError("acceptance_invalid", "fresh exact proposal acceptance and five approvals required")
    T.validate_source_rows(root, payload.get("migrated_source_files"))
    return payload


def _guard(proposal: dict) -> str:
    authority = proposal["authority"]
    enum_name = proposal["proposed_enum"]["name"]
    namespace, _, _record = authority["owner"].rpartition("::")
    include = authority["declaration_file"]
    if not include.startswith("include/"):
        raise T.ProposalError("proposal_invalid", "guard authority must live under include/")
    include = include.removeprefix("include/")
    return f'''#include "{include}"
#include <type_traits>

static_assert(
    std::is_same_v<decltype({authority['owner']}::{authority['field']}), {namespace}::{enum_name}>,
    "{authority['owner']}.{authority['field']} must remain {namespace}::{enum_name}"
);
'''


def _compile(root: Path, guard: Path, clangxx: str) -> dict:
    return T.run([
        clangxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pedantic",
        f"-I{root / 'include'}", "-fsyntax-only", str(guard),
    ], root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--accepted-migration", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--clangxx", default="clang++")
    parser.add_argument("--make", default="make")
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve()
        output = T.output_dir(root, args.output_dir, "prevent-regression")
        proposal_path, proposal = _proposal(root, args.proposal)
        acceptance_path = T.safe_path(root, args.accepted_migration, "accepted migration")
        acceptance = _acceptance(root, args.accepted_migration, proposal_path, proposal)
        before_sources = T.audited_sources(root)
        native = T.native_proof(root, args.clangxx, args.make)
        if not native["passed"]:
            raise T.ProposalError("native_migration_failed", "accepted migrated project test/smoke is not green")
        guard = _guard(proposal)
        with tempfile.TemporaryDirectory(prefix="cpp-state-guard-") as raw:
            temporary = Path(raw)
            guard_path = temporary / "guard.cpp"
            guard_path.write_text(guard, encoding="utf-8")
            current = _compile(root, guard_path, args.clangxx)
            seeded_root = T.project_copy(root, temporary / "seeded")
            header = seeded_root / proposal["authority"]["declaration_file"]
            enum_name = proposal["proposed_enum"]["name"]
            field = proposal["authority"]["field"]
            text = header.read_text(encoding="utf-8")
            before = f"{enum_name} {field};"
            after = f"const char* {field};"
            if text.count(before) != 1:
                raise T.ProposalError("seed_invalid", "exact migrated field anchor is unavailable")
            header.write_text(text.replace(before, after, 1), encoding="utf-8")
            seeded_guard = temporary / "seeded-guard.cpp"
            seeded_guard.write_text(guard, encoding="utf-8")
            seeded = _compile(seeded_root, seeded_guard, args.clangxx)
        if current["returncode"] != 0 or seeded["returncode"] == 0:
            raise T.ProposalError("guard_proof_failed", "guard must accept current migration and reject seeded type regression")
        if T.audited_sources(root) != before_sources:
            raise T.ProposalError("source_mutated", "guard staging changed host sources")
        evidence = {
            "schema_version": "cpp-state-guard-evidence-v1",
            "language": "cpp",
            "status": "verified",
            "staged_only": True,
            "source_mutations": 0,
            "authority": proposal["authority"],
            "enum": proposal["proposed_enum"],
            "guard_sha256": hashlib.sha256(guard.encode()).hexdigest(),
            "proposal_sha256": T.sha256(proposal_path),
            "acceptance_sha256": T.sha256(acceptance_path),
            "accepted_source_files": acceptance["migrated_source_files"],
            "verification": {"native": native, "current_guard": current, "seeded_regression": seeded, "regression_rejected": True},
            "limits": ["exact field-type guard only", "enumerator aliases, values, ODR, ABI, wire, storage, external consumers, templates, overloads, operators, and variants remain outside this guard"],
        }
        T.replace_bundle(output, {"guard.cpp": guard, "evidence.json": T.json_text(evidence)})
        return 0
    except T.ProposalError as exc:
        print(f"stage_cpp_state_guard.py: {exc.kind}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
