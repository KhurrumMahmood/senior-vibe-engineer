#!/usr/bin/env python3
"""Push-inference pass for /orient (ADR 0020).

Read-only. Greps a project tree for a small set of high-signal
"the project looks more mature / more exposed than its declared state"
markers and prints candidate-transition flags. It NEVER writes anything
— not the state file, not a report. Inference only PROPOSES; a human
disposes by (re-)running /orient.

The signal taxonomy and how to read the output are documented in
`knowledge/inference-heuristics.md`.

Output: human-readable flags by default, or `--json` for a machine
payload. Exit code is always 0 unless there is a usage error (2) —
"signals found" is not an error condition, it's the normal result.

Stdlib-only; runs under plain `python3`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Directories never worth scanning — vendored deps, VCS, build output,
# virtualenvs, caches. Keeps the grep fast and the signal clean.
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "vendor",
    "site-packages",
    ".tox",
    # Data / fixture / cache surfaces — transition signals live in
    # hand-written source, not in captured pages or data dumps. Skipping
    # these keeps the scan fast on data-heavy repos (e.g. a crawler with
    # tens of thousands of cached-HTML fixtures).
    "fixtures",
    "__snapshots__",
    "snapshots",
    "cassettes",
    ".cache",
    "htmlcov",
    "http_cache",
    "coverage",
    # Agent worktrees hold full duplicate checkouts of the repo — scanning
    # them re-reads the entire tree N times and yields only echoes of the
    # primary checkout's signals. Always skip.
    "worktrees",
    ".worktrees",
}

# Files larger than this are almost certainly generated artifacts or
# captured data (cached HTML, JSON dumps, SQL exports), not the source
# where a maturity/stakes signal would live. We skip them and report the
# skip count, so a quiet "no signals" can never silently mean "did not
# read a 5 MB fixture." Source files are virtually never this large.
MAX_FILE_BYTES = 512 * 1024

# Text extensions we will read line-by-line for content signals. Binary
# and large-asset extensions are skipped implicitly (not in this set).
TEXT_EXTS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rb",
    ".rs",
    ".java",
    ".php",
    ".sql",
    ".env",
    ".cfg",
    ".ini",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".tf",
    ".conf",
    "",  # extensionless config files (Dockerfile, Procfile, etc.)
}

# Filenames (case-insensitive) that are deploy/ingress signals on their
# own, independent of content.
DEPLOY_FILENAMES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "vercel.json",
    "netlify.toml",
    "procfile",
    "fly.toml",
    "render.yaml",
    "app.yaml",  # GAE
}


@dataclass
class Signal:
    """One transition signal definition."""

    key: str
    label: str
    axis: str  # "stakes", "maturity", or "maturity+stakes"
    suggests: str  # human phrase, e.g. "stakes >= external"
    pattern: re.Pattern[str]
    # Restrict to certain file kinds when a signal would otherwise be noisy.
    only_exts: frozenset[str] | None = None


@dataclass
class Hit:
    signal_key: str
    path: str
    lineno: int
    line: str


@dataclass
class SignalResult:
    signal: Signal
    hits: list[Hit] = field(default_factory=list)


# --- Signal definitions -------------------------------------------------
#
# These are deliberately broad-but-cheap. A hit is a PROMPT for a human,
# never a verdict. False positives are acceptable here — the cost of a
# spurious "re-run /orient?" is one human glance; the cost of a missed
# exposure transition is shipping a prototype-grade control into an
# exposed context. Tune for recall, document the noise in knowledge/.

def _ci(pat: str) -> re.Pattern[str]:
    return re.compile(pat, re.IGNORECASE)


SIGNALS: list[Signal] = [
    Signal(
        key="unauth_side_effect",
        label="Side-effectful HTTP handler (verify auth guard)",
        axis="stakes",
        suggests="stakes >= external (untrusted callers reaching writes)",
        # Route decorators / handlers for mutating verbs across common
        # frameworks. We flag the *presence* of a write surface; the human
        # confirms whether it is unauthenticated.
        pattern=_ci(
            r"@(?:app|router|api|blueprint|bp)\.(?:post|put|patch|delete)\b"
            r"|methods\s*=\s*\[[^\]]*['\"](?:POST|PUT|PATCH|DELETE)['\"]"
            r"|@require_http_methods\([^)]*['\"](?:POST|PUT|PATCH|DELETE)['\"]"
            r"|\.(?:post|put|patch|delete)\(\s*['\"]/"  # express-style app.post('/...')
        ),
        only_exts=frozenset({".py", ".js", ".jsx", ".ts", ".tsx", ".rb", ".go", ".php"}),
    ),
    Signal(
        key="public_deploy",
        label="Public deploy / ingress config",
        axis="maturity+stakes",
        suggests="stakes >= external and likely maturity >= first-users",
        pattern=_ci(
            r"^\s*EXPOSE\s+\d+"  # Dockerfile
            r"|kind:\s*Ingress"  # k8s
            r"|LoadBalancer"  # k8s/cloud LB
            r"|aws_lb\b|aws_alb\b|google_compute_global_address"  # terraform
            r"|server\s*\{"  # nginx server block
            r"|listen\s+\d+\s*;"  # nginx listen
        ),
    ),
    Signal(
        key="payment_pii",
        label="Payment / PII / credential handling",
        axis="stakes",
        suggests="stakes >= external (regulated / high-blast-radius data)",
        pattern=_ci(
            r"\bstripe\b|\bbraintree\b|\bpaypal\b|\bplaid\b"
            r"|card_number|cardnumber|cvv|cvc\b"
            r"|\bssn\b|social_security|passport_number"
            r"|secrets?manager|hashicorp[_-]?vault|vault_client"
        ),
    ),
    Signal(
        key="auth_added",
        label="Auth / login / session surface",
        axis="maturity+stakes",
        suggests="maturity >= first-users and/or stakes >= external",
        pattern=_ci(
            r"\boauth2?\b|\bopenid\b"
            r"|login_required|@login_required"
            r"|create_session|session\[|session_cookie"
            r"|jwt\.(?:encode|decode)|verify_password|check_password"
            r"|passport\.authenticate|use\(passport"
        ),
    ),
    Signal(
        key="real_user_data",
        label="Real-user-data model / production DB",
        axis="maturity",
        suggests="maturity >= first-users (real users / data present)",
        pattern=_ci(
            r"class\s+(?:User|Account|Customer|Member|Subscriber)\b"
            r"|CREATE\s+TABLE\s+(?:users|accounts|customers)\b"
            r"|DATABASE_URL\s*=\s*['\"]?postgres"
            r"|RDS|cloud[_-]?sql|atlas[_-]?uri|mongodb\+srv://"
        ),
    ),
]

# Ordinal ladders — used to phrase the "above declared state" comparison.
MATURITY_ORDER = {"prototype": 0, "first-users": 1, "production": 2}
STAKES_ORDER = {"internal": 0, "external": 1, "public-adversarial": 2}


def iter_text_files(root: Path):
    """Yield text files under root, skipping vendored/build dirs.

    Uses os.walk with in-place dir pruning so we never descend into
    .venv / node_modules / build trees — Path.rglob would still traverse
    them before filtering, which is unacceptably slow on a real repo.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in place so os.walk does not descend into them.
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            path = Path(dirpath) / fn
            name_lower = fn.lower()
            if path.suffix.lower() in TEXT_EXTS or name_lower in DEPLOY_FILENAMES:
                yield path


def deploy_filename_hit(path: Path) -> Hit | None:
    """A deploy-config filename is itself a signal, content aside."""
    if path.name.lower() in DEPLOY_FILENAMES:
        return Hit(
            signal_key="public_deploy",
            path=str(path),
            lineno=0,
            line=f"(file present: {path.name})",
        )
    return None


def scan(root: Path, max_files: int) -> tuple[dict[str, SignalResult], dict[str, int]]:
    """Return (results, stats).

    stats has files_scanned, files_skipped_large, and budget_exhausted
    (1 if the --max-files cap stopped the scan early — reported, never a
    silent partial result).
    """
    results: dict[str, SignalResult] = {s.key: SignalResult(signal=s) for s in SIGNALS}
    stats = {"files_scanned": 0, "files_skipped_large": 0, "budget_exhausted": 0}
    for path in iter_text_files(root):
        rel = path.relative_to(root)
        # Filename-only deploy signal — costs nothing, do it before any
        # size gate so a large compose file still registers as present.
        fn_hit = deploy_filename_hit(path)
        if fn_hit is not None:
            fn_hit.path = str(rel)
            results["public_deploy"].hits.append(fn_hit)
        # Size gate: skip generated/data artifacts (counted, not silent).
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                stats["files_skipped_large"] += 1
                continue
        except OSError:
            continue
        # Defensive overall budget: a pathological repo (e.g. tens of
        # thousands of small fixtures) should not make a quick-orientation
        # helper run unbounded. Stop and report rather than churn.
        if stats["files_scanned"] >= max_files:
            stats["budget_exhausted"] = 1
            break
        # Content signals — read once, test each applicable pattern.
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        stats["files_scanned"] += 1
        suffix = path.suffix.lower()
        lines = text.splitlines()
        for sig in SIGNALS:
            if sig.only_exts is not None and suffix not in sig.only_exts:
                continue
            for i, line in enumerate(lines, start=1):
                if sig.pattern.search(line):
                    results[sig.key].hits.append(
                        Hit(
                            signal_key=sig.key,
                            path=str(rel),
                            lineno=i,
                            line=line.strip()[:160],
                        )
                    )
    # De-dup the public_deploy filename hit if the same file also matched
    # on content (keep both kinds but avoid identical duplicates).
    for res in results.values():
        seen = set()
        deduped = []
        for h in res.hits:
            key = (h.path, h.lineno, h.line)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(h)
        res.hits = deduped
    return results, stats


def read_declared_state(root: Path) -> dict | None:
    state_file = root / ".project-state.json"
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_malformed": True}


def above_declared(signal: Signal, declared: dict | None) -> bool:
    """True if this signal suggests a rung above the declared state.

    No declared state → everything is 'worth a look' (return True).
    Malformed declared state → treat as undeclared.
    """
    if not declared or declared.get("_malformed"):
        return True
    # Map the signal's axis to a comparison. We use a coarse heuristic:
    # any maturity-bearing signal compares against >= first-users(1); any
    # stakes-bearing signal compares against >= external(1). The skill
    # body does the precise human framing — this is just "is it plausibly
    # above where you said you are?"
    raises_maturity = "maturity" in signal.axis
    raises_stakes = "stakes" in signal.axis
    cur_mat = MATURITY_ORDER.get(declared.get("maturity"), 0)
    cur_stk = STAKES_ORDER.get(declared.get("stakes"), 0)
    if raises_stakes and cur_stk < STAKES_ORDER["external"]:
        return True
    if raises_maturity and cur_mat < MATURITY_ORDER["first-users"]:
        return True
    return False


def render_text(
    results: dict[str, SignalResult], declared: dict | None, root: Path, stats: dict[str, int]
) -> None:
    print(f"# /orient push-inference — {root}")
    if declared is None:
        print("\nDeclared state: NONE (.project-state.json not found).")
        print("→ Run /orient to set the project's maturity × stakes state.\n")
    elif declared.get("_malformed"):
        print("\nDeclared state: .project-state.json present but UNPARSEABLE.")
        print("→ Re-run /orient to re-establish a valid state.\n")
    else:
        print(
            f"\nDeclared state: maturity={declared.get('maturity')!r} "
            f"stakes={declared.get('stakes')!r} "
            f"(declared_at={declared.get('declared_at')!r})\n"
        )

    any_flagged = False
    for sig in SIGNALS:
        res = results[sig.key]
        n = len(res.hits)
        if n == 0:
            continue
        flagged = above_declared(sig, declared)
        marker = "FLAG" if flagged else "info"
        if flagged:
            any_flagged = True
        print(f"[{marker}] {sig.label} — {n} hit(s)")
        print(f"        axis: {sig.axis}; suggests: {sig.suggests}")
        for h in res.hits[:5]:
            loc = h.path if h.lineno == 0 else f"{h.path}:{h.lineno}"
            print(f"        - {loc}  {h.line}")
        if n > 5:
            print(f"        … and {n - 5} more")
        print()

    if not any([len(r.hits) for r in results.values()]):
        print("No transition signals found. (Read-only scan; nothing written.)")
    elif any_flagged:
        print(
            "Signals above your declared state are marked [FLAG]. These are "
            "PROPOSALS, not verdicts —\nre-run /orient if any reflect a real "
            "transition. Nothing was written by this scan."
        )
    else:
        print(
            "All signals are at or below your declared state ([info]). No "
            "re-orientation prompted.\nNothing was written by this scan."
        )

    if stats["files_skipped_large"]:
        print(
            f"\n(Note: skipped {stats['files_skipped_large']} file(s) over "
            f"{MAX_FILE_BYTES // 1024} KB as generated/data artifacts; "
            f"scanned {stats['files_scanned']}. Transition signals live in "
            "source, not large fixtures — but if a real source file exceeds "
            "the cap, raise MAX_FILE_BYTES.)"
        )
    if stats["budget_exhausted"]:
        print(
            f"\n(Note: hit the --max-files budget after "
            f"{stats['files_scanned']} files — this scan is PARTIAL. Narrow "
            "--project-root to your source root, or raise --max-files, for "
            "full coverage. A partial scan is not a clean bill of health.)"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root to scan (default: cwd). Read-only.",
    )
    ap.add_argument("--json", action="store_true", help="Emit a machine-readable payload.")
    ap.add_argument(
        "--max-files",
        type=int,
        default=20000,
        help="Defensive cap on files content-scanned (default: 20000). "
        "A pathological repo should not make a quick helper run unbounded; "
        "exhausting the budget is reported, never silent.",
    )
    args = ap.parse_args(argv)

    root = args.project_root.resolve()
    if not root.is_dir():
        print(f"error: --project-root {root} is not a directory", file=sys.stderr)
        return 2

    declared = read_declared_state(root)
    results, stats = scan(root, max_files=args.max_files)

    if args.json:
        payload = {
            "project_root": str(root),
            "declared_state": None if declared is None else declared,
            "scan_stats": stats,
            "signals": [
                {
                    "key": sig.key,
                    "label": sig.label,
                    "axis": sig.axis,
                    "suggests": sig.suggests,
                    "above_declared": above_declared(sig, declared),
                    "hit_count": len(results[sig.key].hits),
                    "hits": [
                        {"path": h.path, "lineno": h.lineno, "line": h.line}
                        for h in results[sig.key].hits[:25]
                    ],
                }
                for sig in SIGNALS
            ],
            "wrote_anything": False,
        }
        print(json.dumps(payload, indent=2))
        return 0

    render_text(results, declared, root, stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
