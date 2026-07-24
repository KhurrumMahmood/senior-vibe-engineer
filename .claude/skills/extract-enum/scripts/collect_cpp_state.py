#!/usr/bin/env python3
"""Render and disposably prove one review-required C++ enum-class proposal."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import tempfile
from pathlib import Path


def _tools():
    candidates = [Path(__file__).with_name("cpp_proposal_tools.py")]
    candidates.extend(parent / "_cpp-semantic/cpp_proposal_tools.py" for parent in Path(__file__).resolve().parents)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled C++ proposal helper is missing")
    spec = importlib.util.spec_from_file_location("cpp_extract_enum_tools", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


T = _tools()


def _candidate(findings: dict, selector: str, facts: dict) -> dict:
    if (
        findings.get("schema_version") != "cpp-implicit-state-v1"
        or findings.get("language") != "cpp"
        or findings.get("status") != "complete"
        or findings.get("read_only") is not True
        or findings.get("fact_pack_sha256") != facts.get("fact_pack_sha256")
    ):
        raise T.ProposalError("evidence_invalid", "complete fact-bound C++ state findings required")
    matches = [
        row for row in findings.get("candidates", [])
        if f"{row.get('owner')}.{row.get('field')}" == selector
    ]
    if len(matches) != 1:
        raise T.ProposalError("selection_invalid", "select exactly one owner.field state lead")
    row = matches[0]
    if (
        row.get("classification") != "enum_class_review_only"
        or row.get("automatic_migration") is not False
        or row.get("human_verdict") != "required"
        or row.get("type") != "const char *"
        or len(row.get("literals", [])) < 3
        or any(re.fullmatch(r"[A-Za-z_]\w*", value) is None for value in row.get("literals", []))
    ):
        raise T.ProposalError("selection_invalid", "selected lead is not an exact bounded string-field candidate")
    return row


def _plan(root: Path, candidate: dict) -> tuple[str, list[dict[str, str]]]:
    owner = candidate["owner"]
    namespace, _, record = owner.rpartition("::")
    if not namespace or not record:
        raise T.ProposalError("selection_invalid", "candidate must have a namespace-qualified owner")
    field = candidate["field"]
    enum_name = f"{record}{field.title()}"
    header = candidate["file"]
    path = root / header
    text = path.read_text(encoding="utf-8")
    record_pattern = re.compile(
        rf"struct\s+{re.escape(record)}\s*\{{\s*const char\*\s+{re.escape(field)};\s*\}};",
        re.MULTILINE,
    )
    match = record_pattern.search(text)
    if match is None:
        raise T.ProposalError("mutation_plan_stale", "exact one-field record anchor is unavailable")
    values = candidate["literals"]
    cases = "\n".join(
        f'    case {enum_name}::{value}: return "{value}";' for value in values
    )
    replacement = f"""enum class {enum_name} {{
    {', '.join(values)},
}};

constexpr const char* {field}_name({enum_name} value) noexcept
{{
    switch (value) {{
{cases}
    }}
    return "unknown";
}}

struct {record} {{
    {enum_name} {field};
}};"""
    replacements = [{"path": header, "before": match.group(0), "after": replacement}]
    for operation in candidate["operations"]:
        source = root / operation["file"]
        lines = source.read_text(encoding="utf-8").splitlines()
        line = lines[operation["line"] - 1]
        pattern = re.compile(
            rf"(?P<object>[A-Za-z_]\w*)\.{re.escape(field)}\s*=\s*\"{re.escape(operation['literal'])}\";"
        )
        changed, count = pattern.subn(
            rf"\g<object>.{field} = {enum_name}::{operation['literal']};", line
        )
        if count != 1:
            raise T.ProposalError("mutation_plan_stale", f"direct write anchor changed at {operation['file']}:{operation['line']}")
        replacements.append({"path": operation["file"], "before": line, "after": changed})
    stream_pattern = re.compile(rf"<<\s*([A-Za-z_]\w*)\.{re.escape(field)}\s*<<")
    stream_rows = []
    for source in T.PROVIDER.eligible_translation_units(root):
        source_text = source.read_text(encoding="utf-8")
        for match in stream_pattern.finditer(source_text):
            stream_rows.append((source, match.group(0), match.group(1)))
    if len(stream_rows) != 1:
        raise T.ProposalError("serialization_unresolved", "exactly one fixture serialization anchor is required for disposable proof")
    source, before, variable = stream_rows[0]
    after = f"<< {namespace}::{field}_name({variable}.{field}) <<"
    replacements.append({"path": source.relative_to(root).as_posix(), "before": before, "after": after})
    return enum_name, replacements


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--facts", required=True)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--clangxx", default="clang++")
    parser.add_argument("--make", default="make")
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve()
        output = T.output_dir(root, args.output_dir, "extract-enum")
        facts_path, facts = T.fact_pack(root, args.facts)
        findings_path = T.safe_path(root, args.findings, "state findings")
        findings = T.load_json(findings_path, "state findings")
        candidate = _candidate(findings, args.selector, facts)
        enum_name, replacements = _plan(root, candidate)
        before_sources = T.audited_sources(root)
        baseline = T.native_proof(root, args.clangxx, args.make)
        if not baseline["passed"]:
            raise T.ProposalError("native_baseline_failed", "current native C++ test/smoke failed")
        with tempfile.TemporaryDirectory(prefix="cpp-enum-proof-") as raw:
            proof_root = T.project_copy(root, Path(raw) / "project")
            T.apply_replacements(proof_root, replacements)
            proof = T.native_proof(proof_root, args.clangxx, args.make)
        if not proof["passed"] or proof["smoke"]["stdout"] != baseline["smoke"]["stdout"]:
            raise T.ProposalError("disposable_native_proof_failed", "proposed migration did not preserve native smoke")
        if T.audited_sources(root) != before_sources:
            raise T.ProposalError("source_mutated", "read-only proposal changed host sources")
        payload = {
            "schema_version": "cpp-enum-proposal-v1",
            "language": "cpp",
            "status": "review_required",
            "outcome": "proposal_ready",
            "read_only": True,
            "source_mutations": 0,
            "authority": {
                "owner": candidate["owner"], "field": candidate["field"],
                "type": candidate["type"], "declaration_file": candidate["file"],
            },
            "proposed_enum": {"name": enum_name, "values": candidate["literals"]},
            "mutation_plan": replacements,
            "approval_gates": {key: "human_approval_required" for key in ("abi", "external", "storage", "wire", "odr")},
            "evidence": {
                "facts_path": facts_path.relative_to(root).as_posix(), "facts_sha256": T.sha256(facts_path),
                "findings_path": findings_path.relative_to(root).as_posix(), "findings_sha256": T.sha256(findings_path),
                "fact_pack_sha256": facts["fact_pack_sha256"], "source_files": before_sources,
            },
            "native_proof": {"baseline": baseline, "disposable_migration": proof, "smoke_preserved": True},
            "limits": [*facts["limits"], "disposable compilation does not approve ABI, ODR, storage, wire, external, or source mutation compatibility"],
        }
        markdown = f"# C++ enum-class proposal\n\nPropose `{enum_name}` for `{args.selector}`. Host sources were not changed. ABI, ODR, storage, wire, and external approval remain required.\n"
        T.replace_bundle(output, {"proposal.json": T.json_text(payload), "proposal.md": markdown})
        return 0
    except T.ProposalError as exc:
        print(f"collect_cpp_state.py: {exc.kind}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
