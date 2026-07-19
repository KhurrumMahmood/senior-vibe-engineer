#!/usr/bin/env python3
"""Detect drift between a SKILL.md and the artifacts it documents.

This is the instruction-artifact-coherence (IAC) suspect lane for the skills
themselves: a skill's prose can promise scripts, flags, tools, and evidence
that its files no longer provide. ``skill_meta.py lint`` already validates the
frontmatter *contract* (required fields, enum values, name==dir); this
detector validates *references between the SKILL.md and reality*, which that
contract does not cover.

Two bands, mirroring every other suspect-lane gate in this repo:

* **Band A — deterministic reference integrity.** Unambiguous, low
  false-positive checks safe to *gate* a commit on (``--gate``): a documented
  script that exists nowhere, a documented ``--flag`` the script's argparse
  never defines, a ``bash`` code block with no ``Bash`` in ``allowed-tools``.
* **Band B — structural proxies for semantic claims.** Heuristic signals that
  a human should read, never block a commit: an orphan script the body never
  mentions, a declared ``produces:``/``evidence_required:`` artifact the body
  never wires in, a read-only ``not_for`` claim contradicted by ``Write``/
  ``Edit`` in ``allowed-tools``.

Output matches the shared suspect-lane JSONL shape (``pattern``, ``file``,
``lineno``, ``summary``, ``recommendation``) plus a ``band`` key so the gate
and the report can filter without re-deriving it.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

BAND_A = {"missing_script_ref", "missing_documented_flag", "bash_tool_undeclared"}

# A token only counts as a concrete script reference if it carries a .py
# suffix; templated tokens (placeholders, globs, shell expansion) are never
# real paths and must not be flagged.
TEMPLATE_CHARS = set("<>*${}|…")
# Grab the whole contiguous path run ending in scripts/<file>.py — the
# lookbehind anchors at the path start so a `<skill-name>/scripts/x.py` or
# `.claude/skills/<name>/scripts/x.py` ref is captured whole, not as a bare
# `scripts/x.py` substring.
SCRIPT_REF_RE = re.compile(r"(?<![\w./-])(?:[\w.-]+/)*scripts/[\w./-]+\.py")
LONG_FLAG_RE = re.compile(r"(?<![\w-])(--[a-z][\w-]+)")
READONLY_CLAIM_RE = re.compile(
    r"\b(?:never edits?|does not edit|read-only|read only|without editing|"
    r"never (?:write|writes|modif\w+))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    pattern: str
    band: str
    file: str
    lineno: int
    summary: str
    recommendation: str


def relpath(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def write_jsonl(records, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _strip_yaml_comment(value: str) -> str:
    """Drop a YAML comment marker that occurs outside a quoted scalar."""
    quote: str | None = None
    escaped = False
    cursor = 0
    while cursor < len(value):
        char = value[cursor]
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quote = None
        elif quote == "'":
            if char == "'" and cursor + 1 < len(value) and value[cursor + 1] == "'":
                cursor += 1
            elif char == "'":
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char == "#" and (cursor == 0 or value[cursor - 1].isspace()):
            return value[:cursor].rstrip()
        cursor += 1
    return value.rstrip()


def _frontmatter_and_body(text: str) -> tuple[dict[str, object] | None, str]:
    """Read only the frontmatter fields this detector owns.

    Full schema validation belongs to ``skill_meta.py``.  This lightweight
    reader is deliberately limited to the detector's evidence fields, which
    keeps a copied skill independent from the repository's YAML runtime while
    accepting the scalar, list, and block forms used by installed skills.
    """
    lines = text.replace("\r\n", "\n").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return {}, text
    body = "\n".join(lines[end + 1:])
    if yaml is not None:
        try:
            metadata = yaml.safe_load("\n".join(lines[1:end])) or {}
        except yaml.YAMLError:
            return None, body  # skill_meta.py owns malformed-frontmatter reporting
        return (metadata if isinstance(metadata, dict) else None), body
    metadata: dict[str, object] = {}
    active_key: str | None = None
    active_block = False
    for raw in lines[1:end]:
        if raw.startswith((" ", "\t")):
            stripped = raw.strip()
            if active_key and stripped.startswith("- "):
                current = metadata.setdefault(active_key, [])
                if isinstance(current, list):
                    item = _strip_yaml_comment(stripped[2:].strip()).strip('"\'')
                    current.append(item)
            elif active_key and active_block:
                current = str(metadata.get(active_key, ""))
                metadata[active_key] = (current + " " + stripped).strip()
            continue
        if ":" not in raw:
            active_key = None
            active_block = False
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        value = _strip_yaml_comment(value.strip())
        active_key = key
        active_block = value in {"|", ">", "|-", ">-"}
        if active_block:
            metadata[key] = ""
        elif value == "":
            metadata[key] = []
        elif value.startswith("[") and value.endswith("]"):
            metadata[key] = [item.strip().strip('"\'') for item in value[1:-1].split(",") if item.strip()]
        else:
            metadata[key] = value.strip('"\'')
    return metadata, body


def emit(
    pattern: str,
    skill_md: Path,
    lineno: int,
    summary: str,
    recommendation: str,
    project_root: Path,
) -> Finding:
    return Finding(
        pattern=pattern,
        band="A" if pattern in BAND_A else "B",
        file=relpath(skill_md, project_root),
        lineno=lineno,
        summary=summary.strip(),
        recommendation=recommendation.strip(),
    )


def iter_skill_dirs(skills_dir: Path) -> list[Path]:
    """Skill dirs (parent of ``<skills_dir>/<name>/SKILL.md``), single level so
    SKILL.md fixtures nested under a skill's ``fixtures/`` tree are skipped."""
    return sorted(p.parent for p in skills_dir.glob("*/SKILL.md"))


def line_of(lines: list[str], needle: str) -> int:
    for idx, line in enumerate(lines, 1):
        if needle in line:
            return idx
    return 1


def normalize_tools(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(t).strip() for t in value if str(t).strip()]
    if isinstance(value, str):
        return [t.strip() for t in value.split(",") if t.strip()]
    return []


def script_option_strings(path: Path) -> set[str] | None:
    """Every ``--long-option`` defined by any ``add_argument`` call in the
    script — the union across subcommands, so a flag defined on *any*
    subparser counts as existing. Returns None if the file cannot be parsed
    (then flag-checking is skipped, never guessed)."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return None
    # argparse defines --help implicitly on every parser; documenting
    # `script.py --help` is always satisfiable.
    opts: set[str] = {"--help"}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "add_argument":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("--"):
                opts.add(arg.value)
    return opts


def resolve_script(token: str, skill_dir: Path, project_root: Path) -> Path | None:
    """A documented script ref is satisfied if it resolves skill-local
    (``<skill>/scripts/x.py``), repo-level (``<repo>/scripts/x.py``), or as a
    relative cross-skill ref (``<other-skill>/scripts/x.py`` →
    ``.claude/skills/<other-skill>/scripts/x.py``). Full ``.claude/skills/.../x.py``
    refs resolve under the repo root directly."""
    token = token.strip()
    if any(c in token for c in TEMPLATE_CHARS):
        return None
    candidates: list[Path] = []
    if token.startswith(".claude/") or token.startswith("/"):
        candidates.append(project_root / token.lstrip("/"))
    else:
        candidates.append(skill_dir / token)
        candidates.append(project_root / token)
        candidates.append(skill_dir.parent / token)  # sibling skill in the same tree
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def scan_skill(skill_dir: Path, project_root: Path) -> list[Finding]:
    skill_md = skill_dir / "SKILL.md"
    try:
        full_text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    fm, body = _frontmatter_and_body(full_text)
    if fm is None:
        return []  # skill_meta.py lint owns malformed-frontmatter reporting
    lines = body.splitlines()
    # Findings report file-relative line numbers, but we scan only the body
    # (frontmatter is contract, not procedure). Offset body lines past the
    # frontmatter so `file:line` stays clickable.
    body_start = full_text.find(body) if body else -1
    line_offset = full_text.count("\n", 0, body_start) if body_start > 0 else 0
    findings: list[Finding] = []

    # --- Band A: script references resolve somewhere ----------------------
    seen_refs: set[str] = set()
    for match in SCRIPT_REF_RE.finditer(body):
        token = match.group(0)
        if token in seen_refs or any(c in token for c in TEMPLATE_CHARS):
            continue
        seen_refs.add(token)
        if resolve_script(token, skill_dir, project_root) is None:
            findings.append(emit(
                "missing_script_ref", skill_md, line_of(lines, token) + line_offset,
                f"Body references `{token}`, which exists in neither the skill's "
                f"scripts/ nor the repo scripts/.",
                "Fix the path, restore the script, or remove the stale reference.", project_root,
            ))

    # --- Band A: documented flags exist in the script's argparse ----------
    # Only inside fenced code blocks (where commands live), and only when a
    # single resolvable *script ref* is on the line — a `scripts/<file>.py`
    # token, the same strict shape the missing_script_ref band uses. Matching
    # any `.py` token here mis-reads a flag *value* (e.g. a `--config
    # path/to/conf.py`) or a delegating launcher (no introspectable argparse)
    # as the documented script and emits a false positive.
    in_fence = False
    for idx, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        flags = LONG_FLAG_RE.findall(line)
        if not flags:
            continue
        scripts = [t for t in SCRIPT_REF_RE.findall(line) if resolve_script(t, skill_dir, project_root)]
        if len(scripts) != 1:
            continue
        resolved = resolve_script(scripts[0], skill_dir, project_root)
        opts = script_option_strings(resolved) if resolved else None
        if opts is None:
            continue
        for flag in dict.fromkeys(flags):
            if flag not in opts:
                findings.append(emit(
                    "missing_documented_flag", skill_md, idx + line_offset,
                    f"Body documents `{scripts[0]} {flag}`, but that script's "
                    f"argparse never defines `{flag}`.",
                    "Add the flag to the script, or correct the documented command.", project_root,
                ))

    # --- Band A: a bash code block implies Bash must be allowed -----------
    tools = normalize_tools(fm.get("allowed-tools"))
    if re.search(r"^```\s*(?:bash|sh|shell)\b", body, re.MULTILINE) and "Bash" not in tools:
        findings.append(emit(
            "bash_tool_undeclared", skill_md, 1,
            "Body has a bash/sh code block but `allowed-tools` does not include `Bash`.",
            "Add `Bash` to allowed-tools, or drop the shell block if the skill does not run commands.", project_root,
        ))

    # --- Band B: orphan scripts the body never mentions -------------------
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        for script in sorted(scripts_dir.glob("*.py")):
            if script.name in {"smoke.py", "__init__.py"}:
                continue
            if script.name not in body:
                findings.append(emit(
                    "orphan_script", skill_md, 1,
                    f"`scripts/{script.name}` exists but the SKILL.md never mentions it.",
                    "Document the script in the pipeline, fold it into a referenced script, or delete it.", project_root,
                ))

    # --- Band B: declared evidence artifacts are wired into the body ------
    # Match on a normalized form so `state_snapshot` is satisfied by "state
    # snapshot" / "state-snapshot" in prose — underscore/hyphen/case differences
    # are formatting, not drift.
    body_norm = re.sub(r"[_-]", " ", body.lower())
    for field in ("produces", "evidence_required"):
        value = fm.get(field)
        if not isinstance(value, list):
            continue
        for item in value:
            name = str(item).strip()
            name_norm = re.sub(r"[_-]", " ", name.lower())
            if name_norm and name_norm not in body_norm:
                findings.append(emit(
                    "evidence_contract_unbacked", skill_md, 1,
                    f"Frontmatter `{field}` declares `{name}`, but the body never "
                    f"names it as an output the procedure produces.",
                    "Wire the declared artifact into the pipeline, or drop it from the contract.", project_root,
                ))

    # --- Band B: read-only not_for claim vs editing tools -----------------
    not_for = str(fm.get("not_for") or "")
    if READONLY_CLAIM_RE.search(not_for):
        editing = [t for t in tools if t in {"Write", "Edit", "NotebookEdit"}]
        if editing:
            findings.append(emit(
                "not_for_tooltell_conflict", skill_md, 1,
                f"`not_for` claims the skill does not edit, but allowed-tools grants "
                f"{', '.join(editing)}.",
                "Reconcile the claim with the tool grant: tighten not_for or drop the editing tool.", project_root,
            ))

    return findings


def scan_skills(skill_dirs: list[Path], project_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for skill_dir in skill_dirs:
        findings.extend(scan_skill(skill_dir, project_root))
    return sorted(findings, key=lambda f: (f.file, f.band, f.pattern, f.lineno, f.summary))


def collect_skill_dirs(names: list[str], skills_dir: Path) -> list[Path]:
    """Resolve each arg to a skill dir. Accepts three shapes so the same gate
    serves both manual calls and pre-commit ``pass_filenames``: a ``SKILL.md``
    file path (→ its parent), a skill directory, or a bare skill name (→
    ``<skills_dir>/<name>``). Args without a SKILL.md are silently skipped."""
    if not names:
        return iter_skill_dirs(skills_dir)
    dirs: list[Path] = []
    for name in names:
        path = Path(name)
        if path.name == "SKILL.md" and path.is_file():
            dirs.append(path.parent)
        elif (path / "SKILL.md").is_file():
            dirs.append(path)
        elif (skills_dir / name / "SKILL.md").is_file():
            dirs.append(skills_dir / name)
    return sorted({d.resolve() for d in dirs})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect SKILL.md ↔ artifact drift.")
    parser.add_argument("skills", nargs="*", help="Skill names/dirs to scan (default: all).")
    parser.add_argument("--skills-dir", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, help="JSONL output path (advisory mode).")
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Band A only: print deterministic findings and exit 1 if any exist.",
    )
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    skills_dir = (args.skills_dir or project_root / ".claude" / "skills").resolve()
    skill_dirs = collect_skill_dirs(args.skills, skills_dir)
    findings = scan_skills(skill_dirs, project_root)

    if args.gate:
        band_a = [f for f in findings if f.band == "A"]
        for f in band_a:
            print(f"{f.file}:{f.lineno}  {f.pattern}  {f.summary}", file=sys.stderr)
        if band_a:
            print(
                f"\nfind-skill-artifact-drift: {len(band_a)} Band-A reference "
                f"drift(s) across {len(skill_dirs)} skill(s).",
                file=sys.stderr,
            )
            return 1
        return 0

    if not args.output:
        parser.error("--output is required unless --gate is set")
    write_jsonl((asdict(f) for f in findings), args.output)
    band_a = sum(1 for f in findings if f.band == "A")
    print(
        f"scanned {len(skill_dirs)} skills; wrote {len(findings)} findings "
        f"({band_a} Band A, {len(findings) - band_a} Band B) to {relpath(args.output, project_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
