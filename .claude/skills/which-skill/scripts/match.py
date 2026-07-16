#!/usr/bin/env python3
"""Skill matcher — primitive recommender for /which-skill.

Reads every SKILL.md frontmatter via the shared scripts/_lib/yaml_frontmatter
parser and ranks skills against a free-text task description. Emits a top-N
JSON or markdown report; in JSON mode the winning candidate also carries a
`task_packet` block (PR B-lite's optional fields: lanes, stage, entrypoint,
consumes, produces, evidence_required, risk_triggers, max_overhead) so an
orchestrator can know not just which skill to invoke but how.

Two purposes:
1. Defend against agent misapplication (the wrong skill is the most
   common failure mode — `/refactor-subsystem` for a typo, etc.).
2. Surface metadata mismatches fast — if /which-skill consistently
   picks wrong, the `not_for` / `best_for` fields are wrong, and the
   PR2 audit knows where to focus.

Exit codes: 0 = ranked successfully, 1 = no skill applies (suggest
proceeding directly), 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent.parent.parent.parent.parent
DEFAULT_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

_lib_parent = str(REPO_ROOT / "scripts")
if _lib_parent not in sys.path:
    sys.path.insert(0, _lib_parent)
from _lib.yaml_frontmatter import FrontmatterError, parse  # noqa: E402
from _lib.capability_registry import load_registry  # noqa: E402
from _lib.skill_activation import (  # noqa: E402
    ActivationError,
    decide_catalog_activation,
)

CAPABILITY_REGISTRY = load_registry()

# Optional task-packet fields surfaced on the winning candidate (PR B-lite).
TASK_PACKET_FIELDS = (
    "lanes", "stage", "entrypoint",
    "consumes", "produces", "evidence_required",
    "risk_triggers", "max_overhead",
)

# Words that don't disambiguate. Loose stopword list — biased toward
# recall over precision so single-word matches stay meaningful.
STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
    "has", "have", "i", "if", "in", "into", "is", "it", "of", "on", "or",
    "that", "the", "this", "to", "was", "we", "will", "with", "you", "use",
    "using", "make", "set", "get", "want", "need", "should", "must",
    "can", "could", "would", "may", "might", "just", "really",
})

# Verbs that signal the job the user is asking for.
JOB_HINTS: dict[str, set[str]] = {
    "plan": {"plan", "planning", "design", "scope"},
    "map": {"map", "inventory", "atlas", "topology", "list"},
    "suspect": {"audit", "find", "scan", "detect", "search", "discover", "look"},
    "explain": {"explain", "understand", "describe", "annotate", "summarize"},
    "refactor": {"refactor", "rewrite", "extract", "split", "clean", "merge", "unify", "fix"},
    "guard": {"guard", "lint", "rule", "prevent", "regression", "enforce"},
    "decide": {"decide", "decision", "adr", "record", "choose"},
    "triage": {"triage", "prioritize", "queue", "debt", "accumulating"},
    "teach": {"teach", "explain why", "tutorial", "walkthrough", "briefing"},
    "construct": {"construct", "author", "write", "create", "draft", "pattern"},
    "diagnose": {"diagnose", "debug", "reproduce", "root", "cause", "regression", "flake"},
    "meta": {"audit", "drift", "stale", "healthy", "registry", "hygiene"},
}

# Words that strongly imply Quick tier (no planning skill applies).
QUICK_HINTS = frozenset({
    "typo", "rename", "one-line", "oneline", "small", "trivial", "simple",
    "quick", "tiny", "minor", "single",
})

TIER_HINTS: dict[str, set[str]] = {
    "feature": {"feature", "endpoint", "ttl", "override", "expose", "add"},
    "system": {"subsystem", "cross-cutting", "cross", "multi-workflow",
               "redesign", "rework", "architecture"},
    "maintenance": {"dead", "duplicate", "duplication", "dormant", "fat",
                    "omnibus", "stringly", "tuple", "smell", "bug",
                    "broken", "failing", "debug", "diagnose", "reproduce",
                    "regression", "flake"},
    "new-project": {"greenfield", "scaffold", "init", "bootstrap", "new project"},
    "cross-cutting": {"adr", "decision", "convention"},
}

OBLIGATION_CHANGE_HINTS = frozenset({"changed", "touched", "diff", "staged"})
OBLIGATION_VERIFY_HINTS = frozenset({
    "test", "tests", "testing", "verify", "verification", "smoke",
    "obligation", "obligations", "tier", "tiers",
})
SKILL_DEVELOPMENT_HINTS = frozenset({"skill", "skills", "frontmatter", "dogfood"})
SKILL_DEVELOPMENT_ACTIONS = frozenset({
    "create", "write", "plan", "new", "revise", "update", "validation",
    "dogfood", "author", "build",
})

WORD_RE = re.compile(r"[a-z][a-z0-9_-]+")


def tokenize(text: str) -> set[str]:
    return {
        w for w in WORD_RE.findall(text.lower())
        if w not in STOPWORDS and len(w) > 1
    }


def infer_tier_signal(task_tokens: set[str]) -> tuple[str | None, list[str]]:
    """Return (inferred_tier, matched_hints).

    Returns ('quick', [...]) if the task looks trivial, in which case
    the matcher will suppress all skill recommendations.
    """
    if task_tokens & QUICK_HINTS:
        return "quick", sorted(task_tokens & QUICK_HINTS)
    best_tier: str | None = None
    best_hits: list[str] = []
    for tier, hints in TIER_HINTS.items():
        hits = sorted(task_tokens & hints)
        if len(hits) > len(best_hits):
            best_tier = tier
            best_hits = hits
    return best_tier, best_hits


def infer_job_signal(task_tokens: set[str]) -> tuple[str | None, list[str]]:
    best_job: str | None = None
    best_hits: list[str] = []
    for job, hints in JOB_HINTS.items():
        hits = sorted(task_tokens & hints)
        if len(hits) > len(best_hits):
            best_job = job
            best_hits = hits
    return best_job, best_hits


def is_test_obligation_signal(task_tokens: set[str]) -> bool:
    """True when wording is about changed files and expected verification.

    This narrow override keeps "map touched files to expected tests" from
    routing to inventory-map skills just because the user used "map" as a
    verb rather than asking for a product workflow map.
    """
    return bool(task_tokens & OBLIGATION_CHANGE_HINTS) and bool(task_tokens & OBLIGATION_VERIFY_HINTS)


def is_skill_development_signal(task_tokens: set[str]) -> bool:
    """True when wording is about designing/writing an agent skill.

    Without this override, generic words like "new" and "ui" can route
    "create a new skill" prompts to product-feature or obligation scans.
    """
    return bool(task_tokens & SKILL_DEVELOPMENT_HINTS) and bool(task_tokens & SKILL_DEVELOPMENT_ACTIONS)


def score_skill(
    skill: dict,
    task_tokens: set[str],
    inferred_tier: str | None,
    inferred_job: str | None,
) -> tuple[int, list[str]]:
    """Return (score, rationale_lines)."""
    rationale: list[str] = []
    score = 0

    best_for_tokens = tokenize(skill.get("best_for", ""))
    not_for_tokens = tokenize(skill.get("not_for", ""))
    desc_tokens = tokenize(skill.get("description", ""))
    name_tokens = tokenize(skill.get("name", ""))

    # 1. best_for overlap is the strongest positive signal.
    bf_hits = task_tokens & best_for_tokens
    if bf_hits:
        score += 5 * len(bf_hits)
        rationale.append(f"best_for hit: {', '.join(sorted(bf_hits))}")

    # 2. not_for overlap is the strongest negative signal.
    nf_hits = task_tokens & not_for_tokens
    if nf_hits:
        score -= 10 * len(nf_hits)
        rationale.append(f"not_for hit (penalty): {', '.join(sorted(nf_hits))}")

    # 3. description/name overlap — secondary positive signal.
    other_hits = task_tokens & (desc_tokens | name_tokens)
    other_hits -= bf_hits
    if other_hits:
        score += 2 * len(other_hits)
        rationale.append(f"description/name hit: {', '.join(sorted(other_hits))}")

    # 4. Tier match — boost if skill.tier == inferred tier.
    skill_tier = skill.get("tier")
    if skill_tier and inferred_tier and skill_tier == inferred_tier:
        score += 8
        rationale.append(f"tier match: {skill_tier}")
    elif skill_tier == "cross-cutting" and inferred_tier:
        # cross-cutting is tier-agnostic (decide, which-skill); small boost.
        score += 3

    # 5. Job match — boost if skill.job matches inferred job.
    skill_job = skill.get("job")
    if skill_job and inferred_job and skill_job == inferred_job:
        score += 6
        rationale.append(f"job match: {skill_job}")

    return score, rationale


def load_skills(skills_dir: Path) -> list[dict]:
    out = []
    for sm in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            fm = parse(sm.read_text(encoding="utf-8"), path=sm).metadata
        except (OSError, UnicodeDecodeError, FrontmatterError) as exc:
            print(f"warning: skipping {sm.name}: {exc}", file=sys.stderr)
            continue
        if not fm:
            continue
        language = fm.get("language")
        framework = fm.get("framework")
        if language is not None and language not in CAPABILITY_REGISTRY.identifiers("languages"):
            print(f"warning: skipping {sm.name}: unregistered language {language!r}", file=sys.stderr)
            continue
        if framework is not None and framework not in CAPABILITY_REGISTRY.identifiers("frameworks"):
            print(f"warning: skipping {sm.name}: unregistered framework {framework!r}", file=sys.stderr)
            continue
        try:
            fm["_path"] = str(sm.relative_to(REPO_ROOT))
        except ValueError:
            fm["_path"] = str(sm)
        out.append(fm)
    return out


def _build_task_packet(skill: dict) -> dict:
    """Pull the optional task-packet fields off a skill, omitting any
    that aren't declared. Returns {} if the skill carries none."""
    return {f: skill[f] for f in TASK_PACKET_FIELDS if f in skill}


def cmd_match(args, skills_dir: Path) -> int:
    task = args.task.strip()
    if not task:
        print("error: empty task description", file=sys.stderr)
        return 2

    task_tokens = tokenize(task)
    inferred_tier, tier_hits = infer_tier_signal(task_tokens)
    inferred_job, job_hits = infer_job_signal(task_tokens)
    if is_test_obligation_signal(task_tokens):
        inferred_job = "suspect"
        job_hits = sorted(set(job_hits) | {"verification-obligation"})
    if is_skill_development_signal(task_tokens):
        inferred_tier = "cross-cutting"
        inferred_job = "plan"
        tier_hits = sorted(set(tier_hits) | {"skill-development"})
        job_hits = sorted(set(job_hits) | {"skill-development"})

    skills = load_skills(skills_dir)
    if not skills:
        print(f"error: no skills found under {skills_dir}", file=sys.stderr)
        return 2

    # Quick tier short-circuit — recommend no planning skill.
    if inferred_tier == "quick":
        out = {
            "task": task,
            "inferred_tier": "quick",
            "tier_hints": tier_hits,
            "recommendation": "proceed_directly",
            "rationale": (
                "Task description matches Quick-tier signals "
                f"({', '.join(tier_hits)}). No planning skill applies. "
                "Optional: /decide if a real choice is being made along the way."
            ),
            "candidates": [],
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"Task: {task}")
            print(f"Inferred tier: quick (hints: {', '.join(tier_hits)})")
            print()
            print("Recommendation: proceed directly — no planning skill applies.")
            print(
                "Optional: /decide if a real choice is being made along the way."
            )
        return 1

    ranked = []
    for sk in skills:
        score, rationale = score_skill(sk, task_tokens, inferred_tier, inferred_job)
        ranked.append((score, sk, rationale))
    ranked.sort(key=lambda t: (-t[0], t[1].get("name", "")))

    threshold = args.threshold
    project_root = args.project_root.resolve()

    try:
        activation = decide_catalog_activation(
            skills,
            project_root=project_root,
            required_capabilities=args.require_capability,
            required_layers=args.require_layer,
            required_bindings=args.require_binding,
        )
    except ActivationError as exc:
        print(f"error: cannot resolve skill activation: {exc}", file=sys.stderr)
        return 2

    # Activation gate — profile incompatibility or a host opt-out cannot be
    # overruled by textual ranking. Material exclusions (candidates that would
    # otherwise clear the score threshold) stay visible with every reason.
    active_ranked = []
    excluded_inactive = []
    for score, sk, rationale in ranked:
        name = sk.get("name", "")
        decision = activation.get(name)
        if decision is not None and not decision.active:
            if score >= threshold:
                display_reason = "; ".join(decision.exclusion_reasons)
                manual_prefix = "host activation manifest opt-out: "
                if len(decision.exclusion_reasons) == 1 and display_reason.startswith(manual_prefix):
                    display_reason = display_reason.removeprefix(manual_prefix)
                excluded_inactive.append({
                    "name": name,
                    "score": score,
                    "reason": display_reason,
                    "reasons": list(decision.exclusion_reasons),
                    "activation": decision.as_dict(),
                })
            continue
        active_ranked.append((score, sk, rationale, decision))

    top = active_ranked[: args.top]
    above = [r for r in top if r[0] >= threshold]

    out = {
        "task": task,
        "capability_registry_version": CAPABILITY_REGISTRY.schema_version,
        "capability_contract_version": CAPABILITY_REGISTRY.contract_version,
        "inferred_tier": inferred_tier,
        "inferred_job": inferred_job,
        "tier_hints": tier_hits,
        "job_hints": job_hits,
        "excluded_inactive": excluded_inactive,
        "candidates": [
            {
                "name": sk.get("name", "?"),
                "score": score,
                "tier": sk.get("tier", ""),
                "job": sk.get("job", ""),
                "language": sk.get("language", ""),
                "framework": sk.get("framework", ""),
                "layer": sk.get("layer", ""),
                "binding": sk.get("binding", ""),
                "rationale": rationale,
                "path": sk.get("_path", ""),
                "task_packet": _build_task_packet(sk),
                "activation": decision.as_dict() if decision is not None else None,
            }
            for score, sk, rationale, decision in top
        ],
    }
    if not above:
        out["recommendation"] = "proceed_directly"
        out["rationale"] = (
            f"No skill scored above the threshold ({threshold}). "
            "Either the task is genuinely Quick tier, or no current skill "
            "matches. Proceed directly; consider /decide if a meaningful "
            "choice is being made."
        )
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"Task: {task}")
            print(
                f"Inferred tier: {inferred_tier} | job: {inferred_job}"
            )
            print()
            print(out["rationale"])
            print()
            print("Top candidates anyway (none above threshold):")
            for score, sk, _rationale, _decision in top:
                print(f"  {sk.get('name', '?'):<25} score={score}")
            if excluded_inactive:
                print()
                print("Excluded (inactive for this repo):")
                for item in excluded_inactive:
                    reason = f" — {item['reason']}" if item["reason"] else ""
                    print(f"  /{item['name']:<25} score={item['score']}{reason}")
        return 1

    winner = above[0][1]
    out["recommendation"] = winner.get("name", "")
    out["task_packet"] = _build_task_packet(winner)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Task: {task}")
        print(
            f"Inferred tier: {inferred_tier or '(unknown)'} | "
            f"job: {inferred_job or '(unknown)'}"
        )
        print()
        print("Top candidates:")
        for score, sk, rationale, decision in above:
            print(
                f"  /{sk.get('name', '?')} (tier={sk.get('tier', '?')}, "
                f"job={sk.get('job', '?')}, score={score})"
            )
            for r in rationale:
                print(f"    - {r}")
            if decision is not None:
                for reason in decision.reasons:
                    print(f"    - activation: {reason}")
        if out["task_packet"]:
            print()
            print(f"Task packet for /{out['recommendation']}:")
            for field, value in out["task_packet"].items():
                print(f"    {field}: {value}")
        if len(above) < len(top):
            print()
            print("Below threshold (shown for context):")
            for score, sk, _rationale, _decision in top[len(above):]:
                print(f"  /{sk.get('name', '?'):<25} score={score}")
        if excluded_inactive:
            print()
            print("Excluded (inactive for this repo):")
            for item in excluded_inactive:
                reason = f" — {item['reason']}" if item["reason"] else ""
                print(f"  /{item['name']:<25} score={item['score']}{reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Rank skills against a free-text task description."
    )
    p.add_argument(
        "task",
        help="Free-text description of the task ('add per-site export TTL override').",
    )
    p.add_argument(
        "--skills-dir", type=Path, default=DEFAULT_SKILLS_DIR,
        help="Override the skills directory (default: .claude/skills/)",
    )
    p.add_argument(
        "--project-root", type=Path, default=REPO_ROOT,
        help=(
            "Repo whose .engineering/manifest.json declares skill activation; "
            "inactive skills are excluded from recommendations (default: this repo)."
        ),
    )
    p.add_argument("--top", type=int, default=3, help="How many candidates to show")
    p.add_argument(
        "--threshold", type=int, default=5,
        help="Minimum score to count as a real recommendation (default: 5)",
    )
    p.add_argument(
        "--require-capability", action="append", default=[],
        help="Require a registry capability claim (repeatable)",
    )
    p.add_argument(
        "--require-layer", action="append", default=[],
        help="Require a logical skill layer (repeatable)",
    )
    p.add_argument(
        "--require-binding", action="append", default=[],
        help="Require an advertised binding (repeatable)",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = p.parse_args(argv)
    return cmd_match(args, args.skills_dir)


if __name__ == "__main__":
    sys.exit(main())
