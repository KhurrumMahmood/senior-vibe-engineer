#!/usr/bin/env python3
"""find-incomplete-sweep — v0 detector (band: kwarg-omission).

Detects the most characteristic AI partial-execution residue: a multi-site
change applied to N-1 of N structurally-similar call sites, leaving one
sibling at the OLD shape. v0 implements ONE band — *keyword-argument
omission*: among the call sites of one callee, a keyword that the strong
majority of siblings pass but one site does not.

The load-bearing discriminator is the **git-trajectory gate**:
a divergence is only a "forgotten sweep" if the sites that HAVE the kwarg
were touched more recently than the straggler (the sweep happened after the
straggler was last edited). A straggler edited just as recently is more
likely a deliberate omission — it is reported separately, below the gate.

Detection only. Never edits code. Advisory SUSPECT output.

Usage:
    .venv/bin/python .claude/skills/find-incomplete-sweep/scripts/scan.py \
        --paths scripts [--min-callsites 4] [--majority-frac 0.75] \
        [--min-present 3] [--out reports/find-incomplete-sweep/scan-<TS>]
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import pathlib
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

# Anchor scans + git at the repo root so results don't depend on the caller's CWD.
# This file lives at .claude/skills/find-incomplete-sweep/scripts/scan.py, so
# parents[4] is the repository root (verified empirically in this checkout).
REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]

# Bare single-segment callee names too generic to cluster meaningfully.
GENERIC_SINGLE = {
    "get", "set", "add", "append", "pop", "join", "format", "split", "strip",
    "keys", "values", "items", "update", "all", "first", "last", "count",
    "exists", "len", "str", "int", "float", "list", "dict", "tuple", "set_",
    "print", "super", "isinstance", "getattr", "setattr", "hasattr", "open",
    "range", "map", "filter", "sorted", "min", "max", "sum", "any", "anyall",
    "startswith", "endswith", "replace", "lower", "upper", "encode", "decode",
}
# kwargs that are universally optional noise — never a meaningful "sweep" token.
SKIP_KWARGS = {"self", "cls"}

# Callees whose kwargs are LOOKUP-VARIANT SELECTORS (which object/row), not
# convention tokens: a site "missing id=" is looking up by pk/slug/name, not
# forgetting. Dropping these removes the dominant false-positive class
# (get_object_or_404(id=), objects.get(id=), qs.filter(...)). These are
# Django-flavored but inert on non-Django code (the names simply never match).
QUERY_LOOKUP_FINAL = {"get", "filter", "exclude", "get_or_create", "update_or_create"}
QUERY_LOOKUP_BARE = {"get_object_or_404", "get_list_or_404"}

# kwargs that are OPTIONAL-BY-NATURE — omission is a valid call, not a sweep
# miss (Thread(args=)/dispatch(args=), save(update_fields=) full-save, using=).
OPTIONAL_KWARGS = {"args", "kwargs", "using", "update_fields"}

# kwargs that are PER-CALL DESIGN CHOICES, not a shared convention — common on
# Django field constructors where func_key collapses every `models.*Field(...)`
# into one group regardless of which relationship it defines (related_name /
# on_delete differ per relationship; a site "missing" them is not a straggler).
# Django-flavored but inert elsewhere (the names simply never match).
DESIGN_CHOICE_KWARGS = {"related_name", "on_delete", "db_index", "db_column"}


@dataclass
class CallSite:
    key: str
    kwargs: frozenset
    file: str
    line: int
    nargs: int = 0  # positional arg count (for arg-count-aware kwargs like flat=)
    kwarg_values: dict = field(default_factory=dict)  # kwarg name -> value signature
    star_kwargs: bool = False  # call has **kwargs unpacking -> kwarg set is unknown


@dataclass
class Finding:
    callee: str
    kwarg: str
    group_size: int
    present_count: int
    majority_frac: float
    straggler_file: str
    straggler_line: int
    present_sites: list = field(default_factory=list)  # (file, line)
    straggler_time: int | None = None
    present_times: list = field(default_factory=list)  # unix times
    gated_in: bool = False
    trajectory_note: str = ""
    optional_by_default: bool = False  # callee declares a default for this kwarg
    override_value: str | None = None  # value the present siblings consistently pass
    default_value: str | None = None   # the callee's declared default it overrides


def func_key(func: ast.AST) -> str | None:
    """Reconstruct a dotted callee key, collapsed to the last two segments."""
    parts: list[str] = []
    cur = func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    elif isinstance(cur, ast.Call):
        parts.append("()")
    if not parts:
        return None
    parts.reverse()
    return ".".join(parts[-2:])


def iter_py_files(paths: list[str]):
    for p in paths:
        root = pathlib.Path(p)
        if not root.is_absolute():
            root = REPO_ROOT / root  # anchor relative --paths at the repo root
        if root.is_file() and root.suffix == ".py":
            yield root
            continue
        for f in root.rglob("*.py"):
            sp = str(f)
            if any(seg in sp for seg in ("/migrations/", "/__pycache__/", "/tests/", "/.venv/")):
                continue
            if f.name.startswith("test_") or f.name.startswith("tests_"):
                continue
            yield f


def collect_callsites(paths: list[str]) -> tuple[list[CallSite], int, int]:
    sites: list[CallSite] = []
    scanned = skipped = 0
    for f in iter_py_files(paths):
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (SyntaxError, UnicodeDecodeError):
            skipped += 1
            continue
        scanned += 1
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            key = func_key(node.func)
            if not key:
                continue
            if "." not in key and key in GENERIC_SINGLE:
                continue
            kw_vals = {
                kw.arg: _literal_sig(kw.value)
                for kw in node.keywords
                if kw.arg and kw.arg not in SKIP_KWARGS
            }
            # `**opts` unpacking (kw.arg is None) means the explicit kwarg set is
            # incomplete — such a site may carry the kwarg via opts, so it must
            # not count as a confident "missing" straggler.
            star_kwargs = any(kw.arg is None for kw in node.keywords)
            kwargs = frozenset(kw_vals)
            sites.append(CallSite(key, kwargs, str(f), node.lineno, len(node.args),
                                  kw_vals, star_kwargs))
    return sites, scanned, skipped


def _is_dataclass_decorated(node: ast.ClassDef) -> bool:
    """True when the class carries a `@dataclass` / `@dataclasses.dataclass`
    decorator (bare or called, e.g. `@dataclass(frozen=True)`)."""
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        name = None
        if isinstance(target, ast.Name):
            name = target.id
        elif isinstance(target, ast.Attribute):
            name = target.attr
        if name == "dataclass":
            return True
    return False


def _value_sig(node: ast.AST) -> str:
    """A stable textual signature of an AST value node. ast.unparse (py3.9+)
    renders literals, names, attributes, unary ops, etc. uniformly."""
    try:
        return ast.unparse(node).strip()
    except (ValueError, RecursionError):
        return "<unparseable>"


def _is_literal(node: ast.AST) -> bool:
    """True for nodes whose value is knowable from source alone — constants,
    signed-constant unary ops, and collections of literals. Names / attributes /
    calls are NOT literal: their value is unknowable here, so they must never
    drive a value-aware promotion (a default `country_code=DEFAULT_CC` and a
    sibling `country_code='us'` could resolve EQUAL despite differing text)."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_is_literal(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and _is_literal(k) and _is_literal(v)
                   for k, v in zip(node.keys, node.values, strict=False))
    return False


def _literal_sig(node: ast.AST) -> str:
    """Comparable value signature for value-awareness: the unparsed literal, or
    the `<expr>` sentinel for any non-literal node. `<expr>` is non-comparable,
    so an unresolved default or call value can never promote a straggler."""
    return _value_sig(node) if _is_literal(node) else "<expr>"


def _dataclass_default_values(node: ast.ClassDef) -> dict[str, str]:
    """Field name -> default-value signature for @dataclass fields with a default.
    `name: T = value` -> sig(value); `field(default=X)` -> sig(X);
    `field(default_factory=...)` -> `<factory>` (mutable default, not comparable).
    A `field(...)` with no default is required and omitted."""
    out: dict[str, str] = {}
    for stmt in node.body:
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            continue
        if stmt.value is None:
            continue  # `name: T` — required, no default
        val = stmt.value
        if isinstance(val, ast.Call):
            fn = val.func
            fn_name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if fn_name == "field":
                dflt = next((kw for kw in val.keywords if kw.arg == "default"), None)
                if dflt is not None:
                    out[stmt.target.id] = _literal_sig(dflt.value)
                elif any(kw.arg == "default_factory" for kw in val.keywords):
                    out[stmt.target.id] = "<factory>"
                continue
        out[stmt.target.id] = _literal_sig(val)
    return out


def _param_default_values(args: ast.arguments) -> dict[str, str]:
    """Parameter name -> default-value signature for a function / __init__.
    Covers positional-or-keyword `defaults` and keyword-only `kw_defaults`
    (a None entry means required)."""
    out: dict[str, str] = {}
    pos = args.posonlyargs + args.args
    n_def = len(args.defaults)
    if n_def:
        for a, d in zip(pos[-n_def:], args.defaults, strict=False):
            out[a.arg] = _literal_sig(d)
    for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=False):
        if d is not None:
            out[a.arg] = _literal_sig(d)
    return out


def collect_default_kwargs(paths: list[str]) -> tuple[dict[str, dict[str, str]], set[str]]:
    """Map a callable's final name -> {param/field name -> default-value signature}.

    Across the scanned paths, indexes by the *bare class/function name* (the
    final segment of a callee key, e.g. `TargetSpec`, `_apply_step_ppc`). For each
    callable we record which parameters/fields are optional-by-default AND their
    default value, so `find_candidates` can down-rank a straggler that merely took
    the default — but PROMOTE it when the siblings consistently pass a different
    (non-default) value (value-awareness).

    Sources:
      - `@dataclass` classes → fields with a default,
      - any class' `__init__` → params with defaults (regular constructors),
      - module-level / nested `def`s → params with defaults.

    Also returns the set of callable names whose signature accepts `**kwargs`.

    On a name COLLISION (two callables share a final name) we MERGE: a param seen
    with the same default value keeps it; a param seen with DIFFERENT defaults is
    marked `<ambiguous>` (not value-comparable, so it stays down-ranked, never
    auto-promoted). Conservative — collisions can only suppress a promotion.
    """
    defaults: dict[str, dict[str, str]] = defaultdict(dict)
    var_kw: set[str] = set()

    def merge(name: str, found: dict[str, str]) -> None:
        cur = defaults[name]
        for k, v in found.items():
            if k in cur and cur[k] != v:
                cur[k] = "<ambiguous>"
            else:
                cur.setdefault(k, v)

    for f in iter_py_files(paths):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if _is_dataclass_decorated(node):
                    merge(node.name, _dataclass_default_values(node))
                for stmt in node.body:
                    if isinstance(stmt, ast.FunctionDef) and stmt.name == "__init__":
                        merge(node.name, _param_default_values(stmt.args))
                        if stmt.args.kwarg is not None:
                            var_kw.add(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                merge(node.name, _param_default_values(node.args))
                if node.args.kwarg is not None:
                    var_kw.add(node.name)
    return defaults, var_kw


def find_candidates(sites, min_callsites, majority_frac, min_present,
                    default_kwargs=None) -> list[Finding]:
    by_key: dict[str, list[CallSite]] = defaultdict(list)
    for s in sites:
        by_key[s.key].append(s)

    findings: list[Finding] = []
    for key, group in by_key.items():
        n = len(group)
        if n < min_callsites:
            continue
        final = key.split(".")[-1]
        # Drop query-lookup callees: their kwargs select WHICH row, not a convention.
        if final in QUERY_LOOKUP_FINAL or key in QUERY_LOOKUP_BARE:
            continue
        kw_count: dict[str, int] = defaultdict(int)
        for s in group:
            for kw in s.kwargs:
                kw_count[kw] += 1
        threshold = max(min_present, math.ceil(majority_frac * n))
        # Optional-by-default fields of the resolved callee (dataclass field /
        # constructor / function param with a declared default), mapped to their
        # default-value signature. A straggler that omitted such a field took the
        # default — usually optional/deliberate, so DOWN-RANK (reported, not gated
        # in). VALUE-AWARENESS: but when the present siblings ALL pass the same
        # value AND it differs from the declared default, the straggler took a
        # DIFFERENT (default) value — that is the flagship forgotten override
        # (country_code='us' on 6/7 calls where the default isn't 'us'), so PROMOTE
        # it back to a normal gated-in candidate.
        callee_defaults = (default_kwargs or {}).get(final, {})
        for kw, cnt in kw_count.items():
            if cnt < threshold or cnt >= n:
                continue  # universal (cnt==n) is complete; below threshold is weak
            if kw in OPTIONAL_KWARGS or kw in DESIGN_CHOICE_KWARGS:
                continue  # optional-by-nature, or a per-call design choice
            present = [s for s in group if kw in s.kwargs]
            # a `**kwargs` site may pass kw via opts — exclude it from "missing".
            missing = [s for s in group if kw not in s.kwargs and not s.star_kwargs]
            # flat=True is illegal with >1 positional field — a straggler that
            # selects multiple columns CANNOT take it; it is not a forgotten site.
            if final == "values_list" and kw == "flat":
                missing = [s for s in missing if s.nargs == 1]
            optional = kw in callee_defaults
            override_val = default_sig = None
            if optional:
                default_sig = callee_defaults.get(kw)
                pvals = {s.kwarg_values.get(kw) for s in present}
                pvals.discard(None)
                NONCOMPARABLE = {"<factory>", "<ambiguous>", "<unparseable>", "<expr>"}
                if (len(pvals) == 1 and default_sig not in NONCOMPARABLE
                        and default_sig is not None):
                    pv = next(iter(pvals))
                    if pv not in NONCOMPARABLE and pv != default_sig:
                        optional = False  # value-aware promotion
                        override_val = pv
            for st in missing:
                findings.append(Finding(
                    callee=key, kwarg=kw, group_size=n,
                    present_count=cnt, majority_frac=round(cnt / n, 2),
                    straggler_file=st.file, straggler_line=st.line,
                    present_sites=[(p.file, p.line) for p in present],
                    optional_by_default=optional,
                    override_value=override_val,
                    default_value=(default_sig if override_val else None),
                ))
    return findings


@lru_cache(maxsize=None)
def _blame_committer_time(abspath: str, line: int) -> int | None:
    """git blame a single line, run from the file's OWN directory so it resolves
    against whatever repo contains the file (not a hardcoded root). Cached by the
    resolved ABSOLUTE path so it is CWD-independent and can't poison across repos."""
    p = pathlib.Path(abspath)
    try:
        out = subprocess.run(
            ["git", "blame", "--porcelain", "-L", f"{line},{line}", "--", p.name],
            cwd=p.parent if p.parent.exists() else REPO_ROOT,
            capture_output=True, text=True, timeout=20,
        )
        if out.returncode != 0:
            return None
        lines = out.stdout.splitlines()
        # An uncommitted ("Not Committed Yet") line blames to the all-zero SHA
        # with committer-time = now; treat it as "no committed blame", not newest.
        if lines and lines[0] and set(lines[0].split()[0]) == {"0"}:
            return None
        for ln in lines:
            if ln.startswith("committer-time "):
                return int(ln.split()[1])
    except (subprocess.SubprocessError, OSError, ValueError):
        return None
    return None


def line_commit_time(file: str, line: int) -> int | None:
    return _blame_committer_time(str(pathlib.Path(file).resolve()), line)


def apply_trajectory_gate(findings: list[Finding]):
    """Gate IN a finding when the straggler is older than the present-site
    sweep — i.e. the kwarg was added after the straggler was last touched.
    Blames ALL present sites (line_commit_time is cached, so unique lines are
    blamed once) rather than a positional prefix, which sampled by file order
    (uncorrelated with recency) and could gate out a real sweep."""
    for fnd in findings:
        if fnd.optional_by_default:
            # never gated in (the callee defaults this kwarg); reported separately.
            fnd.gated_in = False
            fnd.trajectory_note = (
                "kwarg has a declared default on the callee — down-ranked; promote "
                "only if the present sites pass a consistent NON-default value"
            )
            continue
        fnd.straggler_time = line_commit_time(fnd.straggler_file, fnd.straggler_line)
        fnd.present_times = [
            t for (pf, pl) in fnd.present_sites
            if (t := line_commit_time(pf, pl)) is not None
        ]
        if fnd.straggler_time is None or not fnd.present_times:
            fnd.gated_in = False
            fnd.trajectory_note = "no blame data — cannot establish trajectory"
            continue
        newer = sum(1 for t in fnd.present_times if t > fnd.straggler_time)
        frac_newer = newer / len(fnd.present_times)
        if frac_newer >= 0.5:
            fnd.gated_in = True
            fnd.trajectory_note = (
                f"{newer}/{len(fnd.present_times)} kwarg-present sites touched "
                f"AFTER the straggler — consistent with a sweep that missed it"
            )
        else:
            fnd.gated_in = False
            fnd.trajectory_note = (
                f"only {newer}/{len(fnd.present_times)} present sites newer than "
                f"straggler — straggler edited recently; likely deliberate"
            )


def rel(path: str) -> str:
    try:
        return str(pathlib.Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return path


def render(findings, scanned, skipped, args) -> str:
    gated = [f for f in findings if f.gated_in]
    optional_default = [f for f in findings if f.optional_by_default]
    ungated = [f for f in findings if not f.gated_in and not f.optional_by_default]
    gated.sort(key=lambda f: (-f.majority_frac, -f.group_size))
    optional_default.sort(key=lambda f: (-f.majority_frac, -f.group_size))
    ungated.sort(key=lambda f: (-f.majority_frac, -f.group_size))

    L = []
    L.append("# find-incomplete-sweep — findings (v0, band: kwarg-omission)\n")
    L.append(f"- paths: `{', '.join(args.paths)}`")
    L.append(f"- files scanned: {scanned}  (unparseable skipped: {skipped})")
    L.append(f"- thresholds: min-callsites={args.min_callsites}, "
             f"majority-frac={args.majority_frac}, min-present={args.min_present}")
    L.append(f"- raw divergence candidates: {len(findings)}")
    L.append(f"- **gated IN (forgotten-sweep shape): {len(gated)}**")
    L.append(f"- down-ranked (kwarg has a declared default): {len(optional_default)}")
    L.append(f"- gated out (recent straggler / no blame): {len(ungated)}\n")

    def block(f: Finding) -> str:
        lines = [
            f"### `{f.callee}(…, {f.kwarg}=…)` — straggler missing `{f.kwarg}`",
            f"- straggler: `{rel(f.straggler_file)}:{f.straggler_line}` "
            f"(missing `{f.kwarg}`)",
            f"- majority: {f.present_count}/{f.group_size} call sites pass "
            f"`{f.kwarg}` ({int(f.majority_frac*100)}%)",
            *([f"- value-override: siblings all pass `{f.override_value}` ≠ default "
               f"`{f.default_value}` — straggler took the default (candidate forgotten "
               f"override; the scout confirms forgotten vs deliberate)"]
              if f.override_value else []),
            f"- trajectory: {f.trajectory_note}",
            "- present sites: "
            + ", ".join(f"`{rel(pf)}:{pl}`" for pf, pl in f.present_sites[:6])
            + ("" if len(f.present_sites) <= 6 else f" … (+{len(f.present_sites)-6})"),
        ]
        return "\n".join(lines)

    L.append("## Gated IN — likely forgotten sweeps\n")
    L.append("\n\n".join(block(f) for f in gated) if gated else "_none_")
    L.append("\n\n## Down-ranked — kwarg has a declared default "
             "(promote only if the present sites pass a NON-default value)\n")
    L.append("\n\n".join(block(f) for f in optional_default[:25]) if optional_default else "_none_")
    if len(optional_default) > 25:
        L.append(f"\n_… {len(optional_default)-25} more down-ranked candidates omitted._")
    L.append("\n\n## Gated OUT — divergence without sweep-trajectory "
             "(review separately; likely intentional)\n")
    L.append("\n\n".join(block(f) for f in ungated[:25]) if ungated else "_none_")
    if len(ungated) > 25:
        L.append(f"\n_… {len(ungated)-25} more gated-out candidates omitted._")
    return "\n".join(L) + "\n"


def run_kwarg_band(args):
    """The v0 kwarg-omission band: detect + dataclass-default pre-filter + gate."""
    sites, scanned, skipped = collect_callsites(args.paths)
    default_kwargs, _var_kw = collect_default_kwargs(args.paths)
    findings = find_candidates(
        sites, args.min_callsites, args.majority_frac, args.min_present,
        default_kwargs=default_kwargs,
    )
    if not args.no_gate:
        apply_trajectory_gate(findings)

    report = render(findings, scanned, skipped, args)
    if args.out:
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "findings.md").write_text(report)
        (out / "manifest.json").write_text(json.dumps({
            "band": "kwarg-omission",
            "files_scanned": scanned, "files_skipped": skipped,
            "raw_candidates": len(findings),
            "gated_in": sum(1 for f in findings if f.gated_in),
            "down_ranked": sum(1 for f in findings if f.optional_by_default),
            "findings": [
                {"callee": f.callee, "kwarg": f.kwarg,
                 "straggler": f"{rel(f.straggler_file)}:{f.straggler_line}",
                 "majority_frac": f.majority_frac, "group_size": f.group_size,
                 "gated_in": f.gated_in,
                 "optional_by_default": f.optional_by_default,
                 "override_value": f.override_value,
                 "default_value": f.default_value,
                 "trajectory": f.trajectory_note}
                for f in findings
            ],
        }, indent=2))
        print(f"wrote {out}/findings.md  "
              f"({sum(1 for f in findings if f.gated_in)} gated-in / {len(findings)} raw)")
    else:
        sys.stdout.write(report)


def run_placeholder_band(args):
    """The placeholder-residue band — delegates to the sibling module so neither
    band grows into an omnibus. Writes placeholder_findings.md / _manifest.json
    so the kwarg band's findings.md / manifest.json (which scout.py consumes)
    stay untouched."""
    import placeholder as _ph
    items, scanned = _ph.run(args.paths, args.max_age_days)
    report = _ph.render(items, scanned, args.paths, args.max_age_days)
    if args.out:
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "placeholder_findings.md").write_text(report)
        (out / "placeholder_manifest.json").write_text(
            json.dumps(_ph.manifest(items, scanned, args.max_age_days), indent=2))
        print(f"wrote {out}/placeholder_findings.md  "
              f"({sum(1 for i in items if i.gated_in)} gated-in / {len(items)} raw)")
    else:
        sys.stdout.write(report)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", choices=["kwarg", "placeholder", "all"], default="kwarg",
                    help="which detector band(s) to run (default: kwarg-omission)")
    ap.add_argument("--paths", nargs="+", required=True,
                    help="one or more source roots / files to scan (e.g. scripts). "
                         "Required — there is no default scan root, so a wrong "
                         "default can never silently scan nothing.")
    ap.add_argument("--min-callsites", type=int, default=4)
    ap.add_argument("--majority-frac", type=float, default=0.75)
    ap.add_argument("--min-present", type=int, default=3)
    ap.add_argument("--max-age-days", type=float, default=120.0,
                    help="placeholder band recency gate (stubs older = accepted debt)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-gate", action="store_true",
                    help="skip git-trajectory blame (faster, no discriminator)")
    args = ap.parse_args()

    if args.band in ("kwarg", "all"):
        run_kwarg_band(args)
    if args.band in ("placeholder", "all"):
        run_placeholder_band(args)


if __name__ == "__main__":
    main()
