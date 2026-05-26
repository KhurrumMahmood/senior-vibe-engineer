"""Guard: the EXPLAIN job is the read-only proposal stage.

Executable form of precedents.yml `explain-job-is-read-only-proposal.v1`.
In the maintenance loop (map -> suspect -> explain -> refactor -> guard),
EXPLAIN is deliberately read-only: a code-transform PROPOSER turns a SUSPECT
finding into an implementation-ready brief and changes no code; the REFACTOR
counterpart executes that brief. So proposer-NAMED skills (extract-*,
propose-*, introduce-fk, unify-shadows) correctly carry `job: explain`.

Why this guard exists: a 2026-05-25 self-review read these labels as
mislabeled and a fix-now authorization nearly relabeled them off `explain`,
which would have silently wrecked the propose/execute split while passing
every artifact and routing check. This test goes red on exactly that relabel,
so it cannot land without first removing this guard in a separate commit.

The set is a curated allowlist, not a name-prefix rule, because
`extract-existing-ideas` is proposer-PREFIXED yet is `job: meta` (it extracts
ideas, not code structure) -- pinned below so the allowlist is not "completed"
by mislabeling it. Add a new code-transform proposer here when one ships.

Doctrine source: .claude/docs/skill-catalog.md ("EXPLAIN proposes the explicit
form; REFACTOR executes it") and the README EXPLAIN bullet.
"""
from __future__ import annotations

from pathlib import Path

from _lib.yaml_frontmatter import read

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

# Code-transform proposers: SUSPECT finding -> read-only, implementation-ready
# brief. NAMED like actions, but they PROPOSE; they do not execute.
EXPLAIN_PROPOSERS = (
    "extract-cotton-primitive",
    "extract-enum",
    "extract-state-type",
    "extract-workflow-registry",
    "introduce-fk",
    "propose-boundary",
    "propose-folder-reorganization",
    "unify-shadows",
)

# The REFACTOR side that EXECUTES an explain brief -- the other half of the
# propose/execute split this precedent protects.
REFACTOR_EXECUTORS = ("refactor-subsystem",)

# Proposer-PREFIXED but deliberately NOT explain: extracts ideas (meta), not
# code structure. Pinned so nobody "completes" the allowlist by mislabeling it.
NON_EXPLAIN_CARVEOUTS = {"extract-existing-ideas": "meta"}


def _job(skill_name: str) -> str | None:
    skill_md = SKILLS_DIR / skill_name / "SKILL.md"
    assert skill_md.exists(), f"{skill_name}: SKILL.md not found at {skill_md}"
    return read(skill_md).metadata.get("job")


def test_proposer_skills_are_explain():
    """Every documented code-transform proposer carries job: explain."""
    jobs = {name: _job(name) for name in EXPLAIN_PROPOSERS}
    mislabeled = {name: job for name, job in jobs.items() if job != "explain"}
    assert not mislabeled, (
        "code-transform proposers must be job=explain (read-only brief; REFACTOR "
        "executes) per precedents.yml explain-job-is-read-only-proposal.v1 -- "
        "relabeling them would wreck the propose/execute split; "
        f"mislabeled: {mislabeled}"
    )


def test_refactor_counterpart_is_refactor():
    """The executor side of the propose/execute split carries job: refactor."""
    jobs = {name: _job(name) for name in REFACTOR_EXECUTORS}
    mislabeled = {name: job for name, job in jobs.items() if job != "refactor"}
    assert not mislabeled, f"refactor executors must be job=refactor; mislabeled: {mislabeled}"


def test_idea_extractor_is_carved_out_of_explain():
    """extract-existing-ideas is proposer-PREFIXED but job: meta -- explicit carve-out."""
    for name, expected in NON_EXPLAIN_CARVEOUTS.items():
        assert _job(name) == expected, (
            f"{name} is proposer-prefixed but extracts ideas, not code structure; "
            f"expected job={expected!r}. Do not relabel it 'explain' to match its prefix siblings."
        )
