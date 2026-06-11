#!/usr/bin/env python3
"""Sweep-harness prototype: batch detection -> diffable manifest -> digest.

Dogfood exploration for the batch-sweep design (pre-ADR). Runs a battery of
agent-free detectors over a target repo and emits:
  manifest.json  — normalized findings with STABLE finding ids
  digest.md      — counts + top-N, the ONLY thing an agent should read

Finding identity: sha1(rule|path|symbol)[:12] — deliberately excludes line
numbers and volatile metrics so ids survive unrelated drift and manifests
from different runs can be diffed (fixed / new / persisting).

Subcommands:
  scan --root R --out M.json [--scope d1 d2 ...]
  diff BEFORE.json AFTER.json

Battery (each entry degrades gracefully if its tool errors):
  cx          find-complexity-hotspots detect.py   (ecosystem, JSONL)
  omnibus     find-omnibus detect.py per scope dir (ecosystem, JSONL)
  ruff        ruff check --output-format json, aggregated per (path, code)
  strdisp     inline generic AST detector: string-literal equality dispatch
              chains (>=4 `x == "lit"` compares in one function)

Prototype quality: no tests, paths to the ecosystem repo are resolved
relative to this file. Formalization happens after the dogfood verdict.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ES_ROOT = Path(__file__).resolve().parents[3]
VENV_PY = ES_ROOT / ".venv" / "bin" / "python"
RUFF = ES_ROOT / ".venv" / "bin" / "ruff"
CX = ES_ROOT / ".claude" / "skills" / "find-complexity-hotspots" / "scripts" / "detect.py"
OM = ES_ROOT / ".claude" / "skills" / "find-omnibus" / "scripts" / "detect.py"


def fid(rule: str, path: str, symbol: str) -> str:
    return hashlib.sha1(f"{rule}|{path}|{symbol}".encode()).hexdigest()[:12]


def finding(rule, path, symbol, severity, summary, **extra) -> dict:
    return {"id": fid(rule, path, symbol), "rule": rule, "path": path,
            "symbol": symbol, "severity": severity, "summary": summary[:200], **extra}


def _jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


# --- battery members -------------------------------------------------------

def run_cx(root: Path, scope: list[str]) -> list[dict]:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        out = Path(tf.name)
    cmd = [str(VENV_PY), str(CX), "--project-root", str(root), "--output", str(out),
           "--max-findings", "500"] + [str(root / s) for s in scope]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    res = []
    for r in _jsonl(out):
        sev = 3 if r.get("impact", 0) >= 80 else (2 if r.get("impact", 0) >= 50 else 1)
        res.append(finding(f"cx:{r.get('pattern', '?')}", r.get("file", "?"),
                           r.get("symbol", ""), sev, r.get("summary", ""),
                           line=r.get("lineno")))
    return res


def run_omnibus(root: Path, scope: list[str]) -> list[dict]:
    res = []
    for s in scope:
        target = root / s
        if not target.is_dir():
            continue
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            out = Path(tf.name)
        cmd = [str(VENV_PY), str(OM), "--target", str(target), "--project-root",
               str(root), "--output", str(out), "--language", "python"]
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        for r in _jsonl(out):
            sev = 3 if r.get("cluster_count", 0) >= 10 else 2
            res.append(finding("omnibus", r.get("file", "?"), "", sev,
                               f"{r.get('loc')} LOC, {r.get('cluster_count')} symbol clusters, "
                               f"risk signals: {','.join(r.get('risk_signals', [])[:4])}",
                               loc=r.get("loc"), clusters=r.get("cluster_count")))
    return res


def run_ruff(root: Path, scope: list[str]) -> list[dict]:
    cmd = [str(RUFF), "check", "--output-format", "json", "--exit-zero"] + \
          [str(root / s) for s in scope]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=root)
    try:
        rows = json.loads(p.stdout or "[]")
    except json.JSONDecodeError:
        return []
    agg: dict[tuple[str, str], int] = Counter()
    for r in rows:
        rel = str(Path(r.get("filename", "?")).resolve()).replace(str(root) + "/", "")
        agg[(rel, r.get("code") or "?")] += 1
    return [finding(f"ruff:{code}", path, "", 1, f"{n} instance(s) of {code}", count=n)
            for (path, code), n in agg.items()]


def run_strdisp(root: Path, scope: list[str], threshold: int = 4) -> list[dict]:
    """Generic concept detector: functions doing string-literal equality dispatch."""
    res = []
    for s in scope:
        base = root / s
        files = [base] if base.is_file() else sorted(base.rglob("*.py"))
        for f in files:
            if "test" in f.parts[len(root.parts):][0] if f.parts[len(root.parts):] else False:
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                lits = 0
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Compare) and any(
                        isinstance(c, ast.Constant) and isinstance(c.value, str)
                        for c in sub.comparators
                    ) and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in sub.ops):
                        lits += 1
                if lits >= threshold:
                    rel = str(f.relative_to(root))
                    sev = 3 if lits >= 12 else 2
                    res.append(finding("str-dispatch", rel, node.name, sev,
                                       f"{lits} string-literal equality compares in one "
                                       f"function — registry/enum dispatch candidate",
                                       compares=lits, line=node.lineno))
    return res


BATTERY = {"cx": run_cx, "omnibus": run_omnibus, "ruff": run_ruff, "strdisp": run_strdisp}


# --- manifest / digest / diff ----------------------------------------------

def build_manifest(root: Path, scope: list[str]) -> dict:
    findings, errors = [], {}
    for name, fn in BATTERY.items():
        try:
            got = fn(root, scope)
            findings.extend(got)
            print(f"[{name}] {len(got)} findings", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — battery member isolation: one broken detector must not kill the sweep
            errors[name] = str(exc)[:200]
            print(f"[{name}] ERROR {exc}", file=sys.stderr)
    findings.sort(key=lambda x: (-x["severity"], x["rule"], x["path"]))
    return {"target": str(root), "scope": scope,
            "counts": dict(Counter(x["rule"].split(":")[0] for x in findings)),
            "total": len(findings), "errors": errors, "findings": findings}


# Numeric finding fields the ratchet treats as one-way: a persisting finding
# whose metric GREW beyond baseline is a regression even though its id is stable.
RATCHET_METRICS = ("loc", "clusters", "count", "compares")


def cmd_scan(args) -> int:
    root = args.root.resolve()
    manifest = build_manifest(root, args.scope)
    findings = manifest["findings"]
    args.out.write_text(json.dumps(manifest, indent=1))

    by_fam = defaultdict(list)
    for x in findings:
        by_fam[x["rule"].split(":")[0]].append(x)
    lines = [f"# sweep digest — {root.name} ({len(findings)} findings)", ""]
    for fam, rows in sorted(by_fam.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {fam} — {len(rows)}")
        for x in rows[:args.top]:
            sym = f"::{x['symbol']}" if x["symbol"] else ""
            lines.append(f"- `{x['id']}` s{x['severity']} {x['path']}{sym} — {x['summary']}")
        if len(rows) > args.top:
            lines.append(f"- … {len(rows) - args.top} more (see manifest)")
        lines.append("")
    digest = args.out.with_suffix(".digest.md")
    digest.write_text("\n".join(lines))
    print(f"wrote {args.out} + {digest}")
    return 0


def cmd_diff(args) -> int:
    a = {x["id"]: x for x in json.loads(args.before.read_text())["findings"]}
    b = {x["id"]: x for x in json.loads(args.after.read_text())["findings"]}
    fixed, new = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    print(f"fixed: {len(fixed)}   new: {len(new)}   persisting: {len(set(a) & set(b))}")
    for i in fixed:
        print(f"  FIXED {a[i]['rule']} {a[i]['path']}::{a[i]['symbol']}")
    for i in new:
        print(f"  NEW   {b[i]['rule']} {b[i]['path']}::{b[i]['symbol']} — {b[i]['summary'][:80]}")
    return 0 if not new else 1


def cmd_ratchet(args) -> int:
    """Structural seatbelt: the baseline manifest is a one-way ratchet.

    FAIL if the current scan introduces a NEW finding id, or grows a ratchet
    metric (loc/clusters/count/compares) on a persisting finding. When clean
    and anything improved, auto-tighten: rewrite the baseline to the current
    state so the improvement can never silently regress. The baseline and the
    sweep manifest are the same artifact at two moments — the GUARD layer and
    the batch harness share one schema (Atlas seatbelt mechanics,
    independently reimplemented, generalized from lint rules to structure).
    """
    base = {x["id"]: x for x in json.loads(args.baseline.read_text())["findings"]}
    cur_manifest = build_manifest(args.root.resolve(), args.scope)
    cur = {x["id"]: x for x in cur_manifest["findings"]}

    accepted = set(args.accept or [])
    violations: list[str] = []
    waived = 0
    for i in set(cur) - set(base):
        if i in accepted:
            waived += 1
            continue
        x = cur[i]
        violations.append(f"NEW     {x['rule']} {x['path']}::{x['symbol']} — {x['summary'][:80]}  [{i}]")
    for i in set(cur) & set(base):
        for m in RATCHET_METRICS:
            b, c = base[i].get(m), cur[i].get(m)
            if isinstance(b, int) and isinstance(c, int) and c > b:
                if i in accepted:  # deliberate increase: baseline absorbs the new value below
                    waived += 1
                    break
                violations.append(f"GREW    {cur[i]['rule']} {cur[i]['path']}::{cur[i]['symbol']} — {m} {b} -> {c}  [{i}]")

    fixed = set(base) - set(cur)
    improved = sum(
        1 for i in set(cur) & set(base) for m in RATCHET_METRICS
        if isinstance(base[i].get(m), int) and isinstance(cur[i].get(m), int)
        and cur[i][m] < base[i][m]
    )
    if violations:
        print(f"RATCHET FAILED — {len(violations)} regression(s) vs {args.baseline}:")
        for v in violations:
            print(f"  {v}")
        return 1
    if (fixed or improved or waived) and not args.no_update:
        args.baseline.write_text(json.dumps(cur_manifest, indent=1))
        tail = f", {waived} deliberate increase(s) absorbed" if waived else ""
        print(f"RATCHET OK — tightened baseline: {len(fixed)} finding(s) removed, "
              f"{improved} metric(s) improved{tail} ({len(cur)} findings now held)")
    else:
        print(f"RATCHET OK — no change ({len(cur)} findings held)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--scope", nargs="+", default=["."])
    p.add_argument("--top", type=int, default=10)
    p.set_defaults(fn=cmd_scan)
    p = sub.add_parser("diff")
    p.add_argument("before", type=Path)
    p.add_argument("after", type=Path)
    p.set_defaults(fn=cmd_diff)
    p = sub.add_parser("ratchet")
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--scope", nargs="+", default=["."])
    p.add_argument("--no-update", action="store_true",
                   help="check only; do not auto-tighten the baseline")
    p.add_argument("--accept", action="append", metavar="FINDING_ID",
                   help="deliberately accept a new finding or metric increase "
                        "(the SEATBELT_INCREASE analog); repeatable, recorded "
                        "by the baseline absorbing the new value")
    p.set_defaults(fn=cmd_ratchet)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
