#!/usr/bin/env python3
"""Detect docs that drift from Django route and redirect reality."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from product_topology import (  # noqa: E402
    RouteShape,
    extract_docs_routes,
    extract_python_surface,
    extract_routes,
    iter_files,
    normalize_doc_site_route,
    route_by_name,
    route_shape_for,
    write_jsonl,
)


def _view_class(view: str) -> str:
    if "views." in view:
        return view.split("views.", 1)[1].split(".", 1)[0]
    if ".as_view" in view:
        parts = view.split(".")
        if len(parts) >= 2:
            return parts[-2]
    return view


def _target_matches(actual: str, claimed: str, shape: RouteShape) -> bool:
    actual_norm = actual.rstrip("/")
    claimed_norm = claimed.rstrip("/")
    if shape.page_prefix and claimed_norm.startswith("/" + shape.page_prefix + "/"):
        canonical = normalize_doc_site_route(
            claimed_norm, shape.page_prefix, shape.scoped_id_param or "site_id"
        )
        return canonical == actual_norm
    return actual_norm.endswith(claimed_norm)


def detect(
    project_root: Path,
    docs_root: Path,
    root_urls: Path | None = None,
) -> list[dict[str, object]]:
    shape = route_shape_for(project_root)
    url_paths = [root_urls] if root_urls is not None else None
    routes = extract_routes(project_root, url_paths=url_paths, shape=shape)
    redirects, _ = extract_python_surface(project_root)
    route_names = route_by_name(routes)
    actual_paths = {route.normalized_path.rstrip("/"): route for route in routes}
    actual_paths.update({route.normalized_path.rstrip("/") + "/": route for route in routes})

    redirect_targets_by_symbol: dict[str, list[str]] = {}
    for redirect in redirects:
        if redirect.target_name not in route_names:
            continue
        redirect_targets_by_symbol.setdefault(redirect.symbol, []).append(
            route_names[redirect.target_name].normalized_path
        )

    doc_paths = [
        path
        for path in iter_files(docs_root, (".md",))
        if not (".claude" in path.parts and "workflows" in path.parts)
    ]
    mentions, claims = extract_docs_routes(project_root, doc_paths, shape)
    page_prefix = shape.page_prefix or ""
    scoped_id = shape.scoped_id_param or "site_id"
    findings: list[dict[str, object]] = []

    for mention in mentions:
        normalized = normalize_doc_site_route(mention.route, page_prefix, scoped_id).rstrip("/")
        if normalized not in actual_paths:
            findings.append(
                {
                    "pattern": "unknown_documented_route",
                    "file": mention.file,
                    "lineno": mention.lineno,
                    "route": mention.route,
                    "summary": f"Docs mention `{mention.route}`, but no matching route pattern was found.",
                    "recommendation": "Update the doc or add an explicit compatibility route before relying on it.",
                }
            )

    for claim in claims:
        source = normalize_doc_site_route(claim.source, page_prefix, scoped_id).rstrip("/")
        source_route = actual_paths.get(source) or actual_paths.get(source + "/")
        if not source_route:
            continue
        view_class = _view_class(source_route.view)
        actual_targets: list[str] = []
        for symbol, targets in redirect_targets_by_symbol.items():
            if symbol.startswith(view_class + ".") or symbol == view_class:
                actual_targets.extend(targets)
        if not actual_targets:
            findings.append(
                {
                    "pattern": "unverified_redirect_claim",
                    "file": claim.file,
                    "lineno": claim.lineno,
                    "route": claim.source,
                    "summary": f"Docs claim `{claim.source}` redirects to `{claim.target}`, but no simple redirect call was found.",
                    "recommendation": "Verify manually or make the redirect contract explicit in tests.",
                }
            )
            continue
        if not any(_target_matches(target, claim.target, shape) for target in actual_targets):
            findings.append(
                {
                    "pattern": "stale_redirect_claim",
                    "file": claim.file,
                    "lineno": claim.lineno,
                    "route": claim.source,
                    "claimed_target": claim.target,
                    "actual_targets": sorted(set(actual_targets)),
                    "summary": f"Docs claim `{claim.source}` redirects to `{claim.target}`, actual target is {sorted(set(actual_targets))}.",
                    "recommendation": "Update docs or change the redirect after adding route-level tests.",
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--docs-root", type=Path, default=Path(".claude/docs"))
    parser.add_argument(
        "--root-urls",
        type=Path,
        default=None,
        help="Single urlconf override (default: auto-discover all urls.py + *_urls.py)",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    docs_root = args.docs_root if args.docs_root.is_absolute() else project_root / args.docs_root
    if args.root_urls is None:
        root_urls = None
    else:
        root_urls = args.root_urls if args.root_urls.is_absolute() else project_root / args.root_urls
    findings = detect(project_root, docs_root, root_urls)
    write_jsonl(findings, args.output)
    print(f"wrote {args.output}: {len(findings)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
