---
name: move-path
description: Deterministically plan, dry-run, apply, and verify batched file or directory moves while updating identity-resolved references such as Markdown links and exact path tokens. Use when paths need to be renamed or moved safely across a repo with relative links, root-relative links, Windows-style path spellings, case-only renames, Git-tracked files, dry-run review, and ambiguous-reference reporting. Keeps the core deterministic; AI review is for judging the move map and uncertain residues, not performing rewrites.
argument-hint: "--plan moves.yml --dry-run|--apply|--check"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
user-invocable: true
tier: maintenance
job: refactor
best_for: |
  Everyday but high-blast path moves: moving or renaming Markdown docs,
  directories, fixtures, scripts, or mixed repo surfaces where references
  should update in one batch. Best when a move map can be reviewed first
  and the desired behavior is "compute a virtual after-tree, rewrite safe
  references once, apply with git-aware moves, then verify."
not_for: |
  Domain-concept terminology renames in prose (use /rename-concept).
  Python/TypeScript import refactors unless a language adapter has been
  explicitly added and enabled. Large behavior-changing subsystem splits
  that need characterization tests and human Phase 4 sign-off (use
  /refactor-subsystem). Blind global find-and-replace.
language: python
framework: any
---

# /move-path

You are the orchestrator for safe batched path moves. The deterministic
script owns filesystem moves, path normalization, reference resolution,
patch generation, and verification. Your job is to prepare or inspect the
plan, run dry-run first, review uncertainty buckets, then apply only when
the report is clean enough for the intended change.

## Core Contract

The script computes a **virtual after-tree** before touching disk:

```text
plan -> virtual after-tree -> rewrite refs against after-tree -> apply moves + patches -> verify
```

It updates references by resolved identity, not by hopeful text
replacement. A Markdown link is auto-updated only when its target resolves
to a file or directory being moved. Ambiguous prose and unsupported import
forms are reported, not rewritten.

## Commands

```bash
python3 .claude/skills/move-path/scripts/move_path.py --plan moves.yml --dry-run
python3 .claude/skills/move-path/scripts/move_path.py --plan moves.yml --apply
python3 .claude/skills/move-path/scripts/move_path.py --plan moves.yml --check
python3 .claude/skills/move-path/scripts/audit_path_residue.py --plan moves.yml
python3 .claude/skills/move-path/scripts/audit_path_residue.py --plan moves.yml --exclude 'source-materials/input-bundles/**'
```

Useful options:

- `--project-root DIR` — default is git toplevel, else cwd.
- `--report-dir DIR` — default `.engineering/local/move-path/`.
- `--stage` — stage moved and rewritten paths after apply.
- `--allow-dirty-touched` — bypass dirty touched-file refusal.
- `--json` — print the JSON report to stdout.

## Plan Shape

```yaml
version: 1

moves:
  - id: eval-contracts
    from: kb/evals/eval-contracts.md
    to: specs/contracts/reliability/eval-contracts.md

  - id: schemas-dir
    from: kb/schemas/
    to: specs/contracts/schemas/
    mode: directory

reference_scope:
  include:
    - "**/*.md"
    - "**/*.yml"
    - "**/*.yaml"
    - "**/*.json"
  exclude:
    - ".git/**"
    - ".engineering/local/**"
    - "datasets/**"
    - "inputs-*/**"
    - "claude-logs/**"

rewrite:
  markdown_links: update
  markdown_images: update
  html_href_src: update
  backtick_paths: update
  exact_text_paths: suggest
  code_imports: ignore

safety:
  require_clean_touched_files: true
  fail_on_broken_links: true
  fail_on_blocked: true
```

## Confidence Buckets

- `auto` — resolved identity, safe to update.
- `suggest` — likely path/reference, requires review.
- `ignore` — outside configured scope or explicitly unsupported.
- `blocked` — unsafe ambiguity; apply fails unless the plan relaxes the
  relevant safety gate.

For directory moves, `exact_text_paths: update` also rewrites nested
plain-text path tokens such as `inputs-1/kb` when they are rooted under
the moved directory. Use `suggest` first when historical prose may be
describing the old layout rather than linking to the current identity.

## Workflow

1. Write or inspect a move plan. Include many moves in one plan when the
   intended transform is one conceptual batch.
2. Run `--dry-run`.
3. Read `.engineering/local/move-path/report.md` and
   `.engineering/local/move-path/report.json`.
4. Resolve `blocked` findings. Review `suggest` findings.
5. Run `--apply` only after the dry-run report matches the intended
   transform.
6. Run `--check` after manual follow-up edits or before commit.
7. When moved areas include machine-readable manifests, scripts, command
   examples, generated reports, or absolute local paths, run
   `audit_path_residue.py` and review its assumptions, samples, and spot
   checks.

## Git Rules

- Tracked paths move with `git mv`.
- Untracked paths move with filesystem rename and are reported as
  untracked.
- Case-only renames use a temporary path internally.
- Dirty touched files block apply by default.
- `--stage` stages changed old and new paths after apply; otherwise the
  tool leaves the index alone.
- After manual reference or signpost edits, run `--check` before commit. If
  `--stage` was not used, stage the move and rewrite surfaces together so the
  commit is a coherent topology change.
- Keep generated reports under `.engineering/local/move-path/` or clean them
  before handoff. Reports are review artifacts, not source files, unless the
  project explicitly wants to retain them.
- Review low-similarity renames with `git diff -M10 --find-renames` when
  content rewrites make Git show a moved file as delete/add at the default
  threshold.

## Operational Residue Audit

Use `scripts/audit_path_residue.py` when a move touches operational artifacts
that may store paths outside Markdown links: JSON/CSV manifests, lockfiles,
scripts, notebooks, generated reports, command examples, or copied absolute
paths. The helper scans the move plan's reference scope for old relative,
root-relative, absolute POSIX, and Windows-style path spellings, then writes:

- assumptions that define what the scan can and cannot prove;
- machine-readable findings in
  `.engineering/local/move-path/path-residue-audit.json`;
- a Markdown review report with sampled contexts and spot checks showing
  whether old and new paths exist.

Use repeated `--exclude` flags for known preserved provenance areas when the
goal is operational cleanup rather than source-history rewriting.

When a repeatable residue pattern appears during manual cleanup, prefer adding
or refining a deterministic micro-tool here over relying on an LLM-only sweep.
Keep the helper narrow, fixture-backed, and explicit about what would disprove
its assumptions.

## AI Review

Keep the core deterministic. Use AI review only around the report:

- Are any moves conceptually wrong?
- Are skipped or suggested references likely real breakages?
- Is the scope too broad for one commit?
- Are source snapshots or historical records intentionally excluded?

Do not let an LLM perform unstructured rewrites. If the script cannot
prove identity, the reference is a human review item.
