#!/usr/bin/env python3
"""find-incomplete-sweep — scout-packet builder (judgment-prep stage).

The detector (`scan.py`) is deterministic: it gates divergences down to a
trustworthy residue of forgotten-sweep *candidates*. The last call — "is this
a forgotten site, or a deliberate exception?" — is irreducibly judgment
(adversarial review). This script is the seam between the two: it does NOT
judge. It assembles, for each gated-in finding, the exact evidence a judge
needs so the judge never has to re-derive it.

A **scout packet** carries:
  - the divergence metadata from the manifest (callee, kwarg, majority_frac,
    group_size, trajectory note),
  - the straggler's code window (the straggler line ± CONTEXT lines, read
    from disk so it is current),
  - 1-2 present-site code windows (sibling call sites that DO pass the kwarg),
    so the judge can compare shapes side by side.

Present-site locations are re-derived by importing `scan.py`'s own
`collect_callsites` as a library — detection logic stays in one place; this
script never reimplements it. Stdlib only. Robust to missing files/lines.

Usage:
    .venv/bin/python .claude/skills/find-incomplete-sweep/scripts/scout.py \
        --scan-dir reports/find-incomplete-sweep/scan-<TS> \
        --paths scripts [--context 8] [--max-present 2]

Output: `<scan-dir>/scout_packets.json` — one packet per gated-in finding.
The orchestrator (SKILL.md "Scout stage") fans out one judgment per packet.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import subprocess
import sys
from collections import defaultdict

SKILL_SCRIPTS = pathlib.Path(__file__).resolve().parent


def resolve_project_root(explicit: pathlib.Path | None) -> pathlib.Path:
    """Resolve a target root without depending on uninstalled sibling skills."""
    if explicit is not None:
        return explicit.resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return pathlib.Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return pathlib.Path.cwd().resolve()


def load_scan_module():
    """Import scan.py as a library so we reuse its callsite collection.

    Registering in sys.modules first is required: scan.py uses @dataclass with
    a forward-referenced annotation, which dataclasses resolves via
    sys.modules[cls.__module__].
    """
    scan_path = SKILL_SCRIPTS / "scan.py"
    spec = importlib.util.spec_from_file_location("sweep_scan", scan_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load scan.py from {scan_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sweep_scan"] = mod
    spec.loader.exec_module(mod)
    return mod


def read_window(file: str, line: int, context: int, project_root: pathlib.Path) -> dict:
    """Return a code window centered on `line` (1-based), ± context lines.

    Robust: a missing file or an out-of-range line yields an annotated stub
    rather than raising, so one bad ref never sinks the whole packet set.
    """
    path = pathlib.Path(file)
    if not path.is_absolute():
        path = project_root / path  # manifest paths are project-root-relative
    if not path.exists():
        return {"file": file, "line": line, "available": False,
                "note": "file not found on disk", "text": ""}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError) as exc:
        return {"file": file, "line": line, "available": False,
                "note": f"unreadable: {exc}", "text": ""}
    if line < 1 or line > len(lines):
        return {"file": file, "line": line, "available": False,
                "note": f"line {line} out of range (file has {len(lines)})",
                "text": ""}
    lo = max(1, line - context)
    hi = min(len(lines), line + context)
    rendered = []
    for n in range(lo, hi + 1):
        marker = ">>" if n == line else "  "
        rendered.append(f"{marker} {n:>5}│ {lines[n - 1]}")
    return {"file": file, "line": line, "available": True,
            "start": lo, "end": hi, "text": "\n".join(rendered)}


def parse_straggler(ref: str) -> tuple[str, int] | None:
    """'scripts/foo.py:47' -> ('scripts/foo.py', 47). None on malformed input."""
    if ":" not in ref:
        return None
    file, _, ln = ref.rpartition(":")
    try:
        return file, int(ln)
    except ValueError:
        return None


def ensure_compiler_manifest_output_containment(scan_dir: pathlib.Path, manifest: dict,
                                                project_root: pathlib.Path) -> None:
    """Preserve every compiler-manifest run's report-root and no-symlink promise."""
    language = manifest.get("language")
    if language not in {"typescript", "javascript"}:
        return
    language_label = "TypeScript" if language == "typescript" else "checked JavaScript"
    allowed_root = project_root / "reports" / "find-incomplete-sweep"
    if ".." in scan_dir.parts:
        raise ValueError(f"{language_label} scout packet path must not contain parent traversal")
    try:
        scan_dir.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            f"{language_label} scout packets must stay beneath reports/find-incomplete-sweep/"
        ) from exc
    current = project_root
    try:
        parts = scan_dir.relative_to(project_root).parts
    except ValueError as exc:
        raise ValueError(f"{language_label} scout packets must stay inside the project root") from exc
    try:
        scan_dir.resolve().relative_to(allowed_root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"{language_label} scout packets must stay beneath reports/find-incomplete-sweep/"
        ) from exc
    for part in parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{language_label} scout packets must not traverse a symbolic link")
    output = scan_dir / "scout_packets.json"
    if output.is_symlink():
        raise ValueError(f"{language_label} scout packet output must not be a symbolic link")


def build_present_index(scan_mod, paths: list[str], project_root: pathlib.Path):
    """Map (callee_key, kwarg) -> [(file, line), ...] for sites passing kwarg.

    Reuses scan.py's collector so the present-site definition is identical to
    the one the detector used. Returns the index plus the raw site list (so a
    caller can fall back to "any site for this callee" if a kwarg key drifts).
    """
    sites, _scanned, _skipped = scan_mod.collect_callsites(paths, project_root)
    by_kwarg: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    by_callee: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for s in sites:
        by_callee[s.key].append((s.file, s.line))
        for kw in s.kwargs:
            by_kwarg[(s.key, kw)].append((s.file, s.line))
    return by_kwarg, by_callee


def pick_present_sites(by_kwarg, callee: str, kwarg: str,
                       straggler: tuple[str, int], limit: int):
    """Choose up to `limit` present sites to show the judge.

    Prefer sites in a different file from the straggler (more informative
    contrast); fall back to same-file siblings if that is all there is. Never
    return the straggler line itself.
    """
    present = [pl for pl in by_kwarg.get((callee, kwarg), [])
               if pl != straggler]
    straggler_file = straggler[0]
    other_file = [pl for pl in present if pl[0] != straggler_file]
    same_file = [pl for pl in present if pl[0] == straggler_file]
    ordered = other_file + same_file
    return ordered[:limit], len(present)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-dir", required=True,
                    help="a find-incomplete-sweep scan dir containing manifest.json")
    ap.add_argument("--context", type=int, default=8,
                    help="lines of context above/below each call line")
    ap.add_argument("--max-present", type=int, default=2,
                    help="present-site windows to include per finding")
    ap.add_argument("--paths", nargs="+", default=None,
                    help="paths to re-scan for present-site locations "
                         "(required for Python manifests; compiler manifests "
                         "carry compiler-resolved present-site locations)")
    ap.add_argument("--project-root", type=pathlib.Path, default=None,
                    help="Target project root the manifest paths are relative to "
                         "(default: the scan manifest's recorded project_root, "
                         "else git toplevel of cwd, else cwd)")
    args = ap.parse_args()

    scan_dir = pathlib.Path(args.scan_dir)
    raw_scan_dir = scan_dir if scan_dir.is_absolute() else pathlib.Path.cwd() / scan_dir
    manifest_path = scan_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: no manifest.json under {scan_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read manifest.json under {scan_dir}: {exc}", file=sys.stderr)
        sys.exit(1)

    # Anchor precedence: explicit flag > root the scan recorded > cwd toplevel.
    if args.project_root is not None:
        project_root = args.project_root.resolve()
    elif manifest.get("project_root"):
        project_root = pathlib.Path(manifest["project_root"]).resolve()
    else:
        project_root = resolve_project_root(None)
    try:
        ensure_compiler_manifest_output_containment(raw_scan_dir, manifest, project_root)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

    gated = [f for f in manifest.get("findings", []) if f.get("gated_in")]
    if not gated:
        print("no gated-in findings — nothing to scout", file=sys.stderr)
        (scan_dir / "scout_packets.json").write_text(json.dumps(
            {"band": manifest.get("band"), "language": manifest.get("language", "python"),
             "project_root": str(project_root), "scan_dir": str(scan_dir),
             "packet_count": 0, "packets": []}, indent=2))
        return

    is_compiler_manifest = manifest.get("language") in {"typescript", "javascript"}
    if not is_compiler_manifest and not args.paths:
        ap.error("--paths is required for a Python manifest")
    if not is_compiler_manifest:
        scan_mod = load_scan_module()
        by_kwarg, _by_callee = build_present_index(scan_mod, args.paths, project_root)

    packets = []
    for idx, f in enumerate(gated, start=1):
        callee = f["callee"]
        kwarg = f["kwarg"]
        ref = parse_straggler(f["straggler"])
        if ref is None:
            continue
        straggler_file, straggler_line = ref

        if is_compiler_manifest:
            declared_present = f.get("present_sites", [])
            present_locs = []
            for item in declared_present:
                if not isinstance(item, dict):
                    continue
                file = item.get("file")
                line = item.get("line")
                if isinstance(file, str) and isinstance(line, int) and (file, line) != ref:
                    present_locs.append((file, line))
            present_total = len(present_locs)
            present_locs = present_locs[:args.max_present]
        else:
            present_locs, present_total = pick_present_sites(
                by_kwarg, callee, kwarg, ref, args.max_present)

        packet = {
            "id": f"SW-{idx:02d}",
            "callee": callee,
            "kwarg": kwarg,
            "majority_frac": f.get("majority_frac"),
            "group_size": f.get("group_size"),
            "present_count": present_total,
            "trajectory": f.get("trajectory", ""),
            "straggler": {
                "ref": f["straggler"],
                **read_window(straggler_file, straggler_line, args.context, project_root),
            },
            "present_sites": [
                read_window(pf, pl, args.context, project_root) for pf, pl in present_locs
            ],
        }
        if not packet["present_sites"]:
            packet["present_note"] = (
                "no present-site location re-derivable (kwarg key may have "
                "drifted since the scan); judge from the straggler + metadata"
            )
        packets.append(packet)

    out = {
        "band": manifest.get("band"),
        "language": manifest.get("language", "python"),
        "project_root": str(project_root),
        "scan_dir": str(scan_dir),
        "context_lines": args.context,
        "packet_count": len(packets),
        "packets": packets,
    }
    out_path = scan_dir / "scout_packets.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"wrote {out_path}  ({len(packets)} packets)")


if __name__ == "__main__":
    main()
