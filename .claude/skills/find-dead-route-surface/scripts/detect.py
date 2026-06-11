#!/usr/bin/env python3
"""Detect dead `/sites` route/template/static surfaces."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
COMMON_DIR = PROJECT_ROOT / ".claude" / "skills" / "_common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

from product_health import expand_paths, finding, line_for_offset, load_module, read_text  # noqa: E402
from product_topology import relpath, write_jsonl  # noqa: E402

SUFFIXES = (".py", ".js", ".html")
STATIC_JS_RE = re.compile(
    r"(?:static\s+['\"](?P<static>js/[^'\"]+\.js)['\"]|"
    r"src=['\"][^'\"]*/static/(?P<src>js/[^?'\"]+\.js))"
)
TEMPLATE_REF_RE = re.compile(r"['\"](?P<template>core/[^'\"]+\.html)['\"]")
PATH_RE = re.compile(r"path\(\s*['\"](?P<route>[^'\"]+)['\"].*?name\s*=\s*['\"](?P<name>[^'\"]+)['\"]", re.DOTALL)


def _line_lookup(path: Path, needle: str) -> int:
    for lineno, line in enumerate(read_text(path).splitlines(), start=1):
        if needle in line:
            return lineno
    return 1


def _script_refs(template_paths: list[Path], project_root: Path) -> tuple[set[str], list[dict[str, Any]]]:
    refs: set[str] = set()
    findings: list[dict[str, Any]] = []
    for path in template_paths:
        text = read_text(path)
        for match in STATIC_JS_RE.finditer(text):
            ref = match.group("static") or match.group("src")
            if not ref:
                continue
            rel_ref = f"static/{ref}"
            refs.add(rel_ref)
            if not (project_root / rel_ref).exists():
                findings.append(
                    finding(
                        "missing_static_js",
                        path,
                        line_for_offset(text, match.start()),
                        f"Template references `{rel_ref}`, but that static JS file is absent.",
                        "Remove the stale script tag or restore the JS file if the route still needs it.",
                        project_root,
                        confidence="high",
                        next_skill="fix-workflow",
                        guard_candidate=True,
                        static_ref=rel_ref,
                    )
                )
    return refs, findings


def _site_route_py_path(path: Path, project_root: Path) -> bool:
    file = relpath(path, project_root)
    return file.startswith(("app/pages/sites", "app/site_management")) or file in {
        "app/api/ptid.py",
    }


def _template_refs(py_paths: list[Path], project_root: Path) -> set[str]:
    refs: set[str] = set()
    for path in py_paths:
        if not _site_route_py_path(path, project_root):
            continue
        refs.update(match.group("template") for match in TEMPLATE_REF_RE.finditer(read_text(path)))
    return refs


def _site_template_name(path: Path) -> str | None:
    parts = path.parts
    if "templates" not in parts:
        return None
    idx = parts.index("templates")
    return "/".join(parts[idx + 1 :])


def _route_records(project_root: Path) -> list[dict[str, str]]:
    detector_path = PROJECT_ROOT / ".claude" / "skills" / "find-dormant" / "scripts" / "detect_urls.py"
    root_urls = project_root / "app" / "urls.py"
    if detector_path.exists() and root_urls.exists():
        module = load_module("find_dormant_detect_urls", detector_path)
        try:
            return module.walk(root_urls, project_root)
        except (OSError, TypeError, ValueError, AttributeError):
            return []
    records: list[dict[str, str]] = []
    if not root_urls.exists():
        return records
    for match in PATH_RE.finditer(read_text(root_urls)):
        records.append({"url_path": match.group("route"), "url_name": match.group("name"), "source_file": "app/urls.py"})
    return records


def _legacy_route_findings(project_root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for route in _route_records(project_root):
        url_path = str(route.get("url_path") or "")
        name = str(route.get("url_name") or "")
        if not url_path.startswith("sites") and not name.startswith("site"):
            continue
        if re.search(r"(?:prototype|legacy|dev|old)", f"{url_path} {name}", re.IGNORECASE):
            source = project_root / str(route.get("source_file") or "app/urls.py")
            records.append(
                finding(
                    "legacy_prototype_route",
                    source if source.exists() else str(route.get("source_file") or "app/urls.py"),
                    _line_lookup(source, url_path) if source.exists() else 1,
                    f"`/{url_path}` (`{name}`) looks like a prototype/dev route still exposed to users.",
                    "Confirm whether this route is intentionally live; otherwise route it through the canonical `/sites` surface or remove it with a targeted check.",
                    project_root,
                    confidence="medium",
                    next_skill="triage-debt",
                    guard_candidate=False,
                    route=url_path,
                    url_name=name,
                )
            )
    return records


def detect(project_root: Path, paths: list[str] | None = None) -> list[dict[str, object]]:
    scan_paths = expand_paths(project_root, paths, SUFFIXES)
    py_paths = [path for path in scan_paths if path.suffix == ".py"]
    js_paths = [path for path in scan_paths if path.suffix == ".js"]
    template_paths = [path for path in scan_paths if path.suffix == ".html"]

    records: list[dict[str, object]] = []
    loaded_js, script_findings = _script_refs(template_paths, project_root)
    records.extend(script_findings)
    template_refs = _template_refs(py_paths, project_root)
    site_templates = {
        name: path
        for path in template_paths
        if (name := _site_template_name(path)) and name.startswith("core/")
    }

    for ref in sorted(template_refs):
        if ref not in site_templates:
            first = next((path for path in py_paths if ref in read_text(path)), py_paths[0] if py_paths else project_root)
            records.append(
                finding(
                    "route_template_missing",
                    first,
                    _line_lookup(first, ref) if isinstance(first, Path) and first.exists() else 1,
                    f"Python route/view references `{ref}`, but no scanned template provides it.",
                    "Restore the template, update the view to the canonical template, or remove a stale route/view.",
                    project_root,
                    confidence="high",
                    next_skill="fix-workflow",
                    guard_candidate=True,
                    template=ref,
                )
            )

    for template_name, path in sorted(site_templates.items()):
        if template_name in template_refs:
            continue
        if path.name.startswith("_") or path.name in {"site_config_base.html"}:
            continue
        records.append(
            finding(
                "unreferenced_template_surface",
                path,
                1,
                f"`{template_name}` exists under the site template surface but no scanned Python view references it.",
                "Confirm this template is included dynamically; otherwise consider deleting it after a route/static reachability check.",
                project_root,
                confidence="medium",
                next_skill="triage-debt",
                guard_candidate=False,
                template=template_name,
            )
        )

    for path in js_paths:
        file = relpath(path, project_root)
        if not (
            file.startswith("static/js/site-config")
            or file.startswith("static/js/export-")
            or file.startswith("static/js/download-")
        ):
            continue
        if file in loaded_js:
            continue
        records.append(
            finding(
                "unloaded_site_static_js",
                path,
                1,
                f"`{file}` looks like a site workflow JS file but no scanned site template loads it.",
                "Confirm whether it is bundled indirectly; otherwise remove stale JS or add the missing script reference.",
                project_root,
                confidence="medium",
                next_skill="triage-debt",
                guard_candidate=False,
                static_file=file,
            )
        )

    records.extend(_legacy_route_findings(project_root))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    records = detect(args.project_root.resolve(), args.paths or None)
    write_jsonl(records, args.output)
    print(f"wrote {args.output}: {len(records)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
