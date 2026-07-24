#!/usr/bin/env python3
"""Final-artifact executors for the bounded C++ lexical/syntax cohort."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

from cpp_facts import (
    add_fact_arguments,
    atomic_json,
    atomic_text,
    clear_artifacts,
    hash_bytes,
    produce,
    terminal_return_code,
)


def _facts(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return produce(args.project_root, args.target, clangxx=args.clangxx)


def _parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--project-root", required=True, type=Path)
    add_fact_arguments(parser)
    return parser


def _module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _inside_output(root: Path, path: Path, parser: argparse.ArgumentParser) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        parser.error("artifact paths must stay inside --project-root")
    return resolved


def _declarations(facts: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"file": file["file"], **row}
        for file in facts.get("files", [])
        for row in file["declarations"]
    ]


def _functions(facts: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"file": file["file"], **row}
        for file in facts.get("files", [])
        for row in file["functions"]
    ]


def adapt_main(argv: list[str] | None = None) -> int:
    parser = _parser("Produce a bounded C++20 host adapter.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("targets", nargs="*", default=["."])
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = _inside_output(root, args.output_dir, parser)
    artifacts = [
        output / "adapter.yml", output / "adapter.json",
        output / "report.md", output / "evidence.json",
    ]
    clear_artifacts(artifacts)
    args.target = Path(args.targets[0] if args.targets else ".")
    facts, code = _facts(args)
    translation_units = facts.get("compile_database", {}).get("translation_units", [])
    headers = facts.get("compile_database", {}).get("owned_headers", [])
    adapter = {
        "schema_version": 1,
        "status": facts["status"],
        "analysis": {"cpp": facts},
        "project": {"name": root.name, "root": str(root)},
        "stack": {
            "languages": ["cpp"] if facts.get("inventory") else [],
            "frameworks": [], "package_managers": [],
            "build_systems": ["make"] if (root / "Makefile").is_file() else [],
        },
        "commands": {
            "compile_database": ["make compile-db CXX=clang++"],
            "check": ["clang++ <recorded C++20 flags> -fsyntax-only <translation-unit>"],
            "test": ["make test CXX=clang++"],
        },
        "source_roots": [{
            "path": ".", "cpp_translation_units": len(translation_units),
            "compiler_owned_headers": len(headers),
            "source_languages": ["cpp"] if translation_units else [],
        }],
        "boundaries": facts.get("boundaries", {}),
        "standardization": {"cautions": [
            "Observed C++20 compile-command facts do not endorse a framework, layout, ABI, or build variant."
        ]},
        "open_questions": [
            "Which observed build variants and ABI/ODR boundaries are intentionally project-owned?"
        ],
    }
    serialized = json.dumps(adapter, indent=2, sort_keys=True) + "\n"
    atomic_text(artifacts[0], serialized)
    atomic_text(artifacts[1], serialized)
    atomic_text(
        artifacts[2],
        "# Adapt Project Report — C++20\n\n"
        f"**Status:** `{facts['status']}`\n\n"
        f"Translation units: {len(translation_units)}; compiler-owned headers: {len(headers)}. "
        "ODR and ABI remain unresolved.\n",
    )
    atomic_json(artifacts[3], {
        "skill": "adapt-project", "status": facts["status"],
        "evidence": {"adapter": "adapter.yml", "report": "report.md"},
    })
    return terminal_return_code(facts, code)


def explain_main(argv: list[str] | None = None) -> int:
    parser = _parser("Render direct C++ declarations with overload-aware keys.")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = _inside_output(root, args.output, parser)
    sidecar = output.with_suffix("")
    annotations = sidecar / "annotations"
    clear_artifacts([
        output, sidecar / "targets.json", sidecar / "scan.json",
        sidecar / "unexplained.txt", sidecar / "surprises.txt",
    ])
    if annotations.is_dir():
        for old in annotations.glob("*.md"):
            old.unlink()
    facts, code = _facts(args)
    declarations = _declarations(facts) if facts["status"] == "complete" else []
    for row in declarations:
        raw = f"{row['file']}\0{row['qualified_name']}\0{row['signature']}".encode()
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", row["qualified_name"]).strip("-")
        row["symbol_key"] = f"{safe}-{hash_bytes(raw)[:12]}"
    selected, overflow = declarations[:20], declarations[20:]
    annotations.mkdir(parents=True, exist_ok=True)
    for row in selected:
        atomic_text(
            annotations / f"{row['symbol_key']}.md",
            f"# `{row['qualified_name']}`\n\n"
            f"- Signature: `{row['signature']}`\n"
            f"- Source: `{row['file']}`\n"
            f"- Template declaration: `{row['template']}`; operator: `{row['operator']}`.\n"
            "- Contract: direct C++20 spelling; runtime dispatch, ODR, and ABI remain unexplained.\n",
        )
    payload = {
        "schema_version": 1, "status": facts["status"], "language": "cpp",
        "target": str(args.target), "analysis": {"cpp": facts},
        "selected": selected, "overflow": overflow,
        "unexplained": [
            "template instantiations and specialization selection",
            "virtual/dynamic dispatch and runtime behavior", "ODR, ABI, and object layout",
        ],
    }
    atomic_json(sidecar / "targets.json", payload)
    atomic_json(sidecar / "scan.json", facts)
    atomic_text(sidecar / "unexplained.txt", "\n".join(payload["unexplained"]) + "\n")
    atomic_text(sidecar / "surprises.txt", "")
    contracts = [
        f"### `{row['qualified_name']}`\n\n- Signature: `{row['signature']}`\n"
        f"- Evidence: `{row['file']}:{row['line']}` direct spelling."
        for row in selected
    ]
    atomic_text(
        output,
        f"# Explanation — {args.target}\n\n**Status:** `{facts['status']}`\n\n"
        "Qualified C++ declarations and spelled overload signatures follow; ODR, ABI, "
        "instantiation, dispatch, and behavior remain unresolved.\n\n"
        + ("\n\n".join(contracts) if contracts else "No complete direct declaration inventory.")
        + "\n",
    )
    return terminal_return_code(facts, code)


def _load_glossary(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        concepts: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("- name:"):
                if current:
                    concepts.append(current)
                current = {"name": line.split(":", 1)[1].strip().strip("\"'")}
            elif current is not None and line.startswith("avoid:"):
                value = line.split(":", 1)[1].strip()
                current["avoid"] = json.loads(value.replace("'", '"')) if value else []
        if current:
            concepts.append(current)
        payload = {"concepts": concepts}
    if not isinstance(payload, dict) or not isinstance(payload.get("concepts"), list):
        raise ValueError("glossary missing concepts list")
    return payload


def concept_main(argv: list[str] | None = None) -> int:
    parser = _parser("Find strict glossary-backed C++ text divergence.")
    parser.add_argument("--glossary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("targets", nargs="*", default=["."])
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = _inside_output(root, args.output, parser)
    report = _inside_output(root, args.report, parser)
    final_json, scan_json = output.with_name("findings.json"), output.with_name("scan.json")
    clear_artifacts([output, report, final_json, scan_json])
    args.target = Path(args.targets[0] if args.targets else ".")
    facts, code = _facts(args)
    findings: list[dict[str, Any]] = []
    try:
        glossary = _load_glossary(args.glossary)
    except (OSError, UnicodeError, ValueError) as exc:
        facts.update(status="failed", failure_kind="glossary_invalid", detail=str(exc))
        glossary = {"concepts": []}
        code = 2
    if facts["status"] == "complete":
        for concept in glossary["concepts"]:
            if not isinstance(concept, dict):
                continue
            sources = set(concept.get("source_files") or concept.get("sources") or [])
            for term in concept.get("avoid") or []:
                if not isinstance(term, str):
                    continue
                term = term.split("(", 1)[0].strip().strip("\"'").rstrip(",.;:")
                pattern = re.compile(
                    rb"(?<![A-Za-z0-9_])" + re.escape(term.encode()) + rb"(?![A-Za-z0-9_])",
                    re.I,
                )
                for file in facts["files"]:
                    if file["file"] in sources:
                        continue
                    source = (root / file["file"]).read_bytes()
                    for match in pattern.finditer(source):
                        before = source[: match.start()]
                        findings.append({
                            "band": "avoid_term_hit", "concept": concept.get("name", "?"),
                            "file": file["file"], "language": "cpp", "term": term,
                            "match": match.group().decode(), "line": before.count(b"\n") + 1,
                            "span": {"start_byte": match.start(), "end_byte": match.end()},
                            "source_sha256": file["source_sha256"],
                            "claim": "strict-text-evidence-not-symbol-identity",
                        })
    findings.sort(key=lambda row: (row["file"], row["line"], row["term"]))
    jsonl = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    atomic_text(output, jsonl)
    outcome = (
        "failed" if facts["status"] == "failed" else
        "incomplete" if facts["status"] != "complete" else
        "drift-found" if findings else "clean-within-complete"
    )
    atomic_json(final_json, {
        "schema_version": 1, "status": facts["status"], "outcome": outcome,
        "analysis": {"cpp": facts}, "detections_sha256": hash_bytes(jsonl.encode()),
        "findings": findings,
    })
    atomic_json(scan_json, facts)
    lines = [
        "# Concept-divergence scan — C++20", "", f"**Status:** `{facts['status']}`",
        f"**Outcome:** `{outcome}`", "",
    ]
    lines.extend(f"- `{row['file']}:{row['line']}` — `{row['term']}`" for row in findings)
    if not findings:
        lines.append(
            "No strict glossary drift in the complete snapshot."
            if facts["status"] == "complete" else "Analysis incomplete; no clean claim."
        )
    atomic_text(report, "\n".join(lines) + "\n")
    return terminal_return_code(facts, code)


def duplication_main(argv: list[str] | None = None) -> int:
    parser = _parser("Find exact normalized C++ function-body spelling clones.")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = _inside_output(root, args.output_dir, parser)
    artifacts = {
        name: output / filename for name, filename in {
            "collapsed": "collapsed.json", "ranked": "ranked.json",
            "triage": "triage.md", "findings": "findings.json", "scan": "scan.json",
        }.items()
    }
    clear_artifacts(artifacts.values())
    facts, code = _facts(args)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if facts["status"] == "complete":
        for row in _functions(facts):
            if row["loc"] >= 5:
                groups[row["normalized_body_sha256"]].append(row)
    findings: list[dict[str, Any]] = []
    for digest, rows in sorted(groups.items()):
        unique = {(row["file"], row["qualified_name"], row["line"]): row for row in rows}
        if len(unique) < 2:
            continue
        sites = [{
            "file": row["file"], "qualified_name": row["qualified_name"],
            "signature": row["signature"], "start_line": row["line"],
            "end_line": row["end_line"], "source_sha256": row["source_sha256"],
            "spelling_sha256": row["spelling_sha256"],
        } for row in unique.values()]
        findings.append({
            "finding_id": f"CPP-DUP-{digest[:12].upper()}",
            "detector": "cpp20-exact-normalized-function-body-spelling",
            "multiplicity": len(sites), "normalized_body_sha256": digest,
            "sites": sorted(sites, key=lambda row: (row["file"], row["qualified_name"])),
            "claim_boundary": "exact source spelling, not semantic or behavioral equivalence",
        })
    payload = {
        "schema_version": 1, "status": facts["status"], "failure_kind": facts["failure_kind"],
        "analysis": {"cpp": facts}, "findings": findings, "dormant_candidates": [],
    }
    atomic_json(artifacts["collapsed"], payload)
    atomic_json(artifacts["ranked"], payload)
    atomic_json(artifacts["findings"], payload)
    atomic_json(artifacts["scan"], facts)
    lines = [
        "# Duplication triage — C++20", "", f"**Status:** `{facts['status']}`", "",
        "> Exact direct function-body spelling is not semantic or behavioral equivalence.", "",
    ]
    for finding in findings:
        lines.append(f"### `{finding['finding_id']}`")
        lines.extend(f"- `{site['file']}::{site['qualified_name']}`" for site in finding["sites"])
    atomic_text(artifacts["triage"], "\n".join(lines) + "\n")
    return terminal_return_code(facts, code)


def folder_main(argv: list[str] | None = None) -> int:
    parser = _parser("Find direct-sibling C++ filename prefix clusters.")
    parser.add_argument("--cpp-root", required=True)
    parser.add_argument("--min-cluster-size", type=int, default=3)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = _inside_output(root, args.output, parser)
    report, final_json, scan_json = (
        output.with_name("report.md"), output.with_name("findings.json"), output.with_name("scan.json")
    )
    clear_artifacts([output, report, final_json, scan_json])
    args.target = Path(args.cpp_root)
    facts, code = _facts(args)
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    if facts["status"] == "complete":
        for row in facts["inventory"]:
            path = Path(row["file"])
            if row["role"] != "source" or path.suffix not in {".cpp", ".cc", ".cxx"}:
                continue
            if not (path == args.target or args.target in path.parents):
                continue
            prefix = re.split(r"[_-]", path.stem, maxsplit=1)[0]
            if len(prefix) >= 2 and prefix != path.stem:
                groups[(path.parent.as_posix(), prefix)].append(row["file"])
    findings = [{
        "pattern": "flat_prefix_cluster", "language": "cpp", "file": directory,
        "prefix": prefix, "count": len(files), "files": sorted(files),
        "evidence_sha256": hash_bytes("\n".join(sorted(files)).encode()),
        "recommendation": (
            "Human triage only; include/build, namespace, template, ODR, ABI, and move safety remain unresolved."
        ),
    } for (directory, prefix), files in sorted(groups.items()) if len(files) >= args.min_cluster_size]
    outcome = (
        "failed" if facts["status"] == "failed" else
        "incomplete" if facts["status"] != "complete" else
        "drift-found" if findings else "clean"
    )
    jsonl = "".join(json.dumps(row, sort_keys=True) + "\n" for row in findings)
    atomic_text(output, jsonl)
    atomic_json(scan_json, facts)
    atomic_json(final_json, {
        "schema_version": 1, "status": facts["status"], "outcome": outcome,
        "analysis": {"cpp": facts}, "findings": findings,
    })
    atomic_text(
        report,
        "# Folder-topology drift — C++20\n\n"
        f"**Status:** `{facts['status']}`\n**Outcome:** `{outcome}`\n\n"
        "Filename evidence does not authorize moves across include, namespace, ODR, or ABI boundaries.\n",
    )
    return terminal_return_code(facts, code)


def audit_main(argv: list[str] | None, audit_path: Path) -> int:
    parser = _parser("Audit decision references in compile-owned C++ comments.")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = _inside_output(root, args.output_dir, parser)
    artifacts = [output / name for name in (
        "drift.md", "raw-drift.json", "registry-audit.json", "link-check.txt"
    )]
    clear_artifacts(artifacts)
    facts, code = _facts(args)
    if facts["status"] != "complete":
        atomic_json(artifacts[1], {
            "status": facts["status"], "failure_kind": facts["failure_kind"],
            "analysis": {"cpp": facts}, "references": [], "drift": [],
        })
        atomic_json(artifacts[2], {"status": "not-run", "drift": []})
        atomic_text(artifacts[3], f"NOT RUN — {facts['failure_kind']}\n")
        atomic_text(artifacts[0], f"# Decision drift\n\nStatus: `{facts['status']}`\n")
        return terminal_return_code(facts, code)
    audit = _module(audit_path, "audit_decisions_cpp_base")
    decisions = audit.load_decisions(root / "ai-docs/decisions")
    known = {decision.id for decision in decisions}
    pattern = re.compile(r"\bdecision:(\d{4})\b")
    references = [{
        "path": file["file"], "line": comment["line"], "language": "cpp",
        "comment_form": comment["form"], "id": match.group(1),
        "resolved": match.group(1) in known,
        "evidence_scope": "clang-raw-comment-token-c++20-only",
    } for file in facts["files"] for comment in file["comments"]
      for match in pattern.finditer(comment["text"])]
    references.sort(key=lambda row: (row["path"], row["line"], row["id"]))
    full_scope = args.target.as_posix() in {".", ""}
    drift = audit.make_drift(decisions, root, references, full_reference_scope=full_scope)
    registry = audit.registry_audit(decisions)
    link_drift, link_advisory = audit.link_check(decisions, root)
    raw = {
        "status": "complete", "failure_kind": "none", "analysis": {"cpp": facts},
        "references": references, "registry_audit": {"drift": registry},
        "link_check": {"drift": link_drift, "advisory": link_advisory}, "drift": drift,
    }
    atomic_json(artifacts[1], raw)
    atomic_json(artifacts[2], {"count": len(decisions), "drift": registry})
    atomic_text(artifacts[3], "\n".join([*link_advisory, *link_drift] or [
        f"OK — {len(decisions)} decisions, all links resolve"
    ]) + "\n")
    atomic_text(
        artifacts[0],
        audit.render_drift(output.name, decisions, references, drift)
        + "\nC++ evidence is raw comment-token syntax only; runtime applicability is unresolved.\n",
    )
    return 1 if drift else 0


def complexity_main(argv: list[str] | None = None) -> int:
    parser = _parser("Report advisory direct-body C++ branch hotspots.")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = _inside_output(root, args.output_dir, parser)
    clear_artifacts(output / name for name in ("detections.jsonl", "findings.json", "report.md"))
    facts, code = _facts(args)
    findings = [{
        "pattern": "high-branch-function", "language": "cpp",
        "analyzer": facts["analyzer"], "file": row["file"],
        "function": row["name"], "qualified_name": row["qualified_name"],
        "signature": row["signature"], "lineno": row["line"],
        "end_lineno": row["end_line"], "loc": row["loc"],
        "branch_score": row["branch_score"],
        "macro_nodes_omitted": row["macro_nodes_omitted"],
        "evidence_scope": "direct-body-c++-syntax-only",
    } for row in _functions(facts) if row["branch_score"] >= 8] if facts["status"] == "complete" else []
    findings.sort(key=lambda row: (-row["branch_score"], row["file"], row["lineno"]))
    verdict = (
        "incomplete-syntax-evidence" if facts["status"] != "complete"
        else "measure-first" if findings else "no-hotspots"
    )
    payload = {
        "status": facts["status"], "failure_kind": facts["failure_kind"],
        "verdict": verdict, "analysis": {"cpp": facts}, "findings": findings,
    }
    atomic_text(output / "detections.jsonl", "".join(
        json.dumps(row, sort_keys=True) + "\n" for row in findings
    ))
    atomic_json(output / "findings.json", payload)
    atomic_text(
        output / "report.md",
        "# Complexity hotspot audit — C++20\n\n"
        f"Status: `{facts['status']}`\nVerdict: `{verdict}`\n\n"
        "Direct-body syntax omits macro subtrees and does not measure runtime cost.\n",
    )
    return terminal_return_code(facts, code)


def _cluster(name: str) -> str:
    generic = {
        "load", "save", "validate", "authorize", "render", "write", "rotate",
        "find", "get", "set", "create", "update", "delete", "process", "handle",
    }
    words = [word for word in re.split(r"_+|(?<=[a-z])(?=[A-Z])", name) if word]
    specific = [word.casefold() for word in words if word.casefold() not in generic]
    return specific[-1] if specific else words[-1].casefold()


def omnibus_main(argv: list[str] | None = None) -> int:
    parser = _parser("Carry C++ function-name clusters through an explicit scout gate.")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scout-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = _inside_output(root, args.output_dir, parser)
    clear_artifacts(output / name for name in (
        "omnibus.jsonl", "candidates.jsonl", "scan.json", "findings.json", "report.md"
    ))
    facts, code = _facts(args)
    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _functions(facts):
        by_file[row["file"]].append(row)
    detections: list[dict[str, Any]] = []
    if facts["status"] == "complete":
        for file, functions in sorted(by_file.items()):
            clusters: dict[str, list[str]] = defaultdict(list)
            for function in functions:
                clusters[_cluster(function["name"])].append(function["qualified_name"])
            confirmed = {name: names for name, names in clusters.items() if len(names) >= 2}
            if len(confirmed) >= 4:
                detections.append({
                    "file": file, "language": "cpp", "cluster_count": len(confirmed),
                    "clusters": confirmed,
                    "evidence_scope": "qualified-function-name-cluster-syntax-only",
                    "cpp_boundary_note": "namespaces/classes/templates can be facets; scout must decide domains",
                })
    candidates = [{**row, "candidate_id": f"candidate-{index:03d}"}
                  for index, row in enumerate(detections, 1)]
    buckets = {"confirmed_omnibus", "borderline", "coordination_omnibus", "facets_not_domains"}
    findings: list[dict[str, Any]] = []
    missing: list[str] = []
    for candidate in candidates:
        try:
            scout = json.loads((args.scout_dir / f"{candidate['candidate_id']}.json").read_text())
        except (OSError, json.JSONDecodeError):
            missing.append(candidate["candidate_id"])
            continue
        if (
            scout.get("candidate_id") != candidate["candidate_id"]
            or scout.get("bucket") not in buckets
            or not isinstance(scout.get("domains_confirmed"), list)
            or not isinstance(scout.get("facets_collapsed"), list)
            or not scout.get("decomposition_depth_note")
        ):
            missing.append(candidate["candidate_id"])
            continue
        recommendations = {
            "confirmed_omnibus": "/refactor-subsystem <spec-id>",
            "coordination_omnibus": "/map-product-workflow",
            "borderline": "measure responsibility change before decomposition",
            "facets_not_domains": "keep cohesive module",
        }
        findings.append({
            **candidate, **scout, "scout_verdict": "explicit",
            "recommendation": recommendations[scout["bucket"]],
        })
    status, failure = facts["status"], facts["failure_kind"]
    if missing and status == "complete":
        status, failure = "partial", "cpp_scout_evidence_missing"
    payload = {
        "status": status, "failure_kind": failure, "analysis": {"cpp": facts},
        "summary": dict(sorted(Counter(row["bucket"] for row in findings).items())),
        "missing_scouts": missing, "findings": findings,
    }
    atomic_text(output / "omnibus.jsonl", "".join(
        json.dumps(row, sort_keys=True) + "\n" for row in detections
    ))
    atomic_text(output / "candidates.jsonl", "".join(
        json.dumps(row, sort_keys=True) + "\n" for row in candidates
    ))
    atomic_json(output / "scan.json", facts)
    atomic_json(output / "findings.json", payload)
    atomic_text(
        output / "report.md",
        "# Omnibus audit — C++20\n\n"
        f"Status: `{status}`\n\nC++ syntax nominates candidates; explicit scouts distinguish domains from facets.\n",
    )
    return terminal_return_code(facts, code)


def standards_main(argv: list[str] | None = None) -> int:
    parser = _parser("Measure configured C++ direct-call/if syntax coverage.")
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ideas", required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = _inside_output(root, args.output_dir, parser)
    clear_artifacts(output / name for name in ("coverage.json", "coverage.md"))
    try:
        ideas = json.loads(args.ideas.read_text(encoding="utf-8"))["ideas"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"invalid standards file: {exc}", file=sys.stderr)
        return 2
    facts, code = _facts(args)
    fact_files = {row["file"]: row for row in facts.get("files", [])}
    results: list[dict[str, Any]] = []
    for idea in ideas:
        detector = idea.get("contract", {}).get("detector", {})
        base = {
            "id": idea.get("id"), "label": idea.get("label", idea.get("id")),
            "claim_boundary": "direct C++ call spelling and if enclosure syntax only",
        }
        if detector.get("kind") in {"manual", "skill"}:
            results.append({
                **base, "status": "skipped", "situation_sites": 0, "gap_count": 0,
                "coverage_percent": None, "gaps": [],
            })
            continue
        if detector.get("kind") != "ast" or detector.get("enclosed_by") != "if":
            results.append({
                **base, "status": "language_unsupported", "situation_sites": 0,
                "gap_count": 0, "coverage_percent": None, "gaps": [],
            })
            continue
        matched: set[str] = set()
        for pattern in detector.get("paths", []):
            matched.update(
                path.relative_to(root).as_posix() for path in root.glob(pattern)
                if path.is_file() and not path.is_symlink()
                and path.suffix in {".cpp", ".cc", ".cxx"}
            )
        selected = [fact_files[path] for path in sorted(matched) if path in fact_files]
        if not selected:
            results.append({
                **base, "status": "no_files_matched", "situation_sites": 0,
                "gap_count": 0, "coverage_percent": None, "gaps": [],
            })
            continue
        try:
            call_pattern = re.compile(detector["call_matches"])
        except (KeyError, re.error):
            results.append({
                **base, "status": "error", "situation_sites": 0, "gap_count": 0,
                "coverage_percent": None, "gaps": [],
            })
            continue
        sites = [{"file": file["file"], **call} for file in selected for call in file["calls"]
                 if call_pattern.fullmatch(call["spelling"])]
        gaps = [site for site in sites if "if" not in site["enclosures"]]
        status = "scanned" if facts["status"] == "complete" else facts["status"]
        coverage = round(100 * (len(sites) - len(gaps)) / len(sites), 2) if sites else 100.0
        results.append({
            **base, "status": status, "situation_sites": len(sites),
            "gap_count": len(gaps), "coverage_percent": coverage, "gaps": gaps,
        })
    payload = {
        "status": facts["status"], "failure_kind": facts["failure_kind"],
        "analysis": {"cpp": facts}, "standards": results,
    }
    atomic_json(output / "coverage.json", payload)
    atomic_text(
        output / "coverage.md",
        "# Standard coverage — C++20\n\n"
        f"Status: `{facts['status']}`\n\nDirect call/if syntax does not prove runtime handling.\n",
    )
    total_gaps = sum(row["gap_count"] for row in results if row["status"] == "scanned")
    if code:
        return code
    return 1 if facts["status"] == "complete" and total_gaps else 0
