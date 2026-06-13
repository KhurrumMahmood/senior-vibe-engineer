#!/usr/bin/env python3
"""Propose a canonical workflow registry from a product workflow map."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from product_topology import utc_scan_id  # noqa: E402
from workflows import workflow_steps  # noqa: E402


REGISTRY_FIELDS = (
    "id",
    "label",
    "route_name",
    "url_builder",
    "visibility_rule",
    "status_provider",
    "active_tab_key",
    "template_owner",
    "frontend_boot_keys",
    "api_endpoints",
    "api_endpoint_templates",
)


def _strip_cell(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        value = value[1:-1]
    return value.strip()


def _section(text: str, heading: str) -> list[str]:
    wanted = f"## {heading}".lower()
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip().lower() == wanted:
            start = i + 1
            break
    if start is None:
        return []
    out: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        out.append(line)
    return out


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [_strip_cell(cell) for cell in stripped.strip("|").split("|")]
        if not cells or all(set(cell) <= {"-"} for cell in cells if cell):
            continue
        if cells[0].lower() in {"step", "route", "view symbol", "global"}:
            continue
        rows.append(cells)
    return rows


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "step"


def _format_list(values: list[str]) -> str:
    if not values:
        return "none"
    return ", ".join(f"`{value}`" for value in values)


def _route_placeholders(route: str) -> set[str]:
    return set(re.findall(r"{([^{}]+)}", route))


def _load_workflow_map(
    project_root: Path,
    workflow: str,
    workflow_map: Path,
) -> dict[str, Any]:
    map_path = workflow_map if workflow_map.is_absolute() else project_root / workflow_map
    if not map_path.exists():
        raise FileNotFoundError(
            f"workflow map not found: {workflow_map}. "
            f"Run /map-product-workflow {workflow} first or pass --workflow-map."
        )
    text = map_path.read_text(encoding="utf-8")

    descriptor_steps = {
        step["route_name"]: step for step in workflow_steps(project_root)
    }
    steps: list[dict[str, str]] = []
    for cells in _table_rows(_section(text, "Workflow Steps")):
        if len(cells) < 3:
            continue
        label, route_name, path = cells[0], cells[1], cells[2]
        descriptor = descriptor_steps.get(route_name)
        steps.append({
            "id": descriptor["id"] if descriptor else _slug(label),
            "label": label,
            "route_name": route_name,
            "path": path,
        })

    if not steps:
        raise ValueError(
            f"workflow map {workflow_map} contains no workflow steps; "
            "refresh the map after declaring steps in .engineering/docs/product-workflows.md."
        )

    api_endpoints: list[str] = []
    api_endpoint_templates: list[str] = []
    for cells in _table_rows(_section(text, "Site-Scoped API Routes")):
        if len(cells) < 2:
            continue
        route, name = cells[0], cells[1]
        if not name or name == "—":
            name = route
        placeholders = _route_placeholders(route)
        # A scoped id alone is static from the consumer's perspective; extra
        # placeholders require a named endpoint template.
        if len(placeholders) > 1:
            api_endpoint_templates.append(name)
        else:
            api_endpoints.append(name)

    boot_keys: list[str] = []
    for cells in _table_rows(_section(text, "Frontend Boot Contract")):
        if not cells:
            continue
        key = cells[0]
        if key.startswith("window."):
            key = key.removeprefix("window.")
        boot_keys.append(key)

    template_owners: list[str] = []
    for cells in _table_rows(_section(text, "View / Template Ownership")):
        if len(cells) >= 2 and cells[1] and cells[1] != "—":
            template_owners.append(cells[1])

    return {
        "workflow_map": workflow_map,
        "steps": steps,
        "frontend_boot_keys": sorted(dict.fromkeys(boot_keys)),
        "api_endpoints": sorted(dict.fromkeys(api_endpoints)),
        "api_endpoint_templates": sorted(dict.fromkeys(api_endpoint_templates)),
        "template_owners": sorted(dict.fromkeys(template_owners)),
    }


def render_proposal(
    workflow: str,
    registry: dict[str, Any],
    findings: list[Path],
) -> str:
    workflow_map = registry["workflow_map"]
    steps = registry["steps"]
    lines: list[str] = [
        f"# Workflow registry proposal — {workflow}",
        "",
        f"**Source map:** `{workflow_map}`",
        "",
        "## Intent",
        "",
        "Define user-visible workflow steps once, then make sidebar, dashboard, redirects,",
        "templates, and frontend boot payloads consume that registry instead of repeating",
        "step knowledge in separate files.",
        "",
        "## Registry Shape",
        "",
        "| Field | Meaning |",
        "|---|---|",
    ]
    meanings = {
        "id": "Stable step id used by backend and frontend.",
        "label": "Human label shown in navigation/status UI.",
        "route_name": "Canonical Django route name.",
        "url_builder": "Server-side URL construction, usually `reverse()`.",
        "visibility_rule": "Callable/key deciding whether the step is visible/enabled.",
        "status_provider": "Callable/key producing sidebar/dashboard status.",
        "active_tab_key": "Template/sidebar active-state key.",
        "template_owner": "Primary template for the step.",
        "frontend_boot_keys": "Fields exported into the canonical boot payload.",
        "api_endpoints": "Static scoped endpoints exported into the boot payload.",
        "api_endpoint_templates": "Endpoint templates with extra named path parameters.",
    }
    for field in REGISTRY_FIELDS:
        lines.append(f"| `{field}` | {meanings[field]} |")

    boot_keys = registry["frontend_boot_keys"]
    api_endpoints = registry["api_endpoints"]
    api_endpoint_templates = registry["api_endpoint_templates"]

    lines.extend([
        "",
        f"## Proposed `{workflow}` Entries",
        "",
        "| id | label | route | active tab | boot keys |",
        "|---|---|---|---|---|",
    ])
    for step in steps:
        lines.append(
            f"| `{step['id']}` | {step['label']} | `{step['route_name']}` | "
            f"`{step['id']}` | {_format_list(boot_keys)} |"
        )

    lines.extend([
        "",
        "## Endpoint Payload Fields",
        "",
        f"- `api_endpoints`: {_format_list(api_endpoints)}",
        f"- `api_endpoint_templates`: {_format_list(api_endpoint_templates)}",
    ])
    if registry["template_owners"]:
        lines.append(f"- Template owners observed in map: {_format_list(registry['template_owners'])}")

    lines.extend(
        [
            "",
            "## Execution Plan",
            "",
            "1. Add a pure registry module with the fields above and no database writes.",
            "2. Move sidebar/dashboard step definitions to read from the registry.",
            "3. Move redirects to registry route names where behavior is already pinned by tests.",
            "4. Replace template-scattered boot globals with one `window.SITES_CONFIG` payload.",
            "5. Only after compatibility tests pass, group routes behind a workflow-owned include boundary.",
            "",
            "## Inputs Consulted",
            "",
        ]
    )
    lines.append(f"- `{workflow_map}`")
    for path in findings:
        lines.append(f"- `{path}`")

    lines.extend(
        [
            "",
            "## Guard Candidates",
            "",
            "- Route ownership: block new `/sites` routes directly in the global root URL file after grouping lands.",
            "- Frontend boot payload: block new template-level `window.*` globals outside the canonical payload.",
            "- Docs-route drift: periodically compare documented redirects against actual route/view redirects.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", help="Workflow name; matches the host's product-workflows.md.")
    parser.add_argument(
        "--workflow-map",
        type=Path,
        default=None,
        help="Workflow map from /map-product-workflow "
             "(default: .claude/docs/workflows/<workflow>.md)",
    )
    parser.add_argument("--finding", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scan-id", default=None)
    parser.add_argument("--skip-effectiveness-log", action="store_true")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    scan_id = args.scan_id or utc_scan_id("workflow-registry")
    output = args.output or project_root / "reports" / "workflow-registry" / args.workflow / "proposal.md"
    workflow_map = args.workflow_map or Path(".claude/docs/workflows") / f"{args.workflow}.md"
    try:
        registry = _load_workflow_map(project_root, args.workflow, workflow_map)
    except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for finding in args.finding:
        finding_path = finding if finding.is_absolute() else project_root / finding
        if not finding_path.exists():
            print(f"error: finding input not found: {finding}", file=sys.stderr)
            return 1

    markdown = render_proposal(args.workflow, registry, args.finding)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")

    if not args.skip_effectiveness_log:
        buckets = {
            "registry_fields": len(REGISTRY_FIELDS),
            "steps": len(registry["steps"]),
            "api_endpoints": len(registry["api_endpoints"]),
            "api_endpoint_templates": len(registry["api_endpoint_templates"]),
        }
        subprocess.run(
            [
                sys.executable,
                "scripts/log_effectiveness.py",
                "--skill",
                "extract-workflow-registry",
                "--scan-id",
                scan_id,
                "--target",
                args.workflow,
                "--findings-total",
                str(sum(buckets.values())),
                "--buckets",
                json.dumps(buckets, sort_keys=True),
            ],
            cwd=project_root,
            check=False,
        )
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
