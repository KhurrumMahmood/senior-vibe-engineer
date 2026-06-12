#!/usr/bin/env python3
"""Score a /prevent-regression proposal by side-effect (conformance-by-artifact).

Principle: **anti-gateguard-theater**. We never grade a guard by what the run
claims it did. We grade only (a) the artifacts it left on disk, and (b) the
result of re-running the skill's OWN verifiers against those artifacts. A guard
that does not catch the very bug it was built for is theater even if every file
exists and the proposal text says it passed.

The post-condition set is derived from the prevent-regression SKILL.md Phase
Pre/Post declarations:

    C1  pattern.md            Phase 1 Post   (cosmetic)
    C2  rule script + CLI     Phase 2 Post   (cosmetic — contract mechanics)
    C3  fixture pair +        Phase 3 Post   (CONSEQUENTIAL)
        verify_rule.py
    C4  historical-fire       Phase 6 Verification  (CONSEQUENTIAL)
    C5  pre-commit + CI + run.py wiring   Phase 4 Post   (cosmetic)
    C6  CLAUDE.md entry       Phase 5 Post   (cosmetic)
    C7  proposal.md           Phase 6 Post   (cosmetic)
    C8  bounded incidental firing   (CONSEQUENTIAL)

"Consequential" = the check proves the guard does its job *durably*. A guard
does its job only if it both (a) fires on the bug and (b) stays quiet on clean
code. C3 + C4 cover (a): the skill's differential verifier passes and the rule
fires on the real pre-anchor bug while clean on the post-fix HEAD. C8 covers
(b): run across the whole enforcement scope, the rule's hits land ONLY in the
known anti-pattern files — an over-broad rule that also flags innocent code is
not theater (it does catch the bug) but it is a guard that will be # noqa'd or
deleted, after which it protects nothing, so over-firing is a consequential
failure too. The rest are necessary-but-cosmetic: their absence makes the
proposal incomplete, but their presence does not prove the guard works.

Note on C4/C8 hit-counting: both count violation lines by the rule's emitted
tag (``: <rule_name>: ``). If a rule's emitted tag drifts from the wired/manifest
name, C4 sees zero hits and fails — the same scorecard signature as a rule whose
matcher simply misses the bug. The verdict (fail) is correct either way, but the
two root causes are not distinguishable from the scorecard alone.

Overall verdict:
    fail              if ANY consequential check fails
    pass-with-notes   if only cosmetic checks fail
    pass              if everything passes

Output: writes ``conformance.json`` into the proposal dir (or ``--out``) and
prints a human summary. Exit 0 if verdict is pass / pass-with-notes, 1 if fail,
2 on harness error.

Inputs (see --help): the proposal dir, the seeded target repo (post-install),
the anchor SHA, the rule name, and the list of fixed files.

IMPORTANT: this scorer grades the seeded repo AFTER the proposal has been
installed into it (rule + fixtures copied in, wiring applied). Use
``install_proposal.py`` to install first; ``validate.py`` orchestrates a fresh
seed + install + score per proposal so the two proposals never contaminate each
other.

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The real skill verifier we reuse (never reimplement). Resolved relative to the
# project root the scorer is told about, falling back to the worktree default.
VERIFY_RULE_REL = ".claude/skills/prevent-regression/scripts/verify_rule.py"

CLEAN_INPUT = "x = 1\n"  # guaranteed to produce zero hits for any sane rule


@dataclass
class CheckResult:
    id: str
    name: str
    consequential: bool
    passed: bool
    evidence: str


@dataclass
class Scorecard:
    proposal: str
    repo: str
    rule_name: str
    anchor: str
    fixed_files: list[str]
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, c: CheckResult) -> None:
        self.checks.append(c)

    @property
    def verdict(self) -> str:
        consequential_fail = any(c.consequential and not c.passed for c in self.checks)
        if consequential_fail:
            return "fail"
        cosmetic_fail = any((not c.consequential) and not c.passed for c in self.checks)
        return "pass-with-notes" if cosmetic_fail else "pass"

    def to_dict(self) -> dict:
        return {
            "proposal": self.proposal,
            "repo": self.repo,
            "rule_name": self.rule_name,
            "anchor": self.anchor,
            "fixed_files": self.fixed_files,
            "verdict": self.verdict,
            "checks": [
                {
                    "id": c.id,
                    "name": c.name,
                    "consequential": c.consequential,
                    "pass": c.passed,
                    "evidence": c.evidence,
                }
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def _git_show(repo: Path, ref: str) -> tuple[int, str]:
    """Return (rc, content) of ``git show <ref>`` in *repo*."""
    proc = _run(["git", "-C", str(repo), "show", ref])
    return proc.returncode, proc.stdout


def _run_rule_on_stdin(rule_script: Path, content: str, filename: str) -> tuple[int, str]:
    """Invoke the installed rule via its --stdin path. The rule lives under the
    repo's scripts/lint/ so its sibling imports (ast_lint, path_utils) resolve
    via sys.path[0] (the script's own directory)."""
    proc = subprocess.run(
        [sys.executable, str(rule_script), "--stdin", f"--filename={filename}"],
        input=content,
        text=True,
        capture_output=True,
    )
    return proc.returncode, proc.stdout


def _parse_violation(line: str) -> tuple[str, str] | None:
    """Parse a violation line ``path:line:col: tag: msg`` into ``(path, tag)``.

    Returns None for lines that are not well-formed violations. The locator field
    (``path:line:col``) must carry exactly two colons, so message text that itself
    contains ``: <name>: `` — e.g. an allow-list hint like ``# noqa: <rule>: ...``
    — cannot be mistaken for the emitted tag. (This masking is exactly what let an
    early version miscount a tag-drifted rule; see the wrong-name fixture.)"""
    parts = line.split(": ", 2)
    if len(parts) < 2:
        return None
    locator = parts[0]
    if locator.count(":") != 2:  # path:line:col — POSIX paths carry no colon here
        return None
    return locator.split(":", 1)[0], parts[1]


def _count_hits(stdout: str, rule_name: str) -> int:
    """Count violation lines whose emitted tag is exactly *rule_name*."""
    return sum(
        1 for line in stdout.splitlines()
        if (pv := _parse_violation(line)) is not None and pv[1] == rule_name
    )


def _hit_files(stdout: str, rule_name: str) -> set[str]:
    """Return the set of file paths whose violation line's tag is *rule_name*."""
    files: set[str] = set()
    for line in stdout.splitlines():
        pv = _parse_violation(line)
        if pv is not None and pv[1] == rule_name:
            files.add(pv[0])
    return files


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_c1_pattern(proposal: Path) -> CheckResult:
    p = proposal / "pattern.md"
    exists = p.exists() and p.read_text(encoding="utf-8").strip() != ""
    ev = f"{p} present, {p.stat().st_size} bytes" if exists else f"{p} missing or empty"
    return CheckResult("C1", "pattern.md exists & non-empty", False, exists, ev)


def check_c2_rule_cli(repo: Path, rule_name: str, module: str, bad_fixture: Path) -> CheckResult:
    """Rule script exists under the repo's scripts/lint/, is stdlib-only, and
    honors the CLI contract: exit 1 on a known-bad input, 0 on a clean input,
    2 on an empty invocation. The known-bad input is the proposal's own bad
    fixture (the author asserts the rule fires there) — this keeps C2 about the
    CLI/exit-code mechanics, not rule semantics (that is C3/C4)."""
    rule_script = repo / "scripts" / "lint" / f"{module}.py"
    if not rule_script.exists():
        return CheckResult("C2", "rule script + CLI contract", False, False,
                           f"rule script not found at {rule_script}")

    # stdlib-only: no third-party imports. The sibling scaffold (ast_lint,
    # path_utils) is repo-local, and the stdlib set is allow-listed.
    third_party = _scan_third_party_imports(rule_script)
    if third_party:
        return CheckResult("C2", "rule script + CLI contract", False, False,
                           f"non-stdlib imports: {sorted(third_party)}")

    # exit 2 on empty invocation
    empty = subprocess.run([sys.executable, str(rule_script)], text=True, capture_output=True)
    # exit 1 on the proposal's bad fixture
    bad_content = bad_fixture.read_text(encoding="utf-8")
    bad_rc, bad_out = _run_rule_on_stdin(rule_script, bad_content, f"{module}_bad.py")
    # exit 0 on a trivially clean input
    clean_rc, _ = _run_rule_on_stdin(rule_script, CLEAN_INPUT, "clean.py")

    ok = empty.returncode == 2 and bad_rc == 1 and clean_rc == 0
    # Output-format spot check on the bad run. Uses the same tag-field parse as
    # C4/C8 hit-counting, so message text echoing the wired name (e.g. an
    # allow-list hint) cannot mask a drifted emitted tag.
    fmt_ok = any(
        (pv := _parse_violation(line)) is not None and pv[1] == rule_name
        for line in bad_out.splitlines()
    )
    ok = ok and fmt_ok
    ev = (
        f"empty_rc={empty.returncode} (exp 2), bad_rc={bad_rc} (exp 1), "
        f"clean_rc={clean_rc} (exp 0), output_format_ok={fmt_ok}, stdlib_only=True"
    )
    return CheckResult("C2", "rule script + CLI contract", False, ok, ev)


def check_c3_verify_rule(
    project_root: Path,
    repo: Path,
    module: str,
) -> CheckResult:
    """CONSEQUENTIAL. Run the REAL verify_rule.py (skill-owned) against the
    installed rule + fixture pair. verify_rule asserts BAD_RC=1 and GOOD_RC=0
    — the skill's own differential validity gate."""
    verify = project_root / VERIFY_RULE_REL
    if not verify.exists():
        return CheckResult("C3", "fixture pair + verify_rule.py", True, False,
                           f"verify_rule.py not found at {verify}")
    rule_script = repo / "scripts" / "lint" / f"{module}.py"
    bad = repo / "tests" / "lint" / f"{module}_bad.py"
    good = repo / "tests" / "lint" / f"{module}_good.py"
    for label, p in (("rule", rule_script), ("bad", bad), ("good", good)):
        if not p.exists():
            return CheckResult("C3", "fixture pair + verify_rule.py", True, False,
                               f"{label} fixture missing at {p}")
    proc = _run([sys.executable, str(verify),
                 "--rule", str(rule_script),
                 "--bad", str(bad),
                 "--good", str(good)])
    passed = proc.returncode == 0
    # Pull the one-line BAD/GOOD summary from verify_rule's stdout for evidence.
    summary = " | ".join(
        ln.strip() for ln in proc.stdout.splitlines()
        if ln.strip().startswith(("bad", "good", "PASS", "FAIL"))
    )
    ev = f"verify_rule rc={proc.returncode}; {summary or proc.stdout.strip()[:200]}"
    return CheckResult("C3", "fixture pair + verify_rule.py", True, passed, ev)


def check_c4_historical_fire(
    repo: Path,
    rule_name: str,
    module: str,
    anchor: str,
    fixed_files: list[str],
) -> CheckResult:
    """CONSEQUENTIAL. For each fixed file: the rule FIRES (hits>0) on the
    pre-anchor blob (``git show <anchor>^:<file>``) and is CLEAN (hits==0) on
    the HEAD blob. A rule that does not catch the very bug it was built for is
    theater even if every file exists."""
    rule_script = repo / "scripts" / "lint" / f"{module}.py"
    if not rule_script.exists():
        return CheckResult("C4", "historical-fire", True, False,
                           f"rule script not found at {rule_script}")
    if not fixed_files:
        return CheckResult("C4", "historical-fire", True, False,
                           "no fixed files supplied — cannot prove historical fire")

    details: list[str] = []
    all_ok = True
    for rel in fixed_files:
        pre_rc, pre_src = _git_show(repo, f"{anchor}^:{rel}")
        head_rc, head_src = _git_show(repo, f"HEAD:{rel}")
        if pre_rc != 0 or head_rc != 0:
            all_ok = False
            details.append(f"{rel}: git show failed (pre_rc={pre_rc}, head_rc={head_rc})")
            continue
        _, pre_out = _run_rule_on_stdin(rule_script, pre_src, rel)
        _, head_out = _run_rule_on_stdin(rule_script, head_src, rel)
        pre_hits = _count_hits(pre_out, rule_name)
        head_hits = _count_hits(head_out, rule_name)
        ok = pre_hits > 0 and head_hits == 0
        all_ok = all_ok and ok
        verdict = "OK" if ok else "FAIL"
        details.append(
            f"{rel}: pre-anchor hits={pre_hits} (need >0), "
            f"HEAD hits={head_hits} (need 0) → {verdict}"
        )
    return CheckResult("C4", "historical-fire", True, all_ok, "; ".join(details))


def check_c5_wiring(repo: Path, rule_name: str) -> CheckResult:
    """Pre-commit hook entry + CI step + a RuleSpec in run.py all reference the
    rule (grep)."""
    run_py = repo / "scripts" / "lint" / "run.py"
    precommit = repo / ".pre-commit-config.yaml"
    ci = repo / ".github" / "workflows" / "ci.yml"

    run_txt = run_py.read_text(encoding="utf-8") if run_py.exists() else ""
    pc_txt = precommit.read_text(encoding="utf-8") if precommit.exists() else ""
    ci_txt = ci.read_text(encoding="utf-8") if ci.exists() else ""

    run_ok = f'name="{rule_name}"' in run_txt or f"name='{rule_name}'" in run_txt
    pc_ok = f"id: {rule_name}" in pc_txt
    ci_ok = rule_name in ci_txt

    ok = run_ok and pc_ok and ci_ok
    ev = (
        f"run.py RuleSpec={'yes' if run_ok else 'NO'}, "
        f"pre-commit hook={'yes' if pc_ok else 'NO'}, "
        f"CI step={'yes' if ci_ok else 'NO'}"
    )
    return CheckResult("C5", "pre-commit + CI + run.py wiring", False, ok, ev)


def check_c6_claude_md(repo: Path, rule_name: str) -> CheckResult:
    claude = repo / "CLAUDE.md"
    txt = claude.read_text(encoding="utf-8") if claude.exists() else ""
    # A canonical-pattern bullet naming the rule, under a Canonical Patterns head.
    has_section = "Canonical Patterns" in txt
    names_rule = rule_name in txt
    in_bullet = any(
        line.lstrip().startswith(("-", "*")) and rule_name in line
        for line in txt.splitlines()
    )
    ok = has_section and names_rule and in_bullet
    ev = (
        f"Canonical Patterns section={'yes' if has_section else 'NO'}, "
        f"rule named in a bullet={'yes' if in_bullet else 'NO'}"
    )
    return CheckResult("C6", "CLAUDE.md canonical-pattern entry", False, ok, ev)


def check_c7_proposal(proposal: Path) -> CheckResult:
    """proposal.md exists with the sections Phase 6 requires: Source cluster,
    Pattern, Artifacts, Verification."""
    p = proposal / "proposal.md"
    if not p.exists():
        return CheckResult("C7", "proposal.md exists with required sections", False, False,
                           f"{p} missing")
    txt = p.read_text(encoding="utf-8")
    required = ["Source cluster", "Pattern", "Artifacts", "Verification"]
    missing = [h for h in required if f"## {h}" not in txt and h not in txt]
    ok = not missing
    ev = "all required sections present" if ok else f"missing sections: {missing}"
    return CheckResult("C7", "proposal.md exists with required sections", False, ok, ev)


def check_c8_incidental_firing(
    repo: Path,
    rule_name: str,
    module: str,
    antipattern_files: list[str] | None,
    include_regex: str,
    exclude_regex: str | None,
) -> CheckResult:
    """CONSEQUENTIAL. Run the rule across its whole enforcement scope (every
    repo file matching the wired include/exclude) and require every violation
    to land in a known anti-pattern file. A rule that also fires on innocent
    code is over-broad; in practice it gets suppressed or deleted and then
    protects nothing, so over-firing fails conformance the same way a rule that
    misses the bug does.

    Scope = the rule's real enforcement scope, so this measures over-firing
    exactly where the guard actually runs. The fixtures under tests/ and the
    rule script under scripts/ fall outside the include and are not scanned.

    If no anti-pattern ground truth is supplied, C8 cannot tell a stray hit from
    a legitimate one, so it is skipped (pass with a note) rather than failing a
    possibly-fine rule."""
    if not antipattern_files:
        return CheckResult("C8", "bounded incidental firing", True, True,
                           "skipped — no anti-pattern ground truth supplied")
    rule_script = repo / "scripts" / "lint" / f"{module}.py"
    if not rule_script.exists():
        return CheckResult("C8", "bounded incidental firing", True, False,
                           f"rule script not found at {rule_script}")

    include = re.compile(include_regex)
    exclude = re.compile(exclude_regex) if exclude_regex else None
    allowed = set(antipattern_files)

    # Collect in-scope files (repo-relative POSIX), pruning VCS/noise dirs.
    in_scope: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in {"__pycache__", ".venv", "node_modules"}
        ]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            rel = Path(dirpath, fn).relative_to(repo).as_posix()
            if include.search(rel) and not (exclude and exclude.search(rel)):
                in_scope.append(rel)

    if not in_scope:
        return CheckResult("C8", "bounded incidental firing", True, True,
                           "no files in the rule's enforcement scope — vacuously bounded")

    proc = subprocess.run(
        [sys.executable, str(rule_script), *sorted(in_scope)],
        cwd=repo, text=True, capture_output=True,
    )
    hit_files = _hit_files(proc.stdout, rule_name)
    stray = sorted(hit_files - allowed)
    ok = not stray
    ev = (
        f"scanned {len(in_scope)} in-scope file(s); "
        f"hit files={sorted(hit_files)}; allowed (anti-pattern)={sorted(allowed)}; "
        + ("no stray hits" if ok else f"STRAY (over-broad) hits in: {stray}")
    )
    return CheckResult("C8", "bounded incidental firing", True, ok, ev)


# ---------------------------------------------------------------------------
# stdlib-only import scan
# ---------------------------------------------------------------------------

# Repo-local sibling modules that are legitimately importable (they ship with
# the seed's scripts/lint/ scaffold, mirroring the real repo).
_LOCAL_SIBLINGS = {"ast_lint", "path_utils"}


def _scan_third_party_imports(rule_script: Path) -> set[str]:
    """Return top-level imported module names that are neither stdlib nor a
    repo-local sibling. Uses AST so it is robust to comment/string noise."""
    import ast as _ast

    src = rule_script.read_text(encoding="utf-8")
    tree = _ast.parse(src)
    imported: set[str] = set()
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, _ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import — repo-local by definition
            if node.module:
                imported.add(node.module.split(".")[0])

    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    third_party = {
        name
        for name in imported
        if name not in stdlib
        and name not in _LOCAL_SIBLINGS
        and name != "__future__"
    }
    return third_party


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def score(
    proposal: Path,
    repo: Path,
    anchor: str,
    rule_name: str,
    fixed_files: list[str],
    project_root: Path,
    module: str | None = None,
    antipattern_files: list[str] | None = None,
) -> Scorecard:
    # The proposal manifest carries the module name and the rule's enforcement
    # scope (the same include/exclude that get wired into run.py). C8 reuses that
    # scope so it measures over-firing exactly where the guard actually runs.
    manifest: dict = {}
    manifest_path = proposal / "proposal_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if module is None:
        module = manifest.get("module", rule_name.replace("-", "_"))
    include_regex = manifest.get("include_regex", r"^app/.*\.py$")
    exclude_regex = manifest.get("exclude_regex")

    bad_fixture_in_proposal = proposal / "tests" / "lint" / f"{module}_bad.py"

    card = Scorecard(
        proposal=str(proposal),
        repo=str(repo),
        rule_name=rule_name,
        anchor=anchor,
        fixed_files=list(fixed_files),
    )
    card.add(check_c1_pattern(proposal))
    card.add(check_c2_rule_cli(repo, rule_name, module, bad_fixture_in_proposal))
    card.add(check_c3_verify_rule(project_root, repo, module))
    card.add(check_c4_historical_fire(repo, rule_name, module, anchor, fixed_files))
    card.add(check_c5_wiring(repo, rule_name))
    card.add(check_c6_claude_md(repo, rule_name))
    card.add(check_c7_proposal(proposal))
    card.add(check_c8_incidental_firing(
        repo, rule_name, module, antipattern_files, include_regex, exclude_regex))
    return card


def _print_summary(card: Scorecard) -> None:
    print(f"\nConformance scorecard — {card.rule_name}")
    print(f"  proposal : {card.proposal}")
    print(f"  repo     : {card.repo}")
    print(f"  anchor   : {card.anchor}")
    print("  " + "-" * 74)
    for c in card.checks:
        mark = "PASS" if c.passed else "FAIL"
        tag = "[CONSEQUENTIAL]" if c.consequential else "[cosmetic]     "
        print(f"  {c.id}  {mark}  {tag}  {c.name}")
        print(f"        └─ {c.evidence}")
    print("  " + "-" * 74)
    print(f"  VERDICT: {card.verdict.upper()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", required=True, type=Path, help="Proposal directory")
    parser.add_argument("--repo", required=True, type=Path,
                        help="Seeded target repo (AFTER proposal install)")
    parser.add_argument("--anchor", required=True, help="Anchor commit SHA")
    parser.add_argument("--rule-name", required=True, help="Rule name, e.g. no-bare-int-request")
    parser.add_argument("--fixed-files", required=True, nargs="+",
                        help="Repo-relative paths the anchor commit fixed")
    parser.add_argument("--antipattern-files", nargs="*", default=None,
                        help="Repo-relative files that legitimately contain the anti-pattern "
                             "(C8 allow-list of hit sites). If omitted, C8 is skipped.")
    parser.add_argument("--module", default=None,
                        help="Override module name (default: from manifest or rule-name)")
    parser.add_argument("--project-root", type=Path,
                        default=Path(__file__).resolve().parents[2],
                        help="Project root that holds .claude/skills/prevent-regression "
                             "(default: two levels above scripts/skill_comply/)")
    parser.add_argument("--out", type=Path, default=None,
                        help="Where to write conformance.json (default: <proposal>/conformance.json)")
    args = parser.parse_args()

    if not args.proposal.is_dir():
        print(f"error: proposal dir not found: {args.proposal}", file=sys.stderr)
        return 2
    if not args.repo.is_dir():
        print(f"error: repo dir not found: {args.repo}", file=sys.stderr)
        return 2

    card = score(
        proposal=args.proposal,
        repo=args.repo,
        anchor=args.anchor,
        rule_name=args.rule_name,
        fixed_files=args.fixed_files,
        project_root=args.project_root,
        module=args.module,
        antipattern_files=args.antipattern_files,
    )

    out = args.out or (args.proposal / "conformance.json")
    out.write_text(json.dumps(card.to_dict(), indent=2) + "\n", encoding="utf-8")
    _print_summary(card)
    print(f"\nwrote {out}")

    return 0 if card.verdict in ("pass", "pass-with-notes") else 1


if __name__ == "__main__":
    raise SystemExit(main())
