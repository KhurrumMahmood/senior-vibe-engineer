#!/usr/bin/env python3
"""Render the /explain-code document and mandatory sidecars from scout notes.

This family-local renderer deliberately does not infer code behavior. Scouts
write the behavioral annotation; the renderer verifies each selected target has
the required sections, then makes one durable explanation document plus the
unexplained/surprises sidecars used by the skill's effectiveness log.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = (
    "Location",
    "Intent",
    "Preconditions",
    "Postconditions",
    "Invariants",
    "Callers",
    "Unexplained regions",
    "Surprising behavior",
)
SECTION_RE = re.compile(r"^## (?P<name>.+?)\s*$")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read targets JSON {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("targets"), list):
        raise ValueError(f"targets JSON {path} must contain a targets list")
    return value


def _read_annotation(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read annotation {path}: {exc}") from exc
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        match = SECTION_RE.match(line)
        if match:
            current = match.group("name")
            if current.startswith("Callers"):
                current = "Callers"
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    location = "\n".join(sections.get("Location", [])).strip()
    status_match = re.search(r"^\s*-\s*Status:\s*`?(?P<status>[A-Za-z_]+)`?", location, re.MULTILINE)
    status = status_match.group("status") if status_match else "found"
    if status in {"not_found", "annotation_incomplete"}:
        return {"__status__": status}
    missing = [name for name in REQUIRED_SECTIONS if name not in sections]
    if missing:
        raise ValueError(f"annotation {path} is missing required sections: {', '.join(missing)}")
    rendered = {name: "\n".join(lines).strip() for name, lines in sections.items()}
    rendered["__status__"] = status
    return rendered


def _annotation_items(section: str, empty_markers: tuple[str, ...]) -> list[str]:
    stripped = section.strip()
    if not stripped or any(stripped.startswith(marker) for marker in empty_markers):
        return []
    return [line[2:].strip() for line in stripped.splitlines() if line.startswith("- ")]


def _target_slug(target: str) -> str:
    normalized = target.strip().rstrip("/").removeprefix("./")
    if normalized.startswith("core/"):
        normalized = normalized.removeprefix("core/")
    for suffix in (".tsx", ".ts", ".py"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return re.sub(r"[^A-Za-z0-9]+", "-", normalized).strip("-") or "target"


def _source_loc(files: list[Any], project_root: Path) -> int:
    total = 0
    for value in files:
        path = project_root / str(value)
        try:
            total += len(path.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError):
            continue
    return total


def _render_contract(target: dict[str, Any], annotation: dict[str, str]) -> str:
    if annotation.get("__status__") in {"not_found", "annotation_incomplete"}:
        return (
            f"### {target['symbol']}\n\n"
            "**Status:** annotation_incomplete — the scout could not locate or complete "
            "this symbol. Re-run `/explain-code` for the target to retry."
        )
    chunks = [
        f"### {target['symbol']}",
        "",
        f"**Kind:** {target['kind']}.",
        "",
        f"**Intent.** {annotation['Intent']}",
        "",
        "**Preconditions.**",
        annotation["Preconditions"],
        "",
        "**Postconditions.**",
        annotation["Postconditions"],
        "",
        "**Invariants.**",
        annotation["Invariants"],
        "",
        "**Callers.**",
        annotation["Callers"],
    ]
    surprises = _annotation_items(annotation["Surprising behavior"], ("No surprises",))
    if surprises:
        chunks.extend(("", "**Surprises.**", annotation["Surprising behavior"]))
    return "\n".join(chunks)


def render(
    *,
    targets: dict[str, Any],
    annotations_dir: Path,
    output: Path,
    summary: str,
    regenerated: str,
    project_root: Path,
) -> tuple[int, int]:
    selected = targets["targets"]
    annotations: dict[str, dict[str, str]] = {}
    for target in selected:
        if not isinstance(target, dict) or not isinstance(target.get("symbol_key"), str):
            raise ValueError("targets JSON contains an invalid target record")
        annotations[target["symbol_key"]] = _read_annotation(
            annotations_dir / f"{target['symbol_key']}.md"
        )

    target_name = str(targets.get("target", "target"))
    slug = _target_slug(target_name)
    overflow = targets.get("overflow", [])
    unexplained_lines: list[str] = []
    surprise_lines: list[str] = []
    for target in selected:
        symbol = str(target["symbol"])
        annotation = annotations[target["symbol_key"]]
        if annotation.get("__status__") in {"not_found", "annotation_incomplete"}:
            continue
        unexplained_lines.extend(
            f"- {symbol} — {item}"
            for item in _annotation_items(
                annotation["Unexplained regions"],
                ("No unexplained regions",),
            )
        )
        surprise_lines.extend(
            f"- {symbol} — {item}"
            for item in _annotation_items(
                annotation["Surprising behavior"],
                ("No surprises",),
            )
        )
    for item in targets.get("unexplained", []):
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "unresolved export"))
        reason = str(item.get("reason", "not explained"))
        file_name = str(item.get("file", "target"))
        unexplained_lines.append(f"- `{file_name}` — `{symbol}`: {reason}")

    status_row = (
        f"\n| Status | {targets['status']} |"
        if targets.get("status") in {"complete", "partial"}
        else ""
    )
    metadata = (
        f"# Explanation — {target_name}\n\n"
        "| Field | Value |\n"
        "|---|---|\n"
        f"| Target | `{target_name}` |\n"
        f"| Slug | `{slug}` |\n"
        f"| LOC | {_source_loc(targets.get('files', []), project_root)} |\n"
        f"| Public symbols (total) | {targets.get('public_symbol_count', len(selected))} |\n"
        f"| Annotated this run | {len(selected)} |\n"
        f"| Overflow | {len(overflow)} (see targets.json) |\n"
        f"| Regenerated | {regenerated} |"
        f"{status_row}"
    )
    chunks = [metadata, f"## Summary\n\n{summary.strip()}"]
    if selected:
        chunks.append(
            "## Public contracts\n\n"
            + "\n\n".join(_render_contract(target, annotations[target["symbol_key"]]) for target in selected)
        )
    if unexplained_lines:
        chunks.append("## Unexplained regions\n\n" + "\n".join(unexplained_lines))
    if surprise_lines:
        chunks.append("## Follow-on findings\n\n" + "\n".join(surprise_lines))
    chunks.append(f"## How to regenerate\n\n```bash\n/explain-code {target_name}\n```")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n\n".join(chunks) + "\n", encoding="utf-8")
        (annotations_dir.parent / "unexplained.txt").write_text(
            "\n".join(unexplained_lines) + ("\n" if unexplained_lines else ""),
            encoding="utf-8",
        )
        (annotations_dir.parent / "surprises.txt").write_text(
            "\n".join(surprise_lines) + ("\n" if surprise_lines else ""),
            encoding="utf-8",
        )
    except OSError as exc:
        raise ValueError(f"cannot write explanation artifacts: {exc}") from exc
    return len(unexplained_lines), len(surprise_lines)


def _publish_latest(output: Path, annotations_dir: Path) -> None:
    """Publish latest only after the complete documented artifact set exists."""
    report_dir = annotations_dir.parent
    explanations_root = output.parent
    if (
        report_dir.parent != explanations_root
        or output.name != f"{report_dir.name}.md"
        or annotations_dir.name != "annotations"
    ):
        return
    latest = explanations_root / "latest"
    if latest.exists() and not latest.is_symlink():
        raise ValueError(f"latest explanation path is not replaceable: {latest}")
    temporary = explanations_root / f".{report_dir.name}.latest"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    try:
        temporary.symlink_to(report_dir.name)
        os.replace(temporary, latest)
    except OSError as exc:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
        raise ValueError(f"cannot publish latest explanation: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--annotations-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--regenerated", default=None, help="UTC ISO timestamp; defaults to now")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    regenerated = args.regenerated or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        targets = _read_json(args.targets)
        unexplained, surprises = render(
            targets=targets,
            annotations_dir=args.annotations_dir,
            output=args.output,
            summary=args.summary,
            regenerated=regenerated,
            project_root=args.project_root.resolve(),
        )
        _publish_latest(args.output, args.annotations_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output}: {unexplained} unexplained / {surprises} surprises")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
