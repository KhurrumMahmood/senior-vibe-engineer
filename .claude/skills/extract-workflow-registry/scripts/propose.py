#!/usr/bin/env python3
"""Propose a canonical workflow registry from a product workflow map."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from product_topology import SITE_WORKFLOW_STEPS, utc_scan_id  # noqa: E402


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
)


def render_proposal(workflow: str, workflow_map: Path, findings: list[Path]) -> str:
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
    }
    for field in REGISTRY_FIELDS:
        lines.append(f"| `{field}` | {meanings[field]} |")

    lines.extend(["", "## Proposed `/sites` Entries", "", "| id | label | route | active tab |", "|---|---|---|---|"])
    for step in SITE_WORKFLOW_STEPS:
        lines.append(
            f"| `{step['id']}` | {step['label']} | `{step['route_name']}` | `{step['id']}` |"
        )

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
    parser.add_argument("workflow", choices=["sites"])
    parser.add_argument("--workflow-map", type=Path, default=Path(".claude/docs/workflows/sites.md"))
    parser.add_argument("--finding", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scan-id", default=None)
    parser.add_argument("--skip-effectiveness-log", action="store_true")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    scan_id = args.scan_id or utc_scan_id("workflow-registry")
    output = args.output or project_root / "reports" / "workflow-registry" / args.workflow / "proposal.md"
    markdown = render_proposal(args.workflow, args.workflow_map, args.finding)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")

    if not args.skip_effectiveness_log:
        buckets = {"registry_fields": len(REGISTRY_FIELDS), "steps": len(SITE_WORKFLOW_STEPS)}
        subprocess.run(
            [
                "python3",
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
