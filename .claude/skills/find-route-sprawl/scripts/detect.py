#!/usr/bin/env python3
"""Detect product route sprawl in flat Django URL modules."""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
import scope as _scope  # noqa: E402
from product_topology import extract_routes, relpath, write_jsonl  # noqa: E402


def _discover_root_urls(project_root: Path) -> Path | None:
    """Find the Django root URLconf without a hardcoded source root.

    Enumerates `**/urls.py` through the per-skill scope universe (ignore-first;
    honors `.engineering/docs/find-route-sprawl-scope.md` when present), then
    prefers the one in the Django project package — the directory that also
    holds settings/wsgi/asgi. Falls back to the shallowest `urls.py` for a
    deterministic pick, or ``None`` when the repo has no `urls.py` at all.
    """
    candidates = [
        p
        for p in _scope.scan(project_root, "find-route-sprawl", extensions=frozenset({".py"}))
        if p.name == "urls.py"
    ]
    if not candidates:
        return None
    project_markers = {"settings.py", "settings", "wsgi.py", "asgi.py"}
    for path in candidates:
        if {sibling.name for sibling in path.parent.iterdir()} & project_markers:
            return path
    return min(candidates, key=lambda p: (len(p.relative_to(project_root).parts), str(p)))


def detect(project_root: Path, root_urls: Path, page_threshold: int, api_threshold: int) -> list[dict[str, object]]:
    routes = extract_routes(project_root, [root_urls])
    root_file = relpath(root_urls, project_root)
    root_routes = [route for route in routes if route.file == root_file]
    site_pages = [route for route in root_routes if route.is_site_page]
    site_apis = [route for route in root_routes if route.is_site_scoped_api]
    includes = [route for route in routes if route.is_include and ("sites" in route.route or "site" in route.view)]

    findings: list[dict[str, object]] = []
    if len(site_pages) > page_threshold:
        findings.append(
            {
                "pattern": "flat_site_page_routes",
                "file": site_pages[0].file if site_pages else str(root_urls),
                "lineno": site_pages[0].lineno if site_pages else 0,
                "count": len(site_pages),
                "summary": f"{len(site_pages)} `/sites/<site_id>/...` page routes live directly in the root URL file.",
                "recommendation": "Group product workflow page routes behind a workflow-owned include() module.",
            }
        )
    if len(site_apis) > api_threshold:
        findings.append(
            {
                "pattern": "flat_site_scoped_api_routes",
                "file": site_apis[0].file if site_apis else str(root_urls),
                "lineno": site_apis[0].lineno if site_apis else 0,
                "count": len(site_apis),
                "summary": f"{len(site_apis)} site-scoped API routes are mixed into the global API namespace.",
                "recommendation": "Group site-scoped APIs by workflow owner before adding new aliases.",
            }
        )
    if site_pages and not includes:
        findings.append(
            {
                "pattern": "missing_workflow_include",
                "file": site_pages[0].file,
                "lineno": site_pages[0].lineno,
                "count": len(site_pages),
                "summary": "Site workflow routes are declared inline; no workflow include() boundary was found.",
                "recommendation": "Introduce a route include boundary once compatibility tests pin existing names.",
            }
        )

    route_spans: dict[str, list[int]] = defaultdict(list)
    for route in site_pages:
        first_segment = route.route.split("/", 3)[2] if route.route.count("/") >= 2 else route.route
        route_spans[first_segment].append(route.lineno)
    for segment, lines in sorted(route_spans.items()):
        if len(lines) < 2:
            continue
        if max(lines) - min(lines) > 100:
            findings.append(
                {
                    "pattern": "scattered_route_family",
                    "file": site_pages[0].file,
                    "lineno": min(lines),
                    "segment": segment,
                    "summary": f"`/sites/<site_id>/{segment}/...` routes are separated by {max(lines) - min(lines)} lines.",
                    "recommendation": "Keep related workflow routes adjacent or behind the same include().",
                }
            )

    by_name_view: dict[tuple[str, str], list[object]] = defaultdict(list)
    for route in routes:
        if route.name and route.view:
            by_name_view[(route.name, route.view)].append(route)
    for (name, view), duplicates in sorted(by_name_view.items()):
        paths = {route.route for route in duplicates}
        if len(paths) > 1:
            first = duplicates[0]
            findings.append(
                {
                    "pattern": "duplicate_route_alias_surface",
                    "file": first.file,
                    "lineno": first.lineno,
                    "name": name,
                    "view": view,
                    "routes": sorted(paths),
                    "summary": f"`{name}` maps `{view}` through {len(paths)} route strings.",
                    "recommendation": "Document compatibility aliases and test both paths if they must coexist.",
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--root-urls",
        type=Path,
        default=None,
        help="Root URLconf to scan; auto-discovered via scope when omitted.",
    )
    parser.add_argument("--page-threshold", type=int, default=6)
    parser.add_argument("--api-threshold", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    root_urls = args.root_urls
    if root_urls is None:
        root_urls = _discover_root_urls(project_root)
        if root_urls is None:
            write_jsonl([], args.output)
            print(f"wrote {args.output}: 0 findings (no urls.py found)")
            return 0
    elif not root_urls.is_absolute():
        root_urls = project_root / root_urls
    findings = detect(project_root, root_urls, args.page_threshold, args.api_threshold)
    write_jsonl(findings, args.output)
    print(f"wrote {args.output}: {len(findings)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
