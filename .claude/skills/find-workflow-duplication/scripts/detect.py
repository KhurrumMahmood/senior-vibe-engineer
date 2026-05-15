#!/usr/bin/env python3
"""Detect duplicated product-workflow knowledge across code surfaces."""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from product_topology import label_hits, sites_workflow_text_files, workflow_text_files, write_jsonl  # noqa: E402

SCRIPT_SRC_RE = re.compile(
    r"(?:static\s+['\"](?P<static>js/[^'\"]+\.js)['\"]|"
    r"src=['\"][^'\"]*/static/(?P<src>js/[^'\"]+\.js))"
)


def _owner(file: str) -> str:
    if file.endswith("urls.py") or file.endswith("api_urls.py"):
        return "routes"
    if file.startswith("core/views/"):
        return "views"
    if file.startswith("core/services/"):
        return "services"
    if file.startswith("templates/"):
        return "templates"
    if file.startswith("static/js/"):
        return "javascript"
    if file.startswith("docs/") or file.startswith(".claude/docs/"):
        return "docs"
    return file.split("/", 1)[0]


def _active_site_js_files(project_root: Path) -> set[str]:
    template_paths = sorted((project_root / "templates" / "core").glob("site_config*.html"))
    template_paths.extend(sorted((project_root / "templates" / "core" / "includes").glob("*.html")))
    active: set[str] = set()
    for path in template_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in SCRIPT_SRC_RE.finditer(text):
            js_path = match.group("static") or match.group("src")
            if js_path:
                active.add(f"static/{js_path}")
    return active


def _surface(file: str, active_js_files: set[str] | None) -> str:
    if file.startswith("docs/") or file.startswith(".claude/docs/"):
        return "docs"
    if file.startswith("tests/") or file.startswith("testing/"):
        return "tests"
    if file.endswith("urls.py") or file.endswith("api_urls.py"):
        return "route_definition"
    if file.startswith("static/js/"):
        if active_js_files is None:
            return "active_executable"
        return "active_executable" if file in active_js_files else "legacy_unloaded"
    if file.startswith("templates/core/site_config") or file.startswith("templates/core/includes/"):
        return "active_executable"
    if file.startswith("core/views/") or file.startswith("core/services/"):
        return "active_executable"
    return "other"


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def detect(project_root: Path, min_owners: int, workflow: str, min_active_owners: int) -> list[dict[str, object]]:
    paths = sites_workflow_text_files(project_root) if workflow == "sites" else workflow_text_files(project_root)
    active_js_files = _active_site_js_files(project_root) if workflow == "sites" else None
    hits = label_hits(project_root, paths)
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for hit in hits:
        grouped[(str(hit["kind"]), str(hit["value"]))].append(hit)

    findings: list[dict[str, object]] = []
    for (kind, value), group in sorted(grouped.items()):
        owners = sorted({_owner(str(hit["file"])) for hit in group})
        files = sorted({str(hit["file"]) for hit in group})
        if len(owners) < min_owners:
            continue
        surface_by_file = {file: _surface(file, active_js_files) for file in files}
        active_files = sorted(file for file in files if surface_by_file[file] == "active_executable")
        active_owners = sorted(
            {
                _owner(str(hit["file"]))
                for hit in group
                if _surface(str(hit["file"]), active_js_files) == "active_executable"
            }
        )
        if len(active_owners) < min_active_owners:
            continue
        surfaces = [_surface(str(hit["file"]), active_js_files) for hit in group]
        deferred_files = sorted(
            file
            for file in files
            if surface_by_file[file] in {"docs", "tests", "legacy_unloaded", "route_definition"}
        )
        first = group[0]
        pattern = {
            "label": "duplicated_workflow_label",
            "tab_id": "duplicated_workflow_tab_id",
            "route_literal": "duplicated_route_literal",
        }.get(kind, "duplicated_workflow_knowledge")
        active_summary = (
            f" Active executable surface: {len(active_files)} files across "
            f"{len(active_owners)} owner layers."
        )
        findings.append(
            {
                "pattern": pattern,
                "kind": kind,
                "value": value,
                "file": first["file"],
                "lineno": first["lineno"],
                "owners": owners,
                "active_owners": active_owners,
                "surface_counts": _counts(surfaces),
                "files": files[:12],
                "active_files": active_files[:12],
                "deferred_files": deferred_files[:12],
                "count": len(group),
                "summary": (
                    f"`{value}` appears {len(group)} times across {len(owners)} owner layers: "
                    f"{', '.join(owners)}.{active_summary}"
                ),
                "recommendation": (
                    "Move active workflow authority toward the canonical registry; treat docs, "
                    "route definitions, and unloaded legacy files as context or follow-up scope."
                ),
            }
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--workflow", choices=["sites", "generic"], default="sites")
    parser.add_argument("--min-owners", type=int, default=3)
    parser.add_argument("--min-active-owners", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    findings = detect(args.project_root.resolve(), args.min_owners, args.workflow, args.min_active_owners)
    write_jsonl(findings, args.output)
    print(f"wrote {args.output}: {len(findings)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
