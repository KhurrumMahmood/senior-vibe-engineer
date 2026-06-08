#!/usr/bin/env python3
"""find-skill-intent-drift — advisory SUSPECT guard for skill intent contracts.

Compares per-skill intent contracts (.claude/contracts/skills/<name>.yaml, schema v2)
against the actual skills (.claude/skills/<name>/), flagging drift in four bands:

  missing    skill has no intent contract              (intent never captured)
  orphaned   contract exists, skill does not            (intent for a deleted skill)
  malformed  contract missing required schema-v2 keys   (intent capture incomplete)
  stale      SKILL.md's *frontmatter intent surface*     (intent may have drifted
             changed since the contract's last commit     without the contract updating)

The stale band is INTENT-AWARE, not a raw timestamp compare. A SKILL.md body can churn
freely (path-reference sweeps like core/ -> app/, prose edits below the frontmatter) without
the contract going stale — those edits are intent-neutral. Staleness is decided by comparing
the SKILL.md's YAML frontmatter (the intent surface: description / best_for / not_for / job /
tier / escalate_to / ...) as of the contract's last commit against the current frontmatter,
after (a) dropping operational keys that are not intent (argument-hint, allowed-tools, name,
user-invocable) and (b) collapsing path-like tokens to a placeholder so a pure path rename is
not mistaken for an intent change. If the normalized intent map differs, the contract is stale.

This is the "no easy reversion of intent" guard: it cannot block an edit, but it makes
silent intent erosion VISIBLE. Advisory by default (always exits 0, prints findings);
--strict exits 1 on any finding (for CI). Side effect: regenerates
<contracts-dir>/_index.yaml.

Portable: every location is a flag defaulting to the conventional repo layout, so the
same script runs unchanged against a separate engineering-skills (ES2) checkout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

import yaml

REQUIRED = ["skill", "job", "problem_class", "intent", "solves", "born",
            "dogfood_kind", "provenance_confidence"]
BORN_KEYS = ["commit", "date"]
CONF_AXES = ["textual", "structural", "temporal", "dogfood"]
DOGFOOD_KINDS = {"subsystem-refactor", "self-installed-guard", "fixture-pair", "none-found"}
CONF_LEVELS = {"high", "med", "low"}

# Frontmatter keys that describe the CLI/tool surface or bare identity, not the skill's
# intent. Edits here (e.g. an argument-hint path default core/ -> app/, a tool added to
# allowed-tools) must NOT make the intent contract stale.
OPERATIONAL_KEYS = {"argument-hint", "allowed-tools", "name", "user-invocable"}

# A path-like token: a backtick/whitespace/bracket-delimited run that either contains a
# slash segment (foo/bar, app/views) or is a dotted source/config filename
# (urls.py, project-state.json, settings.yaml). Collapsing these to a single placeholder
# means a mechanical path rename inside an intent field reads as "unchanged" — only the
# surrounding prose decides staleness.
_PATHISH = re.compile(
    r"`?"
    r"(?:[\w.\-]+/[\w./\-]*"
    r"|\.?[\w\-]+\.(?:py|json|ya?ml|md|txt|cfg|toml|ini))"
    r"`?"
)


def git_last_epoch(path: Path) -> int | None:
    """Author/commit time of the last commit touching `path`, or None if untracked."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return int(out) if out else None
    except (subprocess.CalledProcessError, ValueError):
        return None


def git_last_sha(path: Path) -> str | None:
    """SHA of the last commit touching `path`, or None if untracked/uncommitted."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return out or None
    except subprocess.CalledProcessError:
        return None


def git_file_at(sha: str, path: Path) -> str | None:
    """Contents of `path` as of commit `sha`. None if the file did not exist there.

    Existence is probed with `git cat-file -e` (exit 0 == blob present) rather than by
    parsing `git show` stderr, which is brittle across git versions. A clean "absent"
    returns None so the caller treats "no SKILL.md at the contract commit" as a real
    change; any other git failure raises GitError so the caller can fall back
    conservatively instead of silently swallowing it.
    """
    obj = f"{sha}:{path}"
    exists = subprocess.run(
        ["git", "cat-file", "-e", obj], capture_output=True, text=True,
    )
    if exists.returncode != 0:
        return None
    proc = subprocess.run(
        ["git", "show", obj], capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git show {obj} failed")
    return proc.stdout


class GitError(RuntimeError):
    """A git invocation failed for a reason other than a missing path."""


def frontmatter_block(text: str) -> str | None:
    """The YAML between the leading `---` fences, or None if there is no such block."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    body: list[str] = []
    for ln in lines[1:]:
        if ln.strip() == "---":
            return "\n".join(body)
        body.append(ln)
    return None  # no closing fence -> malformed frontmatter


def _normalize(value):
    """Recursively normalize a frontmatter value for intent comparison.

    Path-like tokens collapse to <PATH>; runs of whitespace collapse to one space so a
    reflowed block scalar compares equal to its single-line form.
    """
    if isinstance(value, str):
        return re.sub(r"\s+", " ", _PATHISH.sub("<PATH>", value)).strip()
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    return value


def intent_fingerprint(fm_text: str) -> dict:
    """Normalized map of the intent-bearing frontmatter keys.

    Raises yaml.YAMLError on malformed YAML so the caller can fall back conservatively.
    """
    data = yaml.safe_load(fm_text)
    if not isinstance(data, dict):
        return {}
    return {k: _normalize(v) for k, v in data.items() if k not in OPERATIONAL_KEYS}


def classify_stale(contract_path: Path, skillmd_path: Path) -> tuple[bool, str]:
    """Decide the stale state for one skill. Returns (is_stale, state_label).

    Intent-aware: compares the SKILL.md frontmatter at the contract's last commit against
    the current frontmatter, ignoring operational keys and path-token churn. Body-only
    edits never flag.

    Edge cases:
      * contract uncommitted        -> baseline (not stale; matches the prior behavior)
      * SKILL.md absent at commit    -> stale (the intent surface can't be vouched for)
      * git error / unparseable YAML -> conservative fallback to the legacy timestamp
                                        compare (SKILL.md newer than contract == stale),
                                        labeled so the fallback is visible.
    """
    c_sha = git_last_sha(contract_path)
    if c_sha is None:
        return False, "baseline (contract uncommitted)"

    try:
        old_text = git_file_at(c_sha, skillmd_path)
    except GitError:
        return _timestamp_fallback(contract_path, skillmd_path)

    if old_text is None:
        return True, "STALE (SKILL.md absent at contract commit)"

    try:
        current_text = skillmd_path.read_text(encoding="utf-8")
    except OSError:
        return _timestamp_fallback(contract_path, skillmd_path)

    old_fm = frontmatter_block(old_text)
    cur_fm = frontmatter_block(current_text)
    if old_fm is None or cur_fm is None:
        return _timestamp_fallback(contract_path, skillmd_path)

    try:
        old_fp = intent_fingerprint(old_fm)
        cur_fp = intent_fingerprint(cur_fm)
    except yaml.YAMLError:
        return _timestamp_fallback(contract_path, skillmd_path)

    if old_fp != cur_fp:
        return True, "STALE (frontmatter intent changed since contract)"
    return False, "ok"


def _timestamp_fallback(contract_path: Path, skillmd_path: Path) -> tuple[bool, str]:
    """Legacy git-timestamp compare. Used only when the intent-aware path can't run
    (git error, unreadable/unparseable SKILL.md). Conservative: any SKILL.md commit
    newer than the contract is treated as stale, same as the pre-intent-aware behavior."""
    c_epoch = git_last_epoch(contract_path)
    s_epoch = git_last_epoch(skillmd_path)
    if c_epoch is not None and s_epoch and s_epoch > c_epoch:
        return True, "STALE (timestamp fallback: SKILL.md newer than contract)"
    return False, "ok (timestamp fallback)"


def load_contract(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}, None
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as e:
        return None, f"load error: {e}"


def check_malformed(data: dict) -> list[str]:
    problems: list[str] = []
    for k in REQUIRED:
        if k not in data or data[k] in (None, "", []):
            problems.append(f"missing/empty `{k}`")
    born = data.get("born") or {}
    if isinstance(born, dict):
        for k in BORN_KEYS:
            if not born.get(k):
                problems.append(f"born.{k} empty")
    conf = data.get("provenance_confidence") or {}
    if isinstance(conf, dict):
        for ax in CONF_AXES:
            v = conf.get(ax)
            if v not in CONF_LEVELS:
                problems.append(f"provenance_confidence.{ax}={v!r}")
    dk = data.get("dogfood_kind")
    if dk is not None and dk not in DOGFOOD_KINDS:
        problems.append(f"dogfood_kind={dk!r}")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skills-root", default=".claude/skills")
    ap.add_argument("--contracts-dir", default=".claude/contracts/skills")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any finding (CI)")
    ap.add_argument("--no-index", action="store_true", help="skip _index.yaml regen")
    args = ap.parse_args()

    skills_root = Path(args.skills_root)
    contracts_dir = Path(args.contracts_dir)

    skills = sorted(
        d.name for d in skills_root.iterdir()
        if d.is_dir() and d.name != "_common" and (d / "SKILL.md").exists()
    )
    contracts = {p.stem: p for p in contracts_dir.glob("*.yaml") if not p.name.startswith("_")}

    missing = [s for s in skills if s not in contracts]
    orphaned = sorted(s for s in contracts if s not in skills)

    malformed: dict[str, list[str]] = {}
    stale: list[str] = []
    index_rows: list[dict] = []

    for name in skills:
        cp = contracts.get(name)
        if cp is None:
            continue
        data, err = load_contract(cp)
        if err:
            malformed[name] = [err]
            continue
        probs = check_malformed(data)
        if probs:
            malformed[name] = probs

        is_stale, stale_state = classify_stale(cp, skills_root / name / "SKILL.md")
        if is_stale:
            stale.append(name)

        conf = data.get("provenance_confidence") or {}
        index_rows.append({
            "skill": name,
            "born": (data.get("born") or {}).get("date"),
            "problem_class": data.get("problem_class"),
            "dogfood_kind": data.get("dogfood_kind"),
            "dogfood_confidence": conf.get("dogfood"),
            "duplication_risks": len(data.get("duplication_risk") or []),
            "stale": stale_state,
        })

    print(f"skills={len(skills)} contracts={len(contracts)}")

    def section(title: str, items: list[str]) -> None:
        print(f"\n[{title}] {len(items)}")
        for it in items:
            print(f"  - {it}")

    section("missing-contract", missing)
    section("orphaned-contract", orphaned)
    section("stale", stale)
    print(f"\n[malformed] {len(malformed)}")
    for n, ps in malformed.items():
        print(f"  - {n}: {'; '.join(ps)}")

    if not args.no_index:
        idx = {
            "_note": "AUTO-GENERATED by find-skill-intent-drift/scripts/scan.py — do not hand-edit.",
            "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skill_count": len(index_rows),
            "skills": index_rows,
        }
        out = contracts_dir / "_index.yaml"
        out.write_text(
            yaml.safe_dump(idx, sort_keys=False, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"\nwrote {out} ({len(index_rows)} skills)")

    findings = len(missing) + len(orphaned) + len(stale) + len(malformed)
    print(f"\nTOTAL findings: {findings}")
    if args.strict and findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
