#!/usr/bin/env python3
"""Emit review-only dormant Dart top-level function candidates."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


def _provider():
    candidates = [Path(__file__).with_name("dart_lsp_facts.py")]
    candidates.extend(
        parent / "map-subsystem" / "scripts" / "dart_lsp_facts.py"
        for parent in Path(__file__).resolve().parents
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError("assembled Dart LSP fact provider is missing")
    spec = importlib.util.spec_from_file_location("dart_dormant_lsp_facts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def _declarations(root: Path, target: Path) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"^(?:(?:external|static)\s+)?(?:[A-Za-z_$][\w$]*(?:<[^;{}=]+>)?[?!]?\s+)?(?P<name>_[A-Za-z_$][\w$]*)\s*(?:<[^;{}=]+>)?\s*\("
    )
    paths = [target] if target.is_file() else sorted(target.rglob("*.dart"))
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            continue
        depth = 0
        in_block_comment = False
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            stripped = line.strip()
            if "/*" in line:
                in_block_comment = True
            if depth == 0 and not in_block_comment and not stripped.startswith(("//", "@")):
                match = pattern.match(line)
                if match:
                    rows.append(
                        {
                            "name": match.group("name"),
                            "file": path.relative_to(root).as_posix(),
                            "line": line_no,
                            "column": match.start("name") + 1,
                        }
                    )
            # Bounded declaration discovery; LSP owns identity and diagnostics.
            code = re.sub(r"//.*$", "", line)
            depth += code.count("{") - code.count("}")
            depth = max(depth, 0)
            if "*/" in line:
                in_block_comment = False
    return rows


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# find-dormant — Dart review candidates",
        "",
        "> Read-only selected-configuration evidence. No candidate is proof that deletion is safe.",
        "",
        f"Status: `{payload['status']}`",
        f"Review-required candidates: `{len(payload['candidates'])}`",
        "Certain-delete findings: `0`",
        "",
        "## Candidates",
        "",
    ]
    lines.extend(
        f"- `{row['file']}:{row['line']}` `{row['name']}` — zero selected-workspace LSP references; human runtime review required"
        for row in payload["candidates"]
    )
    if not payload["candidates"]:
        lines.append("None on the eligible selected-workspace surface.")
    lines.extend(["", "## Uncertain and deferred", ""])
    lines.extend(
        f"- `{row.get('file', row.get('path', 'project'))}:{row.get('line', 0)}` — {row['reason']}"
        for row in payload["uncertain"]
    )
    if not payload["uncertain"]:
        lines.append("None recorded.")
    lines.extend(["", "## Limitations", "", *[f"- {item}" for item in payload["limits"]], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--dart", default="dart")
    parser.add_argument("--packages", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    root = Path(os.path.realpath(args.project_root.resolve(strict=True)))
    target = Path(os.path.realpath((root / args.target).resolve(strict=True)))
    try:
        target.relative_to(root)
    except ValueError:
        parser.error("target must stay inside project root")
    declarations = _declarations(root, target)
    provider = _provider()
    facts = provider.load_or_collect(
        facts=args.facts,
        project_root=root,
        target=args.target,
        queries=[row["name"] for row in declarations],
        dart=args.dart,
        packages=args.packages,
        cache_dir=args.cache_dir,
        timeout=args.timeout,
    )
    roles = {row["path"]: row["role"] for row in facts.get("source_inventory", [])}
    reference_by_declaration = {
        (row["declaration"]["path"], row["declaration"]["line"], row["name"]): row
        for row in facts.get("reference_queries", [])
    }
    unresolved = facts.get("unresolved_requests", [])
    unresolved_source_paths = {
        row.get("path")
        for row in facts.get("boundaries", [])
        if row.get("kind") in {"augmentation", "conditional-directive", "part"}
    }
    candidates: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    all_production_text = "\n".join(
        (root / row["path"]).read_text(encoding="utf-8", errors="replace")
        for row in facts.get("source_inventory", [])
        if row.get("role") == "production"
    )
    for declaration in declarations:
        if roles.get(declaration["file"]) != "production":
            continue
        if declaration["file"] in unresolved_source_paths:
            uncertain.append(
                {
                    **declaration,
                    "reason": "conditional/part/augmentation source cannot nominate a dormant candidate",
                }
            )
            continue
        reference = reference_by_declaration.get(
            (declaration["file"], declaration["line"], declaration["name"])
        )
        request_failed = any(
            row.get("method") == "textDocument/references"
            and row.get("name") == declaration["name"]
            and row.get("source") == declaration["file"]
            and row.get("line") == declaration["line"]
            for row in unresolved
        )
        string_hit = re.search(rf"['\"]{re.escape(declaration['name'])}['\"]", all_production_text)
        if string_hit:
            uncertain.append(
                {
                    **declaration,
                    "reason": "string/reflection-like name match is not reachability evidence",
                }
            )
            continue
        if request_failed or reference is None:
            uncertain.append({**declaration, "reason": "LSP reference lineage is unresolved"})
            continue
        references = reference.get("references", [])
        if references:
            continue
        if facts.get("status") == "failed":
            uncertain.append(
                {
                    **declaration,
                    "reason": "failed Dart semantic analysis cannot nominate a candidate",
                }
            )
            continue
        candidates.append(
            {
                **declaration,
                "classification": "review_required",
                "resolved_reference_count": 0,
                "certain_delete": False,
                "evidence": "textDocument/references(includeDeclaration=false)",
            }
        )
    for boundary in facts.get("boundaries", []):
        uncertain.append(
            {
                "file": boundary.get("path", "project"),
                "line": boundary.get("line", 0),
                "reason": f"{boundary.get('kind')} is outside dormant reachability claims",
            }
        )
    status = facts.get("status", "failed")
    payload: dict[str, Any] = {
        "schema_version": "dart-dormant-v1",
        "language": "dart",
        "read_only": True,
        "status": status,
        "target": target.relative_to(root).as_posix(),
        "analyzer": "dart-sdk-lsp-selected-references",
        "candidates": candidates,
        "uncertain": uncertain,
        "summary": {
            "review_required": len(candidates),
            "uncertain": len(uncertain),
            "certain_delete": 0,
        },
        "fact_pack_sha256": facts.get("fact_pack_sha256"),
        "query_plan_sha256": facts.get("query_plan_sha256"),
        "source_hashes": facts.get("source_hashes", []),
        "limits": facts.get("limits", []),
        "reason": facts.get("failure_kind"),
    }
    output = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    output = Path(os.path.abspath(output))
    try:
        relative = output.relative_to(root / "reports" / "find-dormant")
    except ValueError:
        parser.error("output-dir must stay beneath reports/find-dormant/")
    if not relative.parts:
        parser.error("output-dir must name a scan")
    current = root
    for part in output.relative_to(root).parts:
        current /= part
        if current.exists() and current.is_symlink():
            parser.error("output-dir must not traverse a symbolic link")
    scan = {
        "schema_version": "dart-dormant-scan-v1",
        "status": status,
        "candidate_count": len(candidates),
        "certain_delete": 0,
        "facts_sha256": facts.get("fact_pack_sha256"),
        "findings_sha256": None,
    }
    findings_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    scan["findings_sha256"] = __import__("hashlib").sha256(findings_text.encode()).hexdigest()
    _atomic(output / "facts.json", json.dumps(facts, indent=2, sort_keys=True) + "\n")
    _atomic(output / "findings.json", findings_text)
    _atomic(output / "scan.json", json.dumps(scan, indent=2, sort_keys=True) + "\n")
    _atomic(output / "report.md", _render(payload))
    print(f"wrote Dart dormant evidence: {output}")
    return 2 if status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
