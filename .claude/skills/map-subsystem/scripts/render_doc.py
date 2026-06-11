#!/usr/bin/env python3
"""Render a subsystem inventory doc from the Stage 1–5 scratch files.

Reads the scratch artifacts produced by the /map-subsystem pipeline
and emits ``.claude/docs/subsystems/<name>.md`` in the format specified
by ``knowledge/output-format.md``. Also appends one line to
``reports/_meta/effectiveness.jsonl``.

The orchestrator is responsible for collecting inventory via find/grep
and running ruff + silent_catch.py; this script is pure rendering. It
does not invoke any subprocess (except ``git`` for the "prior_run"
diff, if ``--prior-doc`` is passed).

Input files (all produced in the scratch dir):

    files.jsonl         — {path, loc, symbols, public, last_commit,
                           last_author, last_date}
    symbols.jsonl       — {file, name, kind, is_public, decorators,
                           lineno, loc, docstring_first_line}
    clusters.jsonl      — {cluster, symbols, loc_sum, domain_hint}
    deps.json           — {internal_imports: [...], external_imports:
                           [...], inbound: [...], inbound_truncated: bool}
    compliance.json     — {rules: [{rule, source, count}], total}
    open_questions.json — [{symbol, file, reason}]

Output:

    .claude/docs/subsystems/<name>.md      — the rendered doc
    reports/_meta/effectiveness.jsonl      — one appended line

Stdlib-only; safe to invoke under bare ``python3``.

Usage:

    render_doc.py --name views-crawling \\
        --target core/views/crawling.py \\
        --scratch reports/map/views-crawling/ \\
        --output .claude/docs/subsystems/views-crawling.md \\
        [--prior-doc .claude/docs/subsystems/views-crawling.md.prev] \\
        [--header "Single-file view module covering ..."] \\
        [--effectiveness-log reports/_meta/effectiveness.jsonl]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return default


def _iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _front_matter(
    name: str,
    target: str,
    ts: str,
    prior_ts: str | None,
    counts: dict,
) -> str:
    lines = [
        "---",
        f"subsystem: {name}",
        f"target: {target}",
        f"regenerated: {ts}",
    ]
    if prior_ts:
        lines.append(f"prior_run: {prior_ts}")
    lines.append(f"files: {counts['files']}")
    lines.append(f"public_symbols: {counts['public_symbols']}")
    lines.append(f"clusters: {counts['clusters']}")
    lines.append(f"compliance_violations: {counts['compliance_violations']}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _files_table(files: list[dict]) -> str:
    if not files:
        return ""
    out = [
        "## Files",
        "",
        "| Path | LOC | Symbols | Public | Last commit | Last author |",
        "|---|--:|--:|--:|---|---|",
    ]
    for f in files:
        sym = f.get("symbols", "—")
        pub = f.get("public", "—")
        commit_cell = f"`{f['last_commit']}` {f['last_date']}" if f.get("last_commit") else "—"
        out.append(
            f"| {f['path']} | {f.get('loc', '—')} | {sym} | {pub} |"
            f" {commit_cell} | {f.get('last_author', '—')} |"
        )
    out.append("")
    return "\n".join(out)


def _public_surface(symbols: list[dict], files: list[dict]) -> str:
    public = [s for s in symbols if s.get("is_public")]
    if not public:
        return ""
    by_file: dict[str, list[dict]] = {}
    for s in public:
        by_file.setdefault(s["file"], []).append(s)
    out = ["## Public surface", ""]
    file_order = [f["path"] for f in files]
    for path in file_order:
        if path not in by_file:
            continue
        out.append(f"### {path}")
        out.append("")
        for kind in ("class", "function", "var"):
            members = [s for s in by_file[path] if s.get("kind") == kind]
            if not members:
                continue
            label = {"class": "Classes", "function": "Functions", "var": "Module vars"}[kind]
            out.append(f"**{label} ({len(members)}):**")
            for m in members:
                doc = m.get("docstring_first_line") or "(no docstring)"
                sig = m.get("signature") or m["name"]
                out.append(f"- `{sig}` — {doc}")
            out.append("")
    return "\n".join(out)


def _clusters_section(clusters: list[dict]) -> str:
    if not clusters:
        return ""
    out = [
        "## Responsibility clusters",
        "",
        "| Cluster | Symbols | LOC | Domain hint |",
        "|---|--:|--:|---|",
    ]
    for c in clusters:
        out.append(
            f"| {c['cluster']} | {c.get('symbols', '—')} |"
            f" {c.get('loc_sum', '—')} | {c.get('domain_hint', '')} |"
        )
    out.append("")
    # SRP sentence = cluster names joined by " and "
    names = [c["cluster"] for c in clusters]
    if len(names) == 1:
        sentence = f'"This file handles {names[0]}."'
        ands = 0
    else:
        sentence = '"This file handles ' + " **and** ".join(names) + '."'
        ands = len(names) - 1
    out.append(f"**SRP sentence:** {sentence} → {ands} `and`s.")
    if ands >= 3:
        out.append("")
        out.append(
            "→ omnibus candidate (see `.claude/docs/architectural-smells.md` "
            "smell 1). Run `/find-omnibus` for triage, or decompose directly "
            "via `/refactor-subsystem` driven by a spec in `ai-docs/specs/`."
        )
    out.append("")
    return "\n".join(out)


def _deps_section(deps: dict) -> str:
    internal = deps.get("internal_imports", [])
    external = deps.get("external_imports", [])
    inbound = deps.get("inbound", [])
    truncated = deps.get("inbound_truncated", False)

    out = ["## Dependency graph", ""]
    out.append(f"**Internal imports ({len(internal)}):**")
    if internal:
        for line in internal:
            out.append(f"- {line}")
    out.append("")
    out.append(f"**External imports ({len(external)}):**")
    if external:
        for line in external:
            out.append(f"- {line}")
    out.append("")

    trunc_note = " (truncated at 200)" if truncated else ""
    out.append(f"**Inbound ({len(inbound)} files{trunc_note}):**")
    if inbound:
        for line in inbound[:25]:
            out.append(f"- {line}")
        if len(inbound) > 25:
            out.append(f"- … ({len(inbound) - 25} more)")
    out.append("")
    return "\n".join(out)


def _compliance_section(compliance: dict) -> str:
    rules = compliance.get("rules", [])
    if not rules:
        return ""
    out = [
        "## Convention compliance",
        "",
        "| Rule | Source | Count | Action |",
        "|---|---|--:|---|",
    ]
    total = 0
    for r in rules:
        count = r.get("count", 0)
        total += count
        action = r.get("action") or ("—" if count == 0 else "review")
        out.append(
            f"| {r['rule']} | {r['source']} | {count} | {action} |"
        )
    out.append("")
    out.append(f"**Total violations:** {total} across {sum(1 for r in rules if r.get('count'))} rules.")
    out.append("")
    return "\n".join(out)


def _open_questions(questions: list[dict]) -> str:
    if not questions:
        return ""
    out = ["## Open questions", ""]
    for q in questions:
        out.append(f"- `{q['symbol']}` ({q['file']}) — {q['reason']}")
    out.append("")
    return "\n".join(out)


def _regenerate_section(name: str) -> str:
    return "\n".join([
        "## How to regenerate",
        "",
        "```bash",
        f"/map-subsystem {name} --refresh",
        "```",
        "",
    ])


def _extract_prior_ts(prior_doc: Path) -> str | None:
    if not prior_doc.exists():
        return None
    txt = prior_doc.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^regenerated:\s*(\S+)", txt, flags=re.MULTILINE)
    return m.group(1) if m else None


def _diff_section(prior_doc: Path | None, counts: dict, prior_ts: str | None) -> str:
    # A trivial diff: cluster / compliance delta only. Symbol-level diff
    # requires parsing the prior doc's public surface and is out of scope
    # for the first iteration — the orchestrator can pass a richer diff
    # via a future `--diff-json` flag.
    if not prior_doc or not prior_doc.exists() or not prior_ts:
        return ""
    txt = prior_doc.read_text(encoding="utf-8", errors="replace")
    prior_clusters = _extract_front_matter_int(txt, "clusters")
    prior_public = _extract_front_matter_int(txt, "public_symbols")
    prior_violations = _extract_front_matter_int(txt, "compliance_violations")
    if prior_clusters is None:
        return ""
    out = [f"## Diff since {prior_ts}", ""]
    if prior_public != counts["public_symbols"]:
        out.append(
            f"- **Public symbols:** {prior_public} → {counts['public_symbols']}"
        )
    if prior_clusters != counts["clusters"]:
        out.append(
            f"- **Cluster count:** {prior_clusters} → {counts['clusters']}"
        )
    if prior_violations != counts["compliance_violations"]:
        out.append(
            f"- **Compliance violations:** {prior_violations} → "
            f"{counts['compliance_violations']}"
        )
    if len(out) == 2:
        out.append("- No aggregate deltas since last run.")
    out.append("")
    return "\n".join(out)


def _extract_front_matter_int(txt: str, key: str) -> int | None:
    m = re.search(rf"^{re.escape(key)}:\s*(-?\d+)", txt, flags=re.MULTILINE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _append_effectiveness(
    log_path: Path,
    name: str,
    ts: str,
    counts: dict,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    scan_id = f"map-{name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    entry = {
        "skill": "map-subsystem",
        "scan_id": scan_id,
        "ts": ts,
        "findings_total": counts["clusters"],
        "buckets": {
            "files": counts["files"],
            "public_symbols": counts["public_symbols"],
            "clusters": counts["clusters"],
            "compliance_violations": counts["compliance_violations"],
        },
        "target": name,
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def render(args: argparse.Namespace) -> int:
    scratch = Path(args.scratch)
    files = _read_jsonl(scratch / "files.jsonl")
    symbols = _read_jsonl(scratch / "symbols.jsonl")
    clusters = _read_jsonl(scratch / "clusters.jsonl")
    deps = _read_json(scratch / "deps.json", {"internal_imports": [], "external_imports": [], "inbound": []})
    compliance = _read_json(scratch / "compliance.json", {"rules": [], "total": 0})
    open_questions = _read_json(scratch / "open_questions.json", [])

    ts = _iso_utc()
    prior_doc = Path(args.prior_doc) if args.prior_doc else None
    prior_ts = _extract_prior_ts(prior_doc) if prior_doc else None

    counts = {
        "files": len(files),
        "public_symbols": sum(1 for s in symbols if s.get("is_public")),
        "clusters": len(clusters),
        "compliance_violations": sum(
            r.get("count", 0) for r in compliance.get("rules", [])
        ),
    }

    out_parts: list[str] = [
        _front_matter(args.name, args.target, ts, prior_ts, counts),
        f"# {args.name}\n",
    ]
    if args.header:
        out_parts.append(args.header.strip() + "\n")

    diff = _diff_section(prior_doc, counts, prior_ts)
    if diff:
        out_parts.append(diff)

    for section in (
        _files_table(files),
        _public_surface(symbols, files),
        _clusters_section(clusters),
        _deps_section(deps),
        _compliance_section(compliance),
        _open_questions(open_questions),
        _regenerate_section(args.name),
    ):
        if section:
            out_parts.append(section)

    doc = "\n".join(out_parts).rstrip() + "\n"

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")

    if args.effectiveness_log:
        _append_effectiveness(Path(args.effectiveness_log), args.name, ts, counts)

    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--name", required=True, help="Subsystem name (kebab-case)")
    p.add_argument("--target", required=True, help="Path to the subsystem")
    p.add_argument("--scratch", required=True, help="Scratch dir with Stage 1–5 outputs")
    p.add_argument("--output", required=True, help="Output markdown path")
    p.add_argument("--prior-doc", help="Prior version for --refresh diff")
    p.add_argument("--header", help="One-paragraph header text")
    p.add_argument(
        "--effectiveness-log",
        default="reports/_meta/effectiveness.jsonl",
        help="Effectiveness log path (empty string to skip)",
    )
    args = p.parse_args(argv)
    if args.effectiveness_log == "":
        args.effectiveness_log = None
    return render(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
