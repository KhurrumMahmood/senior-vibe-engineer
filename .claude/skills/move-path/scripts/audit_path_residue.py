#!/usr/bin/env python3
"""Audit operational path residue after a move-path plan.

This is intentionally small and assumption-forward. It does not parse every
language. It scans scoped text files for path-shaped old references that should
have moved: relative prefixes, root-relative prefixes, absolute POSIX paths, and
Windows-style spellings derived from the current project root.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import move_path  # noqa: E402


ASSUMPTIONS = [
    "The move plan is the source of truth for old->new path identity.",
    "The exact resolved move-plan file is an authority input and is excluded from residue findings.",
    "Bare top-level directory words are not residue unless they appear as path prefixes.",
    "Absolute POSIX and Windows-style paths are generated from the current project root.",
    "Matches are suggestions: historical/provenance references may be intentionally retained.",
    "Binary files and files outside reference_scope include/exclude patterns are skipped.",
]


def line_excerpt(text: str, start: int) -> tuple[int, str]:
    lineno = text.count("\n", 0, start) + 1
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end == -1:
        line_end = len(text)
    return lineno, text[line_start:line_end].strip()[:240]


def audit(
    *,
    plan_path: Path,
    project_root: Path | None,
    max_samples: int,
    extra_excludes: list[str] | None = None,
) -> dict:
    root = (project_root or move_path.git_root(Path.cwd()) or Path.cwd()).resolve()
    plan = move_path.load_plan(plan_path, root)
    moves: list[move_path.MoveSpec] = plan["_moves"]
    includes, excludes = move_path.plan_patterns(plan)
    excludes.extend(extra_excludes or [])
    files = move_path.exclude_authority_file(move_path.iter_scope_files(root, includes, excludes), plan_path, root)
    tokens = move_path.path_residue_tokens(root, moves)

    findings: list[dict] = []
    for rel in files:
        try:
            text = move_path._read_text(root / rel)
        except OSError:
            continue
        for old, new, token_kind in tokens:
            for match in move_path.re.finditer(move_path.residue_pattern(old), text):
                token = match.group(0)
                expected_new = move_path.residue_match_target(old, new, token)
                if move_path.is_current_relative_reference(root, rel, token, expected_new):
                    continue
                lineno, excerpt = line_excerpt(text, match.start())
                findings.append(
                    {
                        "file": rel,
                        "line": lineno,
                        "kind": token_kind,
                        "old": token,
                        "expected_new": expected_new,
                        "excerpt": excerpt,
                    }
                )

    spot_checks = []
    for move in moves:
        src = move.src.rstrip("/")
        dst = move.dst.rstrip("/")
        spot_checks.append(
            {
                "move": move.move_id,
                "old_relative": src,
                "new_relative": dst,
                "old_exists": (root / src).exists(),
                "new_exists": (root / dst).exists(),
                "old_absolute": (root / src).as_posix(),
                "new_absolute": (root / dst).as_posix(),
            }
        )

    return {
        "tool": "audit_path_residue",
        "project_root": root.as_posix(),
        "plan": plan_path.as_posix(),
        "assumptions": ASSUMPTIONS,
        "summary": {
            "moves": len(moves),
            "files_scanned": len(files),
            "tokens_scanned": len(tokens),
            "findings": len(findings),
        },
        "extra_excludes": extra_excludes or [],
        "findings": findings,
        "samples": findings[:max_samples],
        "spot_checks": spot_checks,
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# path residue audit",
        "",
        f"- project: `{payload['project_root']}`",
        f"- plan: `{payload['plan']}`",
        f"- files scanned: {payload['summary']['files_scanned']}",
        f"- findings: {payload['summary']['findings']}",
        "",
        "## Assumptions",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["assumptions"])
    lines.extend(["", "## Spot Checks", ""])
    for row in payload["spot_checks"]:
        lines.append(
            f"- `{row['old_relative']}` -> `{row['new_relative']}`; "
            f"old_exists={row['old_exists']}; new_exists={row['new_exists']}"
        )
    lines.extend(["", "## Samples", ""])
    if not payload["samples"]:
        lines.append("- None")
    for row in payload["samples"]:
        lines.append(
            f"- {row['file']}:{row['line']} `{row['old']}` -> "
            f"`{row['expected_new']}` ({row['kind']})"
        )
        lines.append(f"  - {row['excerpt']}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit old path residue after a move-path plan.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional fnmatch-style exclude pattern; repeatable.",
    )
    parser.add_argument("--max-samples", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-findings", action="store_true")
    args = parser.parse_args(argv)

    root = args.project_root or move_path.git_root(Path.cwd()) or Path.cwd()
    report_dir = args.report_dir or root / move_path.DEFAULT_REPORT_DIR
    payload = audit(
        plan_path=args.plan,
        project_root=root,
        max_samples=args.max_samples,
        extra_excludes=args.exclude,
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    move_path._write_text(report_dir / "path-residue-audit.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    move_path._write_text(report_dir / "path-residue-audit.md", render_markdown(payload))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(report_dir / "path-residue-audit.md")
    if args.fail_on_findings and payload["summary"]["findings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
