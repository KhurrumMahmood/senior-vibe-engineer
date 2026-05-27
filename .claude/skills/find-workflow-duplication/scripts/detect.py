#!/usr/bin/env python3
"""Detect duplicated product-workflow knowledge across code surfaces."""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from product_topology import label_hits, workflow_text_files, write_jsonl  # noqa: E402
import workflows  # noqa: E402

SCRIPT_SRC_RE = re.compile(
    r"(?:static\s+['\"](?P<static>js/[^'\"]+\.js)['\"]|"
    r"src=['\"][^'\"]*/static/(?P<src>js/[^'\"]+\.js))"
)


# Backend layer segments matched as path *components*, so `app/pages/x.py`,
# `core/views/x.py`, and `src/services/y.py` all classify by their conventional
# segment rather than a baked source-root prefix. ADR-0011 split pnci's old
# `core/views` into `app/pages` + `app/api`, which a prefix literal would miss.
_BACKEND_LAYER_SEGMENTS = ("views", "pages", "api", "services", "tasks")


def _owner(file: str) -> str:
    if file.endswith("urls.py") or file.endswith("api_urls.py"):
        return "routes"
    if file.startswith("docs/") or file.startswith(".claude/docs/"):
        return "docs"
    if file.startswith("templates/") or "/templates/" in file:
        return "templates"
    if file.startswith("static/js/") or file.endswith(".js"):
        return "javascript"
    segments = file.split("/")
    for segment in segments:
        if segment in _BACKEND_LAYER_SEGMENTS:
            return segment
    return segments[0]


def _resolve_ui_surfaces(project_root: Path) -> tuple[set[str], set[str] | None]:
    """Resolve the host's UI templates and the JS those templates ``<script>``-load.

    UI templates are host-declared via ``## UI template globs`` in
    ``.engineering/docs/product-workflows.md``; the first return value is their
    repo-relative paths (the active executable template surface). The second is
    the JS they load — used to split loaded ("active_executable") from unloaded
    ("legacy_unloaded") workflow JS.

    When the host declares no UI template globs we cannot tell loaded JS from
    legacy, so the JS set is ``None`` (every JS file counts as active — the old
    ``--workflow generic`` behaviour) and no template is marked active. This is
    the ignore-first contract: a repo with no descriptor assumes no UI layout.
    """
    globs = workflows.workflow_ui_template_globs(project_root)
    if not globs:
        return set(), None
    ui_template_files: set[str] = set()
    active_js_files: set[str] = set()
    for glob in globs:
        for path in sorted(project_root.glob(glob)):
            if not path.is_file():
                continue
            ui_template_files.add(path.relative_to(project_root).as_posix())
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in SCRIPT_SRC_RE.finditer(text):
                js_path = match.group("static") or match.group("src")
                if js_path:
                    active_js_files.add(f"static/{js_path}")
    return ui_template_files, active_js_files


def _surface(file: str, active_js_files: set[str] | None, ui_template_files: set[str]) -> str:
    if file.startswith("docs/") or file.startswith(".claude/docs/"):
        return "docs"
    if file.startswith("tests/") or file.startswith("testing/"):
        return "tests"
    if file.endswith("urls.py") or file.endswith("api_urls.py"):
        return "route_definition"
    if file.startswith("static/js/") or file.endswith(".js"):
        if active_js_files is None:
            return "active_executable"
        return "active_executable" if file in active_js_files else "legacy_unloaded"
    if file in ui_template_files:
        return "active_executable"
    if _owner(file) in _BACKEND_LAYER_SEGMENTS:
        return "active_executable"
    return "other"


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def detect(project_root: Path, min_owners: int, min_active_owners: int) -> list[dict[str, object]]:
    paths = workflow_text_files(project_root)
    ui_template_files, active_js_files = _resolve_ui_surfaces(project_root)
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
        surface_by_file = {file: _surface(file, active_js_files, ui_template_files) for file in files}
        active_files = sorted(file for file in files if surface_by_file[file] == "active_executable")
        active_owners = sorted(
            {
                _owner(str(hit["file"]))
                for hit in group
                if _surface(str(hit["file"]), active_js_files, ui_template_files) == "active_executable"
            }
        )
        if len(active_owners) < min_active_owners:
            continue
        surfaces = [_surface(str(hit["file"]), active_js_files, ui_template_files) for hit in group]
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
    parser.add_argument("--min-owners", type=int, default=3)
    parser.add_argument("--min-active-owners", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    findings = detect(args.project_root.resolve(), args.min_owners, args.min_active_owners)
    write_jsonl(findings, args.output)
    print(f"wrote {args.output}: {len(findings)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
