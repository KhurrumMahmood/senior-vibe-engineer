---
name: engineer-init
description: Bootstrap the engineering-skills runtime so the script-backed skills can actually run. Health-checks candidate Python >= 3.11 interpreters, creates the .venv, installs requirements.txt (PyYAML, ruff, pre-commit), wires pre-commit hooks when the repo is git-tracked, and verifies the install by running a script-backed skill end to end. Idempotent — safe to re-run; each stage skips work already done. Run once per clone, or whenever a skill fails with a missing-module / dependency error. Does not edit production code, does not git-init, and does not scaffold a new project (that is /init-project).
argument-hint: "[--check] [--python /absolute/path]"
allowed-tools: Bash, Read
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Getting a fresh clone of the engineering-skills ecosystem (or a host
  project that vendored it) to the point where the script-backed skills
  actually run. The common trigger: Claude Code lists a skill as a slash
  command, you invoke it, and it fails on its first scripts/*.py call
  because the venv / PyYAML isn't installed. Also the fix when ruff or
  pre-commit is missing. Idempotent status check via --check.
not_for: |
  Greenfield project scaffolding — conventions, lint/CI, baseline ADRs
  and subsystem maps (use /init-project when it ships; until then seed
  them by hand). Installing the ecosystem INTO a host project — copying
  or symlinking .claude/, scripts/, ai-docs/ is a manual step this skill
  does not perform. Upgrading or re-pinning dependencies — edit
  requirements.txt directly. Running git init — this skill detects a git
  repo but never creates one; that is the repo owner's call.
escalate_to: |
  /init-project (planned) when the task is greenfield project
  scaffolding rather than runtime setup. /which-skill once the runtime
  is up and the real task needs a skill recommendation.
language: python
framework: any
---

# /engineer-init

You are the **bootstrapper** for the engineering-skills runtime. Most
skills in this ecosystem shell out to helper scripts under `scripts/`
(`decisions.py`, `plans.py`, `ledger.py`, `skill_meta.py`, the lint
runner) that need `PyYAML` from `requirements.txt`. Claude Code
auto-discovers and lists every skill as a slash command *before* that
runtime exists — so a skill can look available and still fail on its
first script call. This skill closes that gap: it installs the runtime
and proves it works.

You do NOT edit production code, author docs, or create a git
repository. The only things you change on disk are the `.venv/`
directory and (when a git repo is present) the project's pre-commit
hook. Everything else is read-only inspection and a verification run.

## How success is judged

- Stage 0 confirms the working directory is an ecosystem root
  (`requirements.txt`, `scripts/`, and `.claude/` are present).
- Stage 1 rejects interpreters that report a version but hang or fail while
  importing required stdlib modules.
- Stage 2 leaves `.venv/bin/python` present, healthy, and tied to this
  directory rather than a stale pre-rename venv.
- Stage 3 resolves `PyYAML`, `ruff`, and `pre-commit` from the venv by
  installing `requirements.txt` with `.venv/bin/python -m pip`.
- Stage 5 prints the real runtime gates: `.venv/bin/ruff --version`,
  `.venv/bin/python scripts/decisions.py list`, and
  `.venv/bin/python scripts/skill_meta.py lint`. The run is done only
  when the `skill_meta.py lint` result line is reported honestly.
Write toward these gates from Stage 0.

## Core beliefs

1. **Idempotent by construction.** Every stage checks state before
   acting. A second run on a healthy clone does nothing but re-verify.
   "Already done" is a success, not a regret.
2. **Verification is the deliverable.** Creating a venv is not the
   goal; a venv that can run `scripts/skill_meta.py lint` to exit 0 is.
   The skill is not done until a script-backed path has executed.
3. **Setup is not scaffolding.** This skill makes the *runtime* work.
   It does not invent project conventions, seed ADRs, or build
   subsystem maps — that is `/init-project`'s job. Keep the lanes
   separate.
4. **Skipped work is reported, never hidden.** If pre-commit hooks were
   skipped because the directory is not a git repo, the summary says so
   and says how to enable them. A silent skip is a future surprise.
5. **The repo owner owns `git init`.** This skill detects a git repo
   and wires hooks into one when it exists. It never creates one — that
   changes the nature of the directory and is a human decision.

## Argument parsing

Two forms — pick exactly one.

### Form A — Full setup (default)

```
/engineer-init
```

Runs the whole pipeline: Python health check -> venv -> deps -> pre-commit
hooks (if git) -> verify. Each stage no-ops if its work is already done.

Use `--python /absolute/path` when the correct interpreter is known and should
be used to create a missing or unhealthy venv.

### Form B — Status check only

```
/engineer-init --check
```

Runs Stage 0-1 and inspects each later stage's post-condition, but
installs nothing. Reports what is present, what is missing, and the
exact command that would fix each gap. Read-only.

## Pipeline

### Stage 0 — Locate the ecosystem root

**Pre:** skill invoked. **Post:** working directory is the ecosystem
root.

The runtime is rooted where `requirements.txt`, `scripts/`, and
`.claude/` sit side by side. Confirm the working directory has all
three:

```bash
test -f requirements.txt && test -d scripts && test -d .claude \
  && echo "root OK" || echo "WRONG DIR"
```

If this prints `WRONG DIR`, stop. The skill must run from the ecosystem
root (or a host project that vendored `.claude/`, `scripts/`,
`requirements.txt`). Tell the user the working directory looks wrong and
name what is missing — do not guess a path.

### Stage 1 — Run the canonical runtime bootstrap

**Pre:** root confirmed. **Post:** a healthy Python >= 3.11 interpreter has
created or validated the project runtime, installed requirements, and wired
hooks when the root is Git-tracked.

```bash
python3 .claude/skills/which-skill/scripts/setup_runtime.py --project-root .
```

For `--check`, append `--check`. When the user supplied `--python`, pass it
through exactly. This helper is bundled with the default `which-skill` router
and is the single setup implementation used by both repository initialization
and installed-library bootstrap.

The ecosystem requires Python >= 3.11. A version string alone is insufficient:
the helper probes `shutil`, `ssl`, and `venv` imports with a timeout, rejects a
hung or incomplete interpreter, checks the active executable plus common 3.11+
executables and installed pyenv runtimes, then emits every rejected candidate
if none is usable. It does not install a system-wide Python. If discovery
fails, install Python 3.11+ and rerun with an exact `--python` path.

### Stage 2 — Create (or rebuild) the venv

**Pre:** Python OK. **Post:** `.venv/bin/python` exists AND the venv
was created for THIS directory.

The Stage 1 helper owns this stage. Existence is not enough: a venv created before the repo directory was
renamed or moved still has an executable `bin/python`, but every
`bin/` shim (`pip`, `pre-commit`, `playwright`, …) hardcodes the
creation-time absolute path in its shebang and silently targets the
old location. Validate `pyvenv.cfg` before trusting an existing venv;
rebuild on mismatch (a venv is fully regenerable — deleting it loses
nothing).

The helper runs the venv interpreter itself, verifies its runtime prefix is the
current `.venv`, and rebuilds a failed or stale environment from the selected
healthy base interpreter.

### Stage 3 — Install dependencies

**Pre:** venv present. **Post:** `PyYAML`, `ruff`, `pre-commit` resolve
from the venv.

The Stage 1 helper runs `.venv/bin/python -m pip install -r requirements.txt`
and `.venv/bin/python -m pip check`, plus an import check for PyYAML when it is
declared. Always use `python -m pip`, never the `.venv/bin/pip` shim.

`pip` is idempotent — satisfied requirements are left alone. If it fails on a
network error, stop and report it; the first install needs PyPI reachable.

Optional dev/CI extras (the status-dashboard browser smoke) live in
`requirements-dev.txt` — install only when working on the renderer or
reproducing the CI browser step locally:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium --only-shell
```

### Stage 4 — Wire pre-commit hooks

**Pre:** deps installed. **Post:** hooks installed, OR skip recorded.

The Stage 1 helper detects Git worktrees with `git rev-parse` (including linked
worktrees whose `.git` is a file) and runs `.venv/bin/python -m pre_commit
install`. The installed on-demand library passes `--no-hooks`, because its
cache checkout is not the host project whose commits should be guarded.

If skipped: the diff-scoped lints still run via `scripts/lint/run.py`
and CI; only the local commit-time hook is absent. To enable it, the
user runs `git init` and re-invokes `/engineer-init`.

### Stage 5 — Verify

**Pre:** deps installed. **Post:** a script-backed path has exited 0.

Run the three checks. Each exercises a different layer of the runtime:

```bash
.venv/bin/ruff --version                     # ruff resolves
.venv/bin/python scripts/decisions.py list    # PyYAML frontmatter path
.venv/bin/python scripts/skill_meta.py lint   # whole-skill frontmatter parse
```

`skill_meta.py lint` exiting 0 is the load-bearing signal — it parses
every skill's frontmatter through the shared PyYAML module. If it exits
non-zero on a *frontmatter* diagnostic the runtime is still fine (that
is a skill-authoring bug, not a setup failure) — say so. If it fails
with an import error, the venv is broken; re-run Stage 2-3.

### Stage 6 — Summarize

Report to the user in <= 8 lines:

- Python version used.
- venv: created / already present.
- deps: installed / already satisfied.
- pre-commit hooks: wired / skipped (and why).
- Verify: the `skill_meta.py lint` result line.
- Next move: `/which-skill "<task>"` if the user has a task in mind, or
  name a concrete first skill. Remind them script-backed skills must run
  with the working directory at a project root (see README "Before the
  skills work").

For `--check`, the summary lists each post-condition as PRESENT or
MISSING with the one fixing command, and writes nothing.

## Non-goals

- **Greenfield scaffolding.** Conventions, lint/CI wiring, baseline ADRs
  and subsystem maps are `/init-project`'s job, not this skill's.
- **Vendoring the ecosystem into a host project.** Copying or symlinking
  `.claude/`, `scripts/`, and `ai-docs/` into a host project root is a
  manual step (see README "Quick start"). This skill assumes that has
  already happened.
- **Creating a git repository.** The skill detects one and wires hooks
  into it; it never runs `git init`.
- **Dependency management.** Upgrading, re-pinning, or adding deps means
  editing `requirements.txt` by hand. This skill only installs what is
  already pinned there.
- **Editing production code or docs.**

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 0 prints `WRONG DIR` | Working directory is not an ecosystem / host-project root. Name the missing marker (`requirements.txt`, `scripts/`, `.claude/`); do not guess a path. |
| No candidate passes the Python health probe | Install Python >= 3.11, then rerun with `--python /absolute/path`; do not lower `pyproject.toml`. |
| `pip install` fails on a network error | Stop and report. First install needs PyPI; a re-run on a healthy network is safe (idempotent). |
| `pip install` fails on a build error for one package | Report the failing package and its error; the venv is partially populated — Stage 3 is safe to re-run after the cause is fixed. |
| `.venv` exists but `.venv/bin/python` is missing or broken | The venv is corrupt. Remove `.venv/` and re-run; Stage 2 rebuilds it. |
| Not a git repo (Stage 4) | Expected for an unversioned copy. Hooks are skipped, not failed. `git init` + re-run enables them. |
| `skill_meta.py lint` exits 1 on a frontmatter diagnostic | Runtime is fine — this is a skill-authoring issue. Report the diagnostic; recommend fixing the offending SKILL.md, not re-running setup. |
| `skill_meta.py lint` fails with `ModuleNotFoundError` | The venv did not get the deps. Re-run Stage 3; if it still fails, rebuild the venv (Stage 2). |

## Repository layout

```
.claude/skills/engineer-init/
└── SKILL.md          # this file — the whole skill, prompt-only
```

The executable helper lives under
`.claude/skills/which-skill/scripts/setup_runtime.py` so it ships with the
default router set. It is stdlib-only before it creates the venv, and both this
skill and `bootstrap_library.py` call it instead of maintaining separate setup
recipes.

## Related

- `README.md` "Before the skills work — two gotchas" — the human-facing
  statement of the blockers this skill automates.
- `.claude/CLAUDE.md` "Python Environment" — the manual equivalent of
  Stages 1-4.
- `/which-skill` — the next skill to reach for once the runtime is up.
- `/init-project` (planned) — greenfield project scaffolding; the
  escalation target when the task is not runtime setup.
