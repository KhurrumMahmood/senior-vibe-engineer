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
```

Useful options:

- `--project-root DIR` — default is git toplevel, else cwd.
- `--report-dir DIR` — default `.move-path/`.
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
3. Read `.move-path/report.md` and `.move-path/report.json`.
4. Resolve `blocked` findings. Review `suggest` findings.
5. Run `--apply` only after the dry-run report matches the intended
   transform.
6. Run `--check` after manual follow-up edits or before commit.

## Git Rules

- Tracked paths move with `git mv`.
- Untracked paths move with filesystem rename and are reported as
  untracked.
- Case-only renames use a temporary path internally.
- Dirty touched files block apply by default.
- `--stage` stages changed old and new paths after apply; otherwise the
  tool leaves the index alone.

## AI Review

Keep the core deterministic. Use AI review only around the report:

- Are any moves conceptually wrong?
- Are skipped or suggested references likely real breakages?
- Is the scope too broad for one commit?
- Are source snapshots or historical records intentionally excluded?

Do not let an LLM perform unstructured rewrites. If the script cannot
prove identity, the reference is a human review item.
