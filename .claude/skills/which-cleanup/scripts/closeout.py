#!/usr/bin/env python3
"""Build, rank, and render the /which-cleanup closeout artifact.

Consumes the resolved scope + tiered roster and produces the `closeout.json` /
`closeout.md` pair. For the `large` band it also generates a sequenced
MAP->SUSPECT->EXPLAIN->REFACTOR->GUARD plan, a `/refactor-subsystem` spec stub,
and a Claude Code Workflow script skeleton. Advisory only — it never runs the
recommended skills (that is the orchestrator's / human's call).
"""
from __future__ import annotations

from typing import Any

_SCOPED_JOBS = {"suspect", "explain", "refactor"}  # commands carry the changed paths


def _command(skill: str, job: str | None, paths: list[str]) -> str:
    """Runnable slash-invocation for a roster item, scoped to the changed files when apt."""
    if job in _SCOPED_JOBS and paths:
        return f"/{skill} " + " ".join(paths)
    return f"/{skill}"


def _rank_key(item: dict[str, Any]) -> tuple[int, str]:
    # Subsystem-specific scanners before the universal floor; then alpha.
    floor = "universal closeout floor" in item.get("why", "")
    return (1 if floor else 0, item["skill"])


def build(
    *,
    target: str,
    scope_band: str,
    axis_breakdown: dict[str, str],
    resolved_paths: list[str],
    report: dict[str, Any],
    roster: dict[str, Any],
    max_scouts: int,
) -> dict[str, Any]:
    """Assemble the closeout dict (sans scan_id/generated, which run.py stamps)."""
    subsystems = sorted(e["name"] for e in report.get("subsystems", []))
    unmatched = sorted(report.get("unmatched", []))

    checklist: dict[str, list[dict[str, Any]]] = {}
    for band_key, items in roster["buckets"].items():
        ranked = sorted(items, key=_rank_key)
        checklist[band_key] = [
            {**item, "command": _command(item["skill"], item.get("job"), resolved_paths)}
            for item in ranked
        ]

    # Medium band actively dispatches a capped subset of the post-sweep scanners
    # as concurrent read-only scouts scoped to the changed files.
    fanout: list[dict[str, Any]] = []
    if scope_band == "medium":
        fanout = checklist["post_sweep"][:max_scouts]

    notes = (
        "Advisory only — recommends cleanup skills scaled to scope; does not run or "
        "fix anything. Post-sweep first (the most-skipped tier); guard-tail closes the loop."
    )
    return {
        "skill": "which-cleanup",
        "target": target,
        "scope_band": scope_band,
        "axis_breakdown": axis_breakdown,
        "resolved_paths": sorted(resolved_paths),
        "subsystems": subsystems,
        "unmatched": unmatched,
        "checklist": checklist,
        "dropped": roster["dropped"],
        "fanout": fanout,
        "notes": notes,
    }


# --------------------------------------------------------------------------- #
# Rendering                                                                    #
# --------------------------------------------------------------------------- #

_BAND_TITLES = {
    "pre_baseline": "Pre-baseline (would have wanted a *before* snapshot)",
    "post_sweep": "Post-sweep (run these against what changed)",
    "guard_tail": "Guard-tail (close the loop so it can't recur)",
}


def _display_command(item: dict[str, Any], n_paths: int) -> str:
    """Abbreviate a path-heavy scoped command for the human render (JSON keeps it full)."""
    cmd = item["command"]
    if cmd.count(" ") > 3 and n_paths > 3:
        return f"/{item['skill']} «{n_paths} changed files»"
    return cmd


def _render_items(items: list[dict[str, Any]], n_paths: int) -> list[str]:
    if not items:
        return ["  _(none implied for this change)_"]
    lines = []
    for it in items:
        lines.append(f"  - **/{it['skill']}** — {it['why']}")
        lines.append(f"    `{_display_command(it, n_paths)}`")
    return lines


def render_md(c: dict[str, Any]) -> str:
    n_paths = len(c["resolved_paths"])
    lines: list[str] = []
    lines.append(f"# /which-cleanup — closeout ({c['scope_band']})")
    lines.append("")
    lines.append(f"**Target:** `{c['target']}`  ")
    lines.append(f"**Generated:** {c.get('generated', '(unstamped)')}  ")
    lines.append(f"**Scope band:** `{c['scope_band']}` "
                 f"(files={c['axis_breakdown']['files']}, "
                 f"subsystems={c['axis_breakdown']['subsystems']}, "
                 f"diff_loc={c['axis_breakdown']['diff_loc']})  ")
    subs = ", ".join(c["subsystems"]) or "(none matched the registry)"
    lines.append(f"**Subsystems touched:** {subs}  ")
    lines.append(f"**Files:** {len(c['resolved_paths'])}"
                 + (f" · **unmatched:** {len(c['unmatched'])}" if c["unmatched"] else ""))
    lines.append("")

    if c.get("scope_caveat"):
        lines.append(f"> ⚠️ {c['scope_caveat']}")
        lines.append("")

    if c["scope_band"] == "trivial":
        lines.append("> Trivial scope — run the touched test; no cleanup pass warranted. "
                     "Optional `/decide` if this revealed a recurring pattern.")
        lines.append("")

    for band_key in ("post_sweep", "pre_baseline", "guard_tail"):
        lines.append(f"## {_BAND_TITLES[band_key]}")
        lines.extend(_render_items(c["checklist"][band_key], n_paths))
        lines.append("")

    if c["scope_band"] != "trivial":
        lines.append("## 📝 Documentation — update what this change touched")
        lines.append("Closeout biases toward keeping docs current, not just code:")
        lines.append("  - Refresh the reference docs describing the changed surface (per the repo's "
                     "keep-docs-current policy) — don't leave the prose behind the code.")
        lines.append("  - If you changed agent rules (CLAUDE.md / .claude/docs/*), sync the cross-tool "
                     "mirrors (.augment / AGENTS.md / .codex / .cursor / .gemini).")
        lines.append("  - Doc-drift scans: `/find-comment-drift` (in the floor) plus the repo's "
                     "doc / route / rule-surface drift scans.")
        lines.append("")

    if c["scope_band"] == "medium" and c["fanout"]:
        lines.append("## Medium scope — dispatch these as scoped scouts")
        lines.append("")
        lines.append("Run the post-sweep scanners concurrently as **read-only scouts scoped "
                     "to the changed files** (cheap Haiku dispatch), then triage the union:")
        for it in c["fanout"]:
            lines.append(f"  - `{it['command']}`")
        lines.append("")

    if c["scope_band"] == "large":
        lines.append(_large_plan_md(c))
        lines.append("")

    if c["dropped"]:
        names = ", ".join(f"/{d['skill']}" for d in c["dropped"])
        lines.append(f"> Registry-related but not closeout scans (dropped): {names}")
        lines.append("")

    if n_paths:
        lines.append(f"## Changed files ({n_paths})")
        shown = c["resolved_paths"][:25]
        lines.extend(f"  - `{p}`" for p in shown)
        if n_paths > len(shown):
            lines.append(f"  - … (+{n_paths - len(shown)} more)")
        if c["unmatched"]:
            lines.append(f"  _{len(c['unmatched'])} file(s) matched no registry subsystem._")
        lines.append("")

    lines.append("---")
    lines.append(c["notes"])
    return "\n".join(lines).rstrip() + "\n"


def _phase_order(c: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    pre = c["checklist"]["pre_baseline"]
    suspect = [i for i in c["checklist"]["post_sweep"] if i.get("job") == "suspect"]
    explain = [i for i in c["checklist"]["post_sweep"] if i.get("job") == "explain"]
    refactor = [i for i in c["checklist"]["post_sweep"] if i.get("job") == "refactor"]
    guard = c["checklist"]["guard_tail"]
    return [("MAP", pre), ("SUSPECT", suspect), ("EXPLAIN", explain),
            ("REFACTOR", refactor), ("GUARD", guard)]


def _large_plan_md(c: dict[str, Any]) -> str:
    lines = ["## Sequenced closeout plan (large scope)", "",
             "A single sweep is insufficient at this scope. Execute the phases in "
             "order, gating each before the next. Re-run with `--emit-plan` to also "
             "write a `/refactor-subsystem` spec stub + a Workflow script:", ""]
    for phase, items in _phase_order(c):
        skills = ", ".join(f"/{i['skill']}" for i in items) or "_(none)_"
        lines.append(f"- **{phase}** — {skills}")
    lines.append("")
    lines.append("Hand the spec stub to `/refactor-subsystem`; for the global picture "
                 "afterward, run `/triage-debt`.")
    return "\n".join(lines)


def spec_stub(c: dict[str, Any], slug: str) -> str:
    """A /refactor-subsystem-consumable spec stub for the large-band closeout plan."""
    lines = [
        "---",
        f"id: {slug}",
        "status: proposed",
        "kind: closeout",
        'motivating_decision: "0023"',
        "---",
        "",
        f"# Closeout: {slug}",
        "",
        f"Generated by `/which-cleanup` for a `{c['scope_band']}`-scope change "
        f"({len(c['resolved_paths'])} files across {len(c['subsystems'])} subsystem(s)).",
        "",
        "## Scope",
        "",
        f"Subsystems: {', '.join(c['subsystems']) or '(none)'}",
        "",
        "## Phased plan",
        "",
    ]
    for phase, items in _phase_order(c):
        lines.append(f"### {phase}")
        if items:
            for i in items:
                lines.append(f"- `{i['command']}` — {i['why']}")
        else:
            lines.append("- _(none implied)_")
        lines.append("")
    lines.append("## Exceptions")
    lines.append("")
    lines.append("Unknown code stays until explicit approval (refactor-subsystem default).")
    lines.append("")
    return "\n".join(lines)


def workflow_script(c: dict[str, Any], slug: str) -> str:
    """A Claude Code Workflow script that fans the post-sweep scanners out as agents."""
    scanners = [i for i in c["checklist"]["post_sweep"]]
    items_js = ",\n".join(
        f"    {{ skill: {i['skill']!r}, command: {i['command']!r} }}" for i in scanners
    )
    return f"""export const meta = {{
  name: {slug!r},
  description: 'Closeout sweep emitted by /which-cleanup (scope={c['scope_band']})',
  phases: [{{ title: 'Sweep' }}],
}}

// One read-only scout per post-sweep scanner, each scoped to the changed files.
const SCANNERS = [
{items_js}
]

phase('Sweep')
const results = await parallel(SCANNERS.map(s => () =>
  agent(`Run ${{s.command}} as a read-only review of the changed files only. `
    + `Report findings as JSON.`, {{ label: `sweep:${{s.skill}}` }})
))
return results.filter(Boolean)
"""
